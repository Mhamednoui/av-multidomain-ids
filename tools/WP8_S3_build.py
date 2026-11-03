"""WP8 S3 build: per-drive statistic records of the LiDAR pipeline (clean scans of the 23 V31 train + validation drives; attacked scans,
the S4 attack set (seeds [83, drive, scan]) and persistent PointDrop episodes (seeds [101, drive]) of the 10 V31_val drives).
Resumable: one pickle per (kind, drive) in results/WP8/S3/parts/, written to a temp name and renamed; finished parts are skipped.
Run: python -u -W ignore tools/WP8_S3_build.py [--procs 3] [--only clean|att|pdep]   (background, log in results/WP8/logs/)
Attack rules as in lidar.s4_build.drive_attacks (stride 3, scans i % 3 == 1, attacked scan compared with the CLEAN previous scan);
PointDrop episode = the v2 attack (sector 10-60 deg, 50-100 % of its points removed) with fixed parameters for 30 scans and fresh
random thinning each scan; step 1 is compared with the clean previous scan, later steps with the attacked previous scan (as S6)."""
import argparse
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S3_lib as L
from lidar import ego
from lidar.data import load, scan_files
from lidar.fast import PrevScan, ScanStats
from lidar.features import apply_attack, attack_params
from lidar.s4_build import attack_cases


def stats_for(drive):
    L.guard([drive])
    return ScanStats(L.table(), L.PRM)


def job_clean(d):
    out = L.PARTS / f"clean_{d}.pkl"
    if out.exists():
        return d, "skip"
    t0 = time.time()
    ss, files, pose = stats_for(d), scan_files(d), ego.poses(d)
    rows, tl, prev = [], [], None
    for i, f in enumerate(files):
        pts = load(f)
        l1, t, pair, cur = ss.compute(pts, pose[i], prev)
        rows.append(dict(i=i, n_pts=len(pts), **L.row_of(l1, pair)))
        tl.append(L.tile_frame(t, i))
        prev = PrevScan(pts, pose[i], img=cur)                 # this scan's image is the next scan's raw previous image
    L.write_atomic({"scans": pd.DataFrame(rows), "tiles": pd.concat(tl, ignore_index=True)}, out)
    return d, f"{time.time() - t0:.0f}s {len(files)} scans"


def job_att(d):
    out = L.PARTS / f"att_{d}.pkl"
    if out.exists():
        return d, "skip"
    t0 = time.time()
    ss, files, pose, calib, table = stats_for(d), scan_files(d), ego.poses(d), L.calib(), L.table()
    rows, tl = [], []
    for i in range(1, len(files), 3):
        pts = load(files[i])
        rng = np.random.default_rng([83, int(d), i])
        prev = PrevScan(load(files[i - 1]), pose[i - 1])
        for name, att, idx in attack_cases(pts, rng, table, calib):
            l1, t, pair, _ = ss.compute(att, pose[i], prev)
            k = len(rows)
            rows.append(dict(i=i, attack=name, n_pts=len(att), n_inj=0 if idx is None else int(len(idx)), **L.row_of(l1, pair)))
            tl.append(L.tile_frame(t, k))
    L.write_atomic({"scans": pd.DataFrame(rows), "tiles": pd.concat(tl, ignore_index=True)}, out)
    return d, f"{time.time() - t0:.0f}s {len(rows)} attacked scans"


def job_pdep(d):
    out = L.PARTS / f"pdep_{d}.pkl"
    if out.exists():
        return d, "skip"
    t0 = time.time()
    ss, files, pose = stats_for(d), scan_files(d), ego.poses(d)
    rng = np.random.default_rng([101, int(d)])
    rows, tl = [], []
    for j in range(L.PD_EP_PER_DRIVE):
        p = attack_params("PointDrop", rng)
        s0 = int(rng.integers(1, max(2, len(files) - L.EP_LEN)))
        prev = PrevScan(load(files[s0 - 1]), pose[s0 - 1])
        for k in range(s0, min(len(files), s0 + L.EP_LEN)):
            att = apply_attack("PointDrop", load(files[k]), p, rng)
            l1, t, pair, cur = ss.compute(att, pose[k], prev)
            n = len(rows)
            rows.append(dict(i=k, ep=j, step=k - s0 + 1, attack="ep_PointDrop", n_pts=len(att), **L.row_of(l1, pair)))
            tl.append(L.tile_frame(t, n))
            prev = PrevScan(att, pose[k], img=cur)
    L.write_atomic({"scans": pd.DataFrame(rows), "tiles": pd.concat(tl, ignore_index=True)}, out)
    return d, f"{time.time() - t0:.0f}s {len(rows)} episode scans"


def run(task):
    kind, d = task
    try:
        return kind, *{"clean": job_clean, "att": job_att, "pdep": job_pdep}[kind](d)
    except Exception as e:                                                   # report, do not kill the pool
        import traceback
        return kind, d, "FAILED " + traceback.format_exc()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    size = {d: len(scan_files(d)) for d in L.DRIVES}
    tasks = [("att", d) for d in L.VAL] + [("pdep", d) for d in L.VAL] + [("clean", d) for d in L.DRIVES]
    if a.only:
        tasks = [t for t in tasks if t[0] == a.only]
    tasks.sort(key=lambda t: -size[t[1]] * (3.5 if t[0] == "att" else 1.0 if t[0] == "clean" else 0.6))
    print(time.strftime("%H:%M:%S"), len(tasks), "tasks", flush=True)
    with Pool(a.procs) as pool:
        for kind, d, msg in pool.imap_unordered(run, tasks):
            print(time.strftime("%H:%M:%S"), kind, d, msg, flush=True)
    print("done", flush=True)
