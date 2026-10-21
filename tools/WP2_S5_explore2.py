"""WP2 S5 exploration (train/val only): reverse bit vs gear signals in time."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP2_S4_run import *
from can import l1_exp as E
R = (0xd0, 2); GS = [(0x295, 0), (0xc0, 0), (0x274, 14)]
def summarize(name):
    z = np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (name + ".npz"))
    tm, ids, label, dec = load_capture(name)
    rr, V = dec[0xd0]
    flag = V[:, 2]
    out = {"name": name, "dur": round(float(tm[-1]-tm[0]),1), "first_inj": E.first_injected({"t": z["t"], "label": label})}
    out["flag_vals"] = np.unique(flag, return_counts=True)
    for g in GS:
        r2, V2 = dec[g[0]]
        out[f"{g[0]:#x}.{g[1]}"] = np.unique(V2[:, g[1]], return_counts=True)
    # times where gear 0x295.0 takes each value and flag
    t_f = tm[rr]
    r2, V2 = dec[0x295]
    g = V2[:, 0]
    gh = np.array([g[max(np.searchsorted(tm[r2], t, side="right") - 1, 0)] for t in t_f[::10]])
    fl = flag[::10]
    comb = {}
    for a, b in zip(gh, fl): comb[(a, b)] = comb.get((a, b), 0) + 1
    out["gear295 x flag (per 10 frames)"] = comb
    return out
for n in sys.argv[1:]:
    for k, v in summarize(n).items(): print(k, v)
    print()
