"""WP1 S7: learned GPS layers. L3 = normal-only model of the physics residuals; L4 = supervised XGBoost (v2 C2 retrained).

L3 (kind "normal_model"): input is the vector of residuals / innovations the physics layers already produce (B2 dead-reckoning
residual, Doppler-vs-position, EKF NIS, LiDAR residuals, CUSUM scores), NOT lat / lon / speed (those encode the drive). The model is
fit on normal rows only: a Mahalanobis distance with Ledoit-Wolf or MinCovDet covariance, or an isolation forest. No attack data.
L4 (kind "supervised"): XGBoost on the 6 AV-GPS features + the two dead-reckoning residuals (copy of ../codes_v2/gps/kitti_external.py
"C2_kitti_trained_dead_reckoning" and ../codes_v2/gps/features.py, ../codes_v2/common/train_xgb.py; nothing imported from v2). Needs
attack data (synthetic, same generator as the test attacks: optimistic about attack shape, see the S7 report).

Both layers read a precomputed score column (ScoreColumnLayer), because their out-of-fold scores on the development drives and the
final-model scores on the test drives are produced by the tools (tools/WP1_S7_lib.py); the model classes below are what a deployment
would call.
References: Mahalanobis (1936); Rousseeuw, "Least median of squares regression" (1984) for MCD; Liu, Ting, Zhou, "Isolation forest"
(ICDM 2008); Chen and Guestrin, "XGBoost" (KDD 2016); Ledoit and Wolf (2004) for the shrinkage covariance.
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.covariance import LedoitWolf, MinCovDet
from sklearn.ensemble import IsolationForest
from sklearn.metrics import f1_score

from common.config import SEED
from common.layer import Layer

M_PER_DEG = 111_320.0

# ---- L3: residual vectors (column names of the feature frame built by tools/WP1_S7_lib.py) ------------------------------------
RES_A = ["dr_resid_10", "e_velpos", "r3_nis", "lid_z_1", "lid_z_3", "lid_z_10", "lid_course"]
RES_B = RES_A + ["r3_cusum_ekf", "r3_cusum_dr"]
L3_CANDIDATES = {f"{s}|{k}": (s, k) for s in ("A", "B") for k in ("lw", "mcd", "if256", "if1024")}
FIT_CAP = {"lw": 20000, "mcd": 8000, "if256": 20000, "if1024": 20000}


def res_cols(setname):
    return RES_A if setname == "A" else RES_B


def log_transform(X):
    return np.log1p(np.clip(np.nan_to_num(np.asarray(X, float), nan=0.0, posinf=1e6), 0.0, None))


class ResidualNormalModel:
    """Normal-only anomaly score of a residual vector. score(): higher = more abnormal."""

    def __init__(self, kind, cols, seed=SEED):
        self.kind, self.cols, self.seed = kind, list(cols), seed

    def _x(self, df):
        return log_transform(df[self.cols].to_numpy())

    @staticmethod
    def _valid(df):
        """First fix of a run: every residual is undefined (0 by construction): not used for fitting, scored as the median normal score."""
        return (df["k"].to_numpy() >= 1) if "k" in df.columns else np.ones(len(df), bool)

    def fit(self, df):
        df = df[self._valid(df)]
        X = self._x(df)
        cap = FIT_CAP[self.kind]
        if len(X) > cap:                                   # deterministic subsample (speed of MCD)
            X = X[np.random.default_rng(self.seed).choice(len(X), cap, replace=False)]
        self.med = np.median(X, axis=0)
        mad = 1.4826 * np.median(np.abs(X - self.med), axis=0)
        sd = X.std(axis=0)
        self.scale = np.where(mad > 1e-6, mad, np.where(sd > 1e-6, sd, 1.0))
        Z = (X - self.med) / self.scale
        if self.kind == "lw":
            self.est = LedoitWolf().fit(Z)
        elif self.kind == "mcd":
            self.est = MinCovDet(support_fraction=0.9, random_state=self.seed).fit(Z)
        else:
            ms = 256 if self.kind == "if256" else 1024
            self.est = IsolationForest(n_estimators=200, max_samples=min(ms, len(Z)), random_state=self.seed, n_jobs=4).fit(Z)
        self.fill = float(np.median(self._raw(Z)))
        return self

    def _raw(self, Z):
        if self.kind in ("lw", "mcd"):
            return self.est.mahalanobis(Z)
        return -self.est.score_samples(Z)

    def score(self, df):
        Z = (self._x(df) - self.med) / self.scale
        s = self._raw(Z)
        return np.where(self._valid(df), s, self.fill)


# ---- L4: v2 C2 features and model ----------------------------------------------------------------------------------------------
C2_FEATURES = ["pos_step_m", "speed_gap", "heading_gap", "pos_step_mean5", "speed_gap_mean5", "still_gps_moving_imu"]
C2_DR = ["dr_resid_5", "dr_resid_10"]
C2_ALL = C2_FEATURES + C2_DR
C2_NOPOS = [c for c in C2_ALL if c not in ("pos_step_m", "pos_step_mean5")]
NON_PHYSICAL = ("pos_step_m", "pos_step_mean5")           # grow with platform speed: encode the drive / vehicle, not the spoofing


def _run_c2(g):
    lat, lon = g["lat"], g["lon"]
    dlat = lat.diff() * M_PER_DEG
    dlon = lon.diff() * M_PER_DEG * np.cos(np.radians(lat.fillna(0)))
    step = np.sqrt(dlat ** 2 + dlon ** 2)
    sp = g["odo_speed"].astype(float)
    f = pd.DataFrame(index=g.index)
    f["pos_step_m"] = step
    f["speed_gap"] = (step - sp).abs()
    hd = (g["course"].astype(float) - g["heading"].astype(float)).abs() % 360
    f["heading_gap"] = np.minimum(hd, 360 - hd)
    f["pos_step_mean5"] = step.rolling(5, min_periods=1).mean()
    f["speed_gap_mean5"] = f["speed_gap"].rolling(5, min_periods=1).mean()
    f["still_gps_moving_imu"] = ((step < 0.05) & (sp > 0.5)).astype(float)
    rep = g[["x", "y"]].to_numpy(float)
    n = len(g)
    spv, h = sp.to_numpy(), np.radians(g["heading"].to_numpy(float))
    v_mid = np.r_[0, (spv[1:] + spv[:-1]) / 2]
    u = np.c_[np.sin(h), np.cos(h)]
    u_mid = np.r_[[[0, 0]], (u[1:] + u[:-1]) / 2]
    dr = np.cumsum(v_mid[:, None] * u_mid, axis=0)
    for w in (5, 10):
        lag = np.maximum(np.arange(n) - w, 0)
        f[f"dr_resid_{w}"] = np.hypot(*((rep - rep[lag]) - (dr - dr[lag])).T)
    return f


def c2_features(df):
    """The 8 C2 features per fix (causal, per run of `df`), from stream columns lat, lon, x, y, odo_speed, heading, course."""
    return pd.concat([_run_c2(g) for _, g in df.groupby("run", sort=False)]).loc[df.index][C2_ALL]


SPACE = {
    "max_depth": [3, 4, 5, 6, 8, 10],
    "learning_rate": [0.03, 0.05, 0.1, 0.2],
    "subsample": [0.7, 0.8, 0.9, 1.0],
    "colsample_bytree": [0.5, 0.7, 0.9, 1.0],
    "min_child_weight": [1, 3, 5],
    "reg_lambda": [0.5, 1.0, 3.0],
}


def class_weights(y, power=1.0):
    counts = np.bincount(y, minlength=2)
    w = (counts.max() / np.maximum(counts, 1)) ** power
    w = w[y]
    return w / w.mean()


def xgb_search(Xtr, ytr, Xva, yva, n_iter=15, seed=SEED, weight_power=1.0, nthread=4):
    """v2 random search (common/train_xgb.py): 15 random configurations, early stopping 50 on validation logloss, selection by
    validation macro-F1 at 0.5. CPU histogram trees."""
    rng = np.random.default_rng(seed)
    best, trials = None, []
    for _ in range(n_iter):
        params = {k: v[rng.integers(len(v))] for k, v in SPACE.items()}
        m = xgb.XGBClassifier(n_estimators=3000, tree_method="hist", device="cpu", n_jobs=nthread, early_stopping_rounds=50, random_state=42,
                              objective="binary:logistic", eval_metric="logloss", **params)
        m.fit(Xtr, ytr, sample_weight=class_weights(ytr, weight_power) if weight_power else None, eval_set=[(Xva, yva)], verbose=False)
        f1 = f1_score(yva, m.predict(Xva), average="macro")
        trials.append({"params": {k: (v.item() if hasattr(v, "item") else v) for k, v in params.items()}, "val_f1_macro": float(f1),
                       "n_trees": int(m.best_iteration + 1)})
        if best is None or f1 > best[1]:
            best = (m, f1, trials[-1])
    return best[0], {"best": best[2], "val_f1_macro": float(best[1]), "trials": trials}


class C2Model:
    """v2 C2: XGBoost on C2 features. fit(Xtr, ytr, Xva, yva); score(X) = P(attack)."""

    def __init__(self, features=C2_ALL, seed=SEED, n_iter=15):
        self.features, self.seed, self.n_iter = list(features), seed, n_iter

    def fit(self, Ftr, ytr, Fva, yva):
        self.model, self.info = xgb_search(Ftr[self.features].to_numpy(np.float32), np.asarray(ytr), Fva[self.features].to_numpy(np.float32),
                                           np.asarray(yva), n_iter=self.n_iter, seed=self.seed)
        return self

    def score(self, F):
        return self.model.predict_proba(F[self.features].to_numpy(np.float32))[:, 1]

    def importance(self):
        return dict(zip(self.features, [float(v) for v in self.model.feature_importances_]))


class ScoreColumnLayer(Layer):
    """A learned layer as a v3 Layer: raw score = a precomputed column of the sample table (out-of-fold scores on development rows,
    final-model scores on test rows). The harness then calibrates it exactly like the physics layers."""
    domain = "gps"

    def __init__(self, column, name, layer_id, kind, needs_attack_data=False, why=""):
        super().__init__()
        self.column, self.name, self.layer_id, self.kind = column, name, layer_id, kind
        self.needs_attack_data = needs_attack_data
        self._why = why

    def raw_scores(self, samples):
        return np.nan_to_num(samples[self.column].to_numpy(dtype=float), nan=0.0)

    def reasons(self, samples, raw, alarm):
        return [self._why] * len(raw)


def l3_layer(column="s7_l3"):
    return ScoreColumnLayer(column, "gps.l3_residual_normal", "L3", "normal_model",
                            why="The vector of physics residuals is far from what normal driving produces (normal-only model)")


def l4_layer(column="s7_l4", name="gps.l4_c2"):
    return ScoreColumnLayer(column, name, "L4", "supervised", needs_attack_data=True,
                            why="Supervised model (trained on synthetic spoofing) flags the GPS-vs-vehicle consistency features")
