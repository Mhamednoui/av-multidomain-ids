"""WP3 evaluation phantoms: physically consistent ray-cast LiDAR spoofing + physics checks.

A spoofer can only create returns along the sensor's own rays (Cao et al., CCS 2019). A
phantom is a car-sized box (4 x 1.8 x 1.5 m on the ground) at 5-40 m; each real ray that
crosses the box before its real return gets a spoofed return AT THE FIRST SURFACE of the box.
Modes (logic of v2 `raycast_ghost`, imported from lidar.features):
  add          spoofed return added in front of the real one (multi-return sensor)
  replace      real return replaced (single-return sensor; the physics bound)
  budget_add   `add` on at most `budget` (50-400) contiguous rays around the box centre
  budget       `replace` limited the same way
Evaluation parameters (`eval_params`): range stratum "near" (5-15 m, sparse) or "far"
(15-40 m) or "all" (5-40 m), budget 50-400, azimuth/heading random, kept fixed over a
persistent episode (same position relative to the car).
`physics_report` measures the properties that tests/lidar/test_physics.py checks:
occlusion (every spoofed return is the first return along its ray), box-surface membership,
intensity range, point count. Box-cloud phantoms (v2 GhostCluster) are NOT valid evaluation
phantoms; `boxcloud_ghost` is kept only to reproduce v2's number.
"""
import numpy as np

from lidar.features import BOX_HALF, MIN_RAYS, apply_attack, attack_params, boxcloud_ghost, box_hits, raycast_ghost  # noqa

MODES = ("add", "replace", "budget_add", "budget")
RANGE_BANDS = {"near": (5.0, 15.0), "far": (15.0, 40.0), "all": (5.0, 40.0)}
INTENSITY_RANGE = (0.0, 1.0)     # KITTI velodyne reflectivity, normalised


def eval_params(rng, band="all", budget=None):
    """Random phantom placement (position fixed for a persistent episode)."""
    lo, hi = RANGE_BANDS[band]
    return {"range": float(rng.uniform(lo, hi)), "az": float(rng.uniform(-180, 180)),
            "rot": float(rng.uniform(0, np.pi)),
            "budget": int(rng.integers(50, 401)) if budget is None else int(budget),
            "n": 0, "band": band}


def place(pts, p):
    """Phantom parameters actually used: v2's retry shifts the azimuth in 25 deg steps until
    >= MIN_RAYS rays hit the box (identical to raycast_ghost(retry=True))."""
    q = dict(p)
    for _ in range(14):
        if box_hits(pts, q)[0].sum() >= MIN_RAYS:
            break
        q["az"] = (q["az"] + 25.0 + 180.0) % 360.0 - 180.0
    return q


def phantom(pts, p, rng, mode):
    """Attacked scan, number of spoofed returns, parameters used (azimuth after retry)."""
    if mode not in MODES:
        raise ValueError(mode)
    q = place(pts, p)
    att, n = raycast_ghost(pts, q, rng, mode, retry=False)
    return att, n, q


def spoofed_points(before, after, mode):
    """The injected returns of an attacked scan (rows appended or changed)."""
    if mode in ("add", "budget_add"):
        return after[len(before):]
    changed = np.flatnonzero(np.any(before != after, axis=1))
    return after[changed], changed


def point_dirs(xyz):
    r = np.linalg.norm(xyz[:, :3].astype(np.float64), axis=1)
    return xyz[:, :3] / np.maximum(r, 1e-9)[:, None], r


def physics_report(before, after, p, mode, tol=0.05):
    """Physics measurements of one ray-cast attack (before/after = N x 4 arrays).
    first_return_frac: share of spoofed returns nearer than the real return on the same ray
    (add: the real return still exists farther away; replace: it is the removed one);
    on_box_frac: share of spoofed points on the entry face of the box (within tol m);
    intensity_ok: all intensities inside the sensor range."""
    if mode in ("add", "budget_add"):
        new = after[len(before):]
        # the spoofed point i belongs to a real ray: find it by direction (same rays, real return kept)
        dn, rn = point_dirs(new)
        dr, rr = point_dirs(before)
        # match each spoofed point to the real return of the same ray (cosine ~ 1)
        from scipy.spatial import cKDTree
        d, j = cKDTree(dr).query(dn)
        ok_first = (rn < rr[j] - 1e-3) & (d < 1e-4)
        first = float(ok_first.mean()) if len(new) else 1.0
    else:
        idx = np.flatnonzero(np.any(before != after, axis=1))
        new = after[idx]
        dn, rn = point_dirs(new)
        dr, rr = point_dirs(before[idx])
        first = float(((rn < rr - 1e-3) & (np.linalg.norm(dn - dr, axis=1) < 1e-4)).mean()) if len(new) else 1.0
    return {"n_spoofed": int(len(new)), "first_return_frac": first,
            "on_box_frac": box_surface_frac(before, new, p, tol),
            "intensity_ok": bool(len(new) == 0 or (new[:, 3].min() >= INTENSITY_RANGE[0]
                                                    and new[:, 3].max() <= INTENSITY_RANGE[1]))}


def box_surface_frac(pts, new, p, tol=0.05):
    """Share of `new` points lying on the surface of the phantom box (distance to a face <= tol)."""
    if len(new) == 0:
        return 1.0
    ground = np.percentile(pts[:, 2], 5)
    az = np.radians(p["az"])
    c = np.array([p["range"] * np.cos(az), p["range"] * np.sin(az), ground + BOX_HALF[2]])
    cr, sr = np.cos(p["rot"]), np.sin(p["rot"])
    R = np.array([[cr, sr, 0], [-sr, cr, 0], [0, 0, 1]])
    loc = (new[:, :3].astype(np.float64) - c) @ R.T
    inside = np.all(np.abs(loc) <= BOX_HALF + tol, axis=1)
    on_face = np.any(np.abs(np.abs(loc) - BOX_HALF) <= tol, axis=1)
    return float((inside & on_face).mean())


def box_hit_count(pts, p):
    """Number of real rays crossing the box before their real return (the replace-mode point count)."""
    return int(box_hits(pts, p)[0].sum())
