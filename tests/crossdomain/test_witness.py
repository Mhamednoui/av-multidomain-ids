"""Unit tests for crossdomain/ (WP6 S1 motion witnesses)."""
import numpy as np
import pandas as pd

from common.motion import MotionEstimate
from crossdomain import can_sim, comma, v2x_self
from crossdomain import witness as W


def _inst_frame(t, v, src="can", sigma=0.3):
    n = len(t)
    return pd.DataFrame({"t": t, "source": src, "speed": v, "yaw_rate": np.nan, "dx": np.nan, "dy": np.nan, "sigma": np.full(n, sigma)})


def test_to_frame_fields():
    f = W.to_frame([MotionEstimate(t=2.0, source="lidar", speed=3.0, yaw_rate=0.1, displacement=(3.0, 0.2), sigma=0.1),
                    MotionEstimate(t=1.0, source="can", speed=2.0, sigma=0.3)])
    assert list(f.columns) == W.COLS
    assert f["t"].tolist() == [1.0, 2.0]
    assert np.isnan(f.loc[0, "dx"]) and f.loc[1, "dy"] == 0.2


def test_interval_mean_exact_for_constant_acceleration():
    t = np.arange(0, 10.0 + 1e-9, 1.0)
    v = 2.0 + 0.7 * t                                        # 1 Hz instantaneous samples
    g = W.to_grid(_inst_frame(t, v), np.arange(1.0, 10.0))
    want = 2.0 + 0.7 * (np.arange(1.0, 10.0) - 0.5)          # true mean over (t-1, t]
    assert np.allclose(g["speed"].to_numpy(), want)


def test_interval_mean_high_rate_and_gap():
    t = np.arange(0, 20, 0.01)
    v = np.sin(t)
    keep = (t < 8.0) | (t > 11.0)                            # 3 s hole
    g = W.to_grid(_inst_frame(t[keep], v[keep]), np.arange(1.0, 19.0))
    want = np.cos(np.arange(1.0, 19.0) - 1) - np.cos(np.arange(1.0, 19.0))
    s = g["speed"].to_numpy()
    assert np.isnan(s[[7, 8, 9]]).all() and np.isnan(s[10])  # seconds touching the hole are dropped
    ok = np.isfinite(s)
    assert np.allclose(s[ok], want[ok], atol=1e-4)


def test_mean_source_matching_and_lag():
    f = pd.DataFrame({"t": [1.02, 2.0, 3.3], "source": "gps", "speed": [1.0, 2.0, 3.0], "yaw_rate": 0.0, "dx": 0.0, "dy": 0.0, "sigma": 0.45})
    g = W.to_grid(f, np.array([1.0, 2.0, 3.0]))
    assert g["speed"].tolist()[:2] == [1.0, 2.0] and np.isnan(g["speed"].iloc[2])
    g2 = W.to_grid(f, np.array([3.0]), lag=0.3)
    assert g2["speed"].iloc[0] == 3.0


def test_lag_recovery():
    rng = np.random.default_rng(0)
    parts = []
    for k in range(4):
        t = np.arange(0, 120, 0.05)
        x = np.convolve(rng.normal(0, 1, len(t)), np.ones(20) / 20, mode="same")     # smooth random signal
        v = np.cumsum(x) * 0.05 + 10
        tb = np.arange(0.013, 120, 0.1)
        vb = np.interp(tb - 0.30, t, v) + rng.normal(0, 0.01, len(tb))              # b lags a by 0.30 s
        parts.append(W.lag_covariance(t, v, tb, vb, max_lag=1.0, dt=0.01, diff=0.2))
    est = W.estimate_lag(parts, n_boot=100)
    assert abs(est["lag"] - 0.30) < 0.05, est


def test_lag_recovery_through_can_sim():
    rng = np.random.default_rng(1)
    t = np.arange(0, 60, 0.1)
    vf = 8 + 3 * np.sin(t / 3.0) + np.cumsum(rng.normal(0, 0.05, len(t)))
    ox = {"t": t, "vf": vf, "wz": np.zeros(len(t))}
    tm, ids, dlc, B, truth = can_sim.simulate_frames(ox, rng, scale=0.0, latency=0.3)
    raw = np.c_[[s.decode(B) for s in can_sim._sigs()]].T.mean(1) * can_sim.UNIT_MPS
    est = W.estimate_lag([W.lag_covariance(t, vf, tm, raw, max_lag=1.0, dt=0.01, diff=0.2)], n_boot=50)
    assert abs(est["lag"] - 0.30) < 0.05, est


