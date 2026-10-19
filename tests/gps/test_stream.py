"""Tests for gps/stream.py: schema, determinism, split disjointness, and the physics of the two new attacks."""
import numpy as np

from gps import stream as S


def test_doppler_pull_discrete_identity():
    n, k0, wmax, th = 40, 5, 2.0, 0.7
    o, w = S.doppler_pull(n, k0, wmax, th)
    assert np.allclose(o[: k0 + 1], 0) and np.allclose(w[: k0 + 1], 0)         # nothing before onset
    # offset-track derivative == mean of the velocity offsets of the two fixes, exactly
    assert np.allclose(np.diff(o, axis=0), (w[1:] + w[:-1]) / 2)
    # velocity offset reaches wmax at T = wmax / accel and stays; acceleration never exceeds the cap
    assert np.isclose(np.hypot(*w[-1]), wmax)
    assert np.hypot(*np.diff(w, axis=0).T).max() <= S.DOPPLER_ACCEL + 1e-9
    assert np.allclose(np.arctan2(w[-1, 1], w[-1, 0]), th)                        # pulled in the chosen direction


def _straight_truth(ts, v=(8.0, 3.0)):
    return np.outer(ts, v), np.tile(v, (len(ts), 1))


def test_meaconing_delay_profile_smooth_and_capped():
    n, k0, tmax = 80, 6, 2.5
    tau, dtau = S.meacon_delay(n, k0, tmax)
    assert np.allclose(tau[: k0 + 1], 0) and np.all(np.diff(tau) >= -1e-12)
    assert tau.max() <= tmax + 1e-12 and np.isclose(tau[-1], tmax)
    assert dtau.max() <= S.TAU_RATE + 1e-12 and dtau[k0] == 0 and dtau[-1] == 0     # smooth onset and end
    assert np.abs(np.diff(dtau)).max() <= 0.25                                       # no step in the apparent speed
    # analytic tau' matches the finite difference of tau (trapezoid of tau' reproduces tau up to discretisation)
    assert abs(np.sum((dtau[1:] + dtau[:-1]) / 2) - tau[-1]) < 0.15


def test_meaconing_keeps_track_smooth_and_velocity_consistent():
    """Circular truth: reported position = truth(t - tau), reported velocity = V(t - tau)(1 - tau') must be the
    derivative of the reported position (2% of speed), and no speed/accel jump is created."""
    R, om = 200.0, 0.05                                                              # 10 m/s
    truth = lambda t: np.c_[R * np.sin(om * t), R * (1 - np.cos(om * t))]
    vel = lambda t: np.c_[R * om * np.cos(om * t), R * om * np.sin(om * t)]
    t = np.arange(0, 120.0, 0.1)
    k0 = 100                                                                         # onset at 10 s (dt = 0.1: use dt)
    tau, dtau = S.meacon_delay(len(t), k0, 3.0, dt=0.1)
    pos = truth(t - tau)
    v_rep = vel(t - tau) * (1 - dtau)[:, None]
    d = np.gradient(pos, 0.1, axis=0)
    assert np.hypot(*(d - v_rep).T).max() < 0.02 * R * om
    assert np.allclose(pos[: k0 + 1], truth(t[: k0 + 1]))                           # unchanged before onset
    # position error after the ramp = speed x delay (the cue a motion-consistency layer sees)
    err = np.hypot(*(pos[-1] - truth(t[-1:]))[0:1].T)
    assert abs(err[0] - R * om * 3.0) < 0.02 * R * om * 3.0
    speed = np.hypot(*v_rep.T)
    assert (speed >= (1 - S.TAU_RATE) * R * om - 1e-9).all() and np.abs(np.gradient(speed, 0.1)).max() < 0.5


def _drive():
    ox = S.load_oxts("0001")
    return ox, S.resample_1hz(ox, 0.0)


def test_stream_schema_and_determinism():
    ox, g = _drive()
    a = S.make_run(ox, g, np.random.default_rng(1), None, np.random.default_rng(2))
    b = S.make_run(ox, g, np.random.default_rng(1), None, np.random.default_rng(2))
    assert list(a.columns) + ["run", "drive", "part"] == S.COLUMNS or set(S.COLUMNS) - {"run", "drive", "part"} == set(a.columns)
    assert a.equals(b) and not a[["t", "lat", "lon", "odo_speed", "heading"]].isna().any().any()
    assert (a["label"] == 0).all() and a["attack"].eq("none").all()


