"""WP3 S2: build the evaluation tables (L1 statistics + v2 descriptors of attacked scans) for val and test drives.
Needs results/WP3/S2/ring_table.json and results/WP3/S2/calibration_<variant>.npz (variant given as argument, default
the one named in results/WP3/S2/calib_choice.json). Resumable: one pickle per table and drive in
../data_extra/cache_v3/WP3/S2/. Computing features on test scans is not a test evaluation (no model or threshold touched).
Usage: python -u -W ignore tools/WP3_S2_build.py [v2l1|ray ...]"""
import json
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
from lidar import l1_build as B
from lidar.data import CACHE, TEST, VAL, cache_size_gb, scan_files

OUT = CACHE / "S2"
RES = RESULTS / "WP3" / "S2"


def job(args):
    kind, d = args
    f = OUT / f"{kind}_{d}.pkl"
    if f.exists():
        return kind, d, -1
    table = G.RingTable.load(RES / "ring_table.json")
    if kind == "v2l1":
        rows = B.v2_attack_l1(d, table)
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "scan": [r[1] for r in rows], "cls": [r[2] for r in rows],
                             "mode": [r[3] for r in rows], "n_pts": [r[4] for r in rows]})
        stats = np.vstack([r[5] for r in rows])
        obj = {"meta": meta, "stats": stats}
    else:
        name = json.loads((RES / "calib_choice.json").read_text())["variant"]
        calib = C.load_calib(RES / f"calibration_{name}.npz")
        rows = B.ray_rows((d, table, calib))
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "scan": [r[1] for r in rows], "variant": [r[2] for r in rows],
                             "mode": [r[3] for r in rows], "band": [r[4] for r in rows], "timing": [r[5] for r in rows],
                             "n_spoofed": [r[6] for r in rows], "range_m": [r[7] for r in rows], "budget": [r[8] for r in rows]})
        obj = {"meta": meta, "stats": np.vstack([r[9] for r in rows]), "X": np.vstack([r[10] for r in rows]).astype(np.float32)}
    pd.to_pickle(obj, f)
    return kind, d, len(meta)


if __name__ == "__main__":
    kinds = sys.argv[1:] or ["v2l1", "ray"]
    todo = [(k, d) for k in kinds for d in VAL + TEST if not (OUT / f"{k}_{d}.pkl").exists()]
    todo.sort(key=lambda a: -len(scan_files(a[1])))
    print(len(todo), "jobs", flush=True)
    t0 = time.time()
    with Pool(4) as pool:
        for kind, d, n in pool.imap_unordered(job, todo):
            assert cache_size_gb() < 3.0, "cache over 3 GB"
            print(kind, d, n, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
