"""WP4 L4: supervised XGBoost flow classifier (net.l4_xgb), the v2 network model retrained inside the v3 harness.

Purpose: learned attack-vs-benign score per flow on the 60 "clean" CICFlowMeter columns (network.l3.feature_set("clean"): no IPs, no Flow ID, no
timestamp, no ports, no TCP-stack fingerprints). Copied from ../codes_v2 (network/train.py, common/train_xgb.py): class-weighted XGBoost, random
search on the validation split, early stopping on validation; changed: binary objective (a Layer needs one score; v2 was 7-class), margin as raw
score (no probability saturation), time split instead of a random split, CPU histogram trees.
Inputs: DataFrame with the feature columns; training labels y (0 benign / 1 attack) and a weight group (coarse attack group) per flow.
Outputs: raw score = log-odds margin (higher = more attack-like); total-gain feature importance.
Layer contract: common/layer.py (calibration on benign validation, tie-safe 1% budget). needs_attack_data = True.
References: Chen and Guestrin 2016 (XGBoost); Sharafaldin et al. 2018 (CICIDS2017); codes_v2 network/train.py.
"""
import numpy as np
import xgboost as xgb

from common.config import SEED
from common.layer import Layer
from network.l3 import feature_set

# search space of codes_v2/common/train_xgb.py (copied)
SPACE = {
    "max_depth": [3, 4, 5, 6, 8, 10],
    "learning_rate": [0.03, 0.05, 0.1, 0.2],
    "subsample": [0.7, 0.8, 0.9, 1.0],
    "colsample_bytree": [0.5, 0.7, 0.9, 1.0],
    "min_child_weight": [1, 3, 5],
    "reg_lambda": [0.5, 1.0, 3.0],
}


def class_weights(groups, power=0.5):
    """Per-sample weights ~ (1 / group frequency) ** power, normalised to mean 1 (v2 class_weights, on string groups)."""
    g = np.asarray(groups).astype(str)
    u, inv, cnt = np.unique(g, return_inverse=True, return_counts=True)
    w = ((cnt.max() / cnt) ** power)[inv]
    return w / w.mean()


def sample_params(rng, space=None):
    return {k: v[rng.integers(len(v))] for k, v in (space or SPACE).items()}


def matrix(df, cols):
    x = df[cols].to_numpy(np.float32)
    return np.where(np.isinf(x), np.nan, x)


class XGBNet(Layer):
    domain, name, kind, layer_id = "network", "net.l4_xgb", "supervised", "L4"
    needs_attack_data = True
    physical = False

    def __init__(self, feature_set_name="clean", params=None, n_trees=None, n_jobs=4, seed=SEED, max_trees=1500):
        super().__init__()
        self.cols = feature_set(feature_set_name)
        self.params = dict(params or {})
        self.n_trees = n_trees
        self.n_jobs = n_jobs
        self.seed = seed
        self.max_trees = max_trees
        self.model = None
        self.best_n_trees = None

    def _make(self, n_estimators, early=None):
        return xgb.XGBClassifier(n_estimators=n_estimators, tree_method="hist", n_jobs=self.n_jobs, early_stopping_rounds=early, random_state=self.seed,
                                 objective="binary:logistic", eval_metric="logloss", **self.params)

    def fit(self, train, y=None, groups=None, val=None, y_val=None, weight_power=0.5):
        """train: DataFrame with the columns; y 0/1; groups for the sample weights. With val + y_val: early stopping (50 rounds, cap max_trees = 1500);
        else n_trees trees (set at construction)."""
        X = matrix(train, self.cols)
        w = class_weights(groups, weight_power) if groups is not None and weight_power else None
        if val is not None:
            self.model = self._make(self.max_trees, 50)
            self.model.fit(X, np.asarray(y, int), sample_weight=w, eval_set=[(matrix(val, self.cols), np.asarray(y_val, int))], verbose=False)
            self.best_n_trees = int(self.model.best_iteration + 1)
        else:
            assert self.n_trees, "n_trees required without a validation set"
            self.model = self._make(int(self.n_trees))
            self.model.fit(X, np.asarray(y, int), sample_weight=w, verbose=False)
            self.best_n_trees = int(self.n_trees)
        return self

    def raw_scores(self, samples):
        n = self.best_n_trees
        return self.model.predict(matrix(samples, self.cols), output_margin=True, iteration_range=(0, n)).astype(float)

    def importance(self):
        """{feature: share of total gain}, sorted."""
        g = self.model.get_booster().get_score(importance_type="total_gain")
        tot = sum(g.values()) or 1.0
        out = {}
        for k, v in g.items():
            out[self.cols[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k] = v / tot
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    def reasons(self, samples, raw, alarm):
        return [f"flow looks like a learned attack pattern (log-odds {r:.2f})" for r in raw]
