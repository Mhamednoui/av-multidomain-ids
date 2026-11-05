"""WP8 S8 tests: the reference-health gate (system/health31.py). Synthetic inputs only (the union test fits a small Union on random reference ranks)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from system import health31 as H


def test_degraded_thresholds_and_nonfinite():
    d = H.degraded_frames([0.1, 5.0, 5.01, 1.0, np.nan, 0.2], [0.01, 0.01, 0.01, 0.51, 0.01, np.inf])
    assert list(d) == [False, False, True, True, True, True]


def test_tick_gate_window_is_causal_and_one_second():
    t = np.arange(0, 10, 0.1)
    deg = np.zeros(len(t), bool)
    deg[(t >= 3.05) & (t <= 3.25)] = True            # frames at 3.1, 3.2
    g = H.tick_gate(t, deg, np.array([2.0, 3.0, 3.2, 4.0, 4.1, 4.3, 5.0]))
    assert list(g) == [False, False, True, True, True, False, False]
    assert not H.tick_gate(t, np.zeros(len(t), bool), np.array([1.0, 2.0])).any()


def test_gate_series_withholds_verdicts_only_where_gated():
    n = 6
    s = {"gps_score": np.linspace(0, 1, n).astype(np.float32), "gps_alarm": np.array([0, 1, 1, 0, 1, 1], bool), "cross_score": np.ones(n, np.float32), "cross_alarm": np.ones(n, bool),
         "cross_layers": np.ones((n, 7), np.float32), "cross_layer_alarm": np.ones((n, 7), bool), "cross_present": np.ones(n, bool),
         "blame_A1": np.array(["gps"] * n, object), "blame_A3": np.array(["gps"] * n, object), "blame_V3": np.array(["gps"] * n, object)}
    g = np.array([0, 1, 1, 0, 0, 0], bool)
    o = H.gate_series(s, g)
    assert list(o["gps_alarm"]) == [False, False, False, False, True, True]
    assert o["cross_alarm"].tolist() == [True, False, False, True, True, True]
    assert o["gps_score"][1] == 0 and o["gps_score"][3] == s["gps_score"][3] and o["cross_layers"][2].sum() == 0 and o["cross_layers"][0].sum() == 7
    assert o["blame_A1"][1] is None and o["blame_A1"][0] == "gps" and not o["cross_present"][1]
    assert s["gps_alarm"][1] and s["blame_A1"][1] == "gps"        # input not modified


def test_mask_union_equals_union_without_gate_and_drops_pose_layers():
    from lidar.combine31 import Union
    rng = np.random.default_rng(3)
    ref = {l: rng.random(2000) for l in H.LIDAR_LAYERS}
    u = Union(budgets=np.array([0.0025] * 4)).fit(ref)
    raw = {l: rng.random(500) for l in H.LIDAR_LAYERS}
    raw["L2d"][:50] = 5.0                                         # pose layer fires on the first 50 scans
    s0, sc0, a0 = H.mask_union(u, raw, np.zeros(500, bool))
    assert np.array_equal(a0, u.alarm(raw)) and np.allclose(s0, u.stat(raw)) and np.allclose(sc0, u.score(raw))
    g = np.zeros(500, bool)
    g[:25] = True
    s1, sc1, a1 = H.mask_union(u, raw, g)
    assert a0[:50].all() and not a1[:25].any() and a1[25:50].all()  # masked scans lose the L2d alarm, ungated ones keep it
    assert np.array_equal(a1[50:], a0[50:]) and np.allclose(s1[50:], s0[50:])
    raw2 = dict(raw)
    raw2["L2c"] = raw["L2c"].copy()
    raw2["L2c"][:25] = 5.0
    assert not H.mask_union(u, raw2, g)[2][:25].any()
    raw2["L1"] = raw["L1"].copy()
    raw2["L1"][:25] = 5.0
    assert H.mask_union(u, raw2, g)[2][:25].all()                  # pose-free layer L1 still fires at gated scans
