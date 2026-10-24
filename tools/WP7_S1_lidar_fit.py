"""WP7 S1: calibration of the INTERIM LiDAR runner (WP3 S1 retrained v2 baseline) on the NORMAL VALIDATION scans of the WP3 S1 cache (train4, drives 0011 0035 0027, cls Normal).
Test drives are never read. Output: results/WP7/frozen_lidar_interim/calibration.json, results/WP7/S1_lidar_fit.json.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_lidar_fit.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

from lidar.data import CACHE, VAL
from system.placeholder_runners import LidarInterimModel

OUT = ROOT / "results" / "WP7"


def main():
    m = LidarInterimModel(CACHE / "retrained_deployed.json")
    raws, n = [], 0
    for d in VAL:
        p = pd.read_pickle(CACHE / "train4" / f"{d}.pkl")
        keep = (p["meta"]["cls"] == "Normal").to_numpy()
        raws.append(m.raw(p["X"][keep]))
        n += int(keep.sum())
    raw = np.concatenate(raws)
    m.fit_calibration(raw)
    m.save_calibration(OUT / "frozen_lidar_interim" / "calibration.json")
    a3 = json.loads((ROOT / "results" / "WP3" / "cache" / "a3.json").read_text())
    res = {"n_val_normal_scans": n, "threshold_calibrated_score": m.threshold, "raw_threshold_equivalent": float(np.quantile(raw, 0.99)),
           "wp3_s1_val_fpr_0.01_raw_threshold": a3["ops"]["val_fpr_0.01"]["threshold"], "val_FA": float((m.cal.transform(raw) >= m.threshold).mean())}
    (OUT / "S1_lidar_fit.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
