"""WP3 S7 evaluation helpers: load the cached L3 feature tables, per-scan score frames, label-free combination of layers
(max or noisy-or of ECDF ranks), tie-safe thresholds, paired bootstrap, episodes.
Inputs: pickles of tools/WP3_S7_build_l3.py / WP3_S7_build_l4.py. Outputs: DataFrames, detection tables."""
import numpy as np
import pandas as pd

from common.metrics import budget_threshold
from lidar.data import CACHE, FRAME_DT
from lidar.sequence import EPISODE_SCANS, rolling_logodds

ROOT = CACHE / "S7"
PHYS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof"]
CMP = ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
EP_KINDS = ["ep_replace_near", "ep_replace_far", "ep_budget_near", "ep_budget_far"]


def load_l3(kind, drives):
    """(feature table, scans table) of the L3 pickles of the given drives."""
    zs = [pd.read_pickle(ROOT / f"l3_{kind}_{d}.pkl") for d in drives]
    F = pd.concat([z["F"] for z in zs], ignore_index=True)
    F["scan"] = pd.Categorical(F["scan"].astype(str))
    return F, pd.concat([z["scans"] for z in zs], ignore_index=True)


def ecdf_rank(ref, x):
    ref = np.sort(np.asarray(ref, float))
    return np.searchsorted(ref, np.asarray(x, float), side="left") / len(ref)


def combine(ranks, method):
    """ranks: 2-D array (scans x layers) of ECDF ranks in [0, 1]. 'max' or 'noisy_or' (log form: sum of -log(1 - p), rank-equivalent)."""
    r = np.asarray(ranks, float)
    if method == "max":
        return r.max(axis=1)
    return (-np.log1p(-np.clip(r, 0.0, 1.0 - 1e-3))).sum(axis=1)


def det_by(alarm, labels):
    return pd.Series(np.asarray(alarm, float)).groupby(np.asarray(labels)).mean()


def threshold(scores, budget=0.01):
    return budget_threshold(np.asarray(scores, float), budget)


def lodo_fa(scores, drives, budget=0.01):
    """Per-drive FA when the threshold comes from the other drives' (out-of-fold) clean scores."""
    out = {}
    s, dr = np.asarray(scores, float), np.asarray(drives)
    for d in sorted(set(dr)):
        t = threshold(s[dr != d], budget)
        out[d] = float((s[dr == d] >= t).mean())
    return out


def paired_bootstrap(a, b, n=2000, seed=7):
    """Mean difference of two paired 0/1 vectors (b - a) with a 95 % bootstrap interval over scans."""
    d = np.asarray(b, float) - np.asarray(a, float)
    rng = np.random.default_rng(seed)
    m = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(n)])
    return float(d.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def clean_windows(cal_by_drive, step):
    out = []
    for s in cal_by_drive.values():
        for a in range(0, len(s) - EPISODE_SCANS + 1, step):
            out.append(s[a:a + EPISODE_SCANS])
    return out


def episode_stat_threshold(cal_by_drive, q=0.99, step=10):
    return float(np.quantile(np.concatenate([rolling_logodds(w) for w in clean_windows(cal_by_drive, step)]), q))


def episode_table(ep, cal, thr, alarm_thr):
    """ep: scans table (drive, ep, step, attack); cal: calibrated per-scan score aligned to ep. Detected within 3 s per kind."""
    ep = ep.assign(cal=np.asarray(cal, float))
    res = {}
    for kind, g in ep.groupby("attack"):
        det, delays = [], []
        for _, e in g.groupby(["drive", "ep"]):
            st = rolling_logodds(e.sort_values("step").cal.to_numpy())
            hit = np.flatnonzero(st >= thr)
            det.append(len(hit) > 0 and hit[0] + 1 <= EPISODE_SCANS)
            if len(hit):
                delays.append((hit[0] + 1) * FRAME_DT)
        res[kind] = {"episodes": len(det), "detected_3s": int(sum(det)), "median_delay_s": float(np.median(delays)) if delays else None,
                     "onset_scan": float((g[g.step == 1].cal >= alarm_thr).mean()), "sustained_scan": float((g[g.step >= 2].cal >= alarm_thr).mean())}
    return res


def rank_matrix(ref, df, cols):
    """ECDF ranks of the columns `cols` of df against the clean reference frame `ref` (one column per layer)."""
    return np.column_stack([ecdf_rank(ref[c].to_numpy(), df[c].to_numpy()) for c in cols])


def stack_scores(ref, df, cols, method):
    """Combined score of the layers `cols` (label-free: max or noisy-or of ECDF ranks against the reference clean scores) for the
    scans of df, and the same for the reference (out-of-fold clean scans)."""
    return combine(rank_matrix(ref, df, cols), method), combine(rank_matrix(ref, ref, cols), method)


def evaluate_stack(ref, clean, att, cols, method, budget=0.01):
    """One stack: threshold = tie-safe `budget` of the reference clean combined scores. Returns a dict with the test FA, per-drive FA
    (test, and leave-one-drive-out on the reference), per-attack detection and the boolean alarm vector of att (for paired comparisons)."""
    sc_clean, sc_ref = stack_scores(ref, clean, cols, method)
    sc_att, _ = stack_scores(ref, att, cols, method)
    thr = threshold(sc_ref, budget)
    alarm = sc_att >= thr
    ac = sc_clean >= thr
    return {"cols": list(cols), "method": method, "threshold": float(thr), "fa": float(ac.mean()),
            "fa_per_drive": {d: float(v) for d, v in pd.Series(ac).groupby(clean["drive"].to_numpy()).mean().items()},
            "fa_ref": float((sc_ref >= thr).mean()), "fa_ref_lodo": lodo_fa(sc_ref, ref["drive"].to_numpy(), budget),
            "det": {a: float(v) for a, v in det_by(alarm, att["attack"].to_numpy()).items()}, "alarm": alarm, "ref_scores": sc_ref}
