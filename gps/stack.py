"""GPS stack evaluation helpers (WP1 S8): score-matrix level LODO pipeline pieces, shared by the dev / test tools and the tests.

Purpose: the default GPS stack is evaluated with leave-one-drive-out (LODO) folds in which EVERYTHING that is fitted (layer ECDF
calibration, 1% thresholds, CUSUM configuration, combiner method / weights / threshold) comes from the other drives only. Doing that on
Evidence objects would create ~600k objects per fold, so the pieces work on matrices of raw scores and reuse the arithmetic of
common.combiner (same functions, same group halves, same tie-safe threshold); tests/gps/test_stack.py checks that MatrixCombiner equals
common.combiner.DomainCombiner on the same data.
Inputs: raw score columns (n,), calibrated matrices X (n, k) in [0, 1], labels y, groups (drive ids). Outputs: thresholds, combined
scores, fast run-level detections (RunIndex) for configuration selection.
Reference: ARCHITECTURE.md section 4; RULES.md section 5; notes/WP1_gps.md "S8".
"""
import numpy as np

from common.calibration import ECDFCalibrator
from common.combiner import METHODS, DomainCombiner, _combine, _fit_logistic
from common.config import BUDGET_DOMAIN, SEED
from common.metrics import budget_threshold
from common.splits import group_halves, mask

ATTACKS = ("drift", "accel_drift", "jump", "freeze", "doppler_spoof", "meaconing")
V2_ATTACKS = ATTACKS[:4]
DEFAULT_LAYERS = ["gps.max_speed", "gps.long_accel", "gps.lat_accel", "gps.jerk", "gps.yaw_rate", "gps.vel_pos_consistency",
                  "gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr",
                  "gps.lidar_z_1", "gps.lidar_z_3", "gps.lidar_z_10", "gps.lidar_resid_1", "gps.lidar_resid_3", "gps.lidar_course"]
OPTIONAL_LAYERS = ["opt.map_dist", "opt.cusum_lidar", "opt.l3", "opt.l4_c2"]


# ---------------------------------------------------------------------------------------------------------------------------
# calibration on matrices
# ---------------------------------------------------------------------------------------------------------------------------
def raw_threshold(raw, normal_cal, budget=BUDGET_DOMAIN):
    """Tie-safe raw threshold (alarm = raw >= t) from the normal rows `normal_cal` (bool mask)."""
    return budget_threshold(np.asarray(raw, float)[normal_cal], budget)


def calibrate_columns(raw_cols, normal_cal):
    """raw_cols: dict name -> (n,) raw scores; ECDF fitted on the rows `normal_cal`. Returns dict name -> calibrated (n,) and the calibrators."""
    cal, cals = {}, {}
    for n, r in raw_cols.items():
        r = np.asarray(r, float)
        cals[n] = ECDFCalibrator().fit(r[normal_cal])
        cal[n] = cals[n].transform(r)
    return cal, cals


# ---------------------------------------------------------------------------------------------------------------------------
# combiner on matrices (same arithmetic as common.combiner.DomainCombiner)
# ---------------------------------------------------------------------------------------------------------------------------
def noisy_or_log(X):
    """-log prod(1 - s): same ranking as the noisy-or 1 - prod(1 - s) of common.combiner, but it does not saturate at exactly 1.0 in float64
    when several correlated layers are extreme (with 16 layers 1 - prod(1 - s) ties at 1.0 on > 1% of the normal rows and no threshold
    exists: S8 finding). Not bounded by 1, so it is a score for thresholding / ranking, not an Evidence score."""
    return -np.log1p(-np.clip(X, 0.0, 1.0 - 1e-16)).sum(axis=1)


METHODS_EXT = METHODS + ("noisy_or_log",)


