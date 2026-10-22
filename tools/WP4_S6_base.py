"""WP4 S6: scores of the topology-free base stack (tcp_flags + 5 L2a + beacon) and the on-network L3 (service profile, AE) on the D10 validation and test streams.
Same fitting / calibration as S3, S4, S5 (benign TRAIN fit, tie-safe 1% on benign validation, audited Infiltration file excluded; configurations from s3_dev_val.json / s5_dev_val.json;
nothing is chosen here). Output: ../data_extra/cache_v3/WP4/S6/base_val.pkl (harness version: benign val rows carry the benign-only-stream scores, as in S4 / S5), base_test.pkl,
base_cal.pkl (calibrator + threshold per layer). The test file is read only by the S6 verdict script."""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN
from network import l1, l2a, l2b, l3
from tools.WP4_S3_lib import add_scores, fit_calibrate, load, log, stream
from tools.WP4_S5_lib import RES, frame, load_d10
from tools.WP4_S6_lib import S6

L2A = ["net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.slow"]


def add_beacon(df, B):
    f = B.feats(df)
    sc = B.stat_scores(f)
    df[B.score_col] = np.max(np.vstack([sc[k] for k in l2b.PHASE]), axis=0)


def main():
    chosen = json.load(open(os.path.join(RES, "s5_dev_val.json")))["chosen"]
    dev = json.load(open(os.path.join(RES, "s3_dev_val.json")))["chosen"]
    d, X = load_d10()
    tr, vb, vm, te = stream(d, "train", True), stream(d, "val", True), stream(d, "val"), stream(d, "test")
    ben_pos = np.flatnonzero(((vm["family"].astype(str) == "BENIGN") & ~vm["audit"]).to_numpy())
    tr_f, vb_f = frame(d, X, d["split"].astype(str).eq("train").to_numpy() & (d["family"].astype(str) == "BENIGN").to_numpy() & ~d["audit"].to_numpy()), None
    vb_f = frame(d, X, d["split"].astype(str).eq("val").to_numpy() & (d["family"].astype(str) == "BENIGN").to_numpy() & ~d["audit"].to_numpy())
    vm_f, te_f = frame(vm, X), frame(te, X)
    assert len(tr) == len(tr_f) and len(vb) == len(vb_f)
    l2 = l2a.all_layers(dev)
    fit_calibrate(l2, tr, vb)
    B = l2b.Beacon()
    fit_calibrate([B], tr, vb)
    add_scores(vb, l2)
    add_beacon(vb, B)
    for df in (vm, te):
        add_scores(df, l2)
        add_beacon(df, B)
    tf = l1.TcpFlags().fit(tr)
    tf.calibrate(vb, BUDGET_DOMAIN)
    tf.score_col = "s_net.tcp_flags"
    cal = {}
    for L in l2 + [B, tf]:
        cal[L.name] = (L.calibrator, float(L.threshold), L.score_col)
    # L3: service profile + AE (iforest dropped in S5 review)
    for key, cls in (("service", l3.ServiceProfile), ("ae", l3.AutoEncoder)):
        kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in chosen[key]["params"].items()}
        L = cls(feature_set_name="clean", **kw)
        L.fit(tr_f)
        L.calibrate(vb_f, BUDGET_DOMAIN)
        L.score_col = "s_" + L.name
        vm[L.score_col] = L.raw_scores(vm_f)
        te[L.score_col] = L.raw_scores(te_f)
        vb[L.score_col] = L.raw_scores(vb_f)
        cal[L.name] = (L.calibrator, float(L.threshold), L.score_col)
        log("fitted", L.name)
    vm_h = vm.copy()
    cols = [c[2] for c in cal.values() if c[2] not in ("s_net.tcp_flags",)]
    for c in cols:
        vm_h.loc[vm_h.index[ben_pos], c] = vb[c].to_numpy()
    for X_ in (vm_h, te):
        X_[tf.score_col] = tf.raw_scores(X_)
    keep = ["pos", "family", "day", "t", "audit", "period", "split"] + [c[2] for c in cal.values()]
    vm_h[keep].to_pickle(os.path.join(S6, "base_val.pkl"))
    te[keep].to_pickle(os.path.join(S6, "base_test.pkl"))
    pickle.dump(cal, open(os.path.join(S6, "base_cal.pkl"), "wb"))
    log("saved", len(vm_h), len(te), {k: (round(v[1], 4)) for k, v in cal.items()})


if __name__ == "__main__":
    main()
