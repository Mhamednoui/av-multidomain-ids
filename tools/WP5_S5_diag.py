"""WP5 S5 post-hoc diagnostic: is L4's gain on classes 9, 12 (placeholder rows), 17, 18, 19 a "zero residual vector" shortcut?

Run from codes_v3/ after tools/WP5_S5_l4.py:  python -I -u -W ignore tools/WP5_S5_diag.py --cache <dir>
NOT model selection and NOT a second test run: it re-scores the SAME saved final model (results/WP5/s5_l4_model.json) on the same test rows,
splits rows by kind, and fits ONE extra diagnostic model on the train rows of kind 0 only (the result is reported, never used to pick anything).
Row kinds (from l2.Pairs on the frame, raw positions used only to define the kind, never as a model feature):
  0 scored   : the message has a predecessor in its track within DT_MAX and moved (displacement > 0): residuals are informative
  1 unscored : first message of a track, after a gap > DT_MAX or dt <= 0: every residual is exactly 0 by construction
  2 frozen   : valid pair with displacement exactly 0 (message repeats the previous position): residuals are exactly 0 / speed-consistent
Outputs: results/WP5/s5_diag.json, s5_diag.md.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd
import xgboost as xgb

from common.calibration import ECDFCalibrator
from common.config import SEED
from common.metrics import auc, budget_threshold
from v2x import l2, l3, l4, splitting

import WP5_S2_l1 as s2
import WP5_S5_dev as dev

OUT, BUDGET, HELDOUT = s2.OUT, s2.BUDGET, s2.HELDOUT
log, aname, fmt = s2.log, s2.aname, s2.fmt
KIND = {0: "scored", 1: "unscored (first / gap)", 2: "frozen (exact repeat)"}


def row_kinds(df):
    p = l2.Pairs(df)
    k = np.where(~p.valid, 1, np.where(p.d == 0, 2, 0))
    out = np.empty(len(df), int)
    out[p.order] = k
    return out


def main():
    cache = Path(sys.argv[sys.argv.index("--cache") + 1])
    cfg = json.loads((OUT / "s5_dev.json").read_text())
    summ = json.loads((OUT / "s5_summary.json").read_text())["veremi"]
    cols = json.load(open(cache / "columns.json"))
    Ftr, Fva = pd.DataFrame(np.load(cache / "train_feat.npy"), columns=cols), pd.DataFrame(np.load(cache / "val_feat.npy"), columns=cols)
    mtr, mva = pd.read_pickle(cache / "train_meta.pkl"), pd.read_pickle(cache / "val_meta.pkl")
    v, sp = dev.load_frames()
    tr = splitting.rows_of(v, sp["train"])
    tr = tr[~tr["label"].isin(HELDOUT)]
    va = splitting.rows_of(v, sp["val"])
    va = va[~va["label"].isin(HELDOUT)]
    te = splitting.rows_of(v, sp["test"])
    ktr, kva, kte = row_kinds(tr), row_kinds(va), row_kinds(te)
    tracker = dev.tracker_from_s4()
    Fte = l4.feature_table(te, tracker)
    mte = dev.meta_of(te)
    yte = mte["label"].to_numpy() > 0
    ytr, yva = mtr["label"].to_numpy() > 0, mva["label"].to_numpy() > 0
    # --- saved final model, same test rows ---
    m = l4.GBModel(l4.FEATURES, cfg["chosen_params"], n_estimators=cfg["chosen_n_estimators"])
    m.model = xgb.XGBClassifier()
    m.model.load_model(str(OUT / "s5_l4_model.json"))
    pv, pt = m.predict(Fva), m.predict(Fte)
    log("reproduced test AUC", auc(yte.astype(int), pt), "(summary", summ["variants"]["full"]["test_auc"], ")")
    thr = summ["thresholds"]["L4_probability"]
    assert abs(budget_threshold(pv[~yva].astype(float), BUDGET) - thr) < 1e-6
    al = pt >= thr
    out = {"reproduced_test_auc": auc(yte.astype(int), pt), "summary_test_auc": summ["variants"]["full"]["test_auc"], "kinds": KIND}
    # --- kind composition and L4 behaviour by kind ---
    comp = {}
    for nm, kk in (("train", ktr), ("val", kva), ("test", kte)):
        y = {"train": ytr, "val": yva, "test": yte}[nm]
        comp[nm] = {"genuine": {KIND[k]: float((kk[~y] == k).mean()) for k in KIND}, "attack": {KIND[k]: float((kk[y] == k).mean()) for k in KIND}}
    out["composition"] = comp
    out["L4_genuine_FA_by_kind"] = {KIND[k]: {"n": int(((kte == k) & ~yte).sum()), "FA": float(al[(kte == k) & ~yte].mean()) if ((kte == k) & ~yte).any() else None} for k in KIND}
    classes = [aname(c) for c in range(1, 20)]
    lab = mte["label"].to_numpy()
    rows = {}
    for c in range(1, 20):
        mk = lab == c
        rows[aname(c)] = {KIND[k]: {"share": float((kte[mk] == k).mean()), "L4_detection": float(al[mk & (kte == k)].mean()) if (mk & (kte == k)).any() else None}
                          for k in KIND}
    out["by_class_kind"] = rows
    # --- baseline restricted to scored rows, re-thresholded on genuine validation scored rows (L1 rate + L2 + L3 max-union, one 1% budget) ---
    base = ["rate", "pos_speed", "pos_heading", "speed_change", "implied_speed", "heading_rate", "accel_consistency", "overlap", "nis", "cusum_hi"]
    k0v = (kva == 0) & ~yva
    sv_, st_ = [], []
    for b in base:
        c = ECDFCalibrator().fit(Fva[b].to_numpy(float)[k0v])
        sv_.append(c.transform(Fva[b].to_numpy(float)))
        st_.append(c.transform(Fte[b].to_numpy(float)))
    sv_, st_ = np.max(sv_, axis=0), np.max(st_, axis=0)
    thr_b = budget_threshold(sv_[k0v], BUDGET)
    al_b0 = st_ >= thr_b
    # --- diagnostic model trained on kind-0 rows only ---
    sel = ktr == 0
    d = l4.GBModel(l4.FEATURES, cfg["chosen_params"], n_estimators=cfg["chosen_n_estimators"]).fit(Ftr[sel], ytr[sel].astype(int))
    pv0, pt0 = d.predict(Fva), d.predict(Fte)
    thr0 = budget_threshold(pv0[k0v].astype(float), BUDGET)
    al0 = pt0 >= thr0
    k0t = kte == 0
    out["diag_model_scored_rows_only"] = {"n_train_rows": int(sel.sum()), "threshold_p": float(thr0), "val_FA_scored_genuine": float((pv0[k0v] >= thr0).mean()),
                                         "test_FA_scored_genuine": float(al0[k0t & ~yte].mean()), "baseline_threshold_score": float(thr_b),
                                         "baseline_test_FA_scored_genuine": float(al_b0[k0t & ~yte].mean()),
                                         "test_auc_scored_rows": auc(yte[k0t].astype(int), pt0[k0t]),
                                         "baseline_auc_scored_rows": auc(yte[k0t].astype(int), st_[k0t]),
                                         "headline_L4_auc_scored_rows": auc(yte[k0t].astype(int), pt[k0t]),
                                         "importance": dict(list(d.importance().items())[:10])}
    pc = {}
    for c in range(1, 20):
        mk = (lab == c) & k0t
        pc[aname(c)] = {"n_scored_rows": int(mk.sum()), "share_of_class_rows": float(mk.sum() / max((lab == c).sum(), 1)),
                        "diag_model_detection": float(al0[mk].mean()) if mk.any() else None,
                        "headline_L4_detection": float(al[mk].mean()) if mk.any() else None,
                        "baseline_union_detection": float(al_b0[mk].mean()) if mk.any() else None}
    out["scored_rows_by_class"] = pc
    # genuine births: false alarms per genuine first message
    first = kte == 1
    isfirst = Fte["is_first"].to_numpy() > 0
    out["genuine_first_messages"] = {"n": int((isfirst & ~yte).sum()), "L4_FA_per_genuine_first_message": float(al[isfirst & ~yte].mean()),
                                    "share_of_L4_genuine_alarms_that_are_first_messages": float((al & ~yte & isfirst).sum() / max((al & ~yte).sum(), 1)),
                                    "share_of_L4_genuine_alarms_that_are_frozen": float((al & ~yte & (kte == 2)).sum() / max((al & ~yte).sum(), 1))}
    # --- group means on scored rows (seen / unseen) ---
    def mean_over(key, cl):
        v_ = [pc[c][key] for c in cl if pc[c][key] is not None and pc[c]["n_scored_rows"] >= 50]
        return float(np.mean(v_)) if v_ else None
    seen = [aname(c) for c in range(1, 20) if c not in HELDOUT]
    out["scored_rows_means"] = {k: {"seen": mean_over(k, seen), "unseen_6_17": mean_over(k, [aname(6), aname(17)]), "unseen_6": mean_over(k, [aname(6)])}
                                for k in ("diag_model_detection", "headline_L4_detection", "baseline_union_detection")}
    s2.jdump("s5_diag.json", out)
    # --- markdown ---
    L = ["**Row kinds: share of rows (VeReMi)**", "", "| split | class | " + " | ".join(KIND.values()) + " |", "|---|---|---|---|---|"]
    for nm in comp:
        for who in ("genuine", "attack"):
            L.append(f"| {nm} | {who} | " + " | ".join(fmt(comp[nm][who][KIND[k]]) for k in KIND) + " |")
    L += ["", "**L4 (headline model) false alarms on genuine TEST rows by kind**", "", "| kind | genuine rows | FA |", "|---|---|---|"]
    for k, r in out["L4_genuine_FA_by_kind"].items():
        L.append(f"| {k} | {r['n']} | {fmt(r['FA'])} |")
    g = out["genuine_first_messages"]
    L += ["", f"First messages of genuine tracks: {g['n']}; L4 alarms on {fmt(g['L4_FA_per_genuine_first_message'])} of them; "
          f"{fmt(g['share_of_L4_genuine_alarms_that_are_first_messages'])} of all L4 genuine false alarms are first messages, "
          f"{fmt(g['share_of_L4_genuine_alarms_that_are_frozen'])} are frozen repeats.", ""]
    L += ["**Per class: share of rows by kind and headline-L4 detection by kind (TEST)**", "",
          "| class | scored share | scored: L4 | unscored share | unscored: L4 | frozen share | frozen: L4 |", "|---|---|---|---|---|---|---|"]
    for c, r in rows.items():
        s0, s1, s2_ = r[KIND[0]], r[KIND[1]], r[KIND[2]]
        L.append(f"| {c}{' *' if int(c[:2]) in HELDOUT else ''} | {fmt(s0['share'])} | {fmt(s0['L4_detection'])} | {fmt(s1['share'])} | {fmt(s1['L4_detection'])} | {fmt(s2_['share'])} | {fmt(s2_['L4_detection'])} |")
    dm = out["diag_model_scored_rows_only"]
    L += ["", f"**Scored rows only (kind 0): diagnostic L4 trained on scored train rows only vs headline L4 vs baseline union (re-thresholded on genuine val scored rows, 1%)**", "",
          f"FA on genuine scored test rows: diagnostic {fmt(dm['test_FA_scored_genuine'])}, baseline {fmt(dm['baseline_test_FA_scored_genuine'])}; "
          f"AUC on scored test rows: diagnostic {dm['test_auc_scored_rows']:.3f}, headline L4 {dm['headline_L4_auc_scored_rows']:.3f}, baseline {dm['baseline_auc_scored_rows']:.3f}.", "",
          "| class | scored rows | share of class | diagnostic L4 | headline L4 | baseline union |", "|---|---|---|---|---|---|"]
    for c, r in pc.items():
        L.append(f"| {c}{' *' if int(c[:2]) in HELDOUT else ''} | {r['n_scored_rows']} | {fmt(r['share_of_class_rows'])} | {fmt(r['diag_model_detection'])} | {fmt(r['headline_L4_detection'])} | {fmt(r['baseline_union_detection'])} |")
    mm = out["scored_rows_means"]
    L.append(f"| mean over classes with >= 50 scored rows: seen (16) | | | {fmt(mm['diag_model_detection']['seen'])} | {fmt(mm['headline_L4_detection']['seen'])} | {fmt(mm['baseline_union_detection']['seen'])} |")
    L.append(f"| unseen 6 and 17 | | | {fmt(mm['diag_model_detection']['unseen_6_17'])} | {fmt(mm['headline_L4_detection']['unseen_6_17'])} | {fmt(mm['baseline_union_detection']['unseen_6_17'])} |")
    (OUT / "s5_diag.md").write_text("\n".join(L) + "\n")
    log("done")


if __name__ == "__main__":
    main()
