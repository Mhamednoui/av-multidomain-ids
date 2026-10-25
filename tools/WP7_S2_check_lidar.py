"""WP7 S2 integrity check of the LiDAR pass: the clean scan-by-scan stream of every TEST drive (tools/WP7_S2_lidar.py, LidarRunner over the frozen domain) equals the WP6 S5b LiDAR pack
(batch: stored raw layer scores pushed through the frozen Stack / calibrators) tick by tick: combined score, 4 layer scores, own alarms. The pack ticks use floor(OXTS time - first OXTS time).
Output: results/WP7/S2_check_lidar.json.   Usage: python -u -W ignore tools/WP7_S2_check_lidar.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L
import WP7_S2_sim as M

import numpy as np
import pandas as pd


def main():
    pack = pd.read_pickle(L.WP6C / "s5b_lidar.pkl")["test"]
    ps = {s["name"]: s for s in pack["series"]}
    res = {}
    for f in sorted(L.LIDAR_DIR.glob("clean_*.pkl")):
        r = L.pickle.load(open(f, "rb"))
        d = r["drive"]
        tab = M.scan_table(r["rows"])
        p = ps[f"{d}/clean"]
        n = len(p["score"])
        lp = M.lidar_part(tab, 0.0, n)
        res[d] = {"scans": len(r["rows"]), "ticks": n, "max_score_diff": float(np.abs(lp["score"] - p["score"]).max()), "max_layer_diff": float(np.abs(lp["layers"] - p["layers"]).max()),
                  "alarm_mismatch": int((lp["dom_alarm"] != np.asarray(p["dom_alarm"], bool)).sum()), "layer_alarm_mismatch": int((lp["layer_alarm"] != np.asarray(p["layer_alarm"], bool)).sum()),
                  "compute_s_per_scan_median": float(np.median([x["ns"] for x in r["rows"]]) / 1e9)}
        print(d, res[d], flush=True)
    (L.OUT / "S2_check_lidar.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
