"""WP1 S8 shuffled-label control of the only supervised GPS row (L4 = retrained v2 C2, S7 training procedure), 5 fixed seeds.
Rule fixed before running (notes/WP1_gps.md S8, G6): training and validation labels permuted across rows, seeds 101..105, the S7 fit
(train drives / val drives, 4 v2 attacks, 15-trial random search); bound = MEAN test AUC <= 0.55 (the max is reported too). The S7 seed 12345 is
re-run as a reproducibility check (S7 reported 0.553). L3 is fitted on label-0 rows only: nothing to shuffle. The deployed combiner
(noisy_or_log) has no fitted weights: nothing to shuffle.
Outputs: results/WP1/S8_control.json. Run from codes_v3/: python -u -W ignore tools/WP1_S8_control.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S7_lib as W7
import WP1_S4_lib as L
from common.metrics import auc, budget_threshold
from gps import learned

SEEDS = [101, 102, 103, 104, 105]
REF_SEED = 12345
T0 = time.time()


def main():
    dev = W7.feature_frame(None, "dev")
    test = W7.feature_frame(None, "test")
    F = W7.c2_frame(dev)
    Ft = W7.c2_frame(test)
    y = dev["label"].to_numpy()
    part = dev["part"].to_numpy()
    mask = W7.l4_rows(dev, W7.V2_ATTACKS)
    yt = test["label"].to_numpy()
    clean = (test["attack"] == "none").to_numpy()
    out = {"bound_mean_auc": 0.55, "seeds": SEEDS, "reference_seed": REF_SEED, "runs": {}}
    for sd in [REF_SEED] + SEEDS:
        ctrl = W7.l4_fit(F, y, part == "train", part == "val", learned.C2_ALL, mask, shuffle_seed=sd)
        ps = ctrl.score(Ft)
        sv = ctrl.score(F[part == "val"])
        nv = (dev.loc[part == "val", "label"] == 0).to_numpy()
        thr = budget_threshold(sv[nv], 0.01)
        flag = ps >= thr
        sm = L.summarize(test, flag)
        out["runs"][str(sd)] = {"auc_test_rows": auc(yt, ps), "fa_clean_runs": float(flag[clean].mean()),
                                "row_detection": {a: float(flag[(test["attack"] == a).to_numpy() & (yt == 1)].mean()) for a in L.ATT},
                                "run_detected": sm["run_detected"], "val_f1": ctrl.info["val_f1_macro"]}
        print(f"[{time.time() - T0:5.0f}s] seed {sd} AUC {out['runs'][str(sd)]['auc_test_rows']:.4f} FA {out['runs'][str(sd)]['fa_clean_runs']:.4f} "
              f"mean run {np.mean(list(sm['run_detected'].values())):.3f}", flush=True)
    a = [out["runs"][str(s)]["auc_test_rows"] for s in SEEDS]
    out["auc_mean"], out["auc_max"], out["auc_min"] = float(np.mean(a)), float(np.max(a)), float(np.min(a))
    out["met"] = bool(out["auc_mean"] <= 0.55)
    out["mean_run_detection_per_seed"] = {str(s): float(np.mean(list(out["runs"][str(s)]["run_detected"].values()))) for s in SEEDS}
    (L.OUT / "S8_control.json").write_text(json.dumps(out, indent=1, default=float))
    print("MEAN AUC", out["auc_mean"], "max", out["auc_max"], "met", out["met"], flush=True)


if __name__ == "__main__":
    main()
