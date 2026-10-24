"""Tests of the S6 cell-level tracker (lidar.track)."""
import numpy as np

from common.config import RESULTS
from lidar import background as B
from lidar import track as T
from lidar.geometry import RingTable

TABLE = RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
EDGES = B.ring_edges(TABLE)


def wall(r, a0=-180, a1=180, step=0.5):
    el = np.radians(np.sort(TABLE.elevation_deg()))
    az = np.radians(np.arange(a0, a1, step))
    A, E = np.meshgrid(az, el)
    return np.c_[r * np.cos(A).ravel(), r * np.sin(A).ravel(), (r * np.tan(E)).ravel(), np.full(A.size, 0.5)].astype(np.float32)


def stats(cur, pred, raw):
    return T.track_stats(B.Img(cur, EDGES), B.Img(pred, EDGES), B.Img(raw, EDGES))


def test_static_scene_is_explained():
    s = wall(15.0)
    r = stats(s, s, s)
    assert r["app_tot"] == 0 and r["fix_tot"] == 0 and r["van_tot"] == 0


def test_new_surface_in_free_space_is_flagged():
    far = wall(30.0)
    near = np.vstack([wall(30.0), wall(12.0, 20, 40)])
    cur = near[np.argsort(np.hypot(near[:, 0], near[:, 1]))][:0]
    cur = np.vstack([far[~((np.degrees(np.arctan2(far[:, 1], far[:, 0])) > 20) & (np.degrees(np.arctan2(far[:, 1], far[:, 0])) < 40))],
                     wall(12.0, 20, 40)])
    r = stats(cur, far, far)
    assert r["app_tot"] > 100 and r["app_cc"] > 50


def test_occluder_edge_not_new_when_prediction_has_nearer_surface():
    pred = np.vstack([wall(12.0, 20, 40), wall(30.0)])
    r = stats(wall(12.0, 20, 40), pred, pred)
    assert r["app_tot"] == 0


def test_sensor_fixed_surface_counted():
    pred = wall(30.0)                                   # static world prediction says far wall
    cur = wall(12.0, 20, 40)                            # a surface that sits at 12 m in the car frame ...
    raw = wall(12.0, 20, 40)                            # ... and also was at 12 m before: it follows the car
    r = stats(cur, pred, raw)
    assert r["fix_tot"] > 100


def test_vanished_surface_counted():
    pred = wall(12.0, 20, 40)
    r = stats(wall(30.0), pred, pred)
    assert r["van_tot"] > 100
