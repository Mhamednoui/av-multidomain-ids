"""WP3 S6 shared evaluation helpers (loading the cached statistic tables, thresholds, LODO false alarms, episodes)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.metrics import budget_threshold
from lidar.background import StatUnion
from lidar.data import CACHE, DRIVES, FRAME_DT, TEST, VAL, drives_of
from lidar.sequence import EPISODE_SCANS, rolling_logodds

ROOT = CACHE / "S6"
TRAINVAL = drives_of("train") + drives_of("val")
L2C = ["miss_w10", "miss_w20", "miss_g10", "miss_g20", "miss_z20"]
L2D = ["app_tot", "app_cc", "fix_tot", "fix_cc", "van_tot", "van_cc"]
ATT = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof", "cmp_boxcloud",
       "cmp_mradd_near", "cmp_mradd_far"]


def load(kind, drives):
    return pd.concat([pd.read_pickle(ROOT / f"{kind}_{d}.pkl") for d in drives], ignore_index=True)


def layer(layer_id, stats, ref):
    return StatUnion(layer_id, stats).calibrate(ref)


def lodo_fa(layer_id, stats, clean, budget=0.01):
    """Per drive false-alarm rate when the reference and threshold come from the other drives (rank score, tie-safe threshold)."""
    out = {}
    for d in sorted(clean.drive.unique()):
        L = layer(layer_id, stats, clean[clean.drive != d])
        s = L.calibrator.transform(L.raw_scores(clean[clean.drive == d]))
        out[d] = float((s >= L.threshold).mean())
    return out


def alarm(L, df):
    return L.calibrator.transform(L.raw_scores(df)) >= L.threshold


def windows(L, clean, step):
    out = []
    for d, g in clean.groupby("drive"):
        s = L.calibrator.transform(L.raw_scores(g.sort_values("idx")))
        for a in range(0, len(s) - EPISODE_SCANS + 1, step):
            out.append(s[a:a + EPISODE_SCANS])
    return out


def episode_threshold(L, clean):
    return float(np.quantile(np.concatenate([rolling_logodds(w) for w in windows(L, clean, 10)]), 0.99))


def episode_table(L, ep, thr):
    """Per kind: episodes, detected within 3 s, median delay (s) of alarmed, onset (step 1) and sustained (steps 2+) single-scan alarm rate."""
    ep = ep.copy()
    ep["cal"] = L.calibrator.transform(L.raw_scores(ep))
    ep["al"] = ep.cal >= L.threshold
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
                     "onset_scan": float(g[g.step == 1].al.mean()), "sustained_scan": float(g[g.step >= 2].al.mean())}
    return res
