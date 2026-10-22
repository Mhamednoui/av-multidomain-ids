"""WP4 S7 development on VALIDATION only (test never read): combiner selection for every stack and every all-but-one sub-stack of H and O, dos_rate warm-up length.
Combiner: common.combiner.DomainCombiner(method="auto") (noisy_or log form / max / logistic; held-out-half detection at the 1% budget; groups = day x period) fitted on the
S6-harness subsample of the validation stream. Output: results/WP4/s7_dev_val.json, ../data_extra/cache_v3/WP4/S7/combiners.pkl (frozen before the test script runs).
Usage: python -u -W ignore tools/WP4_S7_dev.py"""
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN
from network import l2a
from tools.WP4_S3_lib import fit_calibrate, flow_eval, load, stream
from tools.WP4_S7_lib import EVAL10, H, O, RES, S7, STACKS, Scorer, comb_alarm, fit_combiner, layer_alarm, load_tables, log, val_sample


def main():
    val, test, cal = load_tables()
    del test
    vs = val_sample(val)
    log("validation subsample", len(vs), vs["fam"].value_counts().to_dict())
    res = {"n_val_sample": int(len(vs)), "selection": {}, "method": {}, "threshold": {}}
    combs = {}
    todo = {k: v for k, v in STACKS.items() if k != "L4 alone"}
    for nm, names in list(todo.items()):
        todo[nm] = names
    for base in ("H", "O"):
        for n in STACKS[base]:
            todo[f"{base} all-but {n}"] = [m for m in STACKS[base] if m != n]
    # the O+x stacks' selection and the ablation sub-stacks
    for nm, names in todo.items():
        t0 = time.time()
        C = fit_combiner(vs, cal, names)
        combs[nm] = {"names": list(C.layer_names), "method": C.method, "model": C.model, "threshold": float(C.threshold)}
        res["selection"][nm] = C.selection
        res["method"][nm] = C.method
        res["threshold"][nm] = float(C.threshold)
        # validation view (information; in-sample for the threshold)
        s, al = comb_alarm(C, val[~val["audit"].to_numpy()], cal)
        sc = Scorer(val[~val["audit"].to_numpy()], families=EVAL10)
        r = sc.summary(al, ci=False)
        res.setdefault("val_view", {})[nm] = {"fa": r["fa"], "macro": r["macro"], "detection": r["detection"]}
        log("%-22s method %-9s sel %s FA %.4f macro %.3f (%.0fs)" % (nm, C.method, {k: round(v, 3) for k, v in C.selection.items()}, r["fa"], r["macro"], time.time() - t0))
    pickle.dump(combs, open(os.path.join(S7, "combiners.pkl"), "wb"))
    # ---- dos_rate warm-up length (validation, information): first f of the warm-up minutes of the benign train stream
    log("dos_rate warm-up sweep")
    dev = json.load(open(os.path.join(RES, "s3_dev_val.json")))["chosen"]
    d = load("D10")
    tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
    mins = np.sort(tr["minute"].unique())
    res["warmup"] = {"n_warmup_minutes_total": int(len(mins)), "n_warmup_flows_total": int(len(tr))}
    for frac in (0.1, 0.25, 0.5, 1.0):
        cut = mins[max(int(len(mins) * frac) - 1, 0)]
        sub = tr[tr["minute"] <= cut].reset_index(drop=True)
        L = l2a.DosRate(W=dev.get("net.dos_rate", 1))
        fit_calibrate([L], sub, vb)
        L_s = L.stream_scores(vm)
        vm[L.score_col] = L_s
        fe = flow_eval(L, vm, ["DoS-Hulk", "DoS-GoldenEye", "DDoS-LOIC-HTTP"])
        res["warmup"][str(frac)] = {"minutes": int(len(np.unique(sub["minute"]))), "flows": int(len(sub)), "known_destinations": int(len(L.ids)),
                                    "fa_benign_val": fe["fa_benign"], "detection": fe["detection"], "auc": fe["auc"]}
        log(" warm-up", frac, res["warmup"][str(frac)])
    json.dump(res, open(os.path.join(RES, "s7_dev_val.json"), "w"), indent=1)
    log("saved s7_dev_val.json and combiners.pkl")


if __name__ == "__main__":
    main()
