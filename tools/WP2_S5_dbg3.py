import sys, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP2_S5_eval import *
s = json.load(open(OUT / "s5_select.json"))
print("L3d", s["l3d"]["loco_fa_per_fold"])
for vi in ["5"]:
    v = s["variants"][vi]
    print(vi, v["name"], "thr", v["window_threshold"], {k[8:20]: round(x, 3) for k, x in v["loco_fa_per_fold"].items()})
    for c, r in v["attack_val"].items():
        print("   ", c, "l3c rec", round(r["l3c_recall"], 2), "union", r["union_recall"], "leadFA", r["l3c_lead_fa"])
    wsl, fsl, per = loco_pool(v["name"])
    a = np.concatenate(wsl)
    print("   pool q", np.round(np.quantile(a, [.5, .9, .98, .99, .995, 1]), 2))
    wl, fl = calib(wsl, fsl)
    wsd, fsd, _ = loco_pool("d"); wd, fd = calib(wsd, fsd)
    for c in attack_names(1) + attack_names(2):
        r, al, ok, ws, W, fs = capture_eval(c, "attack", v["name"], wl, fl)
        rd = capture_eval(c, "attack", "d", wd, fd)[0]
        print("   lead", c, "clean", r["clean_windows"], "L3c FA", r["false_alerts_clean"], "L3d FA", rd["false_alerts_clean"], "max clean score", round(float(ws[W['clean'] & ok].max()), 1) if (W['clean'] & ok).any() else None, "thr", round(float(wl.threshold),3))
