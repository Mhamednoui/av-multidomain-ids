"""WP5 S4 diagnostics on the VALIDATION split only (no test): why does the NIS CUSUM flag whole tracks of some classes, and what does the Kalman
tracker see in the classes it cannot detect? Descriptive; no threshold or choice depends on it.
Run from codes_v3/: python -I -u -W ignore tools/WP5_S4_diag.py     Output: results/WP5/s4_diag.json
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

from common.config import results_dir
from common.metrics import budget_threshold
from v2x import adapters, l3, splitting
from v2x.schema import CLASS_NAMES

OUT = results_dir("WP5")
v = adapters.load_veremi()
sp = json.loads((OUT / "splits_veremi.json").read_text())
val = splitting.rows_of(v, sp["val"])
params = json.loads((OUT / "s4_params_veremi.json").read_text())
tr = l3.Tracker(l3.KalmanParams(**params))
r = tr.run(val)
nis, chi, clo, sc = r["nis"], r["chi"], r["clo"], r["scored"]
lab = val["label"].to_numpy()
gen = lab == 0
thr_hi = np.quantile(chi[gen], 0.99)
res = {"cusum_hi_threshold_raw_approx_q99_genuine": float(thr_hi), "per_class": {}}
for c in (0, 2, 9, 11, 12, 13, 16, 17):
    m = lab == c
    al = chi >= thr_hi
    d = {"n": int(m.sum()), "frac_cusum_hi_alarm": float(al[m].mean()),
         "frac_of_alarms_with_own_nis_below_K_HI": float((nis[m & al] < l3.K_HI).mean()) if (m & al).any() else None,
         "frac_nis_above_K_HI": float((nis[m & sc] > l3.K_HI).mean()), "median_nis": float(np.median(nis[m & sc]))}
    if c in (9, 12):
        sub = val[m]
        zero = (sub["x"] == 0) & (sub["y"] == 0)
        d["frac_messages_at_origin_00"] = float(zero.mean())
        d["frac_speed0"] = float((sub["speed"] == 0).mean())
        g = sub.assign(z=zero.to_numpy()).sort_values(["track", "t"]).groupby("track")["z"]
        d["frac_tracks_all_origin"] = float(g.all().mean())
        d["frac_tracks_origin_then_real"] = float((g.first() & ~g.last()).mean())
        d["frac_tracks_real_then_origin"] = float((~g.first() & g.last()).mean())
    res["per_class"][f"{c:02d}_{CLASS_NAMES[c]}"] = d
# genuine stationary messages: how exact are repeated positions?
g = val[gen].sort_values(["track", "t"])
same = g["track"].to_numpy()[1:] == g["track"].to_numpy()[:-1]
dx = np.hypot(np.diff(g["x"].to_numpy()), np.diff(g["y"].to_numpy()))[same]
slow = (g["speed"].to_numpy()[1:] < 0.5)[same]
res["genuine_standstill_pairs"] = {"n": int(slow.sum()), "frac_displacement_exactly_zero": float((dx[slow] == 0).mean()),
                                   "median_displacement_m": float(np.median(dx[slow])), "q90_displacement_m": float(np.quantile(dx[slow], 0.9))}
a = val[lab == 9].sort_values(["track", "t"])
same = a["track"].to_numpy()[1:] == a["track"].to_numpy()[:-1]
dx = np.hypot(np.diff(a["x"].to_numpy()), np.diff(a["y"].to_numpy()))[same]
slow = (a["speed"].to_numpy()[1:] < 0.5)[same]
res["eventual_stop_standstill_pairs"] = {"n": int(slow.sum()), "frac_displacement_exactly_zero": float((dx[slow] == 0).mean())}
(OUT / "s4_diag.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
