"""WP9 B4 GPS: the ONE test scoring of the supervised AV-GPS models (refuses to run unless selection + controls files exist and are committed).
Case I: models chosen on validation (results/WP9/B4_gps_selection.json), thresholds H / S fixed on validation; test = file-2 sessions (+ file-3 normals: false alarms only).
Case II: train on file 2 (all 5 sessions), depth and number of trees from Case I, threshold 0.5; test = all file-1 sessions (+ file-3 normals).
Output: results/WP9/B4_gps_test.json, scores results/WP9/scores/B4/gps_test_caseI.npz / caseII.npz, exposure appended by tools/WP9_B4_exposure.py.
Run: python -u -W ignore tools/WP9_B4_gps_test.py
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import xgboost as xgb

import WP9_B4_gps_lib as L
from common.config import DATA_EXTRA

OUT = L.ROOT / "results" / "WP9"
MODELS = DATA_EXTRA / "cache_v3" / "WP9" / "B4" / "gps"


def committed(path):
    r = subprocess.run(["git", "status", "--porcelain", "--", str(path)], cwd=L.ROOT, capture_output=True, text=True)
    t = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=L.ROOT, capture_output=True, text=True)
    return t.returncode == 0 and r.stdout.strip() == ""


def block(y, s, thr, sess, extra_mask=None):
    pred = s >= thr
    m = L.f1_at(y, pred)
    m["auc"] = L.safe_auc(y, s)
    m["ci_session_cluster"] = L.cluster_boot(y, s, pred, sess)
    m["by_session"] = {k: {"label": int(y[sess == k][0]), "rows": int((sess == k).sum()), "alarm_rate": float(pred[sess == k].mean())} for k in sorted(set(sess))}
    m["thr"] = float(thr)
    return m


def main():
    t0 = time.time()
    for f in ("B4_gps_selection.json", "B4_gps_controls.json"):
        assert committed(OUT / f), f"{f} must be committed before the test is scored"
    df = L.load_sessions()
    sel = json.loads((OUT / "B4_gps_selection.json").read_text())
    c1, c2 = L.LOCK["case_I"], L.LOCK["case_II"]
    res = {"case_I": {}, "case_II": {}, "note": "test scored once per case (notes/WP9_B4.md)"}
    te1, te1x = L.rows(df, c1["test"]), L.rows(df, c1["test_normal_only_extra"])
    sc = {}
    for name, S in sel["sets"].items():
        cols, d = S["features"], S["chosen_depth"]
        m = xgb.XGBClassifier()
        m.load_model(str(MODELS / f"{name}_d{d}.json"))
        s = m.predict_proba(te1[cols])[:, 1]
        sx = m.predict_proba(te1x[cols])[:, 1]
        ch = S["chosen"]
        r = {"depth": d, "trees": ch["trees"]}
        for op, thr in (("H", ch["thr_H"]), ("S", ch["thr_S"])):
            b = block(te1.y.to_numpy(), s, thr, te1.session.to_numpy())
            b["fpr_file3_normals"] = float((sx >= thr).mean())
            b["val_reference"] = ch["val_at_H" if op == "H" else "val_at_S"]
            r[op] = b
        res["case_I"][name] = r
        sc[name] = s
        print("CASE I", name, {op: (round(r[op]["f1"], 4), round(r[op]["recall"], 4), round(r[op]["fpr"], 4), round(r[op]["auc"], 4)) for op in ("H", "S")}, flush=True)
    np.savez_compressed(OUT / "scores" / "B4" / "gps_test_caseI.npz", y=te1.y.to_numpy(), session=te1.session.to_numpy(), **sc)
    # Case II
    tr2, te2 = L.rows(df, c2["train"]), L.rows(df, c2["test"])
    te2x = L.rows(df, c2["test_normal_only_extra"])
    sc2 = {}
    for name, S in sel["sets"].items():
        cols, d, nt = S["features"], S["chosen_depth"], S["chosen"]["trees"]
        m = L.fit_xgb(tr2[cols], tr2.y, None, None, depth=d, n_rounds=nt)
        s = m.predict_proba(te2[cols])[:, 1]
        sx = m.predict_proba(te2x[cols])[:, 1]
        b = block(te2.y.to_numpy(), s, 0.5, te2.session.to_numpy())
        b["fpr_file3_normals"] = float((sx >= 0.5).mean())
        b["depth"], b["trees"] = d, nt
        res["case_II"][name] = b
        sc2[name] = s
        print("CASE II", name, round(b["f1"], 4), round(b["recall"], 4), round(b["fpr"], 4), round(b["auc"], 4), flush=True)
    np.savez_compressed(OUT / "scores" / "B4" / "gps_test_caseII.npz", y=te2.y.to_numpy(), session=te2.session.to_numpy(), **sc2)
    (OUT / "B4_gps_test.json").write_text(json.dumps(res, indent=1))
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
