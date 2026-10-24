"""WP7 S1b: appends section "S1b" to results/WP7/S1_tables.md and reports/WP7_S1.md and the S1b verdicts to results/WP7/S1_acceptance.json, all from results/WP7/S1b_net.json,
S1b_ties.json and S1_bus.json. Run AFTER tools/WP7_S1_report.py (which regenerates the S1 part). Run from codes_v3/: python -I -u -W ignore tools/WP7_S1b_report.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
OUT = ROOT / "results" / "WP7"
net = json.loads((OUT / "S1b_net.json").read_text())
ties = json.loads((OUT / "S1b_ties.json").read_text())
bus = json.loads((OUT / "S1_bus.json").read_text())
acc = json.loads((OUT / "S1_acceptance.json").read_text())
ok = lambda b: "MET" if b else "NOT MET"

a1, a2, a3, lat = net["A1_exactness"], net["A2_causality_truncation"], net["A3_reset"], net["A4_latency"]
met = {"A1": bool(a1["combined"]["all_identical"] and a1["per_layer"]["all_identical"] and a1["n_flows"] >= 30000 and a1["combined"]["alarm_mismatches"] == 0),
       "A2": bool(a2["all_identical"]), "A3": bool(a3["identical"]), "bus": bool(bus["A5_met"] and bus["A6_met"])}
met["S1b"] = all(met.values())
acc["S1b"] = {"net": met, "ties_noncausal_birth_pairs": {k: v["noncausal_birth_pairs"] for k, v in ties["datasets"].items()}}
(OUT / "S1_acceptance.json").write_text(json.dumps(acc, indent=1))

pe, pa = lat["per_emitting_push"]["pooled"], lat["per_push_all_calls"]["pooled"]
am = lat["amortised_ms_per_flow_per_repetition"]
T = ["\n## 7. S1b: network runner over the frozen domain (stack H) and equal-timestamp births\n"]
T.append("| Slice (D10 val, 30 min) | Flows | Families | Alarms (batch) | Combined identical | Layers identical | Max score diff |")
T.append("|---|---|---|---|---|---|---|")
for s in a1["slices"]:
    T.append(f"| {s['slice']} | {s['flows']} | {', '.join(f'{k} {v}' for k, v in s['families'].items())} | {s['alarms']} | {s['identical_combined']} | {s['identical_layers']} | {s['max_abs_score_diff']:.1e} |")
T.append(f"\nTotal {a1['n_flows']} flows, {a1['combined']['n_evidence']} combined + {a1['per_layer']['n_evidence']} per-layer Evidence, alarm mismatches {a1['combined']['alarm_mismatches']} / "
         f"{a1['per_layer']['alarm_mismatches']}, reason mismatches {a1['combined']['reason_mismatches']}, max score diff {a1['combined']['max_abs_score_diff']:.1e}.")
T.append(f"Truncation: {a2['n_checks']} checks (batch prefix, final flows == batch full; stream prefix == stream full), all identical: {a2['all_identical']}. Reset identical: {a3['identical']}.\n")
T.append("| Latency (ms) | n | median | p95 | p99 | median spread (reps) | v2 reference |")
T.append("|---|---|---|---|---|---|---|")
for name, d in (("push, all calls", lat["per_push_all_calls"]), ("push that closes a 5-min bin (re-scores the buffer, emits the flows of the closed bins)", lat["per_emitting_push"])):
    p = d["pooled"]
    T.append(f"| {name} | {p['n']} | {p['median_ms']:.4f} | {p['p95_ms']:.4f} | {p['p99_ms']:.4f} | {d['spread_median_ms']['min']:.4f} - {d['spread_median_ms']['max']:.4f} | - |")
T.append(f"| amortised per flow (total time / flows, 3 repetitions) | {lat['flows_per_repetition']} | {lat['amortised_ms_per_flow_median']:.4f} | - | - | {min(am):.4f} - {max(am):.4f} | ~1 ms |")
T.append("\nEmitting push by buffer size (flows already in the capture):\n")
T.append("| buffer from | to | n | median ms | p95 ms |")
T.append("|---|---|---|---|---|")
for r in lat["emitting_by_buffer_flows"] or []:
    T.append(f"| {r['size_from']:.0f} | {r['size_to']:.0f} | {r['n']} | {r['median_ms']:.1f} | {r['p95_ms']:.1f} |")
T.append("\nEqual-timestamp births (v2x.l3.birth_density counts births with EQUAL timestamp that come later in the table; counting only, no scoring):\n")
T.append("| Dataset split | Messages | Births (tracks) | Messages sharing t with another | Tied birth groups | Non-causal birth pairs | Births affected |")
T.append("|---|---|---|---|---|---|---|")
for k, v in ties["datasets"].items():
    T.append(f"| {k} | {v['messages']} | {v['tracks_births']} | {v['messages_sharing_t_with_another_message']} | {v['tied_birth_groups']} | {v['noncausal_birth_pairs']} | {v['births_with_noncausal_neighbour']} |")
T.append(f"\nBus with the network runner on 25 minutes of D10 validation: A5 {bus['A5_met']}, A6 {bus['A6_met']}; network Evidence on the bus {bus['evidence_on_bus'].get('network/combined')}.")
sec_tables = "\n".join(T) + "\n"

R = ["\n## S1b: network runner over the frozen network domain, and the equal-timestamp count (2026-10-24)\n"]
R.append(f"- **S1b {ok(met['S1b'])}.** `system/net_runner.py NetworkRunner` wraps the frozen `network/domain.py` (stack H, results/WP4/s7_domain, M1_NET section 9); the S1 placeholder is replaced (kept as NetworkPlaceholderRunner, unused).")
R.append(f"- Stream == batch on D10 VALIDATION: {a1['n_flows']} flows in 4 thirty-minute slices ({a1['n_families']} traffic families), 0 alarm mismatches, 0 reason mismatches, max score difference {a1['combined']['max_abs_score_diff']:.1e} "
         f"(combined and per-layer). Truncation {a2['n_checks']} checks identical, reset identical. D10 test not read.")
R.append("- **Semantics**: the frozen layers score a flow by its minute cell / 5-minute bin, so a flow's Evidence is final only when its window has closed. The runner appends flows and, when a flow of a later 5-minute bin "
         "arrives, re-scores the prefix and emits the flows of the closed bins (details['final'] = True); flush() emits the rest like the batch. The Evidence delay is therefore up to ~5 minutes of flow time (a property of the domain, not of the runner).")
R.append(f"- **Latency** (this loaded machine, 3 repetitions): amortised {lat['amortised_ms_per_flow_median']:.3f} ms per flow (range {min(am):.3f}-{max(am):.3f}; v2 ~1 ms), a push, all calls pooled {pa['median_ms']:.4f} ms median (mostly append + timestamp parsing), "
         f"a bin-closing push {pe['median_ms']:.0f} ms median / {pe['p99_ms']:.0f} ms p99 (re-scores the whole buffer; grows with the capture, see S1_tables.md section 7). Repetition 3 overlapped with a unit-test run.")
R.append("- **Equal-timestamp births (counting only, no scoring)**: " + "; ".join(f"{k}: {v['noncausal_birth_pairs']} non-causal pairs of {v['tracks_births']} births ({v['messages_sharing_t_with_another_message']} messages share a timestamp)" for k, v in ties["datasets"].items())
         + ". So the non-causal use of equal-timestamp births in v2x.l3.birth_density is zero on VeReMi (validation and test) and Tampa v2 (genuine frame of validation and test vehicles); it would appear only on data with coarse timestamps.")
R.append("- Tests: tests/system/test_net_runner.py (3, one on the frozen domain and a D10 validation slice). Files: system/net_runner.py, tools/WP7_S1b_{net,ties,report}.py, results/WP7/S1b_net.json, S1b_ties.json.")
rep = (ROOT / "reports" / "WP7_S1.md").read_text()
rep = rep.split("\n## S1b:")[0].rstrip("\n") + "\n" + "\n".join(R) + "\n"
(ROOT / "reports" / "WP7_S1.md").write_text(rep)
tab = (OUT / "S1_tables.md").read_text().split("\n## 7. S1b")[0].rstrip("\n") + "\n" + sec_tables
(OUT / "S1_tables.md").write_text(tab)
print(json.dumps(met))
