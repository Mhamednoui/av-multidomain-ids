"""WP3 S6 L2d tracking of surfaces across scans with ego-motion compensation (cell level: ring x 1 degree azimuth tiles).

Each non-ground cell of the current scan is explained by one of three motion hypotheses relative to the previous scan:
  static world   the previous scan moved by the OXTS ego-motion predicts a surface at the same range (lidar.background.moved);
  sensor-fixed   the surface has the SAME range in the uncompensated previous image (it follows the car's own motion exactly:
                 a phantom fixed to the sensor frame), while the static-world prediction disagrees (needs ego motion >~ 0.3 m/scan);
  new            a surface nearer than anything the compensated previous scan showed along that ray (the ray was free before): it
                 appeared without entering from the edge of the range window or from behind an occluder (a nearer predicted surface
                 in the neighbourhood explains it, so occlusion exits and entries from behind objects are not counted).
Statistics per scan (counts of cells and the largest 8-connected blob): app_tot, app_cc (new surface), fix_tot, fix_cc (sensor-fixed),
van_tot (a predicted non-ground surface that is gone: nothing within 2 m in the neighbourhood now, nearest return farther or none).
Physics limit (stated, tested in S6): a phantom that is placed in the WORLD and moves with a plausible trajectory is a static / moving
surface for this tracker; only its first scan (appearance) can be flagged, never the later ones.
Inputs: Img of the current scan, Img of the compensated previous scan, Img of the previous scan as it was (lidar.background.Img).
"""
import numpy as np
from scipy.ndimage import label, minimum_filter, maximum_filter

from lidar.background import BIG, NAZ, dilate

MARGIN = 2.0       # m, a surface this much nearer than the prediction is "new"
R_NG_HI = 45.0
RAW_TOL = 0.12     # m, same range in the uncompensated previous image
PRED_TOL = 0.30    # m, static-world prediction within this range explains a cell
STRUCT = np.ones((3, 3), int)


def _blob(mask):
    """(count, largest 8-connected component) of a boolean cell mask; azimuth wrap ignored (one cell column)."""
    n = int(mask.sum())
    if n == 0:
        return 0.0, 0.0
    lab, m = label(mask, structure=STRUCT)
    return float(n), float(np.bincount(lab.ravel())[1:].max())


def _near(pred_nmin, o, tol):
    """True where some cell of the 3 x 3 neighbourhood of the predicted non-ground image is within tol of o (o: cell values)."""
    hit = np.zeros(o.shape, bool)
    for dr in (-1, 0, 1):
        for da in (-1, 0, 1):
            p = np.roll(np.roll(pred_nmin, dr, 0), da, 1)
            hit |= np.abs(p - o) <= tol
    return hit


def track_stats(cur, pred, raw_prev):
    """L2d statistics from three Img objects (current, previous moved into the current frame, previous unmoved)."""
    o = cur.nmin
    has = (o < R_NG_HI) & (o < BIG)
    pn = dilate(pred.nmin)
    pany = dilate(pred.amin) < BIG
    app = has & pany & (o < pn - MARGIN)
    near = _near(pred.nmin, o, PRED_TOL)
    fix = has & (np.abs(o - raw_prev.nmin) <= RAW_TOL) & ~near
    # van: predicted non-ground surface, nothing of the current scan within 2 m of it in the neighbourhood
    p = pred.nmin
    pv = (p < R_NG_HI) & (p < BIG)
    gone = pv & ~_near(cur.amin, p, MARGIN)
    out = {}
    out["app_tot"], out["app_cc"] = _blob(app)
    out["fix_tot"], out["fix_cc"] = _blob(fix)
    out["van_tot"], out["van_cc"] = _blob(gone)
    return out
