"""WP2 S5 post-verdict diagnostic (DESCRIPTIVE, no design choice): what raises the false alarms of L3c and of L2b relations-only on the clean test drives.
Output: results/WP2/s5_diag_test.json"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l2b_signals as Z
from can import l3_predictors as P
from WP2_S4_run import CAT, sparse_load
from WP2_S5_eval import CACHE, OUT, VARIANTS, calib, loco_pool, vname, win_table
from WP2_S5_report import SKIP_SEC, l2b_calibration
from WP2_S5_run import load_grid

vi = 5
wsl, fsl, _ = loco_pool(vname(VARIANTS[vi]))
wc, _ = calib(wsl, fsl)
w2, _ = l2b_calibration()
M = pickle.load(open(CACHE / "models" / "final.pkl", "rb"))[True]
nm = lambda j: f"{CAT.cont[j][0]:#x}.{CAT.cont[j][1]}"
res = {}
for c in ["ambient_dyno_drive_benign_anomaly", "ambient_dyno_drive_extended_short", "ambient_highway_street_driving_diagnostics"]:
    Gc, _, g0 = load_grid(c)
    sc, am = P.grid_scores(M, Gc, 0.0, "cusum", return_argmax=True)
    W = win_table(c)
    ws, ok = P.window_scores(sc, W["tm"], g0, W["st"])
    al = wc.alarms(ws) & ok & (np.floor(W["tm"][W["st"]]) >= SKIP_SEC)
    sec = np.floor(W["tm"][W["st"]]).astype(int)
    g = g0 + P.GRID_DT * np.arange(len(sc))
    gsec = np.floor(g).astype(int)
    alsec = set(sec[al])
    steps = np.array([s in alsec for s in gsec])
    ids, cnt = np.unique(am[steps & (sc > wc.threshold * 0 + 0)], return_counts=True) if steps.any() else ([], [])
    o = np.argsort(-np.asarray(cnt))[:6]
    r = {"l3c_alarm_windows": int(al.sum()), "l3c_top_signals_in_alarmed_steps": {nm(ids[i]): int(cnt[i]) for i in o}}
    comb_types = sparse_load(CACHE / "l2b_test" / (c + ".npz"))
    comb = Z.combine(comb_types)
    a2 = w2.alarms(Z.window_max(comb, W["st"])) & (sec >= SKIP_SEC)
    r["l2b_rel_alarm_windows"] = int(a2.sum())
    r["l2b_rel_dominant_type_share"] = {t: float((Z.window_max(comb_types[t].astype(np.float64), W["st"])[a2] >= Z.window_max(comb, W["st"])[a2] - 1e-9).mean()) if a2.any() else None for t in Z.TYPES}
    res[c] = r
    print(c, r, flush=True)
json.dump(res, open(OUT / "s5_diag_test.json", "w"), indent=1)
