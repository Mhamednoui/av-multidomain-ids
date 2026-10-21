"""WP2 S4: L2b signal-physics layer for CAN (ROAD), learned from attack-free decoded signals only.

Purpose: catch masquerade attacks (same ID, same period, plausible bytes) that specification rules (L1) and timing (L2a) cannot see.
The attacker overwrites one signal; the rest of the car keeps telling the truth. L2b checks, causally and frame by frame, the decoded
signals of anonymized.dbc (can/signals.py) against what the vehicle did in attack-free captures:
  value   continuous signal outside [min, max] of the training traffic (excess / span); discrete signal value seen < ms times.
  rate    continuous signal jumps by more than the largest training step between two frames of the same ID (excess over that step);
          discrete signal makes a transition (a -> b) seen < ms times. Noise/counter-like signals (change fraction > 0.9 and
          >= half of 2^len values) have no rate check.
  linear  physical relation between two continuous signals (wheel speeds vs speedometer, ...): pairs with |corr| >= rho on a 0.05 s
          sample-and-hold grid, OLS y = a x + b, violation = |residual| / largest training residual - 1.
  joint   state consistency between two slowly varying discrete signals (reverse-light bit vs gear / direction state ...): pairs with
          normalised mutual information >= 0.7; a combination seen < ms_joint grid samples is a violation.
Everything is computed from summable sufficient statistics (CapStats) so a model can be refit on any set of captures
(leave-one-capture-out). Each check carries a surprise weight -log2(violation rate on held-out clean frames) learned by LOCO (session-specific
states that fire in every held-out capture get no weight); frame score = max over violated checks, window = max over frames.
Inputs: tm (running-max time), IDs, decoded signals (can.signals.decode_all). Outputs: float32 frame raw score per type.
References: Verma et al. 2022 (ROAD); Muter & Asaj 2011 (entropy), Marchetti & Stabili 2017 (sequence/range), Wasicek et al.
2017 and Kang et al. 2018 (signal-level plausibility for in-vehicle intrusion detection).
"""
import json

import numpy as np

from can import signals as S
from can.l1 import CanRule, window_reduce
from common.config import RESULTS

GRID_DT = 0.05
DISC_MAX = 32
TRANS_CAP = 40
CODE_N = 16
TYPES = ["value", "rate", "linear", "joint"]
MAX_PAIRS = 400
MAX_JOINT = 1500
OFF = 32768
MIN_ENT = 0.15      # bits: a discrete signal must spend >= ~3% of the time in a minority state to take part in a joint check


class Catalog:
    """Signal list and label-free candidate sets (from train-ambient statistics in results/WP2/s4_signal_stats.json)."""

    def __init__(self, dbc: dict, stats_path=RESULTS / "WP2" / "s4_signal_stats.json"):
        self.dbc = dbc
        self.keys = [(i, k) for i in sorted(dbc) for k in range(len(dbc[i]))]
        self.j = {key: n for n, key in enumerate(self.keys)}
        st = json.load(open(stats_path))
        self.cont, self.disc = [], []
        for name, v in st.items():
            i, k = name.split(".")
            key = (int(i, 16), int(k))
            if v["nuniq"] >= 40 and v["frac_inc1"] < 0.9 and v["len"] >= 6:
                self.cont.append(key)
            elif 2 <= v["nuniq"] <= 8 and v["frac_changing"] < 0.05:
                self.disc.append(key)
        self.cont_ix = {key: n for n, key in enumerate(self.cont)}
        self.disc_ix = {key: n for n, key in enumerate(self.disc)}
        self.ids = sorted(dbc)


def held(tm_rows, col, tq):
    """Value of a signal held at query times (last frame with time <= tq); NaN before the first frame."""
    pos = np.searchsorted(tm_rows, tq, side="right") - 1
    out = np.full(len(tq), np.nan)
    ok = pos >= 0
    out[ok] = col[pos[ok]]
    return out


