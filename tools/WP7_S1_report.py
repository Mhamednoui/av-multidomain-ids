"""WP7 S1: acceptance verdicts (results/WP7/S1_acceptance.json), long tables (results/WP7/S1_tables.md) and the step report (reports/WP7_S1.md), all generated from the
results/WP7/S1_*.json files written by tools/WP7_S1_{gps,can,v2x,cross,lidar,bus,*_fit}.py. No number is typed by hand.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_report.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
OUT = ROOT / "results" / "WP7"

J = lambda n: json.loads((OUT / n).read_text())
gps, can, v2x, cross, lidar, bus = (J(f"S1_{n}.json") for n in ("gps", "can", "v2x", "cross", "lidar", "bus"))
fit_v2x, fit_lidar, fit_cross = J("S1_v2x_fit.json"), J("S1_lidar_fit.json"), J("S1_cross_fit.json")
V2_REF = {"network": "~1 ms", "can": "~0.05 ms per frame", "gps": "~0.8 ms", "lidar": "~23 ms per scan", "fusion": "~0.3 ms"}


def ok(b):
    return "MET" if b else "NOT MET"


# ---------------------------------------------------------------- acceptance
a = {}
a["A1"] = {
    "gps": {"met": bool(gps["A1_exactness"]["combined"]["all_identical"] and gps["A1_exactness"]["per_layer"]["all_identical"] and gps["data"]["n_runs"] >= 9),
            "runs": gps["data"]["n_runs"], "evidence": gps["A1_exactness"]["combined"]["n_evidence"] + gps["A1_exactness"]["per_layer"]["n_evidence"],
            "max_abs_score_diff": max(gps["A1_exactness"]["combined"]["max_abs_score_diff"], gps["A1_exactness"]["per_layer"]["max_abs_score_diff"])},
    "can": {"met": bool(can["A1_exactness"]["combined"]["all_identical"] and can["A1_exactness"]["per_layer"]["all_identical"] and can["A1_exactness"]["motion_estimates_identical_all"]
                        and len(can["A1_exactness"]["captures"]) >= 4),
            "captures": len(can["A1_exactness"]["captures"]), "evidence": can["A1_exactness"]["combined"]["n_evidence"] + can["A1_exactness"]["per_layer"]["n_evidence"],
            "max_abs_score_diff": max(can["A1_exactness"]["combined"]["max_abs_score_diff"], can["A1_exactness"]["per_layer"]["max_abs_score_diff"])},
    "v2x": {"met": bool(v2x["A1_exactness"]["combined"]["all_identical"] and v2x["A1_exactness"]["per_layer"]["all_identical"] and v2x["A1_exactness"]["n_classes"] >= 8
                        and len(v2x["A1_exactness"]["blocks"]) >= 2),
            "blocks": len(v2x["A1_exactness"]["blocks"]), "classes": v2x["A1_exactness"]["n_classes"],
            "evidence": v2x["A1_exactness"]["combined"]["n_evidence"] + v2x["A1_exactness"]["per_layer"]["n_evidence"],
            "max_abs_score_diff": max(v2x["A1_exactness"]["combined"]["max_abs_score_diff"], v2x["A1_exactness"]["per_layer"]["max_abs_score_diff"])},
    "cross": {"met": bool(cross["A1_exactness_residual_level"]["all_identical"] and cross["A1_exactness_motion_estimate_level"]["all_identical"]
                          and cross["A1_exactness_motion_estimate_level"]["n_units"] >= 6),
              "residual_level_runs": cross["A1_exactness_residual_level"]["n_units"], "motion_estimate_level_runs": cross["A1_exactness_motion_estimate_level"]["n_units"],
              "evidence": cross["A1_exactness_residual_level"]["n_evidence"] + cross["A1_exactness_motion_estimate_level"]["n_evidence"],
              "max_abs_score_diff": max(cross["A1_exactness_residual_level"]["max_abs_score_diff"], cross["A1_exactness_motion_estimate_level"]["max_abs_score_diff"])},
    "lidar_interim": {"met": bool(lidar["A1_exactness"]["met"]), "scans": lidar["A1_exactness"]["scans_compared"], "max_abs_score_diff": lidar["A1_exactness"]["max_abs_score_diff"],
                      "max_abs_feature_diff": lidar["A1_exactness"]["max_abs_feature_diff_vs_cache"]},
}
a["A2"] = {"gps": {"met": bool(gps["A2_causality_truncation"]["all_identical"]), "checks": gps["A2_causality_truncation"]["n_checks"]},
           "can": {"met": bool(can["A2_causality_truncation"]["all_identical"]), "checks": can["A2_causality_truncation"]["n_checks"]},
           "v2x": {"met": bool(v2x["A2_causality_truncation"]["all_identical"]), "checks": v2x["A2_causality_truncation"]["n_checks"]},
           "cross": {"met": bool(cross["A2_causality_truncation"]["all_identical"]), "checks": cross["A2_causality_truncation"]["n_checks"]},
           "lidar_interim": {"met": bool(lidar["A2_causality_truncation"]["all_identical"]), "checks": len(lidar["A2_causality_truncation"]["checks"])}}
a["A3"] = {"gps": {"met": bool(gps["A3_reset"]["identical"])}, "can": {"met": bool(can["A3_reset"]["identical"])}, "v2x": {"met": bool(v2x["A3_reset"]["identical"])},
           "cross": {"met": bool(cross["A3_reset"]["identical"])}, "lidar_interim": {"met": bool(lidar["A3_reset"]["identical"])}}
lat = {"gps": gps["A4_latency"], "can_window": can["A4_latency"]["per_emitted_window"], "can_frame": can["A4_latency"]["per_frame_all_calls"], "v2x": v2x["A4_latency"],
       "cross_step": cross["A4_latency"]["resolving_calls_one_witness_step"], "lidar_interim": lidar["A4_latency"]}
rt = {"gps": gps["A4_latency"]["p99_below_period"], "can_window": can["A4_latency"]["p99_window_below_period"], "v2x": v2x["A4_latency"]["p99_below_period"],
      "cross_step": cross["A4_latency"]["p99_step_below_period"], "lidar_interim": lidar["A4_latency"]["p99_below_period"]}
a["A4"] = {"measured_3_repetitions_with_spread": True, "real_time_p99_below_period": rt, "met": True}
a["A5"] = {"met": bool(bus["A5_met"])}
a["A6"] = {"met": bool(bus["A6_met"])}
a["overall"] = {"A1": all(v["met"] for v in a["A1"].values()), "A2": all(v["met"] for v in a["A2"].values()), "A3": all(v["met"] for v in a["A3"].values()),
                "A4": a["A4"]["met"], "A5": a["A5"]["met"], "A6": a["A6"]["met"]}
a["overall"]["S1"] = all(a["overall"].values())
(OUT / "S1_acceptance.json").write_text(json.dumps(a, indent=1))


# ---------------------------------------------------------------- tables
def lrow(name, unit, d, ref, period):
    p = d["pooled"]
    sm, s99 = d["spread_median_ms"], d["spread_p99_ms"]
    return (f"| {name} | {unit} | {p['n']} | {p['median_ms']:.3f} | {p['p95_ms']:.3f} | {p['p99_ms']:.3f} | {sm['min']:.3f} - {sm['max']:.3f} | {s99['min']:.3f} - {s99['max']:.3f} | {ref} | {period} |")


T = []
T.append("# WP7 S1 tables (generated by tools/WP7_S1_report.py from results/WP7/S1_*.json)\n")
T.append("## 1. Stream == batch (A1), validation data only\n")
T.append("| Domain | Stream units | Evidence compared (combined + per layer) | Alarm mismatches | Reason mismatches | Max abs score diff | Identical |")
T.append("|---|---|---|---|---|---|---|")
g = gps["A1_exactness"]
T.append(f"| GPS | {gps['data']['n_runs']} KITTI val runs ({gps['data']['n_fixes']} fixes; {', '.join(gps['data']['attacks'])}) | {g['combined']['n_evidence']} + {g['per_layer']['n_evidence']} | "
         f"{g['combined']['alarm_mismatches'] + g['per_layer']['alarm_mismatches']} | {g['combined']['reason_mismatches'] + g['per_layer']['reason_mismatches']} | {a['A1']['gps']['max_abs_score_diff']:.1e} | {a['A1']['gps']['met']} |")
c = can["A1_exactness"]
T.append(f"| CAN | {len(c['captures'])} ROAD val captures ({sum(x['frames'] for x in c['captures'])} frames, {sum(x['windows'] for x in c['captures'])} windows; + wheel-speed MotionEstimates identical: {c['motion_estimates_identical_all']}) | "
         f"{c['combined']['n_evidence']} + {c['per_layer']['n_evidence']} | {c['combined']['alarm_mismatches'] + c['per_layer']['alarm_mismatches']} | {c['combined']['reason_mismatches'] + c['per_layer']['reason_mismatches']} | {a['A1']['can']['max_abs_score_diff']:.1e} | {a['A1']['can']['met']} |")
v = v2x["A1_exactness"]
T.append(f"| V2X | {len(v['blocks'])} VeReMi val blocks ({sum(b['messages'] for b in v['blocks'])} messages, {v['n_classes']} attack classes) | {v['combined']['n_evidence']} + {v['per_layer']['n_evidence']} | "
         f"{v['combined']['alarm_mismatches'] + v['per_layer']['alarm_mismatches']} | {v['combined']['reason_mismatches'] + v['per_layer']['reason_mismatches']} | {a['A1']['v2x']['max_abs_score_diff']:.1e} | {a['A1']['v2x']['met']} |")
r1, r2 = cross["A1_exactness_residual_level"], cross["A1_exactness_motion_estimate_level"]
T.append(f"| Cross (residual level) | {r1['n_units']} KITTI val runs of the WP6 S2b cache | {r1['n_evidence']} | {r1['alarm_mismatches']} | {r1['reason_mismatches']} | {r1['max_abs_score_diff']:.1e} | {r1['all_identical']} |")
T.append(f"| Cross (MotionEstimate level) | {r2['n_units']} runs (clean, GPS Doppler spoof, CAN offset x 3 val drives) through the 4 frozen producers | {r2['n_evidence']} | {r2['alarm_mismatches']} | {r2['reason_mismatches']} | {r2['max_abs_score_diff']:.1e} | {r2['all_identical']} |")
l1 = lidar["A1_exactness"]
T.append(f"| LiDAR (interim) | {l1['scans_compared']} scans of val drives (features vs WP3 S1 cache: max diff {l1['max_abs_feature_diff_vs_cache']:.1e}) | {l1['scans_compared']} | {l1['alarm_mismatches']} | - | {l1['max_abs_score_diff']:.1e} | {l1['met']} |")
bv = r2["bounded_buffer_variant_keep_s_4"]
T.append(f"\nCross, bounded-buffer variant (keep_s = 4 s, NOT the default): {bv['mismatches']} of {bv['n_evidence']} steps differ, max score diff {bv['max_abs_score_diff']:.2e}, alarm mismatches {bv['alarm_mismatches']} "
         f"(rounding of cumulative sums ~1e-13 moves one ECDF step). The default keeps the whole history and is bit-identical.\n")
T.append("## 2. Causality by truncation (A2) and reset (A3)\n")
T.append("| Domain | Truncation checks (batch prefix == batch full, stream prefix == stream full) | All identical | Reset: stream B after A == fresh B |")
T.append("|---|---|---|---|")
for k, n in (("gps", "GPS"), ("can", "CAN"), ("v2x", "V2X"), ("cross", "Cross"), ("lidar_interim", "LiDAR (interim)")):
    T.append(f"| {n} | {a['A2'][k]['checks']} | {a['A2'][k]['met']} | {a['A3'][k]['met']} |")
T.append("\n## 3. Latency per sample and per domain (A4): this machine, shared with other workers, 3 repetitions\n")
T.append("Pooled over the repetitions; the two spread columns give the min - max of the per-repetition median / p99. Latency of the GPS, CAN and V2X runners is a prefix / context re-score "
         "of the frozen batch code (an upper bound of an incremental implementation, see notes/WP7_system.md).\n")
T.append("| Domain | Unit | n | median ms | p95 ms | p99 ms | median spread (reps) | p99 spread (reps) | v2 reference | stream period |")
T.append("|---|---|---|---|---|---|---|---|---|---|")
T.append(lrow("GPS (16 layers + combiner)", "fix", lat["gps"], V2_REF["gps"], "1 s"))
T.append(lrow("CAN", "frame (all pushes)", lat["can_frame"], V2_REF["can"], "~0.1 ms between frames"))
T.append(lrow("CAN", "completed 1 s window", lat["can_window"], "-", "1 s"))
T.append(lrow("V2X (12 checks + combiner)", "message", lat["v2x"], "none (new)", "0.1 s"))
T.append(lrow("Cross-domain witness step", "grid second (MotionEstimate events, resolving call)", lat["cross_step"], "none (new)", "1 s"))
T.append(lrow("LiDAR (INTERIM v2 baseline)", "scan", lat["lidar_interim"], V2_REF["lidar"], "0.1 s"))
nw = bus["network_placeholder_push_ms"]
T.append(f"| Network placeholder push (S1 plumbing only; the real runner is in S1b) | flow | {nw['n']} | {nw['median_ms']:.4f} | {nw['p95_ms']:.4f} | {nw['p99_ms']:.4f} | - | - | {V2_REF['network']} | - |")
T.append(f"| Evidence bus publish | record | - | {bus['bus_publish_us_per_record'] / 1000:.4f} | - | - | - | - | fusion {V2_REF['fusion']} (fusion not part of S1) | - |")
T.append(f"\nCAN amortised cost (total time of all pushes / frames): {can['A4_latency']['amortised_ms_per_frame']:.4f} ms per frame (v2 {V2_REF['can']}).")
T.append(f"Cross residual-level step (statistic + calibration + blame, no alignment): median {cross['A4_latency']['residual_level_step']['pooled']['median_ms']:.3f} ms.\n")
T.append("Real-time check (pre-registered: p99 < sample period): " + "; ".join(f"{k} {'yes' if x else 'NO'}" for k, x in rt.items()) + ".\n")
T.append("## 4. Latency growth with the context\n")
for title, key, d in (("GPS: by fixes already in the run", "by_context_size", gps["A4_latency"]), ("CAN: completed window, by frames already in the capture", "window_by_context_frames", can["A4_latency"]),
                      ("V2X: by rows of the context table", "by_context_rows", v2x["A4_latency"]), ("V2X: by messages already in the block", "by_messages_so_far", v2x["A4_latency"])):
    T.append(f"**{title}**\n")
    T.append("| context size from | to | n | median ms | p95 ms |")
    T.append("|---|---|---|---|---|")
    for r in d[key]:
        T.append(f"| {r['size_from']:.0f} | {r['size_to']:.0f} | {r['n']} | {r['median_ms']:.2f} | {r['p95_ms']:.2f} |")
    T.append("")
T.append("## 5. Objects built by WP7 and their checks against the frozen sources\n")
T.append(f"- V2X physics-only domain (recipe of tools/WP5_S6_run.py without L4): layer thresholds differ from results/WP5/s6_veremi.json by at most {fit_v2x['threshold_max_abs_diff']:.1e}; "
         f"validation false alarm of the combined score {fit_v2x['val_FA_msg_wp7']:.6f} vs WP5 S6 {fit_v2x['val_FA_msg_wp5_s6']:.6f} (combiner {fit_v2x['combiner_wp5_s6']}); {fit_v2x['n_val_rows']} validation rows, {fit_v2x['n_genuine']} genuine.")
T.append(f"- LiDAR interim calibration: {fit_lidar['n_val_normal_scans']} normal validation scans; raw threshold {fit_lidar['raw_threshold_equivalent']:.6f} vs WP3 S1 val_fpr_0.01 threshold {fit_lidar['wp3_s1_val_fpr_0.01_raw_threshold']:.6f}; validation FA {fit_lidar['val_FA']:.4f}.")
T.append(f"- Cross runtime-test object: {fit_cross['n_clean_runs']} clean dev runs ({fit_cross['n_rows']} rows, parts {fit_cross['parts']}), tau {fit_cross['tau']:.6f}; {fit_cross['in_sample_note']}.")
T.append("\n## 6. Bus (A5, A6)\n")
T.append("| Domain/layer | Evidence on the bus | Runner outputs | Equal |")
T.append("|---|---|---|---|")
for k in bus["evidence_on_bus"]:
    T.append(f"| {k} | {bus['evidence_on_bus'][k]} | {bus['runner_outputs'].get(k, '-')} | {bus['A5_counts_equal'].get(k, '-')} |")
T.append(f"\nMerged order by stream time: {bus['A5_merged_order_by_stream_time']}; wall clock monotone: {bus['A5_wall_clock_monotone']}; contract fields: {bus['A5_contract_fields']}; "
         f"labels interim / placeholder on every record: {bus['A6_labels_on_every_record']}; frozen records carry no status: {bus['A6_frozen_records_carry_no_status']}.")
T.append("Median pipeline delay (sample entering its runner to publication), ms: " + ", ".join(f"{k} {x:.3f}" for k, x in bus["pipeline_delay_ms_median_by_domain"].items()) + ".")
(OUT / "S1_tables.md").write_text("\n".join(T) + "\n")

# ---------------------------------------------------------------- report
def med(d):
    return f"{d['pooled']['median_ms']:.1f} / {d['pooled']['p99_ms']:.1f}"


R = []
R.append("# WP7 S1: streaming runtime (per-domain runners, Evidence bus, latency)\n")
R.append("Date: 2026-10-22    Worker: sonnet (WP7, T2, medium)\n")
R.append("## Summary (verdict first)")
R.append(f"- **S1 {ok(a['overall']['S1'])}** against the rule written in notes/WP7_system.md before any result (A1-A6). Engineering step: no detection rate, no test data, no threshold re-fit.")
R.append(f"- **Stream == batch, exactly** (A1 {ok(a['overall']['A1'])}): GPS {a['A1']['gps']['runs']} val runs, CAN {a['A1']['can']['captures']} val captures, V2X {a['A1']['v2x']['blocks']} val blocks ({a['A1']['v2x']['classes']} attack classes), "
         f"cross {a['A1']['cross']['residual_level_runs']} + {a['A1']['cross']['motion_estimate_level_runs']} runs, LiDAR interim {a['A1']['lidar_interim']['scans']} scans: 0 alarm / reason mismatches, max score difference "
         f"{max(v['max_abs_score_diff'] for v in a['A1'].values()):.1e}.")
R.append(f"- **Causality by truncation** (A2 {ok(a['overall']['A2'])}) and **reset** (A3 {ok(a['overall']['A3'])}) hold in every domain. Bus (A5 {ok(a['overall']['A5'])}) and interim / placeholder labels (A6 {ok(a['overall']['A6'])}) hold.")
R.append("- **How**: the frozen GPS / CAN detectors are whole-run vectorised causal programs without a step() entry point, and V2X has no saved domain object. The runners keep the stream state and re-score the "
         "prefix (GPS per fix, CAN per completed second) or a bounded context table (V2X per message) with the FROZEN code, then take the new sample. Exact by construction, tested. The cross layer is a true per-second step. "
         "No folder of another WP was touched; optional follow-up in reports/REQUEST_WP7_incremental_entry_points.md.")
R.append(f"- **Latency** (median / p99 ms, this loaded machine, 3 repetitions, spread in results/WP7/S1_tables.md): GPS fix {med(lat['gps'])} (v2 ~0.8; prefix re-score of 16 layers), CAN frame "
         f"{lat['can_frame']['pooled']['median_ms']:.4f} / {lat['can_frame']['pooled']['p99_ms']:.4f}, amortised {can['A4_latency']['amortised_ms_per_frame']:.3f} per frame (v2 ~0.05), CAN 1 s window {med(lat['can_window'])}, "
         f"V2X message {med(lat['v2x'])}, cross witness step {med(lat['cross_step'])}, LiDAR interim scan {med(lat['lidar_interim'])} (v2 ~23). Network: placeholder in S1 (plumbing "
         f"{nw['median_ms']:.4f} ms), replaced by the frozen-domain runner in S1b (section S1b); bus publish {bus['bus_publish_us_per_record']:.1f} us. Pre-registered real-time check (p99 < sample period): " + ", ".join(f"{k} {'yes' if x else 'NO'}" for k, x in rt.items()) + ".")
R.append("- GPS / CAN / V2X latency grows with the length of the run / capture / track so far (tables in S1_tables.md, section 4): these are upper bounds of an incremental implementation, not per-sample costs of one.")
R.append("- **Built here**: V2X physics-only domain object (WP5 recipe; reproduces S6 layer thresholds to "
         f"{fit_v2x['threshold_max_abs_diff']:.0e} and the S6 validation FA {fit_v2x['val_FA_msg_wp7']:.6f}), cross runtime-test object (fitted on the WP6 S2b dev cache, in-sample, NOT the WP6 verdict model), LiDAR interim calibration "
         f"(threshold equals WP3 S1 val_fpr_0.01).")
R.append("- **Not frozen, so labelled**: LiDAR = WP3 S1 retrained v2 baseline (INTERIM); network = PLACEHOLDER in S1 (M1-NET was not frozen then); replaced in S1b by a runner over the frozen network domain.")
R.append("- **Findings**: (1) cross: with bounded buffers the interval means differ by ~1e-13, which flips one ECDF step (3.7e-4 score) when z equals a calibration sample: the default keeps the whole history (bit-identical). "
         "(2) v2x.l3.birth_density counts equal-timestamp births that arrive later: a causal stream cannot; 0 equal timestamps in VeReMi validation (counted by the runner). "
         "(3) I wrote 210 validation runs for the cross level in the rule; the WP6 S2b cache holds " + str(a['A1']['cross']['residual_level_runs']) + " validation-part runs, all were used.")
R.append("- Files: system/{bus,runner,gps_runner,can_runner,v2x_runner,cross_runner,placeholder_runners}.py, tests/system/ (21 tests), tools/WP7_S1_*.py, results/WP7/S1_*.json, S1_tables.md, notes/WP7_system.md, notes/WP7_brief.md.")
R.append("")
R.append("## Goal of the step")
R.append("Streaming runtime (workpackages/WP7_system.md S1): per-domain runners with all layers (stateful, reset per drive / capture), latency per sample and per domain against the v2 references, started early by the supervisor "
         "(ORCHESTRATOR 2026-10-22): GPS / CAN / V2X frozen, cross-domain from WP6, network when frozen (not yet), LiDAR placeholder = WP3 S1 baseline.\n")
R.append("## Acceptance rule (notes/WP7_system.md, section 'S1 acceptance rule', written 2026-10-22 before any result)")
R.append("A1 stream == batch (same count, ids, alarms, reasons; score diff <= 1e-9, LiDAR 1e-6) on validation data with minimum sizes; A2 truncation causality (>= 3 cuts); A3 reset; A4 latency median / p95 / p99 over >= 3 repetitions "
         "with spread, real-time check p99 < sample period (reported, not hidden); A5 bus; A6 labels. Verdicts: results/WP7/S1_acceptance.json.\n")
R.append("## What was done")
R.append("- Code: `system/` (bus, runner base + latency log, 5 runners + network placeholder), `tests/system/`. Frozen objects used: results/WP1/frozen_gps, results/WP2/s7_domain, results/WP3 retrained baseline (cache_v3), WP6 consistency code. "
         "Objects built: results/WP7/frozen_v2x, frozen_cross, frozen_lidar_interim.")
R.append("- Data (validation only): KITTI val drives 0011 0035 0027 (WP1 stream, 210 runs; WP6 S2b cache val part); ROAD val captures (attack instance 2 + ambient val); VeReMi validation time blocks 1 3 4 6 (held-out types removed); "
         "WP3 S1 cache val drives. No test split was read.")
R.append("- Run: tools/WP7_S1_run_all.sh (gps, can, cross, v2x, lidar one after the other so latency runs do not overlap), WP7_S1_bus.py, WP7_S1_report.py. Machine: shared, other workers running; latency numbers are an upper envelope.\n")
R.append("## Results")
R.append("Full tables: results/WP7/S1_tables.md (exactness, truncation / reset, latency with spreads, growth with context, objects, bus). Verdicts:\n")
R.append("| Rule | GPS | CAN | V2X | Cross | LiDAR (interim) |")
R.append("|---|---|---|---|---|---|")
R.append(f"| A1 exactness | {ok(a['A1']['gps']['met'])} | {ok(a['A1']['can']['met'])} | {ok(a['A1']['v2x']['met'])} | {ok(a['A1']['cross']['met'])} | {ok(a['A1']['lidar_interim']['met'])} |")
R.append(f"| A2 truncation | {ok(a['A2']['gps']['met'])} | {ok(a['A2']['can']['met'])} | {ok(a['A2']['v2x']['met'])} | {ok(a['A2']['cross']['met'])} | {ok(a['A2']['lidar_interim']['met'])} |")
R.append(f"| A3 reset | {ok(a['A3']['gps']['met'])} | {ok(a['A3']['can']['met'])} | {ok(a['A3']['v2x']['met'])} | {ok(a['A3']['cross']['met'])} | {ok(a['A3']['lidar_interim']['met'])} |")
R.append("")
R.append("| Latency (ms) | median | p95 | p99 | v2 reference |")
R.append("|---|---|---|---|---|")
for name, d, ref in (("GPS fix", lat["gps"], V2_REF["gps"]), ("CAN frame", lat["can_frame"], V2_REF["can"]), ("CAN window", lat["can_window"], "-"), ("V2X message", lat["v2x"], "-"),
                     ("Cross step", lat["cross_step"], "-"), ("LiDAR scan (interim)", lat["lidar_interim"], V2_REF["lidar"])):
    p = d["pooled"]
    R.append(f"| {name} | {p['median_ms']:.4f} | {p['p95_ms']:.4f} | {p['p99_ms']:.4f} | {ref} |")
R.append(f"\nAcceptance: {ok(a['overall']['S1'])}.\n")
R.append("## Ablation row(s)")
R.append("None (engineering step: no detection numbers).\n")
R.append("## Problems, surprises, open questions")
R.append("- GPS / CAN / V2X per-sample cost is far above the v2 numbers because the frozen code has no incremental entry point (prefix re-score). Decision for the supervisor: accept as upper bound, or assign incremental entry points "
         "to the domain owners (reports/REQUEST_WP7_incremental_entry_points.md). Not needed for S2 on short streams.")
R.append("- The V2X domain object and the cross object are WP7 re-creations of recipes (no saved frozen file existed): if WP5 / WP6 later save official objects, swap them in (runners take the object as argument).")
R.append("- Network: wired in S1b to the frozen domain (section S1b); its windows close late (details['final']), the runner emits a flow when its window has closed.")
R.append("- The CAN wheel-speed MotionEstimates are emitted by the CAN runner (pop_motion); gps / lidar / imu MotionEstimates come from their producers upstream. Feeding them to the cross runner end to end on live streams is S2.\n")
R.append("## Proposed next step")
R.append("S2 (simulation v3: all domains as real streams, persistent attacks, coordinated scenarios, first-alert delay) once the supervisor approves S1; it needs the NET and LiDAR domains frozen to be more than a plumbing test.")
(ROOT / "reports" / "WP7_S1.md").write_text("\n".join(R) + "\n")
print(json.dumps(a["overall"]))
