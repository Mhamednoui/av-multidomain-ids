"""COPIED from ../codes_v2/common/train_xgb.py (WP3 S1; unchanged). XGBoost training with a random hyperparameter search scored on the validation split.

The test split is never seen here. Early stopping and model selection both use the
validation split; the selection criterion is macro F1, so rare classes count as much
as frequent ones.
"""
import time

import numpy as np
import xgboost as xgb
from sklearn.metrics import f1_score

SPACE = {
    "max_depth": [3, 4, 5, 6, 8, 10],
    "learning_rate": [0.03, 0.05, 0.1, 0.2],
    "subsample": [0.7, 0.8, 0.9, 1.0],
    "colsample_bytree": [0.5, 0.7, 0.9, 1.0],
    "min_child_weight": [1, 3, 5],
    "reg_lambda": [0.5, 1.0, 3.0],
}


def class_weights(y: np.ndarray, power: float = 0.5) -> np.ndarray:
    """Per-sample weights ~ (1 / class frequency) ** power, normalised to mean 1."""
    counts = np.bincount(y)
    w_class = (counts.max() / np.maximum(counts, 1)) ** power
    w = w_class[y]
    return w / w.mean()


def fit_one(params, Xtr, ytr, Xva, yva, n_classes, weight_power, device):
    obj = {"objective": "binary:logistic", "eval_metric": "logloss"} if n_classes == 2 else \
          {"objective": "multi:softprob", "eval_metric": "mlogloss", "num_class": n_classes}
    m = xgb.XGBClassifier(n_estimators=3000, tree_method="hist", device=device,
                          early_stopping_rounds=50, random_state=42, **obj, **params)
    m.fit(Xtr, ytr, sample_weight=class_weights(ytr, weight_power) if weight_power else None,
          eval_set=[(Xva, yva)], verbose=False)
    pred = m.predict(Xva)
    return m, f1_score(yva, pred, average="macro"), m.best_iteration + 1


def search(Xtr, ytr, Xva, yva, n_classes, n_iter=25, weight_power=0.5, device="cuda", seed=42, log=print):
    rng = np.random.default_rng(seed)
    best = None
    trials = []
    t0 = time.time()
    for k in range(n_iter):
        params = {key: vals[rng.integers(len(vals))] for key, vals in SPACE.items()}
        m, score, n_trees = fit_one(params, Xtr, ytr, Xva, yva, n_classes, weight_power, device)
        trials.append({"params": params, "val_f1_macro": score, "n_trees": n_trees})
        if best is None or score > best[1]:
            best = (m, score, params, n_trees)
        log(f"  trial {k + 1:2d}/{n_iter}  val macro-F1 {score:.4f}  trees {n_trees:4d}  "
            f"best {best[1]:.4f}  ({time.time() - t0:.0f}s)")
    model, score, params, n_trees = best
    return model, {"best_params": params, "best_n_trees": n_trees, "val_f1_macro": score,
                   "weight_power": weight_power, "trials": trials}
