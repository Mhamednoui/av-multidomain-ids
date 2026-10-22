"""Unit tests for crossdomain/consistency.py and crossdomain/attacks.py (WP6 S2 "which domain lies")."""
import numpy as np
import pandas as pd

from crossdomain import attacks as A
from crossdomain import consistency as CS

TRI = [CS.Edge("gps", "lidar", "speed"), CS.Edge("gps", "can", "speed"), CS.Edge("lidar", "can", "speed")]
DOM = {"gps": "gps", "lidar": "lidar", "can": "can"}


def test_cusum_accumulates_small_bias_and_holds_nan():
    z = np.r_[np.zeros(5), np.full(20, 0.8), [np.nan], np.zeros(3)][:, None]
    s = CS.cusum(z, 0.5)
    assert s[4, 0] == 0.0
    assert np.isclose(s[24, 0], 20 * 0.3)                     # 0.8 - k per step
    assert s[25, 0] == s[24, 0]                               # NaN -> state held
    assert np.isclose(s[26, 0], s[24, 0] - 0.5)               # decays by k on a zero
    assert np.allclose(CS.cusum(z, "inst")[:5, 0], 0.0)
    assert np.isnan(CS.cusum(np.array([[np.nan], [1.0]]), 0.5)[0, 0])


def test_blame_single_liar_and_undecided_cases():
    obs = [True, True, True]
    assert CS.blame_pattern(TRI, [True, True, False], obs) == "gps"
    assert CS.blame_pattern(TRI, [True, False, True], obs) == "lidar"
    assert CS.blame_pattern(TRI, [False, True, True], obs) == "can"
    assert CS.blame_pattern(TRI, [True, True, True], obs) == CS.UNDECIDED       # two liars / all disagree
    assert CS.blame_pattern(TRI, [True, False, False], obs) == CS.UNDECIDED      # one pair: who lies?
    assert CS.blame_pattern(TRI, [True, True, False], [True, True, False]) == CS.UNDECIDED   # partners' agreement not observed
    assert CS.blame_pattern(TRI, [False, False, False], obs) is None
    two = [CS.Edge("gnss", "can", "speed")]
    assert CS.blame_pattern(two, [True], [True]) == CS.UNDECIDED                 # only 2 witnesses


def test_layer_end_to_end_and_evidence():
    rng = np.random.default_rng(0)
    clean = [rng.normal(0, 1, (200, 3)) for _ in range(10)]
    layer = CS.WhichDomainLies(TRI, DOM, k=0.5).fit(clean)
    fa = np.mean([layer.run(Z)["layer_alarm"].mean() for Z in clean])
    assert fa <= 0.01 + 1e-9
    Z = rng.normal(0, 1, (120, 3))
    Z[60:, 0] += 3.0                                          # gps biased vs lidar
    Z[60:, 1] += 3.0                                          # gps biased vs can; lidar-can agree
    t = np.arange(120.0)
    res = layer.run(Z)
    o = CS.run_outcome(t, 60.0, res)
    assert o["detected"] and o["blame"] == "gps" and o["delay"] <= 5
    ev = layer.evidence(t, Z)
    al = [e for e in ev if e.alarm]
    assert al and al[-1].domain == "cross" and al[-1].details["blamed_domain"] == "gps" and "gps" in al[-1].reason
    d = CS.WhichDomainLies.from_dict(layer.to_dict())
    assert np.array_equal(d.run(Z)["layer_alarm"], res["layer_alarm"])


def test_gnss_attacks_follow_wp1_equations():
    t = np.arange(0, 60, 0.2)
    E, N = 20.0 * t, np.zeros_like(t)
    ve, vn = np.full_like(t, 20.0), np.zeros_like(t)
    for name in ("drift", "accel_drift", "doppler_spoof", "meaconing"):
        E2, N2, ve2, vn2, sev = A.gnss_attack(name, t, E, N, ve, vn, 10.0, np.random.default_rng(1))
        pre = t < 10.0
        assert np.allclose(E2[pre], E[pre]) and np.allclose(ve2[pre], ve[pre])
        if name == "doppler_spoof":                           # position offset = integral of the velocity offset
            dpos = np.gradient(np.hypot(E2 - E, N2 - N), t)
            assert np.allclose(dpos[100:-1], np.hypot(ve2 - ve, vn2 - vn)[100:-1], atol=0.05)
        if name in ("drift", "accel_drift"):
            assert np.allclose(ve2, ve)                       # naive spoof: Doppler stays true
        if name == "meaconing":
            assert np.all(np.hypot(ve2, vn2) >= 0.8 * 20.0 - 1e-6)   # apparent speed >= (1 - TAU_RATE) v


def test_can_and_lidar_attacks():
    t = np.arange(0, 30, 0.01)
    v = np.full_like(t, 10.0)
    v2, s = A.can_attack("can_scale", t, v, 10.0, np.random.default_rng(2))
    assert np.allclose(v2[t < 10], 10.0) and np.allclose(v2[t >= 10], 10.0 * (1 + s)) and 0.02 <= abs(s) <= 0.2
    vf, _ = A.can_attack("can_freeze", t, np.linspace(5, 15, len(t)), 10.0, np.random.default_rng(2))
    assert np.ptp(vf[t >= 10]) == 0
    vo, b = A.can_attack("can_offset", t, v, 10.0, np.random.default_rng(3))
    assert np.isclose(vo[-1] - 10.0, b) and np.isclose(vo[t <= 10].max(), 10.0)
    g = pd.DataFrame({"dx": 10.0, "dy": 0.1, "speed": 10.0, "yaw_rate": 0.0}, index=pd.Index(np.arange(1.0, 31.0), name="t"))
    g2, s = A.lidar_attack("lidar_scale", g, 10.0, np.random.default_rng(4))
    assert np.allclose(g2.loc[10.0:, "dx"], 10.0 * (1 + s)) and np.allclose(g2.loc[:9.0, "dx"], 10.0)
    g3, w = A.lidar_attack("lidar_yaw", g, 10.0, np.random.default_rng(4))
    assert np.allclose(g3.loc[10.0:, "yaw_rate"], w)


def test_along_track_is_doppler_consistent():
    t = np.arange(0, 40, 0.1)
    ve, vn = np.full_like(t, 3.0), np.full_like(t, 4.0)
    dE, dN, dve, dvn, w = A.along_track(t, ve, vn, 5.0, 2.0)
    assert np.allclose(np.hypot(ve + dve, vn + dvn)[-1], 7.0)
    assert np.allclose(np.hypot(dE, dN)[-1], A.ramp_integral(t, 5.0, 2.0)[-1], atol=1e-6)
