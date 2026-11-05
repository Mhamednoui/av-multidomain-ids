"""WP9 B2 amendment diagnostic: shuffled-label control (validation only, seeds 1-3) with a NAMED candidate (default xgb_d6_f76), to tell whether a failed AUC criterion of the
selected model (random forest) is specific to that learner. Run (codes_v3): python -u -W ignore -I tools/WP9_B2_ctl_xgb.py <table> <proto> [cand_id]"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import WP9_B2_run as R
table, proto = sys.argv[1:3]
cid = sys.argv[3] if len(sys.argv) > 3 else "xgb_d6_f76"
cand = [c for c in R.CANDS if c["id"] == cid][0]
d, part, boot, classes, cmap, fam, tr_all, y_tr, va, y_va = R.prep(table, proto)
keep = y_va >= 0
is_x = cand["kind"] == "xgb"
res = []
for seed in (1, 2, 3):
    y_sh = np.random.default_rng(seed).permutation(y_tr)
    (pr,), imp, info = R.fit_predict(cand, d, tr_all, y_sh, classes, [va], seed=seed, val_idx=va[keep] if is_x else None, y_val=y_va[keep] if is_x else None)
    m = R.metrics_basic(y_va[keep], pr[keep], classes, fam[tr_all], fam[va][keep], R.weights(d)[va][keep])
    res.append({"seed": seed, "macro_f1": m["macro_f1"], "auc_binary": m["auc_binary"]})
    R.log("ctl_named", table, proto, cid, res[-1])
json.dump({"cand": cand, "runs": res, "note": "amendment diagnostic (validation only); the registered control is *_control.json"}, open(os.path.join(R.RES, "%s_%s_control_%s.json" % (table, proto, cid)), "w"), indent=1)
