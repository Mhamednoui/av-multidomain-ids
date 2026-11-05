"""WP9 B4 LiDAR: fit + selection on VALIDATION (13 train drives -> 3 val drives). 4-class XGBoost, 12 random-search trials x weight power {0.5, 1.0}.
Criterion: validation mean over the 9 kinds of TPR at validation FPR 10% (ties within 0.005: fewer trees, then shallower). Test rows are never loaded.
Output: results/WP9/B4_lidar_selection.json, model ../data_extra/cache_v3/WP9/B4/lidar_model/chosen.json, scores results/WP9/scores/B4/lidar_val.npz.
Run: python -u -W ignore tools/WP9_B4_lidar_fit.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import xgboost as xgb

import WP9_B4_lidar_lib as L
from lidar.train_xgb import SPACE, class_weights

OUT = L.ROOT / "results" / "WP9"
MODELS = L.CACHE.parent / "lidar_model"
N_TRIALS = 12


def fit(prm, wp, Xtr, ytr, Xva, yva, seed=42, n_rounds=None):
    kw = dict(objective="multi:softprob", num_class=4, eval_metric="mlogloss", tree_method="hist", random_state=seed, n_jobs=4, **prm)
    w = class_weights(ytr, wp)
    if n_rounds is None:
        m = xgb.XGBClassifier(n_estimators=3000, early_stopping_rounds=50, **kw)
        m.fit(Xtr, ytr, sample_weight=w, eval_set=[(Xva, yva)], verbose=False)
    else:
        m = xgb.XGBClassifier(n_estimators=n_rounds, **kw)
        m.fit(Xtr, ytr, sample_weight=w, verbose=False)
    return m


def score(m, X):
    return 1.0 - m.predict_proba(X)[:, 0]


def main():
    t0 = time.time()
    MODELS.mkdir(parents=True, exist_ok=True)
    mtr, Xtr = L.load("train")
    mva, Xva = L.load("val")
    assert not set(mtr.drive) & set(mva.drive)
    ytr, yva = mtr.cls.to_numpy(), mva.cls.to_numpy()
    print("train rows", len(mtr), np.bincount(ytr), "val rows", len(mva), np.bincount(yva), flush=True)
    rng = np.random.default_rng(42)
    trials = []
    for k in range(N_TRIALS):
        prm = {key: vals[rng.integers(len(vals))] for key, vals in SPACE.items()}
        wp = [0.5, 1.0][k % 2]
        m = fit(prm, wp, Xtr, ytr, Xva, yva)
        s = score(m, Xva)
        obj, tpr, thr = L.val_objective(mva, s, 0.10)
        o1, t1, _ = L.val_objective(mva, s, 0.01)
        nt = int(m.best_iteration + 1)
        rec = {"trial": k, "params": prm, "weight_power": wp, "trees": nt, "val_obj_tpr10_mean": obj, "val_obj_tpr1_mean": o1, "val_auc_any": L.auc_any(mva, s), "tpr10": tpr}
        trials.append(rec)
        print(f"trial {k:2d} depth {prm['max_depth']} lr {prm['learning_rate']} wp {wp} trees {nt:4d} val mean TPR@10% {obj:.4f} @1% {o1:.4f} AUC {rec['val_auc_any']:.4f} ({time.time()-t0:.0f}s)", flush=True)
    top = max(t["val_obj_tpr10_mean"] for t in trials)
    chosen = min([t for t in trials if top - t["val_obj_tpr10_mean"] <= 0.005], key=lambda t: (t["trees"], t["params"]["max_depth"], t["trial"]))
    m_best = fit(chosen["params"], chosen["weight_power"], Xtr, ytr, Xva, yva)
    assert int(m_best.best_iteration + 1) == chosen["trees"]
    best = (None, chosen, m_best)
    best[2].save_model(str(MODELS / "chosen.json"))
    s = score(best[2], Xva)
    np.savez_compressed(OUT / "scores" / "B4" / "lidar_val.npz", s=s, cls=yva, attack=mva.attack.to_numpy(), drive=mva.drive.to_numpy(), i=mva.i.to_numpy())
    obj, tpr, thr10 = L.val_objective(mva, s, 0.10)
    _, tpr1, thr1 = L.val_objective(mva, s, 0.01)
    per_drive = {d: L.auc_any(mva[mva.drive == d], s[(mva.drive == d).to_numpy()]) for d in sorted(set(mva.drive))}
    res = {"rule": "max validation mean TPR@FPR10% over 9 kinds; ties within 0.005: fewer trees then shallower", "n_train_rows": int(len(mtr)), "n_val_rows": int(len(mva)),
           "trials": trials, "chosen": chosen, "val_thr10": thr10, "val_thr1": thr1, "val_tpr10": tpr, "val_tpr1": tpr1, "val_auc_per_drive": per_drive}
    (OUT / "B4_lidar_selection.json").write_text(json.dumps(res, indent=1))
    print("chosen trial", chosen["trial"], chosen["params"], chosen["weight_power"], "trees", chosen["trees"], flush=True)
    print("val TPR@10%", {k: round(v, 3) for k, v in tpr.items()}, flush=True)
    print("val TPR@1%", {k: round(v, 3) for k, v in tpr1.items()}, flush=True)
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
