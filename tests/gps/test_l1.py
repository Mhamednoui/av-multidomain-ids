"""Tests for gps/l1.py: physical-limit rules on synthetic tracks, causality, layer behaviour, coverage."""
import numpy as np
import pandas as pd

from gps import l1, stream as S


def make(n=60, v=(10.0, 0.0), **over):
    t = np.arange(n, dtype=float)
    vel = np.tile(v, (n, 1))
    d = pd.DataFrame({"t": t, "x": t * v[0], "y": t * v[1], "vel_e": vel[:, 0], "vel_n": vel[:, 1],
                      "numsats": 10.0, "hdop": 1.0, "fix_type": 3.0, "clock_offset": 0.0,
                      "run": "r0"})
    for k, a in over.items():
        d[k] = a
    return d


def feats(d):
    return l1.l1_features(d)


def test_clean_straight_track_inside_every_limit():
    f = feats(make())
    for c in l1.KINEMATIC + ["r_fix", "r_sat_low", "r_dop", "r_clock"]:
        assert f[c].max() < 1.0, c
    assert f["e_velpos"].max() < 1e-9
    assert f["r_speed"].iloc[5] == 10.0 / l1.LIMITS["V_MAX"]


def test_position_jump_violates_acceleration_and_jerk_not_speed_limit_for_small_jump():
    d = make()
    d.loc[30:, "x"] += 40.0                                   # 40 m jump at 1 Hz = +40 m/s for one second
    f = feats(d)
    assert f["r_long"].iloc[30] > 1.0
    assert f["r_long"].iloc[29] < 1.0
    assert f["r_speed"].iloc[30] < 1.0                        # 50 m/s still below 70 m/s
    assert f["e_velpos"].iloc[30] > 30                         # Doppler says 10 m/s, positions say 50 m/s
    d.loc[30:, "x"] += 100.0
    assert feats(d)["r_speed"].iloc[30] > 1.0


def test_lateral_acceleration_and_yaw_rate():
    n = 40
    t = np.arange(n, dtype=float)
    R, v = 4.0, 10.0                                          # radius below R_MIN at 10 m/s: a_lat = 25 m/s^2
    th = v / R * t
    d = make(n)
    d["x"], d["y"] = R * np.sin(th), R * (1 - np.cos(th))
    d["vel_e"], d["vel_n"] = v * np.cos(th), v * np.sin(th)
    f = feats(d)
    assert f["r_lat"].iloc[10] > 1.0
    assert f["r_yaw"].iloc[10] > 1.0
    th2 = 10.0 / 60.0 * t                                     # radius 60 m: fine
    d2 = make(n)
    d2["x"], d2["y"] = 60 * np.sin(th2), 60 * (1 - np.cos(th2))
    d2["vel_e"], d2["vel_n"] = 10 * np.cos(th2), 10 * np.sin(th2)
    f2 = feats(d2)
    assert f2["r_lat"].max() < 1.0 and f2["r_yaw"].max() < 1.0 and f2["r_jerk"].max() < 1.0


def test_yaw_rule_gated_at_low_speed():
    n = 30
    t = np.arange(n, dtype=float)
    d = make(n, v=(1.0, 0.0))
    d["x"] = t * 1.0 * np.where(t % 2 == 0, 1, -1) * 0.0 + 0.5 * np.sin(t * 3.0)   # wandering slowly
    d["vel_e"], d["vel_n"] = 1.0 * np.cos(t * 3), 1.0 * np.sin(t * 3)
    assert feats(d)["r_yaw"].max() == 0.0


def test_features_are_causal():
    rng = np.random.default_rng(0)
    d = make()
    d["x"] += rng.normal(0, 0.5, len(d)); d["y"] += rng.normal(0, 0.5, len(d))
    f1 = feats(d)
    d2 = d.copy()
    d2.loc[40:, ["x", "y", "vel_e", "numsats", "hdop"]] += 100.0
    f2 = feats(d2)
    cols = l1.KINEMATIC + ["e_velpos", "r_sat_low", "r_dop", "d_sat", "d_hdop"]
    assert np.allclose(f1[cols].iloc[:40], f2[cols].iloc[:40])


