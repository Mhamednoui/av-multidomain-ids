"""WP1 S6 post-hoc diagnostic (NOT used for any choice): which drives cause the map_dist false alarms at the LODO threshold.
Outputs results/WP1/S6_diag.json. Run from codes_v3/: python -u -W ignore tools/WP1_S6_diag.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
from gps import map_match as MM

thr = json.loads((L.OUT / "S6_kitti.json").read_text())["calibration"]["lodo"]["lodo_transfer"]["gps.map_dist"]["pooled_threshold_raw"]
kx = L.kitti_stream()
kx = kx.join(MM.stream_features(kx, MM.RoadMap.from_osm()))
c = kx[(kx["label"] == 0)]
out = {"threshold_m": thr, "per_drive": {}}
for d, g in c.groupby("drive"):
    out["per_drive"][d] = {"part": g["part"].iloc[0], "rows": int(len(g)), "fa_at_lodo_thr": float((g["map_dist"] >= thr).mean()),
                           "median_dist": float(g["map_dist"].median()), "p99_dist": float(g["map_dist"].quantile(0.99)), "max_dist": float(g["map_dist"].max())}
    print(d, out["per_drive"][d], flush=True)
(L.OUT / "S6_diag.json").write_text(json.dumps(out, indent=1))
