"""WP1 S5 L2d: LiDAR odometry (point-to-plane ICP) and the motion features it gives the GPS detector.

Purpose: an ego-motion estimate that does not use the GPS receiver (nor the CAN bus, nor the wheel odometry): the
displacement of the vehicle between consecutive velodyne scans. A GPS spoofer cannot change it, so it is a witness
against attacks that stay consistent with the receiver's own velocity (Doppler-consistent spoof, meaconing).
Inputs: KITTI velodyne scans (x forward, y left, z up; N x 4 float32 .bin), their timestamps.
Outputs: relative scan-to-scan transforms (per drive, cached), poses interpolated at 1 Hz fix times,
displacement features for the stream (lidar_disp_*), MotionEstimate objects (common/motion.py).

Method (numpy + scipy cKDTree only):
  - remove points closer than 2.5 m (own vehicle) or farther than 60 m, voxel-grid centroid downsample (default 0.5 m);
  - target normals from the PCA of the 8 nearest neighbours (smallest-eigenvalue eigenvector), skipped where the neighbourhood
    is not planar enough;
  - Gauss-Newton on the point-to-plane error, 6 DOF small-angle update, nearest neighbours with a distance gate that shrinks
    (2.0 -> 0.5 m) and trimming of the 20% worst correspondences (moving objects, vegetation); stops when the update is tiny;
  - initial guess = previous scan-to-scan motion (constant velocity); falls back to identity if the result is implausible
    (more than 3 m or 0.5 rad in 0.1 s) or if too few correspondences remain.
Quality outputs per pair: rms residual of inliers, inlier fraction, iterations (sigma inflation in lidar_motion_sigma()).
References: Chen & Medioni 1992 (point-to-plane ICP); Low 2004 (linearised point-to-plane); Besl & McKay 1992;
Geiger et al., KITTI odometry benchmark (translation error % / rotation deg/m over path-length segments).
"""
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

R_MIN, R_MAX = 2.5, 60.0
VOXEL = 0.5
KNN_NORMAL = 8
GATES = (2.0, 1.0, 0.7, 0.5, 0.5, 0.5, 0.5, 0.5)       # per-iteration correspondence distance gate (m)
TRIM = 0.8                                             # keep the best 80% of the correspondences
FIRST_STARTS = (0.0, 0.5, 1.0, 1.5, 2.0)                # forward starts (m) tried for the first scan pair, which has no previous motion
MAX_STEP = (3.0, 0.5)                                  # plausible motion in one 0.1 s scan interval: metres, radians


# ---------------------------------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------------------------------
def load_scan(path):
    return np.fromfile(str(path), dtype=np.float32).reshape(-1, 4)[:, :3].astype(np.float64)


def voxel_downsample(pts, voxel=VOXEL):
    """Centroid of the points in every occupied voxel (deterministic)."""
    key = np.floor(pts / voxel).astype(np.int64)
    key -= key.min(axis=0)
    dims = key.max(axis=0) + 1
    lin = (key[:, 0] * dims[1] + key[:, 1]) * dims[2] + key[:, 2]
    uniq, inv = np.unique(lin, return_inverse=True)
    cnt = np.bincount(inv).astype(float)
    return np.c_[[np.bincount(inv, weights=pts[:, j]) / cnt for j in range(3)]].T


def preprocess(pts, voxel=VOXEL):
    r = np.linalg.norm(pts[:, :2], axis=1)
    pts = pts[(r > R_MIN) & (r < R_MAX)]
    return voxel_downsample(pts, voxel) if len(pts) else pts


def estimate_normals(pts, tree, k=KNN_NORMAL, planar_ratio=0.2):
    """Unit normals (n,3) and a validity mask: the smallest eigenvalue must be < planar_ratio x the middle one."""
    _, idx = tree.query(pts, k=k)
    nb = pts[idx]                                        # (n, k, 3)
    nb = nb - nb.mean(axis=1, keepdims=True)
    cov = np.einsum("nki,nkj->nij", nb, nb) / k
    w, v = np.linalg.eigh(cov)                           # ascending eigenvalues
    n = v[:, :, 0]
    ok = w[:, 0] < planar_ratio * np.maximum(w[:, 1], 1e-12)
    return n, ok


