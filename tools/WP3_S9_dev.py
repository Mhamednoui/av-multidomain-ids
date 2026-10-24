"""WP3 S9 VALIDATION round (test not read): combiner choice (V1) and density-part decision (V2) by the rules in notes/WP3_lidar.md.
Layers fitted on the 13 train drives; thresholds from the out-of-fold clean reference of the 16 train+val drives; detection on the validation
attacks (3 drives). Writes results/WP3/S9/dev.json and caches the dev frames. Usage: python -u -W ignore tools/WP3_S9_dev.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP3_S9_lib as L
from common.config import RESULTS
from lidar import combine as K

RES = RESULTS / "WP3" / "S9"
PHYS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof"]
CMP = ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
STORE = L.S9C / "dev_frames.pkl"


def evaluate(ref, att, cols, method):
    st = K.Stack(cols, method, 0.01).fit(ref)
    sizes = ref.groupby("drive").size().to_dict()
    fa = K.lodo_fa(ref, cols, method)
    mean, worst, who = K.lodo_summary(fa, sizes)
    det = K.detection(st, att)
    return {"cols": cols, "method": method, "fa_ref": float(st.alarm(ref).mean()), "lodo_mean": mean, "lodo_worst": worst, "lodo_worst_drive": who,
            "lodo_fa": fa, "det": {a: float(det[a]) for a in PHYS + CMP}, "mean_phys": float(np.mean([det[a] for a in PHYS]))}


def choose_combiner(rows):
    """V1: clean-FA control first, then mean physical detection (<= 0.5 point gaps are ties, simplest first)."""
    best_worst = min(r["lodo_worst"] for r in rows.values())
    ok = {m: r for m, r in rows.items() if r["lodo_mean"] <= 0.015 and r["lodo_worst"] <= best_worst + 0.03}
    reason = "survivors of the clean-FA control: " + ", ".join(ok) if ok else "all eliminated: lowest worst-drive FA"
    if not ok:
        ok = {min(rows, key=lambda m: rows[m]["lodo_worst"]): None}
        ok = {m: rows[m] for m in ok}
    top = max(r["mean_phys"] for r in ok.values())
    tied = [m for m in K.METHODS if m in ok and ok[m]["mean_phys"] >= top - 0.005]
    return tied[0], reason, top


def main():
    t0 = time.time()
    if STORE.exists():
        fr = pd.read_pickle(STORE)
    else:
        fr = L.physics("dev")
        pd.to_pickle(fr, STORE)
    print("frames", {k: v.shape for k, v in fr.items()}, f"{time.time() - t0:.0f}s", flush=True)
    ref, att = fr["ref"], fr["att"]
    out = {"n_ref": int(len(ref)), "n_att": att.attack.value_counts().to_dict(), "stacks": {}}
    for tag, cols in (("int", L.HEAD), ("dens", L.HEAD_DENS)):
        for m in K.METHODS:
            r = evaluate(ref, att, cols, m)
            out["stacks"][f"{tag}/{m}"] = r
            print(tag, m, f"fa_ref {r['fa_ref']:.3f} lodo mean {r['lodo_mean']:.3f} worst {r['lodo_worst']:.3f} ({r['lodo_worst_drive']}) mean_phys {r['mean_phys']:.3f}",
                  {a: round(r["det"][a], 3) for a in PHYS}, flush=True)
    rows = {m: out["stacks"][f"int/{m}"] for m in K.METHODS}
    m, why, top = choose_combiner(rows)
    out["V1"] = {"chosen": m, "reason": why, "mean_phys": top}
    a, b = out["stacks"][f"int/{m}"], out["stacks"][f"dens/{m}"]
    gain = b["mean_phys"] - a["mean_phys"]
    keep_dens = bool(gain >= 0.02 and b["lodo_worst"] <= a["lodo_worst"] + 0.02)
    out["V2"] = {"combiner": m, "mean_phys_int": a["mean_phys"], "mean_phys_dens": b["mean_phys"], "gain": gain, "lodo_worst_int": a["lodo_worst"],
                 "lodo_worst_dens": b["lodo_worst"], "density_kept": keep_dens}
    print("V1", out["V1"], "\nV2", out["V2"])
    # single layers at their own 1 % (descriptive: what the shared budget costs)
    out["single"] = {}
    for c in ["raw_L1", "raw_L2a", "raw_L2aF", "raw_L2c", "raw_L2d"]:
        st = K.Stack([c], "max", 0.01).fit(ref)
        d = K.detection(st, att)
        out["single"][c] = {"fa_ref": float(st.alarm(ref).mean()), "det": {x: float(d[x]) for x in PHYS + CMP}}
    out["seconds"] = time.time() - t0
    (RES / "dev.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
