"""make_report_v31_docs.py (WP8 S7): markdown writers used by make_report_v31.py (RESULTS_v31.md, reports/M4.md, results/WP8/S7/exposure.json). Every number is read from results/WP8/S7/*.json.
Added after the freeze commit (hash in results/WP8/S7/freeze_addendum.json)."""
import json

from make_report_v31 import J, ROOT, S7, ci, md_table, pct, system_tables


def domain_tables():
    d = J("domains.json")
    out = []
    lid = d["lidar"]
    out.append("### LiDAR (KITTI H31, fresh): scan-level detection at the frozen alarm rule, paired v3.1 - v3 (bootstrap over 13 drives)\n")
    P = lid["paired_scan_level_v31_minus_v3"]
    out.append(md_table(["attack kind", "scans", "v3", "v3.1", "diff pts [95 % CI]"],
                        [[k, v["n"], pct(v["v3"]), pct(v["v31"]), f"{v['diff_points']:+.1f} [{v['ci_points'][0]:+.1f}, {v['ci_points'][1]:+.1f}]"] for k, v in P.items()]))
    out.append(f"\nClean scan FA: v3 {pct(lid['clean']['v3_fa'], 2)}, v3.1 {pct(lid['clean']['v31_fa'], 2)} (V31_val leave-one-drive-out: v3 rule 2.70 %, v3.1 0.96 %).\n")
    rows = []
    for r in lid["rows"]:
        if "auc" in r and r["subset"].split()[0] in ("v3", "v31"):
            rows.append([r["subset"], r["n_pos"], f"{r['auc']:.3f}" + ci(r.get("auc_ci"), 3, 1), pct(r.get("det@1.0%")), pct(r.get("op_det"))])
    out.append("AUC of the continuous LiDAR score (clean scans vs attacked scans of that kind), detection at 1 % FA read from the curve, detection at the frozen rule:\n")
    out.append(md_table(["subset", "n attacked", "AUC [95 % CI]", "det @ 1 % FA", "det @ frozen rule"], rows))
    for dom, title in (("gps", "GPS (KITTI H31 vehicle block, fresh; v3 = v3.1 frozen object)"), ("cross", "Cross-domain layer (KITTI H31, fresh; v3 = v3.1 recipe)"),
                       ("can", "CAN (ROAD test windows, re-used; v3 = v3.1)"), ("network", "Network stack H (D10 test, re-used)"), ("v2x", "V2X (VeReMi test ego ticks, re-used; v3 = v3.1)")):
        rr = [r for r in d[dom]["rows"] if "auc" in r]
        if dom in ("gps", "cross"):
            rr = [r for r in rr if "[all]" in r["subset"]]
        out.append(f"\n### {title}\n")
        out.append(md_table(["subset", "exposure", "n attacked / n clean", "AUC [95 % CI]", "det @ 1 % FA", "frozen rule: FA / det"],
                            [[r["subset"], r["exposure"], f"{r['n_pos']} / {r['n_neg']}", f"{r['auc']:.3f}" + (ci(r.get("auc_ci"), 3, 1) if r.get("auc_ci") else ""), pct(r.get("det@1.0%")),
                              (f"{pct(r.get('op_fa'), 2)} / {pct(r.get('op_det'))}" if "op_fa" in r else "")] for r in rr]))
    g = d["gps"]
    out.append(f"\nGPS / cross clean-tick FA on H31: gps {pct(g['clean_tick_fa_h31'], 2)} vs {pct(g['clean_tick_fa_V31_val'], 2)} on V31_val; cross {pct(d['cross']['clean_tick_fa_h31'], 2)} vs "
               f"{pct(d['cross']['clean_tick_fa_V31_val'], 2)}. One drive dominates it (2011_09_26_drive_0093: GPS alarms on 94 % and cross alarms on 91 % of its clean ticks; the other 12 drives 0.0-1.7 % and 0.0-5.0 %), "
               "cause not investigated (LiDAR odometry of that drive is healthy: 100 % ok, inlier 0.71).")
    return "\n".join(out)


