"""WP1 S5 step 1: run LiDAR odometry (gps/lidar_odom.py) on every KITTI drive that has velodyne scans; cache per drive.
Cache: results/WP1/cache/lidar_odom_<drive>.npz (gitignored): scan times (s, relative to the first OXTS timestamp, the clock of the
GPS stream), relative planar motions (dx, dy, dyaw), ICP quality. Drives without velodyne: none found (23 of 23), see S5_odometry.json.
Run from codes_v3/: python -u -W ignore tools/WP1_S5_odom_run.py [drive ...]   (Pool(4) over drives; resumes: existing caches are kept)
"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DATA, DATA_EXTRA, results_dir
from gps import lidar_odom as LO
from gps import stream as S

CACHE = results_dir("WP1") / "cache"
CACHE.mkdir(parents=True, exist_ok=True)


def drive_root(d):
    name = f"2011_09_26_drive_{d}_sync"
    root = DATA / "Depth" if d in ("0001", "0015") else DATA_EXTRA / "kitti_raw"
    return root / name / "2011_09_26" / name


def read_times(p):
    return pd.to_datetime(pd.read_csv(p, header=None)[0])


def scan_times(d):
    """Velodyne scan times (s) on the OXTS clock of S.load_oxts (t = 0 at the first OXTS timestamp)."""
    r = drive_root(d)
    t0 = read_times(r / "oxts" / "timestamps.txt").iloc[0]
    return (read_times(r / "velodyne_points" / "timestamps.txt") - t0).dt.total_seconds().to_numpy()


def scan_paths(d):
    return sorted((drive_root(d) / "velodyne_points" / "data").glob("*.bin"))


def has_velodyne(d):
    return len(scan_paths(d)) > 1


def run_drive(d):
    f = CACHE / f"lidar_odom_{d}.npz"
    if f.exists():
        return d, "cached", 0.0
    paths = scan_paths(d)
    t0 = time.time()
    rel, q = LO.scan_odometry(paths, log=lambda s: print(f"[{d}] {s}", flush=True))
    np.savez(f, t=scan_times(d), rel=rel, quality=q, voxel=LO.VOXEL)
    return d, f"{len(paths)} scans", time.time() - t0


def load_cached(d):
    z = np.load(CACHE / f"lidar_odom_{d}.npz")
    return z["t"], z["rel"], z["quality"]


if __name__ == "__main__":
    drives = sys.argv[1:] or sorted(S.SCENE)
    avail = [d for d in drives if has_velodyne(d)]
    print("without velodyne:", [d for d in drives if d not in avail], flush=True)
    todo = sorted(avail, key=lambda d: -len(scan_paths(d)))
    with Pool(4) as p:
        for d, msg, dt in p.imap_unordered(run_drive, todo):
            print(f"done {d}: {msg} in {dt:.0f}s", flush=True)