# ------------------------------------------------------------------ sufficient statistics
class CapStats:
    """Summable statistics of one attack-free capture."""

    def __init__(self, name):
        self.name = name


def capture_stats(name: str, tm, dec: dict, cat: Catalog) -> CapStats:
    ns = len(cat.keys)
    st = CapStats(name)
    st.n, st.nchg, st.dmax = np.zeros(ns), np.zeros(ns), np.zeros(ns)
    st.vals, st.trans = [None] * ns, {}
    g = np.arange(tm[0] + 1.0, tm[-1], GRID_DT)
    st.Gc = np.full((len(g), len(cat.cont)), np.nan, np.float32)
    st.Gd = np.full((len(g), len(cat.disc)), np.nan, np.float32)
    for i, (rows, V) in dec.items():
        tr = tm[rows]
        for k in range(V.shape[1]):
            j, x = cat.j[(i, k)], V[:, k]
            u, c = np.unique(x, return_counts=True)
            st.vals[j] = (u, c)
            d = np.abs(np.diff(x))
            st.n[j], st.nchg[j] = len(x), int((d > 0).sum())
            st.dmax[j] = d.max() if len(d) else 0.0
            if len(u) <= TRANS_CAP and len(x) > 1 and cat.dbc[i][k].length <= 16:
                key = (x[:-1].astype(np.int64) + OFF) * 65536 + (x[1:].astype(np.int64) + OFF)
                st.trans[j] = np.unique(key, return_counts=True)
            if (i, k) in cat.cont_ix:
                st.Gc[:, cat.cont_ix[(i, k)]] = held(tr, x, g)
            elif (i, k) in cat.disc_ix:
                st.Gd[:, cat.disc_ix[(i, k)]] = held(tr, x, g)
    ok = ~np.isnan(st.Gc).any(1)
    X = st.Gc[ok].astype(np.float64)
    st.N, st.S, st.XtX = len(X), X.sum(0), X.T @ X
    return st


def build_codemaps(stats_list, cat: Catalog) -> list:
    """Per discrete candidate: sorted array of at most CODE_N-1 values (most frequent first, then sorted) -> code."""
    maps = []
    for key in cat.disc:
        j = cat.j[key]
        u = np.concatenate([s.vals[j][0] for s in stats_list])
        c = np.concatenate([s.vals[j][1] for s in stats_list])
        uu, inv = np.unique(u, return_inverse=True)
        cc = np.bincount(inv, weights=c)
        keep = np.argsort(-cc, kind="stable")[: CODE_N - 1]
        maps.append(np.sort(uu[keep]))
    return maps


def to_codes(x, vmap):
    """Float values -> int8 codes: index in vmap, CODE_N-1 for unseen values, -1 for NaN."""
    x = np.asarray(x, np.float64)
    out = np.full(len(x), CODE_N - 1, np.int8)
    pos = np.minimum(np.searchsorted(vmap, x), len(vmap) - 1)
    hit = vmap[pos] == x
    out[hit] = pos[hit]
    out[np.isnan(x)] = -1
    return out


def grid_codes(st: CapStats, maps) -> np.ndarray:
    return np.stack([to_codes(st.Gd[:, n], maps[n]) for n in range(st.Gd.shape[1])], axis=1)


# ------------------------------------------------------------------ model
class Model:
    """Fitted envelope. Build with fit_model."""


def _pooled(stats_list, j):
    u = np.concatenate([s.vals[j][0] for s in stats_list if s.vals[j] is not None])
    c = np.concatenate([s.vals[j][1] for s in stats_list if s.vals[j] is not None])
    uu, inv = np.unique(u, return_inverse=True)
    return uu, np.bincount(inv, weights=c)


