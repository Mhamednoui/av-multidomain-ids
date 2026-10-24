"""WP3 S7: L1 sensor-geometry statistics (lidar.geometry.l1_stats) of the clean scans of the 13 TRAIN drives (the S4 clean tables only carry
them for val / test drives), so that L1 can be calibrated on all 16 train+val drives like the other layers. One pickle per drive in
../data_extra/cache_v3/WP3/S7/l1_<drive>.pkl. Usage: python -u -W ignore tools/WP3_S7_l1train.py"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import geometry as G
from lidar.data import CACHE, drives_of, group_id, load, scan_files

OUT = CACHE / "S7"


def job(d):
    f = OUT / f"l1_{d}.pkl"
    if f.exists():
        return d, -1
    table = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
    rows = []
    for i, fl in enumerate(scan_files(d)):
        rows.append(dict(drive=d, idx=i, scan=group_id(d, fl), attack="clean",
                         **{f"l1_{n}": v for n, v in zip(G.STAT_NAMES, G.l1_stats(load(fl), table))}))
    pd.to_pickle(pd.DataFrame(rows), f)
    return d, len(rows)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    todo = sorted(drives_of("train"), key=lambda d: -len(scan_files(d)))
    t0 = time.time()
    with Pool(2) as pool:
        for d, n in pool.imap_unordered(job, todo):
            print(d, n, f"{time.time() - t0:.0f}s", flush=True)
