"""WP4 S2 run: L1 rule layers (network/l1.py) on D10 and D23.

Usage: python -u -W ignore tools/WP4_S2_run.py smoke|verdict
  smoke   : the "test" side is the VALIDATION split (pipeline check, nothing about test is read); writes results/WP4/smoke/
  verdict : the ONE run on the test splits (D10 test, D23 in-dataset test, D10 -> D23 transfer); writes results/WP4/s2_*.json
Layers are fitted on BENIGN TRAIN, calibrated (ECDF, tie-safe 1% budget) on BENIGN VALIDATION. Per-layer numbers use all flows;
the harness (common/evaluate.py: combiner + ablation) runs on a fixed subsample (seed 42): benign N_BEN, each family at most N_FAM flows.
"""
import gc
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import SEED, BUDGET_DOMAIN
from common.evaluate import EvalSet, evaluate_domain
from common.metrics import auc
from network import l1
from tools.WP4_S2_lib import B, load_d10, load_d23

MODE = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert MODE in ("smoke", "verdict")
TEST = "val" if MODE == "smoke" else "test"
RES = os.path.join(os.path.dirname(__file__), "..", "results", "WP4")
OUT = RES if MODE == "verdict" else os.path.join(RES, "smoke")
os.makedirs(OUT, exist_ok=True)
N_BEN, N_FAM = 150_000, 20_000
NOID = ["net.allow_service", "net.proto_port", "net.tcp_flags", "net.flow_rate"]
FLAGONLY = ["net.proto_port", "net.tcp_flags", "net.flow_rate"]


def log(*a):
    print(*a, flush=True)


def fit_layers(tr, vb, names=None):
    out = {}
    for L in l1.all_layers():
        if names is not None and L.name not in names:
            continue
        L.fit(tr).calibrate(vb, BUDGET_DOMAIN)
        out[L.name] = L
    return out


def score_full(layers, df, fams):
    """Per layer on all flows of df: FA on benign, AUC, detection per family (alarm = calibrated score >= layer threshold)."""
    y = (df.family != "BENIGN").to_numpy()
    res, scores = {}, {}
    for n, L in layers.items():
        sc = L.calibrator.transform(L.raw_scores(df))
        al = sc >= L.threshold
        scores[n] = sc
        r = {"threshold": L.threshold, "fa_benign": float(al[~y].mean()), "auc": auc(y, sc), "n_benign": int((~y).sum()),
             "detection": {}, "n": {}}
        for f in fams:
            m = (df.family == f).to_numpy()
            if m.any():
                r["detection"][f] = float(al[m].mean())
                r["n"][f] = int(m.sum())
        res[n] = r
        log("  ", n, "FA %.4f AUC %.3f" % (r["fa_benign"], r["auc"]), {k: round(v, 2) for k, v in r["detection"].items()})
    return res


def subsample(df, seed=SEED):
    rng = np.random.RandomState(seed)
    idx = []
    for f, g in df.groupby("family", observed=True).indices.items():
        k = N_BEN if f == "BENIGN" else N_FAM
        idx.append(g if len(g) <= k else rng.choice(g, k, replace=False))
    idx = np.sort(np.concatenate(idx))
    s = df.iloc[idx]
    return s.sort_values("t", kind="stable")


def evalset(layers, s):
    ev = {n: L.score(s) for n, L in layers.items()}
    y = (s.family != "BENIGN").to_numpy().astype(int)
    at = np.where(y == 1, s.family.astype(str).to_numpy(), "normal")
    return EvalSet(evidence=ev, y=y, attack_type=at, group=s.day.astype(str).to_numpy(), t=np.nan_to_num(s.t.to_numpy()))


def sub_es(es, names):
    return EvalSet(evidence={n: es.evidence[n] for n in names}, y=es.y, attack_type=es.attack_type, group=es.group, t=es.t)


def fams_eval(df, side):
    f = df[df.split == side].family.astype(str)
    return sorted(set(f) - {"BENIGN"})


def stage_portscan(layers, d10_test_ps):
    """PortScan flows BEFORE de-duplication inside the PortScan test window (stage cache): detection per layer."""
    import glob
    p = glob.glob(os.path.join(B, "D10", "stage", "*PortScan*.pkl"))[0]
    s = pd.read_pickle(p, compression="gzip")
    s = s[s.family == "PortScan"]
    lo, hi = d10_test_ps.ts.min(), d10_test_ps.ts.max()
    s = s[(s.ts >= lo) & (s.ts <= hi)].copy()
    for c in ("family", "day"):
        s[c] = s[c].astype(str) if c in s.columns else "x"
    out = {"n_flows": int(len(s)), "window": [str(lo), str(hi)], "detection": {}}
    for n, L in layers.items():
        sc = L.calibrator.transform(L.raw_scores(s))
        out["detection"][n] = float((sc >= L.threshold).mean())
    log("  PortScan pre-dedup test window:", out)
    return out


