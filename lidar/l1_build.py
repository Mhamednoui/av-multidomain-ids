"""WP3 S2 evaluation tables: L1 statistics (and v2 descriptors) of attacked scans, val and test drives.

Tables (one pickle per drive under ../data_extra/cache_v3/WP3/S2/):
  v2l1  one row per row of the S1 `train4` cache (same order, same seeds [42, drive], same attack code path of
        lidar.build.drive_rows): L1 statistics of the attacked scan. The v2 descriptor of the same row is the S1 cache.
  ray   WP3 phantoms, old (S1 generator: origin rays, ideal density) and calibrated (lidar.phantom), same placement
        parameters, 4 modes x range band near (5-15 m) / far (15-40 m), budget 50-400, every 2nd scan:
        L1 statistics + v2 descriptor (onset and sustained timing) of both generators.
Row meta: drive, scan, variant, mode, band, timing, n_spoofed, range_m, budget.
"""
import numpy as np

from lidar import geometry as G
from lidar import phantom as P
from lidar.data import group_id, load, part_of, scan_files
from lidar.features import ATTACKS, apply_attack, attack_params, describe, temporal
from lidar.raycast import MODES, eval_params, phantom as old_phantom

TRAIN_REPS = 2
STRIDE = 2


def v2_attack_l1(d, table):
    """L1 stats of the attacked scans in the exact order of lidar.build.drive_rows (val / test: one rep)."""
    rng = np.random.default_rng([42, int(d)])
    reps = TRAIN_REPS if part_of(d) == "train" else 1
    bins = scan_files(d)
    rows = []
    prev_pts = load(bins[0])
    for b in bins[1:]:
        pts = load(b)
        g = group_id(d, b)
        rows.append((d, g, "Normal", "none", len(pts), G.l1_stats(pts, table)))
        for name in ATTACKS:
            for _ in range(reps):
                p = attack_params(name, rng)
                att = apply_attack(name, pts, p, rng)
                if rng.random() < 0.5:
                    mode = "onset"
                else:
                    mode = "sustained"
                    apply_attack(name, prev_pts, p, rng)       # consumes the rng exactly as drive_rows does
                rows.append((d, g, name, mode, len(att), G.l1_stats(att, table)))
        prev_pts = pts
    return rows


def ray_rows(args):
    """Old and calibrated phantoms on the same placements (every STRIDE-th scan)."""
    d, table, calib = args
    rng = np.random.default_rng([53, int(d)])
    bins = scan_files(d)
    rows = []
    prev_pts = load(bins[0])
    for k, b in enumerate(bins[1:]):
        pts = load(b)
        if k % STRIDE == 0:
            rays, rays_prev = P.prepare(pts, table), None
            prev_clean = describe(prev_pts)
            for band in ("near", "far"):
                p = eval_params(rng, band)
                for mode in MODES:
                    old, n_old, q_old = old_phantom(pts, p, rng, mode)
                    cal, n_cal, q_cal, _ = P.phantom(pts, rays, p, rng, mode, calib)
                    for variant, att, n, q in (("old", old, n_old, q_old), ("cal", cal, n_cal, q_cal)):
                        # sustained: the same phantom (same parameters) in the previous scan
                        if variant == "old":
                            prev_s = old_phantom(prev_pts, q, rng, mode)[0]
                        else:
                            if rays_prev is None:
                                rays_prev = P.prepare(prev_pts, table)
                            prev_s = P.phantom(prev_pts, rays_prev, q, rng, mode, calib)[0]
                        l1 = G.l1_stats(att, table)
                        cur = describe(att)
                        for timing, prev in (("onset", prev_clean), ("sustained", describe(prev_s))):
                            rows.append((d, group_id(d, b), variant, mode, band, timing, n, p["range"], p["budget"], l1,
                                         np.r_[cur, temporal(cur, prev)]))
        prev_pts = pts
    return rows