def fit_model(stats_list, codes_list, cat: Catalog, maps, rho: float, ms: int) -> Model:
    """stats_list: CapStats of the fit captures; codes_list: their grid_codes (same order)."""
    M = Model()
    M.rho, M.ms, M.cat = rho, ms, cat
    ns = len(cat.keys)
    M.cls = np.full(ns, -1, np.int8)            # -1 absent, 0 const, 1 disc, 2 cont
    M.lo, M.hi = np.zeros(ns), np.zeros(ns)
    M.skip_rate = np.zeros(ns, bool)
    M.L = np.ones(ns)
    M.allowed, M.trans_ok = {}, {}
    for key, j in cat.j.items():
        if not any(s.vals[j] is not None for s in stats_list):
            continue
        uu, cc = _pooled(stats_list, j)
        n = sum(s.n[j] for s in stats_list)
        nchg = sum(s.nchg[j] for s in stats_list)
        ln = cat.dbc[key[0]][key[1]].length
        M.lo[j], M.hi[j] = uu[0], uu[-1]
        M.cls[j] = 0 if len(uu) == 1 else (1 if len(uu) <= DISC_MAX else 2)
        M.L[j] = max(max(s.dmax[j] for s in stats_list), 1.0)
        M.skip_rate[j] = ln >= 4 and nchg / max(n, 1) > 0.9 and len(uu) >= 0.5 * 2 ** ln
        if M.cls[j] <= 1:
            M.allowed[j] = uu[cc >= ms]
            tk = [s.trans[j] for s in stats_list if j in s.trans]
            if tk:
                u = np.concatenate([a for a, _ in tk])
                c = np.concatenate([b for _, b in tk])
                u2, inv = np.unique(u, return_inverse=True)
                c2 = np.bincount(inv, weights=c)
                M.trans_ok[j] = u2[c2 >= ms]
    # linear relations on the grid
    N = sum(s.N for s in stats_list)
    S1 = sum(s.S for s in stats_list)
    XtX = sum(s.XtX for s in stats_list)
    mu = S1 / N
    cov = XtX / N - np.outer(mu, mu)
    sd = np.sqrt(np.maximum(np.diag(cov), 0))
    with np.errstate(invalid="ignore", divide="ignore"):
        corr = cov / np.outer(sd, sd)
    iu = np.triu_indices(len(cat.cont), 1)
    cv = np.abs(corr[iu])
    cv[~np.isfinite(cv)] = 0
    sel = np.flatnonzero(cv >= rho)
    sel = sel[np.argsort(-cv[sel], kind="stable")][:MAX_PAIRS]
    M.lin = []
    Gc = np.concatenate([s.Gc for s in stats_list])
    for p in sel:
        a, b = int(iu[0][p]), int(iu[1][p])
        al = cov[a, b] / cov[a, a]
        be = mu[b] - al * mu[a]
        r = np.abs(Gc[:, b] - al * Gc[:, a] - be)
        R = max(float(np.nanmax(r)), 1.0)
        M.lin.append((cat.cont[a], cat.cont[b], float(al), float(be), R, float(cv[p])))
    # joint support between slowly varying discrete signals
    C = np.concatenate(codes_list)
    C, w = np.unique(C, axis=0, return_counts=True)       # slowly varying states: few distinct grid rows
    w = w.astype(np.float64)
    nd = C.shape[1]
    M.joint = []
    ent = np.zeros(nd)
    for a in range(nd):
        m = np.bincount(C[C[:, a] >= 0, a], weights=w[C[:, a] >= 0], minlength=CODE_N)
        p = m / max(m.sum(), 1)
        ent[a] = -(p[p > 0] * np.log2(p[p > 0])).sum()
    cand = []
    msj = 1 if ms <= 1 else 10
    Ci = C.astype(np.int64)
    for a in range(nd):
        if ent[a] < MIN_ENT:
            continue
        for b in range(a + 1, nd):
            if ent[b] < MIN_ENT:
                continue
            ok = (Ci[:, a] >= 0) & (Ci[:, b] >= 0)
            cnt = np.bincount(Ci[ok, a] * CODE_N + Ci[ok, b], weights=w[ok], minlength=CODE_N * CODE_N).reshape(CODE_N, CODE_N)
            pj = cnt / max(cnt.sum(), 1)
            pa, pb = pj.sum(1), pj.sum(0)
            nz = pj > 0
            mi = (pj[nz] * np.log2(pj[nz] / np.outer(pa, pb)[nz])).sum()
            nmi = mi / min(ent[a], ent[b])
            if nmi >= 0.7:
                cand.append((nmi, a, b, cnt >= msj))
    cand.sort(key=lambda z: -z[0])
    M.joint = [(cat.disc[a], cat.disc[b], a, b, allowed, float(nmi)) for nmi, a, b, allowed in cand[:MAX_JOINT]]
    M.maps = maps
    return M


