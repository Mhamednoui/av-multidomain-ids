"""WP2 S4 diagnostic (TRAIN/VAL attack captures, lead before the first injected frame): which weighted checks fire. Usage: python tools/WP2_S4_trace_attack.py <capture> [variant]"""
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
W = pickle.load(open(R.CACHE / f"weights_h{h}.pkl", "rb"))
tm, ids, label, dec = R.load_capture(c)
Z.TRACE, Z.WEIGHTS = {}, W
raws = Z.score_frames(M, tm, dec, len(tm))
nm = lambda k: f"{k[0]:#x}.{k[1]}"
lead = np.ones(len(tm), bool)
idx = np.flatnonzero(label)
if len(idx):
    lead[idx[0] - 50:] = False
    print("first injected frame", idx[0], "of", len(tm))
sc = Z.combine(raws)
print("lead frames", lead.sum(), "score q50/q99/max", np.quantile(sc[lead], [0.5, 0.99, 1]).round(2), "frac > 10 bits", (sc[lead] > 10).mean().round(3))
rows = sorted(((v / max(n, 1), v, n, W.get(t, Z.W_DEFAULT), t) for t, (n, v) in Z.TRACE.items() if v), reverse=True)
for fr, v, n, w, t in rows[:25]:
    key = t[0] + ":" + (nm(R.CAT.keys[t[1]]) if isinstance(t[1], int) else nm(t[1]) + "~" + nm(t[2]))
    print(f"{key:36s} frac {fr:.3f} n {n} weight {w:.1f} {'(default)' if t not in W else ''}")
