"""WP8 S7: LiDAR odometry (gps/lidar_odom.py, the v3 ICP code) of the 13 H31 KITTI drives, cached per drive in ../data_extra/cache_v3/WP8/S7/odom/ (resumable: finished drives are skipped).
Same code and parameters as tools/WP1_S5_odom_run.py; only the paths differ (WP8_S7_lib.patch_h31_paths). Reads H31 velodyne files: run only after the S7 freeze commit.
Run: python -u -W ignore tools/WP8_S7_odom.py [--procs 3] [drive ...]"""
import argparse
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

from gps import lidar_odom as LO


def run_drive(d):
    S7.patch_h31_paths()
    from lidar.data import scan_files
    f = S7.CACHE / "odom" / f"lidar_odom_{d}.npz"
    if f.exists():
        return d, "cached", 0.0
    f.parent.mkdir(parents=True, exist_ok=True)
    paths = scan_files(d)
    t0 = time.time()
    rel, q = LO.scan_odometry(paths, log=lambda s: print(f"[{d}] {s}", flush=True))
    tmp = f.with_name(f.stem + ".tmp.npz")
    np.savez(tmp, t=S7.scan_times(d), rel=rel, quality=q, voxel=LO.VOXEL)
    tmp.replace(f)
    return d, f"{len(paths)} scans", time.time() - t0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("drives", nargs="*")
    a = ap.parse_args()
    ids = a.drives or sorted(S7.kitti_drives())
    with Pool(a.procs) as pool:
        for d, msg, dt in pool.imap_unordered(run_drive, ids):
            print(time.strftime("%H:%M:%S"), d, msg, f"{dt:.0f}s", flush=True)
