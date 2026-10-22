"""KITTI raw velodyne data layer for WP3: drive split, scan files, groups.

Inputs: 23 drives of 2011_09_26 (drives 0001, 0015 under ../codes/data/Depth, the other 21
under ../data_extra/kitti_raw), read only. Outputs: scan paths, point arrays (N x 4: x y z
intensity in [0, 1]), group ids "<drive>/<file>", the drive split of WP1/v2 (TEST 7, VAL 3).
Derived arrays are cached under ../data_extra/cache_v3/WP3/ (gitignored, <= 5 GB).
References: Geiger et al., KITTI (IJRR 2013). Copied from ../codes_v2/lidar/train.py.
"""
import json
from pathlib import Path

import numpy as np

from common.config import DATA, DATA_EXTRA, RESULTS

CACHE = DATA_EXTRA / "cache_v3" / "WP3"
SCENE = {"0001": "city", "0002": "city", "0005": "city", "0011": "city", "0013": "city", "0017": "city",
         "0048": "city", "0060": "city", "0095": "city", "0106": "city", "0113": "city",
         "0019": "residential", "0020": "residential", "0035": "residential", "0039": "residential",
         "0046": "residential", "0079": "residential",
         "0015": "road", "0027": "road", "0028": "road", "0029": "road", "0052": "road", "0070": "road"}
TEST = ["0001", "0005", "0095", "0039", "0079", "0028", "0052"]
VAL = ["0011", "0035", "0027"]
DRIVES = sorted(SCENE)
FRAME_DT = 0.1032      # s between KITTI frames


def part_of(d):
    return "test" if d in TEST else "val" if d in VAL else "train"


def drives_of(part):
    return [d for d in DRIVES if part_of(d) == part]


def drive_dir(d):
    name = f"2011_09_26_drive_{d}_sync"
    root = DATA / "Depth" if d in ("0001", "0015") else DATA_EXTRA / "kitti_raw"
    return root / name / "2011_09_26" / name / "velodyne_points" / "data"


def scan_files(d):
    return sorted(drive_dir(d).glob("*.bin"))


def group_id(d, path):
    return f"{d}/{Path(path).name}"


def load(path):
    return np.fromfile(path, dtype=np.float32).reshape(-1, 4)


def split_table():
    """{part: {drives, groups}} with groups = '<drive>/<file>' of every scan."""
    out = {}
    for part in ("train", "val", "test"):
        ds = drives_of(part)
        out[part] = {"drives": ds, "groups": [group_id(d, f) for d in ds for f in scan_files(d)]}
    return out


def save_split(path=None):
    path = Path(path) if path else RESULTS / "WP3" / "split.json"
    t = split_table()
    allg = [g for p in t.values() for g in p["groups"]]
    assert len(allg) == len(set(allg)), "a scan group appears twice"
    for a in t:
        for b in t:
            assert a == b or not set(t[a]["drives"]) & set(t[b]["drives"]), "drive on two sides"
    meta = {"rule": "by drive (WP1 / v2 split): TEST 7 drives, VAL 3, rest train; group = <drive>/<file>",
            "scene": SCENE, "frame_dt_s": FRAME_DT,
            "parts": {p: {"drives": v["drives"], "scans": len(v["groups"]), "groups": v["groups"]}
                      for p, v in t.items()}}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta))
    return meta


def cache_size_gb():
    return sum(f.stat().st_size for f in CACHE.rglob("*") if f.is_file()) / 1e9 if CACHE.exists() else 0.0
