"""WP1 S5: build results/WP1/S5_tables.md (+ S5_acceptance.json) from S5_odometry.json, S5_dev.json, S5_kitti.json.
No hand-typed numbers. Run from codes_v3/: python -u -W ignore tools/WP1_S5_tables.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir
from WP1_S4_tables import ATT, P, abl_table, delay_table, layer_table

OUT = results_dir("WP1")
REF = ["gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr"]
NEW = ["gps.lidar_z_1", "gps.lidar_z_3", "gps.lidar_z_10", "gps.lidar_resid_1", "gps.lidar_resid_3", "gps.lidar_course", "gps.cusum_lidar"]


def load(n):
    return json.loads((OUT / n).read_text())


def f2(x, d=2):
    return "n/a" if x is None else f"{x:.{d}f}"


def main():
    odo, dev, kit = load("S5_odometry.json"), load("S5_dev.json"), load("S5_kitti.json")
    prim = kit["dev_selection"]["primary_layer_name"]
    md, A = [], {}
    # ---------------- odometry ----------------
    lines = ["**LiDAR odometry vs OXTS ground truth, per drive** (KITTI-style error over path segments of 10/25/50/100 m; 1 s windows with GT speed > 1 m/s)", "",
             "| drive | part | scans | path (m) | translation error | rotation (deg/m) | median 1 s displacement error (m) | median 1 s speed error | ICP inlier fraction | fallback |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d, v in odo["drives"].items():
        lines.append(f"| {d} | {v['part']} | {v['scans']} | {v['path_m']:.0f} | {f2(v['translation_error_pct'])}% | {f2(v['rotation_error_deg_per_m'], 4)} | {f2(v['median_1s_disp_err_m_moving'], 3)} | "
                     f"{f2(v['median_1s_speed_rel_err_pct_moving'])}% | {v['icp_mean_inlier_frac']:.2f} | {P(v['icp_fallback_share'], 1)} |")
    md.append("\n".join(lines) + "\n")
    lines = ["**LiDAR odometry, pooled**", "", "| set | segments | translation error | rotation (deg/m) | median 1 s displacement error (m) | p95 (m) | median 1 s speed error (m/s) | median 1 s yaw error (deg) | sigma coverage (2 sigma) |", "|---|---|---|---|---|---|---|---|---|"]
    for k, lab in (("dev", "16 train+val drives"), ("test", "7 test drives")):
        r = odo[k]
        lines.append(f"| {lab} | {r['segments']} | {f2(r['translation_error_pct'])}% | {f2(r['rotation_error_deg_per_m'], 4)} | {f2(r['median_1s_disp_err_m_moving'], 3)} | {f2(r['p95_1s_disp_err_m_moving'], 3)} | "
                     f"{f2(r['median_1s_speed_err_m_s_moving'], 3)} | {f2(r['median_1s_yaw_err_deg_moving'], 3)} | {P(r['sigma_coverage_2sigma'], 1)} |")
    sg = odo["sigma_model"]
    md.append("\n".join(lines) + f"\n\nSigma model of the published speed: sigma = sqrt({sg['sigma0_m_s']:.4f}^2 + ({sg['rel']:.4f} x speed)^2) m/s, x3 when an ICP fallback happened in the second (fitted on dev only).\n")
    A["C2"] = {"translation_dev_pct": odo["dev"]["translation_error_pct"], "rotation_dev_deg_per_m": odo["dev"]["rotation_error_deg_per_m"],
               "median_1s_disp_err_dev_m": odo["dev"]["median_1s_disp_err_m_moving"], **odo["acceptance"]}
    A["C3"] = {"coverage_test": odo["test"]["sigma_coverage_2sigma"], "coverage_dev": odo["dev"]["sigma_coverage_2sigma"], "met": bool(odo["test"]["sigma_coverage_2sigma"] >= 0.9)}
    # ---------------- dev grid ----------------
    rows = ["| candidate | J | LODO held-out FA | worst drive | " + " | ".join(ATT) + " |", "|" + "---|" * (4 + len(ATT))]
    for c, r in sorted(dev["candidates"].items(), key=lambda kv: -kv[1]["J"]):
        rows.append(f"| {c} | {r['J']:.3f} | {P(r['lodo']['heldout_fa_pooled'], 2)} | {P(r['lodo']['heldout_fa_worst_drive'], 2)} | " + " | ".join(P(r["summary"]["run_detected"][a], 0) for a in ATT) + " |")
    n = dev["nested"]
    md.append("**Development drives (16 train+val), candidates ranked by J (run-level detection, LODO pooled 1% threshold)**\n\n" + "\n".join(rows) + "\n")
    md.append(f"**Nested selection** (choice by J on the 15 other drives, per fold): choices {{{', '.join(f'{k}: {v}' for k, v in n['choice_counts'].items() if v)}}}; held-out FA of the nested procedure {P(n['heldout_fa_pooled'], 2)}; "
              f"J of the nested procedure {n['J']:.3f}; choice on all 16 drives (used on test): {dev['selected_all16']}.\n")
    # ---------------- test ----------------
    for sch, label in (("lodo", "LODO calibration (16 drives) - primary"), ("valonly", "val-only calibration (3 drives)")):
        md.append(layer_table(kit["calibration"][sch]["per_layer"], REF + NEW, f"KITTI test, {label}: run-level detection (row-level in brackets)"))
    for sch in ("lodo", "valonly"):
        md.append(delay_table(kit["calibration"][sch]["per_layer"], ["gps.cusum_dr", prim, "gps.lidar_z_3", "gps.cusum_lidar"], f"Detection delay distribution, {sch}"))
    tr = kit["calibration"]["lodo"]["lodo_transfer"]
    lines = ["**FA transfer on test (clean test runs, 1% budget).**", "", "| layer | val-only calibration | LODO calibration | LODO held-out estimate (dev) | worst dev drive |", "|---|---|---|---|---|"]
    for nme in REF + NEW:
        lines.append(f"| {nme} | {P(kit['calibration']['valonly']['per_layer'][nme]['false_alarm_clean_runs'], 2)} | {P(kit['calibration']['lodo']['per_layer'][nme]['false_alarm_clean_runs'], 2)} | "
                     f"{P(tr[nme]['lodo_heldout_fa_pooled'], 2)} | {P(tr[nme]['lodo_worst_drive_fa'], 2)} |")
    md.append("\n".join(lines) + "\n")
    pl = kit["calibration"]["lodo"]["per_layer"]
    lines = ["**Beat-or-not (LODO, run level): primary L2d vs B2 and vs cusum_dr (S4 best); rule: >= +5 points AND clean-run FA <= reference + 0.5 point.**", "",
             "| attack | vs gps.dr_resid_10 | vs gps.cusum_dr |", "|---|---|---|"]
    verdict = {}
    for a in ATT:
        cells = []
        for ref in ("gps.dr_resid_10", "gps.cusum_dr"):
            diff = pl[prim]["run_detected"][a] - pl[ref]["run_detected"][a]
            fa_ok = pl[prim]["false_alarm_clean_runs"] <= pl[ref]["false_alarm_clean_runs"] + 0.005
            v = "beats" if (diff >= 0.05 and fa_ok) else ("more detection, higher FA" if diff >= 0.05 else "worse" if diff <= -0.05 else "no difference")
            cells.append(f"{100 * diff:+.0f} pts: {v}")
            verdict[f"{ref}|{a}"] = v
        lines.append(f"| {a} | " + " | ".join(cells) + " |")
    md.append("\n".join(lines) + "\n")
    # ---------------- harness ----------------
    for sch, label in (("lodo", "LODO calibration + combiner on the 16 drives"), ("valonly", "val-only (3 drives)")):
        for nm in kit["calibration"][sch]["harness"]:
            md.append(abl_table(kit["calibration"][sch]["harness"][nm], f"Harness {nm}, {label}"))
    # ---------------- acceptance ----------------
    pls = kit["calibration"]["lodo"]["per_layer"]
    A["C4"] = {"fa_clean_runs_test_lodo": pls[prim]["false_alarm_clean_runs"], "fa_clean_runs_test_valonly": kit["calibration"]["valonly"]["per_layer"][prim]["false_alarm_clean_runs"],
               "nested_heldout_fa_dev": n["heldout_fa_pooled"],
               "met": bool(pls[prim]["false_alarm_clean_runs"] <= 0.015 and n["heldout_fa_pooled"] <= 0.015)}
    A["C5"] = {"doppler_spoof_run_lodo": pls[prim]["run_detected"]["doppler_spoof"], "meaconing_run_lodo": pls[prim]["run_detected"]["meaconing"],
               "doppler_spoof_run_valonly": kit["calibration"]["valonly"]["per_layer"][prim]["run_detected"]["doppler_spoof"],
               "meaconing_run_valonly": kit["calibration"]["valonly"]["per_layer"][prim]["run_detected"]["meaconing"],
               "met": bool(pls[prim]["run_detected"]["doppler_spoof"] >= 0.75 and pls[prim]["run_detected"]["meaconing"] >= 0.75),
               "reference_cusum_dr": {a: pls["gps.cusum_dr"]["run_detected"][a] for a in ("doppler_spoof", "meaconing")}}
    A["beat_verdicts_lodo"] = verdict
    for sch in ("lodo", "valonly"):
        H = kit["calibration"][sch]["harness"]
        base, withp = H["S5_stack"]["combined"], H["S5_stack_plus_primary"]["combined"]
        withall = H["S5_stack_plus_all_L2d"]["combined"]
        for key, c in (("primary", withp), ("all_L2d", withall), ("seq", H["S5_stack_plus_seq"]["combined"])):
            rows = {a: c["detection_by_attack"].get(a, 0) - base["detection_by_attack"].get(a, 0) for a in ATT}
            A[f"C6_{sch}_{key}"] = {"auc_base": base["auc"], "auc_with": c["auc"], "auc_gain": c["auc"] - base["auc"], "fa_base": base["false_alarm_rate"], "fa_with": c["false_alarm_rate"],
                                    "det_base": base["detection"], "det_with": c["detection"], "row_level_gain_points": {a: 100 * v for a, v in rows.items()},
                                    "adds": bool((c["auc"] - base["auc"] >= 0.01 or max(rows.values()) >= 0.05) and c["false_alarm_rate"] <= 0.015)}
    (OUT / "S5_acceptance.json").write_text(json.dumps(A, indent=1, default=float))
    (OUT / "S5_tables.md").write_text("\n".join(md))
    print(json.dumps(A, indent=1, default=float))


if __name__ == "__main__":
    main()
