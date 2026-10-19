"""WP5 S2: build reports/WP5_S2.md from results/WP5/s2_*.json and s2_tables.md (no hand-typed numbers in the tables).
Run from codes_v3/: python -I -u -W ignore tools/WP5_S2_report.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results" / "WP5"
S = json.loads((R / "s2_summary.json").read_text())
tables = (R / "s2_tables.md").read_text()
V, T = S["veremi"], S["tampa"]


def pc(x):
    return f"{100 * x:.1f}%"


def md(d, op, c):
    return d["by_class"][op][c]["msg_detection"]


cl_all = [c for c in V["by_class"]["combined"]]
cl_1_12_17 = [c for c in cl_all if int(c[:2]) <= 12 or int(c[:2]) == 17]
cl_13_15 = [c for c in cl_all if int(c[:2]) in (13, 14, 15)]

checks = []
fa_v = {k: d["false_alarm_messages"] for k, d in V["per_operating_point"].items()}
fa_t = {k: d["false_alarm_messages"] for k, d in T["per_operating_point"].items() if "standard" not in k}
checks.append(("3a VeReMi false alarms on genuine test messages <= 1.5% at every operating point",
               max(fa_v.values()) <= 0.015, f"max {pc(max(fa_v.values()))}"))
checks.append(("3b Tampa false alarms on genuine test messages <= 2% at every budget / physical / union operating point",
               max(fa_t.values()) <= 0.02, f"max {pc(max(fa_t.values()))}"))
phys = [V["physical_FA_val_genuine"], V["physical_FA_test_genuine"], T["physical_FA_val_genuine"], T["physical_FA_test_genuine"]]
checks.append(("3c physical field_ranges false alarms <= 0.1% on genuine val and test (both datasets)",
               max(phys) <= 0.001, f"max {pc(max(phys))}"))
exp = []
r_v = [md(V, "v2x.beacon_rate", c) for c in cl_13_15]
r_t = [T["by_class"]["v2x.beacon_rate"][c]["msg_detection"] for c in cl_13_15]
exp.append(("E1 rate layer detects >= 90% of messages of classes 13, 14, 15 on VeReMi test", min(r_v) >= 0.9,
            ", ".join(f"{c[:2]}: {pc(x)}" for c, x in zip(cl_13_15, r_v))))
exp.append(("E1b same on the Tampa injected types 13, 14, 15 (x2, x4, x4)", min(r_t) >= 0.9,
            ", ".join(f"{c[:2]}: {pc(x)}" for c, x in zip(cl_13_15, r_t))))
mp = max(max(md(V, "v2x.field_ranges@physical", c) for c in cl_all),
         max(T["by_class"]["v2x.field_ranges@physical"][c]["msg_detection"] for c in T["by_class"]["combined"]))
exp.append(("E2 field_ranges at the physical limit detects < 5% of every class (both datasets)", mp < 0.05, f"max {pc(mp)}"))
fr = {c: s["msg_detection"] for c, s in T["by_class"]["v2x.freshness"].items()}
fo = max(v for c, v in fr.items() if not c.startswith("S20"))
exp.append(("E3 freshness detects only S20 (every other Tampa type < 5%; S20 >= 90%)", fo < 0.05 and fr["S20_StaleReplay"] >= 0.9,
            f"other max {pc(fo)}, S20 {pc(fr['S20_StaleReplay'])}"))
uv = max(md(V, "L1_union_at_operating_points", c) for c in cl_1_12_17)
ut = max(T["by_class"]["L1_union_at_operating_points"][c]["msg_detection"] for c in cl_1_12_17)
exp.append(("E4 L1 union detects < 30% of classes 1-12 and 17 (VeReMi and Tampa)", max(uv, ut) < 0.3,
            f"VeReMi max {pc(uv)}, Tampa max {pc(ut)}"))

lines = []
w = lines.append
w("# WP5 S2: L1 message checks (beacon rate, freshness, field ranges, sudden appearance)\n")
w("Date: 2026-10-19    Worker: sonnet (medium)\n")
w("## Goal of the step\nL1 message checks as v3 Layers for V2X: beacon rate per sender, timestamp freshness, field ranges (cited physical limits), sudden appearance. Evaluate per attack class on VeReMi (all 19 classes) and on the injected Tampa types, false alarms on genuine test senders, harness ablation.\n")
w("## Acceptance rule (notes/WP5_v2x.md, section 'S2 L1 message checks: acceptance rule', written before any S2 result)\n"
  "1 four Layers + unit tests + run_tests; 2 no threshold fitted on test or attack data, physical limits cited; "
  "3 false alarms at each operating point <= 1.5x budget (VeReMi), <= 2% (Tampa), physical ranges <= 0.1% on genuine val and test; "
  "4 per-class tables for the 19 classes and Tampa types, genuine-sender false alarms, ablation, bootstrap CIs. "
  "Plus pre-registered expectations E1-E4 (below). Held-out attack types 6, 12, 17 were removed from the validation set the combiner sees (marked * in the tables).\n")
w("## What was done\n"
  "- `v2x/l1.py`: `BeaconRate`, `Freshness`, `FieldRanges`, `SuddenAppearance` (domain v2x, layer L1, kind rule, causal per track; limits and sources in the docstring and in `results/WP5/s2_summary.json`).\n"
  "- `v2x/adapters.py`: `load_tampa(with_age=True)` adds `age_s` = RSU log time - generation time (default output unchanged).\n"
  "- `tools/WP5_S2_l1.py` (evaluation, one run on test), `tools/WP5_S2_report.py` (this file), `tests/v2x/test_l1.py` (11 tests).\n"
  "- Calibration on validation genuine messages only (VeReMi val 161426 genuine messages; Tampa val 4491), 1% budget, tie-safe (`common/`). "
  "Tampa evaluation set = all genuine test messages + the falsified messages of the 19 injected scenarios (10 attackers per type) + a supplemental attack S20.\n"
  "- Supplemental S20 StaleReplay (not in the 19, Tampa only): 10 attackers rebroadcast 100 genuine messages of other vehicles each, verbatim with the original timestamp, delivered 10-60 s late. Added because the 19 injected types stamp the current time (as a real attacker would), so freshness cannot see them by construction.\n")
w("### Limits and where they come from\n")
w("| quantity | value | source |\n|---|---|---|")
L = S["limits"]
w(f"| max beacon rate | {L['RATE_MAX_HZ']:.0f} Hz (+{100 * (L['RATE_TOL'] - 1):.0f}% tolerance for the physical alarm) | SAE J2945/1 BSM 10 Hz; ETSI EN 302 637-2 T_GenCam_Min 100 ms |")
w(f"| timestamp resolution | {L['TIME_RES_S'] * 1000:.0f} ms | ETSI generationDeltaTime, SAE J2735 DSecond |")
w(f"| max speed | {L['V_MAX']:.0f} m/s | 250 km/h electronic limit of road cars (VDA); encodings allow 163.8 m/s |")
w(f"| max acceleration | {L['A_MAX']:.2f} m/s^2 (1.3 g) | tyre friction (Wong; Rajamani); encodings +-16 (ETSI) / +-20 (J2735) m/s^2 |")
w(f"| yaw rate | v / {L['R_MIN']:.0f} m for v >= {L['YAW_MIN_SPEED']:.0f} m/s, else {L['YAW_CAP']:.2f} rad/s (J2735 range) | Ackermann minimum radius |")
w(f"| entry distance (sudden appearance) | {L['R_EDGE']:.0f} m | design value; DSRC range 300-1000 m (Kenney, Proc. IEEE 2011) |")
w(f"| future tolerance (freshness) | {L['AGE_FUTURE_TOL']:.0f} s | 1 s resolution of the Tampa RSU log |")
w(f"\nData-driven thresholds (validation genuine, 1% budget), as raw values: VeReMi rate {V['threshold_raw_equivalent']['v2x.beacon_rate'] * L['RATE_MAX_HZ']:.2f} Hz, "
  f"ranges ratio {V['threshold_raw_equivalent']['v2x.field_ranges']:.2f}; Tampa rate {T['threshold_raw_equivalent']['v2x.beacon_rate'] * L['RATE_MAX_HZ']:.1f} Hz, "
  f"freshness {T['threshold_raw_equivalent']['v2x.freshness']:.2f} s, ranges ratio {T['threshold_raw_equivalent']['v2x.field_ranges']:.2f}.\n")
w("### What is and is not evaluated\n")
w(f"- VeReMi: beacon rate and field ranges. Freshness NOT evaluable (the combined CSV has only the send time, no receive time, and the file order is not arrival order). Sudden appearance NOT evaluable (no receiver id / position).\n"
  f"- Tampa: beacon rate, freshness, field ranges. Sudden appearance NOT evaluable (RSU positions are not in the public sample).\n"
  f"- **Sudden appearance: implemented and unit-tested on synthetic data (`tests/v2x/test_l1.py::test_sudden_appearance_synthetic`), NOT evaluated on real data.** No receiver positions were invented.\n"
  f"- The 'combined' column is the harness combination (noisy-or chosen on validation) of the evaluable layers at the 1% budget. The 'L1 union' column is the rule-style operating point: beacon rate (budget) OR field ranges (physical limit) OR freshness (budget, Tampa).\n")
w("## Results (generated from results/WP5/s2_*.json; full tables in results/WP5/s2_tables.md)\n")
w(tables)
w("\nThe harness column 'median delay' is computed per group (time block / vehicle) and is not meaningful here; per-attacker delays are in the sender-level table.\n")
w("## Acceptance\n")
w("| check | result | value |\n|---|---|---|")
for n, ok, v in checks:
    w(f"| {n} | {'MET' if ok else 'NOT MET'} | {v} |")
w("\nPre-registered expectations (stated before the run, not used for tuning):\n")
w("| expectation | outcome | value |\n|---|---|---|")
for n, ok, v in exp:
    w(f"| {n} | {'as expected' if ok else 'NOT as expected'} | {v} |")
allok = all(c[1] for c in checks)
w(f"\nAcceptance 1 (layers, unit tests) and 2 (no fitted threshold on test / attack data, limits cited): MET. 3: {'MET' if allok else 'NOT MET (see table)'}. 4: MET. "
  f"Overall S2: {'MET' if allok else 'PARTIAL'}.\n")
w("## What L1 does and does not do (plain reading)\n"
  f"- L1 catches rate-type attacks: DoS / DoSRandom / DoSDisruptive on VeReMi ({pc(md(V, 'L1_union_at_operating_points', cl_13_15[0]))}, {pc(md(V, 'L1_union_at_operating_points', cl_13_15[1]))}, {pc(md(V, 'L1_union_at_operating_points', cl_13_15[2]))} of messages; every attacker detected within about half a second) and the x4 types on Tampa. "
  f"It misses the x2 DoS on Tampa ({pc(T['by_class']['L1_union_at_operating_points'][cl_13_15[0]]['msg_detection'])}): the validation genuine vehicles already contain 20 Hz bursts (6% of validation inter-arrivals), so the 1% budget threshold is {T['threshold_raw_equivalent']['v2x.beacon_rate'] * L['RATE_MAX_HZ']:.1f} Hz.\n"
  "- L1 misses almost all position / speed falsification, replay and Sybil-with-plausible-rate classes: every claimed value is physically possible and each sender's rate is normal. This is the reason for L2-L4, not a defect of L1. "
  "GridSybil (16) is partly caught on VeReMi only because the ghost pseudonyms are interleaved at different rates (0.17 / 0.33 s gaps), not on the injected Tampa version where ghosts keep the attacker's rate.\n"
  "- The field-range check at its PHYSICAL limit never fires on any attack (VeReMi random speeds reach 56 m/s, below 70 m/s). At the 1% budget operating point it ranks messages by speed / acceleration relative to the limit and thereby catches high-speed falsification (classes 5, 7, 14, 18 about 70%), but this is a learned quantile of genuine speed (max genuine speed 19 m/s), not a physical limit; it flags 49% of genuine senders at least once. Treat that operating point as an ablation device, not as a deployable rule.\n"
  "- False alarms: a 1% message budget is large per sender (about 110 messages per VeReMi sender): the budget-point ranges layer alarms on about half of the genuine senders, the beacon-rate layer and the physical operating points on none (VeReMi). Tampa: 11-16% of genuine vehicles for a single layer, 27% for the union (small sample: 45 test vehicles, intervals in the tables).\n"
  "- Freshness is only useful against stale (late-delivered) messages (S20 100% detection, 1.1% false alarms); it does nothing against the 19 injected types because they carry fresh timestamps.\n")
w("## Ablation rows\nHarness ablation tables are at the end of the Results section (VeReMi: two evaluable layers, so only `only_X` and `all`; Tampa: three layers, `only_X`, `all`, `all_but_X`). "
  "The combiner used validation without attack types 6, 12, 17.\n")
w("## Problems, surprises, open questions\n"
  "- **Class-13 DoS factor.** S1 reported a median factor of 2x. Per sender it is bimodal: 0.5 s and 0.25 s gaps (rates 2 and 4 Hz, mean 2.97, range 2.0-4.2 Hz over the 390 senders of the combined CSV). The Tampa injection keeps x2 (as approved); the VeReMi detection above uses the real data.\n"
  "- **Genuine Tampa vehicles sometimes exceed 10 Hz.** 6.1% of validation and 1.5% of test genuine inter-arrivals correspond to > 10.5 Hz (mostly ~20 Hz bursts; one validation vehicle contributes half of them). Applying the standard maximum literally (physical rate alarm) gives 1.5% false alarms on genuine Tampa test messages, so the data-driven threshold is used. Cause not investigated (duplicated temporary ids or logging artefacts are possible).\n"
  "- Tampa results are noisy (10 attackers per type, 45 test vehicles): use the bootstrap CIs. The combiner / harness AUC on Tampa is dominated by the huge number of injected messages relative to genuine ones (112704 attack vs 8870 genuine test messages); detection rates and false-alarm rates are the meaningful numbers.\n"
  "- Single-message evaluation hides the sender-level picture: for L1 (budget point) report both. VeReMi test used once; Tampa test used once; no re-draws.\n"
  "- Question for the supervisor: should S3 evaluate acceptance-range / sudden-appearance on Tampa with the RSU centroid as receiver (flagged as an approximation), or wait for V2AIX / VeReMi NextGen with receiver positions?\n")
w("## Proposed next step\nS3 (L2 plausibility: position / speed / heading consistency between consecutive beacons, kinematic consistency, overlapping vehicles, OSM road plausibility) is where position and speed falsification should start to be detected.\n")
(ROOT / "reports" / "WP5_S2.md").write_text("\n".join(lines), encoding="utf-8")
print("written; checks:", [(c[0][:2], c[1]) for c in checks], [(e[0][:3], e[1]) for e in exp])
