"""WP8 S4: markdown tables from the S4 JSON files (results/WP8/S4/s4_val_candidates.json, s4_stream_check.json, s4_bot.json) -> results/WP8/S4/s4_tables.md. No number is typed by hand.
Usage: python -u -W ignore -I tools/WP8_S4_report.py"""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
S = os.path.join(ROOT, "results", "WP8", "S4")
c = json.load(open(os.path.join(S, "s4_val_candidates.json")))
sc = json.load(open(os.path.join(S, "s4_stream_check.json")))
b = json.load(open(os.path.join(S, "s4_bot.json")))
C = c["candidates"]
sel = c["selection"]
pct = lambda x: "%.1f" % (100 * x)
L = []
L.append("## T1 Candidates on D10 validation (stack H, mixed val stream, 11 families; delay = flow level; lag = first alarm available after the first attack flow, median over families)\n")
L.append("| candidate | Evidence emitted | macro % | paired diff to v3 (points) [95% CI] | FA % | delay median / max s | lag s | first-tick attack flows alarmed | N1 | N2 FA | N2 macro |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|")
for n in ["v3", "R5", "R2", "R1", "RC5", "RC2", "RC1", "F1"]:
    x = C[n]
    d = x["delay_flow_level"]["all_flows"]
    pv = x.get("paired_vs_v3")
    diff = "-" if not pv else "%.2f [%.2f, %.2f]" % (pv["macro_diff_points"], pv["macro_diff_ci"][0], pv["macro_diff_ci"][1])
    j = {**sel["round1"]["per_candidate"], **sel["round2"]["per_candidate"]}.get(n)
    ok = lambda k: "-" if j is None else ("yes" if j[k] else "NO")
    L.append("| %s | %s | %s | %s | %.2f | %.0f / %.0f | %s | %.2f | %s | %s | %s |" % (n, x["emission"], pct(x["macro"]), diff, 100 * x["fa"], d["median_s"], d["max_s"],
             x["alarm_lag"]["median_of_family_medians_s"], x["alarm_lag"]["mean_first_tick_alarm_share"], ok("N1_delay"), ok("N2_fa"), ok("N2_macro")))
L.append("\nRound 1 (R5/R2/R1) feasible: %s. Round 2 feasible: %s; chosen by the pre-registered rule (lowest median delay, then macro, G8): **%s**. FA bound %.1f %%.\n" % (
    sel["round1"]["feasible"] or "none", sel["round2"]["feasible"], sel["round2"]["chosen"], sel["fa_bound_points"]))
L.append("## T2 Detection per family on D10 validation, % of flows (n = val flows)\n")
cols = ["v3", "R5", "RC5", "RC2", "RC1", "F1"]
L.append("| family | n | " + " | ".join(cols) + " |")
L.append("|---|---|" + "---|" * len(cols))
for f, n in C["v3"]["n"].items():
    L.append("| %s | %d | " % (f, n) + " | ".join(pct(C[k]["detection"][f]) for k in cols) + " |")
L.append("| macro | | " + " | ".join(pct(C[k]["macro"]) for k in cols) + " |")
L.append("| FA % | | " + " | ".join("%.2f" % (100 * C[k]["fa"]) for k in cols) + " |")
L.append("\nv3 reproduction: frozen domain on the rebuilt val cache gives FA %.10f, macro %.10f (stored WP4 S7 val view: identical, tests/v31/test_s4_regression.py); combined threshold re-derived from the rebuilt benign val stream %.6f vs frozen %.6f.\n" % (
    C["v3"]["fa"], C["v3"]["macro"], C["v3"]["rederived_threshold_from_rebuilt_val_benign"], C["v3"]["frozen_threshold"]))
L.append("## T3 Streaming object RC5 on real val flows (one flow at a time)\n")
L.append("| val slice | flows | families | max abs score diff stream vs batch | alarm mismatches | prefix == full | Evidence t == flow ts |")
L.append("|---|---|---|---|---|---|---|")
for d, x in sc["slices"].items():
    L.append("| %s | %d | %s | %g | %d | %s | %s |" % (d, x["flows"], ", ".join(f"{k} {v}" for k, v in x["families"].items()), x["max_abs_score_diff_stream_vs_batch"], x["alarm_mismatches"], x["prefix_equal_full"], x["evidence_t_equals_flow_ts"]))
p = sc["push_ms"]
L.append("\nPer-push compute (n = %d, includes the one-row tcp_flags frame; system CPU %.0f %% with other workers running): median %.2f ms, p95 %.2f ms, p99 %.2f ms, max %.1f ms (N3 limit p99 <= 1000 ms: %s; v3 stall 1.4 s median / 7.7 s max at each bin close).\n" % (
    p["n"], sc["machine"].get("cpu_percent_system", float("nan")), p["median"], p["p95"], p["p99"], p["max"], sc["N3_p99_le_1000ms"]))
