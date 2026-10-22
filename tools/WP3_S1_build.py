"""WP3 S1: build and cache the descriptor tables (resumable, one file per table and drive).

Tables (cache: ../data_extra/cache_v3/WP3/<table>/<drive>.pkl):
  train4   v2 4-class rows (all 23 drives)           lidar.build.drive_rows
  rayv2    v2 ray-cast test rows (val + test)         lidar.build.v2_raycast_rows
  rayw3    WP3 phantoms near/far (val + test)         lidar.build.wp3_phantom_rows
  episodes persistent episodes (val + test)           lidar.build.episode_rows
Run from codes_v3/: python -u -W ignore tools/WP3_S1_build.py [table ...]
"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lidar import build
from lidar.data import CACHE, DRIVES, SCENE, VAL, TEST, cache_size_gb, part_of, scan_files

LIMIT_GB = 5.0
DRAWS = {"val": 3, "test": 2}
N_RAY, EP_LEN = 3, 40


def frame(rows, kind):
    X = np.vstack([r[-1] for r in rows]).astype(np.float32)
    if kind == "train4":
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "scan": [r[1] for r in rows],
                             "cls": [r[2] for r in rows], "mode": [r[3] for r in rows]})
    elif kind == "rayv2":
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "scan": [r[1] for r in rows], "mode": [r[2] for r in rows],
                             "timing": [r[3] for r in rows], "n_spoofed": [r[4] for r in rows],
                             "range_m": [r[5] for r in rows]})
    elif kind == "rayw3":
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "scan": [r[1] for r in rows], "mode": [r[2] for r in rows],
                             "band": [r[3] for r in rows], "timing": [r[4] for r in rows],
                             "n_spoofed": [r[5] for r in rows], "range_m": [r[6] for r in rows],
                             "budget": [r[7] for r in rows]})
    else:
        meta = pd.DataFrame({"drive": [r[0] for r in rows], "kind": [r[1] for r in rows], "name": [r[2] for r in rows],
                             "draw": [r[3] for r in rows], "k": [r[4] for r in rows], "scan": [r[5] for r in rows],
                             "range_m": [r[6] for r in rows]})
    return meta, X


def job(args):
    kind, d = args
    if kind == "train4":
        rows = build.drive_rows(d)
    elif kind == "rayv2":
        rows = build.v2_raycast_rows(d)
    elif kind == "rayw3":
        rows = build.wp3_phantom_rows(d)
    else:
        rows = build.episode_rows((d, DRAWS[part_of(d)], N_RAY, EP_LEN))
    meta, X = frame(rows, kind)
    out = CACHE / kind / f"{d}.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"meta": meta, "X": X}, out)
    return kind, d, len(meta)


def main():
    kinds = sys.argv[1:] or ["train4", "rayv2", "rayw3", "episodes"]
    todo = []
    for kind in kinds:
        ds = DRIVES if kind == "train4" else VAL + TEST
        todo += [(kind, d) for d in ds if not (CACHE / kind / f"{d}.pkl").exists()]
    todo.sort(key=lambda a: -len(scan_files(a[1])))
    print(f"{len(todo)} jobs; cache {cache_size_gb():.2f} GB", flush=True)
    t0 = time.time()
    with Pool(4) as pool:
        for kind, d, n in pool.imap_unordered(job, todo):
            assert cache_size_gb() < LIMIT_GB, "cache over 5 GB"
            print(f"{kind} {d}: {n} rows ({time.time() - t0:.0f}s, cache {cache_size_gb():.2f} GB)", flush=True)


if __name__ == "__main__":
    main()
