"""WP5 S5 (final run): L4 gradient-boosting model on L1-L3 plausibility features. VeReMi TEST scored once; Tampa applied without retraining.

Run from codes_v3/ AFTER tools/WP5_S5_dev.py:  python -I -u -W ignore tools/WP5_S5_l4.py --cache <dir>
Protocol (notes/WP5_v2x.md, 'S5 ... acceptance rule', written before any result): model trained on VeReMi TRAIN without attack types 6, 12, 17;
hyperparameters chosen on validation in the dev stage (results/WP5/s5_dev.json); threshold = 1% of genuine validation messages, tie-safe; test once.
Variants (same hyperparameters, refit on train): A1 no time/track features, A2 residuals only, no_memory (no CUSUM / window features),
shuffled-label control. Baseline = deployable L1+L2+L3 (kf_cusum_lo excluded), calibrated as in S4 on the same validation frame.
Tampa: VeReMi-trained model applied unchanged to injected Tampa messages (3 test vehicles; illustration). Tampa tracker = S4 noise fit on Tampa TRAIN.
Outputs (results/WP5/): s5_summary.json, s5_tables.md, s5_l4_model.json (xgboost), logs.
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

import common.evaluate as ev
from common.calibration import ECDFCalibrator
from common.config import SEED
from common.metrics import auc, budget_threshold
from v2x import adapters, l1, l2, l3, l4, splitting

import WP5_S2_l1 as s2
import WP5_S3_l2 as s3
import WP5_S5_dev as dev

OUT, BUDGET, HELDOUT, SUPP = s2.OUT, s2.BUDGET, s2.HELDOUT, s2.SUPP
log, aname, fmt = s2.log, s2.aname, s2.fmt
s3.SMOKE = False
SEEN = [aname(c) for c in range(1, 20) if c not in HELDOUT]
UNSEEN = [aname(c) for c in HELDOUT]
CLASSES = [aname(c) for c in range(1, 20)]
L1_N = ["v2x.beacon_rate", "v2x.field_ranges"]
L2_N = ["v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate", "v2x.accel_consistency", "v2x.overlap"]
L3_N = ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]
L4_N = "v2x.l4_gb"
RAWCOL = {"v2x.beacon_rate": "rate", "v2x.field_ranges": "field_raw", "v2x.pos_speed": "pos_speed", "v2x.pos_heading": "pos_heading",
          "v2x.speed_change": "speed_change", "v2x.implied_speed": "implied_speed", "v2x.heading_rate": "heading_rate",
          "v2x.accel_consistency": "accel_consistency", "v2x.overlap": "overlap", "v2x.kf_nis": "nis", "v2x.kf_cusum_hi": "cusum_hi",
          "v2x.track_birth": "birth_density"}


def cal_thr(raw_val, genuine_mask):
    c = ECDFCalibrator().fit(raw_val[genuine_mask])
    return c, budget_threshold(c.transform(raw_val[genuine_mask]), BUDGET)


def mean_det(pc_op, classes):
    v = [pc_op["by_class"][c]["msg_detection"] for c in classes if c in pc_op["by_class"]]
    return float(np.mean(v)) if v else None


def summarize_op(pc, classes_all):
    return {"false_alarm_messages": pc["false_alarm_messages"], "false_alarm_genuine_senders": pc["false_alarm_genuine_senders"],
            "mean_detection_19": mean_det(pc, classes_all), "mean_detection_seen16": mean_det(pc, SEEN),
            "mean_detection_unseen_6_17": mean_det(pc, [UNSEEN[0], UNSEEN[2]]), "detection_unseen_12": mean_det(pc, [UNSEEN[1]]),
            "by_class": {c: {k: v for k, v in s.items() if not k.startswith("attackers_")} for c, s in pc["by_class"].items()}}


def boot_all(pc, tmeta, al, rng):
    out = {}
    for c, s in pc["by_class"].items():
        out[c] = s2.boot_ci(s["attackers_hits"], s["attackers_n"], rng)
    return out


# --------------------------------------------------------------------------------------------------------
def run_veremi(cfg, cache, summary, tables):
    cols = json.load(open(cache / "columns.json"))
    Ftr = pd.DataFrame(np.load(cache / "train_feat.npy"), columns=cols)
    Fva = pd.DataFrame(np.load(cache / "val_feat.npy"), columns=cols)
    mtr, mva = pd.read_pickle(cache / "train_meta.pkl"), pd.read_pickle(cache / "val_meta.pkl")
    assert not set(mtr["label"]) & set(HELDOUT) and not set(mva["label"]) & set(HELDOUT)
    ytr, yva = (mtr["label"].to_numpy() > 0).astype(int), (mva["label"].to_numpy() > 0).astype(int)
    log("VeReMi: loading test")
    v, sp = dev.load_frames()
    test = splitting.rows_of(v, sp["test"])
    log("test rows", len(test))
    tracker = dev.tracker_from_s4()
    raw_t = l4.message_scores(test, tracker)
    Fte = l4.feature_table(test, tracker, raw_t)
    mte = dev.meta_of(test)
    yte = (mte["label"].to_numpy() > 0)
    log("test features done")
    params, n_est = cfg["chosen_params"], cfg["chosen_n_estimators"]
    fsets = l4.feature_sets()

    def fit_pred(name, feats, shuffle=False):
        y = ytr.copy()
        if shuffle:
            y = np.random.RandomState(SEED).permutation(y)
        m = l4.GBModel(feats, params, n_estimators=n_est).fit(Ftr, y)
        pv, pt = m.predict(Fva), m.predict(Fte)
        log("fitted", name, "val auc", round(auc(yva, pv), 4), "test auc", round(auc(yte.astype(int), pt), 4))
        return m, pv, pt

    models = {}
    models["full"] = fit_pred("full", fsets["full"])
    models["A1_no_time_track"] = fit_pred("A1", fsets["A1_no_time_track"])
    models["A2_residuals_only"] = fit_pred("A2", fsets["A2_residuals_only"])
    models["no_memory"] = fit_pred("no_memory", fsets["no_memory"])
    models["shuffled_labels"] = fit_pred("shuffled", fsets["full"], shuffle=True)
    models["full"][0].model.save_model(str(OUT / "s5_l4_model.json"))

    gv, gt = ~yva.astype(bool), ~yte
    # --- calibrated layers on the validation frame (same rule as S4) ---
    cal_v, cal_t, al_t, al_v, thr = {}, {}, {}, {}, {}
    for n in L1_N + L2_N + L3_N:
        rv, rt = Fva[RAWCOL[n]].to_numpy(float), Fte[RAWCOL[n]].to_numpy(float)
        c, th = cal_thr(rv, gv)
        cal_v[n], cal_t[n], thr[n] = c.transform(rv), c.transform(rt), th
    pv, pt = models["full"][1], models["full"][2]
    c4, th4 = cal_thr(pv.astype(float), gv)
    cal_v[L4_N], cal_t[L4_N], thr[L4_N] = c4.transform(pv.astype(float)), c4.transform(pt.astype(float)), th4
    thr_p = budget_threshold(pv[gv].astype(float), BUDGET)           # raw probability threshold of the full model
    names = list(cal_v)
    for n in names:
        al_v[n], al_t[n] = cal_v[n] >= thr[n], cal_t[n] >= thr[n]
    log("val genuine FA at ops:", {n: round(float(al_v[n][gv].mean()), 4) for n in names})
    vmeta = pd.DataFrame({"sender": mva["sender"].to_numpy(), "t": mva["t"].to_numpy(), "y": ~gv,
                          "atype": np.where(~gv, mva["label"].map(aname), "normal")})
    tmeta = pd.DataFrame({"sender": mte["sender"].to_numpy(), "t": mte["t"].to_numpy(), "y": yte,
                          "atype": np.where(yte, mte["label"].map(aname), "normal")})
    ES = lambda cal, al, m, grp, ns: ev.EvalSet({n: s3.lite_list(cal[n], al[n]) for n in ns}, m["y"].to_numpy().astype(int),
                                                m["atype"].to_numpy(), grp, m["t"].to_numpy())
    val_es = ES(cal_v, al_v, vmeta, mva["group"].to_numpy(), names)
    test_es = ES(cal_t, al_t, tmeta, mte["group"].to_numpy(), names)
    yv_b = vmeta["y"].to_numpy(bool)
    groups, comb_alarm = {}, {}
    for gname, gn in (("L1+L2", L1_N + L2_N), ("L1+L2+L3", L1_N + L2_N + L3_N), ("L1+L2+L4", L1_N + L2_N + [L4_N]),
                      ("L1+L2+L3+L4", L1_N + L2_N + L3_N + [L4_N])):
        comb, sv, st = ev._combined(val_es, test_es, gn, "auto", BUDGET)
        th = budget_threshold(sv[~yv_b], BUDGET)
        r = ev._summarize(sv, st, val_es, test_es, BUDGET)
        r["method"] = comb.method
        groups[gname] = r
        comb_alarm["combined_" + gname] = st >= th
        log("group", gname, comb.method, "AUC", round(r["auc"], 4), "det", round(r["detection"], 4), "FA", round(r["false_alarm_rate"], 4))
    r4 = ev._summarize(cal_v[L4_N], cal_t[L4_N], val_es, test_es, BUDGET)
    r4["method"] = "single layer"
    groups["L4"] = r4

    def union(ns):
        sv_ = np.max([cal_v[n] for n in ns], axis=0)
        st_ = np.max([cal_t[n] for n in ns], axis=0)
        th = budget_threshold(sv_[gv], BUDGET)
        return st_ >= th, float(th), float((sv_[gv] >= th).mean())

    l1_ops = al_t["v2x.beacon_rate"] | (Fte["field_raw"].to_numpy() >= 1.0)
    a_u23, th_u23, fa_u23 = union(L2_N + L3_N)
    a_u234, th_u234, fa_u234 = union(L2_N + L3_N + [L4_N])
    ops = {n: al_t[n] for n in names}
    ops.update({"L1_ops": l1_ops, "L2L3_union": a_u23, "L1L2L3_union": l1_ops | a_u23, "L2L3L4_union": a_u234, "L1L2L3L4_union": l1_ops | a_u234,
                "L4": al_t[L4_N]})
    ops.update(comb_alarm)
    # variants: own threshold from genuine validation, 1% tie-safe
    variant_info = {}
    for vn, (m, pv_, pt_) in models.items():
        th = budget_threshold(pv_[gv].astype(float), BUDGET)
        ops["L4_" + vn] = pt_.astype(float) >= th
        variant_info[vn] = {"features": m.features, "n_features": len(m.features), "val_threshold_p": float(th), "val_FA": float((pv_[gv] >= th).mean()),
                            "val_auc": auc(yva, pv_), "test_auc": auc(yte.astype(int), pt_), "test_FA": float(ops["L4_" + vn][gt].mean()),
                            "test_detection_all": float(ops["L4_" + vn][yte].mean())}
    pc = s2.per_class(tmeta, ops, CLASSES)
    rng = np.random.RandomState(SEED)
    cis = {k: boot_all(pc[k], tmeta, ops[k], rng) for k in ("L4", "L1L2L3_union", "combined_L1+L2+L3", "combined_L1+L2+L3+L4", "L4_no_memory", "L4_A2_residuals_only")}
    sk = {k: s3.sender_k(tmeta, ops[k], CLASSES, 3) for k in ("L1L2L3_union", "L4", "combined_L1+L2+L3", "combined_L1+L2+L3+L4")}
    sums = {k: summarize_op(d, CLASSES) for k, d in pc.items()}
    # class 12: placeholder rows vs rows after the jump
    c12 = {}
    is12 = (tmeta["atype"] == aname(12)).to_numpy()
    ph = mte["x0"].to_numpy()
    for k in ("L4", "L4_no_memory", "L4_A2_residuals_only", "L1L2L3_union", "combined_L1+L2+L3", "combined_L1+L2+L3+L4"):
        c12[k] = {"all": float(ops[k][is12].mean()), "placeholder_rows": float(ops[k][is12 & ph].mean()) if (is12 & ph).any() else None,
                  "after_jump_rows": float(ops[k][is12 & ~ph].mean()) if (is12 & ~ph).any() else None}
    c12["n_rows"] = {"all": int(is12.sum()), "placeholder": int((is12 & ph).sum()), "after_jump": int((is12 & ~ph).sum())}
    imp = models["full"][0].importance()
    # single-feature test AUC of the five most important features (information)
    top = list(imp)[:8]
    single_auc = {f: max(auc(yte.astype(int), Fte[f].to_numpy(float)), 1 - auc(yte.astype(int), Fte[f].to_numpy(float))) for f in top}
    summ = {"config": {k: cfg[k] for k in ("chosen", "chosen_params", "chosen_n_estimators", "criterion")},
            "n_train": int(len(ytr)), "n_val": int(len(yva)), "n_test": int(len(yte)), "n_test_genuine": int(gt.sum()), "n_test_attack": int(yte.sum()),
            "val_genuine_FA_ops": {n: float(al_v[n][gv].mean()) for n in names},
            "thresholds": {"L4_calibrated_score": th4, "L4_probability": float(thr_p), "L2L3_union": th_u23, "L2L3L4_union": th_u234},
            "union_val_FA": {"L2L3": fa_u23, "L2L3L4": fa_u234},
            "groups": {k: {kk: vv for kk, vv in r.items()} for k, r in groups.items()},
            "variants": variant_info, "importance_gain": imp, "single_feature_test_auc_top8": single_auc,
            "per_operating_point": sums, "ci95_attacker_bootstrap": cis, "sender_ge3_alarms": sk, "class12_diagnostic": c12,
            "stat_unseen": {"classes": UNSEEN},
            "best_iteration_dev": cfg["chosen_n_estimators"]}
    summary["veremi"] = summ
    # --- tables ---
    cols = ["L1L2L3_union", "L4", "combined_L1+L2+L3", "combined_L1+L2+L3+L4", "L4_A1_no_time_track", "L4_A2_residuals_only", "L4_no_memory", "L4_shuffled_labels"]
    t = s2.md_table("VeReMi test: message-level detection per class at the 1% genuine-validation budget (L1L2L3_union = deployable baseline, no kf_cusum_lo)",
                    pc, cols, CLASSES, lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")),
                    "* = attack type NEVER used in training, hyperparameter choice, threshold or combiner (unseen). L4_* variants: same hyperparameters, refit on train.")
    t += "| mean seen (16) | " + " | ".join(fmt(sums[c]["mean_detection_seen16"]) for c in cols) + " |\n"
    t += "| mean unseen 6 and 17 | " + " | ".join(fmt(sums[c]["mean_detection_unseen_6_17"]) for c in cols) + " |\n"
    t += "| mean over 19 | " + " | ".join(fmt(sums[c]["mean_detection_19"]) for c in cols) + " |\n"
    t += "| FA genuine messages | " + " | ".join(fmt(sums[c]["false_alarm_messages"]) for c in cols) + " |\n"
    t += "| FA genuine senders (>= 1 alarm) | " + " | ".join(fmt(sums[c]["false_alarm_genuine_senders"]) for c in cols) + " |\n"
    tables.append("### VeReMi (D12) test\n\n" + t)
    ucols = ["L1L2L3_union", "L2L3L4_union", "L1L2L3L4_union", "combined_L1+L2", "combined_L1+L2+L4", "combined_L1+L2+L3", "combined_L1+L2+L3+L4"]
    t = s2.md_table("VeReMi test: unions and harness combinations (L2L3L4_union = max of calibrated scores at ONE 1% budget)", pc, ucols, CLASSES,
                    lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")), "")
    t += "| mean over 19 | " + " | ".join(fmt(sums[c]["mean_detection_19"]) for c in ucols) + " |\n"
    t += "| FA genuine messages | " + " | ".join(fmt(sums[c]["false_alarm_messages"]) for c in ucols) + " |\n"
    tables.append(t)
    lines = ["| class | L4 detection [95% CI, attacker bootstrap] | deployable L1L2L3_union [95% CI] | n attackers | L4 sender >= 3 alarms | L4 median delay (s) |", "|---|---|---|---|---|---|"]
    for c in CLASSES:
        a, b = pc["L4"]["by_class"].get(c), pc["L1L2L3_union"]["by_class"].get(c)
        if a is None:
            continue
        star = " *" if int(c[:2]) in HELDOUT else ""
        ci4, ciu = cis["L4"][c], cis["L1L2L3_union"][c]
        lines.append(f"| {c}{star} | {fmt(a['msg_detection'])} [{fmt(ci4[0])}, {fmt(ci4[1])}] | {fmt(b['msg_detection'])} [{fmt(ciu[0])}, {fmt(ciu[1])}] | {a['n_attackers']} | "
                     f"{fmt(sk['L4']['by_class'].get(c))} | {fmt(a['median_delay_s'], False)} |")
    tables.append("**VeReMi test: L4 vs deployable baseline with attacker-bootstrap CIs**\n\n" + "\n".join(lines) + "\n")
    lines = ["| group | method | AUC | detection (all attacks) | false alarms | median delay |", "|---|---|---|---|---|---|"]
    for k, r in groups.items():
        lines.append(f"| {k} | {r['method']} | {r['auc']:.3f} | {fmt(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% | {r['delay'].get('median_delay_s') if isinstance(r['delay'], dict) else '-'} |")
    tables.append("**VeReMi test, harness group ablation (all attacks pooled; combiner chosen on validation)**\n\n" + "\n".join(lines) + "\n")
    lines = ["| variant | n features | val AUC | test AUC | val FA | test FA (genuine msgs) | test detection (all attacks pooled) |", "|---|---|---|---|---|---|---|"]
    for k, r in variant_info.items():
        lines.append(f"| {k} | {r['n_features']} | {r['val_auc']:.3f} | {r['test_auc']:.3f} | {fmt(r['val_FA'])} | {fmt(r['test_FA'])} | {fmt(r['test_detection_all'])} |")
    tables.append("**Leakage checks: feature-set ablations and shuffled-label control**\n\n" + "\n".join(lines) + "\n")
    lines = ["| feature | share of total gain | single-feature test AUC (information) |", "|---|---|---|"]
    for f, s in list(imp.items())[:15]:
        lines.append(f"| {f} | {100 * s:.1f}% | {single_auc[f]:.3f} |" if f in single_auc else f"| {f} | {100 * s:.1f}% | - |")
    tables.append("**Gain importance of the final model (top 15)**\n\n" + "\n".join(lines) + "\n")
    lines = ["| operating point | all class-12 rows | zero-placeholder rows (x = y = 0) | rows after the jump |", "|---|---|---|---|"]
    for k in ("L1L2L3_union", "L4", "L4_no_memory", "L4_A2_residuals_only", "combined_L1+L2+L3", "combined_L1+L2+L3+L4"):
        r = c12[k]
        lines.append(f"| {k} | {fmt(r['all'])} | {fmt(r['placeholder_rows'])} | {fmt(r['after_jump_rows'])} |")
    lines.append(f"| rows | {c12['n_rows']['all']} | {c12['n_rows']['placeholder']} | {c12['n_rows']['after_jump']} |")
    tables.append("**Class 12 (DelayedMessages, held out): the zero-placeholder artefact**\n\n" + "\n".join(lines) + "\n")
    tables.append(s3.fa_table("VeReMi test", {k: pc[k] for k in ("L1L2L3_union", "L4", "combined_L1+L2+L3", "combined_L1+L2+L3+L4", "L4_A1_no_time_track", "L4_A2_residuals_only",
                                                                    "L4_no_memory", "L4_shuffled_labels")}))
    return {"models": models, "thr_p": thr_p, "cols": cols}


# --------------------------------------------------------------------------------------------------------
def run_tampa(cfg, vres, summary, tables):
    log("Tampa: loading")
    tp = adapters.load_tampa(with_age=True)
    sp = json.loads((OUT / "splits_tampa_v2.json").read_text())
    p = json.loads((OUT / "s4_params_tampa.json").read_text())
    tracker = l3.Tracker(l3.KalmanParams(**p))
    val_df = splitting.rows_of(tp, sp["val"])
    val_df = val_df.assign(sample_id=val_df["msg_id"])
    ones = np.ones(len(val_df), bool)
    l1_layers = [l for l in l1.make_layers() if l.name in s3.L1_NAMES]
    for l in l1_layers:
        l.calibrate(val_df, budget=BUDGET)
    l2_layers = [l for l in l2.make_layers(None) if l.name != "v2x.map_road"]
    for l in l2_layers:
        l.calibrate_masked(val_df, ones, BUDGET)
    l3_layers = [l for l in l3.make_layers(tracker) if l.name != "v2x.kf_cusum_lo"]
    for l in l3_layers:
        l.calibrate_masked(val_df, ones, BUDGET)
    layers = l1_layers + l2_layers + l3_layers
    base_names = [l.name for l in layers]
    n_l1 = [n for n in base_names if n in s3.L1_NAMES]
    n_l2 = [n for n in base_names if n in s3.L2_NAMES]
    n_l3 = [n for n in base_names if n in l3_names()]
    vf, vk, vmeta = s3.tampa_frames(tp, sp["val"], True)
    tf, tk, tmeta = s3.tampa_frames(tp, sp["test"], False)
    raw_v, phys_v = s3.raw_over_frames(vf, vk, layers)
    raw_t, phys_t = s3.raw_over_frames(tf, tk, layers)
    Fv = pd.concat([l4.feature_table(f, tracker).iloc[np.flatnonzero(k)] for f, k in zip(vf, vk)], ignore_index=True)
    Ft = pd.concat([l4.feature_table(f, tracker).iloc[np.flatnonzero(k)] for f, k in zip(tf, tk)], ignore_index=True)
    assert len(Fv) == len(vmeta) and len(Ft) == len(tmeta)
    yv, yt = vmeta["y"].to_numpy(bool), tmeta["y"].to_numpy(bool)
    log("Tampa val genuine", int((~yv).sum()), "test genuine", int((~yt).sum()), "test attack", int(yt.sum()))
    cal_v, al_v = s3.cal_alarm(layers, raw_v)
    cal_t, al_t = s3.cal_alarm(layers, raw_t)
    ops, info = {}, {}
    for n in base_names:
        ops[n] = al_t[n]
    l1_ops = np.any([phys_t["v2x.field_ranges"] if n == "v2x.field_ranges" else al_t[n] for n in n_l1], axis=0)

    def union(ns, extra_v=None, extra_t=None):
        sv_ = np.max([cal_v[n] for n in ns] + ([extra_v] if extra_v is not None else []), axis=0)
        st_ = np.max([cal_t[n] for n in ns] + ([extra_t] if extra_t is not None else []), axis=0)
        th = budget_threshold(sv_[~yv], BUDGET)
        return st_ >= th, float((sv_[~yv] >= th).mean())

    a_u23, fa_u23v = union(n_l2 + n_l3)
    ops["L1L2L3_union"] = l1_ops | a_u23
    models = vres["models"]
    for vn in ("full", "A1_no_time_track", "A2_residuals_only", "no_memory", "shuffled_labels"):
        m = models[vn][0]
        pv, pt = m.predict(Fv), m.predict(Ft)
        th_v = vres["thr_by_variant"][vn]
        th_t = budget_threshold(pv[~yv].astype(float), BUDGET)
        ops[f"L4_{vn}@veremi_thr"] = pt.astype(float) >= th_v
        ops[f"L4_{vn}@tampa_val_thr"] = pt.astype(float) >= th_t
        info[vn] = {"veremi_threshold_p": float(th_v), "tampa_val_threshold_p": float(th_t), "tampa_val_FA_at_veremi_thr": float((pv[~yv] >= th_v).mean()),
                    "tampa_test_auc": auc(yt.astype(int), pt), "median_p_genuine_tampa_test": float(np.median(pt[~yt])),
                    "median_p_attack_tampa_test": float(np.median(pt[yt]))}
        if vn == "full":
            c4 = ECDFCalibrator().fit(pv[~yv].astype(float))
            cal_v[L4_N], cal_t[L4_N] = c4.transform(pv.astype(float)), c4.transform(pt.astype(float))
            al_v[L4_N] = cal_v[L4_N] >= budget_threshold(cal_v[L4_N][~yv], BUDGET)
            al_t[L4_N] = cal_t[L4_N] >= budget_threshold(cal_v[L4_N][~yv], BUDGET)
            a_u234, _ = union(n_l2 + n_l3, cal_v[L4_N], cal_t[L4_N])
            ops["L1L2L3L4_union@tampa_val_thr"] = l1_ops | a_u234
    names = base_names + [L4_N]
    ES = lambda cal, al, m, ns: ev.EvalSet({n: s3.lite_list(cal[n], al[n]) for n in ns}, m["y"].to_numpy().astype(int), m["atype"].to_numpy(),
                                           m["sender"].to_numpy(), m["t"].to_numpy())
    val_es, test_es = ES(cal_v, al_v, vmeta, names), ES(cal_t, al_t, tmeta, names)
    groups = {}
    for gname, gn in (("L1+L2+L3", base_names), ("L1+L2+L3+L4", names)):
        comb, sv, st = ev._combined(val_es, test_es, gn, "auto", BUDGET)
        th = budget_threshold(sv[~yv], BUDGET)
        r = ev._summarize(sv, st, val_es, test_es, BUDGET)
        r["method"] = comb.method
        groups[gname] = r
        ops["combined_" + gname] = st >= th
    classes = CLASSES + [SUPP]
    pc = s2.per_class(tmeta, ops, classes)
    rng = np.random.RandomState(SEED)
    for nm, d in pc.items():
        for c, s in d["by_class"].items():
            s["ci95_attacker_bootstrap"] = s2.boot_ci(s["attackers_hits"], s["attackers_n"], rng)
        g = tmeta[~yt].assign(a=ops[nm][~yt]).groupby("sender")["a"].agg(["sum", "size"])
        d["false_alarm_ci95_vehicle_bootstrap"] = s2.boot_ci(g["sum"].to_numpy(), g["size"].to_numpy(), rng)
    sums = {k: summarize_op(d, CLASSES) for k, d in pc.items()}
    for k, d in pc.items():
        sums[k]["false_alarm_ci95_vehicle_bootstrap"] = d["false_alarm_ci95_vehicle_bootstrap"]
        sums[k]["detection_StaleReplay"] = d["by_class"].get(SUPP, {}).get("msg_detection")
    summary["tampa"] = {"n_test_genuine": int((~yt).sum()), "n_test_attack": int(yt.sum()), "n_val_genuine": int((~yv).sum()),
                        "L4_models": info, "groups": groups, "per_operating_point": sums,
                        "feature_scale_note": "Tampa beacons are 10 Hz (VeReMi 1 Hz): rate, dt_prev and window features are out of the training range for the full model"}
    cols = ["L1L2L3_union", "combined_L1+L2+L3", "combined_L1+L2+L3+L4", "L4_full@veremi_thr", "L4_full@tampa_val_thr", "L4_A1_no_time_track@tampa_val_thr",
            "L4_A2_residuals_only@veremi_thr", "L4_A2_residuals_only@tampa_val_thr", "L4_shuffled_labels@tampa_val_thr"]
    t = s2.md_table("Tampa test (illustration: 3 vehicles, 2 attackers per type, no statistics): message-level detection, VeReMi-trained L4 applied unchanged",
                    pc, cols, classes, lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")),
                    "@veremi_thr = threshold of VeReMi validation (no Tampa data used); @tampa_val_thr = 1% of genuine Tampa validation messages. * = type unseen by L4 (and by every other layer calibration).")
    t += "| mean over 19 | " + " | ".join(fmt(sums[c]["mean_detection_19"]) for c in cols) + " |\n"
    t += "| FA genuine messages | " + " | ".join(fmt(sums[c]["false_alarm_messages"]) for c in cols) + " |\n"
    t += "| FA 95% CI (vehicle bootstrap) | " + " | ".join("[" + ", ".join(fmt(x) for x in sums[c]["false_alarm_ci95_vehicle_bootstrap"]) + "]" for c in cols) + " |\n"
    tables.append("### Tampa (injected on real BSMs) test: ILLUSTRATION\n\n" + t)
    lines = ["| model | VeReMi threshold (p) | Tampa val threshold (p) | Tampa val FA at VeReMi threshold | Tampa test AUC | median p genuine | median p attack |", "|---|---|---|---|---|---|---|"]
    for k, r in info.items():
        lines.append(f"| {k} | {r['veremi_threshold_p']:.3f} | {r['tampa_val_threshold_p']:.3f} | {fmt(r['tampa_val_FA_at_veremi_thr'])} | {r['tampa_test_auc']:.3f} | {r['median_p_genuine_tampa_test']:.3f} | {r['median_p_attack_tampa_test']:.3f} |")
    tables.append("**Tampa: transfer of the VeReMi-trained models**\n\n" + "\n".join(lines) + "\n")
    lines = ["| group | method | AUC | detection (all attacks) | false alarms |", "|---|---|---|---|---|"]
    for k, r in groups.items():
        lines.append(f"| {k} | {r['method']} | {r['auc']:.3f} | {fmt(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% |")
    tables.append("**Tampa test, harness group ablation (combiner fitted on Tampa validation, as in S4)**\n\n" + "\n".join(lines) + "\n")


def l3_names():
    return ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]


def main():
    cache = Path(sys.argv[sys.argv.index("--cache") + 1])
    cfg = json.loads((OUT / "s5_dev.json").read_text())
    summary = {"budget": BUDGET, "heldout_attack_types": HELDOUT, "seen_classes": SEEN, "unseen_classes": UNSEEN}
    tables = []
    t0 = time.time()
    vres = run_veremi(cfg, cache, summary, tables)
    vres["thr_by_variant"] = {k: summary["veremi"]["variants"][k]["val_threshold_p"] for k in summary["veremi"]["variants"]}
    s2.jdump("s5_summary.json", summary)               # VeReMi numbers are saved before the Tampa step
    run_tampa(cfg, vres, summary, tables)
    summary["total_seconds"] = time.time() - t0
    s2.jdump("s5_summary.json", summary)
    (OUT / "s5_tables.md").write_text("\n".join(tables))
    log("done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
