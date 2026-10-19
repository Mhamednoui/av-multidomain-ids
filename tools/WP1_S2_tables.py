"""WP1 S2: turn results/WP1/S2_*.json into markdown tables (results/WP1/S2_tables.md) for the step report.
Run from codes_v3/: python tools/WP1_S2_tables.py"""
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "results" / "WP1"
ATT = ["drift", "accel_drift", "jump", "freeze", "doppler_spoof", "meaconing"]


def p(x, d=1):
    return "-" if x is None else f"{100 * x:.{d}f}%"


def main():
    k = json.loads((R / "S2_kitti.json").read_text())
    a = json.loads((R / "S2_avgps.json").read_text())
    u = json.loads((R / "S2_uav.json").read_text())
    L = []
    L.append("### KITTI: per layer at its operating point, test (run-level detection = fraction of attack runs with >= 1 alarm after onset; row-level in brackets)\n")
    L.append("| layer | operating point | FA clean runs | FA all normal rows | " + " | ".join(ATT) + " |")
    L.append("|" + "---|" * (4 + len(ATT)))
    rows = list(k["per_layer"].items()) + [("UNION physical kinematic (5 rules)", k["union_physical_kinematic"]),
                                           ("B2 OR physical union", k["b2_or_physical_union"]),
                                           ("B2 OR every L1 rule at its operating point", k["b2_or_every_l1_rule_each_at_its_operating_point"])]
    for n, v in rows:
        op = v.get("operating_point", "")
        L.append(f"| {n} | {op} | {p(v['false_alarm_clean_runs'], 2)} | {p(v['false_alarm_all_normal_rows'], 2)} | " +
                 " | ".join(f"{p(v['run_detected'][x], 0)} ({p(v['detection_by_attack'][x], 1)})" for x in ATT) + " |")
    L.append("\nMedian delay (s) of the detected runs: " + "; ".join(
        f"{n}: " + ", ".join(f"{x} {v['median_delay_s'][x]:.0f}" for x in ATT if v['median_delay_s'][x] is not None)
        for n, v in rows[:6] + rows[6:7]))
    L.append("\n### KITTI: margin to the physical limits (raw ratio, 1.0 = limit)\n")
    L.append("| rule | max on val normal | max on test clean runs | p99 on test clean runs |\n|---|---|---|---|")
    for c, m in k["margin_to_limit"].items():
        L.append(f"| {c} | {m['max_val_normal']:.3f} | {m['max_test_clean_runs']:.3f} | {m['p99_test_clean_runs']:.3f} |")
    L.append("\n### KITTI: harness ablation (budget 1% on validation normal rows; test, one pass)\n")
    for nm, h in k["harness"].items():
        L.append(f"**{nm}** (combiner: {h['combined']['method']})\n")
        L.append((R / f"{nm}.md").read_text().split("\n\n", 1)[1])
    L.append("\n### AV-GPS (test, physical-limit alarms; thresholds not fitted)\n")
    L.append("| rule | artefact? | FA normal rows | normal rows flagged | detection attack rows | AUC (calibrated score) |\n|---|---|---|---|---|---|")
    for n, v in a["per_rule"].items():
        pa = v["physical_alarm"]
        L.append(f"| {n} | {'YES' if v['artefact'] else 'no'} | {p(pa['false_alarm_normal_rows'], 2)} | {pa['normal_rows_flagged']} | {p(pa['detection_attack_rows'], 1)} | {v['auc_calibrated_score']:.3f} |")
    un = a["union_physical_kinematic"]
    L.append(f"\nUnion of the five kinematic rules: FA {p(un['false_alarm_normal_rows'], 2)} ({un['normal_rows_flagged']} of {un['normal_rows']} normal rows), detection {p(un['detection_attack_rows'], 1)}. "
             f"Attack rows with a step over 100 km: {p(a['test_attack_rows_with_step_over_100km'], 2)}, normal rows: {p(a['test_normal_rows_with_step_over_100km'], 2)}.")
    L.append("\n### UAV live flights (alarm counts; spoofing flight: first spoofed fix 118.0 s)\n")
    L.append("| rule | operating point | raw threshold | benign alarms | spoof alarms before 117 s | spoof alarms from 118 s | first spoof alarm (s) | jamming alarms |\n|---|---|---|---|---|---|---|---|")
    for n, v in u["rules"].items():
        s = v["flights"]["spoofing"]
        L.append(f"| {n} | {v['operating_point']} | {'-' if v['raw_threshold'] is None else format(v['raw_threshold'], '.3g')} | {v['flights']['benign']['alarms']} / 248 | "
                 f"{s['alarms_before_117s']} / 118 | {s['alarms_from_118s']} / {s['fixes_from_118s']} | {s['first_alarm_after_onset_s']} | {v['flights']['jamming']['alarms']} / 224 |")
    us = u["union"]["spoofing"]
    L.append(f"\nUnion of the UAV rules, spoofing flight: alarms before 117 s {us['alarms_before_117s']} (FA {p(us['false_alarm_before_117s'], 2)}); "
             f"first alarm {us['first_alarm_after_onset_s']} s (delay {us['delay_from_first_spoofed_fix_s']:.3f} s); fixes flagged from 118 s: {p(us['fraction_of_fixes_from_118s_flagged'], 1)}; "
             f"rules firing within 2 s: {', '.join(us['rules_firing_within_2s'])}. Benign flight: {u['union']['benign']['alarms']} / 248 alarms (in-sample for the calibrated rules). "
             f"Jamming flight (no onset label): {u['union']['jamming']['alarms']} / 224 alarms, times {u['union']['jamming']['alarm_times_s']}.")
    (R / "S2_tables.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
