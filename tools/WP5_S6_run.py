"""WP5 S6 (final run, closes M1-V2X): deployable V2X stack L1 + L2 + L3 + L4-scored, domain combiner, ablation, VeReMi test, Tampa illustration.

Run from codes_v3/ AFTER tools/WP5_S6_dev.py:  python -I -u -W ignore tools/WP5_S6_run.py --cache <dir> [--smoke]
--smoke uses the VALIDATION split as a stand-in test (plumbing check, never touches test). The real run scores the VeReMi test ONCE (a second
exposure of this split: S5 already used it); nothing is chosen after seeing it. Rule: notes/WP5_v2x.md, 'S6 ... acceptance rule'.
Stack: L1 beacon_rate + field_ranges; L2 seven checks (no map_road, yaw, freshness on VeReMi); L3 kf_nis, kf_cusum_hi, track_birth (no kf_cusum_lo);
L4-scored = xgboost on scored rows only (raw score 0 on first messages / gaps / exact repeats). Layers calibrated on genuine validation rows (1%, tie-safe);
domain combiner common/combiner.py method "auto" (noisy_or / logistic / max, chosen on group-split validation halves) for every ablation group.
Evaluation: v2x/stackeval.py (message level on all rows and on scored rows, sender level >= 3 alarms, delay per attacker, block-bootstrap CIs over test time blocks).
Shuffled-label control on scored rows. Tampa (illustration, 3 vehicles, no CIs): VeReMi-trained L4 frozen, Tampa tracker + Tampa layer calibrations, thresholds on Tampa genuine validation.
Outputs (results/WP5/): s6_veremi.json, s6_tampa.json, s6_tables_veremi.md, s6_tables_tampa.md, s6_l4_model.json, logs.
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

import common.combiner as cc
import common.evaluate as ev
from common.calibration import ECDFCalibrator
from common.config import SEED
from common.metrics import auc, budget_threshold
from v2x import adapters, l1, l2, l3, l4, splitting, stackeval

import WP5_S2_l1 as s2
import WP5_S3_l2 as s3
import WP5_S5_dev as dev5

s3.SMOKE = False
OUT, BUDGET, HELDOUT, SUPP = s2.OUT, s2.BUDGET, s2.HELDOUT, s2.SUPP
log, aname, fmt = s2.log, s2.aname, s2.fmt
SMOKE = "--smoke" in sys.argv
SUF = "_smoke" if SMOKE else ""
B_BOOT = 1000
CLASSES = [aname(c) for c in range(1, 20)]
SEEN = [aname(c) for c in range(1, 20) if c not in HELDOUT]
UNSEEN = [aname(6), aname(17)]
C12 = aname(12)
L1_N = ["v2x.beacon_rate", "v2x.field_ranges"]
L2_N = ["v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate", "v2x.accel_consistency", "v2x.overlap"]
L3_N = ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]
L4_N = "v2x.l4_scored"
RAWCOL = {"v2x.beacon_rate": "rate", "v2x.field_ranges": "field_raw", "v2x.pos_speed": "pos_speed", "v2x.pos_heading": "pos_heading",
          "v2x.speed_change": "speed_change", "v2x.implied_speed": "implied_speed", "v2x.heading_rate": "heading_rate",
          "v2x.accel_consistency": "accel_consistency", "v2x.overlap": "overlap", "v2x.kf_nis": "nis", "v2x.kf_cusum_hi": "cusum_hi",
          "v2x.track_birth": "birth_density"}
ALL_N = L1_N + L2_N + L3_N + [L4_N]
GROUPS = {"L1": L1_N, "L2": L2_N, "L3": L3_N, "L4-scored": [L4_N], "L1+L2+L3+L4": ALL_N,
          "all but L1": L2_N + L3_N + [L4_N], "all but L2": L1_N + L3_N + [L4_N], "all but L3": L1_N + L2_N + [L4_N], "all but L4 (= L1+L2+L3)": L1_N + L2_N + L3_N}
FULL, BASE = "L1+L2+L3+L4", "all but L4 (= L1+L2+L3)"
KIND_NAMES = {0: "scored", 1: "first / gap", 2: "exact repeat"}


# --------------------------------------------------------------------------------------------------------------
def pc(x, ci=None, d=1):
    if x is None:
        return "-"
    s = f"{100 * x:.{d}f}%"
    if ci is not None and ci[0] is not None:
        s += f" [{100 * ci[0]:.{d}f}, {100 * ci[1]:.{d}f}]"
    return s


def cell(d, ci=True):
    if d is None:
        return "-"
    return pc(d["p"], d.get("ci") if ci else None)


def cal_thr(raw_val, genuine_mask):
    c = ECDFCalibrator().fit(raw_val[genuine_mask])
    return c, budget_threshold(c.transform(raw_val[genuine_mask]), BUDGET)


def l4_raw(gb, F, kinds):
    return np.where(kinds == 0, gb.predict(F), 0.0)


def fit_scored(feats, params, n_est, F, y, kinds, shuffle=False):
    s = kinds == 0
    yy = np.asarray(y)[s].astype(int)
    if shuffle:
        yy = np.random.RandomState(SEED).permutation(yy)
    return l4.GBModel(feats, params, n_estimators=n_est).fit(F[s], yy)


def eval_pack(tmeta, alarm, kinds, B):
    return stackeval.evaluate_alarms(tmeta, alarm, CLASSES, kinds=kinds, seen=SEEN, unseen=UNSEEN, k=3, B=B)


def kval_pack(tmeta, alarm, kte, sv, th, gv, val_sender):
    """Sender rule chosen on validation: smallest k with <= 1% of genuine validation senders having >= k alarms of this configuration."""
    cnt = pd.Series((sv[gv] >= th).astype(int)).groupby(val_sender[gv]).sum().to_numpy()
    k = 1
    while (cnt >= k).mean() > 0.01 and k < 10000:
        k += 1
    r = stackeval.evaluate_alarms(tmeta, alarm, CLASSES, kinds=kte, seen=SEEN, unseen=UNSEEN, k=k, B=300)
    return {"k": k, "val_genuine_sender_FA": float((cnt >= k).mean()), "sender": r["sender"], "fa_sender": r["fa_sender"], "mean_sender": r["mean_sender"]}


def strip_ci(o):
    if isinstance(o, dict):
        return {k: strip_ci(v) for k, v in o.items() if k != "ci"}
    return o


# --------------------------------------------------------------------------------------------------------------
def run_veremi(cfg, cache, tables):
    tag = "count" if cfg["chosen_time_window_s"] is None else "time"
    cols = json.load(open(cache / "columns.json"))
    tabs = {}
    for tg in sorted({tag, "count"}):
        tabs[tg] = (pd.DataFrame(np.load(cache / f"train_feat_{tg}.npy"), columns=cols), pd.DataFrame(np.load(cache / f"val_feat_{tg}.npy"), columns=cols))
    Ftr, Fva = tabs[tag]
    mtr, mva = pd.read_pickle(cache / "train_meta.pkl"), pd.read_pickle(cache / "val_meta.pkl")
    ktr, kva = np.load(cache / "train_kinds.npy"), np.load(cache / "val_kinds.npy")
    assert not set(mtr["label"]) & set(HELDOUT) and not set(mva["label"]) & set(HELDOUT)
    ytr, yva = (mtr["label"].to_numpy() > 0).astype(int), (mva["label"].to_numpy() > 0).astype(int)
    log("VeReMi: loading", "VALIDATION as stand-in test (smoke)" if SMOKE else "TEST (scored once)")
    v, sp = dev5.load_frames()
    test = splitting.rows_of(v, sp["val" if SMOKE else "test"])
    tracker = dev5.tracker_from_s4()
    raw_t = l4.message_scores(test, tracker)
    Fte_by = {tg: l4.feature_table(test, tracker, raw_t, time_window_s=(None if tg == "count" else l4.WINDOW_S)) for tg in tabs}
    Fte = Fte_by[tag]
    kte = l4.row_kinds(test)
    mte = dev5.meta_of(test)
    yte = mte["label"].to_numpy() > 0
    log("test rows", len(test), "attack", int(yte.sum()))
    feats, params, n_est = cfg["chosen_features"], cfg["chosen_params"], cfg["chosen_n_estimators"]
    gb = fit_scored(feats, params, n_est, Ftr, ytr, ktr)
    gb.model.save_model(str(OUT / f"s6_l4_model{SUF}.json"))
    sh = fit_scored(feats, params, n_est, Ftr, ytr, ktr, shuffle=True)
    p_v, p_t = l4_raw(gb, Fva, kva), l4_raw(gb, Fte, kte)
    ps_v, ps_t = l4_raw(sh, Fva, kva), l4_raw(sh, Fte, kte)
    gv = yva == 0
    log("fitted; val scored AUC", round(auc(yva[kva == 0], p_v[kva == 0]), 4), "test scored AUC", round(auc(yte[kte == 0].astype(int), p_t[kte == 0]), 4))
    # ---- calibrated layers ----
    cal_v, cal_t, thr = {}, {}, {}
    for n in L1_N + L2_N + L3_N:
        rv, rt = Fva[RAWCOL[n]].to_numpy(float), Fte[RAWCOL[n]].to_numpy(float)
        c, th = cal_thr(rv, gv)
        cal_v[n], cal_t[n], thr[n] = c.transform(rv), c.transform(rt), th
    c4, th4 = cal_thr(p_v.astype(float), gv)
    cal_v[L4_N], cal_t[L4_N], thr[L4_N] = c4.transform(p_v.astype(float)), c4.transform(p_t.astype(float)), th4
    al_t = {n: cal_t[n] >= thr[n] for n in cal_t}
    log("val genuine FA at layer ops:", {n: round(float((cal_v[n][gv] >= thr[n]).mean()), 4) for n in cal_v})
    tmeta = pd.DataFrame({"sender": mte["sender"].to_numpy(), "t": mte["t"].to_numpy(), "y": yte,
                          "atype": np.where(yte, mte["label"].map(aname), "normal"), "group": mte["group"].to_numpy()})
    vmeta = pd.DataFrame({"y": ~gv, "atype": np.where(~gv, mva["label"].map(aname), "normal")})
    val_es = ev.EvalSet({n: s3.lite_list(cal_v[n], cal_v[n] >= thr[n]) for n in cal_v}, yva, vmeta["atype"].to_numpy(), mva["group"].to_numpy(), mva["t"].to_numpy())
    test_es = ev.EvalSet({n: s3.lite_list(cal_t[n], al_t[n]) for n in cal_t}, yte.astype(int), tmeta["atype"].to_numpy(), mte["group"].to_numpy(), mte["t"].to_numpy())
    # ---- groups through the domain combiner ----
    res, alarms, sel = {}, {}, {}
    for gname, names in GROUPS.items():
        comb, sv, st = ev._combined(val_es, test_es, names, "auto", BUDGET)
        th = budget_threshold(sv[gv], BUDGET)
        al = st >= th
        alarms[gname] = al
        sel[gname] = {"method": comb.method, "val_half_detection": comb.selection, "n_layers": len(names)}
        if comb.method == "logistic":
            sel[gname]["logistic_coef"] = dict(zip(comb.layer_names, comb.model.coef_[0].round(3).tolist()))
        r = eval_pack(tmeta, al, kte, B_BOOT)
        r["auc_all_rows"] = auc(yte.astype(int), st)
        k0 = kte == 0
        r["auc_scored_rows"] = auc(yte[k0].astype(int), st[k0])
        r["val_FA_msg"] = float((sv[gv] >= th).mean())
        r["combiner"] = sel[gname]
        r["kval"] = kval_pack(tmeta, al, kte, sv, th, gv, mva["sender"].to_numpy())
        res[gname] = r
        log("group", gname, comb.method, "FA", pc(r["fa_msg"]["p"]), "scored mean seen", pc(r["mean_msg_scored"]["seen"]["p"]), "17 scored", pc(r["msg_scored"][aname(17)]["p"]))
    # ---- reference rows: unrestricted-feature scored-row L4 (price of rate invariance); never selected, not deployable for Tampa ----
    refs = {}
    for rset in ("S0_full27", "S1_noT_noRate"):
        run = [r for r in cfg["runs"] if r["set"] == rset and r["config"] == "d5_mcw1"][0]
        feats_r = l4.SCORED_SETS[rset]["features"]
        Ftr_c, Fva_c = tabs["count"]
        mr = fit_scored(feats_r, run["params"], run["n_estimators"], Ftr_c, ytr, ktr)
        pvr, ptr = l4_raw(mr, Fva_c, kva), l4_raw(mr, Fte_by["count"], kte)
        cr, thr_r = cal_thr(pvr.astype(float), gv)
        alr = cr.transform(ptr.astype(float)) >= thr_r
        rr = eval_pack(tmeta, alr, kte, 300)
        rr["auc_scored_rows"] = auc(yte[kte == 0].astype(int), ptr[kte == 0])
        refs["L4-scored " + rset + " (reference)"] = rr
        alarms["ref " + rset] = alr
        if rset == "S0_full27":
            cal_v_r, cal_t_r = dict(cal_v), dict(cal_t)
            cal_v_r[L4_N], cal_t_r[L4_N] = cr.transform(pvr.astype(float)), cr.transform(ptr.astype(float))
            val_r = ev.EvalSet({n: s3.lite_list(cal_v_r[n], cal_v_r[n] >= thr[n]) for n in cal_v_r}, yva, vmeta["atype"].to_numpy(), mva["group"].to_numpy(), mva["t"].to_numpy())
            test_r = ev.EvalSet({n: s3.lite_list(cal_t_r[n], cal_t_r[n] >= thr[n]) for n in cal_t_r}, yte.astype(int), tmeta["atype"].to_numpy(), mte["group"].to_numpy(), mte["t"].to_numpy())
            comb_r, sv_r, st_r = ev._combined(val_r, test_r, ALL_N, "auto", BUDGET)
            th_r = budget_threshold(sv_r[gv], BUDGET)
            rs = eval_pack(tmeta, st_r >= th_r, kte, 300)
            rs["combiner"] = {"method": comb_r.method}
            refs["L1+L2+L3+L4(S0 reference)"] = rs
            alarms["ref stack S0"] = st_r >= th_r
    # ---- single checks alone (own 1% operating point) ----
    checks = {}
    for n in cal_t:
        checks[n] = eval_pack(tmeta, al_t[n], kte, 200)
        alarms["check " + n] = al_t[n]
    # ---- row kinds ----
    kinds = {"share": {}, "stack_detection_by_kind": {}, "stack_FA_by_kind": {}, "L4_detection_by_kind": {}}
    full = alarms[FULL]
    lab = mte["label"].to_numpy()
    for c in range(1, 20):
        m = lab == c
        cn = aname(c)
        kinds["share"][cn] = {KIND_NAMES[k]: float((kte[m] == k).mean()) for k in KIND_NAMES}
        kinds["stack_detection_by_kind"][cn] = {KIND_NAMES[k]: (float(full[m & (kte == k)].mean()) if (m & (kte == k)).any() else None) for k in KIND_NAMES}
        kinds["L4_detection_by_kind"][cn] = {KIND_NAMES[k]: (float(al_t[L4_N][m & (kte == k)].mean()) if (m & (kte == k)).any() else None) for k in KIND_NAMES}
    kinds["genuine_share"] = {KIND_NAMES[k]: float((kte[~yte] == k).mean()) for k in KIND_NAMES}
    kinds["stack_FA_by_kind"] = {KIND_NAMES[k]: (float(full[~yte & (kte == k)].mean()) if (~yte & (kte == k)).any() else None) for k in KIND_NAMES}
    kinds["base_FA_by_kind"] = {KIND_NAMES[k]: (float(alarms[BASE][~yte & (kte == k)].mean()) if (~yte & (kte == k)).any() else None) for k in KIND_NAMES}
    kinds["L4_FA_by_kind"] = {KIND_NAMES[k]: (float(al_t[L4_N][~yte & (kte == k)].mean()) if (~yte & (kte == k)).any() else None) for k in KIND_NAMES}
    # ---- class 12 split (placeholder rows vs after the jump), diagnostic only ----
    ph = mte["x0"].to_numpy()
    is12 = lab == 12
    c12 = {g: {"all": float(alarms[g][is12].mean()), "placeholder_rows": float(alarms[g][is12 & ph].mean()) if (is12 & ph).any() else None,
               "after_jump_rows": float(alarms[g][is12 & ~ph].mean()) if (is12 & ~ph).any() else None} for g in (FULL, BASE, "L4-scored")}
    c12["n_rows"] = {"all": int(is12.sum()), "placeholder": int((is12 & ph).sum()), "after_jump": int((is12 & ~ph).sum())}
    # ---- shuffled-label control on scored rows ----
    k0t, k0v = kte == 0, kva == 0
    thr_s = budget_threshold(ps_v[k0v & gv].astype(float), BUDGET)
    al_s = ps_t >= thr_s
    thr_g = budget_threshold(p_v[k0v & gv].astype(float), BUDGET)
    al_g = p_t >= thr_g
    sc_att = k0t & yte
    per_s = {c: float(al_s[sc_att & (tmeta["atype"].to_numpy() == c)].mean()) for c in CLASSES if (sc_att & (tmeta["atype"].to_numpy() == c)).sum() >= 50}
    per_g = {c: float(al_g[sc_att & (tmeta["atype"].to_numpy() == c)].mean()) for c in CLASSES if (sc_att & (tmeta["atype"].to_numpy() == c)).sum() >= 50}
    fa_s = float(al_s[k0t & ~yte].mean())
    det_s = float(al_s[sc_att].mean())
    control = {"bound": "detection within 1 point of FA (pooled scored attack rows vs scored genuine test rows); bound NOT lowered",
               "shuffled": {"val_threshold_p": float(thr_s), "FA_scored_genuine_test": fa_s, "detection_pooled_scored_attack": det_s,
                            "detection_minus_FA_points": 100 * (det_s - fa_s), "mean_detection_seen_scored": float(np.mean([per_s[c] for c in per_s if c in SEEN])),
                            "mean_detection_unseen_scored": float(np.mean([per_s[c] for c in per_s if c in UNSEEN])) if any(c in per_s for c in UNSEEN) else None,
                            "auc_scored_rows": auc(yte[k0t].astype(int), ps_t[k0t]), "per_class": per_s},
               "real_model": {"FA_scored_genuine_test": float(al_g[k0t & ~yte].mean()), "detection_pooled_scored_attack": float(al_g[sc_att].mean()),
                              "auc_scored_rows": auc(yte[k0t].astype(int), p_t[k0t]), "per_class": per_g}}
    control["pass"] = bool(abs(det_s - fa_s) <= 0.01)
    # ---- importance ----
    imp = gb.importance()
    out = {"smoke": SMOKE, "config": {k: cfg[k] for k in ("chosen_set", "chosen_config", "chosen_params", "chosen_n_estimators", "chosen_features", "chosen_time_window_s", "criterion")},
           "n_test": int(len(test)), "n_test_genuine": int((~yte).sum()), "n_test_attack": int(yte.sum()), "n_test_genuine_scored": int((k0t & ~yte).sum()),
           "bootstrap": {"blocks": int(tmeta["group"].nunique()), "B": B_BOOT, "unit": "VeReMi test time blocks (1800 s), resampled with replacement"},
           "layer_thresholds_calibrated": thr, "groups": res, "references": refs, "checks": checks, "row_kinds": kinds, "class12": c12, "shuffled_control": control,
           "importance_gain": imp}
    # ---- tables ----
    tables.append(make_tables_veremi(out, cfg))
    return out, gb, tracker


def make_tables_veremi(o, cfg):
    G = o["groups"]
    L = []
    L.append(f"### VeReMi test ({'SMOKE: validation stand-in' if o['smoke'] else 'second exposure of the test split'}): ablation of the deployable stack\n")
    L.append(f"Test: {o['n_test']} messages ({o['n_test_genuine']} genuine, {o['n_test_attack']} attack) in {o['bootstrap']['blocks']} time blocks; CIs = block bootstrap over these blocks (B={o['bootstrap']['B']}). "
             "Scored rows = message with a moving predecessor in its track. * = never used in any fit, selection, calibration or combiner (unseen).\n")
    head = ["configuration", "combiner", "FA msgs", "FA scored msgs", "FA senders (>=3)", "scored: mean seen", "scored: 6*", "scored: 17*", "scored: mean 6,17", "sender>=3: mean seen", "k (val rule)", "FA senders (k val)", "sender k val: mean seen", "all rows: mean 19"]
    L += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for g, r in G.items():
        ms, mu = r["mean_msg_scored"], r["mean_msg_scored"].get("unseen")
        L.append("| " + " | ".join([g, r["combiner"]["method"], cell(r["fa_msg"]), cell(r["fa_scored_msg"]), cell(r["fa_sender"]), cell(ms["seen"]),
                                    cell(r["msg_scored"][aname(6)]), cell(r["msg_scored"][aname(17)]), cell(mu), cell(r["mean_sender"]["seen"]), str(r["kval"]["k"]), cell(r["kval"]["fa_sender"]), cell(r["kval"]["mean_sender"]["seen"]), cell(r["mean_msg_all"]["all"])]) + " |")
    L.append("")
    L.append("**Reference rows (not selected, not deployable on Tampa): scored-row L4 with the unrestricted feature sets, scored rows**\n")
    L += ["| model | FA scored msgs | scored: mean seen | scored: 6* | scored: 17* | sender>=3: mean seen | sender>=3: 17* | AUC scored rows |", "|---|---|---|---|---|---|---|---|"]
    for nm, rr in list(o["references"].items()) + [("L1+L2+L3+L4-scored (deployed, invariant S2)", G[FULL]), ("L4-scored (deployed, invariant S2)", G["L4-scored"])]:
        L.append("| " + " | ".join([nm, cell(rr["fa_scored_msg"]), cell(rr["mean_msg_scored"]["seen"]), cell(rr["msg_scored"][aname(6)]), cell(rr["msg_scored"][aname(17)]),
                                    cell(rr["mean_sender"]["seen"]), cell(rr["sender"][aname(17)]), f"{rr['auc_scored_rows']:.3f}" if "auc_scored_rows" in rr else "-"]) + " |")
    L.append("")
    for title, key, ci in (("Message level, SCORED rows only (detection of falsified messages that have a moving predecessor)", "msg_scored", True),
                           ("Message level, ALL rows (first messages and exact repeats included; only the physical layers can alarm on them)", "msg_all", True),
                           ("Sender level (attacker detected = >= 3 alarms among its falsified messages)", "sender", True)):
        L.append(f"**{title}**\n")
        names = list(G)
        L += ["| class | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
        for c in CLASSES:
            star = " *" if int(c[:2]) in HELDOUT else ""
            L.append(f"| {c}{star} | " + " | ".join(cell(G[g][key].get(c), ci=(g in (FULL, BASE))) if key != "msg_scored" or G[g][key][c]["n"] >= 50 else "-" for g in names) + " |")
        L.append("")
    L.append("**Full stack: per class (message level all rows / scored rows with share and n / sender level / delay), CIs by block bootstrap**\n")
    L += ["| class | all rows | scored rows | scored share | n scored | sender >=3 | n attackers | delay to 1st alarm s (q25/med/q75) | delay to 3rd alarm s |", "|---|---|---|---|---|---|---|---|---|"]
    F = G[FULL]
    for c in CLASSES:
        s, sd = F["msg_scored"][c], F["sender"][c]
        dq = lambda q: "-" if q[1] is None else f"{q[0]:.1f}/{q[1]:.1f}/{q[2]:.1f}"
        star = " *" if int(c[:2]) in HELDOUT else ""
        L.append(f"| {c}{star} | {cell(F['msg_all'][c])} | {cell(s) if s['n'] >= 50 else '-'} | {pc(F['scored_share'][c])} | {s['n']} | {cell(sd)} | {sd['n_senders']} | {dq(sd['delay_first_alarm_s_q25_med_q75'])} | {dq(sd['delay_kth_alarm_s_q25_med_q75'])} |")
    L.append("")
    L.append("**Sender level, full stack and L1+L2+L3: k = 3 (supervisor) vs k chosen on validation (<= 1% of genuine validation senders)**\n")
    L += ["| class | n attackers | full k=3 | full k val | L1+L2+L3 k=3 | L1+L2+L3 k val |", "|---|---|---|---|---|---|"]
    kF, kB = G[FULL]["kval"], G[BASE]["kval"]
    for c in CLASSES:
        L.append(f"| {c} | {G[FULL]['sender'][c]['n_senders']} | {cell(G[FULL]['sender'][c])} | {cell(kF['sender'][c])} | {cell(G[BASE]['sender'][c])} | {cell(kB['sender'][c])} |")
    L.append(f"| genuine senders flagged (FA) | {G[FULL]['fa_sender']['n_senders']} | {cell(G[FULL]['fa_sender'])} | {cell(kF['fa_sender'])} | {cell(G[BASE]['fa_sender'])} | {cell(kB['fa_sender'])} |")
    L.append(f"| k | | 3 | {kF['k']} | 3 | {kB['k']} |")
    L.append("")
    L.append("**Single checks alone at their own 1% operating point (message level, all rows; no combiner)**\n")
    names = list(o["checks"])
    L += ["| class | " + " | ".join(n.replace("v2x.", "") for n in names) + " |", "|---|" + "---|" * len(names)]
    for c in CLASSES:
        L.append(f"| {c} | " + " | ".join(pc(o["checks"][n]["msg_all"][c]["p"]) for n in names) + " |")
    L.append("| FA genuine msgs | " + " | ".join(pc(o["checks"][n]["fa_msg"]["p"]) for n in names) + " |")
    L.append("")
    L.append("**Combiner method selection on group-split validation halves (mean detection at 1% FA on the held-out half)**\n")
    L += ["| configuration | chosen | noisy_or | logistic | max |", "|---|---|---|---|---|"]
    for g, r in G.items():
        s = r["combiner"]["val_half_detection"]
        L.append(f"| {g} | {r['combiner']['method']} | " + " | ".join(pc(s.get(m)) for m in ("noisy_or", "logistic", "max")) + " |")
    L.append("")
    k = o["row_kinds"]
    L.append("**Row kinds (test): share of each class and detection of the full stack / of L4-scored by kind**\n")
    L += ["| class | scored share | first/gap share | repeat share | stack: scored | stack: first/gap | stack: repeat | L4: scored | L4: first/gap | L4: repeat |", "|---|---|---|---|---|---|---|---|---|---|"]
    for c in CLASSES:
        sh, sd, l4d = k["share"][c], k["stack_detection_by_kind"][c], k["L4_detection_by_kind"][c]
        L.append(f"| {c} | " + " | ".join([pc(sh[n]) for n in KIND_NAMES.values()] + [pc(sd[n]) for n in KIND_NAMES.values()] + [pc(l4d[n]) for n in KIND_NAMES.values()]) + " |")
    L.append(f"| genuine (share / FA stack) | " + " | ".join([pc(k['genuine_share'][n]) for n in KIND_NAMES.values()] + [pc(k['stack_FA_by_kind'][n]) for n in KIND_NAMES.values()] + [pc(k['L4_FA_by_kind'][n]) for n in KIND_NAMES.values()]) + " |")
    L.append("")
    c12 = o["class12"]
    L.append("**Class 12 (DelayedMessages*, zero-placeholder artefact; not claimed)**\n")
    L += ["| configuration | all rows | placeholder rows (x=y=0) | rows after the jump |", "|---|---|---|---|"]
    for g in (FULL, BASE, "L4-scored"):
        L.append(f"| {g} | {pc(c12[g]['all'])} | {pc(c12[g]['placeholder_rows'])} | {pc(c12[g]['after_jump_rows'])} |")
    L.append(f"| rows | {c12['n_rows']['all']} | {c12['n_rows']['placeholder']} | {c12['n_rows']['after_jump']} |")
    L.append("")
    sc = o["shuffled_control"]
    L.append("**Shuffled-label control on scored rows (bound: detection within 1 point of FA)**\n")
    L += ["| model | FA scored genuine | detection pooled scored attack rows | detection - FA (points) | mean seen | AUC scored rows |", "|---|---|---|---|---|---|"]
    s, r = sc["shuffled"], sc["real_model"]
    L.append(f"| shuffled labels | {pc(s['FA_scored_genuine_test'])} | {pc(s['detection_pooled_scored_attack'])} | {s['detection_minus_FA_points']:.1f} | {pc(s['mean_detection_seen_scored'])} | {s['auc_scored_rows']:.3f} |")
    L.append(f"| real labels | {pc(r['FA_scored_genuine_test'])} | {pc(r['detection_pooled_scored_attack'])} | {100 * (r['detection_pooled_scored_attack'] - r['FA_scored_genuine_test']):.1f} | - | {r['auc_scored_rows']:.3f} |")
    L.append(f"\nControl: {'PASS' if sc['pass'] else 'FAIL'} (|detection - FA| <= 1 point).\n")
    L.append("**Gain importance of the final scored-row L4 (top 12)**\n")
    L += ["| feature | share of gain |", "|---|---|"] + [f"| {f} | {100 * v:.1f}% |" for f, v in list(o["importance_gain"].items())[:12]]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------------------------------------------
def run_tampa(cfg, gb, veremi_out, tables):
    log("Tampa: loading (frozen VeReMi-trained scored-row L4)")
    tp = adapters.load_tampa(with_age=True)
    sp = json.loads((OUT / "splits_tampa_v2.json").read_text())
    p = json.loads((OUT / "s4_params_tampa.json").read_text())
    tracker = l3.Tracker(l3.KalmanParams(**p))
    tw = cfg["chosen_time_window_s"]
    val_df = splitting.rows_of(tp, sp["val"])
    val_df = val_df.assign(sample_id=val_df["msg_id"])
    ones = np.ones(len(val_df), bool)
    l1_names = L1_N + ["v2x.freshness"]
    l1_layers = [l for l in l1.make_layers() if l.name in l1_names]
    for l in l1_layers:
        l.calibrate(val_df, budget=BUDGET)
    l2_layers = [l for l in l2.make_layers(None) if l.name in L2_N]
    for l in l2_layers:
        l.calibrate_masked(val_df, ones, BUDGET)
    l3_layers = [l for l in l3.make_layers(tracker) if l.name in L3_N]
    for l in l3_layers:
        l.calibrate_masked(val_df, ones, BUDGET)
    layers = l1_layers + l2_layers + l3_layers
    vf, vk, vmeta = s3.tampa_frames(tp, sp["val"], True)
    tf, tk, tmeta = s3.tampa_frames(tp, sp["val" if SMOKE else "test"], False)
    raw_v, _ = s3.raw_over_frames(vf, vk, layers)
    raw_t, _ = s3.raw_over_frames(tf, tk, layers)

    def feats(frames, keeps):
        F = pd.concat([l4.feature_table(f, tracker, time_window_s=tw).iloc[np.flatnonzero(k)] for f, k in zip(frames, keeps)], ignore_index=True)
        K = np.concatenate([l4.row_kinds(f)[k] for f, k in zip(frames, keeps)])
        return F, K

    Fv, Kv = feats(vf, vk)
    Ft, Kt = feats(tf, tk)
    assert len(Fv) == len(vmeta) and len(Ft) == len(tmeta)
    yv, yt = vmeta["y"].to_numpy(bool), tmeta["y"].to_numpy(bool)
    cal_v, _ = s3.cal_alarm(layers, raw_v)
    cal_t, _ = s3.cal_alarm(layers, raw_t)
    pv, pt = l4_raw(gb, Fv, Kv), l4_raw(gb, Ft, Kt)
    c4 = ECDFCalibrator().fit(pv[~yv].astype(float))
    cal_v[L4_N], cal_t[L4_N] = c4.transform(pv.astype(float)), c4.transform(pt.astype(float))
    method = veremi_out["groups"][FULL]["combiner"]["method"]
    method = method if method in ("noisy_or", "max") else "max"
    names_all = l1_names + L2_N + L3_N + [L4_N]
    tgroups = {"L1": l1_names, "L2": L2_N, "L3": L3_N, "L4-scored": [L4_N], FULL: names_all, "all but L1": [n for n in names_all if n not in l1_names],
               "all but L2": [n for n in names_all if n not in L2_N], "all but L3": [n for n in names_all if n not in L3_N], BASE: [n for n in names_all if n != L4_N]}
    tmeta = tmeta.assign(group=tmeta["sender"].to_numpy())
    res, alarms = {}, {}
    for g, names in tgroups.items():
        Xv, Xt = np.column_stack([cal_v[n] for n in names]), np.column_stack([cal_t[n] for n in names])
        sv, st = cc._combine(method, Xv), cc._combine(method, Xt)
        th = budget_threshold(sv[~yv], BUDGET)
        al = st >= th
        alarms[g] = al
        r = strip_ci(stackeval.evaluate_alarms(tmeta, al, CLASSES + [SUPP], kinds=Kt, seen=SEEN, unseen=UNSEEN, k=3, B=20))
        r["val_FA_msg"] = float((sv[~yv] >= th).mean())
        r["auc_all_rows"] = auc(yt.astype(int), st)
        k0 = Kt == 0
        r["auc_scored_rows"] = auc(yt[k0].astype(int), st[k0])
        res[g] = r
    k0 = Kt == 0
    kinds = {"genuine_test_share": {KIND_NAMES[k]: float((Kt[~yt] == k).mean()) for k in KIND_NAMES},
             "genuine_val_share": {KIND_NAMES[k]: float((Kv[~yv] == k).mean()) for k in KIND_NAMES},
             "stack_FA_by_kind": {KIND_NAMES[k]: (float(alarms[FULL][~yt & (Kt == k)].mean()) if (~yt & (Kt == k)).any() else None) for k in KIND_NAMES}}
    out = {"smoke": SMOKE, "illustration_only": True, "note": "3 test vehicles, 2 attackers per type: no confidence intervals are claimed",
           "combiner_method_used": method, "n_test_genuine": int((~yt).sum()), "n_test_attack": int(yt.sum()), "n_val_genuine": int((~yv).sum()),
           "layers": names_all, "groups": res, "row_kinds": kinds, "L4_scored_auc_scored_rows": auc(yt[k0].astype(int), pt[k0]),
           "feature_shift_note": "Tampa beacons are 10 Hz, VeReMi 1 Hz; features are rate-invariant by construction (time window / no rate), residual scales are not"}
    L = [f"### Tampa (injected on real BSMs): ILLUSTRATION, 3 test vehicles, no CIs ({'SMOKE' if SMOKE else 'test'})\n",
         f"Frozen VeReMi-trained scored-row L4, Tampa tracker and layer calibrations, thresholds = 1% of Tampa genuine validation messages. Combiner: {method} (parameter-free; VeReMi chose "
         f"{veremi_out['groups'][FULL]['combiner']['method']}). Layers: " + ", ".join(n.replace('v2x.', '') for n in names_all) + ".\n"]
    head = ["configuration", "FA msgs", "FA scored msgs", "scored: mean seen", "scored: 6*", "scored: 17*", "sender>=3: mean seen", "all rows: mean 19", "AUC scored"]
    L += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for g, r in res.items():
        L.append("| " + " | ".join([g, pc(r["fa_msg"]["p"]), pc(r["fa_scored_msg"]["p"]), pc(r["mean_msg_scored"]["seen"]["p"]), pc(r["msg_scored"][aname(6)]["p"]),
                                    pc(r["msg_scored"][aname(17)]["p"]), pc(r["mean_sender"]["seen"]["p"]), pc(r["mean_msg_all"]["all"]["p"]), f"{r['auc_scored_rows']:.3f}"]) + " |")
    L.append("")
    names = list(res)
    L += ["**Per class, message level, scored rows / all rows (full stack vs L1+L2+L3 and each layer alone)**\n", "| class | scored share | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
    for c in CLASSES + [SUPP]:
        s = res[FULL]["msg_scored"].get(c)
        share = res[FULL]["scored_share"].get(c)
        L.append(f"| {c} | {pc(share)} | " + " | ".join((pc(res[g]['msg_scored'][c]['p']) if res[g]['msg_scored'][c]['n'] >= 20 else '(' + pc(res[g]['msg_all'][c]['p']) + ' all)') for g in names) + " |")
    L.append("")
    L.append(f"Genuine Tampa rows by kind (test): {json.dumps({k: round(v, 3) for k, v in kinds['genuine_test_share'].items()})}; stack FA by kind: {json.dumps({k: (round(v, 3) if v is not None else None) for k, v in kinds['stack_FA_by_kind'].items()})}.\n")
    tables.append("\n".join(L) + "\n")
    return out


def main():
    cache = Path(sys.argv[sys.argv.index("--cache") + 1])
    cfg = json.loads((OUT / "s6_dev.json").read_text())
    t0 = time.time()
    tables_v, tables_t = [], []
    vout, gb, tracker = run_veremi(cfg, cache, tables_v)
    (OUT / f"s6_veremi{SUF}.json").write_text(json.dumps(vout, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"s6_tables_veremi{SUF}.md").write_text("\n".join(tables_v))
    log("VeReMi saved", f"{time.time() - t0:.0f}s")
    tout = run_tampa(cfg, gb, vout, tables_t)
    (OUT / f"s6_tampa{SUF}.json").write_text(json.dumps(tout, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / f"s6_tables_tampa{SUF}.md").write_text("\n".join(tables_t))
    log("done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
