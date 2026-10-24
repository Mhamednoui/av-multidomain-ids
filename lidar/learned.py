"""WP3 S7 L3: normal-only model of object statistics (domain "lidar", layer "L3", kind "normal_model").

Purpose: a real object has a joint distribution of size, point count (versus the count expected for its range and angular
footprint), ring coverage, intensity and motion that clean scans reveal; an object that does not fit it is suspicious. Fitted on
CLEAN scans only (no attack, no label), so it cannot learn a generator.
Inputs: S3/S4 object tables (lidar.s4_build.compact: one row per cluster with >= 10 points, column `scan`), S2 calibration
(expected return probability), OXTS poses for the track class (lidar.assoc: matched to the previous scan after ego-motion).
Outputs: object feature table, three normal-only models (robust covariance, isolation forest, small autoencoder), per-scan statistics
(max object score, number of objects above the clean 99.9 % object quantile) and the Layer (ECDF union as in lidar.density.L2aUnion).
Limit stated plainly: a calibrated single-return phantom is matched to real objects in count and size by construction, so a model of
real objects can only flag the part that does not fit (merged giant clusters, wrong intensity), not a plausible object.
References: Liu et al., Isolation Forest (ICDM 2008); Rousseeuw & Van Driessen, MCD (Technometrics 1999); Hawkins et al., autoencoder
outlier detection (2002).
"""
import numpy as np
import pandas as pd
from sklearn.covariance import MinCovDet
from sklearn.ensemble import IsolationForest
from sklearn.neural_network import MLPRegressor

from common.config import SEED
from lidar import assoc, ego
from lidar.density import L2aUnion, residual

BASE_FEATS = ["range", "logn", "u", "length", "width", "height", "z_bottom", "az_span", "elev_span", "n_rings", "ring_cover",
              "int_mean", "int_std", "carlike"]
TRK_FEATS = ["trk_matched", "trk_disp", "trk_lr"]
STATS = ["l3_max", "l3_cnt"]
MODELS = ("cov", "iforest", "ae")


def object_features(objs, calib):
    """Single-scan features of the object rows (columns of lidar.s4_build.KEEP)."""
    rmin, rmax = objs["ring_min"].to_numpy(), objs["ring_max"].to_numpy()
    f = pd.DataFrame({
        "range": objs["range"].to_numpy(), "logn": np.log(objs["n_points"].to_numpy() + 1.0),
        "u": residual(objs, calib), "length": objs["length"].to_numpy(), "width": objs["width"].to_numpy(),
        "height": objs["height"].to_numpy(), "z_bottom": objs["z_bottom"].to_numpy(), "az_span": objs["az_span"].to_numpy(),
        "elev_span": objs["elev_span"].to_numpy(), "n_rings": objs["n_rings"].to_numpy(),
        "ring_cover": objs["n_rings"].to_numpy() / (rmax - rmin + 1.0), "int_mean": objs["int_mean"].to_numpy(),
        "int_std": objs["int_std"].to_numpy(), "carlike": objs["carlike"].to_numpy()})
    return f.astype(np.float32)


def track_features(cur, pose_cur, prev, pose_prev):
    """Track class of the objects of one scan against the previous scan (tables with cx, cy, range, n_points): matched flag (mutual
    nearest centroid within 1 m after ego-motion), displacement (m) and log point-count ratio of the matched pair; 0 where unmatched
    or outside the matching area. Returns an array (len(cur), 3)."""
    out = np.zeros((len(cur), 3), np.float32)
    if len(cur) == 0 or prev is None or len(prev) == 0:
        return out
    cand, jj, d, ratio = assoc.match(cur.reset_index(drop=True), pose_cur, prev.reset_index(drop=True), pose_prev)
    m = jj >= 0
    out[cand[m], 0] = 1.0
    out[cand[m], 1] = d[m]
    out[cand[m], 2] = np.log(ratio[m])
    return out