def se3(x):
    """4x4 transform from the small-angle vector x = (rx, ry, rz, tx, ty, tz) (exact rotation by Rodrigues)."""
    r = x[:3]
    th = np.linalg.norm(r)
    K = np.array([[0, -r[2], r[1]], [r[2], 0, -r[0]], [-r[1], r[0], 0]])
    if th < 1e-12:
        R = np.eye(3) + K
    else:
        R = np.eye(3) + np.sin(th) / th * K + (1 - np.cos(th)) / th ** 2 * K @ K
    T = np.eye(4)
    T[:3, :3], T[:3, 3] = R, x[3:]
    return T


def planar(T):
    """(dx, dy, dyaw) of a 4x4 transform: translation in the plane and rotation about z."""
    return float(T[0, 3]), float(T[1, 3]), float(np.arctan2(T[1, 0], T[0, 0]))


def planar_to_T(dx, dy, dyaw):
    c, s = np.cos(dyaw), np.sin(dyaw)
    T = np.eye(4)
    T[:2, :2] = [[c, -s], [s, c]]
    T[0, 3], T[1, 3] = dx, dy
    return T


# ---------------------------------------------------------------------------------------------------
# ICP
# ---------------------------------------------------------------------------------------------------
class Target:
    """A downsampled scan prepared as ICP target: kd-tree + normals."""

    def __init__(self, pts):
        self.pts = pts
        self.tree = cKDTree(pts)
        self.n, self.ok = estimate_normals(pts, self.tree)


def icp_point_to_plane(src, tgt, init=None, gates=GATES, trim=TRIM):
    """Align `src` (m,3) to Target `tgt`: finds T with T @ src ~ tgt. Returns (T, info)."""
    T = np.eye(4) if init is None else init.copy()
    info = {"iters": 0, "rms": np.nan, "inlier_frac": 0.0, "ok": False}
    for it, gate in enumerate(gates):
        p = src @ T[:3, :3].T + T[:3, 3]
        d, j = tgt.tree.query(p, distance_upper_bound=gate)
        ok = np.isfinite(d) & tgt.ok[np.minimum(j, len(tgt.pts) - 1)]
        if ok.sum() < 200:
            return T, info
        pi, q, n = p[ok], tgt.pts[j[ok]], tgt.n[j[ok]]
        r = np.einsum("ij,ij->i", pi - q, n)
        keep = np.abs(r) <= np.quantile(np.abs(r), trim)
        pi, q, n, r = pi[keep], q[keep], n[keep], r[keep]
        A = np.c_[np.cross(pi, n), n]                    # d r / d (rotation, translation) at the current estimate
        H = A.T @ A + 1e-6 * np.eye(6)
        x = -np.linalg.solve(H, A.T @ r)
        T = se3(x) @ T
        info.update(iters=it + 1, rms=float(np.sqrt(np.mean(r ** 2))), inlier_frac=float(ok.mean()))
        if np.linalg.norm(x[3:]) < 1e-4 and np.linalg.norm(x[:3]) < 1e-5 and it >= 3:
            break
    info["ok"] = True
    return T, info


