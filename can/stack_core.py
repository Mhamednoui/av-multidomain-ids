"""WP2 S7: the CAN stack core: fitted model container and per-window raw scores of ONE capture (ROAD).

Purpose: one code path for the experiments (leave-one-capture-out folds, validation, test) and the deployable domain (can/domain.py), so there
is no train/serve skew. A `RoadModels` object holds what is learned from attack-free traffic only:
  L1   Profile of can/l1.py (ID allow-list, DLC per ID, periods + tolerances, floor ID)
  L2b  can/l2b_signals.Model (continuous-signal linear relations, range / rate limits, joint reverse-bit vs gear states) + surprise weights
  L3c  ridge per-signal predictors (can/l3_predictors.py), several designs (name -> L3cModel)
  L3d  lag-aware gear-vs-reverse-light state predictor
`window_raws(models, U)` turns a capture (t, id, dlc, payload bytes) into 1 s window raw scores of every layer. Windows are the integer seconds of the
running-max clock (`tm`); a window is scored when the 0.05 s grid of the L3 layers exists (from 1 s after the first frame). Causal: the score of a
window uses frames up to its end; sample-and-hold grids and lags look backwards only.
Inputs: UnitData (arrays), RoadModels. Outputs: dict of per-window arrays (sec, w_end, ok, l1_*, l2b_*, l3c_*, l3d).
References: Verma et al. 2022 (ROAD); can/l1.py, can/l2b_signals.py, can/l3_predictors.py (the layers) and their reports WP2_S2 / S4 / S5.
"""
from dataclasses import dataclass

import numpy as np

from can import l1 as L
from can import l2b_signals as Z
from can import l3_predictors as P
from can import signals as S

DBC = S.parse_dbc()
CAT = Z.Catalog(DBC)
DISC = [(0xD0, 2), (0x295, 0), (0xC0, 0), (0x274, 14)]      # reverse bit, 3 gear copies (L3d)
L1_NAMES = [c.name for c in L.RULE_CLASSES]
L2B_TYPES = Z.TYPES
JOINT_KEYS = {(0xD0, 2)}                                   # relations-only joint check: pairs that involve the reverse-light bit
SKIP_RMIN = (0.0, 0.9)


@dataclass
class UnitData:
    """One capture (or a time slice of one) in recorded order. B = payload bytes uint8 (n x 8). label = 1 injected."""
    name: str
    t: np.ndarray
    id: np.ndarray
    dlc: np.ndarray
    B: np.ndarray
    label: np.ndarray

    @property
    def tm(self):
        return np.maximum.accumulate(self.t)

    def __len__(self):
        return len(self.t)


def slice_unit(U: UnitData, i0: int, i1: int, name: str) -> UnitData:
    """Frames [i0, i1) as an own capture (time re-based to 0)."""
    t = U.t[i0:i1]
    return UnitData(name, t - t[0], U.id[i0:i1], U.dlc[i0:i1], U.B[i0:i1], U.label[i0:i1])


def lead_clean(U: UnitData, margin: float = 1.0) -> np.ndarray:
    """Attack-free frames: everything if no injected frame, else the frames more than `margin` s before the first injected one."""
    idx = np.flatnonzero(U.label)
    c = np.ones(len(U), bool)
    if len(idx):
        c[idx[0]:] = False
        c[:idx[0]] = U.t[:idx[0]] < U.t[idx[0]] - margin
    return c


# ------------------------------------------------------------------ L1 profile pieces
def l1_builder(U: UnitData, clean: np.ndarray) -> L.ProfileBuilder:
    F = L.make_features(U.t, U.id, U.dlc, windows=False)
    return L.ProfileBuilder().add(F["id"][clean], F["dlc"][clean], F["dt_id"][clean])


def merge_builders(bs) -> L.ProfileBuilder:
    """Union of ProfileBuilders (clean traffic of several units)."""
    m = L.ProfileBuilder()
    for b in bs:
        m.dlc_pairs |= b.dlc_pairs
        for i, c in b.count.items():
            m.count[i] = m.count.get(i, 0) + c
        for i, parts in b.dt.items():
            m.dt.setdefault(i, []).extend(parts)
    return m


# ------------------------------------------------------------------ grids (as tools/WP2_S5_grids.py)
def make_grid(tm, dec):
    """0.05 s sample-and-hold grids from 1 s after the first frame: Gc (n x 138 continuous), Gd (n x 4 reverse bit + 3 gear copies), t0."""
    g = np.arange(tm[0] + 1.0, tm[-1], Z.GRID_DT)
    Gc = np.full((len(g), len(CAT.cont)), np.nan, np.float32)
    Gd = np.full((len(g), len(DISC)), np.nan, np.float32)
    for (i, k), c in CAT.cont_ix.items():
        if i in dec:
            rows, V = dec[i]
            Gc[:, c] = Z.held(tm[rows], V[:, k], g)
    for c, (i, k) in enumerate(DISC):
        if i in dec:
            rows, V = dec[i]
            Gd[:, c] = Z.held(tm[rows], V[:, k], g)
    return Gc, Gd, (float(g[0]) if len(g) else float(tm[0] + 1.0))


# ------------------------------------------------------------------ container
class RoadModels:
    """Everything learned from attack-free units. l3c: dict design name -> L3cModel (own features); weights: L2b check weights (dict) or None."""

    def __init__(self):
        self.profile = None
        self.l1_variant = 0
        self.l2b = None
        self.l2b_weights = None
        self.l3c = {}
        self.l3d = None


