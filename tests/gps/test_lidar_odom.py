"""Tests for gps/lidar_odom.py and gps/lidar_dr.py: voxel grid, point-to-plane ICP on a synthetic scene, pose chaining, windows,
GPS-vs-LiDAR features, MotionEstimate publication, the Layer contract, the LiDAR dead-reckoning branch."""
import numpy as np
import pandas as pd

from common.motion import MotionEstimate
from gps import cusum, lidar_dr
from gps import lidar_odom as LO


def scene(rng, n=6000):
    """Ground + two walls + a tilted plane + a box face (a non-degenerate 3-D scene), ~ vehicle at the origin, z up."""
    g = np.c_[rng.uniform(-30, 30, n), rng.uniform(-30, 30, n), np.full(n, -1.7)]
    w1 = np.c_[np.full(n // 2, 15.0), rng.uniform(-20, 20, n // 2), rng.uniform(-1.7, 4, n // 2)]
    w2 = np.c_[rng.uniform(-20, 20, n // 2), np.full(n // 2, -10.0), rng.uniform(-1.7, 4, n // 2)]
    a, b = rng.uniform(-25, 0, n // 2), rng.uniform(5, 25, n // 2)
    tilt = np.c_[a, b, 0.3 * a - 1.0]
    box = np.c_[rng.uniform(6, 8, n // 4), np.full(n // 4, 5.0), rng.uniform(-1.7, 1, n // 4)]
    return np.vstack([g, w1, w2, tilt, box])


def test_voxel_downsample_centroids():
    pts = np.array([[0.1, 0.1, 0.1], [0.3, 0.3, 0.3], [5.1, 5.1, 5.1]])
    d = LO.voxel_downsample(pts, 1.0)
    assert len(d) == 2
    assert any(np.allclose(r, [0.2, 0.2, 0.2]) for r in d) and any(np.allclose(r, [5.1, 5.1, 5.1]) for r in d)


def test_icp_recovers_known_motion():
    rng = np.random.default_rng(0)
    world = scene(rng)
    T_true = LO.planar_to_T(1.2, 0.3, 0.05)              # pose of the new frame in the old frame: p_old = T p_new
    src_new = (world - T_true[:3, 3]) @ T_true[:3, :3]    # the same world points seen from the new frame
    tgt = LO.Target(LO.voxel_downsample(world, 0.5))
    src = LO.voxel_downsample(src_new + rng.normal(0, 0.01, src_new.shape), 0.5)
    T, info = LO.icp_point_to_plane(src, tgt, init=np.eye(4))
    dx, dy, dyaw = LO.planar(T)
    assert info["ok"] and abs(dx - 1.2) < 0.03 and abs(dy - 0.3) < 0.03 and abs(dyaw - 0.05) < 0.003, (dx, dy, dyaw)


def test_chain_and_windows():
    rel = np.tile([1.0, 0.0, 0.0], (30, 1))               # 1 m per scan straight ahead, 0.1 s apart -> 10 m/s
    P = LO.chain_poses(rel)
    tp = np.arange(31) * 0.1
    assert np.allclose(P[-1], [30.0, 0.0, 0.0])
    f, l, y = LO.windows(np.array([1.0, 2.0]), P, tp, 1.0)
    assert np.allclose(f, 10.0) and np.allclose(l, 0.0) and np.allclose(y, 0.0)
    f, l, y = LO.windows(np.array([0.5]), P, tp, 1.0)       # window starts before the first scan -> NaN
    assert np.isnan(f[0])
    # turning: constant yaw rate 0.1 rad per scan, body displacement stays (forward) and yaw change is per window
    P2 = LO.chain_poses(np.tile([1.0, 0.0, 0.01], (30, 1)))
    f, l, y = LO.windows(np.array([1.0]), P2, tp, 1.0)
    assert abs(y[0] - 0.10) < 1e-9 and f[0] > 9.5


def synthetic_run(n=40, v=10.0, offset_from=None, drift=0.0, heading_noise=0.0, seed=0):
    """Eastbound run at v m/s; LiDAR odometry exact (heading 90 deg compass); GPS = truth (+ drift m/s after offset_from)."""
    rng = np.random.default_rng(seed)
    tp = np.arange(0, n + 1, 0.1)
    P = np.c_[tp * v, np.zeros(len(tp)), np.zeros(len(tp))]           # odometry frame x = forward
    qual = np.zeros((len(tp) - 1, 5))
    t = np.arange(n, dtype=float)
    x = t * v
    if offset_from is not None:
        x = x + np.clip(t - offset_from, 0, None) * drift
    g = pd.DataFrame({"t": t, "x": x, "y": np.zeros(n), "heading": 90.0 + rng.normal(0, heading_noise, n), "run": "r"})
    return g, tp, P, qual


def test_features_clean_and_attacked():
    g, tp, P, q = synthetic_run()
    f = LO.run_features(g, tp, P, q)
    assert np.abs(f["lid_resid_1"]).max() < 1e-6 and np.abs(f["lid_resid_10"]).max() < 1e-6
    assert np.allclose(f["lid_speed1"][1:], 10.0) and np.allclose(f["lid_dE"][5:], 10.0) and np.allclose(f["lid_dN"][5:], 0.0, atol=1e-9)
    assert (f["lid_course"] == 0).all()
    g2, tp, P, q = synthetic_run(offset_from=20, drift=2.0)           # a 2 m/s Doppler-like velocity offset after k = 20
    f2 = LO.run_features(g2, tp, P, q)
    assert np.allclose(f2["lid_resid_1"][21:], 2.0, atol=1e-6) and f2["lid_resid_1"][:20].max() < 1e-6
    assert f2["lid_resid_10"][35] > 15.0 and f2["lid_z_1"][25] > 3.0 and f["lid_z_1"].max() < 1e-6
    # LiDAR-measured heading change vs GPS course change: a GPS that turns while the vehicle drives straight
    g3 = g.copy(); g3["y"] = np.r_[np.zeros(20), np.arange(20) * 8.0]
    f3 = LO.run_features(g3, tp, P, q)
    assert f3["lid_course"][21] > 3.0 and f3["lid_course"][:21].max() < 1e-6


def test_alignment_uses_compass_offset_not_gps():
    # odometry frame rotated by 30 deg relative to east: LiDAR yaw 0 in its own frame, compass says heading 60 deg (north-of-east 30)
    g, tp, P, q = synthetic_run()
    ang = np.radians(30.0)
    g["x"], g["y"] = g["x"] * np.cos(ang), g["x"] * np.sin(ang)
    g["heading"] = 90.0 - 30.0
    f = LO.run_features(g, tp, P, q)
    assert f["lid_resid_1"].max() < 1e-6 and f["lid_resid_10"].max() < 1e-6


def test_motion_estimates_format():
    g, tp, P, q = synthetic_run()
    me = LO.motion_estimates(g["t"].to_numpy(), P, tp)
    assert me and all(isinstance(m, MotionEstimate) and m.source == "lidar" for m in me)
    assert me[0].t == 1.0 and len(me) == len(g) - 1                       # t = 0 has no full second behind it
    m = me[5]
    assert abs(m.speed - 10.0) < 1e-9 and abs(m.displacement[0] - 10.0) < 1e-9 and abs(m.displacement[1]) < 1e-9 and abs(m.yaw_rate) < 1e-9
    assert 0.05 < m.sigma < 0.3
    assert LO.lidar_motion_sigma(10.0, quality_ok=False) == 3 * LO.lidar_motion_sigma(10.0, quality_ok=True)
    assert LO.lidar_motion_sigma(20.0) > LO.lidar_motion_sigma(2.0)


def test_layer_contract():
    g, tp, P, q = synthetic_run(n=60)
    f = pd.DataFrame(LO.run_features(g, tp, P, q), index=g.index)
    d = g.join(f)
    lay = LO.LidarLayer("lid_z_1").calibrate(d, budget=0.05)
    assert lay.name == "gps.lidar_z_1" and lay.domain == "gps" and lay.layer_id == "L2d"
    g2, tp, P, q = synthetic_run(n=60, offset_from=30, drift=3.0)
    d2 = g2.join(pd.DataFrame(LO.run_features(g2, tp, P, q), index=g2.index))
    ev = lay.score(d2)
    assert not any(e.alarm for e in ev[:30]) and all(e.alarm for e in ev[35:]) and ev[40].reason


def test_lidar_branch_follows_and_detects():
    rng = np.random.default_rng(1)
    n = 120
    w = np.zeros((n, 2))
    for k in range(1, n):
        w[k] = 0.897 * w[k - 1] + np.sqrt(1 - 0.897 ** 2) * 0.981 * rng.normal(size=2)
    t = np.arange(n, dtype=float)
    base = pd.DataFrame({"t": t, "lid_dE": 10.0 + rng.normal(0, 0.08, n), "lid_dN": rng.normal(0, 0.08, n), "run": "r"})
    clean = base.assign(x=t * 10.0 + w[:, 0] + rng.normal(0, 0.3, n), y=w[:, 1] + rng.normal(0, 0.3, n))
    out = lidar_dr.ldr_branch(clean, lidar_dr.LDRConfig(freeze_nis_level=0.0))
    assert abs(out["nis2"].mean() - 2.0) < 1.0
    sc = cusum.score_from_dr(out, "nis", 1.0, clean["run"].to_numpy())
    drift = clean.assign(x=clean["x"] + np.clip(t - 60, 0, None) * 0.5)    # 0.5 m/s pull-off, invisible to a per-fix test
    o2 = lidar_dr.ldr_branch(drift, lidar_dr.LDRConfig(freeze_nis_level=0.0))
    s2 = cusum.score_from_dr(o2, "nis", 1.0, drift["run"].to_numpy())
    assert s2[-1] > 5 * max(sc.max(), 1.0)
    # frozen branch does not follow the attacker: estimate error vs truth stays small while GPS drifts away
    err = np.hypot(o2["est_x"].to_numpy() - t * 10.0, o2["est_y"].to_numpy())
    assert o2["frozen"].iloc[-20:].all() and err[-1] < 0.5 * (n - 60) * 0.5
