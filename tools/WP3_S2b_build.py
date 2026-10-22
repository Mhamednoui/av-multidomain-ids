"""WP3 S2b: build single-return evaluation tables for the VALIDATION drives (resumable, one pickle per table and drive in
../data_extra/cache_v3/WP3/S2b/). Usage: python -u -W ignore tools/WP3_S2b_build.py"""
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
from lidar import sr_build as B
from lidar.data import CACHE, VAL, cache_size_gb, scan_files

OUT = CACHE / "S2b"
RES = RESULTS / "WP3" / "S2"


def job(args):
    kind, d = args
    f = OUT / f"{kind}_{d}.pkl"
    if f.exists():
        return kind, d, -1
    table = G.RingTable.load(RES / "ring_table.json")
    if kind == "sr_v2":
        rows = B.v2_ghost_rows(d, table)
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "scan": [r[1] for r in rows], "cls": [r[2] for r in rows],
                             "mode": [r[3] for r in rows], "n_pts": [r[4] for r in rows]})
        obj = {"meta": meta, "stats": np.vstack([r[5] for r in rows]), "X": np.vstack([r[6] for r in rows]).astype(np.float32)}
    else:
        name = json.loads((RES / "calib_choice.json").read_text())["variant"]
        calib = C.load_calib(RES / f"calibration_{name}.npz")
        rows = B.ray_rows_sr((d, table, calib))
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "scan": [r[1] for r in rows], "variant": [r[2] for r in rows],
                             "mode": [r[3] for r in rows], "band": [r[4] for r in rows], "timing": [r[5] for r in rows],
                             "n_spoofed": [r[6] for r in rows], "range_m": [r[7] for r in rows], "budget": [r[8] for r in rows]})
        obj = {"meta": meta, "stats": np.vstack([r[9] for r in rows]), "X": np.vstack([r[10] for r in rows]).astype(np.float32)}
    OUT.mkdir(parents=True, exist_ok=True)
    pd.to_pickle(obj, f)
    return kind, d, len(meta)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    todo = [(k, d) for k in ("sr_v2", "sr_ray") for d in VAL if not (OUT / f"{k}_{d}.pkl").exists()]
    todo.sort(key=lambda a: -len(scan_files(a[1])))
    print(len(todo), "jobs", flush=True)
    t0 = time.time()
    with Pool(4) as pool:
        for kind, d, n in pool.imap_unordered(job, todo):
            print(kind, d, n, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
