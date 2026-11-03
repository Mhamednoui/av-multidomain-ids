"""WP8 S3b: equality of two saved per-scan score files (numba run vs numpy run of the same frozen_lidar31): alarms, layer raw scores, stat, score.
Run: python -I tools/WP8_S3b_compare.py <numba_tag> <numpy_tag> -> results/WP8/S3b/equality_<numba>_vs_<numpy>.json (all scans and the first 1,113 scans of S3)"""
import json, sys
from pathlib import Path
import numpy as np
SC = Path(__file__).resolve().parents[1] / "results" / "WP8" / "scores" / "S3b"
OUT = SC.parents[1] / "S3b"
a, b = (np.load(SC / f"lidar_val_{t}.npz", allow_pickle=True) for t in sys.argv[1:3])
assert (a["drive"] == b["drive"]).all() and (a["i"] == b["i"]).all()
def cmp(m):
    r = {"n": int(m.sum()), "alarm_differences": int((a["alarm"][m] != b["alarm"][m]).sum())}
    for k in ("L1", "L2a", "L2c", "L2d", "stat", "score"):
        r["max_abs_diff_" + k] = float(np.abs(a[k][m] - b[k][m]).max())
    r["max_abs_diff_all"] = max(v for k, v in r.items() if k.startswith("max_abs"))
    r["met"] = bool(r["alarm_differences"] == 0 and r["max_abs_diff_all"] <= 1e-9)
    return r
n = len(a["i"]); first = np.zeros(n, bool); first[:1113] = True
res = {"numba": sys.argv[1], "numpy": sys.argv[2], "all_scans": cmp(np.ones(n, bool)), "first_1113_scans": cmp(first)}
(OUT / f"equality_{sys.argv[1]}_vs_{sys.argv[2]}.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
