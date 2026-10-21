import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP2_S5_eval import *
wsl, fsl, _ = loco_pool("d")
a = np.concatenate(wsl)
print("LOCO d nonzero windows:", np.round(np.sort(a[a > 0]), 2), "of", len(a))
for c in attack_names(1) + attack_names(2):
    if "masq" in c and "reverse" not in c: continue
    W, ws, ok, fs = l3_arrays(c, "attack", "d")
    cl = W["clean"] & (W["y"] == 0) & ok
    y = (W["y"] == 1) & ok
    print(c, "lead nonzero", np.round(ws[cl][ws[cl] > 0], 2), "attack windows: max %.2f median %.2f min %.2f" % (ws[y].max(), np.median(ws[y]), ws[y].min()) if y.any() else "")
