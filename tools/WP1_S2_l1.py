"""WP1 S2: evaluate the L1 receiver sanity rules (gps/l1.py) per dataset, once on test.

Datasets and what is evaluable (gps.l1.COVERAGE, written before results):
  KITTI  : kinematic physical-limit rules + Doppler-vs-position consistency; B2 (S1) as the baseline layer.
           Attacks: drift, accel_drift, jump, freeze, doppler_spoof, meaconing. Harness ablation (B2 vs L1 vs both).
  AV-GPS : kinematic physical-limit rules from position only; receiver-field rules reported as ARTEFACT only.
  UAV    : fix type, satellites, HDOP (physical), satellite / HDOP / noise / jamming-indicator jumps and
           Doppler-vs-position (calibrated on the benign flight), spoofing flight onset 118.0 s (first spoofed fix).
Outputs: results/WP1/S2_kitti.json, S2_kitti_*.md (harness tables), S2_avgps.json, S2_uav.json, S2_coverage.json.
Run from codes_v3/: python -u -W ignore tools/WP1_S2_l1.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import WP1_S1_b2 as S1
from common.config import SEED, results_dir
from common.evaluate import EvalSet, evaluate_domain, markdown_table, score_groups
from common.metrics import auc
from gps import l1
from gps import stream as S

BUDGET = 0.01
UAV_FIRST_SPOOFED_FIX_S = 118.0


def merge_evalsets(sets):
    first = sets[0]
    ev = {}
    for s in sets:
        ev.update(s.evidence)
    return EvalSet(ev, first.y, first.attack_type, first.group, first.t)


def subset(es, names):
    return EvalSet({n: es.evidence[n] for n in names}, es.y, es.attack_type, es.group, es.t)


def flags_from(evs):
    return np.array([e.alarm for e in evs], bool)


def raw_from(evs):
    return np.array([e.details["raw"] for e in evs], float)


def summarize_flags(df, flag, attacks):
    """df = test rows (in the order of the flags). Row/run-level detection per attack, FA on clean runs and on all normal rows."""
    y = df["label"].to_numpy()
    out = {"false_alarm_clean_runs": float(flag[(df["attack"] == "none").to_numpy()].mean()),
           "false_alarm_all_normal_rows": float(flag[y == 0].mean()),
           "detection_by_attack": {}, "run_detected": {}, "median_delay_s": {}}
    for a in attacks:
        m = (df["attack"] == a).to_numpy()
        out["detection_by_attack"][a] = float(flag[m & (y == 1)].mean())
        det, delays = 0, []
        runs = df[m].assign(f=flag[m])
        nr = runs["run"].nunique()
        for _, g in runs.groupby("run", sort=False):
            hit = np.flatnonzero(g[g["label"] == 1]["f"].to_numpy())
            if len(hit):
                det += 1
                delays.append(int(hit[0]))
        out["run_detected"][a] = float(det / nr) if nr else None
        out["median_delay_s"][a] = float(np.median(delays)) if delays else None
    return out


# ------------------------------------------------------------------------------------------------------------
def run_kitti(out):
    attacks = S.ATTACKS_V2 + S.ATTACKS_NEW
    kx = S.build_kitti(np.random.default_rng(SEED), new_attacks=S.ATTACKS_NEW)
    kx = kx.join(S1.b2_features(kx)).join(l1.l1_features(kx))
    print("KITTI rows", kx.groupby("part").size().to_dict(), flush=True)
    cols = l1.COVERAGE["kitti"]["evaluated"]
    rules = l1.make_rules(cols)
    b2 = S1.B2Layer()
    val_norm = kx[(kx["part"] == "val") & (kx["label"] == 0)]
    for r in rules:
        r.calibrate(val_norm, budget=BUDGET)
    b2.calibrate(val_norm, budget=BUDGET)
    layers = rules + [b2]
    val, test = kx[kx["part"] == "val"], kx[kx["part"] == "test"]
    sets_v, sets_t, flags = [], [], {}
    for lay in layers:
        sv, _ = S1.evalset(lay, val)
        st, ev_t = S1.evalset(lay, test)
        sets_v.append(sv); sets_t.append(st)
        flags[lay.name] = flags_from(ev_t)
    ESv, ESt = merge_evalsets(sets_v), merge_evalsets(sets_t)
    # test frame in evalset order (groupby run, sort=False): rebuild the same order for the flag summaries
    order = np.concatenate([g.index.to_numpy() for _, g in test.groupby("run", sort=False)])
    te = kx.loc[order]
    res = {"rows": kx.groupby("part").size().to_dict(), "budget": BUDGET, "limits": l1.LIMITS,
           "rules_evaluated": cols, "coverage": l1.COVERAGE["kitti"]}
    # --- margins to the physical limits (raw ratios) ---
    marg = {}
    for c in l1.KINEMATIC:
        marg[c] = {"max_val_normal": float(val_norm[c].max()),
                   "max_test_clean_runs": float(te.loc[te["attack"] == "none", c].max()),
                   "p99_test_clean_runs": float(te.loc[te["attack"] == "none", c].quantile(0.99))}
    res["margin_to_limit"] = marg
    # --- per rule at its OPERATING POINT: physical alarm (limit) for physical rules, 1% val budget for data-driven ---
    per = {}
    for lay in layers:
        per[lay.name] = summarize_flags(te, flags[lay.name], attacks)
        per[lay.name]["operating_point"] = ("physical limit (raw >= 1)" if getattr(lay, "physical", False)
                                            else "validation 1% budget, tie-safe")
        if getattr(lay, "physical", False) is False:
            per[lay.name]["threshold_raw_equivalent"] = S1.raw_equiv_threshold(lay)
    res["per_layer"] = per
    phys = [r.name for r in rules if r.physical]
    union = np.any([flags[n] for n in phys], axis=0)
    res["union_physical_kinematic"] = summarize_flags(te, union, attacks)
    res["union_physical_kinematic"]["rules"] = phys
    b2f = flags[b2.name]
    res["b2_or_physical_union"] = summarize_flags(te, b2f | union, attacks)
    allf = np.any([flags[n] for n in flags], axis=0)
    res["b2_or_every_l1_rule_each_at_its_operating_point"] = summarize_flags(te, allf, attacks)
    # --- harness ablations at the 1% domain budget ---
    names_all = [l.name for l in layers]
    kin = [r.name for r in rules if r.physical]
    vp = "gps.vel_pos_consistency"
    runs = {"S2_kitti_all": names_all,
            "S2_kitti_b2_kinematic": kin + [b2.name],
            "S2_kitti_b2_velpos": [vp, b2.name]}
    res["harness"] = {}
    for nm, names in runs.items():
        h = evaluate_domain(nm, subset(ESv, names), subset(ESt, names), wp="WP1", budget=BUDGET, method="auto")
        res["harness"][nm] = {"layers": h["layers"], "combined": h["combined"], "ablation": h["ablation"]}
        print(nm, "combined method", h["combined"]["method"], "AUC", round(h["combined"]["auc"], 4),
              "FA", round(h["combined"]["false_alarm_rate"], 4), flush=True)
    (out / "S2_kitti.json").write_text(json.dumps(res, indent=1, default=float))
    return res


# ------------------------------------------------------------------------------------------------------------
def run_avgps(out):
    av = S.load_avgps()
    av = av.join(l1.l1_features(av))
    cols = l1.COVERAGE["avgps"]["evaluated"]
    art = l1.COVERAGE["avgps"]["artefact_only"]
    val_norm = av[(av["part"] == "val") & (av["label"] == 0)]
    test = av[av["part"] == "test"]
    res = {"rows": av.groupby("part").size().to_dict(), "rules_evaluated": cols, "artefact_only": art,
           "coverage": l1.COVERAGE["avgps"], "limits": l1.LIMITS,
           "test_sessions": {r: {"label": int(g["label"].iloc[0]), "rows": int(len(g))} for r, g in test.groupby("run", sort=False)}}
    huge = test["r_speed"] * l1.LIMITS["V_MAX"] > 1e5            # position step > 100 km in one second: placeholder / no-fix jump
    res["test_attack_rows_with_step_over_100km"] = float(huge[test["label"] == 1].mean())
    res["test_normal_rows_with_step_over_100km"] = float(huge[test["label"] == 0].mean())
    out_rules = {}
    for c in cols + art:
        lay = l1.L1Rule(c).calibrate(val_norm, budget=BUDGET)
        ev = score_groups(lay, {r: g for r, g in test.groupby("run", sort=False)})
        order = np.concatenate([g.index.to_numpy() for _, g in test.groupby("run", sort=False)])
        te = av.loc[order]
        f, y = flags_from(ev), te["label"].to_numpy()
        sc = np.array([e.score for e in ev])
        d = {"physical_alarm": {"false_alarm_normal_rows": float(f[y == 0].mean()), "detection_attack_rows": float(f[y == 1].mean()),
                                "normal_rows_flagged": int(f[y == 0].sum()),
                                "false_alarm_by_session": {r: float(f[(te["run"] == r).to_numpy()].mean())
                                                           for r in te.loc[te["label"] == 0, "run"].unique()},
                                "detected_by_session": {r: float(f[(te["run"] == r).to_numpy()].mean())
                                                        for r in te.loc[te["label"] == 1, "run"].unique()}},
             "auc_calibrated_score": auc(y, sc), "artefact": c in art}
        if c in l1.KINEMATIC:
            d["physical_alarm"]["attack_rows_flagged_with_step_over_100km"] = float((f & (y == 1) & (te["r_speed"] * l1.LIMITS["V_MAX"] > 1e5).to_numpy()).sum())
            d["physical_alarm"]["attack_rows_flagged_total"] = int((f & (y == 1)).sum())
        out_rules[l1.RULES[c][0]] = d
        if not l1.RULES[c][1] == "physical":
            d["threshold_calibrated_on_val"] = lay.threshold
    kin_flags = np.any([np.array(flags_from(score_groups(l1.L1Rule(c).calibrate(val_norm, budget=BUDGET),
                                                         {r: g for r, g in test.groupby("run", sort=False)}))) for c in l1.KINEMATIC], axis=0)
    order = np.concatenate([g.index.to_numpy() for _, g in test.groupby("run", sort=False)])
    te = av.loc[order]
    y = te["label"].to_numpy()
    res["union_physical_kinematic"] = {"false_alarm_normal_rows": float(kin_flags[y == 0].mean()),
                                       "detection_attack_rows": float(kin_flags[y == 1].mean()),
                                       "normal_rows_flagged": int(kin_flags[y == 0].sum()),
                                       "normal_rows": int((y == 0).sum())}
    res["per_rule"] = out_rules
    (out / "S2_avgps.json").write_text(json.dumps(res, indent=1, default=float))
    return res


# ------------------------------------------------------------------------------------------------------------
def run_uav(out):
    uav = l1.attach_uav_extras(S.load_uav())
    uav = uav.join(l1.l1_features(uav))
    cols = l1.COVERAGE["uav"]["evaluated"]
    benign = uav[uav["run"] == "uav/benign"]
    rules = l1.make_rules(cols)
    for r in rules:
        r.calibrate(benign, budget=BUDGET)
    res = {"rules_evaluated": cols, "coverage": l1.COVERAGE["uav"], "limits": l1.LIMITS,
           "calibration": "data-driven rules (jumps, Doppler-vs-position) calibrated on the BENIGN flight, 1% budget, tie-safe; "
                          "physical rules have no calibration",
           "first_spoofed_fix_s": UAV_FIRST_SPOOFED_FIX_S, "label_onset_s": S.UAV_SPOOF_ONSET_S, "rules": {}}
    flights = {n: uav[uav["run"] == f"uav/{n}"] for n in S.UAV_FLIGHTS}
    per_flag = {}
    for r in rules:
        d = {"operating_point": "physical limit (raw >= 1)" if r.physical else "benign flight 1% budget",
             "raw_threshold": None if r.physical else S1.raw_equiv_threshold(r), "flights": {}}
        for n, f in flights.items():
            r.reset()
            ev = r.score(f)
            fl, t, raw = flags_from(ev), f["t"].to_numpy(), raw_from(ev)
            per_flag[(r.name, n)] = fl
            e = {"fixes": int(len(f)), "alarms": int(fl.sum()), "alarm_times_s": [round(float(x), 1) for x in t[fl][:12]]}
            if n == "spoofing":
                pre = t < S.UAV_SPOOF_ONSET_S
                post = t >= UAV_FIRST_SPOOFED_FIX_S
                e["false_alarm_before_117s"] = float(fl[pre].mean())
                e["alarms_before_117s"] = int(fl[pre].sum())
                e["alarms_from_118s"] = int(fl[post].sum()); e["fixes_from_118s"] = int(post.sum())
                hit = np.flatnonzero(fl & post)
                e["first_alarm_after_onset_s"] = float(t[hit[0]]) if len(hit) else None
                e["delay_from_first_spoofed_fix_s"] = float(t[hit[0]] - UAV_FIRST_SPOOFED_FIX_S) if len(hit) else None
                sc = np.array([x.score for x in ev])
                lab = (t >= UAV_FIRST_SPOOFED_FIX_S).astype(int)
                e["auc_vs_fixes_from_118s"] = auc(lab[t < 140], sc[t < 140]) if (lab[t < 140].min() != lab[t < 140].max()) else None
            if n == "benign":
                e["false_alarm_in_sample" if not r.physical else "false_alarm"] = float(fl.mean())
            d["flights"][n] = e
        res["rules"][r.name] = d
    ms = ["spoofing", "jamming", "benign"]
    for n in ms:
        union = np.any([per_flag[(r.name, n)] for r in rules], axis=0)
        t = flights[n]["t"].to_numpy()
        u = {"fixes": int(len(t)), "alarms": int(union.sum()), "alarm_times_s": [round(float(x), 1) for x in t[union][:25]]}
        if n == "spoofing":
            pre = t < S.UAV_SPOOF_ONSET_S
            post = t >= UAV_FIRST_SPOOFED_FIX_S
            u["false_alarm_before_117s"] = float(union[pre].mean())
            u["alarms_before_117s"] = int(union[pre].sum())
            hit = np.flatnonzero(union & post)
            u["first_alarm_after_onset_s"] = float(t[hit[0]]) if len(hit) else None
            u["delay_from_first_spoofed_fix_s"] = float(t[hit[0]] - UAV_FIRST_SPOOFED_FIX_S) if len(hit) else None
            u["fraction_of_fixes_from_118s_flagged"] = float(union[post].mean())
            u["fraction_of_fixes_118_to_137s_flagged"] = float(union[post & (t < 138)].mean())
            u["rules_firing_within_2s"] = [r.name for r in rules if (per_flag[(r.name, n)] & (t >= UAV_FIRST_SPOOFED_FIX_S) & (t <= UAV_FIRST_SPOOFED_FIX_S + 2.0)).any()]
        res.setdefault("union", {})[n] = u
    (out / "S2_uav.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def main():
    out = results_dir("WP1")
    (out / "S2_coverage.json").write_text(json.dumps({"coverage": l1.COVERAGE, "limits": l1.LIMITS}, indent=1))
    k = run_kitti(out)
    print(json.dumps({"union": k["union_physical_kinematic"], "margins": k["margin_to_limit"]}, indent=1, default=float), flush=True)
    a = run_avgps(out)
    print(json.dumps(a["union_physical_kinematic"], indent=1), flush=True)
    u = run_uav(out)
    print(json.dumps(u["union"], indent=1, default=float), flush=True)


if __name__ == "__main__":
    main()
