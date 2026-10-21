"""WP1 S8 development pass: KITTI TRAIN + VAL drives only (test rows are never read here). Nested LODO over the drives with runs:
in every fold the CUSUM configuration, every layer's calibration (ECDF + tie-safe 1% threshold) and the combiner (method, weights,
threshold; halves by drive) are fitted on the other drives only.
1. CUSUM selection per fold and on all dev drives (compare with S4_dev.json).
2. Every layer alone (nested), 16 default + 4 optional.
3. Combiner methods noisy_or / logistic / max / auto on the 16 default layers; logistic control without the Doppler / meaconing attack rows.
4. Choice of the deployed method by the pre-registered rule (notes/WP1_gps.md S8).
5. Ablation with the chosen method: all, all-but-one, + each optional layer.
Outputs: results/WP1/S8_dev.json. Run from codes_v3/: python -u -W ignore tools/WP1_S8_dev.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S8_lib as W
from gps import stack as ST

T0 = time.time()
PARAMETER_FREE = ("noisy_or", "noisy_or_log", "max")


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def choose_method(res):
    """Pre-registered rule: best mean run-level detection among methods with nested FA <= 1.5%; logistic only if it beats the best
    parameter-free method by >= 2 points; none under 1.5% -> lowest FA."""
    ok = {m: r for m, r in res.items() if r["fa_clean_runs"] <= 0.015}
    pool = ok or res
    if not ok:
        return min(pool, key=lambda m: pool[m]["fa_clean_runs"]), "no method has nested FA <= 1.5%: lowest FA"
    pf = [m for m in PARAMETER_FREE if m in pool]
    best_pf = max(pf, key=lambda m: pool[m]["mean_run_detected"]) if pf else None
    if "logistic" in pool and (best_pf is None or pool["logistic"]["mean_run_detected"] >= pool[best_pf]["mean_run_detected"] + 0.02):
        return "logistic", "logistic beats the best parameter-free method by >= 2 points"
    return best_pf, "best parameter-free method (logistic does not beat it by 2 points, or FA > 1.5%)"


def main():
    raw = W.load_raw()
    dev = raw[raw["part"].isin(W.DEV_PARTS)].copy()
    assert not (dev["part"] == "test").any()
    ri = ST.RunIndex(dev)
    drives = sorted(dev["drive"].unique())
    cand = W.candidates(dev)
    names, opt = ST.DEFAULT_LAYERS, ST.OPTIONAL_LAYERS
    log("dev rows", len(dev), "drives with runs", len(drives), "runs", len(ri.start), "candidates", len(cand[0]), len(cand[1]))
    res = {"drives": drives, "n_rows": len(dev), "n_runs": int(len(ri.start))}
    # ---- 1. folds ----
    folds = {d: W.FoldState(dev, ri, [x for x in drives if x != d], names, cand, optional=opt) for d in drives}
    full = W.FoldState(dev, ri, drives, names, cand, optional=opt)
    s4 = json.loads((W.L.OUT / "S4_dev.json").read_text())["selection"]
    res["cusum_selection"] = {"full_dev": full.sel, "s4_dev_json": {"ekf": s4["best_ekf"], "dr": s4["best_dr"], "J_ekf": s4["J"][s4["best_ekf"]], "J_dr": s4["J"][s4["best_dr"]]},
                              "per_fold": {d: folds[d].sel for d in drives}}
    cnt = {}
    for d in drives:
        for k in ("ekf", "dr"):
            cnt.setdefault(k, {}).setdefault(folds[d].sel[k], 0)
            cnt[k][folds[d].sel[k]] += 1
    res["cusum_selection"]["fold_counts"] = cnt
    log("selection full", full.sel, "fold counts", cnt)
    # ---- 2. layers alone, nested ----
    alone = {}
    for n in names + opt:
        f = W.nested_layer_flags(dev, folds, n)
        alone[n] = W.compact(dev, ri, f, W.nested_raw(dev, folds, n))
        log("alone", n, "FA", round(alone[n]["fa_clean_runs"], 4), "mean run", round(alone[n]["mean_run_detected"], 3), "AUC", round(alone[n]["auc_row_level"], 3))
    res["alone_nested"] = alone
    # ---- 3. combiners ----
    # RULES 5.7: the deployed combiner never sees the Doppler-consistent / meaconing attack rows (fit_exclude); the same exclusion is
    # applied to every method so that the choice is made under the zero-shot regime. The six-attack logistic is a side row.
    unseen_rows = ((dev["attack"].isin(["doppler_spoof", "meaconing"])) & (dev["label"] == 1)).to_numpy()
    meth = {}
    for m in ST.METHODS_EXT + ("auto",):
        s, f, info = W.nested_combine(dev, folds, names, m, fit_exclude=unseen_rows)
        meth[m] = W.compact(dev, ri, f, s)
        meth[m]["fold_methods"] = {d: info[d]["method"] for d in drives}
        log("combiner", m, "FA", round(meth[m]["fa_clean_runs"], 4), "mean run", round(meth[m]["mean_run_detected"], 3), "AUC", round(meth[m]["auc_row_level"], 3),
            {a: round(v, 2) for a, v in meth[m]["run_detected"].items()})
    s, f, info = W.nested_combine(dev, folds, names, "logistic")
    meth["logistic_all6_seen"] = W.compact(dev, ri, f, s)
    log("combiner logistic fitted on all six attacks (side row)", {a: round(v, 2) for a, v in meth["logistic_all6_seen"]["run_detected"].items()})
    res["combiners_nested"] = meth
    res["combiner_fit_regime"] = "all combiners fitted without the label-1 rows of doppler_spoof and meaconing (unseen attack types)"
    chosen, why = choose_method({m: meth[m] for m in ST.METHODS_EXT})
    res["chosen_method"], res["chosen_reason"] = chosen, why
    log("CHOSEN", chosen, why)
    # ---- 5. ablation with the chosen method ----
    abl = {"all": meth[chosen]}
    for n in names:
        rest = [x for x in names if x != n]
        s, f, _ = W.nested_combine(dev, folds, rest, chosen, fit_exclude=unseen_rows)
        abl["all_but_" + n] = W.compact(dev, ri, f, s)
        log("all but", n, "FA", round(abl["all_but_" + n]["fa_clean_runs"], 4), "mean run", round(abl["all_but_" + n]["mean_run_detected"], 3))
    for n in opt:
        s, f, _ = W.nested_combine(dev, folds, names + [n], chosen, fit_exclude=unseen_rows)
        abl["plus_" + n] = W.compact(dev, ri, f, s)
        log("plus", n, "FA", round(abl["plus_" + n]["fa_clean_runs"], 4), "mean run", round(abl["plus_" + n]["mean_run_detected"], 3))
    res["ablation_nested"] = abl
    (W.L.OUT / "S8_dev.json").write_text(json.dumps(res, indent=1, default=float))
    log("done")


if __name__ == "__main__":
    main()
