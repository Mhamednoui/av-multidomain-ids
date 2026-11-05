"""WP9 B3 post-hoc diagnostic on VALIDATION (not a selection basis): is the below-band AUC of the within-block sender-label permutation control a systematic effect
or sampling noise of a few label assignments?  Same feature set / depth as the chosen model, 100 trees fixed, 5 seeds, for (a) within-block sender permutation,
(b) global sender permutation, (c) row-level shuffle.  Also reports the AUC when the null model is scored per sender (mean score of the sender's messages).
Run: python -I -u -W ignore tools/WP9_B3_control_seeds.py   -> results/WP9/B3_control_seeds.json
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
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

import WP9_B3_fit as FIT
import WP9_B3_lib as L


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def main():
    sel = json.loads((L.OUT / "B3_selection.json").read_text())
    c = sel["chosen"]
    feats = L.SETS[c["set"]]
    Ftr, mtr = L.load_part("train")
    Fva, mva = L.load_part("val")
    ytr, yva = mtr["label"].to_numpy().astype(int), mva["label"].to_numpy().astype(int)
    X, Xv = Ftr[feats].to_numpy(np.float32), Fva[feats].to_numpy(np.float32)
    snd, blk = mtr["sender"].to_numpy(), mtr["block"].to_numpy()
    us, first = np.unique(snd, return_index=True)
    lab_s = ytr[first]
    blk_s = blk[first]
    inv = np.searchsorted(us, snd)
    out = {"feature_set": c["set"], "depth": c["depth"], "trees": 100, "runs": []}
    for seed in range(5):
        rng = np.random.RandomState(1000 + seed)
        perm_wb = lab_s.copy()
        for b in np.unique(blk_s):
            ix = np.flatnonzero(blk_s == b)
            perm_wb[ix] = rng.permutation(lab_s[ix])
        perm_g = rng.permutation(lab_s)
        for nm, y_new in (("within_block_sender", perm_wb[inv]), ("global_sender", perm_g[inv]), ("rows", rng.permutation(ytr))):
            m = xgb.XGBClassifier(objective="multi:softprob", num_class=L.K, n_estimators=100, max_depth=c["depth"], tree_method="hist", n_jobs=4, random_state=1000 + seed,
                                  eval_metric="mlogloss", **FIT.XGB_PARAMS)
            m.fit(X, y_new, verbose=False)
            P = m.predict_proba(Xv)
            s = L.attack_score(P)
            a = float(roc_auc_score((yva > 0).astype(int), s))
            d = pd.DataFrame({"sender": mva["sender"].to_numpy(), "y": (yva > 0).astype(int), "s": s}).groupby("sender").agg(y=("y", "first"), s=("s", "mean"))
            a_s = float(roc_auc_score(d["y"], d["s"]))
            out["runs"].append({"seed": seed, "perm": nm, "val_auc_msg": a, "val_auc_sender_mean_score": a_s})
            log(seed, nm, round(a, 3), round(a_s, 3))
            L.jd(out, L.OUT / "B3_control_seeds.json")
    df = pd.DataFrame(out["runs"])
    out["summary"] = df.groupby("perm")[["val_auc_msg", "val_auc_sender_mean_score"]].agg(["mean", "min", "max"]).round(3).to_dict()
    L.jd(out, L.OUT / "B3_control_seeds.json")
    log("DONE")


if __name__ == "__main__":
    main()