def model_summary(M: Model) -> dict:
    name = lambda k: f"{k[0]:#x}.{k[1]}"
    return {"rho": M.rho, "ms": M.ms, "n_signals": int((M.cls >= 0).sum()),
            "classes": {"const": int((M.cls == 0).sum()), "disc": int((M.cls == 1).sum()), "cont": int((M.cls == 2).sum())},
            "rate_checked": int(((M.cls == 2) & ~M.skip_rate).sum()),
            "linear_pairs": len(M.lin), "joint_pairs": len(M.joint),
            "linear_top": [[name(a), name(b), round(al, 4), round(be, 2), round(R, 1), round(c, 4)] for a, b, al, be, R, c in M.lin[:15]],
            "joint_top": [[name(a), name(b), round(nmi, 3)] for a, b, _, _, _, nmi in M.joint[:15]]}


# ------------------------------------------------------------------ scoring
TRACE = None        # set to a dict to record, per check, (frames evaluated, frames violating)
WEIGHTS = None      # set to {check tag: surprise weight}; scores are then weights x (1 + log1p(excess) / 10)
W_DEFAULT = 6.6     # checks never seen in the LOCO traces: weight of a check that fires on 1% of clean frames


def check_weight(viol: int, n: int) -> float:
    """Surprise (bits) of a violation of a check that fired on `viol` of `n` held-out clean frames (add-one smoothing)."""
    return float(-np.log2((viol + 1.0) / (n + 2.0)))


JOINT_ONLY = None   # optional set of signal keys: joint checks must involve one of them (post-verdict revision R1, validation only)
CONT_ONLY = False   # S5 "relations only" default (decision 2026-10-22): value / rate checks on continuous signals only, no generic discrete checks
MUTE_T0 = None      # seconds: a check that violates during the first MUTE_T0 s of a capture is session-specific and muted for that
_TM = None          # capture (in-situ baseline, causal: the decision uses only frames up to MUTE_T0); frames before it are not scored


def _put(out, rows, v, tag=None):
    if MUTE_T0 is not None and tag is not None:
        late = _TM[rows] > _TM[0] + MUTE_T0
        v = np.asarray(v)
        v = np.zeros(len(v), v.dtype) if (v[~late] > 0).any() else np.where(late, v, 0)
    if TRACE is not None and tag is not None:
        TRACE[tag] = (int(late.sum()) if MUTE_T0 is not None else len(v), int((np.asarray(v) > 0).sum()))
    if WEIGHTS is not None and tag is not None:
        v = np.where(np.asarray(v) > 0, WEIGHTS.get(tag, W_DEFAULT) * (1.0 + np.log1p(np.asarray(v, np.float64)) / 10.0), 0.0)
    out[rows] = np.maximum(out[rows], v.astype(np.float32))


