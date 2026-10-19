"""WP1 S5 development pass: KITTI TRAIN + VAL drives only (16 drives); the test drives are not read here.
For every L2d candidate (raw metres / standardised z, W = 1, 3, 10 s, plus the compass-free course residual):
  - LODO pooled 1% tie-safe threshold on the clean scores, held-out FA per drive, run-level detections, J (mean of 6 run-level detections +
    slow drift within 30 s, as S4);
  - NESTED selection: for each held-out drive the best (form, W) by J is chosen on the other 15 drives (threshold from those 15 drives),
    then the held-out drive is scored with that choice and the threshold from the 15 drives. Reports the choice per fold, the held-out FA and
    the pooled held-out detection of the nested procedure;
  - the choice for the test pass = best J on all 16 drives.
Outputs: results/WP1/S5_dev.json, S5_dev_grid.md. Run from codes_v3/: python -u -W ignore tools/WP1_S5_dev.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
import WP1_S4_dev as D4
from common.metrics import budget_threshold
from gps import cusum
from gps import lidar_dr
from gps import lidar_odom as LO
from gps.lodo import lodo_report

BUDGET = 0.01
CANDS = {f"lid_{f}_{w}": f"{'z' if f == 'z' else 'resid'}, W={w}" for f in ("resid", "z") for w in LO.WINDOWS}
CANDS["lid_course"] = "course (compass-free)"
KAPPAS = (0.5, 1.0, 1.5, 2.0)


def dev_stream():
    kx = L.kitti_stream()
    dev = kx[kx["part"].isin(L.DEV_PARTS)]
    assert not dev["part"].eq("test").any()
    return dev.join(LO.stream_features(dev))


def main():
    dev = dev_stream()
    drives = sorted(dev["drive"].unique())
    y = dev["label"].to_numpy()
    normal = y == 0
    drive = dev["drive"].to_numpy()
    res = {"candidates": {}, "nested": {}, "n_drives": len(drives)}
    S = {c: dev[c].to_numpy() for c in CANDS}
    out = lidar_dr.run_ldr(dev, lidar_dr.LDRConfig(), L.ekf_cfg())
    runs = dev["run"].to_numpy()
    for stat in ("nis", "axis"):
        for kp in KAPPAS:
            c = f"cusum_lidar_{stat}|k={kp}"
            S[c] = cusum.score_from_dr(out, stat, kp, runs)
            CANDS[c] = c
    for c in S:
        res["candidates"][c] = D4.evaluate(dev, S[c], c)
        r = res["candidates"][c]
        print(c, "J", round(r["J"], 3), "heldout FA", round(r["lodo"]["heldout_fa_pooled"], 4), "run det", {a: round(v, 2) for a, v in r["summary"]["run_detected"].items()}, flush=True)
    best_all = max(S, key=lambda c: res["candidates"][c]["J"])
    res["selected_all16"] = best_all
    # ---- nested selection ----
    choices, fa_num, fa_den, flag_nested = {}, 0, 0, np.zeros(len(dev), bool)
    for d in drives:
        m = drive == d
        js = {}
        for c in S:
            thr = budget_threshold(S[c][normal & ~m], BUDGET)
            sm = L.summarize(dev[~m], S[c][~m] >= thr)
            js[c] = L.j_criterion(sm)
        c = max(js, key=js.get)
        thr = budget_threshold(S[c][normal & ~m], BUDGET)
        flag_nested[m] = S[c][m] >= thr
        choices[d] = {"choice": c, "J_on_other_15": js[c], "threshold": thr, "heldout_fa": float(flag_nested[m & normal].mean()) if (m & normal).any() else None}
    nested_sm = L.summarize(dev, flag_nested)
    res["nested"] = {"choices": choices, "heldout_fa_pooled": float(flag_nested[normal].mean()), "summary": nested_sm, "J": L.j_criterion(nested_sm),
                     "choice_counts": {c: sum(1 for v in choices.values() if v["choice"] == c) for c in S}}
    print("nested held-out FA", res["nested"]["heldout_fa_pooled"], "J", res["nested"]["J"], res["nested"]["choice_counts"], "selected on all 16:", best_all, flush=True)
    (L.OUT / "S5_dev.json").write_text(json.dumps(res, indent=1, default=float))
    rows = ["| candidate | J | LODO held-out FA | worst drive | " + " | ".join(L.ATT) + " |", "|---" * (4 + len(L.ATT)) + "|"]
    for c, r in sorted(res["candidates"].items(), key=lambda kv: -kv[1]["J"]):
        rows.append(f"| {c} | {r['J']:.3f} | {100 * r['lodo']['heldout_fa_pooled']:.2f}% | {100 * r['lodo']['heldout_fa_worst_drive']:.2f}% | " + " | ".join(f"{100 * r['summary']['run_detected'][a]:.0f}%" for a in L.ATT) + " |")
    (L.OUT / "S5_dev_grid.md").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