class MatrixCombiner(DomainCombiner):
    """DomainCombiner whose fit / score take calibrated matrices instead of Evidence lists. `fit_matrix` is a line-by-line copy of
    DomainCombiner.fit; train_mask (optional) restricts the rows used for fitting the logistic weights (control: unseen attack types)."""

    def fit_matrix(self, names, X, y, groups, fit_mask=None):
        self.layer_names = list(names)
        X = np.asarray(X, float)
        y = np.asarray(y).astype(int)
        groups = np.asarray(groups)
        if fit_mask is not None:
            X, y, groups = X[fit_mask], y[fit_mask], groups[fit_mask]
        if self.method == "auto":
            self.selection = self._select(X, y, groups)
            self.method = max(self.selection, key=lambda m: (self.selection[m], -METHODS.index(m)))
        if self.method == "noisy_or_log":
            self.threshold = budget_threshold(noisy_or_log(X)[y == 0], self.budget)
        elif self.method == "logistic":
            ga, gb = group_halves(groups, self.seed)
            ma, mb = mask(groups, ga), mask(groups, gb)
            self.model = _fit_logistic(X[ma], y[ma])
            self.threshold = budget_threshold(_combine("logistic", X[mb], self.model)[y[mb] == 0], self.budget)
        else:
            s = _combine(self.method, X)
            self.threshold = budget_threshold(s[y == 0], self.budget)
        return self

    def score_matrix(self, X):
        if self.method == "noisy_or_log":
            return noisy_or_log(np.asarray(X, float))
        return _combine(self.method, np.asarray(X, float), self.model)


def stack_matrix(cal, names):
    return np.column_stack([cal[n] for n in names])


def combiner_to_dict(c):
    d = {"method": c.method, "budget": c.budget, "threshold": float(c.threshold), "layer_names": list(c.layer_names),
         "selection": {k: float(v) for k, v in c.selection.items()}}
    if c.model is not None:
        d["logistic"] = {"coef": c.model.coef_.ravel().tolist(), "intercept": float(c.model.intercept_[0])}
    return d


def combiner_from_dict(d):
    from sklearn.linear_model import LogisticRegression
    c = MatrixCombiner(method=d["method"], budget=d["budget"])
    c.layer_names, c.threshold, c.selection = list(d["layer_names"]), float(d["threshold"]), dict(d.get("selection", {}))
    if "logistic" in d:
        m = LogisticRegression()
        m.coef_ = np.array([d["logistic"]["coef"]])
        m.intercept_ = np.array([d["logistic"]["intercept"]])
        m.classes_ = np.array([0, 1])
        c.model = m
    return c


# ---------------------------------------------------------------------------------------------------------------------------
# fast run-level detection (rows of a run are contiguous, runs in order)
# ---------------------------------------------------------------------------------------------------------------------------
class RunIndex:
    """Run structure of a stream table (columns run, label, attack, drive, k, onset, severity), for vectorised run-level detection."""

    def __init__(self, df):
        run = df["run"].to_numpy()
        self.start = np.flatnonzero(np.r_[True, run[1:] != run[:-1]])
        self.n = len(df)
        self.y = df["label"].to_numpy().astype(bool)
        att = df["attack"].to_numpy()
        self.run_attack = att[self.start]
        self.run_drive = df["drive"].to_numpy()[self.start]
        sev = df["severity"].to_numpy(float)[self.start]
        self.slow = (self.run_attack == "drift") & (sev < 0.5)
        k, on = df["k"].to_numpy(), df["onset"].to_numpy()
        self.win = (att == "drift") & (df["severity"].to_numpy(float) < 0.5) & (k >= on) & (k < on + 30)
        self.row_attack = att
        self.row_drive = df["drive"].to_numpy()
        self.normal = ~self.y
        self.clean_row = att == "none"

    def detected(self, flag):
        """Per run: any flagged row among its attack rows (label 1)."""
        return np.add.reduceat((np.asarray(flag, bool) & self.y).astype(np.int32), self.start) > 0

    def slow_detected(self, flag):
        return np.add.reduceat((np.asarray(flag, bool) & self.win).astype(np.int32), self.start) > 0

    def j(self, flag, drives):
        """S4 criterion J on the runs of `drives`: mean of 6 run-level detections and slow-drift-within-30-s rate."""
        det, slow = self.detected(flag), self.slow_detected(flag)
        keep = np.isin(self.run_drive, list(drives))
        v = [det[keep & (self.run_attack == a)].mean() for a in ATTACKS]
        s = slow[keep & self.slow]
        v.append(s.mean() if len(s) else 0.0)
        return float(np.mean(v))

    def run_level(self, flag, drives=None):
        det = self.detected(flag)
        keep = np.ones(len(det), bool) if drives is None else np.isin(self.run_drive, list(drives))
        return {a: float(det[keep & (self.run_attack == a)].mean()) for a in ATTACKS}

    def clean_fa(self, flag, drives=None):
        m = self.clean_row if drives is None else self.clean_row & np.isin(self.row_drive, list(drives))
        return float(np.asarray(flag, bool)[m].mean())
