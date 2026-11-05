"""WP9 B2: recompute the test report from the SAVED scores (results/WP9/scores/B2/*.npz) with the current tools/WP9_B2_report.py. No model is refit and the test set is
not scored again; used after the bootstrap fix (eligible classes absent from a resample are skipped). Point estimates must not change (checked).
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_recompute.py <table> <proto> [...]"""
import json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import WP9_B2_run as R
from WP9_B2_report import report

for k in range(1, len(sys.argv), 2):
    table, proto = sys.argv[k], sys.argv[k + 1]
    p = os.path.join(R.RES, "%s_%s_test.json" % (table, proto))
    old = json.load(open(p))
    d, part, boot, classes, cmap, fam, tr_all, y_tr, va, y_va = R.prep(table, proto)
    zv = np.load(os.path.join(R.SCORES, "%s_%s_val.npz" % (table, proto)), allow_pickle=True)
    zt = np.load(os.path.join(R.SCORES, "%s_%s_test.npz" % (table, proto)), allow_pickle=True)
    w = R.weights(d)
    new = report(classes, fam[tr_all], zv["family"], zv["proba"].astype(np.float32), zt["family"], zt["proba"].astype(np.float32), zt["boot"], w[zv["idx"]], w[zt["idx"]])
    # saved probabilities are float16: point estimates of the original float32 scoring are kept, only the CIs are replaced
    assert abs(new["macro_f1"] - old["macro_f1"]) < 5e-3 and abs(new["auc_binary"] - old["auc_binary"]) < 2e-3, (old["macro_f1"], new["macro_f1"])
    for key, v in new.items():
        if key.endswith("_ci"):
            old[key] = v
    for c, m in new["per_class"].items():
        old["per_class"][c]["recall_ci"] = m["recall_ci"]
    old["ci_recomputed_from_saved_scores"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    json.dump(old, open(p, "w"), indent=1)
    print(table, proto, "macroF1 %.4f %s" % (new["macro_f1"], new["macro_f1_ci"]), flush=True)
