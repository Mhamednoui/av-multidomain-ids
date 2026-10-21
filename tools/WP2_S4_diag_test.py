"""WP2 S4 post-verdict DIAGNOSTIC (descriptive only; nothing is tuned on it): which checks raise the clean-window alarms on the test ambient captures.
Usage: python tools/WP2_S4_diag_test.py <capture> [variant]  -> prints the top checks by number of alarmed windows"""
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP2_S4_run as R
from can import l2b_signals as Z

c = sys.argv[1]
h = int(sys.argv[2]) if len(sys.argv) > 2 else 0
M = pickle.load(open(R.CACHE / "models" / f"h{h}__final.pkl", "rb"))
W = pickle.load(open(R.CACHE / f"weights_m_h{h}.pkl", "rb"))
tm, ids, label, dec = R.load_capture(c)
Z.TRACE, Z.WEIGHTS = {}, W
raws = Z.score_frames(M, tm, dec, len(tm))
nm = lambda k: f"{k[0]:#x}.{k[1]}"
rows = sorted(((W.get(t, Z.W_DEFAULT) * (v > 0), v, n, W.get(t, Z.W_DEFAULT), t) for t, (n, v) in Z.TRACE.items() if v), reverse=True)
print(c, "checks firing after the baseline:", len(rows), "; in LOCO weights:", sum(1 for r in rows if r[4] in W))
for _, v, n, w, t in rows[:12]:
    key = t[0] + ":" + (nm(R.CAT.keys[t[1]]) if isinstance(t[1], int) else nm(t[1]) + "~" + nm(t[2]))
    print(f"  {key:34s} frames {v}/{n} weight {w:.1f}{'' if t in W else ' (default)'}")