def scan_odometry(paths, voxel=VOXEL, log=None):
    """Relative planar motions between consecutive scans. paths: ordered scan files.
    Returns arrays (n-1,): dx, dy, dyaw of scan i+1 expressed in the frame of scan i (T_{i<-i+1}), and quality (rms, inlier_frac, iters, ok, fallback)."""
    n = len(paths)
    out = np.zeros((n - 1, 3))
    q = np.zeros((n - 1, 5))
    prev_T = np.eye(4)
    tgt = Target(preprocess(load_scan(paths[0]), voxel))
    for i in range(1, n):
        src = preprocess(load_scan(paths[i]), voxel)
        if i == 1:                                       # no previous motion yet: try forward starts, keep the best inlier fraction
            best = None
            for fwd in FIRST_STARTS:
                T0 = np.eye(4); T0[0, 3] = fwd
                T_, i_ = icp_point_to_plane(src, tgt, init=T0)
                if i_["ok"] and (best is None or i_["inlier_frac"] > best[1]["inlier_frac"]):
                    best = (T_, i_)
            T, info = best if best is not None else icp_point_to_plane(src, tgt, init=prev_T)
        else:
            T, info = icp_point_to_plane(src, tgt, init=prev_T)
        dx, dy, dyaw = planar(T)
        fallback = 0
        if (not info["ok"]) or np.hypot(dx, dy) > MAX_STEP[0] or abs(dyaw) > MAX_STEP[1]:
            T, info = icp_point_to_plane(src, tgt, init=np.eye(4))
            dx, dy, dyaw = planar(T)
            fallback = 1
            if (not info["ok"]) or np.hypot(dx, dy) > MAX_STEP[0] or abs(dyaw) > MAX_STEP[1]:
                T, dx, dy, dyaw = prev_T, *planar(prev_T)         # keep the constant-velocity guess
                fallback = 2
        out[i - 1] = (dx, dy, dyaw)
        q[i - 1] = (info["rms"], info["inlier_frac"], info["iters"], float(info["ok"]), fallback)
        prev_T = T
        tgt = Target(src)
        if log is not None and i % 50 == 0:
            log(f"  scan {i}/{n - 1}")
    return out, q


# ---------------------------------------------------------------------------------------------------
# poses and 1 Hz features
# ---------------------------------------------------------------------------------------------------
def chain_poses(rel):
    """Planar poses (n, 3) = (x, y, yaw) of every scan in the frame of the first scan from the relative motions rel (n-1, 3)."""
    n = len(rel) + 1
    P = np.zeros((n, 3))
    for i in range(1, n):
        dx, dy, dyaw = rel[i - 1]
        c, s = np.cos(P[i - 1, 2]), np.sin(P[i - 1, 2])
        P[i] = (P[i - 1, 0] + c * dx - s * dy, P[i - 1, 1] + s * dx + c * dy, P[i - 1, 2] + dyaw)
    return P


def pose_at(t, P, tp):
    """Pose at times t by linear interpolation of x, y and (unwrapped) yaw along the scan poses P at times tp."""
    return np.c_[np.interp(t, tp, P[:, 0]), np.interp(t, tp, P[:, 1]), np.interp(t, tp, P[:, 2])]


def body_displacement(Pa, Pb):
    """Displacement from pose a to pose b in the body frame of a: (forward, left) and the yaw change. Pa, Pb (n,3)."""
    d = Pb[:, :2] - Pa[:, :2]
    c, s = np.cos(Pa[:, 2]), np.sin(Pa[:, 2])
    fwd, left = c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]
    return fwd, left, Pb[:, 2] - Pa[:, 2]


def windows(t_fix, P, tp, w=1.0):
    """For fix times t_fix: body-frame displacement over [t - w, t] -> (fwd, left, dyaw); NaN where t - w < tp[0] or t > tp[-1]."""
    t0 = np.asarray(t_fix, float) - w
    ok = (t0 >= tp[0] - 1e-9) & (np.asarray(t_fix) <= tp[-1] + 1e-9)
    a, b = pose_at(t0, P, tp), pose_at(t_fix, P, tp)
    fwd, left, dyaw = body_displacement(a, b)
    return np.where(ok, fwd, np.nan), np.where(ok, left, np.nan), np.where(ok, dyaw, np.nan)


# ---------------------------------------------------------------------------------------------------
# MotionEstimate publication
# ---------------------------------------------------------------------------------------------------
SIGMA0, SIGMA_REL = 0.0821, 0.0046   # fitted on the 16 train+val drives by tools/WP1_S5_odometry.py (results/WP1/S5_odometry.json)


def lidar_motion_sigma(speed, quality_ok=True, sigma0=SIGMA0, rel=SIGMA_REL):
    """1-sigma uncertainty of the lidar speed over one second (m/s): sqrt(sigma0^2 + (rel * speed)^2), x3 when ICP quality is poor."""
    s = float(np.hypot(sigma0, rel * speed))
    return s if quality_ok else 3.0 * s


