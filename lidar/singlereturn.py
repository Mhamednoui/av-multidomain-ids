"""WP3 S2b single-return physics: one return per beam (laser, azimuth).

KITTI's HDL-64E reports ONE return per firing (strongest/last of the pulse). An injected return in a beam therefore
REPLACES the real return behind it; both cannot appear. This module removes, for every injected point, the real points of
the same laser and azimuth (|d azimuth| < DAZ) that lie farther away, and counts beam conflicts for the physics tests.
Beam identity of a point: laser = nearest ring line of the ring table after the per-scan common mode, azimuth = atan2(y, x).
Limits: for an off-ring injected point (random box cloud) the laser is the nearest ring, a convention (the attacker
chooses the beam in a real attack); points of calibrated ray-cast phantoms sit on their own ring line, so there it is exact.
Inputs: scans (N x 4), ring table (lidar.geometry). Outputs: boolean keep-mask / conflict counts.
"""
import numpy as np
from scipy.spatial import cKDTree

from lidar.geometry import RingTable

DAZ = 0.04          # deg: below it only ~0.03 % of true same-laser neighbours in clean train scans (S2)
RHO_EPS = 0.05      # m: a real point is "behind" the injected one if it is farther than this margin


def _beam_xy(k, az):
    return np.c_[k.astype(np.float64) * 1000.0, az]


def beams(pts, table, cm=None):
    """(laser index, azimuth deg, range m) of each point."""
    rho = np.linalg.norm(pts[:, :3], axis=1)
    k, _ = table.nearest(pts, cm, rho)
    return k, np.degrees(np.arctan2(pts[:, 1], pts[:, 0])), rho


def conflict_losers(pts, table, is_new, cm=None, daz=DAZ):
    """Indices of the farther point of every pair that shares a beam and involves at least one injected point."""
    k, az, rho = beams(pts, table, cm)
    pairs = cKDTree(_beam_xy(k, az)).query_pairs(daz, p=np.inf, output_type="ndarray")
    if len(pairs) == 0:
        return np.zeros(0, int)
    pairs = pairs[is_new[pairs[:, 0]] | is_new[pairs[:, 1]]]
    far = np.where(rho[pairs[:, 0]] > rho[pairs[:, 1]], pairs[:, 0], pairs[:, 1])
    return np.unique(far)


def add_single_return(real, new, table, cm=None, daz=DAZ):
    """Scan after injecting `new` into `real` on a single-return sensor: in every beam only the nearest return survives
    (real returns behind an injected one disappear; an injected return behind a nearer real one, or behind a nearer
    injected one, is not reported). Conflicts between two REAL returns (clean-scan ambiguity) are left untouched."""
    if len(new) == 0:
        return real
    allp = np.vstack([real, new])
    is_new = np.r_[np.zeros(len(real), bool), np.ones(len(new), bool)]
    keep = np.ones(len(allp), bool)
    keep[conflict_losers(allp, table, is_new, cm, daz)] = False
    return np.vstack([real[keep[:len(real)]], new[keep[len(real):]]])


def beam_conflicts(pts, table, cm=None, daz=DAZ):
    """Number of points that share a beam (same laser, |d az| < daz) with a NEARER-or-equal point of the same scan."""
    if len(pts) < 2:
        return 0
    k, az, rho = beams(pts, table, cm)
    tree = cKDTree(_beam_xy(k, az))
    pairs = tree.query_pairs(daz, p=np.inf, output_type="ndarray")
    if len(pairs) == 0:
        return 0
    far = np.where(rho[pairs[:, 0]] > rho[pairs[:, 1]], pairs[:, 0], pairs[:, 1])
    return int(len(np.unique(far)))


def enforce_appended(real, attacked, table, cm=None):
    """Single-return version of an attack that injects rows into the real scan: rows APPENDED beyond len(real) (box cloud,
    S1 add modes) or rows CHANGED in place (replace modes, same length) are the injected points; the nearest return per beam
    survives. Attacks that only remove points or change intensities pass unchanged."""
    if len(attacked) > len(real):
        return add_single_return(real, attacked[len(real):], table, cm)
    if len(attacked) == len(real):
        ch = np.any(attacked[:, :3] != real[:, :3], axis=1)
        if ch.any():
            return add_single_return(real[~ch], attacked[ch], table, cm)
    return attacked


def apply_attack(name, pts, p, rng, table):
    """lidar.features.apply_attack followed by the single-return rule (same rng draws as the original)."""
    from lidar.features import apply_attack as _apply
    return enforce_appended(pts, _apply(name, pts, p, rng), table)
