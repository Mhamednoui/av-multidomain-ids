"""Tests for gps/map_match.py: class filter, one-way handling, distance/heading on a synthetic road, Layer contract."""
import numpy as np
import pandas as pd

from gps import map_match as MM


def road(oneway=0):
    # east-west road along y=0 from x=-100 to 100 (bearing 90 deg), plus a north-south two-way road at x=50
    A = np.array([[-100.0, 0.0], [50.0, -100.0]])
    B = np.array([[100.0, 0.0], [50.0, 100.0]])
    return MM.RoadMap(A, B, np.array([oneway, 0]))


def test_drivable_class_filter():
    c = MM.DRIVABLE_CLASSES
    assert "residential" in c and "primary_link" in c and "service" in c
    for bad in ("footway", "path", "cycleway", "steps", "pedestrian", "track", "service_link"):
        assert bad not in c


def test_oneway_tags():
    assert MM.oneway_sign({"oneway": "yes"}) == 1 and MM.oneway_sign({"oneway": "-1"}) == -1
    assert MM.oneway_sign({"junction": "roundabout"}) == 1 and MM.oneway_sign({}) == 0


def test_distance_exact_and_heading():
    r = road()
    xy = np.array([[0.0, 7.0], [-20.0, -3.0]])
    dist, head = r.query(xy, np.array([90.0, 270.0]), np.array([10.0, 10.0]))
    assert np.allclose(dist, [7.0, 3.0], atol=1e-6)
    assert np.allclose(head, [0.0, 0.0], atol=1e-6)               # two-way: both directions fine
    _, head2 = r.query(xy[:1], np.array([30.0]), np.array([10.0]))
    assert abs(head2[0] - 60.0) < 1e-6


def test_oneway_wrong_way_and_low_speed():
    r = road(oneway=1)
    xy = np.array([[0.0, 1.0], [0.0, 1.0]])
    _, head = r.query(xy, np.array([270.0, 270.0]), np.array([10.0, 1.0]))
    assert abs(head[0] - 180.0) < 1e-6                             # against the one-way direction
    assert head[1] == 0.0                                          # too slow: course undefined
    r2 = road(oneway=-1)
    _, h = r2.query(xy[:1], np.array([270.0]), np.array([10.0]))
    assert abs(h[0]) < 1e-6


def test_best_candidate_near_junction():
    r = road(oneway=1)
    # near the crossing (50,0): heading north matches the N-S road even though the E-W one-way road is as close
    _, h = r.query(np.array([[50.0, 1.0]]), np.array([0.0]), np.array([10.0]))
    assert h[0] < 1e-6


def test_stream_features_and_layer():
    r = road()
    xy = np.array([[0.0, 2.0], [0.0, 60.0]])
    lat = MM.LAT0 + xy[:, 1] / MM.M_PER_DEG
    lon = MM.LON0 + xy[:, 0] / (MM.M_PER_DEG * np.cos(np.radians(MM.LAT0)))
    df = pd.DataFrame({"lat": lat, "lon": lon, "course": [90.0, 90.0], "odo_speed": [10.0, 10.0]})
    f = MM.stream_features(df, r)
    assert abs(f["map_dist"].iloc[0] - 2.0) < 1e-3 and f["map_dist"].iloc[1] > 40
    lay = MM.MapLayer("map_dist")
    assert lay.layer_id == "L2e" and np.allclose(lay.raw_scores(f), f["map_dist"])
