"""WP6 S1 diagnostics (train + val only, after the A3 verdict on val): per-group residual spread and bias, sensor rates.

Purpose: explain why the pre-registered SigmaModel (constant bias + sqrt(a^2 + (b v)^2)) is not honest on val
(comma: val z std 0.70; KITTI: CAN pairs). Prints per route / drive: n, median r, std r, robust std (1.4826 MAD), GNSS rate.
Output: results/WP6/s1_diag.json. Test groups are not read.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DATA_EXTRA, results_dir  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"


def per_group(tab, gcol):
    out = []
    for (pair, q, g), d in tab.groupby(["pair", "quantity", gcol]):
        r = d["r"].to_numpy()
        out.append({"pair": f"{pair} {q}", "group": g, "part": d["part"].iloc[0], "n": int(len(r)), "median_r": float(np.median(r)),
                    "std_r": float(r.std()), "robust_std_r": float(1.4826 * np.median(np.abs(r - np.median(r)))),
                    "median_v": float(np.median(d["v"])), "rel_bias": float(np.median(r / np.maximum(d["v"], 1.0)))})
    return out


def main():
    tab = pd.read_pickle(CACHE / "s1_comma_tab.pkl")
    tab = tab[tab["part"] != "test"]
    c = pickle.load(open(CACHE / "s1_comma_routes.pkl", "rb"))
    rates = {n: {"gnss_hz": float(len(d["gnss_t"]) / (d["gnss_t"][-1] - d["gnss_t"][0])), "gyro_hz": float(len(np.unique(d["gyro_t"])) / (d["gyro_t"][-1] - d["gyro_t"][0]))}
             for n, d in c["data"].items() if c["part"][n] != "test"}
    com = per_group(tab, "route")
    for r in com:
        r.update(rates[r["group"]])
    k = pickle.load(open(CACHE / "s1_kitti.pkl", "rb"))["tab"]
    kit = per_group(k[k["part"] != "test"], "drive")
    res = {"comma": com, "kitti": kit}
    results_dir("WP6").joinpath("s1_diag.json").write_text(json.dumps(res, indent=1))
    df = pd.DataFrame(com)
    print(df.round(3).to_string())
    print(pd.DataFrame(kit).query("pair.str.contains('can') or pair.str.contains('imu-lidar')", engine="python").round(3).to_string())


if __name__ == "__main__":
    main()
