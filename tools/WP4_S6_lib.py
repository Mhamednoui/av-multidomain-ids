"""WP4 S6 shared helpers: D10 stage stream + 76-feature matrix + dedup mask (rows of the de-duplicated final table), L4 training / evaluation tables."""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN
from common.metrics import auc, budget_threshold
from network import l3
from network.flows import FEATURES, GROUP
from tools.WP4_S5_lib import CACHE as S5, RES, RULE_BLIND, attack_mask, benign_mask, det_at_budget, load_d10, log, summarise  # noqa: F401

S6 = os.path.join(S5, "..", "S6")
os.makedirs(S6, exist_ok=True)
EVAL10 = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator", "PortScan", "Web-BruteForce", "Web-XSS"]
EVAL23 = ["Bot", "DDoS-HOIC", "DDoS-LOIC-HTTP", "DDoS-LOIC-UDP", "DoS-GoldenEye", "DoS-Slowloris", "Infiltration", "SSH-Patator", "Web-BruteForce"]
COLS = l3.feature_set("clean")
GROUPS_LOAO = {"DoS-4": ["DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris"], "WebAttack": ["Web-BruteForce", "Web-XSS", "Web-SQLi"],
               "BruteForce": ["FTP-Patator", "SSH-Patator"]}


def in_final(d):
    """Boolean per stage row: the row is in the de-duplicated final table (cached in the S6 cache)."""
    p = os.path.join(S6, "D10_in_final.npy")
    if os.path.exists(p):
        return np.load(p)
    B = os.path.join(S5, "..", "D10", "final")
    keys = pd.concat([pd.read_pickle(f, compression="gzip")[["file", "row"]] for f in glob.glob(os.path.join(B, "*.pkl"))], ignore_index=True)
    k = d["file"].astype(str) + "|" + d["row"].astype(str)
    m = k.isin(set(keys["file"].astype(str) + "|" + keys["row"].astype(str))).to_numpy()
    np.save(p, m)
    return m


def load_s6():
    d, X = load_d10()
    d["in_final"] = in_final(d)
    d["fam"] = d["family"].astype(str)
    d["grp"] = d["fam"].map(GROUP).fillna(d["fam"])
    d["sp"] = d["split"].astype(str)
    return d, X


def sel(d, split, dedup=True, benign_only=False, attack_only=False):
    """Rows of `split`; dedup: only rows of the final table; the benign flows of the audited Infiltration file never count as benign."""
    m = (d["sp"] == split).to_numpy()
    if dedup:
        m &= d["in_final"].to_numpy()
    ben = (d["fam"] == "BENIGN").to_numpy()
    m &= ~(ben & d["audit"].to_numpy())
    if benign_only:
        m &= ben
    if attack_only:
        m &= ~ben
    return m


def feat(d, X, mask):
    pos = d["pos"].to_numpy()[mask]
    return pd.DataFrame(np.asarray(X[pos])[:, [FEATURES.index(c) for c in COLS]], columns=COLS)


def macro_at_budget(raw, fam, ben_mask, budget=BUDGET_DOMAIN, evaluable=EVAL10):
    """raw/fam over the validation rows (benign = fam BENIGN and ben_mask). Returns det_at_budget dict + macro detection / macro AUC."""
    b = ben_mask & (fam == "BENIGN")
    a = fam != "BENIGN"
    r = det_at_budget(raw[b], raw[a], fam[a], budget=budget)
    r["macro"] = float(np.mean([r["detection"][f] for f in evaluable if f in r["detection"]]))
    r["macro_auc"] = float(np.mean([r["auc"][f] for f in evaluable if f in r["auc"]]))
    return r
