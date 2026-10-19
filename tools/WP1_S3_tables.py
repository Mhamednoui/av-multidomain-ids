"""WP1 S3: markdown tables for the report, generated from results/WP1/S3_*.json -> results/WP1/S3_tables.md."""
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "results" / "WP1"
ATT = ["drift", "accel_drift", "jump", "freeze", "doppler_spoof", "meaconing"]
pc = lambda x: "-" if x is None else f"{100 * x:.0f}%"
pf = lambda x: "-" if x is None else f"{100 * x:.2f}%"


def main():
    k = json.loads((R / "S3_kitti.json").read_text())
    iso = json.loads((R / "S3_isofa.json").read_text())
    av = json.loads((R / "S3_avgps.json").read_text())
    uav = json.loads((R / "S3_uav.json").read_text())
    tu = json.loads((R / "S3_tuning.json").read_text())
    o = []
    o.append("### Tuning (TRAIN / VAL only)\n")
    o.append(f"KITTI receiver error (train clean, reported - true): phi {tu['kitti_gm_estimate_train']['phi']:.3f}, sigma {tu['kitti_gm_estimate_train']['sigma']:.3f} m; q_acc = {tu['kitti_q_acc']} m/s^2 (grid on train clean, mean NIS / dim closest to 1); gate level (val) {tu['kitti_gate_level']}; primary variant chosen on val: **{tu['kitti_primary_variant']}**.\n")
    o.append("| gate level (val) | mean run-level detection over 6 attacks at val 1% budget |\n|---|---|")
    for g, v in tu["kitti_gate_val"].items():
        o.append(f"| {g} | {v['mean_over_attacks']:.3f} |")
    o.append("\n### Filter consistency (NIS)\n")
    o.append("| data | rows | mean NIS | mean dim | ratio | fraction above chi2 95% |\n|---|---|---|---|---|---|")
    rows = [("KITTI train clean (tuned on)", tu["kitti_consistency_train_clean"]), ("KITTI val clean", tu["kitti_consistency_val_clean"]),
            ("KITTI test clean runs", k["consistency_test_clean_runs"]["ungated"]),
            ("AV-GPS train normal (tuned on)", av["tuning_train"]), ("AV-GPS val normal", av["consistency_val"]),
            ("UAV benign flight (tuned on)", uav["consistency_benign"])]
    for n, c in rows:
        o.append(f"| {n} | {c['rows']} | {c['mean_nis']:.2f} | {c['mean_dim']:.2f} | {c['ratio']:.2f} | {100 * c['frac_above_chi2_95']:.1f}% |")
    o.append("\n### KITTI test: run-level detection (row-level in brackets), val-calibrated 1% operating point\n")
    o.append("| layer | FA clean runs | FA all normal rows | " + " | ".join(ATT) + " | drift<0.5 m/s within 30 s |\n|" + "---|" * (len(ATT) + 4))
    for n, d in k["per_layer"].items():
        o.append(f"| {n} | {pf(d['false_alarm_clean_runs'])} | {pf(d['false_alarm_all_normal_rows'])} | " +
                 " | ".join(f"{pc(d['run_detected'][a])} ({100 * d['detection_by_attack'][a]:.1f}%)" for a in ATT) +
                 f" | {pc(d['slow_drift_lt_0.5_within_30s']['detected_within_30s'])} of {d['slow_drift_lt_0.5_within_30s']['runs']} |")
    o.append("\nMedian detection delay (s): " + "; ".join(f"{n}: " + ", ".join(f"{a} {v}" for a, v in d["median_delay_s"].items() if v is not None) for n, d in k["per_layer"].items()))
    o.append("\n### KITTI test DIAGNOSTIC, equal false alarms (oracle threshold on the test clean runs, 1%; not an operating point)\n")
    o.append("| layer | FA clean runs | " + " | ".join(ATT) + " | drift<0.5 within 30 s |\n|" + "---|" * (len(ATT) + 3))
    for n, d in iso.items():
        o.append(f"| {n} | {pf(d['false_alarm_clean_runs'])} | " + " | ".join(pc(d["run_detected"][a]) for a in ATT) +
                 f" | {pc(d['slow_drift_lt_0.5_within_30s']['detected_within_30s'])} |")
    o.append("\n### Beat-or-not vs B2 (rule A4, as written: >= 5 points higher run-level detection AND clean-run FA <= B2 + 0.5 point)\n")
    o.append("| attack | EKF - B2 (run-level, points) | verdict by rule A4 |\n|---|---|---|")
    for a, v in k["verdict_ekf_ungated_vs_b2"].items():
        o.append(f"| {a} | {100 * v['ekf_minus_b2_run_level']:+.0f} | {v['verdict'] if (v['ekf_minus_b2_run_level'] < 0.05 or k['fa_condition_met']) else 'more detection but at higher FA than B2: rule A4 not satisfied (see equal-FA table)'} |")
    o.append(f"\nFA condition (EKF clean-run FA <= B2 + 0.5 point) met: {k['fa_condition_met']}.\n")
    o.append("### Absorption: position-estimate error vs truth at onset +10 s / +30 s (median over test attack runs), ungated and gated\n")
    o.append("| attack | reported error +10 s | estimate error ungated | estimate error gated | reported +30 s | estimate ungated | estimate gated | absorbed fraction +30 s ungated / gated (runs with reported error >= 5 m) | fraction of runs in hold +30 s (gated) |\n|---|---|---|---|---|---|---|---|---|")
    for a in ATT:
        u, g = k["absorption"]["ungated"][a], k["absorption"]["gated"][a]
        f = lambda x: "-" if x is None else f"{x:.2f}"
        fm = lambda x: "-" if x is None else f"{x:.1f}"
        o.append(f"| {a} | {fm(u['+10s']['median_reported_error_m'])} | {fm(u['+10s']['median_estimate_error_m'])} | {fm(g['+10s']['median_estimate_error_m'])} | "
                 f"{fm(u['+30s']['median_reported_error_m'])} | {fm(u['+30s']['median_estimate_error_m'])} | {fm(g['+30s']['median_estimate_error_m'])} | "
                 f"{f(u['+30s']['median_absorbed_fraction_est_over_rep'])} / {f(g['+30s']['median_absorbed_fraction_est_over_rep'])} (n={u['+30s']['runs_with_reported_error_ge_5m']}) | {f(g['+30s']['fraction_in_hold'])} |")
    o.append(f"\nClean runs: median estimate error {k['absorption']['ungated']['clean_runs_median_estimate_error_m']:.2f} m vs reported {k['absorption']['ungated']['clean_runs_median_reported_error_m']:.2f} m (ungated); gated {k['absorption']['gated']['clean_runs_median_estimate_error_m']:.2f} m.\n")
    o.append("### KITTI harness ablation (val 1% budget, test one pass; row-level)\n")
    for nm in ("S3_kitti_all", "S3_kitti_b2_ekf", "S3_kitti_all_gated", "S3_kitti_ekf_pair"):
        o.append(f"**{nm}**\n\n" + (R / f"{nm}.md").read_text().split("\n", 1)[1])
    o.append("### AV-GPS test (position + speed + heading only)\n")
    o.append("| variant | FA normal rows | detection attack rows | AUC | attack rows flagged / with step > 100 km | detection excluding step > 100 km rows |\n|---|---|---|---|---|---|")
    for n in ("ungated", "gated"):
        d = av[n]
        o.append(f"| {n} | {pf(d['false_alarm_normal_rows'])} ({d['normal_rows_flagged']}/{d['normal_rows']}) | {pc(d['detection_attack_rows'])} | {d['auc']:.3f} | {d['attack_rows_flagged']} / {d['attack_rows_with_step_over_100km']} | {pc(d['detection_attack_rows_excluding_step_over_100km'])} ({d['attack_rows_excluding_step_over_100km']} rows) |")
    o.append("\n### UAV (noise and threshold from the benign flight)\n")
    o.append("| variant | benign FA (in-sample) | spoofing: alarms before 117 s | first alarm >= 118 s | fraction of fixes 118-138 s flagged | fraction of fixes in hold from 118 s | jamming flight alarms |\n|---|---|---|---|---|---|---|")
    for n in ("ungated", "gated"):
        f = uav[n]["flights"]
        s = f["spoofing"]
        o.append(f"| {n} | {pf(f['benign']['false_alarm_in_sample'])} | {s['alarms_before_117s']}/{s['fixes_before_117s']} ({pf(s['false_alarm_before_117s'])}) | {s['first_alarm_after_onset_s']:.3f} s | {pc(s['fraction_118_to_138s_flagged'])} | {pc(s['hold_fraction_from_118s'])} | {f['jamming']['alarms']}/{f['jamming']['fixes']} |")
    (R / "S3_tables.md").write_text("\n".join(o) + "\n")


if __name__ == "__main__":
    main()
