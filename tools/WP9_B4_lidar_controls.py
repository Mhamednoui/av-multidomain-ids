"""WP9 B4 LiDAR controls on VALIDATION (committed before the test): row-shuffled labels, within-scan label permutation (5 seeds), feature-importance red flag,
validation AUC per drive. Chosen config from results/WP9/B4_lidar_selection.json (fixed number of rounds = chosen trees for the null fits). No test row is loaded.
Output: results/WP9/B4_lidar_controls.json.   Run: python -u -W ignore tools/WP9_B4_lidar_controls.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import xgboost as xgb

import WP9_B4_lidar_lib as L
from WP9_B4_lidar_fit import fit, score
from lidar.features import feature_names_temporal

OUT = L.ROOT / "results" / "WP9"


def main():
    t0 = time.time()
    sel = json.loads((OUT / "B4_lidar_selection.json").read_text())
    ch = sel["chosen"]
    mtr, Xtr = L.load("train")
    mva, Xva = L.load("val")
    ytr, yva = mtr.cls.to_numpy(), mva.cls.to_numpy()
    names = feature_names_temporal()
    res = {"rules": {"shuffle_band": [0.42, 0.58], "red_flag": "one feature > 0.40 of total gain, or temporal columns (211:) > 0.70"}, "chosen": ch}
    # real model (reload)
    m = xgb.XGBClassifier()
    m.load_model(str(L.CACHE.parent / "lidar_model" / "chosen.json"))
    s = score(m, Xva)
    res["real_val_auc_any"] = L.auc_any(mva, s)
    res["val_auc_per_drive"] = sel["val_auc_per_drive"]
    # 1 row-shuffled train labels
    sh = []
    for seed in (42, 43, 44):
        y = np.random.default_rng(seed).permutation(ytr)
        ms = fit(ch["params"], ch["weight_power"], Xtr, y, Xva, yva, seed=seed, n_rounds=ch["trees"])
        sh.append(L.auc_any(mva, score(ms, Xva)))
        print("row shuffle seed", seed, round(sh[-1], 4), f"({time.time()-t0:.0f}s)", flush=True)
    res["row_shuffle_val_auc"] = sh
    res["row_shuffle_pass"] = bool(all(0.42 <= a <= 0.58 for a in sh))
    # 2 within-scan label permutation: labels permuted among the rows of one (drive, scan) group (clean row + its attacked rows)
    key = (mtr.drive + "/" + mtr.i.astype(str)).to_numpy()
    order = np.argsort(key, kind="stable")
    bounds = np.r_[0, np.flatnonzero(key[order][1:] != key[order][:-1]) + 1, len(key)]
    wp = []
    for seed in range(5):
        rng = np.random.default_rng(1000 + seed)
        y = ytr.copy()
        for a, b in zip(bounds[:-1], bounds[1:]):
            idx = order[a:b]
            y[idx] = ytr[rng.permutation(idx)]
        mp = fit(ch["params"], ch["weight_power"], Xtr, y, Xva, yva, seed=seed, n_rounds=ch["trees"])
        wp.append(L.auc_any(mva, score(mp, Xva)))
        print("within-scan permutation seed", seed, round(wp[-1], 4), f"({time.time()-t0:.0f}s)", flush=True)
    res["within_scan_perm_val_auc"] = wp
    res["within_scan_perm_pass"] = bool(all(0.42 <= a <= 0.58 for a in wp))
    res["within_scan_perm_summary"] = {"min": float(min(wp)), "max": float(max(wp)), "mean": float(np.mean(wp))}
    # 3 importance
    imp = m.get_booster().get_score(importance_type="total_gain")
    tot = sum(imp.values())
    share = {names[int(k[1:])]: v / tot for k, v in imp.items()}
    top = sorted(share.items(), key=lambda kv: -kv[1])
    temporal = sum(v for k, v in imp.items() if int(k[1:]) >= L.N_DESCR) / tot
    res["top_gain_share"] = top[:10]
    res["temporal_gain_share"] = float(temporal)
    res["red_flag"] = bool(top[0][1] > 0.40 or temporal > 0.70)
    (OUT / "B4_lidar_controls.json").write_text(json.dumps(res, indent=1))
    print("real val AUC", round(res["real_val_auc_any"], 4), "shuffle", [round(x, 3) for x in sh], "within-scan", [round(x, 3) for x in wp], flush=True)
    print("top", [(a, round(b, 3)) for a, b in top[:6]], "temporal share", round(temporal, 3), "RED FLAG", res["red_flag"], flush=True)
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
