"""Tests for WP6 S5: fusion/correlator.py (temporal correlator, tick blame, response) and fusion/system.py DensityTransform / M2System."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fusion.correlator import TemporalCorrelator, respond, tick_blame  # noqa: E402
from fusion.system import DensityTransform, M2System, SystemFusion  # noqa: E402


def _alarm(n, ticks):
    a = np.zeros(n, bool)
    a[list(ticks)] = True
    return a


def test_persistence_m_of_w():
    c = TemporalCorrelator(m=2, w=3, gap=5)
    assert c.events(_alarm(30, [4])) == []                        # one isolated alarm tick: LOG only
    ev = c.events(_alarm(30, [4, 6]))
    assert len(ev) == 1 and ev[0].start == 6 and ev[0].first_alarm == 4 and ev[0].end == 6
    assert c.events(_alarm(30, [4, 8])) == []                     # same episode (gap 4 <= 5) but never 2 alarms in 3 ticks
    assert c.log_ticks(_alarm(30, [4, 8])) == 2


def test_gap_merges_and_splits():
    c = TemporalCorrelator(m=1, w=1, gap=5)
    assert len(c.events(_alarm(40, [1, 6, 11]))) == 1             # gaps of 5 merge
    assert len(c.events(_alarm(40, [1, 7]))) == 2                 # gap 6 splits
    assert len(TemporalCorrelator(1, 1, 15).events(_alarm(40, [1, 7, 20]))) == 1


def test_corroboration_opens_immediately():
    a = _alarm(20, [5])
    own = np.zeros((20, 3), bool)
    own[5, [0, 2]] = True
    assert TemporalCorrelator(3, 5, 5, corroborate=False).events(a, own) == []
    ev = TemporalCorrelator(3, 5, 5, corroborate=True).events(a, own, ["gps", "can", "cross"])
    assert len(ev) == 1 and ev[0].corroborated and ev[0].start == 5 and ev[0].domains == ["gps", "cross"]


def test_episode_window_is_causal():
    c = TemporalCorrelator(m=3, w=5, gap=5)
    m = c.confirmed_mask(_alarm(30, [2, 3, 4, 5]))
    assert list(np.flatnonzero(m)) == [4, 5]                      # confirmation at the third alarm; earlier ticks were not yet an alert


def test_tick_blame_rules():
    names = ["gps", "can", "cross"]
    X = np.array([[0.2, 0.9, 0.99], [0.95, 0.3, 0.99], [0.1, 0.2, 0.99], [0.0, 0.0, 0.0]])
    own = np.array([[False, True, True], [True, False, True], [False, False, True], [False, False, False]])
    cb = np.array(["lidar", "undecided", "undecided", None], object)
    out = tick_blame(names, X, own, cb, own[:, 2])
    assert list(out) == ["lidar", "gps", "undecided", "undecided"]  # decided cross blame wins; own alarm; cross-only stays undecided; no evidence


def test_respond_levels():
    assert respond({"undecided": 5}, "undecided", 10)[0] == "WARN"
    assert respond({"v2x": 2}, "v2x", 10)[0] == "WARN"
    assert respond({"network": 60}, "network", 60)[0] == "DEGRADE"          # network / V2X alone never above DEGRADE
    assert respond({"can": 5}, "can", 10)[0] == "DEGRADE"
    assert respond({"can": 5}, "can", 30)[0] == "SAFE_STOP"                # motion-critical degrade lasting >= 30 s
    assert respond({"gps": 4, "can": 3}, "gps", 5) == ("SAFE_STOP", ["can", "gps"])


def test_density_transform():
    rng = np.random.default_rng(0)
    t0 = DensityTransform(0.0).fit(rng.random(100))
    M = rng.random(50)
    assert np.array_equal(t0.transform(M, np.full(50, 7)), M)               # alpha 0 = the S3 tick score unchanged
    t1 = DensityTransform(1.0).fit(rng.random(20000))
    for k in (1, 5, 40):
        q = t1.transform(rng.random((5000, k)).max(axis=1), np.full(5000, k))
        assert abs(np.mean(q) - 0.5) < 0.03                                 # uniform under the null for any density
    assert t1.transform(np.array([0.9]), np.array([0]))[0] == 0.0          # no sample -> no evidence


def test_m2system_run():
    rng = np.random.default_rng(1)
    doms = ["can", "v2x"]
    fus = SystemFusion(doms, "noisy_or").fit_calibration({d: rng.random(500) for d in doms})
    fus.threshold = 0.5
    sysm = M2System(doms, {d: DensityTransform(0.0) for d in doms}, fus, TemporalCorrelator(2, 3, 5))
    n = 30
    parts = {d: {"score": np.zeros(n), "count": np.ones(n), "dom_alarm": np.zeros(n, bool), "layer_alarm": np.zeros((n, 1), bool)} for d in doms}
    parts["can"]["score"][10:14] = 2.0
    parts["can"]["dom_alarm"][10:14] = True
    r = sysm.run(parts, {d: [f"{d}.l"] for d in doms})
    assert r["alarm"][10:14].all() and len(r["events"]) == 1
    e = r["events"][0]
    assert e.blamed == "can" and e.response == "DEGRADE" and "first alarm" in e.explanation and e.start == 11
