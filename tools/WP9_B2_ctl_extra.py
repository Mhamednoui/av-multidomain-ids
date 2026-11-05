"""WP9 B2 amendment diagnostic: extra shuffled-label seeds (4..10) for a (table, protocol) whose registered 3-seed control failed. Validation only.
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_ctl_extra.py <table> <proto>"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import WP9_B2_run as R
table, proto = sys.argv[1:3]
sel = json.load(open(os.path.join(R.RES, "%s_%s_select.json" % (table, proto))))
cand = sel["selected"]
d, part, boot, classes, cmap, fam, tr_all, y_tr, va, y_va = R.prep(table, proto)
keep = y_va >= 0
is_x = cand["kind"] == "xgb"
res = []
for seed in range(4, 11):
    y_sh = np.random.default_rng(seed).permutation(y_tr)
    (pr,), imp, info = R.fit_predict(cand, d, tr_all, y_sh, classes, [va], seed=seed, val_idx=va[keep] if is_x else None, y_val=y_va[keep] if is_x else None)
    m = R.metrics_basic(y_va[keep], pr[keep], classes, fam[tr_all], fam[va][keep], R.weights(d)[va][keep])
    res.append({"seed": seed, "macro_f1": m["macro_f1"], "auc_binary": m["auc_binary"]})
    R.log("ctl_extra", table, proto, res[-1])
base = json.load(open(os.path.join(R.RES, "%s_%s_control.json" % (table, proto))))["runs"]
allr = base + res
json.dump({"cand": cand, "extra_runs": res, "auc_mean_10_seeds": float(np.mean([r["auc_binary"] for r in allr])), "auc_std_10_seeds": float(np.std([r["auc_binary"] for r in allr])),
           "macro_f1_mean_10_seeds": float(np.mean([r["macro_f1"] for r in allr])), "note": "amendment diagnostic written after the registered 3-seed control failed; the registered verdict is unchanged"},
          open(os.path.join(R.RES, "%s_%s_control_extra.json" % (table, proto)), "w"), indent=1)
