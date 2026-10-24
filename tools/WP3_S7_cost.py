"""WP3 S7: scoring cost per scan of L3 (object scoring only; segmentation 0.7 s/scan is S3's) and L4 (describe + XGBoost), measured on validation scans.
Writes results/WP3/S7/cost.json. Usage: python -u -W ignore tools/WP3_S7_cost.py"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import learned as L
from lidar import learned_eval as LE
from lidar import learned_l4 as L4
from lidar.data import load, scan_files
from lidar.features import describe, temporal

with open(L4.ROOT / "models" / "l3_final.pkl", "rb") as fh:
    z = pickle.load(fh)
with open(L4.ROOT / "models" / "l4_final.pkl", "rb") as fh:
    m4 = pickle.load(fh)
F, S = LE.load_l3("clean", ["0011"])
sc = F["scan"].astype(str).to_numpy()
ids = np.unique(sc)[:50]
t = time.time()
for s in ids:
    z["model"].score(F.loc[sc == s, z["feats"]].to_numpy(np.float32))
l3_ms = 1000 * (time.time() - t) / len(ids)
files = scan_files("0011")[:21]
t = time.time()
prev = describe(load(files[0]))
rows = []
for f in files[1:]:
    cur = describe(load(f))
    rows.append(np.r_[cur, temporal(cur, prev)])
    prev = cur
d_ms = 1000 * (time.time() - t) / 20
t = time.time()
for r in rows:
    L4.attack_score(m4, r[None])
p_ms = 1000 * (time.time() - t) / 20
out = {"L3_object_scoring_ms_per_scan": l3_ms, "L4_descriptor_ms_per_scan": d_ms, "L4_predict_ms_per_scan": p_ms}
(RESULTS / "WP3" / "S7" / "cost.json").write_text(json.dumps(out, indent=1))
print(out)
