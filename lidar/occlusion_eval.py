"""WP3 S5 evaluation helpers: load the cached tile tables, scan statistics for a variant, layers, detection tables, LODO thresholds."""
import numpy as np
import pandas as pd

from lidar import occlusion as O
from lidar.data import CACHE

ROOT = CACHE / "S5"
PH = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far"]
FL = ["fl_replace_near", "fl_replace_far", "fl_budget_near", "fl_budget_far"]
CHOICE = PH + ["cmp_boxcloud"]


def load_kind(kind, drives):
    t, s = [], []
    for d in drives:
        z = pd.read_pickle(ROOT / f"{kind}_{d}.pkl")
        t.append(z["tiles"])
        s.append(z["scans"])
    return pd.concat(t, ignore_index=True), pd.concat(s, ignore_index=True)


def frame(tiles, scans, v):
    """One row per scan: scan columns + the four scan statistics of variant v."""
    st = O.scan_stats(tiles, v, scans.scan.tolist())
    return scans.set_index("scan").join(st).reset_index()


def raw(layer, df):
    return layer.raw_scores(df)


def cal(layer, df):
    return layer.calibrator.transform(layer.raw_scores(df))


def detection(layer, df):
    a = cal(layer, df) >= layer.threshold
    return pd.Series(a, index=df.index).groupby(df["attack"].to_numpy()).mean()


def per_drive_fa(layer, df):
    a = cal(layer, df) >= layer.threshold
    return pd.Series(a, index=df.index).groupby(df["drive"].to_numpy()).mean()


def nested_lodo_fa(clean, drives, budget=0.01):
    """For each drive: threshold from the other drives (tie-safe), FA on that drive. Returns {drive: FA}."""
    out = {}
    for d in drives:
        lay = O.L2bUnion().calibrate(clean[clean.drive != d], budget)
        out[d] = float((cal(lay, clean[clean.drive == d]) >= lay.threshold).mean())
    return out
