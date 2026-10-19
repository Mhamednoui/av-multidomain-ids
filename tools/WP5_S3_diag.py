"""WP5 S3 post-hoc diagnostics (NOT part of the acceptance rule, nothing here is used to choose a threshold or a layer).

Run from codes_v3/: python -I -u -W ignore tools/WP5_S3_diag.py   -> results/WP5/s3_diag.json
 A. VeReMi mechanisms on VALIDATION rows only (classes 11, 13, 16; held-out 17 is not looked at): why do the consecutive-beacon checks
    fire on them? (median dt, displacement, speed x dt, pos_speed residual per class vs genuine).
 B. Tampa: why does the map check not transfer? Distance to the nearest drivable way for genuine VALIDATION and TEST messages, per
    test vehicle; and the false-alarm rate of the union of the non-map L2 checks on genuine test messages (descriptive only).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

from common.metrics import budget_threshold
from v2x import adapters, l2, splitting
import WP5_S3_l2 as m

OUT = m.OUT
res = {}

# ---- A: VeReMi mechanisms on validation
v = adapters.load_veremi()
sp = json.loads((OUT / "splits_veremi.json").read_text())
val = splitting.rows_of(v, sp["val"])
val = val[~val["label"].isin(m.HELDOUT)]
p = l2.Pairs(val)
ps = l2.PosSpeed().raw_scores(val)
lab = val["label"].to_numpy()
first = np.empty(len(val), bool)
first[p.order] = ~p.valid
rows = {}
for c in (0, 11, 13, 16):
    k = (lab == c) & ~first
    d = np.empty(len(val)); d[p.order] = p.d
    dt = np.empty(len(val)); dt[p.order] = p.dt
    sp_ = val["speed"].to_numpy()
    rows[m.aname(c) if c else "genuine"] = {
        "n_pairs": int(k.sum()), "median_dt_s": float(np.median(dt[k])), "median_displacement_m": float(np.median(d[k])),
        "median_speed_x_dt_m": float(np.median(sp_[k] * dt[k])), "median_pos_speed_residual_m": float(np.median(ps[k])),
        "frac_zero_displacement": float((d[k] < 0.01).mean())}
res["veremi_val_mechanisms"] = rows

# ---- B: Tampa map check
tp = adapters.load_tampa_v1(with_age=True)
spt = json.loads((OUT / "splits_tampa.json").read_text())
tree = l2.build_road_tree(m.OSM_TAMPA, adapters.TAMPA_LAT0, adapters.TAMPA_LON0)
vd = splitting.rows_of(tp, spt["val"]).copy()
td = splitting.rows_of(tp, spt["test"]).copy()
mp = l2.MapRoad(tree)
dv, dt_ = mp.raw_scores(vd), mp.raw_scores(td)
thr = float(np.quantile(dv, 0.99))
res["tampa_map"] = {"val_distance_quantiles_m": {str(q): float(np.quantile(dv, q)) for q in (0.5, 0.9, 0.99, 1.0)},
                    "test_distance_quantiles_m": {str(q): float(np.quantile(dt_, q)) for q in (0.5, 0.9, 0.99, 1.0)},
                    "val_q99_m": thr, "test_frac_above_val_q99": float((dt_ > thr).mean())}
td["map_d"] = dt_
td["above"] = dt_ > thr
pv = td.groupby("sender").agg(n=("above", "size"), above=("above", "sum"), med_d=("map_d", "median"), rsu=("rx_id", "first"))
pv["share_of_alarms"] = pv["above"] / max(pv["above"].sum(), 1)
res["tampa_map"]["test_vehicles"] = int(len(pv))
res["tampa_map"]["top_vehicles_by_alarms"] = pv.sort_values("above", ascending=False).head(5).reset_index().to_dict("records")
res["tampa_map"]["vehicles_with_any_alarm"] = int((pv["above"] > 0).sum())
vv = vd.assign(d=dv, above=dv > thr).groupby("sender").agg(n=("above", "size"), above=("above", "sum"), rsu=("rx_id", "first"))
res["tampa_map"]["val_vehicles"] = int(len(vv))
res["tampa_map"]["val_top_vehicles_by_alarms"] = vv.sort_values("above", ascending=False).head(3).reset_index().to_dict("records")

# union of the non-map L2 checks, genuine messages only (descriptive)
vd2 = vd.assign(sample_id=vd["msg_id"])
names = [n for n in m.L2_NAMES if n != "v2x.map_road"]
layers = [l for l in l2.make_layers(tree) if l.name in names]
cal_v, cal_t = [], []
for l in layers:
    l.calibrate_masked(vd2, np.ones(len(vd2), bool), m.BUDGET)
    cal_v.append(l.calibrator.transform(l.raw_scores(vd2)))
    cal_t.append(l.calibrator.transform(l.raw_scores(td)))
uv, ut = np.max(cal_v, axis=0), np.max(cal_t, axis=0)
th = budget_threshold(uv, m.BUDGET)
res["tampa_non_map_L2_union_genuine"] = {"val_FA": float((uv >= th).mean()), "test_FA": float((ut >= th).mean()),
                                         "test_genuine_vehicles_with_any_alarm": float(pd.Series(ut >= th).groupby(td["sender"].to_numpy()).any().mean())}
m.s2.jdump("s3_diag.json", res)
print(json.dumps(res, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))[:4000])
