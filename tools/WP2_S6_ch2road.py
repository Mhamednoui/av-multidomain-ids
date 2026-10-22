"""WP2 S6: v2 failure case 2 re-checked on ROAD VALIDATION: the Car-Hacking-trained models applied to ROAD (v2: 0.5% recall).
Car-Hacking models (tools/WP2_S6_ch.py fit) use the ROAD id periods of the P1 training split for dt_id_ratio / id_known (as v2: T0/T1).
T0 = the Car-Hacking thresholds (frame: margin 0 = probability 0.5 as in v2, and the Car-Hacking 1% frame threshold; window: the Car-Hacking 1% window threshold);
T1 = threshold calibrated on the ROAD validation clean windows / frames (1%, tie-safe). Output: results/WP2/s6_ch2road.json
Usage: python -u -W ignore tools/WP2_S6_ch2road.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l1_exp as E
from can import l4_exp as X
from can import l4_features as G
from common.config import DATA_EXTRA, RESULTS
from common.metrics import budget_threshold
import WP2_S6_road as R
from WP2_S6_cache import load

CH = DATA_EXTRA / "WP2_S6_cache" / "ch_run_m"


def main():
    chi = json.load(open(CH / "fit_info.json"))
    rinfo = json.load(open(R.RUN / "p1_info.json"))
    period = {int(a): b for a, b in rinfo["period"].items()}
    codes = E.AttCodes()
    codes.names = list(rinfo["codes"])
    caps = R.caps_table()
    base_of = {n: i for i, n in enumerate(caps["name"])}
    va = caps.loc[caps["part"] == "val", "name"].tolist()
    D = {n: load("road", n) for n in va}
    res = {}
    for k, (nm, cols) in X.MODELS.items():
        m = xgb.XGBClassifier()
        m.load_model(str(CH / f"{k}.json"))
        vi = chi[k]["variant_selection"]["chosen"]
        tabs, frames = [], {}
        for n in va:
            d = D[n]
            F = X.cap_F(d, codes, base_of[n], E.lead_clean(d["t"], d["label"]))
            sc = {k: X.predict(m, X.matrix(d, period, cols))}
            tb = X.window_rows(F, n, sc)
            tb["fi"] = E.first_injected({"t": d["t"], "label": d["label"]}) if d["label"].any() else np.nan
            tabs.append(tb)
            frames[n] = (sc[k], d["label"], F["clean"])
        tbl = pd.concat(tabs, ignore_index=True)
        y = (tbl["y"] == 1).to_numpy()
        cl = X.clean_mask(tbl)
        raw = tbl[f"{k}{vi}"].to_numpy()
        fr_p = np.concatenate([v[0] for v in frames.values()])
        fr_y = np.concatenate([v[1] for v in frames.values()])
        fr_c = np.concatenate([v[2] for v in frames.values()]) & (fr_y == 0)
        out = {"variant": list(G.VARIANTS[vi]), "frame_auc_val": X.frame_auc(fr_y, fr_p), "window_auc_val": X.window_auc(tbl, k, vi)}
        for tag, wthr, fthr in (("T0_carhacking_thresholds", chi[k]["window_threshold"], chi[k]["frame_threshold"]),
                                ("T1_road_val_calibrated", float(budget_threshold(raw[cl], 0.01)), float(budget_threshold(fr_p[fr_c], 0.01)))):
            al = raw >= wthr
            r = {"window_threshold": wthr, "frame_threshold": fthr, "fa_clean_windows": float(al[cl].mean()),
                 "window_recall_all_attack": float(al[y].mean()), "captures": {}}
            for g, d in tbl.groupby("group", sort=False):
                yy = (d["y"] == 1).to_numpy()
                if yy.any():
                    a = al[d.index.to_numpy()]
                    fp, fy, _ = frames[g]
                    r["captures"][g] = {"window_recall": float(a[yy].mean()), "detected": bool(a[yy].any()),
                                        "frame_recall": float((fp[fy == 1] >= fthr).mean())}
            r["frame_recall_all"] = float((fr_p[fr_y == 1] >= fthr).mean())
            r["frame_fa_clean"] = float((fr_p[fr_c] >= fthr).mean())
            r["frame_recall_at_prob_0.5"] = float((fr_p[fr_y == 1] >= 0.0).mean())
            r["frame_fa_at_prob_0.5"] = float((fr_p[fr_y == 0] >= 0.0).mean())
            out[tag] = r
        res[nm] = out
        print(nm, {t: (out[t]["window_recall_all_attack"], out[t]["fa_clean_windows"], out[t]["frame_recall_all"]) for t in out if t.startswith("T")}, flush=True)
    json.dump(res, open(RESULTS / "WP2" / "s6_ch2road.json", "w"), indent=1)


if __name__ == "__main__":
    main()
