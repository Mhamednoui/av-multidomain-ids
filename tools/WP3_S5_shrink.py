"""WP3 S5: rewrite the cached tile tables keeping only the columns of the variant chosen on validation (cache size). Run after WP3_S5_dev.py."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lidar.data import CACHE
from WP3_S5_build import shrink

for f in sorted((CACHE / "S5").glob("*.pkl")):
    z = pd.read_pickle(f)
    n0 = len(z["tiles"].columns)
    z["tiles"] = shrink(z["tiles"])
    pd.to_pickle(z, f)
    print(f.name, n0, "->", len(z["tiles"].columns), flush=True)
