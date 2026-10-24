"""WP3 S3 object segmentation: ground removal, Euclidean clustering and the per-scan object table.

Purpose: turn a scan into a table of objects (the unit of the object-level checks S4-S6).
Inputs: N x 4 scan (x y z intensity), ring table (lidar.geometry). Output: pandas DataFrame, one row per object.
Pipeline (parameters in PARAMS, chosen on validation drives, see notes/WP3_lidar.md S3):
  1 ground: local-grid minimum filter (2 m cells, 5 x 5 minimum filter; lidar.objects.ground_height) or a RANSAC plane
    (points < 25 m, inlier distance 0.12 m, fixed seed) combined with the grid; a point is ground if its height above
    the local ground is below h0; points above `h_max` (overhanging foliage, bridges) and beyond `r_max` are ignored.
  2 clustering: Euclidean connected components of the non-ground points (scipy cKDTree + connected_components), link radius
    eps(r) = e0 + e1 * r growing with the range r of the point (the beam spacing grows linearly with range), min_pts points.
  3 object table: centroid, range, azimuth, oriented box (PCA footprint: length, width, heading; height above ground),
    point count, azimuth span, elevation span, ring coverage (lasers touched from the ring table), mean intensity.
References: Himmelsbach et al. (IROS 2010) ground segmentation; Bogoslavskyi & Stachniss (IROS 2016) range-image clustering;
Rusu (2010) Euclidean cluster extraction. Limits: no labels exist (no tracklets), so merge/split of neighbouring objects
(touching cars, a car next to a wall) is controlled only through the proxies of the acceptance rule.
"""
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from common.config import SEED
from lidar import geometry as G
from lidar import objects as O

PARAMS = {"ground": "grid", "h0": 0.20, "h_max": 3.0, "r_max": 60.0, "e0": 0.6, "e1": 0.01, "min_pts": 5}
COLUMNS = ["cx", "cy", "cz", "range", "az", "length", "width", "heading", "height", "z_bottom", "n_points", "az_span",
           "elev_span", "n_rings", "ring_min", "ring_max", "ring_fill", "int_mean", "int_std", "carlike"]


def ransac_plane(pts, rng, r_fit=25.0, iters=60, tol=0.12):
    """Ground plane z = a x + b y + c from the lowest points within r_fit (RANSAC, near-vertical normal); None if it fails."""
    sel = np.flatnonzero(np.hypot(pts[:, 0], pts[:, 1]) < r_fit)
    if len(sel) < 100:
        return None
    low = sel[pts[sel, 2] < np.percentile(pts[sel, 2], 40)]
    best, best_n = None, 0
    for _ in range(iters):
        tri = pts[rng.choice(low, 3, replace=False), :3].astype(np.float64)
        n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        if abs(n[2]) < 1e-6 or abs(n[2]) / np.linalg.norm(n) < 0.95:
            continue
        coef = np.array([-n[0] / n[2], -n[1] / n[2], 0.0])
        coef[2] = tri[0, 2] - coef[0] * tri[0, 0] - coef[1] * tri[0, 1]
        inl = (np.abs(pts[low, 2] - (coef[0] * pts[low, 0] + coef[1] * pts[low, 1] + coef[2])) < tol).sum()
        if inl > best_n:
            best, best_n = coef, inl
    return best


def height_above_ground(pts, kind="grid"):
    """Height of every point above the estimated local ground (m)."""
    g = O.ground_height(pts)
    h = pts[:, 2] - g
    if kind == "ransac":
        c = ransac_plane(pts, np.random.default_rng(SEED))
        if c is not None:
            plane = c[0] * pts[:, 0] + c[1] * pts[:, 1] + c[2]
            near = np.hypot(pts[:, 0], pts[:, 1]) < 25.0
            h = np.where(near, pts[:, 2] - plane, h)
    return h, g


def eps_of(rng_pts, e0, e1):
    return e0 + e1 * rng_pts


