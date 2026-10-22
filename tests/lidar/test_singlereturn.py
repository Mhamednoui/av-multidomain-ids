"""WP3 S2b physics tests: a single-return sensor reports at most one return per beam (laser, azimuth), whatever the attack.

Synthetic scene as in test_geometry (flat ground seen by every downward laser, ring table fitted in S2).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.config import RESULTS
from lidar import geometry as G
from lidar import phantom as P
from lidar import singlereturn as S
from lidar.features import ATTACKS, attack_params, raycast_ghost
from lidar.raycast import MODES

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
        if rho > 70 or rho < 3:
            continue
        rxy = np.sqrt(rho ** 2 - GROUND ** 2)
        pts.append(np.c_[rxy * np.cos(az), rxy * np.sin(az), GROUND + rng.normal(0, 0.005, len(az)), rng.uniform(0.05, 0.6, len(az))])
    return np.vstack(pts).astype(np.float32)


PARAMS = {"range": 22.0, "az": 10.0, "rot": 0.7, "budget": 300, "n": 800}


def test_clean_scene_has_no_conflicts():
    assert S.beam_conflicts(scene(), TABLE) == 0


def test_every_v2_attack_keeps_one_return_per_beam():
    pts = scene()
    base = S.beam_conflicts(pts, TABLE)
    for name in ATTACKS:
        rng = np.random.default_rng(3)
        p = attack_params(name, rng)
        att = S.apply_attack(name, pts, p, rng, TABLE)
        assert S.beam_conflicts(att, TABLE) <= base, name


def test_box_cloud_without_fix_does_have_conflicts():
    from lidar.features import apply_attack
    pts = scene()
    rng = np.random.default_rng(3)
    p = attack_params("GhostCluster", rng)
    p.update(range=20.0, n=1500)
    raw = apply_attack("GhostCluster", pts, p, rng)
    fixed = S.enforce_appended(pts, raw, TABLE)
    assert S.beam_conflicts(raw, TABLE) > 20
    assert S.beam_conflicts(fixed, TABLE) == 0
    assert len(fixed) < len(raw), "real returns behind injected points removed"


def test_calibrated_raycast_phantoms_single_return_all_modes():
    pts = scene()
    rays = P.prepare(pts, TABLE)
    for mode in MODES:
        att, n, q, idx = P.phantom(pts, rays, dict(PARAMS), np.random.default_rng(5), mode, None)
        assert n > 30
        assert len(att) == len(pts), mode
        assert S.beam_conflicts(att, TABLE) == 0, mode
        # independent check with the laser ids of the real rays: one return per (laser, azimuth) cell
        k = rays["k"].copy()
        az = np.degrees(np.arctan2(att[:, 1], att[:, 0]))
        order = np.lexsort((az, k))
        close = (k[order][1:] == k[order][:-1]) & (np.abs(np.diff(az[order])) < S.DAZ)
        assert close.sum() == 0, mode


def test_add_equals_replace_since_single_return():
    pts = scene()
    rays = P.prepare(pts, TABLE)
    a = P.phantom(pts, rays, dict(PARAMS), np.random.default_rng(6), "add", None)[0]
    r = P.phantom(pts, rays, dict(PARAMS), np.random.default_rng(6), "replace", None)[0]
    b = P.phantom(pts, rays, dict(PARAMS), np.random.default_rng(6), "budget_add", None)[0]
    br = P.phantom(pts, rays, dict(PARAMS), np.random.default_rng(6), "budget", None)[0]
    assert np.array_equal(a, r) and np.array_equal(b, br)


def test_multi_return_variant_has_conflicts():
    pts = scene()
    rays = P.prepare(pts, TABLE)
    att = P.phantom(pts, rays, dict(PARAMS), np.random.default_rng(5), "add", None, single_return=False)[0]
    assert S.beam_conflicts(att, TABLE) > 30


def test_old_origin_ray_phantoms_single_return():
    pts = scene()
    for mode in MODES:
        att, n = raycast_ghost(pts, dict(PARAMS), np.random.default_rng(7), mode, retry=True)
        fixed = S.enforce_appended(pts, att, TABLE)
        assert n > 30 and S.beam_conflicts(fixed, TABLE) <= S.beam_conflicts(pts, TABLE) + 2, mode


def test_l1_duplicate_rule_no_longer_sees_single_return_add():
    pts = scene()
    rays = P.prepare(pts, TABLE)
    base = G.l1_stats(pts, TABLE)[4]
    multi = P.phantom(pts, rays, dict(PARAMS, range=30.0, az=0.0), np.random.default_rng(5), "add", None, single_return=False)[0]
    single = P.phantom(pts, rays, dict(PARAMS, range=30.0, az=0.0), np.random.default_rng(5), "add", None)[0]
    assert G.l1_stats(multi, TABLE)[4] - base > 20
    assert G.l1_stats(single, TABLE)[4] - base <= 2