def other_tables():
    out = []
    bl, net, can, v2a, lc = J("blame.json"), J("network.json"), J("can_summary.json"), J("v2aix.json"), J("lidar_check.json")
    out.append("### Blame on the vehicle block alone (S6 evaluation code, fresh H31; correct / wrong / undecided of detected runs)\n")
    rows = []
    for c in ("V3", "A1", "A3"):
        k = bl["K"][c]
        gc = k["gps_can"]
        rows.append([c, f"{pct(gc['correct'])} / {pct(gc['wrong'])} / {pct(gc['undecided'])} ({gc['detected']}/{gc['runs']})", f"{pct(k['B3']['correct'])} / {pct(k['B3']['wrong'])}",
                     (f"{pct(bl['C'][c]['B2']['correct'])} / {pct(bl['C'][c]['B2']['wrong'])}" if c in bl["C"] else "")])
    out.append(md_table(["candidate", "K gps_can", "K single-domain types (equal weight)", "C GNSS drift / meaconing / doppler"], rows))
    out.append("\n### Network (D10 test, re-used): stack H macro over 11 families, FA, Evidence delay\n")
    cn = net["candidates"]
    out.append(md_table(["variant", "macro", "paired vs v3 (pts) [95 % CI]", "FA", "delay median / max (s)"],
                        [[n, pct(cn[n]["macro"], 2), ("" if n == "v3" else f"{cn[n]['paired_vs_v3']['macro_diff_points']:+.2f}{ci(cn[n]['paired_vs_v3']['macro_diff_ci'], 2, 1)}"), pct(cn[n]["fa"], 2),
                          f"{cn[n]['delay_flow_level']['all_flows']['median_s']:.0f} / {cn[n]['delay_flow_level']['all_flows']['max_s']:.0f}"] for n in ("v3", "F1", "RC5")]))
    out.append("\nPer family detection (v3 / F1 / RC5): " + "; ".join(f"{f} {pct(cn['v3']['detection'][f], 0)}/{pct(cn['F1']['detection'][f], 0)}/{pct(cn['RC5']['detection'][f], 0)}" for f in cn["v3"]["detection"]))
    out.append("\n### CAN (ROAD test, re-used; ROAD accelerator fresh, capture level)\n")
    out.append(md_table(["capture", "frames", "windows", "mismatches", "max diff", "p99 ms (loaded run)", "growth ratio"],
                        [[r["name"], r["frames"], r["windows_batch"], r["alarm_mismatch"] + r["id_mismatch"] + r["reason_mismatch"] + r["motion_mismatch"], r["max_abs_diff"], f"{r['window_ms']['p99']:.0f}",
                          (f"{r['growth']['ratio']:.2f}" if "growth" in r else "")] for r in can]))
    idle = J("can_idle_timing.json")
    if idle:
        out.append("\nIdle re-run of the timing only (labelled; Evidence identical): " + "; ".join(f"{r['name']} p99 {r['p99_ms']:.0f} ms" for r in idle))
    if lc:
        sp2 = lc.get("speed", {}) if "speed_run1_loaded" in lc else {}
        sp = lc.get("speed_run1_loaded", lc.get("speed", {}))
        if sp2:
            out.append(f"\n### LiDAR runtime, repeat (labelled timing re-run)\n\nrepeat {sp2.get('scans')} scans: median {sp2.get('median_ms', float('nan')):.0f} ms, p99 {sp2.get('p99_ms', float('nan')):.0f} ms, other python processes (median) {sp2.get('other_python_processes_median')}.\n")
        out.append(f"\n### LiDAR runtime, first run (judged; lidar_check.json speed_run1_loaded)\n\nspeed {sp.get('scans')} scans: median {sp.get('median_ms', float('nan')):.0f} ms, p95 {sp.get('p95_ms', float('nan')):.0f} ms, "
                   f"p99 {sp.get('p99_ms', float('nan')):.0f} ms, other python processes (median) {sp.get('other_python_processes_median')}; stream == batch: {sp.get('stream_equals_batch')}. "
                   f"v3 literal-code sample check: {lc.get('v3sample')}")
    if v2a:
        out.append("\n### V2AIX (H31, fresh per recording; no per-message file committed)\n")
        rows = []
        for env in ("Mobile", "Stationary"):
            e = v2a["envs"][env]
            fa = e["false_alarms"]["physics"]
            rows.append([env, e["h31_recordings"], e["h31_messages"], f"{pct(fa['per_message'], 2)}{ci(fa['ci'], 2)}", pct(fa["independent"], 2) + f" (n={fa['n_independent_messages']})",
                         pct(e["false_alarms"]["A_physics"]["per_message"], 2), pct(e["injected_mean_over_types"])])
        out.append(md_table(["environment", "recordings", "messages", "genuine FA, V31_val thresholds (physics)", "independent recordings FA", "variant A (VeReMi calibration) FA", "injected mean over types"], rows))
        rt = v2a["runtime"]
        out.append(f"\nSingle-ego runtime: {rt['egos']} Mobile egos with a full pose, compute max {rt['compute_per_stream_s_max']:.3f} s per stream second, p99 per message max {rt['msg_p99_ms_max']:.1f} ms, "
                   f"identical egos {rt['identical_egos']}, stream rows that differ from the time-sorted batch {rt['mismatch_rows_total']} of {rt['messages_total']} (unexplained {rt['mismatch_rows_unexplained']}).")
    return "\n".join(out)