class _Z:
    """Context manager: the module-level switches of can/l2b_signals.py for the S7 relations-only scoring (no mute)."""

    def __init__(self, weights=None, trace=None):
        self.w, self.tr = weights, trace

    def __enter__(self):
        self.old = (Z.WEIGHTS, Z.MUTE_T0, Z.CONT_ONLY, Z.JOINT_ONLY, Z.TRACE)
        Z.WEIGHTS, Z.MUTE_T0, Z.CONT_ONLY, Z.JOINT_ONLY, Z.TRACE = self.w, None, True, JOINT_KEYS, self.tr

    def __exit__(self, *a):
        Z.WEIGHTS, Z.MUTE_T0, Z.CONT_ONLY, Z.JOINT_ONLY, Z.TRACE = self.old


def l2b_trace(model: Z.Model, tm, dec, n) -> dict:
    """Per-check (frames evaluated, violating frames) of one attack-free capture, weights off (for the surprise weights)."""
    tr = {}
    with _Z(None, tr):
        Z.score_frames(model, tm, dec, n)
    return tr


def l2b_window_raws(model: Z.Model, weights, tm, dec, n, st) -> dict:
    with _Z(weights, None):
        raws = Z.score_frames(model, tm, dec, n)
    return {t: np.maximum.reduceat(raws[t], st) for t in L2B_TYPES}


def l3c_series(mdl, Gc, rmins) -> dict:
    """Grid-level windowed-CUSUM L3c score for several r_min from ONE residual matrix (same numbers as P.grid_scores(..., 'cusum'))."""
    z = P.z_matrix(mdl, Gc)
    cs = np.cumsum(np.vstack([np.zeros((1, z.shape[1])), np.maximum(z - P.CUSUM_K, 0.0)]), axis=0, dtype=np.float64)
    idx = np.arange(1, len(z) + 1)
    w = (cs[idx] - cs[np.maximum(idx - P.L3D_WIN, 0)]).astype(np.float32)
    return {rm: w[:, mdl.r2 >= rm].max(1) for rm in rmins}


# ------------------------------------------------------------------ per-window raw scores of one capture
def window_raws(M: RoadModels, U: UnitData, profile=None, dec=None, grid=None) -> dict:
    """Window arrays of every layer for one capture. `profile` overrides M.profile (leave-capture-out L1 for validation captures);
    `dec` / `grid` may be passed when already computed. L3c keys: '<design>@<r_min>' for r_min in SKIP_RMIN."""
    tm = U.tm
    n = len(tm)
    st = Z.window_starts(tm)
    out = {"sec": np.floor(tm[st]).astype(np.int64), "w_end": np.maximum.reduceat(tm, st)}
    clean = lead_clean(U)
    out["y"] = np.maximum.reduceat(U.label.astype(np.int8), st).astype(np.int8)
    out["clean"] = np.minimum.reduceat(clean.astype(np.int8), st).astype(bool)
    idx = np.flatnonzero(U.label)
    out["first_inj"] = float(U.t[idx[0]]) if len(idx) else float("nan")
    # L1
    prof = M.profile if profile is None else profile
    F = L.make_features(U.t, U.id, U.dlc, windows=False)
    for c in L.RULE_CLASSES:
        if c is L.PeriodPerId:
            keep = prof.variant
            for k in range(len(L.VARIANTS)):
                prof.set_variant(k)
                out[f"l1_{c.name}#{k}"] = np.maximum.reduceat(c(prof).frame_raw(F), st).astype(np.float32)
            prof.set_variant(keep)
        else:
            out[f"l1_{c.name}"] = np.maximum.reduceat(c(prof).frame_raw(F), st).astype(np.float32)
    del F
    # decoded signals
    if dec is None:
        dec = S.decode_all(U.id, U.B, DBC)
    if M.l2b is not None:
        r = l2b_window_raws(M.l2b, M.l2b_weights, tm, dec, n, st)
        for t in L2B_TYPES:
            out[f"l2b_{t}"] = r[t].astype(np.float32)
    # L3
    Gc, Gd, g0 = make_grid(tm, dec) if grid is None else grid
    ok = np.zeros(len(st), bool)
    if len(Gc):
        for d, mdl in M.l3c.items():
            for rm, gs in l3c_series(mdl, Gc, SKIP_RMIN).items():
                ws, ok = P.window_scores(gs, tm, g0, st)
                out[f"l3c_{d}@{rm}"] = ws
        if M.l3d is not None:
            ws, ok = P.window_scores(P.l3d_scores(M.l3d, Gd), tm, g0, st)
            out["l3d"] = ws
    out["ok"] = ok
    return out


def top_signals(M: RoadModels, design: str, U: UnitData, rmin: float, mask_time, topn=4, dec=None, grid=None) -> dict:
    """Signals that carry the L3c score (argmax per grid step) at grid steps where mask_time(t_grid) is true: descriptive, for alarm reasons."""
    tm = U.tm
    dec = S.decode_all(U.id, U.B, DBC) if dec is None else dec
    Gc, _, g0 = make_grid(tm, dec) if grid is None else grid
    sc, am = P.grid_scores(M.l3c[design], Gc, rmin, "cusum", return_argmax=True)
    g = g0 + P.GRID_DT * np.arange(len(sc))
    sel = mask_time(g)
    if not sel.any():
        return {}
    ids, cnt = np.unique(am[sel], return_counts=True)
    o = np.argsort(-cnt)[:topn]
    return {f"{CAT.cont[ids[i]][0]:#x}.{CAT.cont[ids[i]][1]}": round(float(cnt[i] / sel.sum()), 3) for i in o}
