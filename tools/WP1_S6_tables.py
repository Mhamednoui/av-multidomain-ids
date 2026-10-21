"""WP1 S6: build results/WP1/S6_tables.md and S6_acceptance.json from S6_dev.json and S6_kitti.json (no hand-typed numbers).
Run from codes_v3/: python -u -W ignore tools/WP1_S6_tables.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir
from WP1_S4_tables import ATT, P, abl_table, delay_table, layer_table

OUT = results_dir("WP1")
REF = ["gps.dr_resid_10", "gps.cusum_dr", "gps.lidar_z_1"]
MAPS = ["gps.map_dist", "gps.map_heading", "gps.map_comb"]


def load(n):
    return json.loads((OUT / n).read_text())


def main():
    dev, kit = load("S6_dev.json"), load("S6_kitti.json")
    prim = "gps." + kit["dev_selection"]["primary_L2e"]
    md, A = [], {}
    d2 = dev["D2"]
    md.append(f"**Map and sanity (16 dev drives, clean rows).** drivable classes: {', '.join(dev['classes'])}; {dev['n_segments']} segments. "
              f"Fixes within 10 m of a drivable segment {P(d2['frac_within_10m'], 1)}; distance median {d2['median_dist_m']:.2f} m, p95 {d2['p95']:.2f} m, p99 {d2['p99']:.2f} m; "
              f"heading deviation (speed >= 3 m/s) median {d2['median_heading_dev_deg']:.1f} deg, p95 {d2['p95_heading_deg']:.1f}, p99 {d2['p99_heading_deg']:.1f}.\n")
    A["D2"] = {**d2}
    rows = ["| candidate | J | LODO held-out FA | worst drive | " + " | ".join(ATT) + " |", "|" + "---|" * (4 + len(ATT))]
    for c, r in sorted(dev["candidates"].items(), key=lambda kv: -kv[1]["J"]):
        rows.append(f"| {c} | {r['J']:.3f} | {P(r['lodo']['heldout_fa_pooled'], 2)} | {P(r['lodo']['heldout_fa_worst_drive'], 2)} | " + " | ".join(P(r["summary"]["run_detected"][a], 0) for a in ATT) + " |")
    n = dev["nested"]
    md.append("**Development drives (16), run-level detection at the LODO pooled 1% threshold**\n\n" + "\n".join(rows) + "\n")
    md.append(f"**Nested selection**: choices {n['choice_counts']}; held-out FA of the nested procedure {P(n['heldout_fa_pooled'], 2)}, J {n['J']:.3f}; choice on all 16 drives (used on test): {dev['selected_all16']}.\n")
    rows = ["| map variant (dev, diagnostic, not selectable) | segments | clean median dist (m) | J map_dist | J map_heading | J map_comb |", "|---|---|---|---|---|---|"]
    rows.append(f"| drivable (used) | {dev['n_segments']} | {d2['median_dist_m']:.2f} | " + " | ".join(f"{dev['candidates'][c.split('.')[1]]['J']:.3f}" for c in MAPS) + " |")
    for k, v in dev["diagnostic_maps"].items():
        rows.append(f"| {k} | {v['n_segments']} | {v['median_dist_clean']:.2f} | " + " | ".join(f"{v['J'][c.split('.')[1]]:.3f}" for c in MAPS) + " |")
    md.append("\n".join(rows) + "\n")
    for sch, label in (("lodo", "LODO calibration (16 drives) - primary"), ("valonly", "val-only calibration (3 drives)")):
        md.append(layer_table(kit["calibration"][sch]["per_layer"], REF + MAPS, f"KITTI test, {label}: run-level detection (row-level in brackets)"))
    for sch in ("lodo", "valonly"):
        md.append(delay_table(kit["calibration"][sch]["per_layer"], [prim, "gps.lidar_z_1", "gps.cusum_dr"], f"Detection delay distribution, {sch}"))
    orf = kit["on_road_fraction_test_within_dev_clean_p99"]
    md.append(f"**Spoofed track on-road fraction** (attacked rows of the 7 test drives whose reported fix is within {kit['clean_p99_m']:.2f} m = clean 99th percentile of a drivable segment; "
              "a map check cannot flag these rows whatever the threshold): " + ", ".join(f"{a} {P(orf[a], 0)}" for a in ATT) + "\n")
    tr = kit["calibration"]["lodo"]["lodo_transfer"]
    lines = ["**FA transfer on test (clean test runs, 1% budget).**", "", "| layer | val-only calibration | LODO calibration | LODO held-out estimate (dev) | worst dev drive |", "|---|---|---|---|---|"]
    for nme in ["gps.dr_resid_10", "gps.cusum_dr", "gps.lidar_z_1"] + MAPS:
        lines.append(f"| {nme} | {P(kit['calibration']['valonly']['per_layer'][nme]['false_alarm_clean_runs'], 2)} | {P(kit['calibration']['lodo']['per_layer'][nme]['false_alarm_clean_runs'], 2)} | "
                     f"{P(tr[nme]['lodo_heldout_fa_pooled'], 2)} | {P(tr[nme]['lodo_worst_drive_fa'], 2)} |")
    md.append("\n".join(lines) + "\n")
    for sch, label in (("lodo", "LODO calibration"), ("valonly", "val-only")):
        for nm in kit["calibration"][sch]["harness"]:
            md.append(abl_table(kit["calibration"][sch]["harness"][nm], f"Harness {nm}, {label}"))
    pl = kit["calibration"]["lodo"]["per_layer"]
    A["D3"] = {"fa_clean_runs_test_lodo": pl[prim]["false_alarm_clean_runs"], "fa_clean_runs_test_valonly": kit["calibration"]["valonly"]["per_layer"][prim]["false_alarm_clean_runs"],
               "nested_heldout_fa_dev": n["heldout_fa_pooled"], "lodo_heldout_fa_dev_primary": tr[prim]["lodo_heldout_fa_pooled"],
               "met": bool(pl[prim]["false_alarm_clean_runs"] <= 0.015 and n["heldout_fa_pooled"] <= 0.015)}
    A["D5_run_level_lodo"] = {a: pl[prim]["run_detected"][a] for a in ATT}
    A["D5_row_level_lodo"] = {a: pl[prim]["row_detection"][a] for a in ATT}
    A["D5_on_road_fraction"] = orf
    for sch in ("lodo", "valonly"):
        H = kit["calibration"][sch]["harness"]
        for key, (b, w) in {"s5stack+primary": ("S6_s5stack", "S6_s5stack_plus_map"), "s5stack+all3": ("S6_s5stack", "S6_s5stack_plus_map_all3"),
                            "base+primary": ("S6_base", "S6_base_plus_map"), "allL2d+primary": ("S6_l2d_all_stack", "S6_l2d_all_stack_plus_map")}.items():
            bc, wc = H[b]["combined"], H[w]["combined"]
            rows = {a: wc["detection_by_attack"].get(a, 0) - bc["detection_by_attack"].get(a, 0) for a in ATT}
            A[f"D4_{sch}_{key}"] = {"auc_base": bc["auc"], "auc_with": wc["auc"], "auc_gain": wc["auc"] - bc["auc"], "fa_base": bc["false_alarm_rate"], "fa_with": wc["false_alarm_rate"],
                                    "det_base": bc["detection"], "det_with": wc["detection"], "row_level_gain_points": {a: 100 * v for a, v in rows.items()},
                                    "adds": bool((wc["auc"] - bc["auc"] >= 0.01 or max(rows.values()) >= 0.05) and wc["false_alarm_rate"] <= 0.015)}
    (OUT / "S6_acceptance.json").write_text(json.dumps(A, indent=1, default=float))
    (OUT / "S6_tables.md").write_text("\n".join(md))
    print(json.dumps(A, indent=1, default=float))


if __name__ == "__main__":
    main()
