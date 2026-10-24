"""WP3 S9: the world-fixed episodes rebuilt for L1 / L2a (lidar/s9_build.py) are the SAME attacked scans as the S6 episodes (n_inj equal).
Usage: python -u -W ignore tools/WP3_S9_check_epw.py [val|test]  -> results/WP3/S9/check_epw_<split>.json"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP3_S9_lib as L
from WP3_S6_lib import load as s6load
from common.config import RESULTS
from lidar.data import TEST, VAL

split = sys.argv[1] if len(sys.argv) > 1 else "val"
drives = VAL if split == "val" else TEST
_, sc = L.load_epw(split, drives)
s6 = s6load(f"epw_{split}", drives)
m = sc[["scan", "n_inj_s9"]].merge(s6[["scan", "n_inj"]], on="scan", how="inner")
res = {"scans_s9": int(len(sc)), "scans_s6": int(len(s6)), "matched": int(len(m)), "n_inj_equal": int((m.n_inj_s9 == m.n_inj).sum())}
print(res)
(RESULTS / "WP3" / "S9" / f"check_epw_{split}.json").write_text(json.dumps(res))
