"""WP1 S4 development pass: KITTI TRAIN + VAL drives only (16 drives). Test drives are never scored here.

1. LODO calibration: for every candidate score, pooled clean (label 0) scores of the 16 drives -> tie-safe 1% threshold; held-out FA per
   drive from the threshold of the other 15 drives; diagnostic of the S3 problem: FA on the 13 train drives with a threshold from the 3 val drives.
2. Grid (kappa x freeze x scale) for the CUSUM layers; criterion J (mean of 6 run-level detections + slow-drift-within-30s) at the pooled threshold.
3. L2c diagnostics (scale convergence on clean runs, drag under attack with / without freezing) and absorption of the DR branch.
Outputs: results/WP1/S4_dev.json, S4_dev_grid.md. Run from codes_v3/: python -u -W ignore tools/WP1_S4_dev.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
from common.metrics import budget_threshold
from gps import cusum, ekf
from gps.lodo import lodo_report

BUDGET = 0.01
KAPPAS = (0.25, 0.5, 1.0, 1.5, 2.0)      # 1.5, 2.0 added after the first dev pass put the best at the edge 1.0 (notes)
FREEZES = {"never": dict(), "self8": dict(freeze_h=8.0), "self8+nis": dict(freeze_h=8.0, freeze_nis_level=0.999)}
SCALES = {"learn": dict(learn_scale=True), "none": dict(learn_scale=False)}


def evaluate(dev, score, name):
    y = dev["label"].to_numpy()
    drive = dev["drive"].to_numpy()
    part = dev["part"].to_numpy()
    normal = y == 0
    rep = lodo_report(score[normal], drive[normal], BUDGET)
    thr = rep["pooled_threshold"]
    flag = score >= thr
    sm = L.summarize(dev, flag)
    # S3 problem on development data: threshold from the 3 val drives only, FA on the 13 train drives
    v_thr = budget_threshold(score[normal & (part == "val")], BUDGET)
    tr_clean = normal & (part == "train")
    rep["val_only_threshold"] = v_thr
    rep["fa_on_train_drives_at_val_only_threshold"] = float((score[tr_clean] >= v_thr).mean())
    rep["fa_on_train_drives_at_lodo_threshold"] = float((score[tr_clean] >= thr).mean())
    return {"name": name, "lodo": rep, "summary": sm, "J": L.j_criterion(sm)}


def main():
    kx = L.kitti_stream()
    dev = kx[kx["part"].isin(L.DEV_PARTS)]
    runs = dev["run"].to_numpy()
    assert not dev["part"].eq("test").any()
    res = {"candidates": {}, "l2c": {}, "absorption": {}}
    # ---- references: B2 and L2a (EKF NIS), LODO vs val-only ----
    b2 = L.S1.B2Layer()
    res["candidates"]["gps.dr_resid_10"] = evaluate(dev, b2.raw_scores(dev), "gps.dr_resid_10")
    eo = ekf.run_filter_all(dev, L.ekf_cfg())
    res["candidates"]["gps.ekf_nis"] = evaluate(dev, ekf.nis_score(eo["nis"].to_numpy(), eo["dim"].to_numpy()), "gps.ekf_nis")
    print("B2 J", res["candidates"]["gps.dr_resid_10"]["J"], "EKF J", res["candidates"]["gps.ekf_nis"]["J"], flush=True)
    # ---- EKF based CUSUMs ----
    for stat in ("nis", "axis"):
        for kp in KAPPAS:
            nm = f"cusum_ekf_{stat}|k={kp}"
            res["candidates"][nm] = evaluate(dev, cusum.score_from_ekf(eo, stat, kp, runs), nm)
            print(nm, round(res["candidates"][nm]["J"], 3), flush=True)
    # ---- DR branch CUSUMs ----
    for sc, skw in SCALES.items():
        for fr, fkw in FREEZES.items():
            cfg = L.dr_cfg(**skw, **fkw)
            do = cusum.run_dr(dev, cfg, L.ekf_cfg())
            key = f"scale={sc}|freeze={fr}"
            res["l2c"][key] = L.scale_diag(dev, do)
            res["absorption"][key] = L.absorption(dev, do)
            for stat in ("axis", "nis"):
                for kp in KAPPAS:
                    nm = f"cusum_dr_{stat}|k={kp}|{key}"
                    res["candidates"][nm] = evaluate(dev, cusum.score_from_dr(do, stat, kp, runs), nm)
                    print(nm, round(res["candidates"][nm]["J"], 3), flush=True)
    cands = {k: v for k, v in res["candidates"].items() if k.startswith("cusum")}
    best = max(cands, key=lambda k: cands[k]["J"])
    best_dr = max((k for k in cands if "_dr_" in k), key=lambda k: cands[k]["J"])
    best_ekf = max((k for k in cands if "_ekf_" in k), key=lambda k: cands[k]["J"])
    res["selection"] = {"criterion": "J = mean(6 run-level detections, slow drift <0.5 m/s within 30 s) at the pooled-LODO 1% threshold on the 16 drives",
                        "best_overall": best, "best_dr": best_dr, "best_ekf": best_ekf,
                        "J": {k: cands[k]["J"] for k in (best, best_dr, best_ekf)}}
    print("SELECTED", res["selection"], flush=True)
    (L.OUT / "S4_dev.json").write_text(json.dumps(res, indent=1, default=float))
    rows = ["| candidate | J | slow-drift30 | FA clean runs (in-sample) | LODO held-out FA | worst drive FA | FA train drives @ val-only thr | FA train drives @ LODO thr |",
            "|---|---|---|---|---|---|---|---|"]
    for k, v in sorted(res["candidates"].items(), key=lambda kv: -kv[1]["J"]):
        r = v["lodo"]
        rows.append(f"| {k} | {v['J']:.3f} | {v['summary']['slow_drift_lt_0.5_within_30s']['rate']:.2f} | {100 * v['summary']['false_alarm_clean_runs']:.2f}% | "
                    f"{100 * r['heldout_fa_pooled']:.2f}% | {100 * r['heldout_fa_worst_drive']:.2f}% | {100 * r['fa_on_train_drives_at_val_only_threshold']:.2f}% | "
                    f"{100 * r['fa_on_train_drives_at_lodo_threshold']:.2f}% |")
    (L.OUT / "S4_dev_grid.md").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
