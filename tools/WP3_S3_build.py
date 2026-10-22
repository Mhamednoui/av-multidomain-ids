"""WP3 S3: object tables of every clean scan (train, val, test drives) with the chosen parameters (results/WP3/S3/choice.json).
One pickle per drive in ../data_extra/cache_v3/WP3/S3/objects_<drive>.pkl = {"objects": DataFrame (drive, idx, scan + COLUMNS),
"scans": DataFrame (drive, idx, scan, n_pts, n_obj, ground_frac, secs)}. Resumable. Computing tables on test scans is not a test
evaluation (no choice or model touches them)."""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import geometry as G
from lidar import segment as S
from lidar.data import CACHE, DRIVES, cache_size_gb, group_id, load, scan_files

OUT = CACHE / "S3"
TABLE = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")


def params():
    c = json.loads((RESULTS / "WP3" / "S3" / "choice.json").read_text())
    return {"ground": c["ground"]["kind"], "h0": c["ground"]["h0"], "e0": c["cluster"]["e0"], "e1": c["cluster"]["e1"]}


def job(d):
    f = OUT / f"objects_{d}.pkl"
    if f.exists():
        return d, -1
    prm = params()
    objs, scans = [], []
    for i, b in enumerate(scan_files(d)):
        pts = load(b)
        t0 = time.time()
        tab, _, h = S.segment(pts, TABLE, prm, return_labels=True)
        secs = time.time() - t0
        near = np.hypot(pts[:, 0], pts[:, 1]) < 40.0
        g = group_id(d, b)
        tab.insert(0, "scan", g)
        tab.insert(0, "idx", i)
        tab.insert(0, "drive", d)
        objs.append(tab)
        scans.append(dict(drive=d, idx=i, scan=g, n_pts=len(pts), n_obj=len(tab), ground_frac=float((h[near] <= prm["h0"]).mean()), secs=secs))
    OUT.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"objects": pd.concat(objs, ignore_index=True), "scans": pd.DataFrame(scans), "params": prm}, f)
    return d, len(scans)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    todo = sorted([d for d in DRIVES if not (OUT / f"objects_{d}.pkl").exists()], key=lambda d: -len(scan_files(d)))
    print(len(todo), "drives", params(), flush=True)
    t0 = time.time()
    with Pool(4) as pool:
        for d, n in pool.imap_unordered(job, todo):
            assert cache_size_gb() < 3.0
            print(d, n, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