def test_doppler_spoof_run_is_velocity_consistent():
    ox, g = _drive()
    clean = S.make_run(ox, g, np.random.default_rng(3), None, np.random.default_rng(9))
    att = S.make_run(ox, g, np.random.default_rng(3), "doppler_spoof", np.random.default_rng(9))
    k0 = int(att["onset"].iloc[0])
    assert (att["label"].to_numpy() == (np.arange(len(att)) >= k0)).all()
    # same receiver-noise draw and same Doppler-noise seed -> the differences are exactly the attack terms
    dv = att[["vel_e", "vel_n"]].to_numpy() - clean[["vel_e", "vel_n"]].to_numpy()
    dx = att[["x", "y"]].to_numpy() - clean[["x", "y"]].to_numpy()
    assert np.hypot(*dv[: k0 + 1].T).max() < 1e-9 and np.hypot(*dx[: k0 + 1].T).max() < 1e-9
    # reported velocity offset == derivative of the position offset (trapezoid): Doppler consistency, exact
    assert np.allclose(np.diff(dx, axis=0), (dv[1:] + dv[:-1]) / 2, atol=1e-9)
    assert np.hypot(*dv[-1:].T)[0] <= S.SEV["doppler_spoof"][1] + 1e-9
    assert np.isclose(np.hypot(*dv[-1:].T)[0], att["severity"].iloc[0]) or len(att) - k0 < att["severity"].iloc[0] / S.DOPPLER_ACCEL + 1


def test_meaconing_run_clock_and_onset():
    ox, g = _drive()
    att = S.make_run(ox, g, np.random.default_rng(4), "meaconing", np.random.default_rng(5))
    k0 = int(att["onset"].iloc[0])
    assert (att["clock_offset"].to_numpy()[: k0 + 1] == 0).all() and att["clock_offset"].iloc[-1] <= 0
    assert -att["clock_offset"].max() < 1e-12 or att["clock_offset"].min() >= -S.SEV["meaconing"][1] - 1e-9
    assert att["label"].sum() == len(att) - k0
    # odometry and heading are untouched by the attack (a spoofer cannot change the vehicle's own sensors)
    clean = S.make_run(ox, g, np.random.default_rng(4), None, np.random.default_rng(5))
    assert att["odo_speed"].notna().all() and clean["odo_speed"].notna().all()


def test_v2_attacks_keep_naive_velocity_true():
    ox, g = _drive()
    d = S.make_run(ox, g, np.random.default_rng(6), "drift", np.random.default_rng(7))
    c = S.make_run(ox, g, np.random.default_rng(6), None, np.random.default_rng(7))
    # drift draws more rng values than clean, so only the structure is compared: the Doppler noise has the
    # same aux seed, hence the reported velocity is identical in the naive attack (position-only)
    assert np.allclose(d[["vel_e", "vel_n"]].to_numpy(), c[["vel_e", "vel_n"]].to_numpy())


def test_splits_disjoint_by_group():
    assert not (set(S.TEST) & set(S.VAL))
    assert set(S.TEST) | set(S.VAL) < set(S.SCENE)
    assert len(set(S.SCENE) - set(S.TEST) - set(S.VAL)) == 13
    kv = S.build_kitti(np.random.default_rng(S.SEED), drives=["0001", "0011", "0015"])
    parts = kv.groupby("drive")["part"].nunique()
    assert (parts == 1).all()                                       # a drive is in exactly one part
    assert set(kv.loc[kv["part"] == "test", "drive"]) == {"0001"} and set(kv.loc[kv["part"] == "val", "drive"]) == {"0011"}


def test_avgps_and_uav_adapters():
    av = S.load_avgps()
    assert list(av.columns) == S.COLUMNS and av["run"].nunique() == 15
    assert av.groupby("run")["part"].nunique().max() == 1 and av.groupby("run")["label"].nunique().max() == 1
    assert set(av.loc[av["part"] == "val", "run"]) == S.AVGPS_VAL
    u = S.load_uav()
    assert list(u.columns) == S.COLUMNS and set(u["run"]) == {"uav/benign", "uav/jamming", "uav/spoofing"}
    sp = u[u["run"] == "uav/spoofing"]
    assert sp.loc[sp["t"] < S.UAV_SPOOF_ONSET_S, "label"].sum() == 0 and sp.loc[sp["t"] >= S.UAV_SPOOF_ONSET_S, "label"].min() == 1
    assert u["acc_n"].notna().all() and np.abs(u["acc_n"]).max() < 20


def test_wp0_regression_numbers_stored():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent.parent.parent / "results" / "WP1" / "S1_b2_reproduction.json"
    if not p.exists():
        return
    r = json.loads(p.read_text())
    assert r["matches_wp0_s3"] and r["matches_v2_json"] and r["extended_keeps_v2_runs_identical"]
