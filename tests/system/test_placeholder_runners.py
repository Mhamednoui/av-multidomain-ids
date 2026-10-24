"""Tests for system/placeholder_runners.py (WP7 S1): the LiDAR interim runner (state = previous descriptor, first-scan flag, reset, labels) with a stand-in model, and the network
placeholder (neutral Evidence, labelled; adapter to the documented NetworkDomain.score_stream interface with a stand-in)."""
import numpy as np

from common.calibration import ECDFCalibrator
from common.evidence import Evidence
from lidar.features import describe, temporal
from system.placeholder_runners import LidarInterimRunner, NetworkPlaceholderRunner


class FakeModel:
    """Stand-in for LidarInterimModel: raw = squashed mean of the temporal summary features (any deterministic function of the 429-dim row)."""

    def __init__(self):
        self.cal = ECDFCalibrator().fit(np.linspace(0.0, 0.5, 200))
        self.threshold = 0.99

    def raw(self, X):
        X = np.atleast_2d(X)
        assert X.shape[1] == 429
        return 1 / (1 + np.exp(-np.abs(X[:, -7:]).mean(1) / 50.0)) - 0.5


def _scan(seed, n=6000):
    r = np.random.default_rng(seed)
    pts = np.c_[r.uniform(-40, 40, n), r.uniform(-40, 40, n), r.uniform(-1.8, 1.5, n), r.uniform(0, 1, n)].astype(np.float32)
    return pts


def _stream(seeds):
    return [{"points": _scan(s), "t": 0.1 * k, "sample_id": f"d/{k:010d}.bin"} for k, s in enumerate(seeds)]


def test_lidar_interim_features_state_first_scan_and_labels():
    run = LidarInterimRunner(FakeModel())
    smp = _stream([1, 2, 3])
    out = run.run(smp, key="d")
    assert [e.sample_id for e in out] == [s["sample_id"] for s in smp]
    assert out[0].details["first_scan_no_previous"] and not out[1].details["first_scan_no_previous"]
    assert all(e.details["status"] == "interim" and e.domain == "lidar" and e.layer == "combined" for e in out)
    assert run.status == "interim"
    cur, prev = describe(smp[1]["points"]), describe(smp[0]["points"])      # second scan by hand: describe(cur) + temporal(cur, prev)
    row = np.r_[cur, temporal(cur, prev)]
    expect = float(FakeModel().raw(row)[0])
    assert abs(out[1].details["raw_p_attack"] - expect) < 1e-9


def test_lidar_interim_reset_and_truncation():
    smp = _stream([4, 5, 6, 7])
    full = LidarInterimRunner(FakeModel()).run(smp, key="a")
    part = LidarInterimRunner(FakeModel()).run(smp[:2], key="a")
    assert [e.score for e in part] == [e.score for e in full[:2]]
    r = LidarInterimRunner(FakeModel())
    r.run(_stream([9, 9, 9]), key="other")
    again = r.run(smp, key="a")
    assert [e.score for e in again] == [e.score for e in full] and again[0].details["first_scan_no_previous"]


def test_network_placeholder_is_neutral_and_labelled():
    run = NetworkPlaceholderRunner()
    out = run.run([{"t": 1.0, "sample_id": "f0"}, {"t": 2.0}], key="cap")
    assert len(out) == 2 and all(isinstance(e, Evidence) and e.domain == "network" and not e.alarm and e.score == 0.0 for e in out)
    assert all(e.details["status"] == "placeholder" for e in out) and run.status == "placeholder"


def test_network_adapter_uses_documented_interface_with_stand_in():
    class Stand:
        def score_stream(self, flows):
            comb = [Evidence("network", "combined", "network.combined", float(t), 0.2 * i, i == len(flows) - 1, "r" if i == len(flows) - 1 else "", {"final": False}, str(i))
                    for i, t in enumerate(flows["t"])]
            return comb, {}

    run = NetworkPlaceholderRunner(Stand(), buffer=3)
    out = run.run([{"t": float(k), "sample_id": f"f{k}"} for k in range(5)], key="cap")
    assert [e.sample_id for e in out] == [f"f{k}" for k in range(5)] and all(e.alarm for e in out)
    assert all(e.details["status"] == "placeholder" for e in out)
