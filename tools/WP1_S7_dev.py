"""WP1 S7 development pass: KITTI TRAIN + VAL drives only (15 drives with runs); the test drives are not read here.
  L3  8 candidates (residual set A/B x lw / mcd / if256 / if1024): out-of-fold (leave-one-drive-out) scores, LODO pooled 1% threshold, run-level
      detection, J; STRICTLY nested selection (inner leave-two-out); the test choice = best J on all dev drives; final model fit on all dev label-0 rows.
  L4  v2 C2 (XGBoost, 4 v2 attacks) + L4_nopos (no pos_step features) + L4_all (6 attacks, upper bound): nested LODO (validation = the val drives other
      than the held-out one), importances, held-out FA per drive; final models = train drives, selection on the val drives (v2 protocol).
Outputs: results/WP1/S7_dev.json, S7_dev_grid.md, cache/s7_oof.npz, cache/s7_final.pkl. Run from codes_v3/: python -u -W ignore tools/WP1_S7_dev.py
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S7_lib as W
import WP1_S4_lib as L
from common.metrics import auc
from gps import learned

T0 = time.time()


def log(*a, **k):
    print(f"[{time.time() - T0:6.0f}s]", *a, **k)


def short(r, name):
    return {"name": name, "J": r["J"], "lodo_heldout_fa": r["lodo"]["heldout_fa_pooled"], "worst_drive_fa": r["lodo"]["heldout_fa_worst_drive"],
            "per_drive_fa": {k: v["fa"] for k, v in r["lodo"]["per_drive"].items()}, "run_detected": r["summary"]["run_detected"],
            "row_detection": r["summary"]["row_detection"], "slow_drift": r["summary"]["slow_drift_lt_0.5_within_30s"],
            "delays": r["summary"]["delays"], "clean_run_fa_pooled_threshold": r["summary"]["false_alarm_clean_runs"]}


def main():
    kx = L.kitti_stream()
    dev0 = kx[kx["part"].isin(L.DEV_PARTS)]
    assert not dev0["part"].eq("test").any()
    dev = W.feature_frame(dev0, "dev")
    y = dev["label"].to_numpy()
    F = W.c2_frame(dev)
    assert np.allclose(F['dr_resid_10'].to_numpy(), dev['dr_resid_10'].to_numpy(), atol=1e-6)      # C2 dead-reckoning feature = B2 feature
    drives = sorted(dev["drive"].unique())
    log("dev rows", len(dev), "drives", len(drives), flush=True)
    res = {"drives": drives, "n_rows": len(dev)}

    # ------------------------------- L3 -------------------------------
    cands = learned.L3_CANDIDATES
    oof3, pair3, _ = W.l3_scores(dev, cands, log)
    res["L3"] = {"candidates": {}}
    for c in cands:
        r = W.evaluate_scores(dev, oof3[c], c)
        res["L3"]["candidates"][c] = short(r, c)
        res["L3"]["candidates"][c]["auc_row"] = auc(y, oof3[c])
        log("L3", c, "J", round(r["J"], 3), "AUC", round(res["L3"]["candidates"][c]["auc_row"], 3), "heldout FA", round(r["lodo"]["heldout_fa_pooled"], 4),
            "run det", {a: round(v, 2) for a, v in r["summary"]["run_detected"].items()}, flush=True)
    best3 = max(cands, key=lambda c: res["L3"]["candidates"][c]["J"])
    res["L3"]["selected_all_dev"] = best3
    res["L3"]["nested"] = W.l3_nested(dev, pair3, oof3, drives, list(cands))
    log("L3 nested held-out FA", res["L3"]["nested"]["heldout_fa_pooled"], "J", res["L3"]["nested"]["J"], res["L3"]["nested"]["choice_counts"], "selected:", best3, flush=True)

    # ------------------------------- L4 -------------------------------
    variants = {"l4_c2": (learned.C2_ALL, W.V2_ATTACKS), "l4_nopos": (learned.C2_NOPOS, W.V2_ATTACKS), "l4_all": (learned.C2_ALL, tuple(L.ATT))}
    oof4, res["L4"] = {}, {}
    for v, (feats, atts) in variants.items():
        log("L4 variant", v, flush=True)
        oof4[v], info, imp = W.l4_oof(dev, F, feats, atts, log=log)
        r = W.evaluate_scores(dev, oof4[v], v)
        res["L4"][v] = {**short(r, v), "auc_row": auc(y, oof4[v]), "importance_gain_mean_over_folds": imp, "folds": info,
                        "pos_step_share": float(sum(imp.get(k, 0.0) for k in learned.NON_PHYSICAL))}
        log("L4", v, "J", round(r["J"], 3), "AUC", round(res["L4"][v]["auc_row"], 3), "heldout FA", round(r["lodo"]["heldout_fa_pooled"], 4), "worst", round(r["lodo"]["heldout_fa_worst_drive"], 3),
            "run det", {a: round(x, 2) for a, x in r["summary"]["run_detected"].items()}, "importance", {k: round(x, 2) for k, x in imp.items()}, flush=True)

    # ------------------------------- final models (dev data only) -------------------------------
    s, kind = learned.L3_CANDIDATES[best3]
    final = {"l3": learned.ResidualNormalModel(kind, learned.res_cols(s)).fit(dev[y == 0]), "l3_name": best3}
    part = dev["part"].to_numpy()
    tr, va = part == "train", part == "val"
    final["l4"] = {}
    for v, (feats, atts) in variants.items():
        mask = W.l4_rows(dev, atts)
        final["l4"][v] = W.l4_fit(F, y, tr, va, feats, mask)
        log("final", v, "val F1", final["l4"][v].info["val_f1_macro"], final["l4"][v].info["best"], flush=True)
        res["L4"][v]["final_model"] = {"best": final["l4"][v].info["best"], "val_f1": final["l4"][v].info["val_f1_macro"],
                                       "importance_gain": final["l4"][v].importance()}
    np.savez(W.CACHE / "s7_oof.npz", index=dev.index.to_numpy(), l3=oof3[best3], **{k: v for k, v in oof4.items()})
    with open(W.CACHE / "s7_final.pkl", "wb") as f:
        pickle.dump(final, f)
    (L.OUT / "S7_dev.json").write_text(json.dumps(res, indent=1, default=float))
    rows = ["| candidate | J | AUC (row) | LODO held-out FA | worst drive | " + " | ".join(L.ATT) + " |", "|---" * (5 + len(L.ATT)) + "|"]
    for grp in (res["L3"]["candidates"], res["L4"]):
        for c, r in sorted(grp.items(), key=lambda kv: -kv[1]["J"]):
            rows.append(f"| {c} | {r['J']:.3f} | {r['auc_row']:.3f} | {100 * r['lodo_heldout_fa']:.2f}% | {100 * r['worst_drive_fa']:.2f}% | " + " | ".join(f"{100 * r['run_detected'][a]:.0f}%" for a in L.ATT) + " |")
    (L.OUT / "S7_dev_grid.md").write_text("\n".join(rows) + "\n")
    log("done", flush=True)


if __name__ == "__main__":
    main()
