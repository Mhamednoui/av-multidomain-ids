"""WP3 S3 association of objects between consecutive scans with OXTS ego-motion (nearest centroid, mutual).

Inputs: two object tables (lidar.segment) and the poses (lidar.ego) of the two scans. Output: matches (indices, distance after
ego-motion compensation, point-count ratio). Static world assumed: moving objects (oncoming cars) legitimately fail the
distance gate, so the match rate is a lower bound of the segmentation stability (parked cars, walls, poles are static).
"""
import numpy as np
from scipy.spatial import cKDTree

from lidar import ego


def match(tab_a, pose_a, tab_b, pose_b, thr=1.0, r_lo=0.0, r_hi=60.0):
    """Objects of A with range in [r_lo, r_hi): index in B of the mutual nearest centroid within thr (m), else -1."""
    if len(tab_a) == 0 or len(tab_b) == 0:
        return np.zeros(0, int), np.zeros(0, int), np.zeros(0), np.zeros(0)
    ca = ego.between(tab_a[["cx", "cy"]].to_numpy(), pose_a, pose_b)
    cb = tab_b[["cx", "cy"]].to_numpy()
    d_ab, j = cKDTree(cb).query(ca)
    d_ba, i = cKDTree(ca).query(cb)
    ra = tab_a["range"].to_numpy()
    rb = np.hypot(ca[:, 0], ca[:, 1])
    cand = np.flatnonzero((ra >= r_lo) & (ra < r_hi) & (rb < 55.0))      # still inside the segmented area after the move
    ok = (d_ab[cand] <= thr) & (i[j[cand]] == cand)
    jj = np.where(ok, j[cand], -1)
    ratio = np.full(len(cand), np.nan)
    m = jj >= 0
    ratio[m] = tab_b["n_points"].to_numpy()[jj[m]] / tab_a["n_points"].to_numpy()[cand[m]]
    return cand, jj, np.where(m, d_ab[cand], np.nan), ratio
