"""GPSDomain: the deployable GPS domain detector of v3 (WP1 S8, frozen for WP6 / WP7).

Purpose: one object that turns a unified GPS stream (gps/stream.py columns + the LiDAR odometry columns of gps/lidar_odom.py) into
(1) Evidence per layer and (2) one combined domain Evidence ("gps.combined", layer "combined"), with the physics reason of every alarm;
plus the ego-motion estimates the GPS side can publish (MotionEstimate, source "gps"; LiDAR motion: gps.lidar_odom.motion_estimates).
Default stack (16 layers): L1 five kinematic rules + Doppler-vs-position; B2 dead-reckoning residual; L2a EKF NIS; L2b CUSUM on the EKF
innovation and on the frozen dead-reckoning branch (with L2c odometry-scale learning); L2d six instantaneous GPS-vs-LiDAR-odometry checks.
Out of the default (optional rows of the ablation only): L2e map matching, cusum_lidar, L3 normal-only model, L4 supervised model.
Combiner: "noisy_or_log" = -sum log(1 - s_i) of the ECDF-calibrated layer scores (= the noisy-or ranking of common.combiner without its
float saturation at 1.0 with many correlated layers), turned into a 0..1 Evidence score by the ECDF of the same statistic on the
calibration drives' normal rows; alarm = score >= tie-safe 1% threshold. No attack labels are used anywhere in the fit.
Inputs: DataFrame with the gps/stream.py columns, plus the feature columns: dr_resid_10, still (b2.b2_features), the L1 columns
(l1.l1_features), lid_* (lidar_odom.stream_features). `prepare(df)` adds the first two groups and, when `lidar=True` and the columns are
missing, the third from the cached odometry (KITTI only: a vehicle needs its own LiDAR odometry source).
Outputs: lists of common.evidence.Evidence; save(folder) / load(folder) (domain.json + calibrators.npz).
Reference: ARCHITECTURE.md sections 2-4; reports/M1_GPS.md; notes/WP1_brief.md "Frozen GPS domain output".
"""
import json
from dataclasses import asdict, fields
from pathlib import Path

import numpy as np

from common.calibration import ECDFCalibrator
from common.evidence import Evidence
from common.metrics import budget_threshold
from gps import b2, l1, stack
from gps import lidar_odom as LO
from gps.cusum import CusumLayer, DRConfig
from gps.ekf import EKFConfig, EKFLayer

L2D_COLUMNS = ["lid_z_1", "lid_z_3", "lid_z_10", "lid_resid_1", "lid_resid_3", "lid_course"]
SCHEMA_VERSION = 1
BUDGET = 0.01


def prepare(df, lidar=True):
    """Add the feature columns the layers read (idempotent). df must be sorted by run and time, whole runs."""
    out = df
    if "dr_resid_10" not in out.columns:
        out = out.join(b2.b2_features(out))
    if "e_velpos" not in out.columns:
        out = out.join(l1.l1_features(out))
    if lidar and L2D_COLUMNS[0] not in out.columns:
        out = out.join(LO.stream_features(out))
    return out


def make_layers(config, lidar=True):
    """The default stack as Layer objects, from a config dict {"ekf": EKFConfig fields, "dr": DRConfig fields, "cusum_ekf": {stat, kappa},
    "cusum_dr": {stat, kappa}}."""
    e = EKFConfig(**config["ekf"])
    d = DRConfig(**config["dr"])
    rules = l1.make_rules(l1.COVERAGE["kitti"]["evaluated"])
    cus_e = CusumLayer("ekf", config["cusum_ekf"]["stat"], config["cusum_ekf"]["kappa"], e, name="gps.cusum_ekf")
    cus_d = CusumLayer("dr", config["cusum_dr"]["stat"], config["cusum_dr"]["kappa"], e, d, name="gps.cusum_dr")
    layers = rules + [b2.B2Layer(), EKFLayer(e, "gps.ekf_nis"), cus_e, cus_d]
    if lidar:
        layers += [LO.LidarLayer(c) for c in L2D_COLUMNS]
    return layers


def default_config(tune, cusum_ekf, cusum_dr):
    """Config of the S8 final fit. tune = results/WP1/S3_tuning.json (Gauss-Markov receiver noise, q_acc); cusum_* = dict(stat, kappa)."""
    g = tune["kitti_gm_estimate_train"]
    e = EKFConfig(gm_phi=g["phi"], gm_sigma=g["sigma"], q_acc=tune["kitti_q_acc"])
    d = DRConfig(gm_phi=g["phi"], gm_sigma=g["sigma"], learn_scale=True, freeze_h=8.0, freeze_nis_level=0.999)
    return {"ekf": asdict(e), "dr": asdict(d), "cusum_ekf": cusum_ekf, "cusum_dr": cusum_dr}


