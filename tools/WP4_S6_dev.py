"""WP4 S6 development on VALIDATION only: random search (v2 SPACE) for the L4 XGBoost. Writes results/WP4/s6_dev_val.json, saves the chosen model to the S6 cache.
Selection (fixed in notes before any score): macro over the 11 evaluable families of the detection at the tie-safe 1% budget of the benign validation scores; ties -> macro AUC."""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from network.l4 import SPACE, XGBNet, sample_params
from tools.WP4_S6_lib import RES, S6, load_s6, log, sel, feat, macro_at_budget

N_TRIALS = int(sys.argv[1]) if len(sys.argv) > 1 else 6
# v2 SPACE restricted for run time on the shared machine (the first full-space attempt, trial 1 = 457 s at depth 3, was aborted after 25 min; log s6_dev_aborted_fullspace.log):
# no learning rate 0.03 / 0.05 and no depth 10 (v2 chose depth 5, lr 0.2)
DEV_SPACE = dict(SPACE, learning_rate=[0.1, 0.2], max_depth=[3, 4, 5, 6, 8])
d, X = load_s6()
mt, mv = sel(d, "train"), sel(d, "val")
tr, va = feat(d, X, mt), feat(d, X, mv)
ytr, yva = (d["fam"].to_numpy()[mt] != "BENIGN").astype(int), (d["fam"].to_numpy()[mv] != "BENIGN").astype(int)
gtr, fam_va = d["grp"].to_numpy()[mt], d["fam"].to_numpy()[mv]
log("train", len(tr), "attack", int(ytr.sum()), "val", len(va), "attack", int(yva.sum()))
log("train family counts", dict(zip(*np.unique(d["fam"].to_numpy()[mt], return_counts=True))))
rng = np.random.default_rng(42)
trials, best = [], None
t0 = time.time()
for k in range(N_TRIALS):
    p = sample_params(rng, DEV_SPACE)
    L = XGBNet(params=p).fit(tr, ytr, gtr, val=va, y_val=yva)
    raw = L.raw_scores(va)
    r = macro_at_budget(raw, fam_va, np.ones(len(va), bool))
    t = {"params": {kk: (float(v) if isinstance(v, (float, np.floating)) else int(v)) for kk, v in p.items()}, "n_trees": L.best_n_trees, "macro": r["macro"], "macro_auc": r["macro_auc"],
         "fa_val": r["fa_benign"], "detection": r["detection"], "seconds": time.time() - t0}
    trials.append(t)
    log("trial %d/%d macro %.4f auc %.4f trees %d (%.0fs)" % (k + 1, N_TRIALS, r["macro"], r["macro_auc"], L.best_n_trees, time.time() - t0), t["params"],
        {a: round(b, 2) for a, b in r["detection"].items()})
    if best is None or (r["macro"], r["macro_auc"]) > (best[0], best[1]):
        best = (r["macro"], r["macro_auc"], t, L)
t = best[2]
best[3].model.save_model(os.path.join(S6, "l4_model.json"))
json.dump({"rule": "max macro detection of 11 families at 1% benign-val budget, ties -> macro AUC", "chosen": {"params": t["params"], "n_trees": t["n_trees"]},
           "val_macro": best[0], "val_macro_auc": best[1], "trials": trials, "n_train": len(tr), "n_val": len(va)}, open(os.path.join(RES, "s6_dev_val.json"), "w"), indent=1)
log("CHOSEN", t["params"], t["n_trees"], "macro %.4f" % best[0])
