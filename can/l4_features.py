"""WP2 S6: causal stream features, window k-th-largest alerts and the L4 Layer (learned timing / payload models).

Purpose: retrain the v2 CAN models (../codes_v2/can/features.py, train.py, road_windows.py; logic copied, features
vectorised) inside the v3 harness. Features are causal: a frame only uses frames that came before it in the recorded
order (never re-sorted; the sign of dt is never used: gaps are clipped at 0, frames.dt_clipped).
Features (FEATURES): id, dlc, b0..b7, dt_prev, dt_id, id_known, dt_id_ratio, n_id_win (same ID in the previous 100
frames), n_unique_win (distinct IDs in the previous 100 frames), bytes_changed (bytes differing from the previous frame
of the same ID, NaN for the first frame of an ID), same_payload. TIMING = v2 "behaviour" set (no raw ID, no payload
bytes), PAYLOAD = the full set.
Window alert (v2 road_windows): "count of frames above t_f >= k" is the same as "k-th largest frame score > t_f"; so the
window raw score is the k-th largest frame score of the window (rule "all") or the maximum over IDs of the k-th largest
score inside the ID (rule "maxid"); the threshold is the tie-safe budget threshold on clean validation windows.
Inputs: t, id, dlc, B (n, 8 int16, -1 beyond the DLC). Outputs: raw feature arrays, float32 matrices, window tables.
References: Song et al. 2016 / Seo et al. 2018 (Car-Hacking), Verma et al. 2022 (ROAD), codes_v2/can.
"""
import numpy as np

from can.frames import dt_clipped
from can.l1 import CanRule, window_reduce
from common.metrics import budget_threshold

WIN = 100
PAYLOAD_COLS = [f"b{i}" for i in range(8)]
FEATURES = ["id", "dlc"] + PAYLOAD_COLS + ["dt_prev", "dt_id", "id_known", "dt_id_ratio", "n_id_win",
                                           "n_unique_win", "bytes_changed", "same_payload"]
TIMING = [c for c in FEATURES if c != "id" and c not in PAYLOAD_COLS]
RULES = ["all", "maxid"]
KS = [1, 2, 3, 5, 10, 20, 50]
FLOOR = -50.0                 # window score when fewer than k frames (below any log-odds margin)
VARIANTS = [(r, k) for r in RULES for k in KS]


# ------------------------------------------------------------------ raw (period-independent) features
def stream_raw(t, ids, dlc, B) -> dict:
    """dt_prev, dt_id (float32, NaN where undefined), n_id (int16), n_uniq (int16), bchg (int8, -1 = no previous frame
    of this ID). B: (n, 8) int16 with -1 beyond the DLC. Frames in recorded order."""
    t = np.asarray(t, np.float64)
    ids = np.asarray(ids)
    n = len(t)
    order = np.argsort(ids, kind="stable")
    ids_s = ids[order]
    first = np.r_[True, ids_s[1:] != ids_s[:-1]] if n else np.zeros(0, bool)
    d = dt_clipped(t[order])
    d[first] = np.nan
    dt_id = np.empty(n, np.float32)
    dt_id[order] = d
    prev_s = np.where(first, -1, np.r_[-1, order[:-1]]).astype(np.int64) if n else np.zeros(0, np.int64)
    pv = np.empty(n, np.int64)
    pv[order] = prev_s
    gid = np.cumsum(first) - 1
    keys = gid.astype(np.int64) * (n + 1) + order
    lo = np.searchsorted(keys, gid.astype(np.int64) * (n + 1) + np.maximum(order - WIN, 0), side="left")
    n_id = np.empty(n, np.int16)
    n_id[order] = (np.arange(n) - lo).astype(np.int16)
    j = np.arange(n, dtype=np.int64)
    start = np.where(pv >= 0, np.maximum(j + 1, pv + WIN + 1), j + 1)
    end = j + WIN
    size = n + WIN + 2
    cs = np.cumsum(np.bincount(start, minlength=size)[:size] - np.bincount(end + 1, minlength=size)[:size])
    n_uniq = cs[:n].astype(np.int16)
    bchg = np.full(n, -1, np.int8)
    has = np.flatnonzero(pv >= 0)
    B = np.asarray(B)
    for a in range(0, len(has), 2_000_000):
        h = has[a:a + 2_000_000]
        bchg[h] = (B[h] != B[pv[h]]).sum(axis=1).astype(np.int8)
    dt_prev = dt_clipped(t).astype(np.float32)
    return {"dt_prev": dt_prev, "dt_id": dt_id, "n_id": n_id, "n_uniq": n_uniq, "bchg": bchg}


class PeriodBuilder:
    """Median gap per ID from clean frames (v2: id_period = median of positive per-ID gaps)."""

    def __init__(self, sub_max: int = 50000):
        self.dt, self.sub_max = {}, sub_max

    def add(self, ids, dt_id):
        ids = np.asarray(ids)
        dt_id = np.asarray(dt_id)
        ok = np.isfinite(dt_id) & (dt_id > 0)
        ids, dt_id = ids[ok], dt_id[ok]
        if len(ids) == 0:
            return self
        o = np.argsort(ids, kind="stable")
        s_id, s_dt = ids[o], dt_id[o]
        st = np.flatnonzero(np.r_[True, s_id[1:] != s_id[:-1]])
        en = np.r_[st[1:], len(s_id)]
        for a, b in zip(st, en):
            x = s_dt[a:b]
            if len(x) > self.sub_max:
                x = x[:: int(np.ceil(len(x) / self.sub_max))]
            self.dt.setdefault(int(s_id[a]), []).append(x.astype(np.float64))
        return self

    def finish(self) -> dict:
        return {i: float(np.median(np.concatenate(v))) for i, v in sorted(self.dt.items())}