def motion_estimates(t_fix, P, tp, quality_ok=None, sigma0=SIGMA0, rel=SIGMA_REL, w=1.0):
    """List of MotionEstimate(source='lidar') for the fixes t_fix (one per second).
    displacement = (dx, dy) in metres over the last second in the BODY frame of the vehicle at the start of that second
    (dx forward, dy left; independent of any compass or GPS); speed = |displacement| / w; yaw_rate = dyaw / w (rad/s, positive left).
    Fixes without a full window are skipped."""
    from common.motion import MotionEstimate
    fwd, left, dyaw = windows(t_fix, P, tp, w)
    out = []
    for i, t in enumerate(t_fix):
        if not np.isfinite(fwd[i]):
            continue
        sp = float(np.hypot(fwd[i], left[i]) / w)
        qok = True if quality_ok is None else bool(quality_ok[i])
        out.append(MotionEstimate(t=float(t), source="lidar", speed=sp, yaw_rate=float(dyaw[i] / w),
                                  displacement=(float(fwd[i]), float(left[i])), sigma=lidar_motion_sigma(sp, qok, sigma0, rel)))
    return out


# ---------------------------------------------------------------------------------------------------
# stream features: LiDAR displacement vs GPS displacement
# ---------------------------------------------------------------------------------------------------
WINDOWS = (1, 3, 10)                 # seconds (fixes) over which the GPS and LiDAR displacements are compared
# frozen noise model of the standardised residual lid_z_W (set BEFORE any detection result):
GM_PHI, GM_SIGMA = 0.897, 0.981      # receiver error AR(1) fitted on KITTI train in S3 (results/WP1/S3_tuning.json)
LIDAR_REL = 0.019                    # LiDAR odometry relative error: translation error of the 16 dev drives (S5_odometry.json: 1.88%)
COMPASS_RAD = np.radians(2.0)        # compass noise per fix (stream.py)
ALPHA_FIXES = 20                     # trailing fixes used for the compass offset of the 1 s east-north LiDAR displacement (lid_dE, lid_dN)
MIN_COURSE_SPEED = 2.0               # m/s: below this the GPS displacement direction is noise


def cache_file(d, folder=None):
    from common.config import results_dir
    return Path(folder or results_dir("WP1") / "cache") / f"lidar_odom_{d}.npz"