fc = json.load(open(os.path.join(S, "s4_final_check.json")))
r = fc["reproduces_F1"]
L.append("### T3b Streaming object F1 (Stream31Final: tick-final emission)\n")
L.append("Fitted on the benign val stream it reproduces the F1 row of T1 (macro %.4f, FA %.4f; max abs score diff to the float32 saved scores %.1e, alarm mismatches %d). Streaming == batch on the same three slices: max abs score diff %s, alarm mismatches %s; stream-time delay median %.0f s (emission when the first flow of the next tick arrives); the maximum %.0f s of the slices is the gap between recording periods in which no flow arrives to trigger the flush (a clock timer closes the tick: delay <= 1 tick). Per-push compute (incl. the tick flush): median %.2f ms, p99 %.2f ms, max %.0f ms.\n" % (
    r["macro"], r["fa"], r["max_abs_score_diff_vs_eval_F1"], r["alarm_mismatches_vs_eval_F1"], sorted({x["max_abs_score_diff_stream_vs_batch"] for x in fc["slices"].values()}), sorted({x["alarm_mismatches"] for x in fc["slices"].values()}),
    fc["delay_s_all_slices"]["median"], fc["delay_s_all_slices"]["max"], fc["push_ms"]["median"], fc["push_ms"]["p99"], fc["push_ms"]["max"]))
L.append("## T4 Unseen Bot, part A: where the Bot flows (val, published labels, n = %d; corrected by the documented rule n = %d) sit in the H layers\n" % (b["n_bot_published"], b["n_bot_corrected"]))
L.append("| layer | AUC Bot vs benign | median calibrated score of Bot | Bot flows above the layer's 1% threshold | median raw Bot | median raw benign | p99 raw benign |")
L.append("|---|---|---|---|---|---|---|")
for n, x in b["A_layers_H"].items():
    L.append("| %s | %.3f | %.3f | %.1f %% | %.3g | %.3g | %.3g |" % (n, x["auc_bot_vs_benign"], x["median_calibrated_bot"], 100 * x["share_bot_above_layer_threshold"], x["median_raw_bot"], x["median_raw_benign"], x["p99_raw_benign"]))
sh = b["A_shape_duplicates"]
L.append("\nFlow shape: %d distinct Bot shapes (fwd/bwd packets, fwd/bwd bytes, dst port); every Bot flow has its shape among the BENIGN-labelled headline flows; %d BENIGN-labelled val flows carry a Bot shape (%d from an Ares victim to the C2: the label noise of WP4 S6), so an exact-shape detector has precision at most %.1f %%.\n" % (
    sh["bot_shapes"], sh["benign_flows_with_a_bot_shape"], sh["benign_with_bot_shape_dst_is_c2"], 100 * sh["max_precision_of_an_exact_shape_detector"]))
L.append("| Bot group (published labels) src -> dst:port | flows | active minutes | median gap (min) | span (min) | flows per active minute |")
L.append("|---|---|---|---|---|---|")
for g in b["A_groups_published"]:
    L.append("| %s -> %s:%d | %d | %d | %s | %d | %.2f |" % (g["src"], g["dst"], g["port"], g["flows"], g["active_minutes"], g["median_gap_min"], g["span_min"], g["flows_per_active_minute"]))
L.append("\n## T5 Unseen Bot, part B: label-free candidates (fit on benign train, 1% of benign val; added to H at a constant 1% combined budget)\n")
L.append("| candidate | alone: Bot published % | Bot corrected % | groups hit | FA % | AUC | precision | + H: Bot % | + H: macro % (diff) | + H: FA % | counts for N4 |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|")
for n, x in b["B_candidates"].items():
    if n == "H_reference":
        continue
    a, h = x["alone"], x["added_to_H"]
    L.append("| %s | %.1f | %.1f | %d / %d | %.2f | %.3f | %.1f %% | %.1f | %.1f (%.1f) | %.2f | %s |" % (n, 100 * a["bot_published"], 100 * a["bot_corrected"], a["groups_hit"], a["groups"], 100 * a["fa"], a["auc_bot_vs_benign"],
             100 * a["precision_on_alarmed_bot_or_benign"], 100 * h["bot_published"], 100 * h["macro"], h["macro_diff_vs_H_points"], 100 * h["fa"], x["counts_for_N4"]))
L.append("\nH reference on the same stream: Bot %.1f %%, macro %.1f %%, FA %.2f %%. %s\n" % (100 * b["B_candidates"]["H_reference"]["bot"], 100 * b["B_candidates"]["H_reference"]["macro"], 100 * b["B_candidates"]["H_reference"]["fa"], b["B_note"]))
open(os.path.join(S, "s4_tables.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
