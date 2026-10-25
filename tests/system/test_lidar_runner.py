"""WP7 S2: LidarRunner (system/lidar_runner.py) is the frozen LiDAR stream: same Evidence as LidarStream.push, 5 Evidence per scan (combined + 4 layers), first scan flagged, reset clears the
previous scan, latency log has one entry per scan. Uses 3 scans of the VALIDATION drive 0011 (skipped when the KITTI raw data or the frozen domain folder is missing)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
FROZEN = ROOT / "results" / "WP3" / "S9" / "frozen_lidar"


class Skip(Exception):
    pass


def _data():
    if not (FROZEN / "domain.pkl").exists():
        raise Skip("frozen LiDAR domain not present")
    from lidar import ego
    from lidar.data import load, scan_files
    try:
        files = scan_files("0011")[:3]
    except Exception as e:
        raise Skip(f"KITTI drive 0011 not available: {e}")
    if len(files) < 3:
        raise Skip("KITTI drive 0011 not available")
    return [load(f) for f in files], ego.poses("0011")[:3]


def test_runner_equals_frozen_stream():
    from lidar.domain import LAYERS, LidarDomain
    from system.lidar_runner import LidarRunner
    pts, pose = _data()
    dom = LidarDomain.load(FROZEN)
    run = LidarRunner(dom)
    run.reset("0011")
    ref = dom.stream()
    for i in range(3):
        out = run.push({"points": pts[i], "pose": pose[i], "t": 0.1 * i, "sample_id": f"s{i}"})
        comb, per = ref.push(pts[i], pose[i], 0.1 * i, f"s{i}")
        assert len(out) == 5 and out[0].layer == "combined"
        assert abs(out[0].score - comb.score) == 0.0 and out[0].alarm == comb.alarm
        for j, x in enumerate(LAYERS):
            assert abs(out[1 + j].score - per[x].score) == 0.0 and out[1 + j].alarm == per[x].alarm
        assert out[0].details["first_scan_no_previous"] == (i == 0)
    assert len(run.latency.ns) == 3 and run.period_s == 0.1


def test_reset_clears_previous_scan():
    from lidar.domain import LidarDomain
    from system.lidar_runner import LidarRunner
    pts, pose = _data()
    run = LidarRunner(LidarDomain.load(FROZEN))
    run.reset("a")
    run.push({"points": pts[0], "pose": pose[0], "t": 0.0})
    run.push({"points": pts[1], "pose": pose[1], "t": 0.1})
    run.reset("b")
    out = run.push({"points": pts[1], "pose": pose[1], "t": 0.1})
    assert out[0].details["first_scan_no_previous"] is True
    assert np.isfinite(out[0].score)
