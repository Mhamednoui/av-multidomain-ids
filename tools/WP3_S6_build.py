"""WP3 S6: build L2c / L2d statistic tables in ../data_extra/cache_v3/WP3/S6/ (resumable, one pickle per drive and kind).
Usage: python -u -W ignore tools/WP3_S6_build.py <kind> [<kind> ...] [--drives 0011,0035] [--procs 4]
Kinds: clean (all drives), att_val, att_test, ep_val, ep_test (S4 sensor-fixed persistent phantoms), epw_val, epw_test (world-fixed)."""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import background_build as BB
from lidar import calibration as C
from lidar import geometry as G
from lidar.data import CACHE, DRIVES, TEST, VAL, cache_size_gb, scan_files

S2 = RESULTS / "WP3" / "S2"
OUT = CACHE / "S6"
DRV = {"clean": DRIVES, "att_val": VAL, "att_test": TEST, "ep_val": VAL, "ep_test": TEST, "epw_val": VAL, "epw_test": TEST}
N_EP = {"ep_val": 2, "epw_val": 2, "ep_test": 3, "epw_test": 3}


def job(a):
    kind, d = a
    f = OUT / f"{kind}_{d}.pkl"
    if f.exists():
        return kind, d, -1
    table = G.RingTable.load(S2 / "ring_table.json")
    calib = C.load_calib(S2 / "calibration_beta.npz")
    if kind == "clean":
        df = BB.drive_clean(d, table)
    elif kind.startswith("att"):
        df = BB.drive_attacks(d, table, calib)
    else:
        df = BB.drive_episodes(d, table, calib, N_EP[kind], world=kind.startswith("epw"))
    pd.to_pickle(df, f)
    return kind, d, len(df)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    args, drives, procs = sys.argv[1:], None, 4
    for flag in ("--drives", "--procs"):
        if flag in args:
            k = args.index(flag)
            v = args[k + 1]
            args = args[:k] + args[k + 2:]
            if flag == "--drives":
                drives = v.split(",")
            else:
                procs = int(v)
    todo = [(k, d) for k in args for d in DRV[k] if (drives is None or d in drives) and not (OUT / f"{k}_{d}.pkl").exists()]
    todo.sort(key=lambda a: -len(scan_files(a[1])))
    print(len(todo), "jobs", flush=True)
    t0 = time.time()
    with Pool(procs) as pool:
        for kind, d, n in pool.imap_unordered(job, todo):
            print(kind, d, n, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
