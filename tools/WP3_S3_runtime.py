"""WP3 S3: single-process runtime of segment() on 40 validation scans (the cached secs came from 4 parallel workers)."""
import json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import geometry as G, segment as S
from lidar.data import VAL, load, scan_files
from WP3_S3_build import params
T = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
prm = params()
ts = []
for d in VAL:
    for b in scan_files(d)[::14][:14]:
        p = load(b); t = time.time(); S.segment(p, T, prm); ts.append(time.time() - t)
r = {"n": len(ts), "median_s": float(np.median(ts)), "p90_s": float(np.quantile(ts, 0.9))}
(RESULTS / "WP3" / "S3" / "runtime_single.json").write_text(json.dumps(r)); print(r)
