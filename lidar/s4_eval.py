"""WP3 S4 evaluation helpers: load cached object tables, fit the L2a object model, scan / object scores, thresholds (val-only, LODO).

Inputs: pickles of tools/WP3_S4_build.py ({"objs": object rows with column `scan`, "scans": one row per scan}).
Outputs: per-scan DataFrames (one row per scan: STATS maxima + L1 statistics), calibrated Layers, detection tables.
"""
import numpy as np
import pandas as pd

from common.metrics import budget_threshold
from lidar import density as D
from lidar.data import part_of


def load_kind(root, kind, drives, which="tiles"):
    """(units, scans): units = tile table (default) or cluster table; tiles get the constant footprint columns of the density model."""
    o, s = [], []
    for d in drives:
        z = pd.read_pickle(root / f"{kind}_{d}.pkl")
        o.append(z[which])
        s.append(z["scans"])
    o = pd.concat(o, ignore_index=True)
    if which == "tiles":
        o["ring_min"], o["ring_max"], o["az_span"] = 0.0, 7.0, 2.0 - 0.1728
    return o, pd.concat(s, ignore_index=True)


def scan_frame(model, objs, scans):
    """One row per scan: the scan's columns + the four scan scores (0 for scans without a scored object)."""
    sc = model.scores(objs)
    mx = D.scan_scores(objs, sc, "scan")
    df = scans.set_index("scan").join(mx).reset_index()
    df[D.ALL_STATS] = df[D.ALL_STATS].fillna(0.0)
    return df


def object_frame(model, objs):
    """Object table with its four scores."""
    return pd.concat([objs.reset_index(drop=True), model.scores(objs).reset_index(drop=True)], axis=1)


def fit_model(clean_objs, scans, drives, calib, nmin):
    m = scans.set_index("scan").loc[clean_objs["scan"].to_numpy(), "drive"].to_numpy()
    return D.ObjectModel(calib, nmin).fit(clean_objs[np.isin(m, drives)])


def union_layer(df_clean, budget=0.01):
    return D.L2aUnion().calibrate(df_clean, budget)


def cal_scores(layer, df):
    return layer.calibrator.transform(layer.raw_scores(df))


def object_raw(layer, obj_scores):
    """Union raw score of single objects (max over the ECDFs of the four statistics), same scale as the scan score."""
    return np.column_stack([np.searchsorted(layer.ref[s], obj_scores[s].to_numpy(), side="left") / len(layer.ref[s])
                            for s in layer.stats if s in obj_scores.columns]).max(axis=1)


def lodo_scan_scores(clean_objs, clean_scans, drives, calib, nmin):
    """Pooled out-of-fold scan frames: for each drive a model fitted on the other drives scores that drive's clean scans."""
    out = []
    mm = clean_scans.set_index("scan")["drive"]
    drv_of_obj = mm.loc[clean_objs["scan"].to_numpy()].to_numpy()
    for d in drives:
        model = D.ObjectModel(calib, nmin).fit(clean_objs[np.isin(drv_of_obj, [x for x in drives if x != d])])
        sel = clean_scans[clean_scans.drive == d]
        o = clean_objs[drv_of_obj == d]
        out.append(scan_frame(model, o, sel))
    return pd.concat(out, ignore_index=True)


def detection(layer, df, by="attack"):
    """Fraction of scans with a calibrated score at or above the layer threshold, per value of `by`."""
    a = cal_scores(layer, df) >= layer.threshold
    return pd.Series(a, index=df.index).groupby(df[by].to_numpy()).mean()


def per_drive_fa(layer, df):
    a = cal_scores(layer, df) >= layer.threshold
    return pd.Series(a, index=df.index).groupby(df["drive"].to_numpy()).mean()


def tie_safe_threshold(scores, budget=0.01):
    return budget_threshold(np.asarray(scores, float), budget)


def is_test(d):
    return part_of(d) == "test"