def cluster(xyz, rho, e0, e1, min_pts, shell=10.0, e_near=0.0, r_near=20.0):
    """Connected components with a range-dependent link radius; labels of points in clusters with >= min_pts points, else -1.
    Links: all pairs closer than e0 (any range) plus, inside each 10 m range shell, pairs closer than eps(upper edge of the
    shell) = e0 + e1 * r (the radius grows with range, one tree per shell keeps the pair count small)."""
    n = len(xyz)
    edges = [cKDTree(xyz).query_pairs(e0, output_type="ndarray")]
    if e1 > 0:
        sid = (rho // shell).astype(int)
        for s in np.unique(sid):
            idx = np.flatnonzero(sid == s)
            r = eps_of((s + 1) * shell, e0, e1)
            if len(idx) > 1 and r > e0:
                pr = cKDTree(xyz[idx]).query_pairs(r, output_type="ndarray")
                if len(pr):
                    edges.append(idx[pr])
    pairs = np.vstack(edges)
    if e_near > 0:      # S4: tighter link between two points that are both near (dense returns, avoids merging with structure)
        d = np.linalg.norm(xyz[pairs[:, 0]] - xyz[pairs[:, 1]], axis=1)
        far = np.maximum(rho[pairs[:, 0]], rho[pairs[:, 1]]) >= r_near
        pairs = pairs[far | (d <= e_near)]
    _, lab = connected_components(coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n)), directed=False)
    size = np.bincount(lab)
    return np.where(size[lab] >= min_pts, lab, -1)


def object_row(pts, idx, ground, k):
    p = pts[idx].astype(np.float64)
    c = p[:, :3].mean(0)
    az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
    azc = np.degrees(np.arctan2(c[1], c[0]))
    d_az = (az - azc + 180.0) % 360.0 - 180.0
    elev = np.degrees(np.arctan2(p[:, 2], np.hypot(p[:, 0], p[:, 1])))
    xy = p[:, :2] - p[:, :2].mean(0)
    if len(p) >= 3:
        w, v = np.linalg.eigh(np.cov(xy.T))
        q = xy @ v
        ext = np.ptp(q, axis=0)
        major = v[:, 1]
        length, width = float(ext[1]), float(ext[0])
        heading = float(np.degrees(np.arctan2(major[1], major[0])) % 180.0)
    else:
        length = width = heading = 0.0
    gmin = float(ground[idx].min())
    rings = k[idx]
    height = float(p[:, 2].max() - gmin)
    zb = float(p[:, 2].min() - gmin)
    rng_c = float(np.hypot(c[0], c[1]))
    car = (O.CAR["h"][0] <= height <= O.CAR["h"][1] and O.CAR["long"][0] <= length <= O.CAR["long"][1]
           and width <= O.CAR["short_max"] and zb <= O.CAR["bottom_max"] and len(p) >= O.CAR["n_min"]
           and O.CAR["range"][0] <= rng_c <= O.CAR["range"][1])
    return [c[0], c[1], c[2], rng_c, azc, length, width, heading, height, zb, len(p), float(np.ptp(d_az)),
            float(np.ptp(elev)), int(len(np.unique(rings))), int(rings.min()), int(rings.max()),
            float(len(np.unique(rings)) / (rings.max() - rings.min() + 1)), float(p[:, 3].mean()), float(p[:, 3].std()), bool(car)]


def segment(pts, table, params=None, return_labels=False):
    """Object table of one scan (DataFrame with COLUMNS). With return_labels: also the labels array (len(pts), -1 = none)."""
    prm = dict(PARAMS, **(params or {}))
    h, ground = height_above_ground(pts, prm["ground"])
    rho_xy = np.hypot(pts[:, 0], pts[:, 1])
    sel = np.flatnonzero((h > prm["h0"]) & (h < prm["h_max"]) & (rho_xy < prm["r_max"]))
    labels = np.full(len(pts), -1)
    if len(sel) < prm["min_pts"]:
        out = pd.DataFrame(columns=COLUMNS)
        return (out, labels, h) if return_labels else out
    lab = cluster(pts[sel, :3].astype(np.float64), rho_xy[sel], prm["e0"], prm["e1"], prm["min_pts"],
                  e_near=prm.get("e_near", 0.0), r_near=prm.get("r_near", 20.0))
    keep = lab >= 0
    sel, lab = sel[keep], lab[keep]
    asg = table.assign(pts)
    order = np.argsort(lab, kind="stable")
    ls = lab[order]
    starts = np.r_[0, np.flatnonzero(np.diff(ls)) + 1, len(ls)]
    rows = []
    for oid, (a, b) in enumerate(zip(starts[:-1], starts[1:])):
        idx = sel[order[a:b]]
        labels[idx] = oid
        rows.append(object_row(pts, idx, ground, asg["k"]))
    out = pd.DataFrame(rows, columns=COLUMNS)
    return (out, labels, h) if return_labels else out
