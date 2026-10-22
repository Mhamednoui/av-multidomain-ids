"""WP3 S2 tests: ring geometry (L1), calibrated ray-cast phantoms, calibration statistics.

Synthetic scene built from the fitted ring table (results/WP3/S2/ring_table.json): flat ground at z = -1.73 m seen by
every laser with negative elevation, 0.18 deg azimuth step, 5 mm height noise. Real-scan checks are skipped if the data is missing.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import geometry as G
from lidar import objects as O
from lidar import phantom as P
from lidar.features import raycast_ghost

TABLE = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
GROUND = -1.73


def ground_scene(seed=0, rho_max=70.0, noise=0.005):
    rng = np.random.default_rng(seed)
    az = np.radians(np.arange(-180, 180, 0.18))
    pts = []
    for k in range(64):
        if TABLE.s[k] >= -0.01:
            continue
        rho = (GROUND - TABLE.v[k]) / TABLE.s[k]
        if rho > rho_max or rho < 3:
            continue
        rxy = np.sqrt(rho ** 2 - GROUND ** 2)
        z = GROUND + rng.normal(0, noise, len(az))
        pts.append(np.c_[rxy * np.cos(az), rxy * np.sin(az), z, rng.uniform(0.05, 0.6, len(az))])
    return np.vstack(pts).astype(np.float32)


def base_off(pts):
    return G.l1_stats(pts, TABLE)[0]


def test_ring_table_matches_spec():
    el = TABLE.elevation_deg()
    assert len(el) == 64 and np.all(np.diff(el) < 0.05), "elevations decrease from the top laser"
    assert abs(el[0] - G.SPEC["elev_max"]) < 0.3 and abs(el[-1] - G.SPEC["elev_min"]) < 0.4
    assert 0.05 < TABLE.v.min() and TABLE.v.max() < 0.35, "laser vertical offsets are decimetres"


def test_clean_synthetic_scene_has_no_l1_alarm_statistics():
    pts = ground_scene()
    st = dict(zip(G.STAT_NAMES, G.l1_stats(pts, TABLE)))
    assert st["n_off_ring"] < 0.002 * len(pts), st
    assert st["n_range"] == 0 and st["n_intensity"] == 0 and st["n_dup"] == 0, st


def test_box_cloud_is_off_ring():
    pts = ground_scene()
    rng = np.random.default_rng(1)
    n = 600
    az = np.radians(30.0)
    box = np.c_[28 * np.cos(az) + rng.uniform(-2, 2, n), 28 * np.sin(az) + rng.uniform(-0.9, 0.9, n),
                GROUND + rng.uniform(0, 1.5, n), rng.uniform(0.1, 0.5, n)].astype(np.float32)
    clean = G.l1_stats(pts, TABLE)
    att = G.l1_stats(np.vstack([pts, box]), TABLE)
    assert att[0] - clean[0] > 0.2 * n, (clean, att)   # expected 1 - 2 tau / spacing, ~0.35 at 28 m
    assert att[1] > 3 * max(clean[1], 20)


def test_common_mode_removed():
    pts = ground_scene()
    shifted = pts.copy()
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    shifted[az > 0, 2] += 0.03       # pitch / heave step during the sweep
    shifted[az <= 0, 2] -= 0.03
    st = G.l1_stats(shifted, TABLE)
    assert st[0] < 0.01 * len(pts), st


def test_range_and_intensity_limits():
    pts = ground_scene()
    bad = pts[:10].copy()
    bad[:, :3] *= 3.0
    bad[:5, 3] = 1.4
    bad[5:, 3] = -0.1
    st = G.l1_stats(np.vstack([pts, bad]), TABLE)
    assert st[3] == 10 and st[2] >= 1


def test_phantom_points_lie_on_their_ring():
    pts = ground_scene()
    rays = P.prepare(pts, TABLE)
    rng = np.random.default_rng(2)
    p = {"range": 22.0, "az": 10.0, "rot": 0.7, "budget": 400}
    att, n, q, idx = P.phantom(pts, rays, p, rng, "add", None, single_return=False)
    assert n >= 60
    a = TABLE.assign(att)
    res_new = a["res"][len(pts):]
    assert np.abs(res_new).max() < 0.02, np.abs(res_new).max()
    assert (a["k"][len(pts):] == rays["k"][idx]).mean() > 0.9, "same laser as the real ray"


def test_old_origin_rays_leave_the_ring_but_new_rays_do_not():
    pts = ground_scene()
    rng = np.random.default_rng(3)
    p = {"range": 15.0, "az": 10.0, "rot": 0.3, "budget": 400, "n": 0}
    old, n_old = raycast_ghost(pts, p, rng, "add", retry=False)
    rays = P.prepare(pts, TABLE)
    new, n_new, _, _ = P.phantom(pts, rays, p, rng, "add", None, single_return=False)
    k_old, r_old = TABLE.nearest(old[len(pts):], None)
    k_new, r_new = TABLE.nearest(new[len(pts):], None)
    assert n_old > 30 and n_new > 30
    assert np.abs(r_old).max() > 2 * np.abs(r_new).max() + 0.01, (np.abs(r_old).max(), np.abs(r_new).max())


def test_phantom_first_return_and_modes():
    pts = ground_scene()
    rays = P.prepare(pts, TABLE)
    rng = np.random.default_rng(4)
    p = {"range": 25.0, "az": -40.0, "rot": 1.1, "budget": 120}
    n_add = P.phantom(pts, rays, p, rng, "add", None, single_return=False)[1]
    att, n_rep, q, idx = P.phantom(pts, rays, p, rng, "replace", None)
    assert n_add == n_rep and len(att) == len(pts)
    assert (np.linalg.norm(att[idx, :3], axis=1) < np.linalg.norm(pts[idx, :3], axis=1)).all(), "nearer than the real return"
    att_b, n_b, _, _ = P.phantom(pts, rays, p, rng, "budget_add", None, single_return=False)
    assert n_b == min(120, n_add) and len(att_b) == len(pts) + n_b


def test_add_mode_creates_duplicates_replace_does_not():
    pts = ground_scene()
    rays = P.prepare(pts, TABLE)
    rng = np.random.default_rng(5)
    p = {"range": 30.0, "az": 0.0, "rot": 0.4, "budget": 400}
    base = G.l1_stats(pts, TABLE)
    add, n, _, _ = P.phantom(pts, rays, p, rng, "add", None, single_return=False)
    rep, n2, _, _ = P.phantom(pts, rays, p, rng, "replace", None)
    s_add, s_rep = G.l1_stats(add, TABLE), G.l1_stats(rep, TABLE)
    assert s_add[4] - base[4] > 0.5 * n, (s_add, base, n)
    assert s_rep[4] - base[4] <= 0.02 * n + 2, (s_rep, base, n)
    assert s_rep[0] <= base[0] + 0.02 * n + 5, "a replaced return is a legal single-return scan: on its ring"


def test_calibration_thinning_and_intensity():
    lib = [[np.full(50, 0.3, np.float32)], [np.full(50, 0.7, np.float32)]]
    cal = P.Calib([5.0, 20.0, 45.0], [0.5, 0.8], np.inf, lib)
    assert abs(cal.mean_p(12.5) - 0.5) < 1e-9 and abs(cal.mean_p(32.5) - 0.8) < 1e-9
    rng = np.random.default_rng(0)
    assert np.all(cal.draw_intensity(10.0, 20, rng) == 0.3) and np.all(cal.draw_intensity(40.0, 20, rng) == 0.7)
    cb = P.Calib([5.0, 20.0, 45.0], [0.5, 0.5], 8.0, lib)
    pis = np.array([cb.draw_pi(12.0, rng) for _ in range(4000)])
    assert abs(pis.mean() - 0.5) < 0.02 and 0.01 < pis.var() < 0.1
    pts = ground_scene()
    rays = P.prepare(pts, TABLE)
    p = {"range": 20.0, "az": 5.0, "rot": 0.5, "budget": 10 ** 6}
    full = P.phantom(pts, rays, p, np.random.default_rng(1), "add", None, single_return=False)[1]
    cal2 = P.Calib([5.0, 20.0, 45.0], [0.6, 0.6], np.inf, lib)
    kept = np.mean([P.phantom(pts, rays, p, np.random.default_rng(s), "add", cal2, single_return=False)[1] for s in range(20)])
    assert abs(kept / full - 0.6) < 0.06, kept / full
    a1 = P.phantom(pts, rays, p, np.random.default_rng(9), "add", cal2, single_return=False)[0]
    a2 = P.phantom(pts, rays, p, np.random.default_rng(9), "add", cal2, single_return=False)[0]
    assert np.array_equal(a1, a2), "seeded generator is deterministic"


def test_calibration_roundtrip():
    lib = [[np.arange(5, dtype=np.float32) / 10, np.ones(3, np.float32)], [np.zeros(2, np.float32)]]
    cal = P.Calib([5.0, 20.0, 45.0], [0.5, 0.8], 7.5, lib)
    with tempfile.TemporaryDirectory() as d:
        C.save_calib(cal, Path(d) / "c.npz")
        c2 = C.load_calib(Path(d) / "c.npz")
    assert np.allclose(c2.p, cal.p) and c2.kappa == 7.5
    assert [len(b) for b in c2.library] == [2, 1] and np.allclose(c2.library[0][0], lib[0][0])


def test_ks_compare_detects_difference():
    rng = np.random.default_rng(0)
    mk = lambda mu: [{"range": 20.0, "q": float(x), "n": 100, "int": rng.uniform(0, 1, 30)} for x in rng.normal(mu, 0.1, 200)]
    same = C.compare(mk(0.5), mk(0.5), edges=np.array([10.0, 30.0]))[0]
    diff = C.compare(mk(0.5), mk(0.8), edges=np.array([10.0, 30.0]))[0]
    assert same["D_q"] < 0.2 < diff["D_q"]


def test_cluster_extraction_finds_a_synthetic_car():
    pts = ground_scene()
    rng = np.random.default_rng(6)
    n = 400
    car = np.c_[20 + rng.uniform(-2, 2, n), 5 + rng.uniform(-0.9, 0.9, n), GROUND + rng.uniform(0.1, 1.5, n), rng.uniform(0.1, 0.5, n)]
    cl = O.clusters(np.vstack([pts, car]).astype(np.float32), TABLE)
    assert any(abs(c["range"] - np.hypot(20, 5)) < 1.5 and 300 <= c["n"] <= 420 for c in cl), [c["range"] for c in cl]


def test_real_scan_ring_residuals():
    try:
        from lidar.data import load, scan_files
        pts = load(scan_files("0011")[30])
    except Exception:
        return
    a = TABLE.assign(pts)
    m = (a["rho"] >= 8) & (a["rho"] <= 80)
    assert np.mean(np.abs(a["res"][m]) > G.TAU_Z) < 0.01
    assert np.quantile(np.abs(a["res"][m]), 0.99) < 0.08
