"""WP2 S4 probe: fit one fold and print the model summary (timing, pairs found). Usage: python tools/WP2_S4_fit_probe.py <held-out capture> [variant]"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP2_S4_run as R
from can import l2b_signals as Z

st, maps, codes = R.get_stats()
c = sys.argv[1]
h = int(sys.argv[2]) if len(sys.argv) > 2 else 0
t = time.time()
M = R.fit(st, codes, maps, [n for n in R.AMB if n != c], h)
print("fit s", round(time.time() - t, 1), flush=True)
print(json.dumps(Z.model_summary(M)), flush=True)