def load_odometry(d, folder=None):
    """Cached odometry of a drive -> (scan times (s, GPS-stream clock), planar poses (n,3), quality (n-1,5))."""
    z = np.load(cache_file(d, folder))
    return z["t"], chain_poses(z["rel"]), z["quality"]


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def run_features(g, tp, P, qual, windows=WINDOWS):
    """Features of ONE stream run g (rows in time order, KITTI stream columns) from the odometry poses P at scan times tp.
    lid_z_W: lid_resid_W divided by its modelled standard deviation per axis (receiver AR(1) difference + LiDAR relative error x path
      + compass error x path): Rayleigh-distributed when clean, comparable across speeds.
    lid_resid_W: |GPS displacement over the last W fixes - LiDAR displacement over the same interval| in metres, with the LiDAR
      displacement rotated into the east-north frame by the compass offset alpha (circular mean over the window of
      compass yaw - LiDAR yaw; the compass is the vehicle's own sensor, not the receiver's); W is shortened at the start of a run.
    lid_course: lateral metres equivalent of |change of GPS course - change of LiDAR direction| between consecutive seconds
      (compass-free); 0 below MIN_COURSE_SPEED.
    lid_dE / lid_dN: the 1 s LiDAR displacement in east-north (compass offset over the last ALPHA_FIXES fixes), input of gps/lidar_dr.py.
    lid_fwd1 / lid_left1 / lid_dyaw1 / lid_speed1: the 1 s LiDAR motion in the body frame (the MotionEstimate); lid_ok: ICP quality
      of the scan pairs in the last second (no fallback)."""
    t = g["t"].to_numpy()
    n = len(t)
    Pt = pose_at(t, P, tp)
    xy = g[["x", "y"]].to_numpy()
    psi = np.radians(90.0 - g["heading"].to_numpy())
    e = psi - Pt[:, 2]
    C, S_ = np.r_[0.0, np.cumsum(np.cos(e))], np.r_[0.0, np.cumsum(np.sin(e))]
    k = np.arange(n)
    out = {}
    for w in windows:
        lag = np.maximum(k - w, 0)
        alpha = np.arctan2(S_[k + 1] - S_[lag], C[k + 1] - C[lag])
        D = Pt[:, :2] - Pt[lag, :2]
        ca, sa = np.cos(alpha), np.sin(alpha)
        De = np.c_[ca * D[:, 0] - sa * D[:, 1], sa * D[:, 0] + ca * D[:, 1]]
        r = np.hypot(*((xy - xy[lag]) - De).T)
        out[f"lid_resid_{w}"] = r
        nw = np.minimum(w, k) + 1                                          # compass samples in the window
        var = (2 * GM_SIGMA ** 2 * (1 - GM_PHI ** np.minimum(w, k)) + (LIDAR_REL ** 2 + (COMPASS_RAD ** 2) / nw) * (D ** 2).sum(axis=1) + 0.05 ** 2)
        out[f"lid_z_{w}"] = r / np.sqrt(var)
    lag1 = np.maximum(k - 1, 0)
    la = np.maximum(k - ALPHA_FIXES, 0)
    a5 = np.arctan2(S_[k + 1] - S_[la], C[k + 1] - C[la])
    D1 = Pt[:, :2] - Pt[lag1, :2]
    out["lid_dE"] = np.cos(a5) * D1[:, 0] - np.sin(a5) * D1[:, 1]
    out["lid_dN"] = np.sin(a5) * D1[:, 0] + np.cos(a5) * D1[:, 1]
    fwd, left, dyaw = body_displacement(Pt[lag1], Pt)
    sp = np.hypot(fwd, left)
    dg = xy - xy[lag1]
    ang_g = np.arctan2(dg[:, 1], dg[:, 0])
    gam = Pt[lag1, 2] + np.arctan2(left, fwd)                     # LiDAR direction of travel in the odometry frame
    lag2 = np.maximum(k - 1, 0)
    dpsi = wrap(ang_g - ang_g[lag2])
    dgam = wrap(gam - gam[lag2])
    ok = (sp > MIN_COURSE_SPEED) & (sp[lag2] > MIN_COURSE_SPEED) & (k >= 2)
    out["lid_course"] = np.where(ok, sp * np.abs(wrap(dpsi - dgam)), 0.0)
    out.update(lid_fwd1=fwd, lid_left1=left, lid_dyaw1=dyaw, lid_speed1=sp)
    bad = np.r_[0.0, np.cumsum(qual[:, 4] > 0)]                    # fallback count prefix over scan pairs
    i0 = np.clip(np.searchsorted(tp, t - 1.0), 0, len(tp) - 1)
    i1 = np.clip(np.searchsorted(tp, t), 0, len(tp) - 1)
    out["lid_ok"] = (bad[i1] - bad[i0] == 0).astype(float)
    return out


def stream_features(df, folder=None, windows=WINDOWS):
    """Add the LiDAR features to a KITTI stream (index aligned to df). Needs the cached odometry of every drive in df."""
    import pandas as pd
    parts = []
    for d, gd in df.groupby("drive", sort=False):
        tp, P, qual = load_odometry(d, folder)
        for _, g in gd.groupby("run", sort=False):
            parts.append(pd.DataFrame(run_features(g, tp, P, qual, windows), index=g.index))
    return pd.concat(parts).loc[df.index]


# ---------------------------------------------------------------------------------------------------
# detection layers (v3 Layer contract)
# ---------------------------------------------------------------------------------------------------
def _layer_class():
    from common.layer import Layer

    class LidarLayer(Layer):
        """L2d: GPS vs LiDAR-odometry displacement residual (metres). Reads the stream columns of stream_features()
        (so the ICP is not rerun per layer / per attack run: the LiDAR motion does not depend on the GPS attack)."""
        domain = "gps"
        kind = "physics"
        layer_id = "L2d"

        def __init__(self, column="lid_resid_1", name=None):
            super().__init__()
            self.column = column
            self.name = name or f"gps.{column.replace('lid_', 'lidar_')}"

        def raw_scores(self, samples):
            return samples[self.column].to_numpy(dtype=float).copy()

        def reasons(self, samples, raw, alarm):
            return [f"GPS displacement disagrees with the vehicle's LiDAR odometry by {r:.1f} m" for r in raw]

    return LidarLayer


LidarLayer = _layer_class()
