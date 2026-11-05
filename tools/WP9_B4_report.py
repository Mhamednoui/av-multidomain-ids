"""WP9 B4: generate results/WP9/B4_tables.md and results/WP9/B4_summary.json (acceptance verdicts) from the result JSONs. No hand-typed numbers.
Also computes the post-hoc DIAGNOSTIC 'equal test-FPR' LiDAR comparison from the stored test scores (labelled; thresholds from the test clean scans, not a result).
Run: python -u -W ignore tools/WP9_B4_report.py
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

import WP9_B4_lidar_lib as LL
from common.metrics import budget_threshold

R = ROOT / "results" / "WP9"
J = lambda n: json.loads((R / n).read_text())


def f(x, d=3):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{d}f}"


def ci(c, d=3):
    return f"[{f(c[0], d)}, {f(c[1], d)}]"


def gps_tables(out, summ):
    t, sel, ctl, v3, proxy = J("B4_gps_test.json"), J("B4_gps_selection.json"), J("B4_gps_controls.json"), J("B4_gps_v3.json"), None
    out.append("## GPS: AV-GPS, Case I (train file 1 sessions, validation file 1 sessions, test file 2; session-cluster bootstrap over 5 test sessions)\n")
    out.append("| feature set | op | F1 [95% CI] | precision | recall | FPR | AUC | macro-F1 | FPR file-3 normals |\n|---|---|---|---|---|---|---|---|---|")
    for name, r in t["case_I"].items():
        for op in ("H", "S"):
            b = r[op]
            out.append(f"| {name} (depth {r['depth']}) | {op} | {f(b['f1'])} {ci(b['ci_session_cluster']['f1'])} | {f(b['precision'])} | {f(b['recall'])} | {f(b['fpr'])} | {f(b['auc'])} | {f(b['macro_f1'])} | {f(b['fpr_file3_normals'])} |")
    c = v3["combined"]
    out.append(f"| v3 GPS layers, combined (label-free, no training) | H | {f(c['f1'])} {ci(c['ci_session_cluster']['f1'])} | {f(c['precision'])} | {f(c['recall'])} | {f(c['fpr'])} | {f(c['auc'])} | {f(c['macro_f1'])} | {f(c['fpr_file3_normals'])} |")
    out.append("\nH = threshold at 1% of validation normal rows; S = validation F1-optimal threshold (literature convention, reported after H). Bar: Abrar et al. cross-dataset F1 0.90-0.965 (other features/split).\n")
    out.append("Per test session alarm rate (F_full S / F_pos H / v3 combined): " + "; ".join(
        f"{k} (label {v['label']}, {v['rows']} rows): {f(v['alarm_rate'], 2)} / {f(t['case_I']['F_pos']['H']['by_session'][k]['alarm_rate'], 2)} / {f(c['by_session'][k]['alarm_rate'], 2)}" for k, v in t["case_I"]["F_full"]["S"]["by_session"].items()) + "\n")
    out.append("v3 layers alone (F1 / recall / FPR / AUC at the 1% validation budget): " + "; ".join(f"{k.replace('gps.', '')} {f(v['f1'], 2)}/{f(v['recall'], 2)}/{f(v['fpr'], 3)}/{f(v['auc'], 2)}" for k, v in v3["layers"].items()) + "\n")
    out.append(f"v3 combined AUC {f(c['auc'])} vs session-label permutation null 5-95% {ci(c['auc_session_label_permutation_null_q05_q95'])} (only 10 distinct labelings of 5 sessions): separates = {c['G3_separates']}.\n")
    out.append("## GPS: Case II (train file 2, 5 sessions, fixed depth/trees from Case I, threshold 0.5; test = 25 file-1 sessions)\n")
    out.append("| feature set | F1 [95% CI] | recall | FPR | AUC |\n|---|---|---|---|---|")
    for name, b in t["case_II"].items():
        out.append(f"| {name} | {f(b['f1'])} {ci(b['ci_session_cluster']['f1'])} | {f(b['recall'])} | {f(b['fpr'])} | {f(b['auc'])} |")
    out.append("\n## GPS: controls (validation, 8 sessions)\n")
    out.append("| feature set | val AUC | row-shuffle AUC (5 seeds, fixed rounds) | pass band 0.42-0.58 | session-perm null q05/q50/q95 | real > q95 | top gain features |\n|---|---|---|---|---|---|---|")
    for name, r in ctl["sets"].items():
        q = r["session_perm_null_auc"]["q05_q50_q95"]
        out.append(f"| {name} | {f(r['real_val_auc'])} | {', '.join(f(x, 2) for x in r['row_shuffle_val_auc'])} | {r['row_shuffle_pass']} | {f(q[0], 2)}/{f(q[1], 2)}/{f(q[2], 2)} | {r['session_perm_pass']} | " + ", ".join(f"{a} {f(b, 2)}" for a, b in r["top_gain_share"][:3]) + " |")
    pr = ctl["proxy_only_vehicle_state"]["val_auc_by_depth"]
    out.append(f"\nProxy-only vehicle-state model (Velocity, Throttle, Steering, Yaw Rate, Roll, Pitch; no GPS field): validation AUC {f(pr['3'])} (depth 3) / {f(pr['5'])} (depth 5): the label is predictable without GPS information.\n")
    # verdicts
    g1 = t["case_I"]["F_full"]["S"]["f1"] >= 0.90
    g2o = any(t["case_I"][k]["S"]["f1"] >= 0.80 and t["case_I"][k]["S"]["fpr"] <= 0.05 for k in ("F_nosat", "F_kin"))
    g2 = any(t["case_I"][k]["S"]["f1"] >= 0.80 and t["case_I"][k]["S"]["fpr"] <= 0.05 for k in ("F_kin_noVS", "F_pos"))
    summ["gps"] = {"G1_F_full_S_f1_ge_0.90": bool(g1), "G1_value": t["case_I"]["F_full"]["S"]["f1"], "G2_original_F_nosat_or_F_kin": bool(g2o), "G2_restated_F_kin_noVS_or_F_pos": bool(g2),
                   "G2_values_S": {k: {"f1": t["case_I"][k]["S"]["f1"], "fpr": t["case_I"][k]["S"]["fpr"]} for k in t["case_I"]}, "G3_v3_separates": c["G3_separates"],
                   "v3_combined": {k: c[k] for k in ("f1", "recall", "fpr", "auc")}}


def lidar_tables(out, summ):
    t, sel = J("B4_lidar_test.json"), J("B4_lidar_selection_static.json")
    d = t["detectors"]
    kinds = LL.KINDS + ["NAIVE", "PHYSICAL", "ALL_ATTACKS"]
    out.append("## LiDAR: KITTI, 7 test drives (drive-cluster bootstrap), per-scan TPR at thresholds transferred from the 3 validation drives\n")
    out.append(f"Test rows {t['n_test_rows']} (clean {t['n_test_clean']}). Supervised = {t['variant']}.\n")
    for op, lab in (("fpr10", "FPR target 10%"), ("fpr1", "FPR target 1%")):
        out.append(f"### {lab}\n")
        out.append("| kind | supervised (static) TPR [CI] | supervised phys-only (cmp_* unseen) | v3.1 stack (LODO) same val threshold | paired sup - v3.1 [CI] |\n|---|---|---|---|---|")
        for k in kinds:
            s, p, v = d["supervised"]["ops"][op]["kinds"][k], d["supervised_phys_only"]["ops"][op]["kinds"][k], d["v31"]["ops"][op]["kinds"][k]
            pr = t["paired_supervised_minus_v31"][op].get(k)
            out.append(f"| {k} | {f(s['tpr'])} {ci(s['ci_drive_boot'], 2)} | {f(p['tpr'])} | {f(v['tpr'])} | " + (f"{f(pr['diff'])} {ci(pr['ci'], 2)}" if pr else "-") + " |")
        fp = lambda n: d[n]["ops"][op]["fpr"]
        out.append(f"| **test FPR (clean scans)** | {f(fp('supervised')['fpr'], 4)} {ci(fp('supervised')['ci_drive_boot'], 3)} | {f(fp('supervised_phys_only')['fpr'], 4)} | {f(fp('v31')['fpr'], 4)} | |\n")
    nat = d["v31"]["native_alarm_1pct"]
    out.append("v3.1 native alarm (design budget 1%): FPR " + f(nat["fpr"], 4) + "; TPR " + "; ".join(f"{k} {f(nat[k]['tpr'], 2)}" for k in LL.KINDS + ["NAIVE", "PHYSICAL"]) + "\n")
    out.append("### Per-kind AUC vs clean test scans\n")
    out.append("| kind | supervised | phys-only | v3.1 |\n|---|---|---|---|")
    for k in LL.KINDS + ["ALL_ATTACKS"]:
        out.append(f"| {k} | {f(d['supervised']['auc'][k])} | {f(d['supervised_phys_only']['auc'][k])} | {f(d['v31']['auc'][k])} |")
    out.append("\n### 4-class decision (Normal, PointDrop, IntensitySpoof, Phantom), prevalence-balanced weighting (each class total weight 1)\n")
    out.append("| detector | op | macro-F1 | recall Normal / PointDrop / IntensitySpoof / Phantom (unweighted) |\n|---|---|---|---|")
    for n in ("supervised", "supervised_phys_only"):
        for op in ("fpr10", "fpr1"):
            q = d[n]["ops"][op]["four_class"]
            out.append(f"| {n} | {op} | {f(q['macro_f1_balanced'])} | " + " / ".join(f(q["unweighted_recall"][c], 2) for c in LL.CLASSES) + " |")
    # diagnostic equal test-FPR
    sc = np.load(R / "scores" / "B4" / "lidar_test.npz", allow_pickle=True)
    mte = pd.DataFrame({"drive": sc["drive"], "i": sc["i"], "attack": sc["attack"]})
    v31 = pd.read_pickle(R / "scores" / "B4" / "lidar_v31_scores.pkl")
    v31 = v31[v31.drive.isin(mte.drive.unique())]
    kv = pd.Series(v31.score.values, index=(v31.drive + "|" + v31.i.astype(str) + "|" + v31.attack).values)
    mk = (mte.drive + "|" + mte.i.astype(str) + "|" + mte.attack).values
    diag = {}
    out.append("\n### Diagnostic only (post hoc): TPR at EQUAL test FPR (threshold taken from the test clean scores of each detector, so not an operating point anyone could set in advance)\n")
    out.append("| kind | sup 10% | v3.1 10% | sup 1% | v3.1 1% |\n|---|---|---|---|---|")
    S = {"sup": sc["supervised"], "v31": kv.loc[mk].to_numpy()}
    clean = (mte.attack == "clean").to_numpy()
    for k in LL.KINDS + ["NAIVE", "PHYSICAL"]:
        kk = {"NAIVE": LL.NAIVE, "PHYSICAL": LL.PHYSICAL}.get(k, [k])
        m = mte.attack.isin(kk).to_numpy()
        row = {}
        for n, s in S.items():
            for fpr in (0.10, 0.01):
                thr = budget_threshold(s[clean], fpr)
                row[f"{n}_{fpr}"] = float((s[m] >= thr).mean())
        diag[k] = row
        out.append(f"| {k} | {f(row['sup_0.1'])} | {f(row['v31_0.1'])} | {f(row['sup_0.01'])} | {f(row['v31_0.01'])} |")
    out.append("\n## LiDAR: validation selection and controls\n")
    cs, cf = J("B4_lidar_controls_static.json"), J("B4_lidar_controls.json")
    fs = J("B4_lidar_selection.json")
    out.append(f"- Full 429-column model (chosen trial {fs['chosen']['trial']}, {fs['chosen']['trees']} trees): validation mean TPR@10% {f(fs['chosen']['val_obj_tpr10_mean'])}, AUC {f(fs['chosen']['val_auc_any'])}; importance RED FLAG (temporal block {f(cf['temporal_gain_share'])}, top {cf['top_gain_share'][0][0]} {f(cf['top_gain_share'][0][1])}); not test-scored.")
    out.append(f"- Static 211-column model (trial {sel['chosen']['trial']}, {sel['chosen']['trees']} trees, depth {sel['chosen']['params']['max_depth']}): validation mean TPR@10% {f(sel['chosen']['val_obj_tpr10_mean'])}, @1% {f(sel['chosen']['val_obj_tpr1_mean'])}, AUC {f(sel['chosen']['val_auc_any'])}; per validation drive AUC " + ", ".join(f"{k} {f(v, 2)}" for k, v in sel["val_auc_per_drive"].items()) + ".")
    out.append(f"- Controls static: row-shuffled labels AUC {', '.join(f(x, 2) for x in cs['row_shuffle_val_auc'])} (pass {cs['row_shuffle_pass']}); within-scan permutation {', '.join(f(x, 2) for x in cs['within_scan_perm_val_auc'])} (pass as written {cs['within_scan_perm_pass']}); top gain " + ", ".join(f"{a} {f(b, 2)}" for a, b in cs["top_gain_share"][:3]) + f"; temporal share {f(cs['temporal_gain_share'])}; red flag {cs['red_flag']}.")
    out.append(f"- Full model within-scan permutation (flawed design, singleton groups kept): {', '.join(f(x, 2) for x in cf['within_scan_perm_val_auc'])}; row-shuffle {', '.join(f(x, 2) for x in cf['row_shuffle_val_auc'])}.\n")
    sup10, sup1 = d["supervised"]["ops"]["fpr10"], d["supervised"]["ops"]["fpr1"]
    summ["lidar"] = {"L1_naive_add_pooled_tpr10": sup10["kinds"]["NAIVE"]["tpr"], "L1_ci": sup10["kinds"]["NAIVE"]["ci_drive_boot"], "L1_met": bool(sup10["kinds"]["NAIVE"]["tpr"] >= 0.85 and sup10["fpr"]["fpr"] <= 0.15),
                     "L2_pointdrop_tpr10": sup10["kinds"]["PointDrop"]["tpr"], "L2_intensity_tpr10": sup10["kinds"]["IntensitySpoof"]["tpr"], "L2_far_phantoms_tpr10": [sup10["kinds"][k]["tpr"] for k in ("ph_replace_far", "ph_budget_far")],
                     "L2_pd_is_ge_0.9": bool(sup10["kinds"]["PointDrop"]["tpr"] >= 0.9 and sup10["kinds"]["IntensitySpoof"]["tpr"] >= 0.9), "L2_far_le_0.25": bool(all(sup10["kinds"][k]["tpr"] <= 0.25 for k in ("ph_replace_far", "ph_budget_far"))),
                     "L4_test_fpr": {n: {op: d[n]["ops"][op]["fpr"]["fpr"] for op in ("fpr10", "fpr1")} for n in d},
                     "L4_within_0.5_1.5x": {n: {op: bool(0.5 * x <= d[n]["ops"][op]["fpr"]["fpr"] <= 1.5 * x) for op, x in (("fpr10", 0.10), ("fpr1", 0.01))} for n in d},
                     "L3_supervised_better_ci_excludes_0": {op: [k for k, v in t["paired_supervised_minus_v31"][op].items() if v["ci"][0] > 0] for op in ("fpr10", "fpr1")},
                     "L3_v31_better_ci_excludes_0": {op: [k for k, v in t["paired_supervised_minus_v31"][op].items() if v["ci"][1] < 0] for op in ("fpr10", "fpr1")},
                     "diag_equal_test_fpr": diag}


def main():
    out = ["# WP9 B4 tables (generated by tools/WP9_B4_report.py from results/WP9/B4_*.json)\n"]
    summ = {}
    gps_tables(out, summ)
    lidar_tables(out, summ)
    (R / "B4_tables.md").write_text("\n".join(out), encoding="utf-8")
    (R / "B4_summary.json").write_text(json.dumps(summ, indent=1))
    print("written", len(out), "blocks")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "diag_equal_test_fpr"} for k, v in summ.items()}, indent=1)[:3500])


if __name__ == "__main__":
    main()
