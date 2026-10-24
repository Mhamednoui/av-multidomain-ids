"""WP3 S6 validation round: single-statistic detections (pooled threshold of the 16 train+val clean drives, 1 %), choice of the unions.
Writes results/WP3/S6/dev.json and dev.md. Only validation attacks / episodes are read. Usage: python -u -W ignore tools/WP3_S6_dev.py"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP3_S6_lib import *  # noqa
from common.config import RESULTS

RES = RESULTS / "WP3" / "S6"
GAIN = 3.0       # points: a statistic enters a union if it raises the mean detection of the target attacks by >= GAIN
TARGET = {"L2c": ["PointDrop"], "L2d": ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far"]}
CAND = {"L2c": L2C, "L2d": L2D}


def objective(lid, L, att, ep):
    """Mean detection over the target attacks; L2d also counts the sustained steps (>= 2) of the sensor-fixed validation episodes where the car moves."""
    v = [alarm(L, att[att.attack == a]).mean() for a in TARGET[lid]]
    if lid == "L2d":
        e = ep[(ep.step >= 2) & (ep.disp > 0.5)]
        v += [alarm(L, g).mean() for _, g in e.groupby("attack")]
    return float(np.mean(v))


def main():
    clean = load("clean", TRAINVAL)
    ep_v = load("ep_val", VAL)
    clean_val = clean[clean.drive.isin(VAL)]
    att = load("att_val", VAL)
    out = {"single": {}, "choice": {}}
    for lid, cand in CAND.items():
        for s in cand:
            L = layer(lid, [s], clean)
            fa_l = lodo_fa(lid, [s], clean)
            det = {a: float(alarm(L, att[att.attack == a]).mean()) for a in ATT}
            out["single"][s] = {"fa_val": float(alarm(L, clean_val).mean()), "lodo_fa_mean": float(np.mean(list(fa_l.values()))),
                                "lodo_fa_max": float(max(fa_l.values())), "det": det}
    for lid, cand in CAND.items():
        keep, best = [], 0.0
        order = sorted(cand, key=lambda s: -objective(lid, layer(lid, [s], clean), att, ep_v))
        for s in order:
            trial = keep + [s]
            L = layer(lid, trial, clean)
            fa = float(alarm(L, clean_val).mean())
            m = objective(lid, L, att, ep_v)
            if fa <= 0.02 and m >= best + GAIN / 100:
                keep, best = trial, m
        out["choice"][lid] = {"stats": keep, "mean_target_det_val": best}
        L = layer(lid, keep, clean) if keep else None
        if L is not None:
            out["choice"][lid]["fa_val"] = float(alarm(L, clean_val).mean())
            out["choice"][lid]["det_val"] = {a: float(alarm(L, att[att.attack == a]).mean()) for a in ATT}
            thr = episode_threshold(L, clean)
            out["choice"][lid]["episode_stat_threshold"] = thr
            for kind in ("ep_val", "epw_val"):
                out["choice"][lid][kind] = episode_table(L, load(kind, VAL), thr)
    (RES / "dev.json").write_text(json.dumps(out, indent=1))
    lines = ["| statistic | FA val | LODO FA mean / max | " + " | ".join(ATT) + " |", "|" + "---|" * (3 + len(ATT))]
    for s, r in out["single"].items():
        lines.append(f"| {s} | {100 * r['fa_val']:.2f} | {100 * r['lodo_fa_mean']:.2f} / {100 * r['lodo_fa_max']:.1f} | "
                     + " | ".join(f"{100 * r['det'][a]:.1f}" for a in ATT) + " |")
    (RES / "dev.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(json.dumps(out["choice"], indent=1))


if __name__ == "__main__":
    main()
