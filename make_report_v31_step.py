"""make_report_v31_step.py (WP8 S7): writes reports/WP8_S7.md from the saved S7 result files (numbers read from results/WP8/S7/*.json; process facts are fixed text). Called by make_report_v31_docs.write_docs.
Added after the freeze commit (hash in results/WP8/S7/freeze_addendum.json)."""
from make_report_v31 import J, ci, pct


def step_report(V, head, imp_txt, worse):
    R = {r["row"]: r for r in V["rows"]}
    sysr, dom, lc = J("system_h31.json"), J("domains.json"), J("lidar_check.json")
    a, b = sysr["runs"]["v31"], sysr["runs"]["v3"]
    ph = J("system_h31_no0093.json")
    g = dom["gps"]
    lid = dom["lidar"]
    pdw = lid["paired_scan_level_v31_minus_v3"]["PointDrop"]
    K1, K4 = R["M4-1 clean tick FA (K)"], R["M4-4 K mean event detection, single-domain types"]
    r1, r2 = lc["speed_run1_loaded"], lc["speed"]
    pk = sysr["paired_v31_minus_v3"]["K"]["fa_tick"]
    ph_txt = (f"K clean FA {pct(ph['runs']['v31']['K']['fa_tick'], 2)} (v3 {pct(ph['runs']['v3']['K']['fa_tick'], 2)}), events per hour {ph['runs']['v31']['K']['events_per_hour']:.1f} "
              f"(v3 {ph['runs']['v3']['K']['events_per_hour']:.1f})") if ph else "not run"
    n_met = V["n_met"]
    lines = [
        "# WP8 S7: final scoring on the fresh hold-out H31 (milestone M4)", "", "Date: 2026-11-05    Worker: sonnet (high, T3)    Branch v3.1 (tag v3.0 untouched)", "", "## Summary (<= 40 lines)",
        f"- {head}",
        "- Order of work (orchestrator decision): (a) regression R2 (7 checks, all pass: results/WP8/S7/regression.json) and H31 sha256 verification against locks/H31.json (43 items, all_ok) AFTER freeze.json was committed "
        "(8aac3dd); (b) ONE paired scoring of frozen v3 and frozen v3.1 on the same H31 composites; (c) labelled variants (network RC5, blame A3, budget 1.5 %, motion-critical SAFE_STOP); (d) per-domain rows; "
        "(e) M3-style simulation. Every long run wrote its chunks once; no chunk was redone.",
        f"- Verdict: {n_met} of {V['n_rows']} rows MET -> M4 NOT MET. MET: M4-3 (C), M4-4, M4-5, M4-7, M4-13, M4-14, M4-15. NOT MET: M4-1 and M4-2 (K and C), M4-3 (K), M4-6, M4-8, M4-10, M4-11, M4-12. "
        "NOT EVALUATED (counts as not met): M4-9 (D23 half).",
        f"- False alarms did NOT transfer to H31: K clean tick FA {K1['v31']} (v3 {K1['v3']}), C {R['M4-1 clean tick FA (C)']['v31']} (v3 {R['M4-1 clean tick FA (C)']['v3']}); V31_val had 1.9 %. "
        f"Events per clean hour K {a['K']['events_per_hour']:.1f} / C {a['C']['events_per_hour']:.1f} (bound 10; v3 {b['K']['events_per_hour']:.1f} / {b['C']['events_per_hour']:.1f}). "
        f"The S2 gain on V31_val is not reproduced on K FA: paired difference {100 * pk['diff']:+.2f} pts {ci(pk['ci'], 2)}.",
        f"- One H31 drive dominates K: 2011_09_26_drive_0093 alarms on 94 % (GPS), 91 % (cross) and 86 % (LiDAR scans, v3 and v3.1 alike) of its clean ticks; cause not investigated (odometry healthy). "
        f"Without it (labelled post-hoc diagnostic, not a verdict): {ph_txt}: still above the bounds. GPS clean-tick FA on H31 {pct(g['clean_tick_fa_h31'], 2)} vs {pct(g['clean_tick_fa_V31_val'], 2)} on V31_val.",
        f"- Detection: K event detection {K4['v31']} (v3 {K4['v3']}; {K4['evidence']}), held-out {R['M4-5 K held-out (zero-day) types']['v31']} (v3 {R['M4-5 K held-out (zero-day) types']['v3']}); "
        "high partly because the alarm rate is high.",
        f"- LiDAR: PointDrop per scan {pct(pdw['v31'])} vs v3 {pct(pdw['v3'])} (paired {pdw['diff_points']:+.1f} pts [{pdw['ci_points'][0]:+.1f}, {pdw['ci_points'][1]:+.1f}], fresh H31, 13 drives): the in-stack gain is real. "
        f"In the system, per-scan PointDrop events {pct(a['K']['by_type']['lidar_scan|PointDrop']['event_detection'], 0)} (v3 {pct(b['K']['by_type']['lidar_scan|PointDrop']['event_detection'], 0)}), "
        f"3 s episodes {pct(a['K']['by_type']['lidar_episode|ep_PointDrop']['event_detection'], 0)} (as predicted in S2). Clean scan FA {pct(lid['clean']['v31_fa'], 2)} (v3 {pct(lid['clean']['v3_fa'], 2)}; drive 0093 86 %). "
        f"Speed: median {r1['median_ms']:.0f} ms, p99 {r1['p99_ms']:.0f} ms with {r1['other_python_processes_median']:.0f} other python processes (rule 100 / 250 ms; S3b: 73-76 ms on a quieter machine): NOT MET as measured; "
        f"repeat {r2['median_ms']:.0f} ms with {r2['other_python_processes_median']:.0f} other processes. Stream == batch exact. Literal frozen-v3 check: {lc['v3sample']['alarm_disagreements']} alarm disagreements on {lc['v3sample']['scans']} scans.",
        f"- Blame: K gps_can {R['M4-12 KITTI gps_can blame']['v31']} ({R['M4-12 KITTI gps_can blame']['v3']}), the known S6 limit; comma GNSS spoofs {R['M4-13 comma GNSS spoof blame']['v31']} (v3: 100 % undecided): fixed on fresh H31. "
        f"System blame K correct / wrong {R['M4-6 blame equal weight per type (K): correct / wrong']['v31']} (bound 75 / 10).",
        f"- Network (D10 test, re-used): {R['M4-9 network']['v31']}; {R['M4-9 network']['note']}. CAN: Evidence identical to the batch (0 mismatches); {R['M4-10 CAN']['v31']}. V2AIX: {R['M4-11 V2X (V2AIX)']['v31']}.",
        f"- G4 improvement claims (paired CI excludes 0 in the good direction; system rows are PARTIALLY fresh, so they are not fresh-data claims): {imp_txt}. CI excludes 0 in the BAD direction: {worse}. "
        "Claims that stand on fresh data: LiDAR PointDrop at scan level and comma GNSS blame (M4-13). KITTI gps_can blame and the GPS / LiDAR false alarms are not improved.",
        "- Not scored (stated): Civic Chunk_4 (no decoder), D23, Car-Hacking / D11 / OTIDS / normal_run CAN parts, VeReMi 2018, Tampa. Timing was taken on a shared machine; repeats are labelled and the verdict uses the first run.",
        "", "## Acceptance rules", "M4-1..M4-15 and G1-G10 as pre-registered (notes/WP8_v31.md section 2, orchestrator decisions, and 'S7 protocol clarifications' committed before the freeze). Nothing was changed after the result was seen.", "",
        "## What was done",
        "- Runner wrappers: system/runners31.py (CanRunner31, V2XRunner31, LidarRunner31, NetRunner31 F1 / RC5, Blame31Stream A1, Fusion31Runner); stream == batch tests on synthetic / V31_val material (tests/v31/test_s7_runners.py, 6 pass); full suite 557 pass, run_all --check OK.",
        "- Freeze: results/WP8/S7/freeze.json (39 artefact files, 610 code files, commit 8aac3dd) plus the frozen cross recipe (frozen_cross31.pkl) and the budget 1.5 % system (frozen_system31_b15); files added afterwards (pack, can_idle, posthoc, report writers) are hashed in freeze_addendum.json.",
        "- Dry runs on V31_val before the freeze: network, vehicle and V2X sources reproduce the S4 / S2 caches exactly; the simulation reproduces the frozen_system31 in-sample check exactly (K FA 1.80 %, 4.53 events/h, detection 72.9 %).",
        "- H31 scoring tools: tools/WP8_S7_{odom,kitti,comma,lidar,can,net,v2x,veh,blame,sim,domains,v2aix,lidar_check,verify,regress}.py; logs results/WP8/logs/S7_*.log; chunks results/WP8/S7/parts; scores results/WP8/scores/S7 (V2AIX aggregates only).",
        "- Outputs: reports/M4.md, RESULTS_v31.md, results/WP8/S7/{m4_verdict,system_h31,domains,blame,network,can_summary,can_idle_timing,lidar_check,v2aix,exposure}.json, curves/ (ROC and AUC with group-bootstrap CI for GPS, cross, LiDAR, CAN, network, V2X, system K and C).",
        "", "## Problems and open points",
        "- The frozen GPS, cross and LiDAR domains alarm on drive 0093 for the whole drive: a generalisation failure that drives the K false alarms. Not tuned (rule). It needs an investigation step before any further claim about false alarms.",
        "- C clean FA is 6 % without a drive-level anomaly: V2X (about 10 % of clean ticks carry a V2X own alarm on VeReMi test egos), CAN and network dominate; the equal-split 2 % budget does not hold when a domain's tick FA exceeds 1 %.",
        "- Timing rules were measured on a shared machine; an isolated re-measurement is needed to settle M4-8 speed and M4-10 p99 (S3b / S5 numbers on quieter runs met them).",
        "- The D23 half of M4-9 cannot be evaluated (stage cache not on disk). V2AIX Stationary genuine FA is above the 1.5 % bound.", ""]
    return "\n".join(lines)
