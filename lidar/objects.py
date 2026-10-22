"""WP3 S2 real-object table from unlabelled KITTI scans: car-like clusters (no tracklets are available).

Purpose: measure how many returns a real car-sized object gets at a given range, to calibrate the attack generator.
Inputs: N x 4 scan, ring table. Output: list of dict per car-like cluster (range, azimuth, size, point count, sensor
cells covered, occupancy q = points / cells, intensities).
Method: local ground = 5 x 5 minimum filter (2 m cells) of the cell minimum height; non-ground = 0.3-2.5 m above it;
connected components with a 0.6 m link (scipy cKDTree); car-like = 1.1-2.0 m tall, longest footprint side 1.4-5.2 m
(PCA), shortest <= 2.4 m, bottom within 0.7 m of the ground, >= 15 points, 6-45 m. Limits: clusters of two touching
cars, bushes and vans pass or fail by shape only; a cluster whose neighbour is merged is dropped by the length rule,
which biases the table towards isolated objects. The same statistic is computed on generator phantoms.
"""
import numpy as np
from scipy.ndimage import minimum_filter
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from lidar import geometry as G

CELL = 2.0
LINK = 0.6
CAR = {"h": (1.1, 2.0), "long": (1.4, 5.2), "short_max": 2.4, "bottom_max": 0.7, "n_min": 15, "range": (6.0, 45.0)}


def ground_height(pts, extent=60.0):
    """Local ground height of each point from a minimum filter over 2 m cells."""
    n = int(2 * extent / CELL)
    ix = np.clip(((pts[:, 0] + extent) / CELL).astype(int), 0, n - 1)
    iy = np.clip(((pts[:, 1] + extent) / CELL).astype(int), 0, n - 1)
    grid = np.full((n, n), np.inf)
    np.minimum.at(grid, (ix, iy), pts[:, 2])
    fill = np.nanmedian(grid[np.isfinite(grid)]) if np.isfinite(grid).any() else -1.7
    grid[~np.isfinite(grid)] = fill + 5.0       # empty cell must not look like ground
    g = minimum_filter(grid, size=5, mode="nearest")
    return g[ix, iy]


def clusters(pts, table, asg=None):
    """Car-like clusters of one scan (list of dict)."""
    ground = ground_height(pts)
    h = pts[:, 2] - ground
    rho_xy = np.hypot(pts[:, 0], pts[:, 1])
    sel = np.flatnonzero((h > 0.3) & (h < 2.5) & (rho_xy < 50.0))
    if len(sel) < CAR["n_min"]:
        return []
    xyz = pts[sel, :3].astype(np.float64)
    tree = cKDTree(xyz)
    pairs = tree.query_pairs(LINK, output_type="ndarray")
    adj = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(sel), len(sel)))
    _, lab = connected_components(adj, directed=False)
    asg = table.assign(pts) if asg is None else asg
    out = []
    order = np.argsort(lab, kind="stable")
    lab_s = lab[order]
    starts = np.r_[0, np.flatnonzero(np.diff(lab_s)) + 1, len(lab_s)]
    for a, b in zip(starts[:-1], starts[1:]):
        if b - a < CAR["n_min"]:
            continue
        idx = sel[order[a:b]]
        c = describe_cluster(pts, idx, ground[idx], asg)
        if c is not None:
            out.append(c)
    return out


def footprint(xy):
    """Longest and shortest side of the PCA-aligned footprint box (m)."""
    c = xy - xy.mean(0)
    if len(c) < 3:
        return 0.0, 0.0
    w, v = np.linalg.eigh(np.cov(c.T))
    q = c @ v
    ext = np.ptp(q, axis=0)
    return float(ext.max()), float(ext.min())


def describe_cluster(pts, idx, ground, asg):
    p = pts[idx]
    rng_c = float(np.hypot(p[:, 0].mean(), p[:, 1].mean()))
    if not CAR["range"][0] <= rng_c <= CAR["range"][1]:
        return None
    height = float(p[:, 2].max() - ground.min())
    bottom = float(p[:, 2].min() - ground.min())
    longest, shortest = footprint(p[:, :2])
    if not (CAR["h"][0] <= height <= CAR["h"][1] and CAR["long"][0] <= longest <= CAR["long"][1]
            and shortest <= CAR["short_max"] and bottom <= CAR["bottom_max"]):
        return None
    az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
    cells = G.ideal_cells(asg["k"][idx], az)
    return {"range": rng_c, "az": float(az[0]), "n": int(len(p)), "cells": cells, "q": len(p) / max(cells, 1.0),
            "length": longest, "width": shortest, "height": height, "int": p[:, 3].astype(np.float32),
            "rings": int(asg["k"][idx].max() - asg["k"][idx].min() + 1)}


def point_set_stats(pts_obj, asg_idx_k):
    """Same statistic for a set of points (a phantom): count, cells, occupancy."""
    az = np.degrees(np.arctan2(pts_obj[:, 1], pts_obj[:, 0]))
    cells = G.ideal_cells(asg_idx_k, az)
    return len(pts_obj), cells, len(pts_obj) / max(cells, 1.0)