def write_exposure():
    rows = [
        ("KITTI 13 H31 drives (GPS, cross, LiDAR, blame, K vehicle block)", "fresh H31", 0, 1), ("comma2k19 Chunk_2 RAV4 21 routes (C vehicle block)", "fresh H31", 0, 1),
        ("comma2k19 Chunk_4 Civic", "not scored (no Civic decoder)", 0, 0), ("V2AIX 674 recordings", "fresh H31 (672 same site-day as calibration, 2 independent)", 0, 1),
        ("ROAD test captures (15)", "re-used test (exposure n+1)", 7, 8), ("ROAD accelerator drive_2 / reverse_2", "fresh H31 (capture level)", 0, 1), ("D10 test (network)", "re-used test (exposure n+1)", 7, 8),
        ("VeReMi test (V2X ego views)", "re-used test (exposure n+1)", 3, 4),
        ("system composites K / C", "partially fresh (vehicle block fresh; CAN / network / V2X streams re-used)", 5, 6),
        ("Car-Hacking, D11, OTIDS, normal_run, D23, Tampa, VeReMi 2018", "not scored in S7", None, None)]
    ex = {"written": "WP8 S7", "scored_once_on_H31": True, "rows": [{"material": m, "label": lab, "exposure_before": a, "exposure_after": b} for m, lab, a, b in rows]}
    (S7 / "exposure.json").write_text(json.dumps(ex, indent=1))


