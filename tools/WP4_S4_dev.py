"""WP4 S4 development on TRAIN/VAL only (D10): beaconing statistics, choice of WIN / N_MIN. Test is never read.
Output: results/WP4/s4_dev_val.json"""
import json, os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.WP4_S3_lib import RES, load, log, stream, flow_eval, window_eval
from network import l2b
from common.config import BUDGET_DOMAIN

d = load("D10")
tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
del d
out = {}
for win, n_min, pc in [(64, 4, False), (64, 5, False), (64, 6, False), (64, 8, False), (32, 4, False), (32, 6, False), (64, 6, True)]:
    t0 = time.time()
    L = l2b.Beacon(win=win, n_min=n_min, port_cond=pc)
    L.fit(tr)
    subs = {s: l2b.BeaconStat(s, win=win, n_min=n_min) for s in l2b.STATS}
    for X in (vb, vm):
        f = L.feats(X)
        sc = L.stat_scores(f)
        X[L.score_col] = np.max(np.vstack([sc[k] for k in l2b.PHASE]), axis=0)
        for s, S in subs.items():
            X[S.score_col] = sc[s]
    res = {}
    for LL in [L] + list(subs.values()):
        LL.calibrate(vb, BUDGET_DOMAIN)
        fe = flow_eval(LL, vm, ["Bot"])
        res[LL.name] = {"fa": fe["fa_benign"], "bot": fe["detection"].get("Bot"), "thr": LL.threshold, "auc": fe["auc"]}
        log(win, n_min, pc, LL.name, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res[LL.name].items()})
    out[f"{win}_{n_min}_{pc}"] = res
    log("  time", round(time.time() - t0))
json.dump(out, open(os.path.join(RES, "s4_dev_val.json"), "w"), indent=1)
