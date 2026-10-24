"""WP3 S5 tests: see-through (sandwich) search, tile counts, scan statistics, best-case attacker calibration."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lidar import occlusion as O
from lidar.phantom import Calib


def _row(az, rho, lab):
    az, rho, lab = np.asarray(az, float), np.asarray(rho, float), np.asarray(lab)
    return np.zeros(len(az), np.int64), az, lab, rho


def test_far_point_between_object_points_is_found():
    g, az, lab, rho = _row([10.0, 10.18, 10.36], [20.0, 35.0, 20.1], [0, -1, 0])
    p, ex, sp, st = O.sandwich(g, az, lab, rho, 0.8, lambda a, b: a - b)
    assert list(p) == [0] and ex[0] > 14 and abs(sp[0] - 0.36) < 1e-9


def test_not_found_when_nearer_or_outside_or_other_cluster_or_far_gap():
    for az, rho, lab, gap in [([10, 10.18, 10.36], [20, 20.2, 20.1], [0, -1, 0], 0.8),      # not farther
                              ([10, 10.18, 10.36], [20, 35, 20.1], [0, -1, 1], 0.8),        # different clusters
                              ([10, 10.18, 12.0], [20, 35, 20.1], [0, -1, 0], 0.8),         # gap too large
                              ([10, 10.18, 10.36], [20, 35, 30.0], [0, -1, 0], 0.8),        # object points at different range
                              ([10, 10.18, 10.36], [20, 35, 20.1], [0, 0, 0], 0.8)]:        # the middle point is in the cluster
        g, a, l_, r = _row(az, rho, lab)
        assert len(O.sandwich(g, a, l_, r, gap, lambda x, y: x - y)[0]) == 0


def test_tile_table_counts_and_scan_stats():
    n = 40
    rng = np.random.default_rng(0)
    az = np.radians(np.arange(n) * 0.18)
    r = np.full(n, 15.0)
    r[20] = 30.0                                    # one far return inside the object row
    lab = np.zeros(n, int)
    lab[20] = -1
    pts = np.c_[r * np.cos(az), r * np.sin(az), rng.uniform(0, 1, n), np.full(n, 0.3)].astype(np.float32)
    k = np.full(n, 20)
    rank = np.arange(64)
    t = O.tile_table(pts, lab, k, rank)
    assert t["sr_0_0_0"].sum() == 1 and 24 <= t["n_points"].sum() <= n - 1
    t.insert(0, "scan", "a")
    s = O.scan_stats(t, (0, 0, 0), ["a", "b"])
    assert s.loc["a", "tot"] == 1 and s.loc["b", "tot"] == 0 and s.loc["a", "maxf"] > 0


def test_full_calibration_fills_every_ray():
    c = Calib([6, 12, 20, 30], [0.4, 0.5, 0.6], 5.0, [[np.array([0.2])]] * 3)
    f = O.FullCalib.of(c)
    assert f.draw_pi(15.0, np.random.default_rng(0)) == 1.0
    assert np.all(f.mean_p(np.array([8.0, 25.0])) == 1.0)


def test_union_layer_ranks_clean():
    clean = pd.DataFrame({s: np.arange(100.0) for s in O.STATS})
    lay = O.L2bUnion().calibrate(clean, 0.05)
    hi = pd.DataFrame({s: [1000.0] for s in O.STATS})
    assert lay.score(hi)[0].alarm