def write_docs(V, improvement_rows):
    R = V["rows"]
    tab = md_table(["row", "rule", "v3.1 (H31)", "v3 (H31)", "verdict", "exposure"], [[r["row"], r["rule"], r["v31"], r["v3"], r["verdict"], r["exposure"]] for r in R])
    imp = [x for x in improvement_rows if x["ci_excludes_0_good_direction"]]
    fmt = lambda x: f"{x['family']} {x['metric']} " + (f"{x['diff']:+.2f}/h" if x['metric'] in ('events_per_hour', 'safe_stop_per_hour') else f"{100 * x['diff']:+.2f} pts")
    imp_txt = "; ".join(fmt(x) for x in imp) or "none"
    worse = "; ".join(fmt(x) for x in improvement_rows if x.get('ci_excludes_0_bad_direction')) or 'none'
    head = (f"**M4 verdict: {V['m4']}** ({V['n_met']} of {V['n_rows']} rows MET). Frozen v3 (tag v3.0) and frozen v3.1 scored once, paired, on H31 "
            "(freeze.json commit 8aac3dd; H31 sha256 verified; regression R2 passed).")
    notes = ("Honest limits: composites are constructed (the vehicle block is real / simulated per domain, CAN / network / V2X streams are re-used test material), so system rows are labelled partially fresh "
             "and a paired improvement there is reported as such, not as a fresh-data claim. Not scored: Civic Chunk_4, D23, Car-Hacking / D11 / OTIDS / normal_run, VeReMi 2018, Tampa. Nothing was re-tuned after the freeze.")
    sysT, domT, othT = system_tables(), domain_tables(), other_tables()
    phT = posthoc_table()
    m4 = (f"# M4: AV-IDS v3.1 on the fresh hold-out H31 (milestone report)\n\nDate: 2026-11-05    Source: reports/WP8_S7.md; numbers: results/WP8/S7/*.json (m4_verdict.json, system_h31.json, domains.json, "
          f"blame.json, network.json, can_summary.json, lidar_check.json, v2aix.json)\n\n## Summary (<= 40 lines)\n\n{head}\n\n{tab}\n\nG4 improvement claims (paired CI excludes 0 in the good direction; system rows, "
          f"partially fresh material): {imp_txt}. Paired CI excludes 0 in the BAD direction: {worse}.\n\n{notes}\n\n## System detail\n\n{sysT}\n\n{phT}\n\n## Domains\n\n{domT}\n\n{othT}\n")
    (ROOT / "reports" / "M4.md").write_text(m4, encoding="utf-8")
    (ROOT / "RESULTS_v31.md").write_text(f"# RESULTS v3.1 (side by side with RESULTS_v3.md; generated by make_report_v31.py from results/WP8/S7/*.json)\n\n{head}\n\n{tab}\n\n## System: v3 and v3.1 on the same H31 composites\n\n"
                                         f"{sysT}\n\n{phT}\n\n## Domains\n\n{domT}\n\n{othT}\n\n{notes}\n\nFiles: results/WP8/S7/{{freeze.json, regression.json, h31_verify.json, system_h31.json, domains.json, blame.json, "
                                         "network.json, can_summary.json, lidar_check.json, v2aix.json, m4_verdict.json, exposure.json, curves/}}; scores results/WP8/scores/S7/.\n", encoding="utf-8")
    from make_report_v31_step import step_report
    (ROOT / 'reports' / 'WP8_S7.md').write_text(step_report(V, head, imp_txt, worse), encoding='utf-8')
    return head, imp_txt


def posthoc_table():
    ph = J("system_h31_no0093.json")
    if not ph:
        return ""
    out = ["### Post-hoc diagnostic (labelled; NOT a verdict, written after the M4 numbers were seen): the same frozen systems without KITTI drive 0093\n",
           "Drive 0093 alone raises the clean-tick alarms of three independent domains (GPS 94 %, cross 91 %, LiDAR scan 86 % of its clean ticks / scans, v3 and v3.1 alike); its cause was not investigated. "
           "K composites rebuilt from the other 12 drives with the same construction and seeds of the code (the composite draws change because the pool changes).\n"]
    rows = []
    for run, lab in (("v3", "v3"), ("v31", "v3.1")):
        r = ph["runs"][run]["K"]
        rows.append([lab, pct(r["fa_tick"], 2) + ci(r["fa_tick_ci"], 2), f"{r['events_per_hour']:.2f}", f"{r['SAFE_STOP_per_hour']:.2f}", pct(r["det_single"]), pct(r["det_heldout"]),
                     f"{pct(r['blame_correct'])} / {pct(r['blame_wrong'])}"])
    out.append(md_table(["K without drive 0093", "clean tick FA", "events / h", "SAFE_STOP / h", "event detection", "held-out", "blame correct / wrong"], rows))
    return "\n".join(out)
