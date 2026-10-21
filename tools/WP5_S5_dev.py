"""WP5 S5 (dev stage): features of VeReMi TRAIN and VALIDATION (held-out types 6, 12, 17 removed), hyperparameter choice on validation.

Run from codes_v3/:  python -I -u -W ignore tools/WP5_S5_dev.py --cache <dir>
Test is never read here. Output: results/WP5/s5_dev.json (grid, chosen config, best number of trees), cache of float32 feature tables
(train_feat.npy, val_feat.npy, meta parquet-free npz) in --cache (outside the repo; delete after the final run).
Selection criterion (fixed in notes/WP5_v2x.md before any result): mean message detection over the 16 SEEN attack classes at the 1% budget
of genuine validation messages; ties broken by validation AUC. Early stopping on validation aucpr picks the number of trees.
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

from common.config import SEED
from common.metrics import auc, budget_threshold
from v2x import adapters, l3, l4, splitting
import WP5_S2_l1 as s2

OUT, BUDGET, HELDOUT = s2.OUT, s2.BUDGET, s2.HELDOUT
log = s2.log
GRID = [
    {"name": "d3_mcw1", "max_depth": 3, "min_child_weight": 1},
    {"name": "d3_mcw50", "max_depth": 3, "min_child_weight": 50},
    {"name": "d5_mcw1", "max_depth": 5, "min_child_weight": 1},
    {"name": "d5_mcw50", "max_depth": 5, "min_child_weight": 50},
    {"name": "d8_mcw1", "max_depth": 8, "min_child_weight": 1},
    {"name": "d8_mcw50", "max_depth": 8, "min_child_weight": 50},
    {"name": "d5_mcw50_slow", "max_depth": 5, "min_child_weight": 50, "learning_rate": 0.05, "subsample": 0.7, "colsample_bytree": 0.7},
    {"name": "d8_mcw50_slow", "max_depth": 8, "min_child_weight": 50, "learning_rate": 0.05, "subsample": 0.7, "colsample_bytree": 0.7},
]


def load_frames():
    v = adapters.load_veremi()
    v["sample_id"] = v["msg_id"]
    sp = json.loads((OUT / "splits_veremi.json").read_text())
    first_t = v.groupby("sender")["t"].min()
    v["group"] = v["sender"].map((first_t // splitting.BLOCK_S).astype(int).astype(str))
    return v, sp


def tracker_from_s4():
    p = json.loads((OUT / "s4_params_veremi.json").read_text())
    return l3.Tracker(l3.KalmanParams(**p))


def meta_of(frame):
    return pd.DataFrame({"label": frame["label"].to_numpy(), "sender": frame["sender"].to_numpy(), "t": frame["t"].to_numpy(),
                         "group": frame["group"].to_numpy(), "x0": (frame["x"].to_numpy() == 0) & (frame["y"].to_numpy() == 0)})


def mean_det_seen(p, meta, thr_budget=BUDGET):
    """Mean detection over the seen classes at the genuine budget of the same scores (validation use only)."""
    lab = meta["label"].to_numpy()
    g = p[lab == 0]
    thr = budget_threshold(g, thr_budget)
    al = p >= thr
    per = {int(c): float(al[lab == c].mean()) for c in sorted(set(lab) - {0}) if c not in HELDOUT}
    return float(np.mean(list(per.values()))), per, float(thr), float(al[lab == 0].mean())


def main():
    cache = Path(sys.argv[sys.argv.index("--cache") + 1])
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log("loading VeReMi")
    v, sp = load_frames()
    tr = splitting.rows_of(v, sp["train"])
    tr = tr[~tr["label"].isin(HELDOUT)]
    va = splitting.rows_of(v, sp["val"])
    va = va[~va["label"].isin(HELDOUT)]
    assert not set(tr["label"]) & set(HELDOUT) and not set(va["label"]) & set(HELDOUT)
    log("train rows", len(tr), "val rows", len(va))
    tracker = tracker_from_s4()
    ftr = l4.feature_table(tr, tracker)
    log("train features done", f"{time.time() - t0:.0f}s")
    fva = l4.feature_table(va, tracker)
    log("val features done", f"{time.time() - t0:.0f}s")
    np.save(cache / "train_feat.npy", ftr.to_numpy())
    np.save(cache / "val_feat.npy", fva.to_numpy())
    mtr, mva = meta_of(tr), meta_of(va)
    mtr.to_pickle(cache / "train_meta.pkl")
    mva.to_pickle(cache / "val_meta.pkl")
    json.dump(list(ftr.columns), open(cache / "columns.json", "w"))
    ytr, yva = (mtr["label"].to_numpy() > 0).astype(int), (mva["label"].to_numpy() > 0).astype(int)
    log("genuine/attack train", int((ytr == 0).sum()), int(ytr.sum()), "val", int((yva == 0).sum()), int(yva.sum()))
    res = []
    for cfg in GRID:
        params = {k: w for k, w in cfg.items() if k != "name"}
        m = l4.GBModel(l4.FEATURES, params)
        t1 = time.time()
        m.fit(ftr, ytr, fva, yva)
        p = m.predict(fva)
        md, per, thr, fa = mean_det_seen(p, mva)
        r = {"name": cfg["name"], "params": params, "best_iteration": m.best_iteration, "n_estimators": m.n_estimators,
             "val_mean_detection_seen16": md, "val_auc": auc(yva, p), "val_threshold": thr, "val_FA": fa, "val_per_class": per,
             "fit_seconds": time.time() - t1}
        log(cfg["name"], f"trees {m.n_estimators} mean_det_seen {md:.4f} auc {r['val_auc']:.4f} fa {fa:.4f} {r['fit_seconds']:.0f}s")
        res.append(r)
    best = max(res, key=lambda r: (round(r["val_mean_detection_seen16"], 6), r["val_auc"]))
    out = {"grid": res, "chosen": best["name"], "chosen_params": best["params"], "chosen_n_estimators": best["n_estimators"],
           "criterion": "mean message detection over 16 seen classes at 1% genuine validation budget (ties: validation AUC)",
           "train_rows": int(len(tr)), "val_rows": int(len(va)), "heldout_removed": HELDOUT, "features": l4.FEATURES,
           "seed": SEED, "total_seconds": time.time() - t0}
    s2.jdump("s5_dev.json", out)
    log("chosen", best["name"], "dev done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
