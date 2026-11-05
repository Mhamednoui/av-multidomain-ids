"""WP9 B4 LiDAR: descriptor rows (429 columns, lidar.features) of clean scans and of the 9 attack kinds, per drive, resumable.

Clean rows: every scan i >= 1 of a drive (temporal part vs the previous clean scan). Attack rows (onset: previous scan clean):
  train drives: scans i % 2 == 1, rng [97, drive, i];  val / test drives: scans i % 3 == 1, rng [83, drive, i] (= S4 / WP8 S3 evaluation set).
Attack kinds from lidar.s4_build.attack_cases (9 per scan). Output: ../data_extra/cache_v3/WP9/B4/lidar/<kind>_<drive>.pkl = {"meta", "X"}.
Never opens a drive that is not in locks/WP9_kitti.json (H31 guard). Run: python -u -W ignore tools/WP9_B4_lidar_build.py [--procs 3] [--parts train val test]
"""
import argparse
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from common.config import DATA_EXTRA

OUT = DATA_EXTRA / "cache_v3" / "WP9" / "B4" / "lidar"
LOCK = json.loads((ROOT / "locks" / "WP9_kitti.json").read_text())
PART = {d: p for p, v in LOCK["parts"].items() for d in v["drives"]}


def work(job):
    kind, d = job
    f = OUT / f"{kind}_{d}.pkl"
    if f.exists():
        return job, 0.0, "skip"
    from WP8_lib import assert_not_h31
    from lidar.data import group_id, load, scan_files
    from lidar.features import describe, temporal
    from lidar.learned_l4 import tools
    from lidar.s4_build import attack_cases
    assert d in PART
    assert_not_h31([f"2011_09_26_drive_{d}"])
    t0 = time.time()
    table, calib = tools()
    files = scan_files(d)
    X, meta = [], []
    if kind == "clean":
        prev = describe(load(files[0]))
        for i in range(1, len(files)):
            cur = describe(load(files[i]))
            X.append(np.r_[cur, temporal(cur, prev)])
            meta.append((d, group_id(d, files[i]), i, "clean", 0))
            prev = cur
    else:
        stride, seed = (2, 97) if PART[d] == "train" else (3, 83)
        for i in range(1, len(files), stride):
            pts = load(files[i])
            prev_clean = describe(load(files[i - 1]))
            rng = np.random.default_rng([seed, int(d), i])
            g = group_id(d, files[i])
            for name, att, idx in attack_cases(pts, rng, table, calib):
                cur = describe(att)
                X.append(np.r_[cur, temporal(cur, prev_clean)])
                meta.append((d, g, i, name, 0 if idx is None else len(idx)))
    df = pd.DataFrame(meta, columns=["drive", "base", "i", "attack", "n_inj"])
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    pd.to_pickle({"meta": df, "X": np.array(X, np.float32)}, tmp)
    tmp.replace(f)
    return job, time.time() - t0, f"{len(df)} rows"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("--parts", nargs="+", default=["train", "val", "test"])
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    ds = [d for p in a.parts for d in LOCK["parts"][p]["drives"]]
    jobs = [("clean", d) for d in ds] + [("attack", d) for d in sorted(ds, key=lambda d: -LOCK["parts"][PART[d]]["n_scans"][d])]
    if a.only:
        jobs = [j for j in jobs if j[1] in a.only]
    print(len(jobs), "jobs", flush=True)
    with Pool(a.procs) as pool:
        for job, dt, msg in pool.imap_unordered(work, jobs):
            print(time.strftime("%H:%M:%S"), job, f"{dt:.0f}s", msg, flush=True)


if __name__ == "__main__":
    main()
