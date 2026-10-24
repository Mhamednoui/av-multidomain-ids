"""WP3 S4: build object tables (chosen segmentation variant) in ../data_extra/cache_v3/WP3/S4/<variant>/ (resumable, one pickle per drive and kind).
Usage: python -u -W ignore tools/WP3_S4_build.py <kind> [<kind> ...] [--drives 0011,0035]
Kinds: clean (all drives, L1 statistics for val / test drives), att_val, att_test (attack tables of every 3rd scan), ep_test (persistent episodes).
The variant is read from results/WP3/S4/variant_choice.json."""
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
from lidar import s4_build as B
from lidar.data import CACHE, DRIVES, TEST, VAL, cache_size_gb, part_of, scan_files
from WP3_S3_build import params

S2 = RESULTS / "WP3" / "S2"
CH = json.loads((RESULTS / "WP3" / "S4" / "variant_choice.json").read_text())
OUT = CACHE / "S4" / (CH["variant"] + "_t")


def prm():
    return dict(params(), **CH["params"])


def job(args):
    kind, d = args
    f = OUT / f"{kind}_{d}.pkl"
    if f.exists():
        return kind, d, -1
    table = G.RingTable.load(S2 / "ring_table.json")
    calib = C.load_calib(S2 / "calibration_beta.npz")
    if kind == "clean":
        o, s, tl = B.drive_clean(d, table, prm(), l1=part_of(d) != "train")
    elif kind.startswith("att"):
        o, s, tl = B.drive_attacks(d, table, calib, prm())
    else:
        o, s, tl = B.drive_episodes(d, table, calib, prm())
    pd.to_pickle({"objs": o, "scans": s, "tiles": tl}, f)
    return kind, d, len(s)


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
    print(len(todo), "jobs", CH, flush=True)
    t0 = time.time()
    with Pool(4) as pool:
        for kind, d, n in pool.imap_unordered(job, todo):
            assert cache_size_gb() < 3.0
            print(kind, d, n, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
