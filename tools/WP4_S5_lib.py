"""WP4 S5 shared helpers: D10 stage stream + aligned 76-feature matrix, frames for the L3 layers, detection at a tie-safe budget, signature check."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN
from common.metrics import auc, budget_threshold
from network.flows import FEATURES
from tools.WP4_S3_lib import RES, S3, load, log, stream  # noqa: F401

CACHE = os.path.join(S3, "..", "S5")
RULE_BLIND = ["Bot", "Web-XSS", "Web-BruteForce", "DoS-Slowloris"]       # families the rules of S2-S4 miss (S3 report caveat 6, S4)


def load_d10():
    d = load("D10")
    d["pos"] = np.arange(len(d))
    X = np.load(os.path.join(CACHE, "D10_X.npy"), mmap_mode="r")
    return d, X


def frame(d, X, mask=None):
    """DataFrame with the 76 features (float32) + dst_port, protocol for the rows of the stream table `d` (all rows, or a boolean mask)."""
    pos = d["pos"].to_numpy() if mask is None else d["pos"].to_numpy()[mask]
    f = pd.DataFrame(np.asarray(X[pos]), columns=FEATURES)
    f["dst_port"] = d["dst_port"].to_numpy()[mask] if mask is not None else d["dst_port"].to_numpy()
    f["protocol"] = d["protocol"].to_numpy()[mask] if mask is not None else d["protocol"].to_numpy()
    return f


def benign_mask(d, split):
    return ((d["split"].astype(str) == split) & (d["family"].astype(str) == "BENIGN") & ~d["audit"]).to_numpy()


def attack_mask(d, split):
    return ((d["split"].astype(str) == split) & (d["family"].astype(str) != "BENIGN")).to_numpy()


def det_at_budget(raw_ben, raw_atk, fam_atk, budget=BUDGET_DOMAIN, thr=None):
    """Threshold = tie-safe budget quantile of the benign scores (or the given raw threshold); detection per family, FA, AUC."""
    thr = budget_threshold(raw_ben, budget) if thr is None else thr
    alarm = raw_atk >= thr
    fam = np.asarray(fam_atk)
    out = {"threshold": float(thr), "fa_benign": float((raw_ben >= thr).mean()), "detection": {}, "n": {}, "auc": {}}
    for f in sorted(set(fam)):
        m = fam == f
        out["detection"][f] = float(alarm[m].mean())
        out["n"][f] = int(m.sum())
        y = np.r_[np.zeros(len(raw_ben)), np.ones(int(m.sum()))]
        out["auc"][f] = auc(y, np.r_[raw_ben, raw_atk[m]])
    y = np.r_[np.zeros(len(raw_ben)), np.ones(len(raw_atk))]
    out["auc_all"] = auc(y, np.r_[raw_ben, raw_atk])
    return out


def summarise(r, evaluable):
    """macro detection over the evaluable families, over the rule-blind families."""
    ev = [f for f in evaluable if f in r["detection"]]
    bl = [f for f in RULE_BLIND if f in r["detection"]]
    return {"macro": float(np.mean([r["detection"][f] for f in ev])), "blind4": float(np.mean([r["detection"][f] for f in bl])),
            "macro_auc": float(np.mean([r["auc"][f] for f in ev]))}
