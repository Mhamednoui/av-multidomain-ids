"""Tests for gps/ekf.py: NIS consistency on a synthetic clean track, detection of a jump, gating, layer contract."""
import numpy as np
import pandas as pd

from gps import ekf
from gps.ekf import EKFConfig


def track(n=200, seed=0, v=10.0, noise=True):
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)
    cfg = EKFConfig()
    w = np.zeros((n, 2))
    for k in range(1, n):
        w[k] = cfg.gm_phi * w[k - 1] + np.sqrt(1 - cfg.gm_phi ** 2) * cfg.gm_sigma * rng.normal(size=2)
    x, y = t * v + w[:, 0], np.zeros(n) + w[:, 1]
    e = lambda s: rng.normal(0, s, n) if noise else np.zeros(n)
    return pd.DataFrame({"t": t, "x": x + e(0.3), "y": y + e(0.3), "vel_e": v + e(0.05), "vel_n": e(0.05),
                         "odo_speed": v + e(0.05), "heading": 90.0 + e(2.0), "acc_e": e(0.05), "acc_n": e(0.05), "run": "r"})


def test_clean_track_is_consistent():
    nis = np.concatenate([ekf.filter_run(track(seed=s), EKFConfig(q_acc=0.05, k_scale=0.0))["nis"].to_numpy()[5:] for s in range(5)])
    assert 0.7 < nis.mean() / 6 < 1.4
    assert (nis > 12.59).mean() < 0.12


def test_position_jump_is_flagged():
    d = track()
    d.loc[100:, "x"] += 30.0
    r = ekf.filter_run(d, EKFConfig())
    assert r["nis"].iloc[100] > 50
    assert r["nis"].iloc[50:99].max() < 40


def test_gating_stops_the_filter_following_a_slow_drift():
    d = track(n=300, noise=False)
    t = d["t"].to_numpy()
    d["x"] = d["x"] + np.clip(t - 100, 0, None) * 0.5       # 0.5 m/s drift of position only (Doppler stays true)
    ung = ekf.filter_run(d, EKFConfig())
    gat = ekf.filter_run(d, EKFConfig().gated(0.99))
    truth = t * 10.0
    err_u = abs(ung["est_x"].iloc[250] - truth[250])
    err_g = abs(gat["est_x"].iloc[250] - truth[250])
    assert err_g < err_u or err_u < 1.0
    assert gat["hold"].iloc[250]
    assert gat["nis"].iloc[250] > ung["nis"].iloc[250] or ung["nis"].iloc[250] > 20


def test_layer_contract_and_causality():
    d = track()
    lay = ekf.EKFLayer(EKFConfig()).calibrate(d, budget=0.05)
    ev = lay.score(d)
    assert len(ev) == len(d) and ev[0].domain == "gps" and ev[0].layer == "L2a"
    assert all(0 <= e.score <= 1 for e in ev)
    ev2 = lay.score(d.iloc[:120])
    assert np.allclose([e.score for e in ev[:120]], [e.score for e in ev2])      # row k uses rows <= k only


def test_runs_do_not_leak_into_each_other():
    a, b = track(seed=1), track(seed=2)
    b["run"] = "r2"
    b["x"] += 1000.0                                                              # different place
    both = pd.concat([a, b], ignore_index=True)
    r = ekf.run_filter_all(both, EKFConfig())
    assert r["nis"].iloc[200:].max() < 60                                         # second run starts from its own first fix
    assert np.allclose(r["nis"].iloc[1:200], ekf.filter_run(a, EKFConfig())["nis"].iloc[1:200])


def test_no_odometry_no_heading_still_runs():
    d = track().drop(columns=["odo_speed", "heading", "acc_e", "acc_n"])
    r = ekf.filter_run(d, EKFConfig(use_odo=False, use_head=False, acc_mode="none"))
    assert (r["dim"].iloc[1:] == 4).all()