def drive_features(objs, scans, ref_objs, ref_scans, calib, poses, episodic=False):
    """Feature table (base + track class) of every object row of one drive. The previous scan of a scan is the clean scan idx - 1
    (`ref_*` tables; onset) or, for persistent episodes (episodic=True, step > 1), the same episode one step earlier (attacked).
    Scans without a previous scan get track features 0. Row order = objs."""
    F = object_features(objs, calib)
    T = np.zeros((len(objs), 3), np.float32)
    ix = objs.groupby("scan", sort=False).indices
    rix = ref_objs.groupby("scan", sort=False).indices
    ref_by = dict(zip(ref_scans["idx"].to_numpy(), ref_scans["scan"].to_numpy()))
    ep_by = {}
    if episodic:
        ep_by = {(a, e, st): sid for sid, a, e, st in zip(scans["scan"], scans["attack"], scans["ep"], scans["step"])}
    for sid, a, e, st, k in zip(scans["scan"], scans["attack"], scans.get("ep", scans["idx"] * 0), scans.get("step", scans["idx"] * 0),
                                scans["idx"]):
        if sid not in ix or k < 1:
            continue
        cur = objs.iloc[ix[sid]]
        if episodic and st > 1 and (a, e, st - 1) in ep_by and ep_by[(a, e, st - 1)] in ix:
            prev = objs.iloc[ix[ep_by[(a, e, st - 1)]]]
        else:
            ps = ref_by.get(k - 1)
            prev = ref_objs.iloc[rix[ps]] if ps in rix else None
        T[ix[sid]] = track_features(cur, poses[k], prev, poses[k - 1])
    out = pd.concat([F.reset_index(drop=True), pd.DataFrame(T, columns=TRK_FEATS)], axis=1)
    out.insert(0, "scan", pd.Categorical(objs["scan"].to_numpy()))
    out["oid"] = objs["oid"].to_numpy()
    out["ph_n"] = objs["ph_n"].to_numpy() if "ph_n" in objs.columns else np.float32(0)
    out["n_points"] = objs["n_points"].to_numpy()
    return out


class Prep:
    """Robust standardisation (median / MAD-scaled IQR, clipped at +-8) of a feature table."""

    def fit(self, F):
        a = np.asarray(F, np.float64)
        self.med = np.median(a, axis=0)
        q1, q3 = np.quantile(a, [0.25, 0.75], axis=0)
        self.sc = np.maximum((q3 - q1) / 1.349, 1e-3)
        return self

    def transform(self, F):
        return np.clip((np.asarray(F, np.float64) - self.med) / self.sc, -8.0, 8.0)


class NormalModel:
    """kind in MODELS. fit(F, rng) on a feature table of clean objects; score(F) -> higher = less normal."""

    def __init__(self, kind, n_fit=60000, n_ref=100000, seed=SEED):
        assert kind in MODELS
        self.kind, self.n_fit, self.n_ref, self.seed = kind, n_fit, n_ref, seed

    def fit(self, F):
        rng = np.random.default_rng(self.seed)
        F = np.asarray(F, np.float32)
        order = rng.permutation(len(F))
        fit_i, ref_i = order[:self.n_fit], order[self.n_fit:self.n_fit + self.n_ref]
        if len(ref_i) < 1000:                  # small training sets: reference on the fit objects
            ref_i = fit_i
        self.prep = Prep().fit(F[fit_i])
        Z = self.prep.transform(F[fit_i])
        if self.kind == "cov":
            self.m = MinCovDet(support_fraction=0.9, random_state=self.seed).fit(Z[:20000])
        elif self.kind == "iforest":
            self.m = IsolationForest(n_estimators=100, max_samples=4096, random_state=self.seed, n_jobs=4).fit(Z)
        else:
            self.m = MLPRegressor(hidden_layer_sizes=(12, 4, 12), activation="tanh", batch_size=512, max_iter=60, tol=1e-5,
                                  n_iter_no_change=6, random_state=self.seed).fit(Z, Z)
        ref = self.score(F[ref_i])
        self.q999 = float(np.quantile(ref, 0.999))
        return self

    def score(self, F):
        Z = self.prep.transform(F)
        if self.kind == "cov":
            return np.sqrt(self.m.mahalanobis(Z))
        if self.kind == "iforest":
            return -self.m.score_samples(Z)
        return ((self.m.predict(Z) - Z) ** 2).mean(axis=1)


def scan_stats(scan_ids, score, q999):
    """Per-scan maximum object score and number of objects above q999 (DataFrame indexed by scan id)."""
    s = pd.Series(np.asarray(score, float))
    g = np.asarray(scan_ids)
    out = pd.DataFrame({"l3_max": s.groupby(g).max(), "l3_cnt": (s > q999).groupby(g).sum().astype(float)})
    return out


def scan_frame(model, F, scan_ids, scans):
    """One row per scan of `scans` with the L3 statistics (0 for scans without object)."""
    st = scan_stats(scan_ids, model.score(F), model.q999)
    df = scans.set_index("scan").join(st).reset_index()
    df[STATS] = df[STATS].fillna(0.0)
    return df


def make_layer(oof_scan_frame, budget=0.01):
    lay = L2aUnion(STATS).calibrate(oof_scan_frame, budget)
    lay.layer_id, lay.name = "L3", "L3"
    return lay
