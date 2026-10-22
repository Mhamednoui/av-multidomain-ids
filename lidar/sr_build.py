"""WP3 S2b evaluation tables with the single-return rule (validation drives only).

Same drives, scans, seeds and placement draws as lidar.l1_build (v2l1: [42, drive]; ray: [53, drive]); the only change is the
physics: lidar.singlereturn (one return per beam). Tables:
  sr_v2   GhostCluster (box cloud) rows of the v2 protocol: L1 statistics + descriptor (429) of the single-return attack,
          onset / sustained like lidar.build.drive_rows. PointDrop / IntensitySpoof do not inject returns: unchanged (S2 tables).
  sr_ray  old (S1 origin-ray generator + single-return enforcement) and cal (lidar.phantom, single_return=True) phantoms.
"""
import numpy as np

from lidar import geometry as G
from lidar import phantom as P
from lidar import singlereturn as S
from lidar.data import group_id, load, part_of, scan_files
from lidar.features import ATTACKS, apply_attack, attack_params, describe, temporal
from lidar.raycast import MODES, eval_params, phantom as old_phantom

TRAIN_REPS = 2
STRIDE = 2


def v2_ghost_rows(d, table):
    rng = np.random.default_rng([42, int(d)])
    reps = TRAIN_REPS if part_of(d) == "train" else 1
    bins = scan_files(d)
    rows = []
    prev_pts = load(bins[0])
    prev_clean = describe(prev_pts)
    for b in bins[1:]:
        pts = load(b)
        clean = describe(pts)
        g = group_id(d, b)
        for name in ATTACKS:
            for _ in range(reps):
                p = attack_params(name, rng)
                att = apply_attack(name, pts, p, rng)
                onset = rng.random() < 0.5
                prev_att = None if onset else apply_attack(name, prev_pts, p, rng)
                if name != "GhostCluster":
                    continue
                att = S.enforce_appended(pts, att, table)
                cur = describe(att)
                if onset:
                    mode, prev = "onset", prev_clean
                else:
                    mode, prev = "sustained", describe(S.enforce_appended(prev_pts, prev_att, table))
                rows.append((d, g, name, mode, len(att), G.l1_stats(att, table), np.r_[cur, temporal(cur, prev)]))
        prev_pts, prev_clean = pts, clean
    return rows


def ray_rows_sr(args):
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
                    old = S.enforce_appended(pts, old, table)
                    cal, n_cal, q_cal, _ = P.phantom(pts, rays, p, rng, mode, calib)
                    for variant, att, n, q in (("old", old, n_old, q_old), ("cal", cal, n_cal, q_cal)):
                        if variant == "old":
                            prev_s = S.enforce_appended(prev_pts, old_phantom(prev_pts, q, rng, mode)[0], table)
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