def score_frames(M: Model, tm, dec: dict, n: int, only=None) -> dict:
    """Raw per-type scores (float32, length n; 0 = inside the learned envelope) for one capture, frames in recorded order."""
    global _TM
    _TM = tm
    cat = M.cat
    out = {t: np.zeros(n, np.float32) for t in TYPES}
    for i, (rows, V) in dec.items():
        for k in range(V.shape[1]):
            j = cat.j[(i, k)]
            c = M.cls[j]
            if c < 0 or (CONT_ONLY and c != 2):
                continue
            x = V[:, k]
            if c == 2:
                span = max(M.hi[j] - M.lo[j], 1.0)
                _put(out["value"], rows, np.maximum(np.maximum(M.lo[j] - x, x - M.hi[j]), 0) / span, ("value", j))
                if not M.skip_rate[j] and len(x) > 1:
                    d = np.r_[0.0, np.abs(np.diff(x))]
                    _put(out["rate"], rows, np.maximum(d / M.L[j] - 1.0, 0), ("rate", j))
            else:
                al = M.allowed[j]
                if len(al):
                    bad = al[np.minimum(np.searchsorted(al, x), len(al) - 1)] != x
                else:
                    bad = np.ones(len(x), bool)
                _put(out["value"], rows, bad.astype(np.float32), ("value", j))
                if j in M.trans_ok and len(x) > 1:
                    tk = M.trans_ok[j]
                    key = (x[:-1].astype(np.int64) + OFF) * 65536 + (x[1:].astype(np.int64) + OFF)
                    q = np.minimum(np.searchsorted(tk, key), max(len(tk) - 1, 0))
                    badt = (tk[q] != key) if len(tk) else np.ones(len(key), bool)
                    _put(out["rate"], rows[1:], badt.astype(np.float32), ("rate", j))
    for ka, kb, al, be, R, _ in M.lin:
        if ka[0] not in dec or kb[0] not in dec:
            continue
        ra, Va = dec[ka[0]]
        rb, Vb = dec[kb[0]]
        rq = ra if ka[0] == kb[0] else np.union1d(ra, rb)
        tq = tm[rq]
        va = held(tm[ra], Va[:, ka[1]], tq)
        vb = held(tm[rb], Vb[:, kb[1]], tq)
        r = np.abs(vb - al * va - be)
        ok = np.isfinite(r)
        _put(out["linear"], rq[ok], np.maximum(r[ok] / R - 1.0, 0), ("linear", ka, kb))
    for ka, kb, a, b, allowed, _ in M.joint:
        if ka[0] not in dec or kb[0] not in dec:
            continue
        if JOINT_ONLY is not None and ka not in JOINT_ONLY and kb not in JOINT_ONLY:
            continue
        ra, Va = dec[ka[0]]
        rb, Vb = dec[kb[0]]
        rq = ra if ka[0] == kb[0] else np.union1d(ra, rb)
        tq = tm[rq]
        ca = to_codes(held(tm[ra], Va[:, ka[1]], tq), M.maps[a])
        cb = to_codes(held(tm[rb], Vb[:, kb[1]], tq), M.maps[b])
        ok = (ca >= 0) & (cb >= 0)
        viol = ~allowed[ca[ok].astype(np.int64), cb[ok].astype(np.int64)]
        _put(out["joint"], rq[ok], viol, ("joint", ka, kb))
    return out


def window_starts(tm):
    w = np.floor(tm).astype(np.int64)
    return np.r_[0, np.flatnonzero(np.diff(w)) + 1]


def window_max(arr, starts):
    return np.maximum.reduceat(arr, starts)


class SignalPhysicsLayer(CanRule):
    """L2b as a Layer. samples = feature dict F (can.l1.make_features with windows) with F['l2b_raw'] = per-type weighted
    check scores (score_frames with WEIGHTS set); calibrate_from_raw on LOCO clean frames / windows gives the 1% thresholds."""
    name = "can.l2b_signals"
    layer_id = "L2"
    kind = "physics"
    why = "decoded signals leave the envelope or the physical relations learned from attack-free driving"

    def __init__(self, unit="frame"):
        super().__init__(None, unit)

    def frame_raw(self, F):
        return combine(F["l2b_raw"])

    def clone(self, unit):
        return SignalPhysicsLayer(unit)


def combine(raws: dict) -> np.ndarray:
    """Frame score = max over the check types of the weighted violation scores (WEIGHTS set during scoring)."""
    return np.max(np.stack([raws[t] for t in TYPES]), axis=0).astype(np.float64)
