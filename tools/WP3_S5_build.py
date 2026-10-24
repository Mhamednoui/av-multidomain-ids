"""WP3 S5: build the see-through tile tables in ../data_extra/cache_v3/WP3/S5/ (resumable, one pickle per drive and kind).
Usage: python -u -W ignore tools/WP3_S5_build.py <kind> [<kind> ...] [--drives 0011,0035]
Kinds: clean (all drives), att_val, att_test (attacks of every 3rd scan), ep_test (persistent episodes)."""
import json
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
from lidar import occlusion_build as B
from lidar.data import CACHE, DRIVES, TEST, VAL, cache_size_gb, scan_files
from WP3_S3_build import params

S2 = RESULTS / "WP3" / "S2"
OUT = CACHE / "S5"


def shrink(tl):
    """After the validation choice (variant_choice.json exists): keep only the columns of the chosen variant (cache size)."""
    f = RESULTS / "WP3" / "S5" / "variant_choice.json"
    if not f.exists():
        return tl
    from lidar import occlusion as O
    v = tuple(json.loads(f.read_text())["variant"])
    keep = ["scan", "oid", "range", "n_points", "ph_n", *O.variant_cols(v)]
    return tl[[c for c in keep if c in tl.columns]]


def job(args):
    kind, d = args
    f = OUT / f"{kind}_{d}.pkl"
    if f.exists():
        return kind, d, -1
    table = G.RingTable.load(S2 / "ring_table.json")
    calib = C.load_calib(S2 / "calibration_beta.npz")
    if kind == "clean":
        tl, sc = B.drive_clean(d, table, params())
    elif kind.startswith("att"):
        tl, sc = B.drive_attacks(d, table, calib, params())
    else:
        tl, sc = B.drive_episodes(d, table, calib, params())
    tl = shrink(tl)
    tl = tl.astype({c: "float32" for c in tl.columns if tl[c].dtype == "float64"})
    pd.to_pickle({"tiles": tl, "scans": sc}, f)
    return kind, d, len(sc)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    drives = None
    if "--drives" in args:
        k = args.index("--drives")
        drives = args[k + 1].split(",")
        args = args[:k] + args[k + 2:]
    todo = []
    for kind in args:
        ds = {"clean": DRIVES, "att_val": VAL, "att_test": TEST, "ep_test": TEST}[kind]
        todo += [(kind, d) for d in ds if (drives is None or d in drives) and not (OUT / f"{kind}_{d}.pkl").exists()]
    todo.sort(key=lambda a: -len(scan_files(a[1])))
    print(len(todo), "jobs", flush=True)
    t0 = time.time()
    with Pool(4) as pool:
        for kind, d, n in pool.imap_unordered(job, todo):
            print(kind, d, n, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