# ------------------------------------------------------------------------------------------------ D10
def run_d10():
    log("== D10", MODE)
    d = load_d10()
    tr = d[(d.family == "BENIGN") & (d.split == "train")]
    vb = d[(d.family == "BENIGN") & (d.split == "val")]
    layers = fit_layers(tr, vb)
    known = sorted(layers["net.allow_pair"].known)
    log("known hosts:", known)
    va = d[d.split == "val"]
    te = d[d.split == TEST]
    fams = fams_eval(d, "test")
    res = {"mode": MODE, "test_side": TEST, "n_train_benign": len(tr), "n_val_benign": len(vb), "n_test": len(te),
           "n_test_benign": int((te.family == "BENIGN").sum()), "known_hosts": known,
           "allow_params": {"min_support": l1.AllowPair.min_support, "rare_port": l1.AllowPair.rare_port}}
    res["layers"] = score_full(layers, te, fams)
    res["portscan_predup"] = stage_portscan(layers, te[te.family == "PortScan"])
    # harness on a fixed subsample
    vs, ts = subsample(va), subsample(te)
    ev_v, ev_t = evalset(layers, vs), evalset(layers, ts)
    res["subsample"] = {"val": len(vs), "test": len(ts)}
    for nm, names in (("all", sorted(layers)), ("no_identity", NOID)):
        r = evaluate_domain("s2_d10_" + nm, sub_es(ev_v, names), sub_es(ev_t, names), wp="WP4", out_dir=OUT)
        res["harness_" + nm] = {"combined": r["combined"], "ablation": r["ablation"]}
        log("  harness", nm, "combined FA %.4f det %.4f" % (r["combined"]["false_alarm_rate"], r["combined"]["detection"]),
            {k: round(v, 2) for k, v in r["combined"]["detection_by_attack"].items()})
    json.dump(res, open(os.path.join(OUT, "s2_d10.json"), "w"), indent=1)
    return layers, ev_v


# ------------------------------------------------------------------------------------------------ D23
def run_d23(d10_layers, d10_ev_val):
    log("== D23", MODE)
    d = load_d23()
    tue = (d.day.astype(str) == "2018-02-20")
    fams = fams_eval(d, "test")
    res = {"mode": MODE, "test_side": TEST, "families_test": fams}
    # (a) in-dataset
    tr, vb = d[(d.family == "BENIGN") & (d.split == "train")], d[(d.family == "BENIGN") & (d.split == "val")]
    te = d[d.split == TEST]
    lay = fit_layers(tr, vb, FLAGONLY)
    log(" in-dataset flag/protocol/rate layers, all files")
    res["in_dataset_flaglayers"] = score_full(lay, te, fams)
    trT, vbT, teT = tr[tue.loc[tr.index]], vb[tue.loc[vb.index]], te[tue.loc[te.index]]
    layT = fit_layers(trT, vbT, ["net.allow_pair", "net.allow_service"])
    log(" in-dataset allow-list layers, Tuesday 20-02 only (n_test=%d)" % len(teT))
    res["in_dataset_allow_tue"] = score_full(layT, teT, fams)
    vs, ts = subsample(d[d.split == "val"]), subsample(te)
    r = evaluate_domain("s2_d23_in_dataset_flag", evalset(lay, vs), evalset(lay, ts), wp="WP4", out_dir=OUT)
    res["harness_in_dataset_flag"] = {"combined": r["combined"], "ablation": r["ablation"]}
    log("  harness in-dataset flag combined FA %.4f det %.4f" % (r["combined"]["false_alarm_rate"], r["combined"]["detection"]))
    del lay, layT, tr, vb, trT, vbT, vs
    gc.collect()
    # (b) transfer: D10-fitted layers (calibrator + threshold from D10 validation), no refit
    log(" transfer D10 -> D23, flag layers, all files")
    fl = {n: d10_layers[n] for n in FLAGONLY}
    res["transfer_flaglayers"] = score_full(fl, te, fams)
    log(" transfer D10 -> D23, allow-list layers, Tuesday 20-02 (expected to fail)")
    al = {n: d10_layers[n] for n in ("net.allow_pair", "net.allow_service")}
    res["transfer_allow_tue"] = score_full(al, teT, fams)
    r = evaluate_domain("s2_d23_transfer_flag", sub_es(d10_ev_val, FLAGONLY), evalset(fl, ts), wp="WP4", out_dir=OUT)
    res["harness_transfer_flag"] = {"combined": r["combined"], "ablation": r["ablation"]}
    log("  harness transfer flag combined FA %.4f det %.4f" % (r["combined"]["false_alarm_rate"], r["combined"]["detection"]))
    json.dump(res, open(os.path.join(OUT, "s2_d23.json"), "w"), indent=1)


if __name__ == "__main__":
    ly, ev = run_d10()
    gc.collect()
    run_d23(ly, ev)
    log("done", MODE)