def period_arrays(period: dict):
    ids = np.array(sorted(period), np.int64)
    return ids, np.array([period[int(i)] for i in ids], np.float64)


def feature_matrix(raw: dict, ids, dlc, B, period: dict, cols=FEATURES) -> np.ndarray:
    """float32 matrix (n, len(cols)) in the order of `cols`. period: {id: median gap}."""
    ids = np.asarray(ids)
    n = len(ids)
    pid, pval = period_arrays(period) if period else (np.zeros(0, np.int64), np.zeros(0))
    if len(pid):
        pos = np.minimum(np.searchsorted(pid, ids), len(pid) - 1)
        known = pid[pos] == ids
        per = np.where(known, pval[pos], np.nan)
    else:
        known, per = np.zeros(n, bool), np.full(n, np.nan)
    B = np.asarray(B)
    dlc = np.asarray(dlc)
    ex = np.arange(8)[None, :] < dlc[:, None]
    bchg = raw["bchg"].astype(np.float32)
    bchg[raw["bchg"] < 0] = np.nan
    cols_d = {"id": ids, "dlc": dlc, "dt_prev": raw["dt_prev"], "dt_id": raw["dt_id"],
              "id_known": known, "dt_id_ratio": raw["dt_id"] / per, "n_id_win": raw["n_id"],
              "n_unique_win": raw["n_uniq"], "bytes_changed": bchg,
              "same_payload": np.where(np.isnan(bchg), np.nan, (bchg == 0).astype(np.float32))}
    X = np.empty((n, len(cols)), np.float32)
    for k, c in enumerate(cols):
        if c in cols_d:
            X[:, k] = cols_d[c]
        else:
            i = int(c[1:])
            X[:, k] = np.where(ex[:, i], B[:, i], -1)
    return X


# ------------------------------------------------------------------ window k-th largest
def window_kth(F: dict, score, ids, variants=VARIANTS) -> np.ndarray:
    """(n_windows, len(variants)) float32 window raw scores. F needs wo / ws (can.l1.add_window_index).
    Windows with fewer than k frames (rule all) / no ID with k frames (rule maxid) get FLOOR."""
    wo, ws = F["wo"], F["ws"]
    nw = len(ws)
    ln = np.diff(np.r_[ws, len(wo)])
    seg = np.repeat(np.arange(nw), ln)
    s = np.asarray(score, np.float32)[wo]
    lo_, hi_ = float(s.min()) if len(s) else 0.0, float(s.max()) if len(s) else 1.0
    u = (s.astype(np.float64) - lo_) / (hi_ - lo_ + 1e-9)            # rank key in [0, 1]; scores may be margins
    out = np.full((nw, len(variants)), FLOOR, np.float32)
    ks_all = [(vi, k) for vi, (r, k) in enumerate(variants) if r == "all"]
    ks_id = [(vi, k) for vi, (r, k) in enumerate(variants) if r == "maxid"]
    if ks_all:
        o = np.argsort(seg.astype(np.float64) + (1.0 - u) * 0.999)
        ss = s[o]
        for vi, k in ks_all:
            ok = ln >= k
            out[ok, vi] = ss[ws[ok] + k - 1]
    if ks_id:
        uid, code = np.unique(np.asarray(ids)[wo], return_inverse=True)
        g = seg.astype(np.int64) * len(uid) + code
        o = np.argsort(g.astype(np.float64) + (1.0 - u) * 0.999)
        gs, ss, sg = g[o], s[o], seg[o]
        st = np.flatnonzero(np.r_[True, gs[1:] != gs[:-1]])
        rank = np.arange(len(gs)) - np.repeat(st, np.diff(np.r_[st, len(gs)]))
        for vi, k in ks_id:
            m = rank == k - 1
            col = np.full(nw, FLOOR, np.float32)
            np.maximum.at(col, sg[m], ss[m])
            out[:, vi] = col
    return out


def frame_to_window_max(F, score):
    return window_reduce(F, score)


# ------------------------------------------------------------------ Layer
class L4Layer(CanRule):
    """Learned CAN layer (XGBoost). kind supervised, layer L4. samples = feature dict F (can.l1.make_features with
    windows) with F['X'] = float32 feature matrix (already period-resolved). unit 'frame': probability of attack;
    unit 'window': window_kth score for the chosen variant."""
    layer_id = "L4"
    kind = "supervised"
    needs_attack_data = True
    why = "a model trained on labelled attacks finds this window unlike normal traffic"

    def __init__(self, model=None, name="can.l4_timing", cols=TIMING, unit="frame", variant=(RULES[0], 1)):
        super().__init__(None, unit)
        self.model, self.name, self.cols, self.variant = model, name, list(cols), tuple(variant)

    def frame_raw(self, F):
        if "p" in F:
            return F["p"]
        return self.model.predict(F["X"], output_margin=True)

    def raw_scores(self, F):
        p = np.asarray(self.frame_raw(F), np.float64)
        if self.unit == "frame":
            return p
        return window_kth(F, p, F["id"], [self.variant])[:, 0].astype(np.float64)

    def clone(self, unit):
        return L4Layer(self.model, self.name, self.cols, unit, self.variant)


def tie_safe(clean_raw, budget=0.01) -> float:
    return budget_threshold(np.asarray(clean_raw, float), budget)
