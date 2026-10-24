"""WP3 S4 choices 2 and 3 on VALIDATION (no test table is read): nmin in {10, 20, 40}; val-only vs LODO threshold decision.
Writes results/WP3/S4/dev.json."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import s4_eval as E
from lidar.data import CACHE, VAL, drives_of

RES = RESULTS / "WP3" / "S4"
ROOT = CACHE / "S4" / (json.loads((RES / "variant_choice.json").read_text())["variant"] + "_t")
CHOICE = ["PointDrop", "IntensitySpoof", "cmp_boxcloud", "ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far"]


def main():
    calib = C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")
    tr, va = drives_of("train"), drives_of("val")
    co, cs = E.load_kind(ROOT, "clean", tr + va)
    ao, as_ = E.load_kind(ROOT, "att_val", VAL)
    out = {"nmin": {}}
    for nmin in (8, 16, 32):
        model = E.fit_model(co, cs, tr, calib, nmin)
        cv = E.scan_frame(model, co[np.isin(cs.set_index("scan").loc[co.scan, "drive"].to_numpy(), va)], cs[cs.drive.isin(va)])
        lay = E.union_layer(cv)
        det = E.detection(lay, E.scan_frame(model, ao, as_))
        r = {a: float(det[a]) for a in det.index}
        r["FA_val"] = float((E.cal_scores(lay, cv) >= lay.threshold).mean())
        r["mean_choice"] = float(np.mean([det[a] for a in CHOICE]))
        out["nmin"][nmin] = r
        print(nmin, r, flush=True)
    best = max(out["nmin"], key=lambda k: (round(out["nmin"][k]["mean_choice"], 6), k))
    out["nmin_chosen"] = int(best)
    drives = tr + va
    oof = E.lodo_scan_scores(co, cs, drives, calib, int(best))
    lay = E.union_layer(oof)
    fa = E.per_drive_fa(lay, oof)
    out["lodo"] = {"pooled_fa": float((E.cal_scores(lay, oof) >= lay.threshold).mean()), "per_drive_fa": {d: float(v) for d, v in fa.items()},
                   "worst_drive_fa": float(fa.max()), "n_scans": int(len(oof))}
    out["primary"] = "lodo" if fa.max() > 0.03 else "val_only"
    (RES / "dev.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
