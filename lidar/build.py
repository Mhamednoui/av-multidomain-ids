"""WP3 S1 tables: descriptor rows for training, ray-cast evaluation and persistent episodes.

Inputs: KITTI velodyne scans (lidar.data), v2 descriptor + attacks (lidar.features),
ray-cast phantoms (lidar.raycast). Outputs: pandas tables cached under
../data_extra/cache_v3/WP3/ (see tools/WP3_S1_build.py). Every row carries
`scan` = "<drive>/<file>" (group id) and `drive`.
Copies the row logic of ../codes_v2/lidar/train.py (drive_rows), raycast_test.py (drive_rows)
and sequence.py (drive_sequences); same seeds, so the v2 rows are reproduced exactly.
Row layout: descriptor (211) + scan-to-scan features (211 + 7) = 429 columns.
"""
import numpy as np

from lidar.data import SCENE, group_id, load, part_of, scan_files
from lidar.features import ATTACKS, apply_attack, attack_params, describe, feature_names_temporal, \
    raycast_ghost, temporal
from lidar.raycast import MODES, eval_params, phantom

TRAIN_REPS = 2
NAMES = feature_names_temporal()
META_COLS = ["drive", "scan", "cls", "mode"]


def drive_rows(d):
    """v2 training / validation / test rows of one drive (4 classes, onset or sustained)."""
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
        rows.append((d, g, "Normal", "none", np.r_[clean, temporal(clean, prev_clean)]))
        for name in ATTACKS:
            for _ in range(reps):
                p = attack_params(name, rng)
                cur = describe(apply_attack(name, pts, p, rng))
                if rng.random() < 0.5:
                    mode, prev = "onset", prev_clean
                else:
                    mode, prev = "sustained", describe(apply_attack(name, prev_pts, p, rng))
                rows.append((d, g, name, mode, np.r_[cur, temporal(cur, prev)]))
        prev_pts, prev_clean = pts, clean
    return rows


def v2_raycast_rows(d):
    """v2 ray-cast test rows (lidar/raycast_test.py): add / replace / budget_add / budget,
    range 5-40 m, onset and sustained."""
    rng = np.random.default_rng([7, int(d)])
    bins = scan_files(d)
    rows = []
    prev_pts = load(bins[0])
    prev_clean = describe(prev_pts)
    for b in bins[1:]:
        pts = load(b)
        p = attack_params("GhostCluster", rng)
        p["budget"] = int(rng.integers(50, 401))
        for mode in MODES:
            att, n = raycast_ghost(pts, p, rng, mode, retry=True)
            prev_s = describe(raycast_ghost(prev_pts, p, rng, mode, retry=True)[0])
            cur = describe(att)
            for timing, prev in (("onset", prev_clean), ("sustained", prev_s)):
                rows.append((d, group_id(d, b), mode, timing, n, p["range"], np.r_[cur, temporal(cur, prev)]))
        prev_pts, prev_clean = pts, describe(pts)
    return rows


def wp3_phantom_rows(d, stride=1):
    """WP3 evaluation phantoms: 4 modes x range band near (5-15 m) / far (15-40 m), budget 50-400,
    onset and sustained. Placement is drawn fresh for every scan."""
    rng = np.random.default_rng([3, int(d)])
    bins = scan_files(d)
    rows = []
    prev_pts = load(bins[0])
    prev_clean = describe(prev_pts)
    for k, b in enumerate(bins[1:]):
        pts = load(b)
        if k % stride == 0:
            for band in ("near", "far"):
                p = eval_params(rng, band)
                for mode in MODES:
                    att, n, q = phantom(pts, p, rng, mode)
                    prev_s = describe(phantom(prev_pts, q, rng, mode)[0])
                    cur = describe(att)
                    for timing, prev in (("onset", prev_clean), ("sustained", prev_s)):
                        rows.append((d, group_id(d, b), mode, band, timing, n, p["range"], p["budget"],
                                     np.r_[cur, temporal(cur, prev)]))
        prev_pts, prev_clean = pts, describe(pts)
    return rows


def episode_rows(args):
    """Persistent episodes of one drive (sequence logic of v2 + ray-cast episodes).
    v2 part: the clean drive and DRAWS persistent attacks per type over the whole drive.
    WP3 part: ray-cast phantoms (budget_add, budget) x (near, far), n_ray draws each,
    EP_LEN consecutive scans from a random start; the phantom keeps its position relative to
    the car. Row = (drive, kind, name, draw, k, scan group, range, descriptor+temporal)."""
    d, n_draws, n_ray, ep_len = args
    rng = np.random.default_rng([23, int(d)])
    bins = scan_files(d)
    clean = [describe(load(b)) for b in bins]
    out = [(d, "v2", "Normal", 0, k, group_id(d, bins[k]), np.nan, np.r_[clean[k], temporal(clean[k], clean[k - 1])])
           for k in range(1, len(bins))]
    for name in ATTACKS:
        for j in range(n_draws):
            p = attack_params(name, rng)
            att = [None] + [describe(apply_attack(name, load(b), p, rng)) for b in bins[1:]]
            out.append((d, "v2", name, j, 1, group_id(d, bins[1]), p.get("range", np.nan),
                        np.r_[att[1], temporal(att[1], clean[0])]))
            for k in range(2, len(bins)):
                out.append((d, "v2", name, j, k, group_id(d, bins[k]), p.get("range", np.nan),
                            np.r_[att[k], temporal(att[k], att[k - 1])]))
    rng = np.random.default_rng([29, int(d)])
    for mode in ("budget_add", "budget"):
        for band in ("near", "far"):
            for j in range(n_ray):
                p = eval_params(rng, band)
                s0 = int(rng.integers(1, max(2, len(bins) - ep_len)))
                name = f"ray_{mode}_{band}"
                prev = clean[s0 - 1]
                for k in range(s0, min(len(bins), s0 + ep_len)):
                    att, n, q = phantom(load(bins[k]), p, rng, mode)
                    cur = describe(att)
                    out.append((d, "wp3", name, j, k - s0 + 1, group_id(d, bins[k]), p["range"],
                                np.r_[cur, temporal(cur, prev)]))
                    prev = cur
    return out
