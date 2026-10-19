"""WP1 S4: L2b CUSUM / SPRT on innovations, and L2c online odometry-scale calibration (v3 Layers).

Purpose: slow GPS drifts and spoofs that a self-consistent GPS solution hides from a per-fix chi-square test.
A per-fix NIS test (L2a) only sees large innovations; a sequential test accumulates small, same-sign innovations.
Two innovation sources:
  1. the S3 EKF (IMU + odometry + Doppler + heading + GPS). Fast, but the filter ABSORBS slow attacks: its receiver-error
     state follows the offset (S3: 43% of a drift and 99% of a Doppler-consistent spoof are absorbed after 30 s).
  2. a DEAD-RECKONING BRANCH (this file): position from odometry + compass heading only (no Doppler, no IMU), state
     x = [p (2), w (2), s] = position, Gauss-Markov receiver error, odometry scale. GPS position corrects it, but only
     while it is trusted: when the freeze statistic (its own CUSUM, or the EKF NIS = another layer) is suspicious the GPS
     update is skipped, so the branch keeps following the vehicle's own sensors and the attacker cannot drag it
     (this is also L2c: the scale s is only learned through GPS updates, so it is frozen with them).
Tests (all on standardised innovations, Gaussian N(0,1) when the model holds):
  - CUSUM: S_k = max(0, S_{k-1} + x_k - kappa), x_k the projection of the innovation on one of 8 directions (0, 45, 90, 135
    degrees and opposite; the drift direction is unknown), score = max over the bank. Page's CUSUM with kappa = delta/2 IS Wald's
    SPRT for a mean shift delta restarted at 0 (Page 1954; Lorden 1971), so the kappa grid covers the SPRT family.
  - NIS-CUSUM: x_k = (NIS_k - m)/sqrt(2m) with NIS_k ~ chi2(m).
The score is the running statistic (not reset after an alarm): it stays high while the attack lasts (row level detection).
Inputs: stream tables (gps/stream.py). Outputs: Layers with domain gps, layer id L2b (CusumLayer) and L2c (ScaleLayer is a diagnostic
view of the branch's scale state, see tools/WP1_S4_*.py).
References: Page, Biometrika 1954 (CUSUM); Basseville & Nikiforov, Detection of Abrupt Changes (1993) ch. 2 (CUSUM, SPRT);
Groves, Principles of GNSS, Inertial and Multisensor Integrated Navigation (2013) ch. 17 (integrity monitoring); Bar-Shalom et al. (2001).
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy.stats import chi2

from common.layer import Layer
from gps import ekf

ANGLES = np.radians(np.arange(0, 360, 45.0))
DIRS = np.c_[np.cos(ANGLES), np.sin(ANGLES)]          # (8, 2) unit vectors in (east, north)


# ---------------------------------------------------------------------------------------------------------
# sequential statistics
# ---------------------------------------------------------------------------------------------------------
def cusum_scalar(x, kappa):
    """One-sided CUSUM of a series x (NaN counts as 0): S_k = max(0, S_{k-1} + x_k - kappa)."""
    s, out = 0.0, np.zeros(len(x))
    for k, v in enumerate(np.nan_to_num(np.asarray(x, float))):
        s = max(0.0, s + v - kappa)
        out[k] = s
    return out


def bank_projection(nu, S):
    """Standardised projection of the 2-d innovations nu (n,2) with covariance S (n,3 = Sxx, Sxy, Syy) on the 8 directions -> (n, 8)."""
    var = (DIRS[:, 0][None, :] ** 2) * S[:, [0]] + 2 * DIRS[:, 0][None, :] * DIRS[:, 1][None, :] * S[:, [1]] + (DIRS[:, 1][None, :] ** 2) * S[:, [2]]
    return (nu @ DIRS.T) / np.sqrt(np.maximum(var, 1e-12))


def cusum_bank(proj, kappa):
    """Bank of 8 one-sided CUSUMs on proj (n, 8); returns the max over the bank, (n,)."""
    s, out = np.zeros(proj.shape[1]), np.zeros(len(proj))
    p = np.nan_to_num(proj)
    for k in range(len(p)):
        s = np.maximum(0.0, s + p[k] - kappa)
        out[k] = s.max()
    return out


def nis_excess(nis, dim):
    """Standardised chi-square excess (NIS - m)/sqrt(2m); 0 where undefined."""
    out = np.zeros(len(nis))
    ok = ~np.isnan(nis) & (dim > 0)
    out[ok] = (nis[ok] - dim[ok]) / np.sqrt(2.0 * dim[ok])
    return out


# ---------------------------------------------------------------------------------------------------------
# dead-reckoning branch with odometry scale state (L2c)
# ---------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class DRConfig:
    r_pos: float = 0.3            # m, white part of the GPS position noise
    gm_phi: float = 0.9           # receiver error correlation per second
    gm_sigma: float = 1.0         # m, receiver error std per axis
    sd_head_deg: float = 2.0      # compass heading noise
    sd_odo: float = 0.05          # m/s odometry noise
    scale_sd0: float = 0.02       # prior std of the odometry scale error (2%)
    scale_rw: float = 2e-4        # random walk of the scale per fix
    learn_scale: bool = True      # False: the 2% scale error is treated as extra position noise (S3 style), s stays 1
    freeze_h: float = np.inf      # freeze the GPS update while the freeze-CUSUM >= freeze_h (inf = never)
    freeze_nis_level: float = 0.0 # >0: also freeze at fixes where the (external) EKF NIS exceeds chi2_m(level)
    kappa_freeze: float = 0.5     # allowance of the freeze-CUSUM
    warm: int = 3                 # first fixes are trusted unconditionally (the filter has nothing else)
    release_after: int = 0        # unused placeholder (kept 0): release happens when the freeze-CUSUM decays

    def with_(self, **kw):
        return replace(self, **kw)


def dr_branch(df, cfg: DRConfig, ext_susp=None):
    """Run the dead-reckoning branch over ONE run (time ordered). ext_susp: optional bool array (n,), another layer's suspicion
    (True = do not trust the GPS at this fix). Returns DataFrame with nu_e, nu_n, S_ee, S_en, S_nn (innovation and covariance
    BEFORE the update), nis2, scale, frozen, est_x, est_y, fz (freeze-CUSUM)."""
    n = len(df)
    t = df["t"].to_numpy(float)
    z = df[["x", "y"]].to_numpy(float)
    odo = df["odo_speed"].to_numpy(float)
    h = np.radians(df["heading"].to_numpy(float))
    u = np.c_[np.sin(h), np.cos(h)]
    s2, r2 = cfg.gm_sigma ** 2, cfg.r_pos ** 2
    x = np.zeros(5)
    x[:2] = z[0]
    x[4] = 1.0
    P = np.zeros((5, 5))
    for ax in range(2):
        P[ax, ax] = s2 + r2
        P[2 + ax, 2 + ax] = s2
        P[ax, 2 + ax] = P[2 + ax, ax] = -s2
    P[4, 4] = cfg.scale_sd0 ** 2 if cfg.learn_scale else 0.0
    nu_o, S_o = np.full((n, 2), np.nan), np.full((n, 3), np.nan)
    nis2, scale, frozen, est, fzs = np.full(n, np.nan), np.ones(n), np.zeros(n, bool), np.zeros((n, 2)), np.zeros(n)
    est[0] = x[:2]
    fz = np.zeros(8)
    sh = np.radians(cfg.sd_head_deg) / np.sqrt(2.0)         # mean of two independent compass readings
    Hm = np.zeros((2, 5)); Hm[0, 0] = Hm[1, 1] = Hm[0, 2] = Hm[1, 3] = 1.0
    chi2_lim = chi2.ppf(cfg.freeze_nis_level, 2) if cfg.freeze_nis_level > 0 else np.inf
    for k in range(1, n):
        dt = t[k] - t[k - 1]
        if not dt > 1e-6:
            dt = 1.0
        um = (u[k] + u[k - 1]) / 2
        vm = np.nan_to_num((odo[k] + odo[k - 1]) / 2) if not (np.isnan(odo[k]) or np.isnan(odo[k - 1])) else 0.0
        d = vm * dt * um                                     # nominal displacement from the vehicle's own sensors
        ph = cfg.gm_phi ** dt
        F = np.eye(5)
        F[2, 2] = F[3, 3] = ph
        if cfg.learn_scale:
            F[0, 4], F[1, 4] = d[0], d[1]
        x = F @ x
        if not cfg.learn_scale:
            x[:2] += d                                       # with learning, F[:, 4] = d already adds s * d
        dist = float(np.hypot(*d))
        mag = max(vm * dt, 1e-9)
        ua = d / max(dist, 1e-9) if dist > 1e-9 else np.array([0.0, 1.0])
        ub = np.array([-ua[1], ua[0]])
        q_along = (cfg.sd_odo * dt) ** 2 + (0.0 if cfg.learn_scale else (cfg.scale_sd0 * mag) ** 2)
        q_cross = (sh * mag) ** 2
        Q = np.zeros((5, 5))
        Q[:2, :2] = q_along * np.outer(ua, ua) + q_cross * np.outer(ub, ub)
        for ax in range(2):
            Q[2 + ax, 2 + ax] = (1 - ph ** 2) * s2
        if cfg.learn_scale:
            Q[4, 4] = cfg.scale_rw ** 2
        P = F @ P @ F.T + Q
        nu = z[k] - (x[:2] + x[2:4])
        S = Hm @ P @ Hm.T + r2 * np.eye(2)
        nu_o[k], S_o[k] = nu, (S[0, 0], S[0, 1], S[1, 1])
        nis2[k] = float(nu @ np.linalg.solve(S, nu))
        # ---- freeze decision (uses information up to the previous fix + the external layer at this fix) ----
        fr = k >= cfg.warm and (fz.max() >= cfg.freeze_h or (ext_susp is not None and bool(ext_susp[k])))
        frozen[k] = fr
        if not fr:
            K = P @ Hm.T @ np.linalg.inv(S)
            x = x + K @ nu
            IKH = np.eye(5) - K @ Hm
            P = IKH @ P @ IKH.T + K @ (r2 * np.eye(2)) @ K.T
        # freeze CUSUM on the standardised projections of this fix's innovation
        pr = bank_projection(nu[None, :], np.array([[S[0, 0], S[0, 1], S[1, 1]]]))[0]
        fz = np.maximum(0.0, fz + pr - cfg.kappa_freeze)
        fzs[k] = fz.max()
        scale[k] = x[4]
        est[k] = x[:2]
    return pd.DataFrame({"nu_e": nu_o[:, 0], "nu_n": nu_o[:, 1], "S_ee": S_o[:, 0], "S_en": S_o[:, 1], "S_nn": S_o[:, 2], "nis2": nis2,
                         "scale": scale, "frozen": frozen, "est_x": est[:, 0], "est_y": est[:, 1], "fz": fzs}, index=df.index)


def ext_nis_flag(ekf_out, level):
    """Boolean array: the EKF NIS is above chi2_m(level) (another layer's suspicion); NaN rows -> False."""
    nis, dim = ekf_out["nis"].to_numpy(), ekf_out["dim"].to_numpy()
    ok = ~np.isnan(nis) & (dim > 0)
    out = np.zeros(len(nis), bool)
    out[ok] = nis[ok] > chi2.ppf(level, dim[ok])
    return out


def _runs(df):
    if "run" in df.columns:
        return [g for _, g in df.groupby("run", sort=False)]
    return [df]


def run_dr(df, cfg, ekf_cfg=None):
    """dr_branch over every run of df, aligned to df.index. ekf_cfg given and cfg.freeze_nis_level > 0: the ungated EKF
    supplies the external suspicion."""
    outs = []
    for g in _runs(df):
        ext = None
        if cfg.freeze_nis_level > 0 and ekf_cfg is not None:
            ext = ext_nis_flag(ekf.filter_run(g, ekf_cfg), cfg.freeze_nis_level)
        outs.append(dr_branch(g, cfg, ext))
    return pd.concat(outs).loc[df.index]


# ---------------------------------------------------------------------------------------------------------
# scores from branch outputs
# ---------------------------------------------------------------------------------------------------------
def score_from_dr(out, stat, kappa, runs):
    """out = run_dr output, runs = array of run ids aligned to out. stat: 'axis' (direction bank on the innovation) or 'nis'."""
    res = np.zeros(len(out))
    r = np.asarray(runs)
    first = np.r_[True, r[1:] != r[:-1]]
    idx = np.flatnonzero(first)
    ends = np.r_[idx[1:], len(out)]
    nu = out[["nu_e", "nu_n"]].to_numpy(); S = out[["S_ee", "S_en", "S_nn"]].to_numpy(); nis2 = out["nis2"].to_numpy()
    for a, b in zip(idx, ends):
        if stat == "axis":
            res[a:b] = cusum_bank(bank_projection(nu[a:b], S[a:b]), kappa)
        else:
            res[a:b] = cusum_scalar(nis_excess(nis2[a:b], np.where(np.isnan(nis2[a:b]), 0, 2)), kappa)
    return res


def score_from_ekf(out, stat, kappa, runs):
    """EKF filter outputs (ekf.run_filter_all, with nu_x, nu_y, s_x, s_y) -> CUSUM score. stat 'axis' or 'nis'."""
    res = np.zeros(len(out))
    r = np.asarray(runs)
    first = np.r_[True, r[1:] != r[:-1]]
    idx = np.flatnonzero(first)
    ends = np.r_[idx[1:], len(out)]
    zx = (out["nu_x"] / out["s_x"]).to_numpy(); zy = (out["nu_y"] / out["s_y"]).to_numpy()
    nis, dim = out["nis"].to_numpy(), out["dim"].to_numpy()
    for a, b in zip(idx, ends):
        if stat == "axis":
            res[a:b] = cusum_bank(np.c_[zx[a:b], zy[a:b]] @ DIRS.T, kappa)
        else:
            res[a:b] = cusum_scalar(nis_excess(nis[a:b], dim[a:b]), kappa)
    return res


class CusumLayer(Layer):
    """L2b: CUSUM on innovations. source 'ekf' (S3 ungated EKF) or 'dr' (dead-reckoning branch); stat 'axis' or 'nis'."""
    domain = "gps"
    kind = "physics"
    layer_id = "L2b"

    def __init__(self, source, stat, kappa, ekf_cfg, dr_cfg=None, name=None):
        super().__init__()
        self.source, self.stat, self.kappa = source, stat, kappa
        self.ekf_cfg, self.dr_cfg = ekf_cfg, dr_cfg
        self.name = name or f"gps.cusum_{source}_{stat}"

    def raw_scores(self, samples):
        runs = samples["run"].to_numpy() if "run" in samples.columns else np.zeros(len(samples), int)
        if self.source == "ekf":
            return score_from_ekf(ekf.run_filter_all(samples, self.ekf_cfg), self.stat, self.kappa, runs)
        return score_from_dr(run_dr(samples, self.dr_cfg, self.ekf_cfg), self.stat, self.kappa, runs)

    def reasons(self, samples, raw, alarm):
        what = "dead-reckoning branch (odometry + heading)" if self.source == "dr" else "EKF"
        return [f"Sustained small GPS-vs-{what} disagreement accumulated by the CUSUM test (slow drift or spoof)"] * len(raw)


def true_scale(g):
    """Reference odometry scale s* of a KITTI-stream run: true path length / odometry path length (what the branch should learn)."""
    d = np.hypot(np.diff(g["x_true"].to_numpy()), np.diff(g["y_true"].to_numpy()))
    o = g["odo_speed"].to_numpy()
    om = (o[1:] + o[:-1]) / 2 * np.diff(g["t"].to_numpy())
    return float(d.sum() / max(om.sum(), 1e-9))
