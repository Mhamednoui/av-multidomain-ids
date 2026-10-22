"""WP3 S3 tests: segmentation, object table, ego-motion association (synthetic scenes from the S2 ring table)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.config import RESULTS
from lidar import assoc, ego
from lidar import geometry as G
from lidar import phantom as P
from lidar import segment as S

TABLE = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
GROUND = -1.73


def scene(seed=0):
    rng = np.random.default_rng(seed)
    az = np.radians(np.arange(-180, 180, 0.18))
    pts = []
    for k in range(64):
        if TABLE.s[k] >= -0.01:
            continue
        rho = (GROUND - TABLE.v[k]) / TABLE.s[k]
        if rho > 55 or rho < 3:
            continue
        rxy = np.sqrt(rho ** 2 - GROUND ** 2)
        pts.append(np.c_[rxy * np.cos(az), rxy * np.sin(az), GROUND + rng.normal(0, 0.005, len(az)), rng.uniform(0.05, 0.6, len(az))])
    return np.vstack(pts).astype(np.float32)


def with_box(pts, rng_m, az_deg, seed):
    rays = P.prepare(pts, TABLE)
    p = {"range": rng_m, "az": az_deg, "rot": 0.3, "budget": 400}
    att, n, q, idx = P.phantom(pts, rays, p, np.random.default_rng(seed), "replace", None)
    return att, idx, P.box_pose(pts, q)[0]


def test_flat_ground_has_no_objects():
    assert len(S.segment(scene(), TABLE)) == 0


def test_one_box_is_one_object_with_the_right_geometry():
    att, idx, c = with_box(scene(), 18.0, 20.0, 1)
    tab, lab, _ = S.segment(att, TABLE, return_labels=True)
    pl = lab[idx]
    main = np.bincount(pl[pl >= 0]).argmax()
    assert (pl == main).mean() > 0.9
    o = tab.iloc[main]
    assert np.hypot(o.cx - c[0], o.cy - c[1]) < 2.5, "centroid of the visible faces is within half a car length of the box centre"
    assert 0.9 < o.height < 1.8 and 1.5 < o.length < 5.0 and o.n_points >= 30
    assert o.n_rings >= 3 and o.az_span > 1.0 and 0.0 <= o.int_mean <= 1.0
    assert set(S.COLUMNS) <= set(tab.columns)


def test_two_separate_boxes_are_two_objects():
    pts = scene()
    a, ia, _ = with_box(pts, 15.0, 20.0, 2)
    b, ib, _ = with_box(a, 25.0, -100.0, 3)
    tab = S.segment(b, TABLE)
    assert len(tab) == 2


def test_far_object_survives_radius_clustering():
    att, idx, c = with_box(scene(), 38.0, 60.0, 4)
    tab = S.segment(att, TABLE)
    assert len(tab) >= 1 and (np.hypot(tab.cx - c[0], tab.cy - c[1]) < 2.0).any()


def test_ego_roundtrip_and_motion():
    pa, pb = np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])
    xy = np.array([[10.0, 2.0]])
    assert np.allclose(ego.from_world(ego.to_world(xy, pa), pa), xy)
    assert np.allclose(ego.between(xy, pa, pb), [[9.0, 2.0]]), "car moved 1 m east (heading 0): the point is 1 m closer"
    pc = np.array([0.0, 0.0, np.pi / 2])
    assert np.allclose(ego.between(np.array([[5.0, 0.0]]), pa, pc), ego.from_world(ego.to_world(np.array([[5.0, 0.0]]), pa), pc))


def test_association_after_ego_motion():
    import pandas as pd
    a = pd.DataFrame({"cx": [10.0, 20.0, 30.0], "cy": [0.0, 5.0, -5.0], "range": [10.0, 20.6, 30.4], "n_points": [100, 50, 20]})
    pa, pb = np.array([0.0, 0.0, 0.0]), np.array([1.0, 0.0, 0.0])
    b = pd.DataFrame({"cx": [9.0, 19.0, 29.0, 40.0], "cy": [0.0, 5.0, -5.0, 0.0], "range": [9.0, 19.6, 29.4, 40.0], "n_points": [90, 60, 18, 10]})
    cand, jj, dist, ratio = assoc.match(a, pa, b, pb, 1.0, 0, 60)
    assert list(jj) == [0, 1, 2] and np.nanmax(dist) < 1e-6 and np.allclose(ratio, [0.9, 1.2, 0.9])
    cand, jj, _, _ = assoc.match(a, pa, b, np.array([0.0, 0.0, 0.0]), 0.5, 0, 60)
    assert (jj == -1).sum() >= 2, "without ego-motion compensation the objects do not match"
