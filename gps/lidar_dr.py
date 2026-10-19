"""WP1 S5 L2d (sequential): dead-reckoning branch driven by LiDAR odometry + CUSUM on its innovations.

Purpose: the S4 dead-reckoning branch (gps/cusum.py dr_branch) moves a position estimate with the vehicle's own sensors and takes GPS
updates only while it trusts them; its innovations are accumulated by a CUSUM. Here the displacement comes from LiDAR odometry
(stream columns lid_dE, lid_dN of gps/lidar_odom.py: ~0.5% speed error and an independent sensor) instead of wheel odometry x compass
heading (2% scale error, 2 deg heading noise). No odometry-scale state is needed any more.
State x = [p (2), w (2)]: position and Gauss-Markov receiver error (phi, sigma from S3). Predict: p += d_lidar, w *= phi. Measurement: GPS
position = p + w + white noise. Process noise on p: sqrt(s0^2 + (rel |d|)^2) per axis (sigma model of results/WP1/S5_odometry.json) plus the
alignment noise (compass 2 deg / sqrt(ALPHA_FIXES + 1)) x |d| across the track.
Freeze (cannot be dragged by the attacker): the GPS update is skipped while the freeze-CUSUM >= freeze_h or the (external) ungated EKF NIS is
above chi2(0.999) (same rule and constants as S4, nothing re-tuned). Output columns are those of cusum.dr_branch, so cusum.score_from_dr applies.
Inputs: stream rows of ONE run with lid_dE, lid_dN. Outputs: DataFrame (innovations, covariance, nis2, frozen, estimate).
References: as gps/cusum.py (Page 1954; Basseville & Nikiforov 1993); Bar-Shalom et al. 2001 (Kalman filter, NIS).
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.stats import chi2

from gps import cusum, ekf
from gps import lidar_odom as LO


@dataclass(frozen=True)
class LDRConfig:
    r_pos: float = 0.3
    gm_phi: float = 0.897
    gm_sigma: float = 0.981
    sigma0: float = LO.SIGMA0           # m per second of displacement
    rel: float = LO.SIGMA_REL
    sd_head_deg: float = 2.0
    freeze_h: float = 8.0
    freeze_nis_level: float = 0.999
    kappa_freeze: float = 0.5
    warm: int = 3

    def with_(self, **kw):
        return replace(self, **kw)


def ldr_branch(g, cfg: LDRConfig, ext_susp=None):
    n = len(g)
    t = g["t"].to_numpy(float)
    z = g[["x", "y"]].to_numpy(float)
    d_all = g[["lid_dE", "lid_dN"]].to_numpy(float)
    s2, r2 = cfg.gm_sigma ** 2, cfg.r_pos ** 2
    x = np.zeros(4)
    x[:2] = z[0]
    P = np.zeros((4, 4))
    for ax in range(2):
        P[ax, ax] = s2 + r2
        P[2 + ax, 2 + ax] = s2
        P[ax, 2 + ax] = P[2 + ax, ax] = -s2
    Hm = np.zeros((2, 4)); Hm[0, 0] = Hm[1, 1] = Hm[0, 2] = Hm[1, 3] = 1.0
    nu_o, S_o, nis2 = np.full((n, 2), np.nan), np.full((n, 3), np.nan), np.full(n, np.nan)
    frozen, est, fzs = np.zeros(n, bool), np.zeros((n, 2)), np.zeros(n)
    est[0] = x[:2]
    fz = np.zeros(8)
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        dt = dt if dt > 1e-6 else 1.0
        d = np.nan_to_num(d_all[k])
        ph = cfg.gm_phi ** dt
        F = np.eye(4); F[2, 2] = F[3, 3] = ph
        x = F @ x
        x[:2] += d
        dist = float(np.hypot(*d))
        ua = d / dist if dist > 1e-9 else np.array([0.0, 1.0])
        ub = np.array([-ua[1], ua[0]])
        q_al = cfg.sigma0 ** 2 * dt + (cfg.rel * dist) ** 2
        sh = np.radians(cfg.sd_head_deg) / np.sqrt(min(k, LO.ALPHA_FIXES) + 1.0)     # compass offset averaged over the trailing fixes
        q_cr = q_al + (sh * dist) ** 2
        Q = np.zeros((4, 4))
        Q[:2, :2] = q_al * np.outer(ua, ua) + q_cr * np.outer(ub, ub)
        for ax in range(2):
            Q[2 + ax, 2 + ax] = (1 - ph ** 2) * s2
        P = F @ P @ F.T + Q
        nu = z[k] - (x[:2] + x[2:4])
        S = Hm @ P @ Hm.T + r2 * np.eye(2)
        nu_o[k], S_o[k] = nu, (S[0, 0], S[0, 1], S[1, 1])
        nis2[k] = float(nu @ np.linalg.solve(S, nu))
        fr = k >= cfg.warm and (fz.max() >= cfg.freeze_h or (ext_susp is not None and bool(ext_susp[k])))
        frozen[k] = fr
        if not fr:
            K = P @ Hm.T @ np.linalg.inv(S)
            x = x + K @ nu
            IKH = np.eye(4) - K @ Hm
            P = IKH @ P @ IKH.T + K @ (r2 * np.eye(2)) @ K.T
        pr = cusum.bank_projection(nu[None, :], np.array([[S[0, 0], S[0, 1], S[1, 1]]]))[0]
        fz = np.maximum(0.0, fz + pr - cfg.kappa_freeze)
        fzs[k] = fz.max()
        est[k] = x[:2]
    return pd.DataFrame({"nu_e": nu_o[:, 0], "nu_n": nu_o[:, 1], "S_ee": S_o[:, 0], "S_en": S_o[:, 1], "S_nn": S_o[:, 2], "nis2": nis2,
                         "frozen": frozen, "est_x": est[:, 0], "est_y": est[:, 1], "fz": fzs}, index=g.index)


def run_ldr(df, cfg: LDRConfig, ekf_cfg=None):
    """ldr_branch over every run of df (aligned to df.index); the ungated EKF (ekf_cfg) supplies the external suspicion."""
    outs = []
    for _, g in df.groupby("run", sort=False):
        ext = cusum.ext_nis_flag(ekf.filter_run(g, ekf_cfg), cfg.freeze_nis_level) if (ekf_cfg is not None and cfg.freeze_nis_level > 0) else None
        outs.append(ldr_branch(g, cfg, ext))
    return pd.concat(outs).loc[df.index]


def _make_layer_class():
    from common.layer import Layer

    class LidarCusumLayer(Layer):
        """L2d sequential: CUSUM (stat 'nis' or 'axis', allowance kappa) on the innovations of the LiDAR dead-reckoning branch.
        raw_scores needs the stream columns of lidar_odom.stream_features() and, for the EKF freeze, the S3 EKF config."""
        domain = "gps"
        kind = "physics"
        layer_id = "L2d"

        def __init__(self, stat, kappa, ekf_cfg, cfg=None, name="gps.cusum_lidar"):
            super().__init__()
            self.stat, self.kappa, self.ekf_cfg, self.cfg, self.name = stat, kappa, ekf_cfg, cfg or LDRConfig(), name

        def raw_scores(self, samples):
            runs = samples["run"].to_numpy() if "run" in samples.columns else np.zeros(len(samples), int)
            return cusum.score_from_dr(run_ldr(samples, self.cfg, self.ekf_cfg), self.stat, self.kappa, runs)

        def reasons(self, samples, raw, alarm):
            return ["Sustained disagreement between the GPS track and the vehicle's LiDAR odometry (CUSUM)"] * len(raw)

    return LidarCusumLayer


LidarCusumLayer = _make_layer_class()
