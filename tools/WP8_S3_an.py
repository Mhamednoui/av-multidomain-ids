"""WP8 S3 analysis library: from the per-drive records (tools/WP8_S3_build.py) to layer raw scores, out-of-fold references, the union /
max combiners with per-layer budgets, leave-one-drive-out evaluation on V31_val and the PointDrop episode rule.
Layers (as the v3 frozen domain): L1 = union of the ECDF ranks of the 5 L1 statistics; L2a = union of ranks of (int_hi, int_lo, cnt_int_hi,
cnt_int_lo) of the intensity tail scores of the tiles, intensity model refitted without the scored drive; L2c = union of ranks of the chosen
miss statistic(s); L2d = union of ranks of (app_cc, fix_tot). Layer raw score = max rank over its statistics against the reference."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S3_lib as L
from lidar import density as D
from lidar.fast import IntensityScorer
from lidar.sequence import EPISODE_SCANS, rolling_logodds

A_STATS = ["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]
LAYER_STATS = {"L1": L.L1_KEYS, "L2a": A_STATS, "L2c": ["miss_w20"], "L2d": ["app_cc", "fix_tot"]}
C_OPTIONS = {"miss_w20": ["miss_w20"], "miss_w10": ["miss_w10"], "miss_g20": ["miss_g20"], "miss_z20": ["miss_z20"],
             "u(w20,z20)": ["miss_w20", "miss_z20"]}


class IntensityRef:
    """Intensity cells of clean tiles (the .i dict of lidar.density.ObjectModel.fit for the intensity half) + nmin for IntensityScorer."""

    def __init__(self, tiles, nmin=8):
        self.nmin = nmin
        t = tiles[(tiles.n_points >= nmin) & (tiles.range >= D.R_EDGES[0]) & (tiles.range <= D.R_EDGES[-1])]
        im, n, r = t.int_mean.to_numpy(), t.n_points.to_numpy(), t.range.to_numpy()
        rb = np.clip(np.searchsorted(D.R_EDGES, r, side="right") - 1, 0, len(D.R_EDGES) - 2)
        nb = np.clip(np.searchsorted(D.N_EDGES, n, side="right") - 1, 0, len(D.N_EDGES) - 2)
        self.i = {}
        for a in range(len(D.R_EDGES) - 1):
            ma = rb == a
            self.i[(a, -1)] = np.sort(im[ma])
            for q in range(len(D.N_EDGES) - 1):
                mq = ma & (nb == q)
                if mq.sum() >= D.MIN_CELL:
                    self.i[(a, q)] = np.sort(im[mq])


def l2a_stats(tiles, nscan, scorer):
    """(nscan, 4) array of the L2a statistics of scans 0..nscan-1 from their tile table (column si)."""
    out = np.zeros((nscan, 4))
    if len(tiles) == 0:
        return out
    si = tiles.si.to_numpy()
    o = np.argsort(si, kind="stable")
    si = si[o]
    r, n, im = tiles.range.to_numpy()[o], tiles.n_points.to_numpy()[o], tiles.int_mean.to_numpy()[o]
    st = np.r_[0, np.flatnonzero(np.diff(si)) + 1, len(si)]
    for a, b in zip(st[:-1], st[1:]):
        out[si[a]] = scorer.scan_stats(r[a:b], n[a:b], im[a:b])
    return out


def load_parts(kinds=("clean", "att", "pdep"), drives=None):
    z = {}
    for k in kinds:
        for d in (drives or (L.DRIVES if k == "clean" else L.VAL)):
            f = L.PARTS / f"{k}_{d}.pkl"
            if f.exists():
                z[(k, d)] = pd.read_pickle(f)
    return z


def build_frame(parts):
    """One frame of all scans with the L2a statistics from the leave-one-drive-out intensity model.
    Columns: kind (clean/att/pdep), drive, i, attack, ep, step, 5 L1, 13 pair stats, 4 L2a stats."""
    drives = sorted({d for (k, d) in parts if k == "clean"})
    frames = []
    for d in drives:
        others = pd.concat([parts[("clean", x)]["tiles"] for x in drives if x != d], ignore_index=True)
        scorer = IntensityScorer(IntensityRef(others))
        for k in ("clean", "att", "pdep"):
            if (k, d) not in parts:
                continue
            z = parts[(k, d)]
            df = z["scans"].copy()
            df.insert(0, "kind", k)
            df.insert(1, "drive", d)
            if k == "clean":
                df["attack"] = "clean"
            a = l2a_stats(z["tiles"], len(df), scorer)
            for j, c in enumerate(A_STATS):
                df[c] = a[:, j]
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def rank_ref(ref, x):
    return np.searchsorted(np.sort(ref), np.asarray(x, float), side="left") / len(ref)


def layer_raw(ref_df, df, c_stats):
    """dict layer -> raw score (union rank over the layer statistics against the reference frame ref_df)."""
    stats = dict(LAYER_STATS, L2c=c_stats)
    out = {}
    for lay in LAYERS:
        out[lay] = np.max([rank_ref(ref_df[s].to_numpy(), df[s].to_numpy()) for s in stats[lay]], axis=0)
    return out


from lidar.combine31 import LAYERS, Union, alpha_budgets, ecdf_rank, waterfill   # noqa: E402


def candidates():
    cs = [("M0_v3_max", "miss_w20", "max", None)]
    for s in C_OPTIONS:
        for a in (0.25, 0.40, 0.55, 0.70, 0.85):
            cs.append((f"alpha{a:.2f}|{s}", s, "union", a))
    cs.append(("W0|miss_w20", "miss_w20", "union", "W0"))
    return cs


def fit_fold(frame, hold, c_name, method, alpha, B=0.01):
    """Stack fitted on the clean reference scans of all drives except `hold` (list); returns (stack, ref_frame)."""
    cs = C_OPTIONS[c_name]
    ref = frame[(frame.kind == "clean") & (frame.i >= 1) & ~frame.drive.isin(hold)]
    raw = layer_raw(ref, ref, cs)
    if method == "max":
        st = Union(B, "max").fit(raw)
    else:
        if alpha == "W0":
            R = np.column_stack([ecdf_rank(np.sort(raw[l]), raw[l]) for l in LAYERS])
            b = waterfill(R, B)
        else:
            b = alpha_budgets(alpha, B)
        st = Union(b, "union").fit(raw)
    st.cs, st.ref_frame = cs, ref
    return st, ref


def episode_eval(stacks_by_fold, frame):
    """PointDrop 3 s episodes with the v2 rolling log-odds rule, fold by fold. Returns detection list, delays and false-episode list."""
    det, delays, fe = [], [], []
    for d, st in stacks_by_fold.items():
        ref = st.ref_frame.sort_values(["drive", "i"])
        sc = st.score(layer_raw(st.ref_frame, ref, st.cs))
        wref = []
        for dd, idx in ref.reset_index(drop=True).groupby("drive").indices.items():
            s = sc[idx]
            wref += [s[a:a + EPISODE_SCANS] for a in range(0, len(s) - EPISODE_SCANS + 1, 10)]
        thr = float(np.quantile(np.concatenate([rolling_logodds(w) for w in wref]), 0.99))
        cl = frame[(frame.kind == "clean") & (frame.drive == d) & (frame.i >= 1)].sort_values("i")
        scc = st.score(layer_raw(st.ref_frame, cl, st.cs))
        for a in range(0, len(scc) - EPISODE_SCANS + 1, EPISODE_SCANS):
            fe.append(bool((rolling_logodds(scc[a:a + EPISODE_SCANS]) >= thr).any()))
        ep = frame[(frame.kind == "pdep") & (frame.drive == d)]
        for j, g in ep.groupby("ep"):
            g = g.sort_values("step")
            s = rolling_logodds(st.score(layer_raw(st.ref_frame, g, st.cs)))
            hit = np.flatnonzero(s >= thr)
            ok = len(hit) > 0 and hit[0] + 1 <= EPISODE_SCANS
            det.append(bool(ok))
            if ok:
                delays.append((hit[0] + 1) * 0.1032)
    return det, delays, fe


def evaluate(frame, name, c_name, method, alpha, with_episodes=False, B=0.01):
    """LODO over V31_val drives: pooled clean FA, per-drive FA, detection per attack kind (+ per-scan alarm vectors)."""
    out = {"name": name}
    fa_all, fa_drive = [], {}
    det_alarm = {k: [] for k in L.ATTACKS}
    det_drive = {k: [] for k in L.ATTACKS}
    stacks = {}
    for d in L.VAL:
        st, ref = fit_fold(frame, [d], c_name, method, alpha, B)
        stacks[d] = st
        cl = frame[(frame.kind == "clean") & (frame.drive == d) & (frame.i >= 1)]
        a = st.alarm(layer_raw(ref, cl, st.cs))
        fa_all.append(a)
        fa_drive[d] = float(a.mean())
        at = frame[(frame.kind == "att") & (frame.drive == d)]
        aa = st.alarm(layer_raw(ref, at, st.cs))
        for k in L.ATTACKS:
            m = (at.attack == k).to_numpy()
            det_alarm[k].append(aa[m])
            det_drive[k].append((int(aa[m].sum()), int(m.sum())))
        if method == "union":
            out.setdefault("budgets_by_fold", {})[d] = [float(x) for x in st.budgets]
    fa = np.concatenate(fa_all)
    out["fa"] = float(fa.mean())
    out["fa_worst_drive"] = float(max(fa_drive.values()))
    out["fa_by_drive"] = fa_drive
    out["det"] = {k: float(np.concatenate(v).mean()) for k, v in det_alarm.items()}
    out["det_by_drive"] = det_drive
    out["alarms"] = {k: np.concatenate(v) for k, v in det_alarm.items()}
    out["n_clean"], out["n_attacked_per_kind"] = int(len(fa)), int(len(out["alarms"]["PointDrop"]))
    if with_episodes:
        det, delays, fe = episode_eval(stacks, frame)
        out["episodes"] = {"n": len(det), "detected_3s": int(sum(det)), "median_delay_s": float(np.median(delays)) if delays else None,
                           "false_episode_rate": float(np.mean(fe)), "n_clean_windows": len(fe)}
    return out, stacks
