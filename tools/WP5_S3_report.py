"""WP5 S3: build reports/WP5_S3.md from results/WP5/s3_*.json and s3_tables.md (numbers in tables come from the JSON).
Run from codes_v3/: python -I -u -W ignore tools/WP5_S3_report.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results" / "WP5"
S = json.loads((R / "s3_summary.json").read_text())
D = json.loads((R / "s3_diag.json").read_text())
tables = (R / "s3_tables.md").read_text()
V, T = S["veremi"], S["tampa"]
L2N = ["v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate", "v2x.accel_consistency",
       "v2x.yaw_consistency", "v2x.overlap", "v2x.map_road"]
HELD = (6, 12, 17)


def pc(x):
    return "-" if x is None else f"{100 * x:.1f}%"


def md(d, op, c):
    return d["by_class"][op][c]["msg_detection"]


cl = list(V["by_class"]["L2_union"])
num = lambda c: int(c[:2]) if c[:2].isdigit() else -1
cls_of = lambda ids: [c for c in cl if num(c) in ids]


def det_list(d, op, ids):
    return ", ".join(f"{num(c)}: {pc(md(d, op, c))}" for c in cls_of(ids) if c in d["by_class"][op])


# ---- acceptance 3
fa_v = {k: x["false_alarm_messages"] for k, x in V["per_operating_point"].items() if "@physical" not in k and "physical" not in k}
fa_t = {k: x["false_alarm_messages"] for k, x in T["per_operating_point"].items() if "physical" not in k}
phys_v = max(max(x["val_genuine"], x["test_genuine"]) for x in V["physical_FA"].values())
phys_t = max(max(x["val_genuine"], x["test_genuine"]) for x in T["physical_FA"].values())
bad_t = {k: x for k, x in fa_t.items() if x > 0.02}
bad_v = {k: x for k, x in fa_v.items() if x > 0.015}
checks = [
    ("3a VeReMi: every check and union <= 1.5% false alarms on genuine test messages", not bad_v,
     f"max {pc(max(fa_v.values()))} ({max(fa_v, key=fa_v.get)})"),
    ("3b Tampa: every check and union <= 2% false alarms on genuine test messages", not bad_t,
     "exceeded by " + ", ".join(f"{k} {pc(x)}" for k, x in sorted(bad_t.items(), key=lambda kv: -kv[1])) if bad_t else f"max {pc(max(fa_t.values()))}"),
    ("3c physical limits (speed_change, implied_speed, heading_rate, field_ranges) <= 0.1% on genuine val and test",
     max(phys_v, phys_t) <= 0.001, f"VeReMi max {100 * phys_v:.4f}%, Tampa max {100 * phys_t:.4f}%"),
]
nm = D["tampa_non_map_L2_union_genuine"]
# ---- expectations
Lu = lambda c: md(V, "L2_union", c)
Tu = lambda c: md(T, "L2_union", c)
p1 = [c for c in cls_of([3, 4, 7, 10, 14, 15, 18, 19])]
p2 = cls_of([1, 5])
p3v = cls_of([6, 8])
p4 = cls_of([2, 11, 12, 13, 16, 17])
exp = [
    ("P1 VeReMi: classes 3, 4, 7, 10, 14, 15, 18, 19 >= 85% (L2 union)", all(Lu(c) >= 0.85 for c in p1), ", ".join(f"{num(c)}: {pc(Lu(c))}" for c in p1)),
    ("P2 VeReMi: classes 1 and 5 >= 80%", all(Lu(c) >= 0.8 for c in p2), ", ".join(f"{num(c)}: {pc(Lu(c))}" for c in p2)),
    ("P3 VeReMi: classes 6 and 8 between 20% and 80%; Tampa < 50%", all(0.2 <= Lu(c) <= 0.8 for c in p3v) and all(Tu(c) < 0.5 for c in p3v),
     "VeReMi " + ", ".join(f"{num(c)}: {pc(Lu(c))}" for c in p3v) + "; Tampa " + ", ".join(f"{num(c)}: {pc(Tu(c))}" for c in p3v)),
    ("P4 VeReMi: classes 2, 11, 12, 13, 16, 17 each < 10% (consecutive checks blind)", all(Lu(c) < 0.1 for c in p4), ", ".join(f"{num(c)}: {pc(Lu(c))}" for c in p4)),
    ("P4 Tampa: same classes each < 10% (map may add on class 2)", all(Tu(c) < 0.1 for c in p4), ", ".join(f"{num(c)}: {pc(Tu(c))}" for c in p4)),
    ("P5 class 9 EventualStop message level < 10%", Lu(cls_of([9])[0]) < 0.1 and Tu(cls_of([9])[0]) < 0.1,
     f"VeReMi {pc(Lu(cls_of([9])[0]))}, Tampa {pc(Tu(cls_of([9])[0]))}"),
    ("P6 union false alarms on genuine test messages <= 1.5% (VeReMi), <= 2% (Tampa)",
     V["per_operating_point"]["L2_union"]["false_alarm_messages"] <= 0.015 and T["per_operating_point"]["L2_union"]["false_alarm_messages"] <= 0.02,
     f"VeReMi {pc(V['per_operating_point']['L2_union']['false_alarm_messages'])}, Tampa {pc(T['per_operating_point']['L2_union']['false_alarm_messages'])}"),
]

# ---- plain verdict table
def verdict(x):
    return "caught" if x >= 0.8 else ("partly" if x >= 0.3 else "not caught")


vt = ["| class | VeReMi msgs (union L2) | VeReMi attackers >= 3 alarms | Tampa msgs (union L2) | Tampa attackers >= 3 alarms | verdict VeReMi / Tampa |", "|---|---|---|---|---|---|"]
for c in cl + [c for c in T["by_class"]["L2_union"] if c not in cl]:
    v = V["by_class"]["L2_union"].get(c)
    t = T["by_class"]["L2_union"].get(c)
    vs = V["sender_ge3_alarms"]["L2_union"]["by_class"].get(c)
    ts = T["sender_ge3_alarms"]["L2_union"]["by_class"].get(c)
    star = " *" if num(c) in HELD else ""
    vt.append(f"| {c}{star} | {pc(v['msg_detection']) if v else '-'} | {pc(vs)} | {pc(t['msg_detection']) if t else '-'} | {pc(ts)} | "
              f"{verdict(v['msg_detection']) if v else '-'} / {verdict(t['msg_detection']) if t else '-'} |")
vt = "\n".join(vt)

mech = D["veremi_val_mechanisms"]
tm = D["tampa_map"]
g = lambda k: mech[k]
lines = []
w = lines.append
w("# WP5 S3: L2 plausibility (consecutive-beacon, kinematic, overlap, map)\n")
w("Date: 2026-10-19    Worker: sonnet (medium)\n")
w("## Goal of the step\nF2MD-style plausibility per sender (Kamel et al.): position / speed / heading consistency between consecutive beacons, kinematic consistency, overlapping vehicles, map plausibility (Tampa only). "
  "Supervisor decisions applied: no receiver-position approximation; acceptance-range and sudden appearance are NOT in S3 (deferred to S3b, need real receiver positions); map check skipped on VeReMi (no Luxembourg map).\n")
w("## Acceptance rule (notes/WP5_v2x.md, 'S3 L2 plausibility: acceptance rule', written before any S3 result)\n"
  "1 nine Layers + unit tests; 2 no threshold fitted on test or attack data, limits cited, OSM recorded; 3 false alarms: every check and the union <= 1.5% (VeReMi) / <= 2% (Tampa), physical limits <= 0.1% on genuine val and test; "
  "4 per-check, union and combined detection for all 19 classes (+S20), false alarms on genuine messages and senders, delay per attacker, harness ablation on top of L1, Tampa bootstrap CIs. "
  "Pre-registered expectations P1-P6 (below). Held-out attack types 6, 12, 17 (marked *) stayed out of calibration and of the combiner's validation set.\n")
w("## What was done\n"
  "- `v2x/l2.py`: nine Layers (domain v2x, layer L2, kind physics, causal): `pos_speed`, `pos_heading`, `speed_change`, `implied_speed`, `heading_rate`, `accel_consistency`, `yaw_consistency`, `overlap`, `map_road` (definitions, constants and sources in the module docstring). "
  "Thresholds from validation genuine messages only (1% budget, tie-safe, `calibrate_masked`: the whole validation frame is scored so neighbours exist, the fit uses genuine rows only); physical operating point (raw >= 1) for `speed_change`, `implied_speed`, `heading_rate`.\n"
  "- `tests/v2x/test_l2.py` (15 tests: every check on synthetic data, causality, row-order independence, receiver separation, map distance, masked calibration). Full suite: 116 passed.\n"
  "- `tools/WP5_S3_l2.py` (one dev run on validation, one dry run with validation as a stand-in test, one final run on test: `results/WP5/logs/s3_run1.log`), `tools/WP5_S3_diag.py` (post-hoc diagnostics, not used for any choice), `tools/WP5_S3_report.py` (this file).\n"
  "- Data: VeReMi D12 (val/test as in S1, 7 evaluable L2 layers: no yaw rate, no map) and Tampa D14 with injected attacks (all 9 layers). Each Tampa scenario is scored together with the genuine rest of its split (neighbours for overlap), only attacker messages are evaluated. "
  "New dataset **D27 OSM Tampa** (Overpass, ODbL 1.0, drivable classes only, 1,782 ways, 1.4 MB) recorded in DATASETS.md and the notes.\n"
  "- Operating points: each check at the 1% budget; the three limit checks also at the physical limit; `L2_union` = max of the calibrated L2 scores at ONE 1% budget (an OR of nine 1% checks would break the budget); `L1_and_L2_union` = L1 union (beacon rate budget OR field ranges physical OR freshness budget) OR `L2_union`; "
  "`combined_*` = harness combiner (chosen on validation) of the L1, the L2 and all layers.\n")
w("### Not done, on purpose\n- Acceptance-range threshold and sudden appearance (S3b: need real receiver positions). Map check on VeReMi (no Luxembourg map). No Tampa RSU centroid was used as receiver position.\n")
w("## Results (generated from results/WP5/s3_*.json; full tables in results/WP5/s3_tables.md)\n")
w("### What each class looks like, in one table (L2 union at the 1% budget; * = held-out type)\n")
w("verdict: caught >= 80% of messages, partly 30-80%, not caught < 30% (message level). 'attackers >= 3 alarms' = share of attackers with at least 3 alarmed messages (sender-level view; genuine senders with >= 3 alarms: "
  f"VeReMi {pc(V['sender_ge3_alarms']['L2_union']['false_alarm_genuine_senders'])}, Tampa {pc(T['sender_ge3_alarms']['L2_union']['false_alarm_genuine_senders'])}).\n")
w(vt + "\n")
w("Caveat: the Tampa union includes the map check, whose false alarms do not transfer (union false alarms on genuine Tampa test messages " + pc(T["per_operating_point"]["L2_union"]["false_alarm_messages"]) + ", acceptance bound 2%); read the Tampa columns together with the per-check tables, where the non-map checks keep their budget.\n")
w(tables)
w("\nThe harness column 'median delay' is computed per group (time block / vehicle) and is not meaningful here; per-attacker delays are the 'median delay' values in the sender-level tables.\n")
w("## Acceptance\n")
w("| check | result | value |\n|---|---|---|")
for n, ok, v in checks:
    w(f"| {n} | {'MET' if ok else 'NOT MET'} | {v} |")
w("\nPre-registered expectations (stated before the run, not used for tuning):\n")
w("| expectation | outcome | value |\n|---|---|---|")
for n, ok, v in exp:
    w(f"| {n} | {'as expected' if ok else 'NOT as expected'} | {v} |")
allok = all(c[1] for c in checks)
w(f"\nAcceptance 1 (nine Layers, unit tests, run_tests 116 passed) and 2 (no fitted threshold on test or attack data, limits cited, OSM recorded): MET. 3: {'MET' if allok else 'NOT MET on Tampa (see table); VeReMi and the physical limits are MET'}. 4: MET. "
  f"Overall S3: {'MET' if allok else 'PARTIAL'}. The only criterion missed is the Tampa false-alarm bound, caused by the map check (below).\n")
w("## What L2 catches and what it does not (plain reading)\n")
w(f"- **Caught (VeReMi / Tampa message level)**: RandomPos 3 ({pc(Lu(cls_of([3])[0]))} / {pc(Tu(cls_of([3])[0]))}), RandomPosOffset 4 ({pc(Lu(cls_of([4])[0]))} / {pc(Tu(cls_of([4])[0]))}), RandomSpeed 7 ({pc(Lu(cls_of([7])[0]))} / {pc(Tu(cls_of([7])[0]))}), "
  f"RandomSpeedOffset 8 ({pc(Lu(cls_of([8])[0]))} / {pc(Tu(cls_of([8])[0]))}), Disruptive 10 ({pc(Lu(cls_of([10])[0]))} / {pc(Tu(cls_of([10])[0]))}), DoSRandom 14 ({pc(Lu(cls_of([14])[0]))} / {pc(Tu(cls_of([14])[0]))}), DoSDisruptive 15 ({pc(Lu(cls_of([15])[0]))} / {pc(Tu(cls_of([15])[0]))}). "
  "Random content jumps between consecutive beacons, so displacement vs speed x dt, implied speed and speed change expose it. The physical limits alone (no fitted threshold) already catch 3 RandomPos and 14 / 15 / 10 via `implied_speed`, and 7 / 14 partly via `speed_change` (tables above).\n")
w(f"- **Constant speed / constant position**: ConstSpeed 5 {pc(Lu(cls_of([5])[0]))} / {pc(Tu(cls_of([5])[0]))}, ConstSpeedOffset 6 {pc(Lu(cls_of([6])[0]))} / {pc(Tu(cls_of([6])[0]))}, ConstPos 1 {pc(Lu(cls_of([1])[0]))} / {pc(Tu(cls_of([1])[0]))}. "
  "The check is the same (the claimed speed does not produce the observed displacement) but it depends on dt and on position noise: VeReMi has dt = 1 s and noise sigma ~4 m per axis, so a 5-30 m/s error is large; Tampa has dt = 0.1 s and a GPS-like noise, so the same speed error is a metre or less and mostly hidden. "
  "Per attacker the picture is much better than per message: at least 3 alarms for most attackers (table above).\n")
w(f"- **Not caught**: ConstPosOffset 2 ({pc(Lu(cls_of([2])[0]))} / {pc(Tu(cls_of([2])[0]))}; on Tampa the map check adds a third, with the false alarms below), EventualStop 9 ({pc(Lu(cls_of([9])[0]))} / {pc(Tu(cls_of([9])[0]))}: only the stopping transition is implausible; sender level on VeReMi {pc(V['by_class']['L2_union'][cls_of([9])[0]]['sender_detected'])} for >= 1 alarm but {pc(V['sender_ge3_alarms']['L2_union']['by_class'][cls_of([9])[0]])} for >= 3), "
  f"DelayedMessages 12 ({pc(Lu(cls_of([12])[0]))} / {pc(Tu(cls_of([12])[0]))}: a 3 s old state is a consistent trajectory), Tampa DataReplay 11 ({pc(Tu(cls_of([11])[0]))}) and GridSybil 16 ({pc(Tu(cls_of([16])[0]))}), VeReMi Sybil with a new pseudonym per message 18 ({pc(Lu(cls_of([18])[0]))}) and 19 ({pc(Lu(cls_of([19])[0]))}).\n")
w(f"- **Why VeReMi 18 / 19 are blind**: a fresh pseudonym per message means every track has one message, so there is no consecutive pair to test (a receiver cannot link the pseudonyms). Only `overlap` and `map_road` need no history; overlap sees a part of 19 ({pc(md(V, 'v2x.overlap', cls_of([19])[0]))} of messages) because the random disruptive content lands on other vehicles. L1 field ranges at its budget point (a quantile of genuine speed, not a physical limit) is what catches 18 in the combination.\n")
w(f"- **VeReMi classes 11, 13, 16 are detected although the expectation was that they are not** (validation rows, `results/WP5/s3_diag.json`): DataReplay 11 replays states with position jumps (median displacement {g('11_DataReplay')['median_displacement_m']:.1f} m vs speed x dt {g('11_DataReplay')['median_speed_x_dt_m']:.1f} m); "
  f"DoS 13 repeats the same state at dt = {g('13_DoS')['median_dt_s']:.2f} s ({pc(g('13_DoS')['frac_zero_displacement'])} of consecutive pairs have zero displacement while the speed says {g('13_DoS')['median_speed_x_dt_m']:.1f} m); "
  f"GridSybil 16 ghosts move {g('16_GridSybil')['median_displacement_m']:.1f} m per beacon while claiming {g('16_GridSybil')['median_speed_x_dt_m']:.1f} m (speed x dt). "
  "So this is a property of how VeReMi implements these attacks, not evidence that L2 detects replay or Sybil in general. The injected Tampa versions (consistent replay, constant-velocity DoS, grid ghosts at the true speed) are, as predicted, mostly invisible to these checks.\n")
w(f"- **Overlap**: on VeReMi it fires on {pc(md(V, 'v2x.overlap', cls_of([11])[0]))} of DataReplay and {pc(md(V, 'v2x.overlap', cls_of([17])[0]))} of DataReplaySybil messages (replayed positions land on live vehicles) and on {pc(md(V, 'v2x.overlap', cls_of([16])[0]))} of GridSybil (ghosts 15 m / 3.5 m away do not overlap a 4.5 x 1.8 m footprint, as predicted). "
  f"On Tampa it has {pc(T['per_operating_point']['v2x.overlap']['false_alarm_messages'])} false alarms and fires only on 19 ({pc(md(T, 'v2x.overlap', cls_of([19])[0]))}). "
  "The 76.9% on S20 is an artefact of how S20 is built (every stale message is its own track, so 0.1 s neighbours of the same victim 'overlap' each other); it is not a detection result and is not credited to L2.\n")
w(f"- **Map (Tampa)**: catches {pc(md(T, 'v2x.map_road', cls_of([2])[0]))} of ConstPosOffset 2 (position shifted 100-300 m, often off the road), {pc(md(T, 'v2x.map_road', cls_of([3])[0]))} of RandomPos 3, but its **false alarms do not transfer** from validation to test: "
  f"{pc(T['per_operating_point']['v2x.map_road']['false_alarm_messages'])} on genuine test messages (95% CI {pc(T['per_operating_point']['v2x.map_road']['false_alarm_ci95_vehicle_bootstrap'][0])} to {pc(T['per_operating_point']['v2x.map_road']['false_alarm_ci95_vehicle_bootstrap'][1])}) against 1% on validation. "
  f"Post-hoc diagnosis (`s3_diag.json`): the validation q99 distance is {tm['val_q99_m']:.1f} m (maximum {tm['val_distance_quantiles_m']['1.0']:.1f} m) but {tm['vehicles_with_any_alarm']} of {tm['test_vehicles']} test vehicles exceed it and two of them (RSUs thea24 and thea1, median distance about 27 m from any mapped drivable way) produce {100 * (tm['top_vehicles_by_alarms'][0]['share_of_alarms'] + tm['top_vehicles_by_alarms'][1]['share_of_alarms']):.0f}% of the alarms. "
  "Likely causes (not verified): roads or lots missing from the OSM extract (service / private roads, a parking area, a construction detour) or a position offset of those vehicles. The wide vehicle-bootstrap interval shows how little validation (45 vehicles, a few RSUs) says about unseen places. The same lesson as the GPS work package: a map check calibrated on a few drives does not transfer to places it has not seen.\n")
w(f"- **False alarms in numbers**: VeReMi union {pc(V['per_operating_point']['L2_union']['false_alarm_messages'])} of genuine messages, but {pc(V['per_operating_point']['L2_union']['false_alarm_genuine_senders'])} of genuine senders have at least one alarm ({pc(V['sender_ge3_alarms']['L2_union']['false_alarm_genuine_senders'])} have >= 3): a 1% message budget over ~110 messages per sender is large per sender, as in S2; a sender-level rule needs >= k alarms. "
  f"Tampa: the union of the eight non-map L2 checks has {pc(nm['test_FA'])} false alarms on genuine test messages (validation {pc(nm['val_FA'])}), so the budget does transfer for the checks that do not depend on place; {pc(nm['test_genuine_vehicles_with_any_alarm'])} of the test vehicles raise at least one alarm.\n")
w("## Ablation on top of L1 (harness)\n"
  "Each layer alone, all layers, and all-but-one are in the harness tables above (`only_*`, `all`, `all_but_*`); the group rows 'L1 / L2 / L1+L2' are in the last table of each dataset. "
  f"VeReMi: L1 AUC {V['groups']['L1']['auc']:.3f} / detection {pc(V['groups']['L1']['detection'])}, L2 {V['groups']['L2']['auc']:.3f} / {pc(V['groups']['L2']['detection'])}, L1+L2 {V['groups']['L1+L2']['auc']:.3f} / {pc(V['groups']['L1+L2']['detection'])} "
  f"(false alarms {100 * V['groups']['L1+L2']['false_alarm_rate']:.2f}%). "
  f"Tampa: L1 {T['groups']['L1']['auc']:.3f} / {pc(T['groups']['L1']['detection'])}, L2 {T['groups']['L2']['auc']:.3f} / {pc(T['groups']['L2']['detection'])}, L1+L2 {T['groups']['L1+L2']['auc']:.3f} / {pc(T['groups']['L1+L2']['detection'])} "
  f"(false alarms {100 * T['groups']['L1+L2']['false_alarm_rate']:.2f}%, driven by the map layer). "
  "On VeReMi `pos_speed` is the layer whose removal costs the most (`all_but_v2x.pos_speed`), then `field_ranges` and `beacon_rate` (classes 18 and 13-15); on Tampa `pos_speed` and `map_road`. L1 and L2 are complementary: L1 keeps the rate attacks (13 on Tampa, 18 on VeReMi) that L2 misses, L2 adds all the position / speed falsification.\n")
w("## Problems, surprises, open questions\n"
  "- **Tampa ids are per RSU, not per vehicle (new finding, affects S1).** The same BSM (same msgCnt, time, position, speed, heading) appears with a different `coreData_id` at each RSU that heard it (every id occurs at exactly one RSU: 226 ids, 38 RSUs). "
  "So the '226 vehicles' of S1 are (vehicle, RSU) sessions; one physical vehicle can sit in train, validation and test under different ids. Consequences: the S1 vehicle split can leak, validation-calibrated thresholds see copies of test trajectories (test false alarms are slightly optimistic), replay pools can contain copies of the attacker. "
  "S1 numbers are unchanged and S1 was not redone (outside S3); decision for the supervisor: re-split Tampa by (time block, RSU group) or by trajectory identity, or accept and state the limit.\n"
  "- **Deviation from the written design (decided on validation data before any test run, documented in the notes):** the overlap check compares only tracks heard by the same receiver. Without it 30% of genuine Tampa validation messages 'overlap' with their own copy under another id.\n"
  f"- **Map check fails the Tampa false-alarm bound** (above). It was not retuned. Options for the supervisor: report the map layer as validated on validation only and keep it out of the Tampa union; calibrate it per place with more vehicles; or wait for a second Tampa day. The non-map L2 union holds the budget ({pc(nm['test_FA'])}).\n"
  "- **Pre-registered expectations missed** (table above): P1 for classes 18 and 19 (pseudonym per message, no history), P3 (the offset speed classes are detected more than predicted), P4 (VeReMi's own implementation of replay, DoS and GridSybil is inconsistent in itself). Reported, not tuned.\n"
  "- **S20 StaleReplay overlap** (76.9%) is a construction artefact (see above). the L2 kinematic checks on S20 are 0%, as expected: a verbatim old message is kinematically consistent; only freshness (L1) sees it.\n"
  f"- **Per-sender false alarms**: at a 1% message budget {pc(V['per_operating_point']['L2_union']['false_alarm_genuine_senders'])} of the genuine VeReMi senders raise at least one alarm; per-sender decisions need a count rule (>= 3 alarms: {pc(V['sender_ge3_alarms']['L2_union']['false_alarm_genuine_senders'])} of genuine senders) or the L3 tracker. The `delay` numbers are for the first alarm, i.e. optimistic about how fast a *reliable* sender-level decision is.\n"
  "- VeReMi test used once (final run), Tampa test used once. Tampa results are noisy (10 attackers per type): intervals in the tables.\n"
  "- Overpass first returned HTTP 406 (no User-Agent) and a busy-server timeout; the retry with a User-Agent succeeded. Download size 1.4 MB, disk free unchanged (~42 GB).\n")
w("## Proposed next step\nS4 (L3): per-sender Kalman tracker trained on normal motion with innovation tests. It should (a) turn the per-message alarms of L2 into a better sender-level decision, (b) see slow drifts that the consecutive checks cannot (ConstPosOffset, Delayed, consistent replay). "
  "Before S4, the supervisor should decide on the Tampa id issue (re-split) and on the map layer. S3b (acceptance range, sudden appearance) waits for receiver positions (D25 / D13).\n")
(ROOT / "reports" / "WP5_S3.md").write_text("\n".join(lines), encoding="utf-8")
print("written; checks:", [(c[0][:2], c[1]) for c in checks], [(e[0][:3], e[1]) for e in exp])
