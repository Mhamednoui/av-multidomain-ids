"""WP2 S5 diagnostic (train/val only): the highway drive left out of the fit, as a seventh LOCO fold (unseen driving regime). Reports the L3c
alarm rate of that held-out capture at the pooled 1% window threshold of the six dyno folds, per variant. Output: results/WP2/s5_highway_fold.json
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l3_predictors as P
from WP2_S4_run import AMB
from WP2_S5_eval import CACHE, OUT, VARIANTS, calib, loco_pool, vname, win_table
from WP2_S5_run import LOCO, load_grid

HW = "ambient_highway_street_driving_long"
mu, sd = pickle.load(open(CACHE / "scale.pkl", "rb"))
grams = pickle.load(open(CACHE / "grams.pkl", "rb"))
fit_names = [n for n in AMB if n != HW]
Gc, _, g0 = load_grid(HW)
W = win_table(HW)
res = {}
for own in (False, True):
    M = P.fit_l3c(grams, fit_names, LOCO, mu, sd, own)
    for vi, v in enumerate(VARIANTS):
        if v[0] != own:
            continue
        wsl, fsl, _ = loco_pool(vname(v))
        wl, _ = calib(wsl, fsl)
        gs = P.grid_scores(M, Gc, v[1], v[2])
        ws, ok = P.window_scores(gs, W["tm"], g0, W["st"])
        res[vname(v)] = {"windows": int(ok.sum()), "alarm_rate_at_pooled_1pct": float(wl.alarms(ws[ok]).mean()), "median_score": float(np.median(ws[ok]))}
        print(vname(v), res[vname(v)], flush=True)
json.dump(res, open(OUT / "s5_highway_fold.json", "w"), indent=1)
