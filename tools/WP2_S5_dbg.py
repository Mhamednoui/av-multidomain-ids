import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP2_S5_eval import *
s = json.load(open(OUT / "s5_select.json"))
v = s["variants"]["0"]
print(v["window_threshold"], v["frame_threshold"])
print(json.dumps(v["attack_val"], indent=0)[:1500])
print(s["l3d"]["window_threshold"], s["l3d"]["loco_fa_per_fold"])
wsl, fsl, per = loco_pool("cross_r0.0_max")
a = np.concatenate(wsl); print("loco window pool", len(a), np.quantile(a, [.5, .9, .99, 1]))
for c in ["max_speedometer_attack_2_masquerade", "correlated_signal_attack_2_masquerade"]:
    W, ws, ok, fs = l3_arrays(c, "attack", "cross_r0.0_max")
    print(c, "first inj", W["fi"], "tm0", W["tm"][0], "windows", len(ws), np.round(ws, 1))
    print(W["y"])
