"""WP3 S7 validation round for L4 (retrained v2 descriptor model on the physically consistent attack set) and its leakage controls.
Train = 13 train drives; validation = 3 val drives (hyperparameter search, threshold, controls). Test is not touched.
Writes results/WP3/S7/dev_l4.json and importance_dev.csv. Usage: python -u -W ignore tools/WP3_S7_dev_l4.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP3_S7_lib import *  # noqa
from common.config import RESULTS
from lidar.learned_eval import PHYS, CMP

RES = RESULTS / "WP3" / "S7"
TYPES_NOPH = ["PointDrop", "IntensitySpoof"]
BUDGET = ["ph_budget_near", "ph_budget_far"]
PHANT = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far"]


def clean_params(prm):
    return {a: (b if isinstance(b, (int, str)) else float(b)) for a, b in prm.items()}


def group_shares(imp):
    grp = pd.Series({n: L4.feature_group(n) for n in imp.index})
    return {g: float(v) for g, v in imp.groupby(grp.loc[imp.index].to_numpy()).sum().sort_values(ascending=False).items()}


def main():
    t0 = time.time()
    tr, va = drives_of("train"), drives_of("val")
    X, y, mtr = train_set(tr)
    Xes, yes, _ = train_set(va)                      # validation rows in the training layout (early stopping)
    nm_va, nx_va = L4.normal_rows(va)
    ev_m, ev_X = load_rows("ev", va)
    out = {"n_train": int(len(y)), "n_val_es": int(len(yes)), "n_val_normal": int(len(nx_va)), "search": []}
    print("train", X.shape, np.bincount(y), "val", np.bincount(yes), flush=True)

    rng = np.random.default_rng(42)
    best = None
    for k in range(12):
        prm = L4.random_params(rng)
        m = L4.fit_xgb(X, y, prm, 800, Xva=Xes, yva=yes)
        n_trees = int(m.best_iteration) + 1
        thr, fa, det = detection_at_budget(m, nx_va, ev_m, ev_X)
        sc = mean_phys(det)
        out["search"].append({"params": clean_params(prm), "n_trees": n_trees, "val_fa": fa, "mean_phys": sc, "det": det})
        print(k, prm, n_trees, f"FA {fa:.3f} mean_phys {sc:.3f}", {a: round(v, 2) for a, v in det.items() if a in PHYS}, f"{time.time() - t0:.0f}s", flush=True)
        if best is None or sc > best[0]:
            best = (sc, prm, n_trees)
    _, prm, n_trees = best
    out["choice"] = {"params": clean_params(prm), "n_trees": n_trees, "mean_phys_val": best[0]}
    print("CHOICE", out["choice"], flush=True)

    m = L4.fit_xgb(X, y, prm, n_trees)
    thr, fa, det = detection_at_budget(m, nx_va, ev_m, ev_X)
    out["chosen_val"] = {"threshold": thr, "fa": fa, "det": det}
    sel = ev_m.attack.isin(PHYS).to_numpy()
    Xe_phys = np.vstack([nx_va, ev_X[sel]])
    ev_y = np.r_[np.zeros(len(nx_va), int), np.ones(int(sel.sum()), int)]
    out["val_auc"] = L4.auc(ev_y, L4.attack_score(m, Xe_phys))
    sn = L4.attack_score(m, nx_va)
    out["val_auc_by_attack"] = {}
    for a in PHYS + CMP:
        k = (ev_m.attack == a).to_numpy()
        out["val_auc_by_attack"][a] = L4.auc(np.r_[np.zeros(len(sn)), np.ones(int(k.sum()))], np.r_[sn, L4.attack_score(m, ev_X[k])])
    print("chosen", fa, det, "AUC", out["val_auc"], flush=True)

    # C1 null control
    nulls = L4.null_aucs(X, y, prm, n_trees, Xe_phys, ev_y)
    out["null_control"] = {"seeds": [11, 12, 13, 14, 15], "aucs": nulls, "mean": float(np.mean(nulls)), "bound": 0.55, "met": bool(np.mean(nulls) <= 0.55)}
    print("null", nulls, np.mean(nulls), flush=True)

    # C2 importance (total, per group, per class) and ablation
    imp = L4.importance_table(m)
    imp.to_csv(RES / "importance_dev.csv", header=["gain_share"])
    out["importance"] = {"top10": {n: float(v) for n, v in imp.head(10).items()}, "top1_share": float(imp.iloc[0]), "by_group": group_shares(imp),
                         "per_class": {}}
    for c, name in ((1, "PointDrop"), (2, "IntensitySpoof"), (3, "Phantom")):
        k = (y == 0) | (y == c)
        mc = L4.fit_xgb(X[k], (y[k] > 0).astype(int), prm, n_trees)
        ic = L4.importance_table(mc)
        out["importance"]["per_class"][name] = {"top10": {n: float(v) for n, v in ic.head(10).items()}, "groups": dict(list(group_shares(ic).items())[:4])}
        print("class", name, [(n, round(float(v), 3)) for n, v in ic.head(5).items()], flush=True)
    top5 = [L4.NAMES.index(n) for n in imp.index[:5]]
    keep = np.setdiff1d(np.arange(X.shape[1]), top5)
    ma = L4.fit_xgb(X[:, keep], y, prm, n_trees)
    ta, faa, deta = detection_at_budget(ma, nx_va[:, keep], ev_m, ev_X[:, keep])
    out["ablation_top5"] = {"dropped": list(imp.index[:5]), "fa": faa, "det": deta, "mean_phys": mean_phys(deta)}
    print("ablation", mean_phys(deta), flush=True)

    # C3 leave-one-attack-type-out
    groups = {"Phantom (all four)": PHANT, "budget phantoms": BUDGET, "replace phantoms": ["ph_replace_near", "ph_replace_far"], "PointDrop": ["PointDrop"],
              "IntensitySpoof": ["IntensitySpoof"]}
    out["loto"] = {}
    for gname, held in groups.items():
        types = [t for t in PHYS if t not in held]
        Xl, yl, _ = train_set(tr, types)
        ml = L4.fit_xgb(Xl, yl, prm, n_trees)
        _, fal, detl = detection_at_budget(ml, nx_va, ev_m, ev_X)
        out["loto"][gname] = {"held_out": held, "val_fa": fal, "held_out_detection": {a: detl[a] for a in held},
                              "in_distribution_detection": {a: det[a] for a in held}, "seen_detection": {a: detl[a] for a in types}}
        print("LOTO", gname, {a: (round(detl[a], 3), round(det[a], 3)) for a in held}, flush=True)

    # comparison variants
    Xn, yn, _ = train_set(tr, TYPES_NOPH)
    mn = L4.fit_xgb(Xn, yn, prm, n_trees)
    _, fan, detn = detection_at_budget(mn, nx_va, ev_m, ev_X)
    out["variant_nophantom"] = {"val_fa": fan, "det": detn}
    _, Xv2, yv2 = L4.v2_rows(tr)
    m2 = L4.fit_xgb(Xv2, yv2, prm, n_trees)
    _, fa2, det2 = detection_at_budget(m2, nx_va, ev_m, ev_X)
    out["variant_v2"] = {"val_fa": fa2, "det": det2}
    print("nophantom", {a: round(v, 2) for a, v in detn.items()}, "\nv2", {a: round(v, 2) for a, v in det2.items()}, flush=True)
    out["seconds"] = time.time() - t0
    (RES / "dev_l4.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
