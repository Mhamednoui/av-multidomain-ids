"""WP4 S6 leave-one-attack-out PREVIEW on VALIDATION (test never read).
For each held-out family X of S1 (11 evaluable) and the groups DoS-4 / WebAttack / BruteForce: train L4 WITHOUT X (same hyperparameters and tree count as the chosen model, no early stopping),
score the validation rows, threshold = tie-safe 1% budget of the benign validation scores, detection of X. Union with the topology-free base (tcp_flags + 5 L2a, thresholds of S3 / S4) if
../data_extra/cache_v3/WP4/S6/base_val.pkl exists. Output results/WP4/s6_loao.json (+ raw scores in the S6 cache).
Usage: python -u -W ignore tools/WP4_S6_loao.py [name ...]   (default: all)"""
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN
from common.metrics import auc, budget_threshold
from network.l4 import XGBNet
from tools.WP4_S6_lib import EVAL10, GROUPS_LOAO, RES, S6, feat, load_s6, log, sel

BASE = ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.slow"]


def base_alarm(pos):
    p = os.path.join(S6, "base_val.pkl")
    if not os.path.exists(p):
        return None
    b = pd.read_pickle(p).set_index("pos").loc[pos]
    cal = pickle.load(open(os.path.join(S6, "base_cal.pkl"), "rb"))
    al = np.zeros(len(b), bool)
    per = {}
    for n in BASE:
        c, thr, col = cal[n]
        a = c.transform(b[col].to_numpy(float)) >= thr
        per[n] = a
        al |= a
    return al, per


def main():
    chosen = json.load(open(os.path.join(RES, "s6_dev_val.json")))["chosen"]
    d, X = load_s6()
    mt, mv = sel(d, "train"), sel(d, "val")
    tr, va = feat(d, X, mt), feat(d, X, mv)
    fam_tr, fam_va = d["fam"].to_numpy()[mt], d["fam"].to_numpy()[mv]
    grp_tr = d["grp"].to_numpy()[mt]
    pos_va = d["pos"].to_numpy()[mv]
    ben = fam_va == "BENIGN"
    ba = base_alarm(pos_va)
    names = [(f, [f]) for f in EVAL10] + [(g, m) for g, m in GROUPS_LOAO.items()]
    if len(sys.argv) > 1:
        names = [x for x in names if x[0] in sys.argv[1:]]
    out_p = os.path.join(RES, "s6_loao.json")
    res = json.load(open(out_p)) if os.path.exists(out_p) else {}
    for nm, members in names:
        if nm in res:
            continue
        t0 = time.time()
        keep = ~np.isin(fam_tr, members)
        L = XGBNet(params=chosen["params"], n_trees=chosen["n_trees"]).fit(tr[keep], (fam_tr[keep] != "BENIGN").astype(int), grp_tr[keep])
        raw = L.raw_scores(va)
        thr = budget_threshold(raw[ben], BUDGET_DOMAIN)
        al = raw >= thr
        r = {"members": members, "n_train_removed": int((~keep).sum()), "fa_val_benign": float(al[ben].mean()), "threshold": float(thr), "per_member": {}}
        held = np.isin(fam_va, members)
        for m in members:
            mm = fam_va == m
            if mm.sum() == 0:
                continue
            y = np.r_[np.zeros(int(ben.sum())), np.ones(int(mm.sum()))]
            e = {"n": int(mm.sum()), "detection_l4": float(al[mm].mean()), "auc_l4": auc(y, np.r_[raw[ben], raw[mm]])}
            if ba is not None:
                bal, per = ba
                e["detection_base"] = float(bal[mm].mean())
                e["detection_union"] = float((bal | al)[mm].mean())
            r["per_member"][m] = e
        if members[0] != nm:
            mm = held
            y = np.r_[np.zeros(int(ben.sum())), np.ones(int(mm.sum()))]
            r["group"] = {"n": int(mm.sum()), "detection_l4": float(al[mm].mean()), "auc_l4": auc(y, np.r_[raw[ben], raw[mm]])}
            if ba is not None:
                r["group"]["detection_base"] = float(ba[0][mm].mean())
                r["group"]["detection_union"] = float((ba[0] | al)[mm].mean())
        if ba is not None:
            r["fa_base_val_benign"] = float(ba[0][ben].mean())
            r["fa_union_val_benign"] = float((ba[0] | al)[ben].mean())
        res[nm] = r
        json.dump(res, open(out_p, "w"), indent=1)
        log(nm, "FA %.4f" % r["fa_val_benign"], {k: (round(v["detection_l4"], 3), round(v["auc_l4"], 3)) for k, v in r["per_member"].items()}, "group", r.get("group"),
            "(%.0fs)" % (time.time() - t0))


if __name__ == "__main__":
    main()
