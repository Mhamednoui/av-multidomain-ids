"""Physics-consistency tests of the WP3 attack generator (S1).

Synthetic ideal scene: HDL-64E-like 64 rings, 0.18 deg azimuth step (KITTI 10 Hz), flat ground at
z = -1.73 m, returns up to 120 m. One real KITTI scan test is skipped if the data is missing.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lidar import data
from lidar.features import apply_attack, attack_params, boxcloud_ghost
from lidar.raycast import MODES, box_surface_frac, INTENSITY_RANGE, box_hit_count, eval_params, phantom, physics_report


class Skip(Exception):
    pass


ELEV = np.r_[np.linspace(2.0, -8.33, 32), np.linspace(-8.87, -24.33, 32)]


def scene(seed=0, h=1.73, rmax=120.0):
    rng = np.random.default_rng(seed)
    az = np.radians(np.arange(-180, 180, 0.18))
    el = np.radians(ELEV)
    A, E = np.meshgrid(az, el)
    A, E = A.ravel(), E.ravel()
    down = E < 0
    r = np.minimum(h / np.tan(-E[down]) / np.cos(E[down]) * np.cos(E[down]), rmax)   # horizontal range
    A, E = A[down], E[down]
    x, y, z = r * np.cos(A), r * np.sin(A), -h * np.ones(len(r))
    z = np.where(r >= rmax, -h + r * np.tan(E), z)
    return np.c_[x, y, z, rng.uniform(0.05, 0.6, len(r))].astype(np.float32)


def test_ideal_scene_is_valid():
    pts = scene()
    assert len(pts) > 40000 and np.isfinite(pts).all()
    assert abs(np.percentile(pts[:, 2], 5) + 1.73) < 0.3


def test_point_count_range_law():
    pts = scene()
    rots = np.linspace(0, np.pi, 8, endpoint=False)
    mean = {}
    for r in (10, 15, 20, 30, 40):
        mean[r] = np.mean([box_hit_count(pts, {"range": r, "az": a, "rot": t})
                           for a in (0.0, 90.0, -135.0) for t in rots])
    assert 150 <= mean[30] <= 450, mean            # a real car at 30 m: ~270 returns
    slope = np.polyfit(np.log(list(mean)), np.log(list(mean.values())), 1)[0]
    assert -2.6 <= slope <= -1.5, (slope, mean)    # ~ 1/r^2
    assert mean[10] > 5 * mean[30]


def _check(mode, seed=1, band="all", pts=None):
    rng = np.random.default_rng(seed)
    pts = scene() if pts is None else pts
    p = eval_params(rng, band)
    att, n, q = phantom(pts, p, rng, mode)
    return pts, att, n, q


def test_phantom_is_first_return_and_on_box_surface():
    for mode in MODES:
        for seed in range(4):
            pts, att, n, q = _check(mode, seed)
            rep = physics_report(pts, att, q, mode)
            assert rep["n_spoofed"] == n and n >= 30, (mode, rep)
            assert rep["first_return_frac"] == 1.0, (mode, rep)   # nothing behind a closer return
            assert rep["on_box_frac"] >= 0.99, (mode, rep)
            assert rep["intensity_ok"]


def test_add_keeps_real_returns_replace_removes_them():
    pts, att, n, _ = _check("add")
    assert len(att) == len(pts) + n and np.array_equal(att[:len(pts)], pts)
    pts, att, n, _ = _check("replace")
    assert len(att) == len(pts) and int(np.any(att != pts, axis=1).sum()) == n


def test_budget_limits_points_and_is_contiguous():
    rng = np.random.default_rng(5)
    pts = scene()
    p = eval_params(rng, "far", budget=60)
    att, n, q = phantom(pts, p, rng, "budget_add")
    assert 30 <= n <= 60
    new = att[len(pts):]
    az = np.degrees(np.arctan2(new[:, 1], new[:, 0]))
    cen = q["az"]
    off = np.abs((az - cen + 180) % 360 - 180)
    nf = box_hit_count(pts, q)
    assert nf >= n and off.max() <= 25.0         # concentrated around the box centre, not scattered


def test_intensity_inside_sensor_range():
    for mode in MODES:
        pts, att, n, q = _check(mode, 3)
        new = att[len(pts):] if mode.endswith("add") or mode == "add" else att[np.any(att != pts, axis=1)]
        assert new[:, 3].min() >= INTENSITY_RANGE[0] and new[:, 3].max() <= INTENSITY_RANGE[1]


def test_boxcloud_ghost_fails_the_surface_check():
    """The v2 box-cloud phantom fills the volume: the physics check must reject it."""
    rng = np.random.default_rng(2)
    pts = scene()
    p = attack_params("GhostCluster", rng)
    p["n"] = 800
    att = boxcloud_ghost(pts, p, rng)
    q = dict(p)
    assert box_surface_frac(pts, att[len(pts):], q) < 0.4


def test_point_drop_removes_only_a_sector():
    rng = np.random.default_rng(4)
    pts = scene()
    p = {"c": 30.0, "w": 40.0, "frac": 1.0}
    out = apply_attack("PointDrop", pts, p, rng)
    keep_set = {tuple(r) for r in out}
    gone = np.array([tuple(r) not in keep_set for r in pts])
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    inside = (np.abs((az - 30.0 + 180) % 360 - 180) <= 20.0) & (np.hypot(pts[:, 0], pts[:, 1]) <= 60.0)
    assert np.array_equal(gone, inside)            # frac 1: the whole sector (<= 60 m) is blind, nothing else
    assert len(out) == len(pts) - inside.sum()
    p["frac"] = 0.5
    out = apply_attack("PointDrop", pts, p, rng)
    dropped = 1 - (len(out) - (~inside).sum()) / inside.sum()
    assert 0.4 < dropped < 0.6                      # frac 0.5: about half of the sector's points
    assert len(out) >= (~inside).sum()             # partial: outside points all kept


def test_intensity_spoof_changes_only_intensity():
    rng = np.random.default_rng(6)
    pts = scene()
    p = {"c": -60.0, "w": 30.0}
    out = apply_attack("IntensitySpoof", pts, p, rng)
    assert out.shape == pts.shape and np.array_equal(out[:, :3], pts[:, :3])
    ch = out[:, 3] != pts[:, 3]
    assert ch.sum() > 100
    assert out[ch, 3].min() >= 0.8 and out[ch, 3].max() <= 1.0
    az = np.degrees(np.arctan2(pts[ch, 1], pts[ch, 0]))
    assert (np.abs((az + 60.0 + 180) % 360 - 180) <= 15.0).all() and (np.hypot(pts[ch, 0], pts[ch, 1]) <= 40).all()


def test_split_is_by_drive_and_groups_are_unique():
    t = data.split_table()
    assert sorted(sum((v["drives"] for v in t.values()), [])) == data.DRIVES and len(data.DRIVES) == 23
    assert t["test"]["drives"] == ["0001", "0005", "0028", "0039", "0052", "0079", "0095"]
    assert t["val"]["drives"] == ["0011", "0027", "0035"]
    groups = sum((v["groups"] for v in t.values()), [])
    assert len(groups) == len(set(groups)) and all("/" in g and g.endswith(".bin") for g in groups)
    assert {g.split("/")[0] for g in t["test"]["groups"]}.isdisjoint({g.split("/")[0] for g in t["train"]["groups"]})


def test_real_scan_phantom_is_occluding():
    f = data.scan_files("0005")
    if not f:
        raise Skip("KITTI data missing")
    pts = data.load(f[10])
    for mode in ("add", "budget_add", "replace"):
        rng = np.random.default_rng(8)
        p = eval_params(rng, "near")
        att, n, q = phantom(pts, p, rng, mode)
        rep = physics_report(pts, att, q, mode)
        assert rep["first_return_frac"] == 1.0 and rep["on_box_frac"] >= 0.99 and rep["intensity_ok"], rep
        if n:
            assert rep["n_spoofed"] == n