def test_encode_decode_roundtrip():
    rng = np.random.default_rng(2)
    raw = rng.integers(0, 1 << 14, (50, 4))
    B = can_sim.encode_wheels(raw)
    dec = np.c_[[s.decode(B) for s in can_sim._sigs()]].T
    assert (dec == raw).all()


def test_can_sim_through_frozen_domain():
    from can.domain import CanDomain
    from common.config import RESULTS
    dom = CanDomain.load(RESULTS / "WP2" / "s7_domain")
    t = np.arange(0, 30, 0.1)
    ox = {"t": t, "vf": np.full(len(t), 10.0), "wz": np.full(len(t), 0.1)}
    est = can_sim.can_motion_estimates(dom, can_sim.simulate_frames(ox, np.random.default_rng(3), scale=0.0))
    assert len(est) >= 25 and all(e.source == "can" for e in est)
    sp = np.array([e.speed for e in est])
    assert np.all(np.abs(sp - 10.0) < 0.05)                  # 0.01 km/h unit, 4-wheel mean cancels the turn split
    assert abs(est[0].sigma - 0.3) < 1e-9


def test_pair_table_and_honesty():
    rng = np.random.default_rng(4)
    grid = np.arange(1.0, 2001.0)
    v = 10 + rng.normal(0, 1, len(grid))
    ga = pd.DataFrame({"speed": v + rng.normal(0, 0.3, len(grid)), "yaw_rate": 0.0, "dx": 0.0, "dy": 0.0, "sigma": 0.3}, index=pd.Index(grid, name="t"))
    gb = pd.DataFrame({"speed": v + rng.normal(0, 0.4, len(grid)), "yaw_rate": 0.0, "dx": 0.0, "dy": 0.0, "sigma": 0.4}, index=pd.Index(grid, name="t"))
    tab = W.pair_table(ga, gb, "gps", "lidar", "speed")
    assert np.allclose(tab["s"], 0.5)
    h = W.honesty(tab["z"])
    assert h["honest"] and abs(h["std"] - 1) < 0.06
    assert not W.honesty(tab["z"] * 2)["honest"]


def test_sigma_model_recovers_noise_and_bias():
    rng = np.random.default_rng(5)
    v = rng.uniform(0, 30, 20000)
    r = 0.1 + 0.01 * v + rng.normal(0, 1, len(v)) * np.sqrt(0.2 ** 2 + (0.02 * v) ** 2)
    m = W.SigmaModel(bias="linear").fit(r, v)
    d = m.to_dict()
    assert abs(d["bias"] - 0.1) < 0.02 and abs(d["bias_per_mps"] - 0.01) < 0.002
    assert abs(d["a"] - 0.2) < 0.03 and abs(d["b"] - 0.02) < 0.003
    m2 = W.SigmaModel.from_dict(d)
    assert np.allclose(m2.z(r, v), m.z(r, v))
    assert W.honesty(m.z(r, v))["honest"]
    c = W.SigmaModel().fit(r, v)                               # pre-registered constant bias
    assert c.to_dict()["bias_per_mps"] == 0.0


def test_comma_helpers():
    B = np.array([[0x35, 0x77, 0x35, 0x62, 0x35, 0x5C, 0x35, 0x48]], np.uint8)
    cnt = comma.raw_wheel_counts(B)
    assert cnt[0, 0] == 0x3577
    assert abs(cnt[0, 0] * 0.01 - 67.67 - 69.2) < 0.01        # Toyota convention: km/h
    t = np.arange(0, 5, 0.2)
    ty, w = comma.gnss_yaw_rate(t, 10.0 * t, np.full(len(t), 20.0))    # bearing grows clockwise = right turn
    assert np.allclose(w, -np.radians(10.0))
    rs = [type("P", (), {"name": f"d_2018-08-{k:02d}--00-00-00"})() for k in range(1, 21)]
    sp = comma.split_routes(rs)
    assert [len(sp[k]) for k in ("train", "val", "test")] == [12, 4, 4]
    assert sp["train"][-1].name < sp["val"][0].name < sp["test"][0].name


def test_v2x_self_report():
    tr = pd.DataFrame({"t": [0.0, 1.0, 2.0, 5.0], "x": [0.0, 0.0, 0.0, 0.0], "y": [0.0, 10.0, 20.0, 50.0], "speed": [10.0] * 4,
                       "heading": [np.pi / 2] * 4, "yaw_rate": [np.nan] * 4, "spd_sigma": [np.nan] * 4})
    est = v2x_self.bsm_motion_estimates(tr)
    assert len(est) == 2                                       # the 3 s gap is skipped
    assert np.allclose(est[0].displacement, (10.0, 0.0)) and est[0].yaw_rate is None and est[0].sigma == 0.45