class GPSDomain:
    def __init__(self, config, lidar=True, budget=BUDGET):
        self.config, self.lidar, self.budget = config, lidar, budget
        self.layers = make_layers(config, lidar)
        self.names = sorted(l.name for l in self.layers)
        self.comb_cal = None
        self.comb_threshold = None

    # ---- fitting (normal data only) ----------------------------------------------------------------
    def fit(self, df):
        """df: prepared stream rows of whole runs (calibration drives). Uses the rows with label 0 only."""
        norm = df[df["label"] == 0] if "label" in df.columns else df
        for l in self.layers:
            l.calibrate(norm, budget=self.budget)
        S = self._statistic(self._calibrated(norm))
        self.comb_cal = ECDFCalibrator().fit(S)
        self.comb_threshold = budget_threshold(self.comb_cal.transform(S), self.budget)
        return self

    # ---- scoring ------------------------------------------------------------------------------------
    def _calibrated(self, df):
        return {l.name: l.calibrator.transform(np.asarray(l.raw_scores(df), float)) for l in self.layers}

    def _statistic(self, cal):
        return stack.noisy_or_log(stack.stack_matrix(cal, self.names))

    def score_arrays(self, df):
        """Fast path: (S, combined score 0..1, alarm) arrays aligned to df, no Evidence objects."""
        S = self._statistic(self._calibrated(df))
        sc = self.comb_cal.transform(S)
        return S, sc, sc >= self.comb_threshold

    def score(self, df, with_layers=False):
        """Evidence list (layer 'combined') aligned to df; with_layers=True also returns {layer name: Evidence list}."""
        per = {l.name: l.score(df) for l in self.layers}
        cal = {n: np.array([e.score for e in ev]) for n, ev in per.items()}
        S = self._statistic(cal)
        sc = self.comb_cal.transform(S)
        t = df["t"].to_numpy(float)
        ids = (df["run"].astype(str) + "/" + df["k"].astype(str)).to_numpy() if {"run", "k"} <= set(df.columns) else np.arange(len(df)).astype(str)
        out = []
        for i in range(len(df)):
            alarm = bool(sc[i] >= self.comb_threshold)
            reason = ""
            if alarm:
                fired = sorted([(per[n][i].score, n, per[n][i].reason) for n in self.names if per[n][i].alarm], reverse=True)
                who = "; ".join(f"{n} ({s:.3f}): {r}" for s, n, r in fired[:3]) if fired else "no single layer alarms, the evidence of several layers adds up"
                reason = f"GPS domain alarm (statistic {S[i]:.1f}); strongest: {who}"
            out.append(Evidence(domain="gps", layer="combined", name="gps.combined", t=float(t[i]), score=float(sc[i]), alarm=alarm, reason=reason,
                                details={"statistic": float(S[i]), "method": "noisy_or_log",
                                         "layer_scores": {n: per[n][i].score for n in self.names}},
                                sample_id=str(ids[i])))
        return (out, per) if with_layers else out

    # ---- persistence --------------------------------------------------------------------------------
    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        arrs = {}
        for l in self.layers:
            arrs[f"{l.name}:sorted"] = l.calibrator.sorted_
            arrs[f"{l.name}:scale"] = np.array([l.calibrator.scale_])
        arrs["combined:sorted"] = self.comb_cal.sorted_
        arrs["combined:scale"] = np.array([self.comb_cal.scale_])
        np.savez_compressed(folder / "calibrators.npz", **arrs)
        meta = {"schema": SCHEMA_VERSION, "budget": self.budget, "lidar": self.lidar, "config": self.config, "layer_names": self.names,
                "layer_thresholds": {l.name: l.threshold for l in self.layers}, "combined": {"method": "noisy_or_log", "threshold": self.comb_threshold}}
        (folder / "domain.json").write_text(json.dumps(meta, indent=1))

    @classmethod
    def load(cls, folder):
        folder = Path(folder)
        meta = json.loads((folder / "domain.json").read_text())
        assert meta["schema"] == SCHEMA_VERSION
        d = cls(meta["config"], lidar=meta["lidar"], budget=meta["budget"])
        z = np.load(folder / "calibrators.npz")
        for l in d.layers:
            c = ECDFCalibrator()
            c.sorted_, c.scale_ = z[f"{l.name}:sorted"], float(z[f"{l.name}:scale"][0])
            l.calibrator, l.threshold, l.budget = c, meta["layer_thresholds"][l.name], meta["budget"]
        c = ECDFCalibrator()
        c.sorted_, c.scale_ = z["combined:sorted"], float(z["combined:scale"][0])
        d.comb_cal, d.comb_threshold = c, meta["combined"]["threshold"]
        return d


# ---------------------------------------------------------------------------------------------------------------
# ego motion published by the GPS side
# ---------------------------------------------------------------------------------------------------------------
GPS_POSITION_STEP_SIGMA = 0.45        # m/s: std of one-second position differences of a clean receiver (S3 Gauss-Markov: sigma * sqrt(2 (1 - phi)))


def gps_motion_estimates(df, sigma=GPS_POSITION_STEP_SIGMA):
    """One MotionEstimate (source "gps") per fix after the first of ONE run: displacement = reported position change over the last second in the
    BODY frame (x forward, y left; rotated with the compass heading column, like the LiDAR MotionEstimate), speed = its norm / dt, yaw_rate =
    change of the compass heading per second (rad/s, positive left), sigma = 1-sigma of the speed from the clean-receiver noise model.
    A spoofer controls this estimate: it is a CLAIM to compare with independent sources (CAN wheel speed, LiDAR odometry), not a witness."""
    from common.motion import MotionEstimate
    x, y, t = df["x"].to_numpy(float), df["y"].to_numpy(float), df["t"].to_numpy(float)
    h = np.radians(df["heading"].to_numpy(float))
    out = []
    for k in range(1, len(df)):
        dt = t[k] - t[k - 1]
        if dt <= 0:
            continue
        de, dn = x[k] - x[k - 1], y[k] - y[k - 1]
        hm = h[k - 1]                                      # heading at the start of the interval; heading is a compass bearing (0 = north, clockwise)
        fwd = de * np.sin(hm) + dn * np.cos(hm)
        left = -de * np.cos(hm) + dn * np.sin(hm)
        dh = (h[k] - h[k - 1] + np.pi) % (2 * np.pi) - np.pi
        out.append(MotionEstimate(t=float(t[k]), source="gps", speed=float(np.hypot(fwd, left) / dt), yaw_rate=float(-dh / dt),
                                  displacement=(float(fwd), float(left)), sigma=float(sigma)))
    return out
