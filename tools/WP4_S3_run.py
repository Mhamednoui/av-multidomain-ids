"""WP4 S3 run: L2a host time-window layers (network/l2a.py) on D10 and D23 Tue-20-02.

Usage: python -u -W ignore tools/WP4_S3_run.py smoke|verdict
  smoke   : the "test" side is the VALIDATION split (pipeline check, nothing about test read); writes results/WP4/smoke/
  verdict : the ONE run on test (D10 test; D23 Tue-20-02 test, transfer without refit and refit); writes results/WP4/s3_*.json
Windows W per layer: from results/WP4/s3_dev_val.json (chosen on validation). Fit on the BENIGN-only train stream, calibration (flow unit via
Layer.calibrate, window unit via a raw cell threshold, both tie-safe 1%) on the BENIGN-only val stream; test = mixed stream.
Audited file (D10 Thursday afternoon, compromised-host scan labelled BENIGN) is excluded from benign fit / calibration / headline FA but kept in the
stream; FA with the published labels is reported next to it.
Harness (common/evaluate.py): topology-free L1 (net.tcp_flags, refit on stage benign train/val) + the five L2a layers, on a fixed subsample drawn
AFTER the window features are computed on the full stream.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN, SEED
from common.evaluate import EvalSet, evaluate_domain
from network import l1, l2a
from tools.WP4_S3_lib import RES, add_scores, fit_calibrate, flow_eval, load, log, stream, subsample, window_eval

MODE = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert MODE in ("smoke", "verdict")
TEST = "val" if MODE == "smoke" else "test"
OUT = RES if MODE == "verdict" else os.path.join(RES, "smoke")
os.makedirs(OUT, exist_ok=True)
N_BEN, N_FAM = 150_000, 20_000
L2A = ["net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.slow"]


def families_of(df):
    return sorted(set(df["family"].astype(str)) - {"BENIGN"})


def or_combo(layers, df, fams):
    """Any L2a layer alarms (flow unit)."""
    al = np.zeros(len(df), bool)
    for L in layers:
        al |= L.calibrator.transform(df[L.score_col].to_numpy(float)) >= L.threshold
    fam = df["family"].astype(str).to_numpy()
    ben = (fam == "BENIGN") & ~df["audit"].to_numpy()
    out = {"fa_benign": float(al[ben].mean()), "fa_benign_published_labels": float(al[fam == "BENIGN"].mean()),
           "detection": {f: float(al[fam == f].mean()) for f in fams if (fam == f).any()}}
    if "in_final" in df:
        m = df["in_final"].to_numpy()
        out["detection_dedup_subset"] = {f: float(al[(fam == f) & m].mean()) for f in fams if ((fam == f) & m).any()}
    return out


def evalset(layers, s):
    ev = {L.name: L.score(s) for L in layers}
    y = (s["family"].astype(str) != "BENIGN").to_numpy().astype(int)
    at = np.where(y == 1, s["family"].astype(str).to_numpy(), "normal")
    return EvalSet(evidence=ev, y=y, attack_type=at, group=s["day"].astype(str).to_numpy(), t=np.nan_to_num(s["t"].to_numpy()))


def sub(es, names):
    return EvalSet(evidence={n: es.evidence[n] for n in names}, y=es.y, attack_type=es.attack_type, group=es.group, t=es.t)


def mark_in_final(d):
    import glob
    B = os.path.join(os.path.dirname(__file__), "..", "..", "data_extra", "cache_v3", "WP4", "D10", "final")
    keys = pd.concat([pd.read_pickle(f, compression="gzip")[["file", "row"]] for f in glob.glob(os.path.join(B, "*.pkl"))], ignore_index=True)
    keys["k"] = keys["file"].astype(str) + "|" + keys["row"].astype(str)
    k = d["file"].astype(str) + "|" + d["row"].astype(str)
    return k.isin(set(keys["k"])).to_numpy()


def per_layer(layers, df, fams, same_network=True):
    res = {}
    for L in layers:
        fe, we = flow_eval(L, df, fams), window_eval(L, df, fams)
        res[L.name] = {"W": L.W, "flow": fe, "window": we}
        log("  ", L.name, "W", L.W, "FA %.4f (pub %.4f) win FA %.4f" % (fe["fa_benign"], fe["fa_benign_published_labels"], we["fa_benign_cells"]),
            {k: round(v, 2) for k, v in fe["detection"].items()})
    return res


def run_d10():
    log("== D10", MODE)
    dev = json.load(open(os.path.join(RES, "s3_dev_val.json")))["chosen"]
    d = load("D10")
    d["in_final"] = mark_in_final(d)
    tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
    te = vm if MODE == "smoke" else stream(d, "test")
    ben_pos = np.flatnonzero(((vm["family"].astype(str) == "BENIGN") & ~vm["audit"]).to_numpy())
    del d
    layers = l2a.all_layers(dev)
    fit_calibrate(layers, tr, vb)
    res = {"mode": MODE, "test_side": TEST, "W": dev, "n_train_benign": len(tr), "n_val_benign": len(vb), "n_test": len(te),
           "win_threshold": {L.name: L.win_threshold for L in layers}, "flow_threshold": {L.name: L.threshold for L in layers}}
    # L1 topology-free (tcp_flags) on the stage streams
    tf = l1.TcpFlags().fit(tr)
    tf.calibrate(vb, BUDGET_DOMAIN)
    # features: benign val rows from the benign-only stream (calibration side), attack rows from the mixed stream
    add_scores(vb, layers)
    add_scores(vm, layers)
    if MODE == "verdict":
        add_scores(te, layers)
    else:
        te = vm
    vm_h = vm.copy()
    for L in layers:
        vm_h.loc[vm_h.index[ben_pos], L.score_col] = vb[L.score_col].to_numpy()
    fams = families_of(te)
    res["families"] = fams
    res["layers"] = per_layer(layers, te, fams)
    res["or_l2a"] = or_combo(layers, te, fams)
    log("  OR", {k: round(v, 2) for k, v in res["or_l2a"]["detection"].items()}, "FA %.4f" % res["or_l2a"]["fa_benign"])
    # tcp_flags flow-unit numbers on the same stream
    tf.score_col = "s_net.tcp_flags"
    for X in (te, vm_h):
        X[tf.score_col] = tf.raw_scores(X)
    res["layers"]["net.tcp_flags"] = {"W": None, "flow": flow_eval(tf, te, fams), "window": None}
    # ---- harness
    layers_h = layers + [tf]
    val_h = vm_h[~vm_h["audit"].to_numpy()]
    test_h = te[~te["audit"].to_numpy()]
    vs, ts = subsample(val_h, N_BEN, N_FAM, SEED).sort_values("t", kind="stable"), subsample(test_h, N_BEN, N_FAM, SEED).sort_values("t", kind="stable")
    res["subsample"] = {"val": len(vs), "test": len(ts)}
    ev_v, ev_t = evalset(layers_h, vs), evalset(layers_h, ts)
    for nm, names in (("l1_l2a", [L.name for L in layers_h]), ("l2a_only", L2A)):
        r = evaluate_domain("s3_d10_" + nm, sub(ev_v, names), sub(ev_t, names), wp="WP4", out_dir=OUT)
        res["harness_" + nm] = {"combined": r["combined"], "ablation": r["ablation"]}
        log("  harness", nm, "combined FA %.4f det %.4f" % (r["combined"]["false_alarm_rate"], r["combined"]["detection"]),
            {k: round(v, 2) for k, v in r["combined"]["detection_by_attack"].items()})
    json.dump(res, open(os.path.join(OUT, "s3_d10.json"), "w"), indent=1)
    return layers, dev


def run_d23(d10_layers, dev):
    log("== D23 Tue-20-02", MODE)
    d = load("D23tue")
    tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
    te = vm if MODE == "smoke" else stream(d, "test")
    del d
    fams = families_of(te)
    res = {"mode": MODE, "test_side": TEST, "families": fams, "n_test": len(te), "n_train_benign": len(tr), "n_val_benign": len(vb)}
    log(" transfer (D10 tables and thresholds, destination baseline not looked up)")
    add_scores(te, d10_layers, same_network=False)
    res["transfer"] = per_layer(d10_layers, te, fams)
    res["transfer_or"] = or_combo(d10_layers, te, fams)
    log("  OR", {k: round(v, 2) for k, v in res["transfer_or"]["detection"].items()}, "FA %.4f" % res["transfer_or"]["fa_benign"])
    log(" refit on D23 benign train / val")
    layers = l2a.all_layers(dev)
    fit_calibrate(layers, tr, vb)
    add_scores(te, layers)
    res["refit"] = per_layer(layers, te, fams)
    res["refit_or"] = or_combo(layers, te, fams)
    log("  OR", {k: round(v, 2) for k, v in res["refit_or"]["detection"].items()}, "FA %.4f" % res["refit_or"]["fa_benign"])
    json.dump(res, open(os.path.join(OUT, "s3_d23.json"), "w"), indent=1)


if __name__ == "__main__":
    layers, dev = run_d10()
    run_d23(layers, dev)
