"""WP3 S5: cost of the see-through tile table per scan (segmentation excluded) on 10 validation scans -> results/WP3/S5/runtime.json."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import RESULTS
from lidar import geometry as G
from lidar import occlusion as O
from lidar import segment as S
from lidar.data import load, scan_files
from WP3_S3_build import params

t = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
rank = O.elevation_rank(t)
ts, tseg = [], []
for f in scan_files("0011")[100:110]:
    pts = load(f)
    a = time.time()
    _, lab, _ = S.segment(pts, t, params(), return_labels=True)
    b = time.time()
    k = t.assign(pts)["k"]
    O.tile_table(pts, lab, k, rank)
    ts.append(time.time() - b)
    tseg.append(b - a)
r = {"occlusion_ms_per_scan_incl_ring_assign": 1000 * float(np.mean(ts)), "segmentation_ms_per_scan": 1000 * float(np.mean(tseg))}
(RESULTS / "WP3" / "S5" / "runtime.json").write_text(json.dumps(r, indent=1))
print(r)
