"""WP7 S1: build the V2X physics-only domain (system/v2x_runner.py) from the VeReMi VALIDATION split (held-out types 6 / 12 / 17 removed, as WP5 S6) and check it against
the numbers WP5 stored (results/WP5/s6_veremi.json: layer thresholds, validation false alarms). Test split is never read.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_v2x_fit.py     Output: results/WP7/frozen_v2x/domain.json, results/WP7/S1_v2x_fit.json
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np

from v2x import l3, splitting
import WP5_S5_dev as dev5
from system.v2x_runner import HELDOUT, LAYER_NAMES, V2XPhysicsDomain

OUT = ROOT / "results" / "WP7"


def main():
    t0 = time.time()
    v, sp = dev5.load_frames()
    va = splitting.rows_of(v, sp["val"])
    va = va[~va["label"].isin(HELDOUT)].sort_values("t", kind="stable").reset_index(drop=True)
    print("val rows", len(va), "genuine", int((va["label"] == 0).sum()), f"{time.time() - t0:.0f}s", flush=True)
    dom = V2XPhysicsDomain(dev5.tracker_from_s4()).fit(va)
    print("fitted", f"{time.time() - t0:.0f}s", flush=True)
    dom.save(OUT / "frozen_v2x")
    s6 = json.loads((ROOT / "results" / "WP5" / "s6_veremi.json").read_text())
    thr6 = s6["layer_thresholds_calibrated"]
    g = (va["label"] == 0).to_numpy()
    raws = dom.raws(va)
    cal = dom.calibrated(raws)
    comb = np.max(np.stack([cal[n] for n in LAYER_NAMES]), axis=0)
    ref = s6["groups"]["all but L4 (= L1+L2+L3)"]
    res = {"n_val_rows": int(len(va)), "n_genuine": int(g.sum()),
           "thresholds_wp7": dom.thr, "thresholds_wp5_s6": {n: thr6[n] for n in LAYER_NAMES},
           "threshold_max_abs_diff": max(abs(dom.thr[n] - thr6[n]) for n in LAYER_NAMES),
           "combined_threshold": dom.comb_thr, "val_FA_msg_wp7": float((comb[g] >= dom.comb_thr).mean()), "val_FA_msg_wp5_s6": ref["val_FA_msg"],
           "combiner_wp5_s6": ref["combiner"]["method"], "layer_val_FA": {n: float((cal[n][g] >= dom.thr[n]).mean()) for n in LAYER_NAMES},
           "seconds": time.time() - t0}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "S1_v2x_fit.json").write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("threshold_max_abs_diff", "val_FA_msg_wp7", "val_FA_msg_wp5_s6", "combined_threshold")}, indent=1), flush=True)


if __name__ == "__main__":
    main()
