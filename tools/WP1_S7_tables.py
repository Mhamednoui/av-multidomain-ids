"""WP1 S7: build results/WP1/S7_tables.md and S7_acceptance.json from S7_dev.json, S7_kitti.json, S7_external.json. No hand-typed numbers.
Run from codes_v3/: python -u -W ignore tools/WP1_S7_tables.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir
from WP1_S4_tables import ATT, P, abl_table, delay_table, layer_table

OUT = results_dir("WP1")
L3, L4, L4N, L4A = "gps.l3_residual_normal", "gps.l4_c2", "gps.l4_c2_nopos", "gps.l4_c2_all_attacks"
INPUTS = ["gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr", "gps.lidar_z_1", "gps.lidar_z_3", "gps.lidar_z_10", "gps.vel_pos_consistency"]
SHOW = ["gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_ekf", "gps.cusum_dr", "gps.lidar_z_1", L3, L4, L4N, L4A]


def load(n):
    return json.loads((OUT / n).read_text())


def adds(base, new):
    """E4 rule: AUC +0.01 or some attack row-level +5 points, combined FA <= 1.5%."""
    b, n = base["combined"], new["combined"]
    gains = {a: n["detection_by_attack"][a] - b["detection_by_attack"][a] for a in ATT}
    d_auc = n["auc"] - b["auc"]
    fa_ok = n["false_alarm_rate"] <= 0.015
    return {"d_auc": d_auc, "max_gain": max(gains.values()), "gain_by_attack": gains, "fa": n["false_alarm_rate"], "fa_base": b["false_alarm_rate"],
            "fa_ok": bool(fa_ok), "adds": bool(fa_ok and (d_auc >= 0.01 or max(gains.values()) >= 0.05)),
            "adds_unseen_attacks": bool(fa_ok and max(gains["doppler_spoof"], gains["meaconing"]) >= 0.05)}


def main():
    dev, kit, ext = load("S7_dev.json"), load("S7_kitti.json"), load("S7_external.json")
    md, A = [], {}
    # ---------------- dev ----------------
    rows = ["| candidate | J | AUC (row, OOF) | LODO held-out FA | worst drive | " + " | ".join(ATT) + " |", "|" + "---|" * (5 + len(ATT))]
    for grp in (dev["L3"]["candidates"], dev["L4"]):
        for c, r in sorted(grp.items(), key=lambda kv: -kv[1]["J"]):
            rows.append(f"| {c} | {r['J']:.3f} | {r['auc_row']:.3f} | {P(r['lodo_heldout_fa'], 2)} | {P(r['worst_drive_fa'], 2)} | " + " | ".join(P(r["run_detected"][a], 0) for a in ATT) + " |")
    n3 = dev["L3"]["nested"]
    md.append("**Development drives (15 with runs), out-of-fold scores, LODO pooled 1% threshold; run-level detection**\n\n" + "\n".join(rows) +
              f"\n\nL3 nested selection (inner leave-two-out): choices {n3['choice_counts']}; held-out FA {P(n3['heldout_fa_pooled'], 2)}; J {n3['J']:.3f}; run-level " +
              ", ".join(f"{a} {P(n3['summary']['run_detected'][a], 0)}" for a in ATT) + f". Choice for test = {dev['L3']['selected_all_dev']}.\n")
    imp = ["| model | " + " | ".join(dev["L4"]["l4_c2"]["importance_gain_mean_over_folds"].keys()) + " | pos_step share |", "|---" * 10 + "|"]
    for v in ("l4_c2", "l4_nopos", "l4_all"):
        i = dev["L4"][v]["importance_gain_mean_over_folds"]
        keys = list(dev["L4"]["l4_c2"]["importance_gain_mean_over_folds"].keys())
        imp.append(f"| {v} (mean over 15 folds) | " + " | ".join(f"{i[k]:.2f}" if k in i else "-" for k in keys) + f" | {P(dev['L4'][v]['pos_step_share'], 0)} |")
        i = dev["L4"][v]["final_model"]["importance_gain"]
        imp.append(f"| {v} (final model) | " + " | ".join(f"{i[k]:.2f}" if k in i else "-" for k in keys) + f" | {P(sum(i.get(k, 0) for k in ('pos_step_m', 'pos_step_mean5')), 0)} |")
    md.append("**L4 gain importance (normalised to 1)**\n\n" + "\n".join(imp) + "\n")
    pdf = sorted({d for v in dev["L4"].values() for d in v["per_drive_fa"]})
    rows = ["| layer (dev held-out FA per drive, threshold from the other drives) | " + " | ".join(pdf) + " |", "|" + "---|" * (len(pdf) + 1)]
    for nm, r in [("L3 " + dev["L3"]["selected_all_dev"], dev["L3"]["candidates"][dev["L3"]["selected_all_dev"]])] + [(k, v) for k, v in dev["L4"].items()]:
        rows.append(f"| {nm} | " + " | ".join(P(r["per_drive_fa"].get(d), 1) for d in pdf) + " |")
    md.append("\n".join(rows) + "\n")
    # ---------------- test ----------------
    for scheme in ("lodo", "valonly"):
        per = kit["calibration"][scheme]["per_layer"]
        md.append(layer_table(per, SHOW, f"KITTI test, {scheme} calibration: run-level detection (row-level in brackets)"))
        if scheme == "lodo":
            md.append(delay_table(per, [n for n in SHOW if n in per], "Detection delay, lodo calibration"))
    per = kit["calibration"]["lodo"]["per_layer"]
    drs = sorted(per[L3]["per_drive_clean_fa"])
    rows = ["| layer (test clean-run FA per drive, LODO threshold) | " + " | ".join(drs) + " | worst | drives > 3% |", "|" + "---|" * (len(drs) + 3)]
    for n in ["gps.dr_resid_10", "gps.cusum_dr", "gps.lidar_z_1", L3, L4, L4N]:
        rows.append(f"| {n} | " + " | ".join(P(per[n]["per_drive_clean_fa"][d], 1) for d in drs) + f" | {P(per[n]['worst_drive_fa'], 1)} | {per[n]['n_drives_fa_gt_3pct']} |")
    md.append("\n".join(rows) + "\n")
    for scheme in ("lodo", "valonly"):
        for nm, h in kit["calibration"][scheme]["harness"].items():
            md.append(abl_table(h, f"Harness {nm} ({scheme})"))
    # ---------------- verdicts ----------------
    hl, hv = kit["calibration"]["lodo"]["harness"], kit["calibration"]["valonly"]["harness"]
    A["E2"] = {n: {"test_fa_clean_runs_lodo": per[n]["false_alarm_clean_runs"], "test_fa_clean_runs_valonly": kit["calibration"]["valonly"]["per_layer"][n]["false_alarm_clean_runs"]} for n in (L3, L4, L4N)}
    A["E2"][L3]["nested_dev_heldout_fa"] = n3["heldout_fa_pooled"]
    A["E2"][L4]["nested_dev_heldout_fa"] = dev["L4"]["l4_c2"]["lodo_heldout_fa"]
    for k in (L3, L4):
        A["E2"][k]["met"] = bool(A["E2"][k]["test_fa_clean_runs_lodo"] <= 0.015 and A["E2"][k]["nested_dev_heldout_fa"] <= 0.015)
    best_in = max(INPUTS, key=lambda n: per[n]["auc_row_level"])
    A["E3"] = {"l3_auc": per[L3]["auc_row_level"], "best_input": best_in, "best_input_auc": per[best_in]["auc_row_level"],
               "l4_auc": per[L4]["auc_row_level"], "met": bool(per[L3]["auc_row_level"] >= per[best_in]["auc_row_level"] + 0.01)}
    A["E4"] = {}
    for scheme, hh in (("lodo", hl), ("valonly", hv)):
        A["E4"][scheme] = {"L3": adds(hh["S7_stack"], hh["S7_stack_plus_l3"]), "L4": adds(hh["S7_stack"], hh["S7_stack_plus_l4"]),
                           "L3+L4": adds(hh["S7_stack"], hh["S7_stack_plus_l3_l4"]), "L4_nopos": adds(hh["S7_stack"], hh["S7_stack_plus_l4_nopos"]),
                           "L4_all_attacks": adds(hh["S7_stack"], hh["S7_stack_plus_l4_all_attacks"]),
                           "L3+L4_all_attacks": adds(hh["S7_stack"], hh["S7_stack_plus_l3_l4_all_attacks"]),
                           "stack_AUC": hh["S7_stack"]["combined"]["auc"], "stack_FA": hh["S7_stack"]["combined"]["false_alarm_rate"]}
    ctrl = kit["shuffled_label_control"]
    mean_run = lambda n: float(np.mean([per[n]["run_detected"][a] for a in ATT]))
    imp_final = kit["importance_final"]["l4_c2"]
    share = sum(imp_final.get(k, 0) for k in ("pos_step_m", "pos_step_mean5"))
    wd = [dev["L4"]["l4_c2"]["worst_drive_fa"], per[L4]["worst_drive_fa"]]
    A["E5"] = {"shuffled_label": {"test_auc": ctrl["auc_test_rows"], "fa_clean_runs": ctrl["fa_clean_runs"], "row_detection": ctrl["row_detection"],
                                  "met": bool(ctrl["auc_test_rows"] <= 0.55 and max(ctrl["row_detection"].values()) <= ctrl["fa_clean_runs"] + 0.02)},
               "pos_step_share_final": share, "pos_step_share_dev_folds": dev["L4"]["l4_c2"]["pos_step_share"],
               "mean_run_level_l4": mean_run(L4), "mean_run_level_l4_nopos": mean_run(L4N), "mean_run_level_l4_all": mean_run(L4A),
               "red_flag_speed_features": bool(share > 0.5 or abs(mean_run(L4) - mean_run(L4N)) > 0.05),
               "worst_drive_fa_dev_l4": wd[0], "worst_drive_fa_test_l4": wd[1], "drives_gt_3pct_test_l4": per[L4]["n_drives_fa_gt_3pct"],
               "worst_drive_fa_dev_l3": dev["L3"]["candidates"][dev["L3"]["selected_all_dev"]]["worst_drive_fa"], "worst_drive_fa_test_l3": per[L3]["worst_drive_fa"],
               "drives_gt_3pct_test_l3": per[L3]["n_drives_fa_gt_3pct"]}
    A["E7"] = {n: {"doppler_spoof": per[n]["run_detected"]["doppler_spoof"], "meaconing": per[n]["run_detected"]["meaconing"]} for n in ("gps.cusum_dr", L3, L4)}
    A["E7"]["stack_combined_row_level"] = {a: hl["S7_stack"]["combined"]["detection_by_attack"][a] for a in ("doppler_spoof", "meaconing")}
    md.append("**Shuffled-label control of L4 (training and validation labels permuted, seed %d)**: test AUC %.3f, clean-run FA %s, row detection %s.\n" %
              (ctrl["seed"], ctrl["auc_test_rows"], P(ctrl["fa_clean_runs"], 2), ", ".join(f"{a} {P(v, 1)}" for a, v in ctrl["row_detection"].items())))
    # ---------------- external ----------------
    lines = ["**L4 on AV-GPS sessions (KITTI-trained C2 applied unchanged)**", "", "| part | variant | AUC | KITTI threshold: FA / detection | own 1% threshold: FA / detection |", "|---|---|---|---|---|"]
    for part in ("test", "val", "train"):
        for v, r in ext["avgps"][part].items():
            if not isinstance(r, dict) or "auc" not in r:
                continue
            lines.append(f"| {part} | {v} | {r['auc']:.3f} | {P(r['kitti_threshold']['fa'], 1)} / {P(r['kitti_threshold']['detection'], 1)} | {P(r['own_1pct_threshold']['fa'], 1)} / {P(r['own_1pct_threshold']['detection'], 1)} |")
    lines.append("")
    lines.append("AV-GPS threshold taken on the 3 val sessions, applied to test sessions: " + "; ".join(f"{k}: FA {P(v['fa'], 1)}, detection {P(v['detection'], 1)}" for k, v in ext["avgps"]["val_calibrated_on_test"].items()))
    md.append("\n".join(lines) + "\n")
    lines = ["**L4 proxy on the UAV flights (Doppler speed replaces odometry; diagnostic only, features NOT available as trained)**", "",
             "| variant | threshold | benign alarm rate | jamming alarm rate | spoofing: before 117 s | spoofing: from 118 s | first alarm after 118 s |", "|---|---|---|---|---|---|---|"]
    for v in ("l4_c2", "l4_nopos", "l4_all"):
        for tn in ("kitti_threshold", "benign_1pct_threshold"):
            u = ext["uav"][v]
            sp = u["spoofing"][tn]
            lines.append(f"| {v} | {tn} | {P(u['benign'][tn]['alarm_rate'], 1)} | {P(u['jamming'][tn]['alarm_rate'], 1)} | {P(sp['alarm_rate_before_117s'], 1)} | {P(sp['alarm_rate_from_118s'], 1)} | {sp['first_alarm_after_118s']} |")
    md.append("\n".join(lines) + "\n")
    A["E6"] = {"avgps_test": {v: {"auc": r["auc"], "fa_kitti_threshold": r["kitti_threshold"]["fa"], "detection_kitti_threshold": r["kitti_threshold"]["detection"],
                                    "fa_own": r["own_1pct_threshold"]["fa"], "detection_own": r["own_1pct_threshold"]["detection"]}
                               for v, r in ext["avgps"]["test"].items() if isinstance(r, dict) and "auc" in r},
               "uav": "features not available (no odometry); proxy diagnostic in S7_external.json"}
    (OUT / "S7_tables.md").write_text("\n".join(md))
    (OUT / "S7_acceptance.json").write_text(json.dumps(A, indent=1, default=float))
    print("written")


if __name__ == "__main__":
    main()
