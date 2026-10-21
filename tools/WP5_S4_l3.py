"""WP5 S4: evaluate the V2X L3 per-sender Kalman tracker (v2x/l3.py) on top of L1 + L2 on VeReMi (D12, primary) and injected Tampa (D14, illustration).

Run from codes_v3/:  python -I -u -W ignore tools/WP5_S4_l3.py [--dev | --smoke]
  --dev    noise fit on TRAIN, calibration on VALIDATION, consistency and false alarms on validation, validation detection per class; test never touched.
  --smoke  pipeline check with the validation part standing in for test (files *_smoke, to delete; never reported).
  (none)   the single final run: test scored once per dataset. Acceptance rule: notes/WP5_v2x.md, 'S4 L3 per-sender Kalman tracker: acceptance rule'.
Protocol: noise parameters (sp, sv, sa) by maximum likelihood on genuine TRAIN tracks only; every threshold on genuine VALIDATION messages (1% budget, tie-safe),
held-out attack types 6, 12, 17 removed from the validation frame; L1 and L2 calibrated exactly as in tools/WP5_S3_l2.py (map_road not used anywhere).
Helpers (calibration of L1/L2, per-class tables, Tampa scenario frames) are imported from WP5_S2_l1.py / WP5_S3_l2.py; the harness is common/evaluate.py with the
fast combiner of S3.
Outputs (results/WP5/): s4_veremi.json/.md, s4_tampa.json/.md (harness), s4_summary.json, s4_params_<dataset>.json, s4_tables.md.
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
from common.config import SEED
from common.metrics import budget_threshold
from v2x import adapters, l1, l2, l3, splitting

import WP5_S2_l1 as s2
import WP5_S3_l2 as s3

OUT, BUDGET, HELDOUT, SUPP = s2.OUT, s2.BUDGET, s2.HELDOUT, s2.SUPP
DEV = "--dev" in sys.argv
SMOKE = "--smoke" in sys.argv
SUF = "_smoke" if SMOKE else ""
log, aname, fmt = s2.log, s2.aname, s2.fmt
L1_NAMES = s3.L1_NAMES
L2_NAMES = [n for n in s3.L2_NAMES if n != "v2x.map_road"]
L3_NAMES = ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.kf_cusum_lo", "v2x.track_birth"]
L3_KF = L3_NAMES[:3]
s3.SMOKE = False


def consistency_report(tracker, frame, genuine_mask):
    run = tracker.run(frame)
    g = np.asarray(genuine_mask, bool)
    sc = run["scored"] & g
    out = {"all_genuine": l3.consistency(run["nis"], sc)}
    sp_ = frame["speed"].to_numpy(dtype=float)
    out["moving_ge_3mps"] = l3.consistency(run["nis"], sc & (sp_ >= 3.0))
    out["slow_lt_3mps"] = l3.consistency(run["nis"], sc & (sp_ < 3.0))
    return out


def mean_detection(pc_op, classes):
    v = [pc_op["by_class"][c]["msg_detection"] for c in classes if c in pc_op["by_class"]]
    return float(np.mean(v)) if v else None


def analyse4(tag, layers, raw_val, raw_test, phys_val, phys_test, vmeta, tmeta, val_group, test_group, classes, supp=False, first_test=None):
    names = [l.name for l in layers]
    n_l1 = [n for n in names if n in L1_NAMES]
    n_l2 = [n for n in names if n in L2_NAMES]
    n_l3 = [n for n in names if n in L3_NAMES]
    n_l3kf = [n for n in n_l3 if n in L3_KF]
    byname = {l.name: l for l in layers}
    yv, yt = vmeta["y"].to_numpy(bool), tmeta["y"].to_numpy(bool)
    cal_v, al_v = s3.cal_alarm(layers, raw_val)
    cal_t, al_t = s3.cal_alarm(layers, raw_test)
    ES = lambda cal, al, m, grp: ev.EvalSet({n: s3.lite_list(cal[n], al[n]) for n in names}, m["y"].to_numpy().astype(int),
                                            m["atype"].to_numpy(), grp, m["t"].to_numpy())
    val_es, test_es = ES(cal_v, al_v, vmeta, val_group), ES(cal_t, al_t, tmeta, test_group)
    log(tag, "harness (all layers)")
    res = ev.evaluate_domain(f"s4_{tag}", val_es, test_es, wp="WP5", budget=BUDGET, method="auto")
    groups, comb_alarm = {}, {}
    for gname, gn in (("L1", n_l1), ("L2", n_l2), ("L3", n_l3), ("L1+L2", n_l1 + n_l2), ("L1+L2+L3", names)):
        comb, sv, st = ev._combined(val_es, test_es, gn, "auto", BUDGET)
        thr = budget_threshold(sv[~yv], BUDGET)
        r = ev._summarize(sv, st, val_es, test_es, BUDGET)
        r["method"] = comb.method
        groups[gname] = r
        comb_alarm[f"combined_{gname}"] = st >= thr
    comb_all, sv, st = ev._combined(val_es, test_es, names, res["combined"]["method"], BUDGET)
    comb_alarm["combined_all"] = st >= budget_threshold(sv[~yv], BUDGET)

    def union(ns):
        sv_ = np.max([cal_v[n] for n in ns], axis=0)
        st_ = np.max([cal_t[n] for n in ns], axis=0)
        thr = budget_threshold(sv_[~yv], BUDGET)
        return st_ >= thr, float(thr), float((sv_[~yv] >= thr).mean())

    al_u2, thr_u2, fa_u2 = union(n_l2)
    al_u3kf, thr_u3kf, fa_u3kf = union(n_l3kf)
    al_u3, thr_u3, fa_u3 = union(n_l3)
    al_u23, thr_u23, fa_u23 = union(n_l2 + n_l3)
    al_l1u = np.any([phys_test["v2x.field_ranges"] if n == "v2x.field_ranges" else al_t[n] for n in n_l1], axis=0)
    ops = {n: al_t[n] for n in names}
    ops.update({"L1_union_at_operating_points": al_l1u, "L2_union": al_u2, "L3_kf_union": al_u3kf, "L3_union": al_u3,
                "L2_L3_union": al_u23, "L1_and_L2_union": al_l1u | al_u2, "L1_L2_L3_union": al_l1u | al_u23})
    ops.update(comb_alarm)
    pc = s2.per_class(tmeta, ops, classes)
    rng = np.random.RandomState(SEED)
    if supp:
        for nm, d in pc.items():
            for c, s in d["by_class"].items():
                s["ci95_attacker_bootstrap"] = s2.boot_ci(s["attackers_hits"], s["attackers_n"], rng)
            g = tmeta[~yt].assign(a=ops[nm][~yt]).groupby("sender")["a"].agg(["sum", "size"])
            d["false_alarm_ci95_vehicle_bootstrap"] = s2.boot_ci(g["sum"].to_numpy(), g["size"].to_numpy(), rng)
    cls19 = [c for c in classes if c[:2].isdigit()]
    mean_det = {k: mean_detection(d, cls19) for k, d in pc.items()}
    s3k = {k: s3.sender_k(tmeta, ops[k], classes, 3) for k in ("L2_union", "L3_union", "L1_and_L2_union", "L1_L2_L3_union", "combined_L1+L2", "combined_L1+L2+L3")}
    birth = {}
    if first_test is not None:
        fv, ft = first_test
        birth = {"val_FA_per_genuine_birth": float(al_v["v2x.track_birth"][~yv & fv[0]].mean()) if (~yv & fv[0]).any() else None,
                 "test_FA_per_genuine_birth": float(al_t["v2x.track_birth"][~yt & ft].mean()) if (~yt & ft).any() else None,
                 "n_val_genuine_births": int((~yv & fv[0]).sum()), "n_test_genuine_births": int((~yt & ft).sum())}
    phys_fa = {"v2x.field_ranges": {"val_genuine": float(phys_val["v2x.field_ranges"][~yv].mean()),
                                    "test_genuine": float(phys_test["v2x.field_ranges"][~yt].mean())}}
    summ = {"layers_run": names, "n_val_genuine": int((~yv).sum()), "n_val_for_combiner": int(len(yv)),
            "n_test": int(len(yt)), "n_test_genuine": int((~yt).sum()), "n_test_attack": int(yt.sum()),
            "threshold_raw_equivalent": {n: s3.raw_equiv_val(byname[n], raw_val[n], cal_v[n]) for n in names},
            "union_thresholds_score": {"L2": thr_u2, "L3_kf": thr_u3kf, "L3": thr_u3, "L2_L3": thr_u23},
            "union_val_FA": {"L2": fa_u2, "L3_kf": fa_u3kf, "L3": fa_u3, "L2_L3": fa_u23},
            "val_FA_budget_ops": {n: float(al_v[n][~yv].mean()) for n in names},
            "physical_FA": phys_fa, "birth": birth,
            "groups": {k: {kk: vv for kk, vv in v.items() if kk != "delay"} | {"delay": v["delay"]} for k, v in groups.items()},
            "per_operating_point": {k: {kk: vv for kk, vv in d.items() if kk != "by_class"} for k, d in pc.items()},
            "mean_detection_19_classes": mean_det,
            "by_class": {k: {c: {kk: vv for kk, vv in s.items() if not kk.startswith("attackers_")} for c, s in d["by_class"].items()}
                         for k, d in pc.items()},
            "sender_ge3_alarms": s3k,
            "harness_method": res["combined"]["method"], "harness_selection": res["combined"]["method_selection"]}
    return res, summ, pc, s3k, ops


def tables_for4(title, pc, s3k, classes, mean_det):
    out = []
    lcols = L3_NAMES
    out.append(s2.md_table(f"{title}: message-level detection per class, each L3 check at the 1% validation budget", pc, lcols, classes,
                           lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")), "* = attack type held out of calibration and combiner."))
    ucols = ["L1_and_L2_union", "L2_union", "L3_kf_union", "L3_union", "L2_L3_union", "L1_L2_L3_union", "combined_L1+L2", "combined_L3", "combined_L1+L2+L3"]
    ucols = [c for c in ucols if c in pc]
    t = s2.md_table(f"{title}: message-level detection, unions and harness combinations", pc, ucols, classes,
                    lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")),
                    "L2_union / L3_kf_union / L3_union / L2_L3_union = max of calibrated scores at one 1% budget (L3_union includes the track-birth check); "
                    "L1_and_L2_union = L1 operating points OR L2_union (S3); L1_L2_L3_union = L1 operating points OR L2_L3_union; combined_* = harness combiner chosen on validation.")
    t += "| mean over the classes | " + " | ".join(fmt(mean_det.get(c)) for c in ucols) + " |\n"
    out.append(t)
    scols = ["L1_and_L2_union", "L3_union", "L1_L2_L3_union"]
    out.append(s2.md_table(f"{title}: sender-level detection (>= 1 alarm among the attacker's falsified messages) / median delay of detected attackers (s)", pc, scols, classes,
                           lambda d, c: f"{fmt(d['by_class'].get(c, {}).get('sender_detected'))} / {fmt(d['by_class'].get(c, {}).get('median_delay_s'), False)} s", ""))
    ks = ["L1_and_L2_union", "L3_union", "L1_L2_L3_union"]
    lines = ["| class | " + " | ".join(f"{k} >= 3 alarms" for k in ["L2_union", "L3_union", "L1_and_L2_union", "L1_L2_L3_union"]) + " |", "|---|---|---|---|---|"]
    for c in classes:
        if c in s3k["L3_union"]["by_class"]:
            lines.append(f"| {c} | " + " | ".join(fmt(s3k[k]["by_class"].get(c)) for k in ["L2_union", "L3_union", "L1_and_L2_union", "L1_L2_L3_union"]) + " |")
    lines.append("| genuine senders with >= 3 alarms | " + " | ".join(fmt(s3k[k]["false_alarm_genuine_senders"]) for k in ["L2_union", "L3_union", "L1_and_L2_union", "L1_L2_L3_union"]) + " |")
    out.append("\n".join(lines) + "\n")
    return out


def first_flags(frame):
    return l1.first_in_track(frame)


# ----------------------------------------------------------------------------------------------------------
def run_veremi(summary, tables):
    log("VeReMi: loading")
    v = adapters.load_veremi()
    v["sample_id"] = v["msg_id"]
    sp = json.loads((OUT / "splits_veremi.json").read_text())
    first_t = v.groupby("sender")["t"].min()
    v["group"] = v["sender"].map((first_t // splitting.BLOCK_S).astype(int).astype(str))
    train = splitting.rows_of(v, sp["train"])
    gen_train = train[train["label"] == 0]
    tracker = l3.Tracker()
    t0 = time.time()
    info = tracker.fit(gen_train)
    senders = info.pop("senders_used")
    assert set(senders) <= set(map(str, sp["train"]))
    log("noise fit on genuine train:", tracker.params.to_dict(), {k: info[k] for k in ("n_tracks", "n_messages", "neg_loglik_per_message", "nfev", "converged")}, f"{time.time() - t0:.0f}s")
    info["n_senders_used"] = len(senders)
    tracker.save(OUT / f"s4_params_veremi{SUF}.json")
    val_all = splitting.rows_of(v, sp["val"])
    val_h = val_all[~val_all["label"].isin(HELDOUT)]
    gen_mask = (val_h["label"] == 0).to_numpy()
    cons = consistency_report(tracker, val_h, gen_mask)
    log("VeReMi genuine VAL consistency:", json.dumps(cons["all_genuine"]))
    log("   moving:", json.dumps(cons["moving_ge_3mps"]))
    log("   slow  :", json.dumps(cons["slow_lt_3mps"]))
    val_norm = val_all[val_all["label"] == 0]
    l1_layers = [l for l in l1.make_layers() if l.name in ("v2x.beacon_rate", "v2x.field_ranges")]
    for l in l1_layers:
        l.calibrate(val_norm, budget=BUDGET)
    l2_layers = [l for l in l2.make_layers() if l.name not in ("v2x.yaw_consistency", "v2x.map_road")]
    for l in l2_layers:
        l.calibrate_masked(val_h, gen_mask, BUDGET)
    l3_layers = l3.make_layers(tracker)
    for l in l3_layers:
        l.calibrate_masked(val_h, gen_mask, BUDGET)
        log("  calibrated", l.name, "thr (score)", l.threshold)
    layers = l1_layers + l2_layers + l3_layers
    yv = (val_h["label"] > 0).to_numpy()
    raw_val, phys_val = s3.raw_over_frames([val_h], [np.ones(len(val_h), bool)], layers)
    vmeta = pd.DataFrame({"sender": val_h["sender"].to_numpy(), "t": val_h["t"].to_numpy(), "y": yv,
                          "atype": np.where(yv, val_h["label"].map(aname), "normal")})
    _, al_v = s3.cal_alarm(layers, raw_val)
    fa_v = {n: round(float(a[~yv].mean()), 4) for n, a in al_v.items()}
    log("VeReMi val genuine FA at budget ops:", fa_v)
    fv = first_flags(val_h)
    log("VeReMi val genuine births", int((~yv & fv).sum()), "FA per genuine birth (track_birth)", float(al_v["v2x.track_birth"][~yv & fv].mean()))
    if DEV:
        classes = [aname(c) for c in range(1, 20)]
        cal_v, _ = s3.cal_alarm(layers, raw_val)
        rows = []
        for nm in L3_NAMES + ["L3 kf union"]:
            sc = np.max([cal_v[n] for n in L3_KF], axis=0) if nm == "L3 kf union" else cal_v[nm]
            thr = budget_threshold(sc[~yv], BUDGET)
            al = sc >= thr
            rows.append((nm, {c: round(float(al[vmeta["atype"].to_numpy() == c].mean()), 3) for c in classes if (vmeta["atype"].to_numpy() == c).any()}))
        for nm, r in rows:
            log("VAL detection", nm, r)
        return None
    test = val_all if SMOKE else splitting.rows_of(v, sp["test"])
    log("VeReMi: scoring test", len(test))
    raw_test, phys_test = s3.raw_over_frames([test], [np.ones(len(test), bool)], layers)
    yt = (test["label"] > 0).to_numpy()
    tmeta = pd.DataFrame({"sender": test["sender"].to_numpy(), "t": test["t"].to_numpy(), "y": yt,
                          "atype": np.where(yt, test["label"].map(aname), "normal")})
    cons_test = consistency_report(tracker, test, ~yt)
    log("VeReMi genuine TEST consistency (information only):", json.dumps(cons_test["all_genuine"]))
    classes = [aname(c) for c in range(1, 20)]
    res, summ, pc, s3k, ops = analyse4("veremi" + SUF, layers, raw_val, raw_test, phys_val, phys_test, vmeta, tmeta,
                                       val_h["group"].to_numpy(), test["group"].to_numpy(), classes,
                                       first_test=((fv,), first_flags(test)))
    summ["noise_fit"] = {"params": tracker.params.to_dict(), **info}
    summ["consistency_val_genuine"] = cons
    summ["consistency_test_genuine"] = cons_test
    summ["constants"] = {"K_HI": l3.K_HI, "K_LO": l3.K_LO, "DT_MAX": l3.DT_MAX, "BIRTH_RADIUS_M": l3.BIRTH_RADIUS_M, "BIRTH_WINDOW_S": l3.BIRTH_WINDOW_S,
                         "SP_MIN": l3.SP_MIN, "SV_MIN": l3.SV_MIN, "SA_MIN": l3.SA_MIN}
    # track length context for the classes the tracker cannot see
    tl = test[yt].groupby(["sender", "track"]).size().reset_index(name="n")
    tl["atype"] = tl["sender"].map(test[yt].drop_duplicates("sender").set_index("sender")["label"].map(aname))
    summ["track_length_attack_test"] = {c: {"median_messages_per_track": float(g["n"].median()), "frac_tracks_one_message": float((g["n"] == 1).mean())}
                                        for c, g in tl.groupby("atype")}
    summary["veremi"] = summ
    tables.append("### VeReMi (D12) test\n")
    tables += tables_for4("VeReMi test", pc, s3k, classes, summ["mean_detection_19_classes"])
    tables.append(s3.fa_table("VeReMi test", pc))
    tables.append(open(OUT / f"s4_veremi{SUF}.md").read())
    gl = ["| group | method | AUC | detection (all attacks) | false alarms |", "|---|---|---|---|---|"]
    for k, r in summ["groups"].items():
        gl.append(f"| {k} | {r['method']} | {r['auc']:.3f} | {fmt(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% |")
    tables.append("**VeReMi test, harness group ablation (L3 on top of L1 + L2)**\n\n" + "\n".join(gl) + "\n")
    return res


def run_tampa(summary, tables):
    log("Tampa: loading")
    tp = adapters.load_tampa(with_age=True)
    sp = json.loads((OUT / "splits_tampa_v2.json").read_text())
    train = splitting.rows_of(tp, sp["train"])
    tracker = l3.Tracker()
    info = tracker.fit(train)
    senders = info.pop("senders_used")
    assert set(senders) <= set(map(str, sp["train"]))
    info["n_senders_used"] = len(senders)
    log("Tampa noise fit on train passages:", tracker.params.to_dict(), {k: info[k] for k in ("n_tracks", "n_messages", "neg_loglik_per_message", "converged")})
    tracker.save(OUT / f"s4_params_tampa{SUF}.json")
    val_df = splitting.rows_of(tp, sp["val"])
    val_df = val_df.assign(sample_id=val_df["msg_id"])
    cons = consistency_report(tracker, val_df, np.ones(len(val_df), bool))
    log("Tampa genuine VAL consistency:", json.dumps(cons["all_genuine"]))
    l1_layers = [l for l in l1.make_layers() if l.name in L1_NAMES]
    for l in l1_layers:
        l.calibrate(val_df, budget=BUDGET)
    l2_layers = [l for l in l2.make_layers(None) if l.name != "v2x.map_road"]
    for l in l2_layers:
        l.calibrate_masked(val_df, np.ones(len(val_df), bool), BUDGET)
    l3_layers = l3.make_layers(tracker)
    for l in l3_layers:
        l.calibrate_masked(val_df, np.ones(len(val_df), bool), BUDGET)
    layers = l1_layers + l2_layers + l3_layers
    vf, vk, vmeta = s3.tampa_frames(tp, sp["val"], True)
    raw_val, phys_val = s3.raw_over_frames(vf, vk, layers)
    yv = vmeta["y"].to_numpy(bool)
    _, al_v = s3.cal_alarm(layers, raw_val)
    log("Tampa val genuine FA at budget ops:", {n: round(float(a[~yv].mean()), 4) for n, a in al_v.items()})
    if DEV:
        classes = [aname(c) for c in range(1, 20)] + [SUPP]
        cal_v, _ = s3.cal_alarm(layers, raw_val)
        for nm in L3_NAMES:
            al = cal_v[nm] >= budget_threshold(cal_v[nm][~yv], BUDGET)
            log("TAMPA VAL detection", nm, {c: round(float(al[vmeta["atype"].to_numpy() == c].mean()), 3) for c in classes if (vmeta["atype"].to_numpy() == c).any()})
        return None
    sp_test = sp["val"] if SMOKE else sp["test"]
    tf, tk, tmeta = s3.tampa_frames(tp, sp_test, SMOKE)
    log("Tampa: scoring test", len(tmeta), "messages")
    raw_test, phys_test = s3.raw_over_frames(tf, tk, layers)
    yt = tmeta["y"].to_numpy(bool)
    classes = [aname(c) for c in range(1, 20)] + [SUPP]
    cons_test = consistency_report(tracker, tf[0], np.ones(len(tf[0]), bool))
    res, summ, pc, s3k, ops = analyse4("tampa" + SUF, layers, raw_val, raw_test, phys_val, phys_test, vmeta, tmeta,
                                       vmeta["sender"].to_numpy(), tmeta["sender"].to_numpy(), classes, supp=True)
    summ["noise_fit"] = {"params": tracker.params.to_dict(), **info}
    summ["consistency_val_genuine"] = cons
    summ["consistency_test_genuine"] = cons_test
    summary["tampa"] = summ
    tables.append("### Tampa (injected on real BSMs) test: ILLUSTRATION (3 test vehicles, 2 attackers per type), no statistics\n")
    tables += tables_for4("Tampa test", pc, s3k, classes, summ["mean_detection_19_classes"])
    tables.append(s2.md_table("Tampa test: attacker-bootstrap 95% CI of message detection (NOT valid intervals with 2 attackers; shown for completeness)", pc,
                              ["L3_union", "L1_L2_L3_union"], classes,
                              lambda d, c: "[" + ", ".join(fmt(x) for x in d["by_class"].get(c, {}).get("ci95_attacker_bootstrap", [None, None])) + "]", ""))
    tables.append(s3.fa_table("Tampa test", pc, ci=True))
    tables.append(open(OUT / f"s4_tampa{SUF}.md").read())
    gl = ["| group | method | AUC | detection (all attacks) | false alarms |", "|---|---|---|---|---|"]
    for k, r in summ["groups"].items():
        gl.append(f"| {k} | {r['method']} | {r['auc']:.3f} | {fmt(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% |")
    tables.append("**Tampa test, harness group ablation (L3 on top of L1 + L2)**\n\n" + "\n".join(gl) + "\n")
    return res


def main():
    assert not (DEV and SMOKE)
    summary = {"budget": BUDGET, "heldout_attack_types": HELDOUT, "map_road": "not used (outside every union)"}
    tables = []
    run_veremi(summary, tables)
    run_tampa(summary, tables)
    if not DEV:
        s2.jdump(f"s4_summary{SUF}.json", summary)
        (OUT / f"s4_tables{SUF}.md").write_text("\n".join(tables))
    log("done" + (" (dev: no test touched)" if DEV else ""))


if __name__ == "__main__":
    main()
