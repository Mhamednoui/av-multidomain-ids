"""WP3 S2 Part A, stage 1: real car-like clusters and uncalibrated phantoms on TRAIN and VAL scans (every 3rd scan).
Cache: ../data_extra/cache_v3/WP3/S2/collect_<drive>.pkl (resumable). Never touches test drives."""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import geometry as G
from lidar.data import CACHE, TEST, drives_of, load, scan_files

OUT = CACHE / "S2"
STRIDE = 3


def job(d):
    f = OUT / f"collect_{d}.pkl"
    if f.exists():
        return d, -1
    table = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
    rng = np.random.default_rng([31, int(d)])
    rows = []
    for i, fp in enumerate(scan_files(d)):
        if i % STRIDE:
            continue
        for r in C.scan_records(load(fp), table, rng):
            r["drive"], r["scan"] = d, i
            rows.append(r)
    OUT.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(rows, f)
    return d, len(rows)


if __name__ == "__main__":
    ds = [d for d in drives_of("train") + drives_of("val")]
    assert not set(ds) & set(TEST)
    t0 = time.time()
    with Pool(4) as pool:
        for d, n in pool.imap_unordered(job, ds):
            print(d, n, f"{time.time() - t0:.0f}s", flush=True)
