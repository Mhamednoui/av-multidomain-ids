"""WP9 B1 POST-HOC analysis: validation-F1-optimal operating point instead of the 1% false-alarm budget.

Declared after the test numbers at the 1% budget were seen, so it is NOT part of the pre-registered acceptance rules; the
threshold is still chosen on validation windows only (maximising binary attack F1) and applied once to the saved test scores.
Reason: published CAN papers report F1 without a false-alarm budget; at ~1-3% attack-window prevalence a 1% FPR budget
caps precision. Output: results/WP9/B1_f1op.json
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B1_lib as L

SUBS = {"carhacking": ["test_blocks"], "road": ["test"], "d11": ["test_01", "test_02", "test_03", "test_04"]}


def best_thr(y, s):
    o = np.argsort(-s)
    ys = (y[o] != 0).astype(float)
    tp = np.cumsum(ys); fp = np.cumsum(1 - ys)
    P = ys.sum()
    f1 = 2 * tp / np.maximum(tp + fp + P, 1)
    i = int(np.argmax(f1))
    return float(s[o][i]) , float(f1[i])


def main():
    out = {}
    for tag in ["carhacking", "road", "d11_set_01", "d11_set_02", "d11_set_03", "d11_set_04"]:
        ds = tag.split("_")[0]
        t = json.load(open(L.OUT / f"B1_{tag}_test.json"))
        zv = np.load(L.SCORES / f"{tag}_val.npz", allow_pickle=True)
        zt = np.load(L.SCORES / f"{tag}_test.npz", allow_pickle=True)
        for mname in t["models"]:
            yv, sv = zv["y"], zv[f"s_{mname}"].astype(np.float64)
            thr, fv = best_thr(yv, sv)
            for sub in SUBS[ds]:
                d = zt[f"{mname}__{sub}"].item()
                y, s = d["y"], d["s"].astype(np.float64)
                pos, neg = y != 0, y == 0
                tp = int(np.sum(pos & (s >= thr))); fp = int(np.sum(neg & (s >= thr))); fn = int(np.sum(pos & (s < thr)))
                pr = tp / max(tp + fp, 1); rc = tp / max(tp + fn, 1)
                out[f"{tag}|{mname}|{sub}"] = {"val_best_f1": fv, "thr": thr, "test_precision": pr, "test_recall": rc,
                                               "test_f1": L.f1(pr, rc), "test_fpr": fp / max(neg.sum(), 1)}
    L.jd(out, L.OUT / "B1_f1op.json")
    for k, v in out.items():
        print(k, {a: round(b, 3) for a, b in v.items()})


if __name__ == "__main__":
    main()
