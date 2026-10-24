"""Tests of the S6 background model (lidar.background) and the world-fixed episode geometry."""
import numpy as np

from common.config import RESULTS
from lidar import background as B
from lidar import background_build as BB
from lidar.geometry import RingTable

TABLE = RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
EDGES = B.ring_edges(TABLE)


def cylinder(r=15.0, step=0.5, drop=None):
    el = np.radians(np.sort(TABLE.elevation_deg()))
    az = np.radians(np.arange(-180, 180, step))
    A, E = np.meshgrid(az, el)
    pts = np.c_[r * np.cos(A).ravel(), r * np.sin(A).ravel(), (r * np.tan(E)).ravel(), np.full(A.size, 0.5)].astype(np.float32)
    if drop is not None:
        a = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
        pts = pts[~((a > drop[0]) & (a < drop[1]))]
    return pts


def test_ring_edges_count():
    assert len(EDGES) == 63


def test_identical_scans_no_miss():
    s = cylinder()
    m = B.miss_stats(B.Img(s, EDGES), B.Img(s, EDGES))
    assert m["miss_w10"] < 1e-9 and m["miss_tot"] == 0.0


def test_removed_sector_is_missing():
    s = cylinder()
    m = B.miss_stats(B.Img(cylinder(drop=(20, 50)), EDGES), B.Img(s, EDGES))
    assert m["miss_w10"] > 0.9 and m["miss_z20"] > 10


def test_random_half_drop_detected():
    s = cylinder()
    a = np.degrees(np.arctan2(s[:, 1], s[:, 0]))
    rng = np.random.default_rng(0)
    cut = s[~((a > 0) & (a < 40) & (rng.random(len(s)) < 0.6))]
    m = B.miss_stats(B.Img(cut, EDGES), B.Img(s, EDGES))
    assert m["miss_w10"] > 0.4


def test_moved_identity_and_window_sums():
    s = cylinder()
    p = np.array([3.0, 4.0, 0.7])
    assert np.allclose(B.moved(s, p, p)[:, :2], s[:, :2], atol=1e-4)
    c = np.ones((2, B.NAZ))
    assert np.allclose(B.window_sums(c, 10), 10)


def test_world_params_stationary_and_translation():
    q = {"range": 20.0, "az": 10.0, "rot": 0.5}
    p0 = np.array([0.0, 0.0, 0.0])
    r = BB.world_params(q, p0, p0)
    assert abs(r["range"] - 20.0) < 1e-6 and abs(r["az"] - 10.0) < 1e-6 and abs(r["rot"] - 0.5) < 1e-6
    r2 = BB.world_params({"range": 20.0, "az": 0.0, "rot": 0.0}, p0, np.array([5.0, 0.0, 0.0]))
    assert abs(r2["range"] - 15.0) < 0.2   # car drove 5 m towards a point straight ahead (small IMU-velodyne offset)