def test_features_do_not_leak_across_runs():
    a, b = make(20), make(20, v=(0.0, 20.0))
    b["run"] = "r1"; b["x"] += 1e6                             # second run starts a million metres away
    both = pd.concat([a, b], ignore_index=True)
    f = feats(both)
    assert f["r_long"].iloc[20] == 0.0 and f["e_velpos"].iloc[20] == 0.0   # first fix of a run: nothing to difference
    assert np.isclose(f["r_speed"].iloc[20], 20.0 / l1.LIMITS["V_MAX"])    # only its own Doppler speed
    assert f["r_long"].max() < 1.0


def test_receiver_rules():
    d = make(numsats=np.r_[np.full(30, 10.0), np.full(30, 3.0)], fix_type=np.r_[np.full(40, 3.0), np.full(20, 0.0)],
             hdop=np.r_[np.full(50, 1.0), np.full(10, 6.0)])
    f = feats(d)
    assert f["r_sat_low"].iloc[29] == 0 and f["r_sat_low"].iloc[30] == 1.0
    assert f["d_sat"].iloc[30] == 7.0 and f["d_sat"].iloc[31] == 0.0
    assert f["r_fix"].iloc[39] == 0 and f["r_fix"].iloc[40] == 1
    assert f["r_dop"].iloc[49] < 1 and f["r_dop"].iloc[50] > 1
    c = make(clock_offset=np.r_[np.zeros(30), np.linspace(0, 3, 30)])
    assert feats(c)["r_clock"].iloc[40] > 1 and feats(c)["r_clock"].iloc[10] == 0


def test_missing_fields_give_zero_not_nan():
    d = make().drop(columns=["vel_e", "vel_n"])
    d["vel_e"] = np.nan; d["vel_n"] = np.nan
    f = feats(d)
    assert not f.isna().any().any()
    assert (f["e_velpos"] == 0).all()
    assert f["d_noise"].eq(0).all()


def test_layer_physical_alarm_is_the_written_limit_and_calibrated_score_is_monotone():
    d = make()
    d.loc[30:, "x"] += 60.0
    f = feats(d)
    val = feats(make(80))
    lay = l1.L1Rule("r_long").calibrate(pd.concat([val]), budget=0.01)
    ev = lay.score(f)
    raw = f["r_long"].to_numpy()
    assert [e.alarm for e in ev] == list(raw >= 1.0)
    assert all(e.reason for e in ev if e.alarm) and not any(e.reason for e in ev if not e.alarm)
    sc = np.array([e.score for e in ev])
    o = np.argsort(raw, kind="stable")
    assert np.all(np.diff(sc[o]) >= 0)
    assert ev[0].domain == "gps" and ev[0].layer == "L1" and ev[0].name == "gps.long_accel"


def test_data_driven_rule_threshold_from_validation_only_and_tie_safe():
    rng = np.random.default_rng(1)
    val = pd.DataFrame({"d_sat": np.r_[np.zeros(190), np.ones(10)]})            # 5% of val normals have a jump of 1
    lay = l1.L1Rule("d_sat").calibrate(val, budget=0.01)
    test = pd.DataFrame({"d_sat": np.r_[np.zeros(95), np.ones(5), np.full(5, 8.0)]})
    ev = lay.score(test)
    alarm = np.array([e.alarm for e in ev])
    assert not alarm[:95].any()
    assert alarm[100:].all()
    assert (np.array([e.alarm for e in lay.score(val)])).mean() <= 0.01        # tie-safe on validation


def test_doppler_consistent_spoof_stays_inside_l1_but_freeze_does_not():
    rng = np.random.default_rng(3)
    n = 50
    off, dv = S.doppler_pull(n, 10, 2.0, 0.5)
    d = make(n)
    d["x"] += off[:, 0]; d["y"] += off[:, 1]
    d["vel_e"] += dv[:, 0]; d["vel_n"] += dv[:, 1]
    f = feats(d)
    assert f["e_velpos"].max() < 0.5 and f[l1.KINEMATIC].max().max() < 1.0
    fr = make(n)
    fr.loc[20:, ["x", "y"]] = fr.loc[20, ["x", "y"]].to_numpy(float)
    assert feats(fr)["e_velpos"].iloc[25] > 8.0


def test_coverage_table_is_consistent():
    for ds, c in l1.COVERAGE.items():
        assert set(c["evaluated"]) <= set(l1.RULES)
        assert not set(c["evaluated"]) & set(c["not_evaluated"]), ds
    assert "r_sat_low" not in l1.COVERAGE["kitti"]["evaluated"] and "r_dop" not in l1.COVERAGE["avgps"]["evaluated"]
