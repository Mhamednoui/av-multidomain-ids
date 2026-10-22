"""WP4 S3 shared helpers: stage streams, fitting / calibration of the L2a layers, flow-unit and window-unit evaluation, delay.

Streams are the PRE-DEDUP stage tables of tools/WP4_S3_prep.py (../data_extra/cache_v3/WP4/S3/). Fit and calibration use the
BENIGN-ONLY stream of a split (attack flows removed before the window features are computed); test is scored on the mixed stream.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN
from common.metrics import auc, budget_threshold
from network import l2a

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
S3 = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4", "S3")
RES = os.path.join(ROOT, "results", "WP4")


def log(*a):
    print(*a, flush=True)


AUDIT_FILE = "Infilteration"   # D10 Thursday afternoon: the compromised host's network scan is labelled BENIGN (see notes 2026-10-22 S3 audit)


def load(ds):
    d = pd.read_pickle(os.path.join(S3, ds + "_stage.pkl"))
    d["audit"] = d["file"].astype(str).str.contains(AUDIT_FILE).to_numpy()
    return d


def stream(d, split, benign_only=False):
    m = d["split"].astype(str).to_numpy() == split
    if benign_only:
        m &= (d["family"].astype(str).to_numpy() == "BENIGN") & ~d["audit"].to_numpy()
    return d.loc[m].reset_index(drop=True)


def fit_calibrate(layers, tr_ben, val_ben, budget=BUDGET_DOMAIN):
    """Fit on the benign train stream; flow-unit calibration (Layer.calibrate, tie-safe budget) and window-unit raw threshold on the
    benign val stream."""
    for L in layers:
        L.fit(tr_ben)
        L.calibrate(val_ben, budget)
        raw = L.raw_scores(val_ben)
        cm = cell_max(L.cells(val_ben), raw)
        L.win_threshold = budget_threshold(cm[1], budget)
        L.win_budget_n = int(len(cm[1]))
    return layers


def add_scores(df, layers, same_network=True):
    for L in layers:
        df[L.score_col] = L.stream_scores(df, same_network)
    return df


def cell_max(cell, raw):
    """(cell ids, max raw per cell)."""
    s = pd.Series(raw).groupby(cell).max()
    return s.index.to_numpy(), s.to_numpy()


def flow_eval(L, df, families, same_network=True):
    """Flow unit: alarm = calibrated score >= layer threshold. FA on benign flows (split: benign flows whose cell contains an attack flow),
    AUC, detection per family, per-segment delay (minutes from the first attack flow of the segment)."""
    raw = df[L.score_col].to_numpy(float)
    cal = L.calibrator.transform(raw)
    alarm = cal >= L.threshold
    fam = df["family"].astype(str).to_numpy()
    atk = fam != "BENIGN"
    cell = L.cells(df) if hasattr(L, "cells") else np.arange(len(df))
    cell_has_atk = pd.Series(atk).groupby(cell).transform("max").to_numpy()
    aud = df["audit"].to_numpy()
    ben_all = ~atk
    ben = ~atk & ~aud                      # headline benign: published BENIGN labels minus the audited Infiltration file
    out = {"fa_benign": float(alarm[ben].mean()), "fa_benign_published_labels": float(alarm[ben_all].mean()),
           "fa_benign_audit_file": float(alarm[ben_all & aud].mean()) if (ben_all & aud).any() else None,
           "n_benign": int(ben.sum()), "n_benign_audit": int((ben_all & aud).sum()),
           "fa_benign_in_attack_cells": float((alarm & ben & cell_has_atk).sum() / ben.sum()),
           "fa_benign_other": float((alarm & ben & ~cell_has_atk).sum() / ben.sum()),
           "benign_in_attack_cells_share": float((ben & cell_has_atk).sum() / ben.sum()),
           "auc": auc(atk, cal), "threshold": L.threshold, "detection": {}, "n": {}, "delay_min": {}}
    day_ = df["day"].astype(str).to_numpy()
    out["fa_by_day"] = {str(k): float(alarm[ben & (day_ == k)].mean()) for k in np.unique(day_) if (ben & (day_ == k)).any()}
    t = df["t"].to_numpy(float)
    day = df["day"].astype(str).to_numpy()
    per = df["period"].to_numpy()
    for f in families:
        m = fam == f
        if not m.any():
            continue
        out["detection"][f] = float(alarm[m].mean())
        out["n"][f] = int(m.sum())
        seg = pd.DataFrame({"d": day[m], "p": per[m], "t": t[m], "a": alarm[m]})
        dl = []
        for _, g in seg.groupby(["d", "p"]):
            hit = g.loc[g["a"], "t"]
            dl.append(float((hit.min() - g["t"].min()) / 60.0) if len(hit) else None)
        out["delay_min"][f] = dl
    return out


def window_eval(L, df, families):
    """Window unit: cells (layer key, minute / bin). Cell raw = max over its flows; attack cell = contains >= 1 attack flow of the family
    (a cell is assigned the first attack family in it); threshold = benign-val cell budget (L.win_threshold)."""
    raw = df[L.score_col].to_numpy(float)
    cell = L.cells(df)
    fam = df["family"].astype(str).to_numpy()
    d = pd.DataFrame({"c": cell, "raw": raw, "f": np.where(fam == "BENIGN", "", fam), "aud": df["audit"].to_numpy() & (fam == "BENIGN")})
    g = d.groupby("c").agg(raw=("raw", "max"), f=("f", "max"), n=("raw", "size"), aud=("aud", "max"))
    alarm = g["raw"].to_numpy() >= L.win_threshold
    atk = (g["f"] != "").to_numpy()
    aud = g["aud"].to_numpy()
    out = {"fa_benign_cells": float(alarm[~atk & ~aud].mean()), "n_benign_cells": int((~atk & ~aud).sum()),
           "fa_benign_cells_published_labels": float(alarm[~atk].mean()), "detection": {}, "n": {}}
    for f in families:
        m = (g["f"] == f).to_numpy()
        if m.any():
            out["detection"][f] = float(alarm[m].mean())
            out["n"][f] = int(m.sum())
    return out


def subsample(df, n_ben, n_fam, seed):
    rng = np.random.RandomState(seed)
    idx = []
    for f, g in df.groupby(df["family"].astype(str), observed=True).indices.items():
        k = n_ben if f == "BENIGN" else n_fam
        idx.append(g if len(g) <= k else rng.choice(g, k, replace=False))
    return df.iloc[np.sort(np.concatenate(idx))]
