"""Tests of lidar.domain (WP3 S9): MotionEstimate passthrough on synthetic odometry (no data needed); the frozen domain on real KITTI scans
(skipped if the frozen folder or the data is missing): Evidence contract, causality, first scan, per-layer Evidence."""
from pathlib import Path

import numpy as np

from lidar.domain import COLS, LAYERS, LidarDomain

FROZEN = Path(__file__).resolve().parents[2] / "results" / "WP3" / "S9" / "frozen_lidar"


class Skip(Exception):
    pass


def test_motion_estimates_passthrough_constant_speed():
    t = np.arange(0, 6.0, 0.1)
    P = np.c_[10.0 * t, np.zeros_like(t), np.zeros_like(t)]            # 10 m/s straight
    est = LidarDomain.motion_estimates([2.0, 3.0, 5.0], P, t)
    assert len(est) == 3 and all(e.source == "lidar" for e in est)
    assert all(abs(e.speed - 10.0) < 1e-6 for e in est)
    assert all(abs(e.displacement[0] - 10.0) < 1e-6 and abs(e.displacement[1]) < 1e-6 for e in est)


def test_motion_estimates_quality_inflates_sigma():
    t = np.arange(0, 6.0, 0.1)
    P = np.c_[10.0 * t, np.zeros_like(t), np.zeros_like(t)]
    q = np.zeros((len(t) - 1, 5))
    q[34, 4] = 2                                                         # ICP fallback in the second before t = 3.5
    good, bad = LidarDomain.motion_estimates([2.0, 3.5], P, t, q)
    assert bad.sigma > 2.5 * good.sigma


def test_motion_estimates_skip_fixes_without_full_window():
    t = np.arange(0, 3.0, 0.1)
    P = np.c_[5.0 * t, np.zeros_like(t), np.zeros_like(t)]
    est = LidarDomain.motion_estimates([0.5, 2.0], P, t)
    assert len(est) == 1 and est[0].t == 2.0


def _scans(n=4):
    from lidar import ego
    from lidar.data import load, scan_files
    try:
        files = scan_files("0095")[:n]
        pose = ego.poses("0095")[:n]
        return [load(f) for f in files], pose
    except Exception:
        raise Skip("KITTI data missing")


def test_frozen_domain_evidence_contract_and_causality():
    if not (FROZEN / "domain.pkl").exists():
        raise Skip("frozen domain not built")
    scans, pose = _scans(4)
    d = LidarDomain.load(FROZEN)
    s = d.stream()
    out = [s.push(scans[i], pose[i], t=0.1 * i, sample_id=f"x/{i}") for i in range(4)]
    comb0, per0 = out[0]
    assert comb0.domain == "lidar" and comb0.layer == "combined" and comb0.name == "lidar.combined"
    assert comb0.details["first_scan_no_previous"] is True and per0["L2c"].details["available"] is False
    for c, per in out:
        assert 0.0 <= c.score <= 1.0 and set(per) == set(LAYERS)
        assert all(0.0 <= e.score <= 1.0 and e.domain == "lidar" for e in per.values())
        assert set(c.details["layer_scores"]) == set(LAYERS) and c.sample_id.startswith("x/")
    # causal: scores of scan 2 do not depend on the scans after it
    c2, _ = d.score_scan(scans[2], pose[2], (scans[1], pose[1]), t=0.2, sample_id="x/2")
    assert abs(c2.score - out[2][0].score) < 1e-12 and c2.alarm == out[2][0].alarm


def test_intensity_model_equals_object_model_on_intensity_columns(tmp_path=None):
    import pandas as pd
    from lidar import density as D
    from lidar.domain import IntensityModel
    from lidar.phantom import Calib
    rng = np.random.default_rng(0)
    calib = Calib([6, 12, 16, 20, 25, 30, 35, 45], [0.6] * 7, np.inf, [[np.array([0.2])] for _ in range(7)])

    def objs(n):
        rows = []
        for _ in range(n):
            rings, steps = int(rng.integers(4, 12)), int(rng.integers(10, 60))
            rows.append(dict(range=rng.uniform(8, 40), ring_min=10, ring_max=10 + rings - 1, az_span=(steps - 1) * 0.1728,
                             n_points=int(rng.integers(8, 200)), int_mean=float(rng.normal(0.25, 0.1))))
        return pd.DataFrame(rows)

    full = D.ObjectModel(calib, nmin=10).fit(objs(3000))
    cut = IntensityModel.from_model(full)
    x = objs(500)
    a, b = full.scores(x), cut.scores(x)
    assert (a[["int_hi", "int_lo"]].to_numpy() == b[["int_hi", "int_lo"]].to_numpy()).all()
    assert (b[["dens_hi", "dens_lo"]].to_numpy() == 0).all()
    x["scan"] = np.repeat(np.arange(50), 10)
    sa, sb = D.scan_scores(x, a), D.scan_scores(x, b)
    cols = ["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]
    assert (sa[cols].to_numpy() == sb[cols].to_numpy()).all()
