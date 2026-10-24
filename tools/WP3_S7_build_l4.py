"""WP3 S7: L4 descriptor rows (v2 descriptor + scan-to-scan features) in ../data_extra/cache_v3/WP3/S7/l4_<kind>_<drive>.pkl.
Kinds: tr (training / validation attack rows: train + val drives, every 2nd scan, 6 physical attacks), ev (S4 evaluation attack set, val
+ test drives, 9 attacks), ep (S4 sensor-fixed persistent episodes, test drives). Resumable. Usage:
python -u -W ignore tools/WP3_S7_build_l4.py [tr ev ep] [--drives 0048,0002]"""
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lidar import learned_l4 as L4
from lidar.data import TEST, VAL, cache_size_gb, drives_of, scan_files

KINDS = {"tr": drives_of("train") + drives_of("val"), "ev": VAL + TEST, "ep": TEST}
FUN = {"tr": L4.train_rows, "ev": L4.eval_rows, "ep": L4.episode_rows}


def job(args):
    kind, d = args
    f = L4.ROOT / f"l4_{kind}_{d}.pkl"
    if f.exists():
        return kind, d, -1, 0.0
    t0 = time.time()
    meta, X = FUN[kind](d)
    pd.to_pickle({"meta": meta, "X": X}, f)
    return kind, d, len(meta), time.time() - t0


if __name__ == "__main__":
    L4.ROOT.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    drives = None
    if "--drives" in args:
        k = args.index("--drives")
        drives = args[k + 1].split(",")
        args = args[:k] + args[k + 2:]
    kinds = args or list(KINDS)
    todo = [(k, d) for k in kinds for d in KINDS[k] if drives is None or d in drives]
    todo.sort(key=lambda a: -len(scan_files(a[1])))
    print(len(todo), "jobs", flush=True)
    t0 = time.time()
    with Pool(3) as pool:
        for kind, d, n, sec in pool.imap_unordered(job, todo):
            print(kind, d, n, f"{sec:.0f}s total {time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
