"""WP5 S6 (dev stage): choose the feature set and hyperparameters of the deployable scored-row L4 on VeReMi VALIDATION only.

Run from codes_v3/:  python -I -u -W ignore tools/WP5_S6_dev.py --cache <dir>
Test is never read. Rule (notes/WP5_v2x.md, 'S6 ... acceptance rule', written before any result): train on scored TRAIN rows only
(kind 0 of v2x.l4.row_kinds; attack types 6, 12, 17 removed from train, validation and neighbour features), 4 candidate feature sets
(S0, S1 reference only; S2, S3 eligible because they have no time scale), criterion = mean detection over the seen classes with >= 50 scored
validation rows at the 1% budget of scored genuine validation rows; S2 wins over S3 unless S3 is better by >= 1.0 point.
Output: results/WP5/s6_dev.json; cache (float32 feature tables, row kinds, meta) in --cache, deleted after the final run.
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
from v2x import l4, splitting
import WP5_S2_l1 as s2
import WP5_S5_dev as dev5

OUT, BUDGET, HELDOUT = s2.OUT, s2.BUDGET, s2.HELDOUT
log = s2.log
MIN_SCORED = 50
SIMPLE_MARGIN = 0.01
GRID = [
    {"name": "d3_mcw1", "max_depth": 3, "min_child_weight": 1},
    {"name": "d5_mcw1", "max_depth": 5, "min_child_weight": 1},
    {"name": "d5_mcw50", "max_depth": 5, "min_child_weight": 50},
    {"name": "d8_mcw50", "max_depth": 8, "min_child_weight": 50},
]


def criterion(p, lab, kinds):
    """Mean detection over seen classes (>= MIN_SCORED scored rows) on scored attack rows at the 1% budget of scored genuine rows."""
    k0 = kinds == 0
    thr = budget_threshold(p[k0 & (lab == 0)].astype(float), BUDGET)
    al = p >= thr
    per = {}
    for c in sorted(set(lab) - {0}):
        m = k0 & (lab == c)
        if c in HELDOUT or m.sum() < MIN_SCORED:
            continue
        per[int(c)] = float(al[m].mean())
    return float(np.mean(list(per.values()))), per, float(thr), float(al[k0 & (lab == 0)].mean())


def main():
    cache = Path(sys.argv[sys.argv.index("--cache") + 1])
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    v, sp = dev5.load_frames()
    tr = splitting.rows_of(v, sp["train"])
    tr = tr[~tr["label"].isin(HELDOUT)].reset_index(drop=True)
    va = splitting.rows_of(v, sp["val"])
    va = va[~va["label"].isin(HELDOUT)].reset_index(drop=True)
    assert not set(tr["label"]) & set(HELDOUT) and not set(va["label"]) & set(HELDOUT)
    log("train rows", len(tr), "val rows", len(va))
    tracker = dev5.tracker_from_s4()
    tabs = {}
    for nm, fr in (("train", tr), ("val", va)):
        raw = l4.message_scores(fr, tracker)
        for tag, tw in (("count", None), ("time", l4.WINDOW_S)):
            tabs[(nm, tag)] = l4.feature_table(fr, tracker, raw, time_window_s=tw)
        np.save(cache / f"{nm}_kinds.npy", l4.row_kinds(fr))
        dev5.meta_of(fr).to_pickle(cache / f"{nm}_meta.pkl")
        log(nm, "features done", f"{time.time() - t0:.0f}s")
    json.dump(list(tabs[("train", "count")].columns), open(cache / "columns.json", "w"))
    for (nm, tag), t in tabs.items():
        np.save(cache / f"{nm}_feat_{tag}.npy", t.to_numpy())
    ktr, kva = np.load(cache / "train_kinds.npy"), np.load(cache / "val_kinds.npy")
    ltr, lva = tr["label"].to_numpy(), va["label"].to_numpy()
    ytr, yva = (ltr > 0).astype(int), (lva > 0).astype(int)
    s_tr, s_va = ktr == 0, kva == 0
    comp = {"train_rows": int(len(tr)), "train_scored": int(s_tr.sum()), "val_rows": int(len(va)), "val_scored": int(s_va.sum()),
            "val_genuine_scored": int((s_va & (yva == 0)).sum()), "val_attack_scored": int((s_va & (yva == 1)).sum())}
    log(comp)
    res = []
    for sname, spec in l4.SCORED_SETS.items():
        tag = "count" if spec["time_window_s"] is None else "time"
        Ftr, Fva = tabs[("train", tag)], tabs[("val", tag)]
        grid = GRID if spec["eligible"] else [g for g in GRID if g["name"] == "d5_mcw1"]
        for cfg in grid:
            params = {k: w for k, w in cfg.items() if k != "name"}
            m = l4.GBModel(spec["features"], params)
            t1 = time.time()
            m.fit(Ftr[s_tr], ytr[s_tr], Fva[s_va], yva[s_va])
            p = np.zeros(len(va))
            p[s_va] = m.predict(Fva[s_va])
            md, per, thr, fa = criterion(p, lva, kva)
            r = {"set": sname, "eligible": spec["eligible"], "config": cfg["name"], "params": params, "n_features": len(spec["features"]),
                 "best_iteration": m.best_iteration, "n_estimators": m.n_estimators, "val_mean_detection_seen_scored": md,
                 "val_auc_scored": auc(yva[s_va], p[s_va]), "val_threshold_p": thr, "val_FA_scored_genuine": fa, "val_per_class": per,
                 "fit_seconds": time.time() - t1}
            log(sname, cfg["name"], f"trees {m.n_estimators} mean_det {md:.4f} auc {r['val_auc_scored']:.4f} fa {fa:.4f} {r['fit_seconds']:.0f}s")
            res.append(r)
    best_by_set = {}
    for sname, spec in l4.SCORED_SETS.items():
        rs = [r for r in res if r["set"] == sname]
        best_by_set[sname] = max(rs, key=lambda r: (round(r["val_mean_detection_seen_scored"], 6), r["val_auc_scored"]))
    elig = [s for s, sp_ in l4.SCORED_SETS.items() if sp_["eligible"]]
    s2r, s3r = best_by_set["S2_resid"], best_by_set["S3_timewin"]
    gain = s3r["val_mean_detection_seen_scored"] - s2r["val_mean_detection_seen_scored"]
    chosen = best_by_set["S3_timewin"] if gain >= SIMPLE_MARGIN else best_by_set["S2_resid"]
    spec = l4.SCORED_SETS[chosen["set"]]
    out = {"runs": res, "best_by_set": {k: {"config": r["config"], "val_mean_detection_seen_scored": r["val_mean_detection_seen_scored"]} for k, r in best_by_set.items()},
           "S3_minus_S2_validation_points": gain, "simplicity_margin": SIMPLE_MARGIN, "chosen_set": chosen["set"], "chosen_config": chosen["config"],
           "chosen_params": chosen["params"], "chosen_n_estimators": chosen["n_estimators"], "chosen_features": spec["features"],
           "chosen_time_window_s": spec["time_window_s"], "eligible_sets": elig, "composition": comp,
           "criterion": "mean detection over seen classes (>= 50 scored val rows), scored attack rows, 1% of scored genuine validation rows",
           "heldout_removed": HELDOUT, "seed": SEED, "total_seconds": time.time() - t0}
    s2.jdump("s6_dev.json", out)
    log("chosen", chosen["set"], chosen["config"], f"S3-S2 {gain:+.4f}", "dev done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
