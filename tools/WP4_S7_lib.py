"""WP4 S7 shared helpers: S7 score tables (D10 val / test stage rows with every layer's raw score), vectorised combiner (common/combiner.py functions on arrays),
stack definitions, metrics per family with bootstrap CIs over time blocks, delay, label variants (published / Bot-corrected).
Tables are built by tools/WP4_S7_prep.py into ../data_extra/cache_v3/WP4/S7/."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import combiner as cb
from common.combiner import DomainCombiner
from common.config import BUDGET_DOMAIN, SEED
from common.metrics import auc, budget_threshold
from tools.WP4_S6_lib import EVAL10, EVAL23, GROUPS_LOAO, RES, S6  # noqa: F401
from tools.WP4_S3_lib import subsample  # noqa: F401

S7 = os.path.join(S6, "..", "S7")
os.makedirs(S7, exist_ok=True)

N_BEN, N_FAM = 150_000, 2_000             # validation subsample for the combiner: benign 150k, <= 2000 flows per family (family-balanced; S6 used 20000, which let Hulk / LOIC dominate the pooled selection)
BLOCK_S = 600                              # bootstrap block = 10 minutes
N_BOOT = 2000

H = ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce"]
ON = ["net.dos_rate", "net.l3_service", "net.l3_ae"]
O = H + ON
TOPO = ["net.allow_service", "net.allow_pair"]
STACKS = {"H": H, "O": O, "O+slow": O + ["net.slow"], "O+beacon": O + ["net.beacon"], "O+topology": O + TOPO,
          "O+L4": O + ["net.l4_xgb"], "L4 alone": ["net.l4_xgb"]}
COL = {n: "s_" + n for n in O + ["net.slow", "net.beacon", "net.l4_xgb"] + TOPO}


def log(*a):
    print(*a, flush=True)


def load_tables():
    val = pd.read_pickle(os.path.join(S7, "d10_val.pkl"))
    test = pd.read_pickle(os.path.join(S7, "d10_test.pkl"))
    cal = pickle.load(open(os.path.join(S7, "cal.pkl"), "rb"))
    return val, test, cal


def cal_matrix(df, cal, names):
    """Calibrated (0..1) scores, one column per layer."""
    return np.column_stack([cal[n][0].transform(df[COL[n]].to_numpy(float)) for n in names])


def layer_alarm(df, cal, name):
    return cal[name][0].transform(df[COL[name]].to_numpy(float)) >= cal[name][1]


class ArrCombiner(DomainCombiner):
    """DomainCombiner whose evidence are arrays (no Evidence objects): fit on validation arrays, apply to arrays. Same selection, thresholds and functions."""

    def _matrix(self, evidence):
        return np.column_stack([np.asarray(evidence[n], float) for n in self.layer_names])

    def scores(self, X):
        return cb._combine(self.method, X, self.model)


def val_sample(val, exclude=()):
    """Harness subsample of the validation stream (audit file benign excluded), minus the families in `exclude`."""
    m = ~val["audit"].to_numpy() & ~val["fam"].isin(list(exclude)).to_numpy()
    return subsample(val[m].assign(family=val["fam"][m]), N_BEN, N_FAM, SEED)


def fit_combiner(vs, cal, names, method="auto"):
    """vs: validation subsample (columns fam, day, period + scores). Returns (combiner, X-columns order). Groups = 10-minute time blocks."""
    X = cal_matrix(vs, cal, names)
    y = (vs["fam"].to_numpy() != "BENIGN").astype(int)
    g = (vs["t"].to_numpy(float) // BLOCK_S).astype("int64").astype(str)          # groups = 10-minute time blocks (day x period groups put each family in ONE half)
    C = ArrCombiner(method=method, budget=BUDGET_DOMAIN)
    C.fit({n: X[:, i] for i, n in enumerate(names)}, y, g)
    C.names = list(names)
    return C


def comb_alarm(C, df, cal):
    """Combined score and alarm of a fitted ArrCombiner on a table (layers in C.layer_names order)."""
    X = np.column_stack([cal[n][0].transform(df[COL[n]].to_numpy(float)) for n in C.layer_names])
    s = C.scores(X)
    return s, s >= C.threshold


# ---------------------------------------------------------------- metrics
def blocks_of(df):
    return (df["day"].astype(str) + "|" + (df["t"].to_numpy(float) // BLOCK_S).astype("int64").astype(str)).to_numpy()


class Scorer:
    """Per-family detection, FA, macro with bootstrap CIs over time blocks for one test table and one label variant."""

    def __init__(self, df, fam_col="fam", families=EVAL10, seed=SEED):
        self.df = df
        self.fam = df[fam_col].to_numpy()
        self.audit = df["audit"].to_numpy()
        self.families = [f for f in families if (self.fam == f).any()]
        b = blocks_of(df)
        self.bu, self.binv = np.unique(b, return_inverse=True)
        self.seed = seed
        self.ben = (self.fam == "BENIGN") & ~self.audit          # headline benign
        self.ben_pub = self.fam == "BENIGN"                      # published-label benign (audit file included)
        self.audit_ben = (self.fam == "BENIGN") & self.audit

    def _counts(self, mask_list, alarm):
        nb = len(self.bu)
        n = np.column_stack([np.bincount(self.binv[m], minlength=nb) for m in mask_list]).astype(float)
        k = np.column_stack([np.bincount(self.binv[m & alarm], minlength=nb) for m in mask_list]).astype(float)
        return n, k

    def summary(self, alarm, ci=True, extra_fams=()):
        """dict: fa (headline), fa_pub, fa_audit, detection per family with n and CI, macro with CI, n_blocks per family."""
        alarm = np.asarray(alarm, bool)
        fams = list(self.families) + [f for f in extra_fams if (self.fam == f).any() and f not in self.families]
        masks = [self.ben, self.ben_pub] + [self.fam == f for f in fams]
        n, k = self._counts(masks, alarm)
        N, K = n.sum(0), k.sum(0)
        out = {"fa": float(K[0] / N[0]), "fa_pub": float(K[1] / N[1]), "n_benign": int(N[0]),
               "fa_audit_file": float(alarm[self.audit_ben].mean()) if self.audit_ben.any() else None,
               "detection": {f: float(K[2 + i] / N[2 + i]) for i, f in enumerate(fams)}, "n": {f: int(N[2 + i]) for i, f in enumerate(fams)},
               "n_blocks": {f: int((n[:, 2 + i] > 0).sum()) for i, f in enumerate(fams)}}
        ev = [i for i, f in enumerate(fams) if f in self.families]
        out["macro"] = float(np.mean([K[2 + i] / N[2 + i] for i in ev]))
        out["n_ge50"] = int(sum(K[2 + i] / N[2 + i] >= 0.5 for i in ev))
        if ci:
            rng = np.random.RandomState(self.seed)
            nb = len(self.bu)
            res = []
            for _ in range(N_BOOT // 250):
                idx = rng.randint(0, nb, (250, nb))
                Nb = n[idx].sum(1)
                Kb = k[idx].sum(1)
                with np.errstate(invalid="ignore", divide="ignore"):
                    res.append(np.where(Nb > 0, Kb / Nb, np.nan))
            R = np.concatenate(res)
            lo, hi = np.nanpercentile(R, [2.5, 97.5], axis=0)
            out["fa_ci"] = [float(lo[0]), float(hi[0])]
            out["detection_ci"] = {f: [float(lo[2 + i]), float(hi[2 + i])] for i, f in enumerate(fams)}
            mac = np.nanmean(R[:, [2 + i for i in ev]], axis=1)
            out["macro_ci"] = [float(np.percentile(mac, 2.5)), float(np.percentile(mac, 97.5))]
        return out

    def delay(self, alarm, families=None):
        """Per family: list over (day, period) segments of minutes from the first attack flow of the family to its first alarmed flow (None = never)."""
        df = self.df
        t, alarm = df["t"].to_numpy(float), np.asarray(alarm, bool)
        seg = (df["day"].astype(str) + "|" + df["period"].astype(str)).to_numpy()
        out = {}
        for f in families or self.families:
            m = self.fam == f
            if not m.any():
                continue
            d = pd.DataFrame({"s": seg[m], "t": t[m], "a": alarm[m]})
            dl = []
            for _, g in d.groupby("s"):
                hit = g.loc[g["a"], "t"]
                dl.append(float((hit.min() - g["t"].min()) / 60.0) if len(hit) else None)
            out[f] = dl
        return out

    def auc_all(self, score):
        m = self.ben | ((self.fam != "BENIGN"))
        return auc((self.fam[m] != "BENIGN").astype(int), score[m])


def load_combiner(entry):
    """Rebuild a fitted ArrCombiner from a frozen entry of combiners.pkl."""
    C = ArrCombiner(method=entry["method"])
    C.layer_names, C.model, C.threshold = list(entry["names"]), entry["model"], entry["threshold"]
    return C


def or_alarm(df, cal, names):
    al = np.zeros(len(df), bool)
    for n in names:
        al |= layer_alarm(df, cal, n)
    return al
