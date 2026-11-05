"""WP9 B4 GPS step: fit + selection on VALIDATION only (Case I). 3 feature sets x 3 depths, XGBoost; thresholds H (1% val normal budget) and S (val max-F1).
No test session is read for any fit/choice here: test sessions are loaded as part of the frame but never indexed (assert at the end).
Output: results/WP9/B4_gps_selection.json, models in ../data_extra/cache_v3/WP9/B4/gps/. Run: python -u -W ignore tools/WP9_B4_gps_fit.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B4_gps_lib as L
from common.config import DATA_EXTRA
import numpy as np
from common.metrics import budget_threshold

OUT = L.ROOT / "results" / "WP9"
MODELS = DATA_EXTRA / "cache_v3" / "WP9" / "B4" / "gps"
DEPTHS = (3, 5, 7)


def main():
    t0 = time.time()
    MODELS.mkdir(parents=True, exist_ok=True)
    df = L.load_sessions()
    c1 = L.LOCK["case_I"]
    tr, va = L.rows(df, c1["train"]), L.rows(df, c1["val"])
    assert not set(tr.session) & set(va.session)
    assert not (set(tr.session) | set(va.session)) & set(c1["test"] + c1["test_normal_only_extra"])
    fsets = L.feature_sets(df)
    res = {"rule": "per feature set the depth with the highest validation F1 at the validation F1-optimal threshold (ties within 0.005: smaller depth)",
           "n_train_rows": int(len(tr)), "n_val_rows": int(len(va)), "sets": {}}
    for name, cols in fsets.items():
        cand = {}
        for d in DEPTHS:
            m = L.fit_xgb(tr[cols], tr.y, va[cols], va.y, depth=d)
            s = m.predict_proba(va[cols])[:, 1]
            thr_s, f1s = L.best_f1_threshold(va.y, s)
            thr_h = budget_threshold(s[va.y.to_numpy() == 0], 0.01)
            cand[d] = {"depth": d, "trees": L.n_trees(m), "val_auc": L.safe_auc(va.y, s), "thr_S": thr_s, "val_f1_S": f1s,
                       "thr_H": thr_h, "val_at_H": L.f1_at(va.y, s >= thr_h), "val_at_S": L.f1_at(va.y, s >= thr_s)}
            print(f"{name:8s} depth {d} trees {cand[d]['trees']:3d} val AUC {cand[d]['val_auc']:.4f} F1(S) {f1s:.4f} thr_S {thr_s:.3f} | H: rec {cand[d]['val_at_H']['recall']:.3f} fpr {cand[d]['val_at_H']['fpr']:.4f} ({time.time()-t0:.0f}s)", flush=True)
            m.save_model(str(MODELS / f"{name}_d{d}.json"))
        best = max(cand.values(), key=lambda c: (round(c["val_f1_S"] / 0.005), -c["depth"]))
        # tie rule: within 0.005 smaller depth
        top = max(c["val_f1_S"] for c in cand.values())
        best = min([c for c in cand.values() if top - c["val_f1_S"] <= 0.005], key=lambda c: c["depth"])
        res["sets"][name] = {"features": cols, "candidates": {str(k): v for k, v in cand.items()}, "chosen_depth": best["depth"], "chosen": best}
        print("chosen", name, best["depth"], flush=True)
    (OUT / "B4_gps_selection.json").write_text(json.dumps(res, indent=1))
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
