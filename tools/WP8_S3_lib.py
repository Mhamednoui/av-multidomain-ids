"""WP8 S3 shared code: the V31 drive split, per-scan statistic records of the v3.1 LiDAR pipeline, and the analysis helpers.

Statistics (lidar.fast.ScanStats) of one scan: L1 statistics (5), L2c / L2d pair statistics (13), tile table of the v3.1 clustering and of
the exact v3 clustering. Everything the layers, combiners and thresholds need is computed from these records (tools/WP8_S3_build.py writes
them per drive to results/WP8/S3/parts/; tools/WP8_S3_eval.py scores them). Only V31 train / V31_val drives are ever opened (assert_not_h31).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP8_lib import assert_not_h31                                                    # noqa: E402
from common.config import RESULTS                                                     # noqa: E402
from lidar import calibration as C                                                    # noqa: E402
from lidar import geometry as G                                                       # noqa: E402

PARTS = ROOT / "results" / "WP8" / "S3" / "parts"
SCORES = ROOT / "results" / "WP8" / "scores" / "S3"
V31 = json.loads((ROOT / "locks" / "V31_val.json").read_text())["domains"]["kitti_vehicle_block"]
TRAIN, VAL = list(V31["train"]), list(V31["val"])
DRIVES = sorted(TRAIN + VAL)
PAIR_KEYS = ["miss_w10", "miss_g10", "miss_w20", "miss_g20", "miss_z20", "miss_tot", "app_tot", "app_cc", "fix_tot", "fix_cc",
             "van_tot", "van_cc", "disp"]
L1_KEYS = list(G.STAT_NAMES)
PRM = {"ground": "grid", "h0": 0.3, "e0": 0.4, "e1": 0.0, "vox": 0.1}               # v3 segment_params + the v3.1 voxel flag
ATTACKS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof", "cmp_boxcloud",
           "cmp_mradd_near", "cmp_mradd_far"]
HEADLINE = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof"]
EP_LEN = 30
PD_EP_PER_DRIVE = 3


def guard(drives):
    assert_not_h31([f"2011_09_26_drive_{d}" for d in drives])


def table():
    return G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")


def calib():
    return C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")


def row_of(l1, pair):
    r = dict(zip(L1_KEYS, [float(x) for x in l1]))
    r.update({k: (float(pair[k]) if pair is not None else np.nan) for k in PAIR_KEYS})
    return r


def tile_frame(tl, si):
    t = tl[["range", "n_points", "int_mean"]].astype(np.float32).copy()
    t.insert(0, "si", np.int32(si))
    return t


def write_atomic(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    pd.to_pickle(obj, tmp)
    tmp.replace(path)
