"""WP1 S5 post-hoc diagnostic (explains the Doppler / meaconing numbers; nothing is chosen from it): run-level detection of the primary
L2d layer by attack severity, using the LODO raw-equivalent threshold stored by the test pass (results/WP1/S5_kitti.json) on the test runs.
Severity = final velocity offset (doppler_spoof, m/s) or final delay (meaconing, s) or pull-off (drift m/s, accel_drift m/s^2).
Output: results/WP1/S5_severity.json. Run from codes_v3/: python -u -W ignore tools/WP1_S5_severity.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
from gps import lidar_odom as LO

BINS = {"doppler_spoof": (0.2, 1.0, 2.0, 3.01), "meaconing": (0.5, 1.0, 2.0, 3.01), "drift": (0.2, 0.5, 1.0, 2.01), "accel_drift": (0.05, 0.15, 0.3, 0.51)}


def main():
    kit = json.loads((L.OUT / "S5_kitti.json").read_text())
    prim = kit["dev_selection"]["primary_layer_name"]
    col = {"gps.lidar_z_1": "lid_z_1", "gps.lidar_z_3": "lid_z_3"}[prim]
    thr = kit["calibration"]["lodo"]["per_layer"][prim]["threshold_raw_equivalent"]
    kx = L.kitti_stream()
    te = kx[kx["part"] == "test"]
    te = te.join(LO.stream_features(te))
    flag = te[col].to_numpy() >= thr
    d = te.assign(f=flag)
    res = {"layer": prim, "threshold_raw_equivalent": thr, "note": "post-hoc diagnostic on the test runs, nothing chosen from it", "bins": {}}
    for a, edges in BINS.items():
        res["bins"][a] = []
        runs = d[(d["attack"] == a)].groupby("run", sort=False)
        rows = [(g["severity"].iloc[0], bool(g.loc[g["label"] == 1, "f"].any()), int((g["label"] == 1).sum())) for _, g in runs]
        for lo, hi in zip(edges[:-1], edges[1:]):
            sel = [(s, hit, n) for s, hit, n in rows if lo <= s < hi]
            res["bins"][a].append({"severity_range": [lo, hi], "runs": len(sel), "detected": float(np.mean([h for _, h, _ in sel])) if sel else None,
                                   "median_attacked_fixes": float(np.median([n for _, _, n in sel])) if sel else None})
    (L.OUT / "S5_severity.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
