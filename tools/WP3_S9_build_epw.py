"""WP3 S9: build the S4-style tables (L1 statistics + tiles) of the world-fixed persistent episodes (val dry run, test) in
../data_extra/cache_v3/WP3/S9/ (resumable, one pickle per drive). Usage: python -u -W ignore tools/WP3_S9_build_epw.py [val|test] [--procs 4]"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import geometry as G
from lidar.data import CACHE, TEST, VAL, scan_files
from lidar.s9_build import drive_episodes_world
from WP3_S4_build import prm

OUT = CACHE / "S9"
S2 = RESULTS / "WP3" / "S2"


def job(args):
    split, d = args
    f = OUT / f"epw_{split}_{d}.pkl"
    if f.exists():
        return d, -1
    table = G.RingTable.load(S2 / "ring_table.json")
    calib = C.load_calib(S2 / "calibration_beta.npz")
    s, tl = drive_episodes_world(d, table, calib, prm())
    pd.to_pickle({"scans": s, "tiles": tl}, f)
    return d, len(s)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    splits = [a for a in sys.argv[1:] if a in ("val", "test")] or ["val", "test"]
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 4
    todo = [(s, d) for s in splits for d in (VAL if s == "val" else TEST)]
    todo.sort(key=lambda a: -len(scan_files(a[1])))
    t0 = time.time()
    with Pool(procs) as p:
        for d, n in p.imap_unordered(job, todo):
            print(d, n, f"{time.time() - t0:.0f}s", flush=True)
