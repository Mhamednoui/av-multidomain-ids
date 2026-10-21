"""WP2 S4: VALIDATION-ONLY ablation of the check types (variant 0) and of revision R1 (joint checks restricted to the reverse-light bit).
Uses LOCO held-out captures (calibration) and the train/val masquerade attack captures (attack 1 and 2); no test capture is read.
Usage: python -u -W ignore tools/WP2_S4_ablate_val.py -> results/WP2/s4_ablation_val.json
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l1_exp as E
from can import l2b_signals as Z
from common.config import DATA_EXTRA, RESULTS
from common.metrics import budget_threshold
from WP2_S4_run import CACHE, LOCO, attack_names, sparse_load

SKIP_W = 4
Z.MUTE_T0 = 3.0


def wins(raws, types, tm):
    sc = np.max(np.stack([raws[t] for t in types]), axis=0)
    return Z.window_max(sc, Z.window_starts(tm)), sc


def run(tag, loco_dir, att_dir, types):
    pool = []
    for c in LOCO:
        tm = np.maximum.accumulate(np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (c + ".npz"))["t"])
        w, _ = wins(sparse_load(CACHE / loco_dir / f"h0__{c}.npz"), types, tm)
        pool.append(w[SKIP_W:])
    pool = np.concatenate(pool)
    thr = budget_threshold(pool, 0.01)
    out = {"types": types, "window_threshold": float(thr), "loco_fa": float((pool >= thr).mean()), "attack": {}}
    for c in attack_names(1) + attack_names(2):
        if "masquerade" not in c:
            continue
        z = np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (c + ".npz"))
        tm = np.maximum.accumulate(z["t"])
        w, _ = wins(sparse_load(CACHE / att_dir / f"h0__{c}.npz"), types, tm)
        st = Z.window_starts(tm)
        y = np.maximum.reduceat(z["label"], st) > 0
        clean = (np.minimum.reduceat(E.lead_clean(z["t"], z["label"]).astype(np.int8), st) > 0) & (np.arange(len(st)) >= SKIP_W)
        al = w >= thr
        out["attack"][c] = {"recall": float(al[y].mean()), "fa_clean": float(al[clean].mean())}
    out["mean_recall"] = float(np.mean([v["recall"] for v in out["attack"].values()]))
    print(tag, out["types"], "thr", round(thr, 2), "loco_fa", round(out["loco_fa"], 4), "mean recall", round(out["mean_recall"], 3),
          {k[:22]: round(v["recall"], 2) for k, v in out["attack"].items()}, flush=True)
    return out


def main():
    res = {}
    for name, types in [("all", Z.TYPES), ("no_joint", ["value", "rate", "linear"]), ("no_linear", ["value", "rate", "joint"]),
                        ("no_value", ["rate", "linear", "joint"]), ("no_rate", ["value", "linear", "joint"]),
                        ("only_linear", ["linear"]), ("only_joint", ["joint"]), ("only_value_rate", ["value", "rate"])]:
        res[name] = run(name, "loco_m", "attack_m", types)
    if (CACHE / "loco_r1").exists() and len(list((CACHE / "attack_r1").glob("h0__*"))) >= 18:
        res["R1_joint_reverse_bit_only"] = run("R1", "loco_r1", "attack_r1", Z.TYPES)
    json.dump(res, open(RESULTS / "WP2" / "s4_ablation_val.json", "w"), indent=1)


if __name__ == "__main__":
    main()
