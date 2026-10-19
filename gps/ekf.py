"""WP1 S3: L2a extended Kalman filter (IMU + odometry + GPS) with a per-fix NIS chi-square test, as a v3 Layer.

Purpose: physics consistency of the whole sensor set. The filter predicts the vehicle state from the IMU
acceleration, corrects it with the vehicle's own sensors (odometry speed, compass heading) and with the GPS
(position, Doppler velocity). The Normalised Innovation Squared of each fix, NIS_k = nu' S^-1 nu, is chi-square
distributed with m degrees of freedom (m = number of active measurements) when the model is right; a spoofed GPS
makes it large. Layer score = -log P(chi2_m >= NIS) (monotone in NIS, comparable across m), then the usual
validation ECDF calibration of common.layer.Layer.

State x = [e, n, ve, vn, we, wn]: position, velocity (east / north, m, m/s) and the receiver error w (first order
Gauss-Markov: civil receiver multipath / atmosphere wander is correlated over seconds, so treating it as white would
make the NIS wrong).
Process (dt = fix interval, a = IMU acceleration, nav frame, trapezoid mean of the two fixes unless the source gives
a window mean):
  p_k = p_{k-1} + v_{k-1} dt + a dt^2/2,   v_k = v_{k-1} + a dt,   w_k = phi^dt w_{k-1} + eta,
  Q = q^2 [[dt^4/4, dt^3/2], [dt^3/2, dt^2]] per axis (white acceleration error q) and (1 - phi^2dt) sigma_w^2 for w.
Measurements (all independent, R diagonal):
  GPS position  z = p + w + eps_pos           (2)   R = r_pos^2
  GPS Doppler   z = v + eps_dop               (2)   R = sd^2           (if the source has it)
  odometry      z = |v| + eps_odo             (1)   R = so^2 + (k_scale z)^2   (wheel-scale error as noise; S4 will calibrate it)
  heading       z = atan2(ve, vn) + eps_head  (1)   R = sh^2, innovation wrapped; only when speed > 1 m/s
Update in Joseph form. Gated variant: when NIS exceeds chi2_m(gate_level) the GPS block (position + Doppler) is left
out of that update and of the following ones (dead-reckoning from the last trusted state, odometry and heading keep
correcting velocity) until `release_n` consecutive fixes have NIS below chi2_m(0.95).

Inputs: stream table of one run (gps/stream.py columns: t, x, y, vel_e, vel_n, odo_speed, heading, acc_e, acc_n).
Outputs: filter_run -> DataFrame (nis, dim, est_x, est_y, hold); EKFLayer.raw_scores -> -log survival of NIS.
References: Bar-Shalom, Li, Kirubarajan, Estimation with Applications to Tracking and Navigation (2001), sec. 5.4
(NIS consistency test); Groves, Principles of GNSS, Inertial and Multisensor Integrated Navigation (2013), ch. 14
(GNSS / INS integration, innovation based integrity monitoring).
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.stats import chi2

from common.layer import Layer


@dataclass(frozen=True)
class EKFConfig:
    r_pos: float = 0.3            # m, white part of the position measurement (receiver thermal noise)
    gm_phi: float = 0.9           # receiver error correlation per second
    gm_sigma: float = 1.0         # m, receiver error std per axis
    q_acc: float = 0.1            # m/s^2, white acceleration error (IMU noise + 1 Hz sampling of the acceleration)
    sd_dop: float = 0.05          # m/s, Doppler velocity noise
    sd_odo: float = 0.05          # m/s, odometry noise
    k_scale: float = 0.02         # wheel odometry scale error (2%)
    sd_head_deg: float = 2.0      # compass-like heading noise
    use_dop: bool = True
    use_odo: bool = True
    use_head: bool = True
    acc_mode: str = "mid"         # "mid" (trapezoid of instantaneous values), "window" (mean over the last second), "none"
    gate_level: float = 0.0       # 0 = ungated; else chi2 quantile above which the GPS block is held out
    release_n: int = 3
    v0_sd: float = 3.0            # m/s, initial velocity std when no Doppler

    def gated(self, level, release_n=3):
        return replace(self, gate_level=level, release_n=release_n)


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def filter_run(df, cfg: EKFConfig) -> pd.DataFrame:
    """Run the EKF over the rows of ONE run (time ordered). Returns per-fix nis (NaN at the first fix), dim, estimate, hold."""
    n = len(df)
    t = df["t"].to_numpy(float)
    z_pos = df[["x", "y"]].to_numpy(float)
    has = lambda c: c in df.columns and not df[c].isna().all()
    dop = df[["vel_e", "vel_n"]].to_numpy(float) if cfg.use_dop and has("vel_e") else None
    odo = df["odo_speed"].to_numpy(float) if cfg.use_odo and has("odo_speed") else None
    head = np.radians(df["heading"].to_numpy(float)) if cfg.use_head and has("heading") else None
    acc = df[["acc_e", "acc_n"]].to_numpy(float) if cfg.acc_mode != "none" and has("acc_e") else None
    nis, dim, est, hold_out = np.full(n, np.nan), np.zeros(n, int), np.zeros((n, 2)), np.zeros(n, bool)
    nu_pos, s_pos = np.full((n, 2), np.nan), np.full((n, 2), np.nan)     # position innovation and its std (S4: CUSUM input)
    s2, sg2 = cfg.gm_sigma ** 2, cfg.gm_sigma ** 2
    # ---- initial state (w = 0, so e0 = z0; errors of e and w are perfectly anti-correlated) ----
    x = np.zeros(6)
    x[:2] = z_pos[0]
    P = np.zeros((6, 6))
    for ax in range(2):
        P[ax, ax] = s2 + cfg.r_pos ** 2
        P[4 + ax, 4 + ax] = s2
        P[ax, 4 + ax] = P[4 + ax, ax] = -s2
    if dop is not None and not np.isnan(dop[0]).any():
        x[2:4] = dop[0]
        P[2, 2] = P[3, 3] = cfg.sd_dop ** 2
    else:
        if odo is not None and head is not None and not np.isnan(odo[0]) and not np.isnan(head[0]):
            x[2:4] = odo[0] * np.array([np.sin(head[0]), np.cos(head[0])])
        P[2, 2] = P[3, 3] = cfg.v0_sd ** 2
    est[0] = x[:2]
    hold, ok_run = False, 0
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        if not dt > 1e-6:
            dt = 1.0
        a = np.zeros(2)
        if acc is not None:
            a = acc[k] if cfg.acc_mode == "window" else (acc[k] + acc[k - 1]) / 2
            a = np.nan_to_num(a)
        F = np.eye(6)
        F[0, 2] = F[1, 3] = dt
        ph = cfg.gm_phi ** dt
        F[4, 4] = F[5, 5] = ph
        x = F @ x
        x[:2] += 0.5 * a * dt ** 2
        x[2:4] += a * dt
        Q = np.zeros((6, 6))
        q2 = cfg.q_acc ** 2
        for ax in range(2):
            Q[ax, ax] = q2 * dt ** 4 / 4
            Q[2 + ax, 2 + ax] = q2 * dt ** 2
            Q[ax, 2 + ax] = Q[2 + ax, ax] = q2 * dt ** 3 / 2
            Q[4 + ax, 4 + ax] = (1 - ph ** 2) * sg2
        P = F @ P @ F.T + Q
        # ---- measurement blocks: (is_gps, innovation, H, R diag) ----
        nu, H, R, gps = [], [], [], []

        def add(inn, Hm, Rd, is_gps):
            for i in range(len(inn)):
                nu.append(inn[i]); H.append(Hm[i]); R.append(Rd[i]); gps.append(is_gps)

        Hp = np.zeros((2, 6)); Hp[0, 0] = Hp[1, 1] = Hp[0, 4] = Hp[1, 5] = 1
        add(z_pos[k] - (x[:2] + x[4:6]), Hp, [cfg.r_pos ** 2] * 2, True)
        if dop is not None and not np.isnan(dop[k]).any():
            Hd = np.zeros((2, 6)); Hd[0, 2] = Hd[1, 3] = 1
            add(dop[k] - x[2:4], Hd, [cfg.sd_dop ** 2] * 2, True)
        spd = float(np.hypot(x[2], x[3]))
        if odo is not None and not np.isnan(odo[k]) and spd > 0.3:
            Hs = np.zeros((1, 6)); Hs[0, 2], Hs[0, 3] = x[2] / spd, x[3] / spd
            add([odo[k] - spd], Hs, [cfg.sd_odo ** 2 + (cfg.k_scale * odo[k]) ** 2], False)
        if (head is not None and not np.isnan(head[k]) and spd > 1.0 and
                (odo is None or (not np.isnan(odo[k]) and odo[k] > 1.0))):
            Hh = np.zeros((1, 6)); Hh[0, 2], Hh[0, 3] = x[3] / spd ** 2, -x[2] / spd ** 2
            add([_wrap(head[k] - np.arctan2(x[2], x[3]))], Hh, [np.radians(cfg.sd_head_deg) ** 2], False)
        nu, H, R, gps = np.array(nu), np.array(H), np.array(R), np.array(gps)
        S = H @ P @ H.T + np.diag(R)
        m = len(nu)
        nis[k] = float(nu @ np.linalg.solve(S, nu))
        dim[k] = m
        nu_pos[k], s_pos[k] = nu[:2], np.sqrt(np.diag(S)[:2])
        # ---- gate ----
        if cfg.gate_level > 0:
            if nis[k] > chi2.ppf(cfg.gate_level, m):
                hold, ok_run = True, 0
            elif hold:
                ok_run = ok_run + 1 if nis[k] < chi2.ppf(0.95, m) else 0
                if ok_run >= cfg.release_n:
                    hold, ok_run = False, 0
        hold_out[k] = hold
        use = ~gps if hold else np.ones(m, bool)
        if use.any():
            Hu, Ru, nuu = H[use], R[use], nu[use]
            Su = Hu @ P @ Hu.T + np.diag(Ru)
            K = P @ Hu.T @ np.linalg.inv(Su)
            x = x + K @ nuu
            IKH = np.eye(6) - K @ Hu
            P = IKH @ P @ IKH.T + K @ np.diag(Ru) @ K.T
        est[k] = x[:2]
    return pd.DataFrame({"nis": nis, "dim": dim, "est_x": est[:, 0], "est_y": est[:, 1], "hold": hold_out,
                         "nu_x": nu_pos[:, 0], "nu_y": nu_pos[:, 1], "s_x": s_pos[:, 0], "s_y": s_pos[:, 1]}, index=df.index)


def nis_score(nis, dim):
    """-log survival of NIS under chi2(dim): 0 where undefined (first fix)."""
    out = np.zeros(len(nis))
    ok = ~np.isnan(nis) & (dim > 0)
    out[ok] = -chi2.logsf(nis[ok], dim[ok])
    return out


def run_filter_all(df, cfg):
    """filter_run over every run of df (rows of a run in time order); aligned to df.index."""
    if "run" not in df.columns:
        return filter_run(df, cfg)
    return pd.concat([filter_run(g, cfg) for _, g in df.groupby("run", sort=False)]).loc[df.index]


class EKFLayer(Layer):
    """L2a: EKF NIS test. Stateless between calls (each call filters whole runs), so reset() is a no-op."""
    domain = "gps"
    kind = "physics"
    layer_id = "L2a"

    def __init__(self, cfg: EKFConfig, name="gps.ekf_nis"):
        super().__init__()
        self.cfg = cfg
        self.name = name

    def raw_scores(self, samples):
        r = run_filter_all(samples, self.cfg)
        return nis_score(r["nis"].to_numpy(), r["dim"].to_numpy())

    def reasons(self, samples, raw, alarm):
        return ["GPS fix is inconsistent with the vehicle's own motion (IMU, odometry, heading): innovation chi-square test failed"] * len(raw)
