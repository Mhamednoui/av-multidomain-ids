"""WP1 S4: build results/WP1/S4_tables.md (+ S4_acceptance.json) from S4_dev.json, S4_kitti.json, S4_l2c.json, S4_uav.json.
No hand-typed numbers. Run from codes_v3/: python -u -W ignore tools/WP1_S4_tables.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import results_dir

OUT = results_dir("WP1")
ATT = ["drift", "accel_drift", "jump", "freeze", "doppler_spoof", "meaconing"]
P = lambda x, d=1: "n/a" if x is None else f"{100 * x:.{d}f}%"


def load(n):
    return json.loads((OUT / n).read_text())


def layer_table(per, names, title):
    head = ["layer", "FA clean runs", "FA normal rows"] + ATT + ["slow drift <0.5 m/s within 30 s", "AUC (row)"]
    lines = [f"**{title}**", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for n in names:
        s = per[n]
        sd = s["slow_drift_lt_0.5_within_30s"]
        row = [n, P(s["false_alarm_clean_runs"], 2), P(s["false_alarm_all_normal_rows"], 2)]
        row += [f"{P(s['run_detected'][a], 0)} ({P(s['row_detection'][a], 0)})" for a in ATT]
        row += [f"{P(sd['rate'], 0)} of {sd['runs']}", f"{s['auc_row_level']:.3f}"]
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines) + "\n"


def delay_table(per, names, title):
    lines = [f"**{title}** (fixes after onset of the first alarm, detected runs only; q10 / q25 / median / q75 / q90; share of ALL runs detected within 10 s / 30 s)", "",
             "| layer | " + " | ".join(ATT) + " |", "|" + "---|" * (len(ATT) + 1)]
    for n in names:
        cells = []
        for a in ATT:
            d = per[n]["delays"][a]
            q = d["delays_q10_25_50_75_90_s"]
            cells.append("-" if q is None else "/".join(f"{x:.0f}" for x in q) + f" ; {P(d['within_10s'], 0)} / {P(d['within_30s'], 0)}")
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def abl_table(h, title):
    atts = sorted({a for r in h["ablation"].values() for a in r["detection_by_attack"]})
    head = ["configuration", "AUC", "detection", "false alarms"] + [f"det {a}" for a in atts]
    lines = [f"**{title}**", "", "| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for k, r in h["ablation"].items():
        lines.append("| " + " | ".join([k, f"{r['auc']:.3f}", P(r["detection"]), P(r["false_alarm_rate"], 2)] +
                                       [P(r["detection_by_attack"].get(a)) for a in atts]) + " |")
    return "\n".join(lines) + "\n"


def main():
    dev, kit, l2c = load("S4_dev.json"), load("S4_kitti.json"), load("S4_l2c.json")
    uav = load("S4_uav.json")
    sel = dev["selection"]
    md, acc = [], {}
    md.append(f"Selected on the 16 train+val drives (S4_dev.json): best DR layer `{sel['best_dr']}`, best EKF-innovation layer `{sel['best_ekf']}`; criterion {sel['criterion']}.\n")
    # ---------------- dev LODO vs val-only ----------------
    cands = ["gps.dr_resid_10", "gps.ekf_nis", sel["best_ekf"], sel["best_dr"]]
    lines = ["**Development drives (train + val): what LODO changes.** FA on the 13 train drives with a threshold from the 3 val drives only, vs the pooled LODO threshold; "
             "held-out FA = each drive's FA with the threshold from the other 15 drives.", "",
             "| layer | FA 13 train drives @ val-only thr | FA 13 train drives @ LODO thr | LODO held-out FA (pooled) | worst held-out drive |", "|---|---|---|---|---|"]
    for k in cands:
        r = dev["candidates"][k]["lodo"]
        lines.append(f"| {k} | {P(r['fa_on_train_drives_at_val_only_threshold'], 2)} | {P(r['fa_on_train_drives_at_lodo_threshold'], 2)} | {P(r['heldout_fa_pooled'], 2)} | {P(r['heldout_fa_worst_drive'], 2)} |")
    md.append("\n".join(lines) + "\n")
    # ---------------- dev grid top ----------------
    top = sorted(((k, v["J"], v["summary"]["slow_drift_lt_0.5_within_30s"]["rate"], v["lodo"]["heldout_fa_pooled"]) for k, v in dev["candidates"].items() if k.startswith("cusum")),
                 key=lambda x: -x[1])[:8]
    md.append("**Grid, top 8 by J (dev drives, LODO threshold)** (full table: S4_dev_grid.md)\n\n| candidate | J | slow-drift30 | LODO held-out FA |\n|---|---|---|---|\n" +
              "\n".join(f"| {k} | {j:.3f} | {P(s, 0)} | {P(f, 2)} |" for k, j, s, f in top) + "\n")
    # ---------------- test, both calibrations ----------------
    names = ["gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr", "gps.cusum_dr_noscale", "gps.cusum_dr_nofreeze"]
    for sch, label in (("lodo", "LODO calibration (16 drives) - primary"), ("valonly", "val-only calibration (3 drives)")):
        per = kit["calibration"][sch]["per_layer"]
        md.append(layer_table(per, names, f"KITTI test, {label}: run-level detection (row-level in brackets)"))
    for sch in ("lodo", "valonly"):
        md.append(delay_table(kit["calibration"][sch]["per_layer"], ["gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr"], f"Detection delay distribution, {sch}"))
    # transfer
    tr = kit["calibration"]["lodo"]["lodo_transfer"]
    lines = ["**FA transfer on test (clean test runs, 1% budget).**", "", "| layer | val-only calibration | LODO calibration | LODO held-out estimate (dev) | worst dev drive |", "|---|---|---|---|---|"]
    for n in ("gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr"):
        lines.append(f"| {n} | {P(kit['calibration']['valonly']['per_layer'][n]['false_alarm_clean_runs'], 2)} | {P(kit['calibration']['lodo']['per_layer'][n]['false_alarm_clean_runs'], 2)} | "
                     f"{P(tr[n]['lodo_heldout_fa_pooled'], 2)} | {P(tr[n]['lodo_worst_drive_fa'], 2)} |")
    md.append("\n".join(lines) + "\n")
    # beat B2
    pl = kit["calibration"]["lodo"]["per_layer"]
    lines = ["**Beat-or-not vs B2 (both LODO-calibrated; rule B6: >= +5 points run-level AND clean-run FA <= B2 + 0.5 point).**", "",
             "| attack | " + " | ".join(["gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr"]) + " |", "|---|---|---|---|"]
    b2 = pl["gps.dr_resid_10"]
    verdict = {}
    for a in ATT:
        cells = []
        for n in ("gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr"):
            diff = pl[n]["run_detected"][a] - b2["run_detected"][a]
            fa_ok = pl[n]["false_alarm_clean_runs"] <= b2["false_alarm_clean_runs"] + 0.005
            v = "beats B2" if (diff >= 0.05 and fa_ok) else ("more detection, higher FA" if diff >= 0.05 else "worse" if diff <= -0.05 else "no difference")
            cells.append(f"{100 * diff:+.0f} pts: {v}")
            verdict[f"{n}|{a}"] = v
        lines.append(f"| {a} | " + " | ".join(cells) + " |")
    md.append("\n".join(lines) + "\n")
    # ---------------- L2c ----------------
    sel_k = "learn+freeze(selected)"
    cl = l2c[sel_k]["scale"]["clean"]
    md.append("**L2c on clean TEST runs: scale convergence** (|s_hat - s*|/s*, median over runs that reach that time; prior error = |1 - s*|)\n\n| prior median | prior RMS | 10 s | 20 s | 30 s | 60 s |\n|---|---|---|---|---|---|\n" +
              f"| {P(cl['prior_error_median'], 2)} | {P(cl['prior_error_rms'], 2)} | " + " | ".join(f"{P(cl[f'median_rel_error_at_{k}s'], 2)} (n={cl[f'runs_at_{k}s']})" for k in (10, 20, 30, 60)) + " |\n")
    lines = ["**L2c on TEST attacks: scale error at onset+30 s (drag) with / without freezing** (s* from the run; frozen = share of the first 30 s with GPS updates skipped)", "",
             "| attack | runs | at onset | +30 s learn+freeze | +30 s learn, no freeze | +30 s no scale learning | frozen share |", "|---|---|---|---|---|---|---|"]
    for a in ATT:
        s1, s2, s3 = (l2c[k]["scale"]["attacks"][a] for k in (sel_k, "learn+nofreeze", "noscale+freeze"))
        lines.append(f"| {a} | {s1['runs']} | {P(s1['median_rel_error_at_onset'], 2)} | {P(s1['median_rel_error_at_onset_plus_30s'], 2)} | {P(s2['median_rel_error_at_onset_plus_30s'], 2)} | "
                     f"{P(s3['median_rel_error_at_onset_plus_30s'], 2)} | {P(s1['mean_frozen_fraction_first_30s'], 0)} |")
    md.append("\n".join(lines) + "\n")
    lines = ["**Absorption on TEST: position-estimate error / reported error at onset+30 s (median, runs with reported error >= 5 m)**", "",
             "| attack | ungated EKF (S3) | DR branch, no freeze | DR branch, selected (freeze) |", "|---|---|---|---|"]
    for a in ATT:
        f = lambda d: "n/a" if d is None else f"{d:.2f}"
        lines.append(f"| {a} | {f(l2c['ungated_ekf_absorption'][a]['median_absorbed_fraction'])} | {f(l2c['learn+nofreeze']['absorption'][a]['median_absorbed_fraction'])} | "
                     f"{f(l2c[sel_k]['absorption'][a]['median_absorbed_fraction'])} |")
    md.append("\n".join(lines) + "\n")
    # ---------------- harness ----------------
    for sch, label in (("lodo", "LODO calibration + combiner fitted on the 16 drives"), ("valonly", "val-only (3 drives)")):
        for nm in ("S4_all", "S4_base_dr", "S4_base_ekfcusum", "S4_l2b_pair"):
            h = kit["calibration"][sch]["harness"][nm]
            md.append(abl_table(h, f"Harness ablation {nm}, {label}"))
    # ---------------- UAV ----------------
    lines = ["**UAV (EKF-based CUSUM only; threshold from the benign flight at 1%, in-sample)**", "", "| layer | alarms before 117 s | first alarm >= 118 s | delay (s) | share of fixes from 118 s flagged | benign alarms | jamming alarms |", "|---|---|---|---|---|---|---|"]
    for k, v in uav.items():
        if not k.startswith("cusum"):
            continue
        s = v["flights"]["spoofing"]
        lines.append(f"| {k} | {s['alarms_before_117s']}/{s['fixes_before_117s']} | {s['first_alarm_after_118s']} | {s['delay_from_first_spoofed_fix_s']} | {P(s['fraction_from_118s_flagged'], 0)} | "
                     f"{v['flights']['benign']['alarms']}/{v['flights']['benign']['fixes']} | {v['flights']['jamming']['alarms']}/{v['flights']['jamming']['fixes']} |")
    md.append("\n".join(lines) + "\n")
    # ---------------- acceptance ----------------
    A = {}
    cm = l2c[sel_k]["scale"]["clean"]
    A["B2_scale_30s_le_0.7pct"] = {"value": cm["median_rel_error_at_30s"], "met": bool(cm["median_rel_error_at_30s"] is not None and cm["median_rel_error_at_30s"] <= 0.007),
                                   "60s": "not evaluable: no test run reaches 60 s" if cm["runs_at_60s"] == 0 else cm["median_rel_error_at_60s"]}
    drag = {}
    for a in ("drift", "accel_drift", "doppler_spoof", "meaconing"):
        drag[a] = (l2c[sel_k]["scale"]["attacks"][a]["median_rel_error_at_onset_plus_30s"], l2c["learn+nofreeze"]["scale"]["attacks"][a]["median_rel_error_at_onset_plus_30s"])
    A["B3_freeze_protects"] = {"per_attack_freeze_vs_nofreeze": drag,
                               "met": bool(all(f is not None and n is not None and f <= 0.5 * n and f <= 0.01 for f, n in drag.values()))}
    for sch in ("lodo", "valonly"):
        pls = kit["calibration"][sch]["per_layer"]
        A[f"B4_fa_clean_runs_le_1.5pct_{sch}"] = {n: pls[n]["false_alarm_clean_runs"] for n in ("gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr")}
        A[f"B4_met_{sch}"] = {n: bool(pls[n]["false_alarm_clean_runs"] <= 0.015) for n in ("gps.cusum_ekf", "gps.cusum_dr")}
    A["B5_slow_drift_ge_60pct"] = {n: {"lodo": pl[n]["slow_drift_lt_0.5_within_30s"], "valonly": kit["calibration"]["valonly"]["per_layer"][n]["slow_drift_lt_0.5_within_30s"]}
                                   for n in ("gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr")}
    A["B5_met_lodo"] = {n: bool((pl[n]["slow_drift_lt_0.5_within_30s"]["rate"] or 0) >= 0.6 and pl[n]["false_alarm_clean_runs"] <= 0.015) for n in ("gps.cusum_ekf", "gps.cusum_dr")}
    A["B6_verdicts_vs_B2_lodo"] = verdict
    for sch in ("lodo", "valonly"):
        base, full = kit["calibration"][sch]["harness"]["S4_base"]["combined"], kit["calibration"][sch]["harness"]["S4_all"]["combined"]
        ab = kit["calibration"][sch]["harness"]["S4_all"]["ablation"]
        rows = {a: full["detection_by_attack"].get(a, 0) - base["detection_by_attack"].get(a, 0) for a in ATT}
        A[f"B7_{sch}"] = {"auc_base": base["auc"], "auc_all": full["auc"], "auc_gain": full["auc"] - base["auc"], "fa_base": base["false_alarm_rate"], "fa_all": full["false_alarm_rate"],
                          "row_level_gain_points": {a: 100 * v for a, v in rows.items()},
                          "adds": bool((full["auc"] - base["auc"] >= 0.01 or max(rows.values()) >= 0.05) and full["false_alarm_rate"] <= 0.015)}
    ab = l2c
    A["B8_absorption_dr_frozen"] = {a: l2c[sel_k]["absorption"][a]["median_absorbed_fraction"] for a in ATT}
    A["B8_met"] = bool(all((l2c[sel_k]["absorption"][a]["median_absorbed_fraction"] or 9) <= 0.3 for a in ("doppler_spoof", "meaconing")))
    A["B9_uav"] = {k: {"delay_s": v["flights"]["spoofing"]["delay_from_first_spoofed_fix_s"], "fa_before_117": v["flights"]["spoofing"]["false_alarm_before_117s"]}
                   for k, v in uav.items() if k.startswith("cusum")}
    (OUT / "S4_acceptance.json").write_text(json.dumps(A, indent=1, default=float))
    (OUT / "S4_tables.md").write_text("\n".join(md))
    print("\n".join(md))
    print(json.dumps(A, indent=1, default=float))


if __name__ == "__main__":
    main()
