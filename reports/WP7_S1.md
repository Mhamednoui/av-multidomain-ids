# WP7 S1: streaming runtime (per-domain runners, Evidence bus, latency)

Date: 2026-10-22    Worker: sonnet (WP7, T2, medium)

## Summary (verdict first)
- **S1 MET** against the rule written in notes/WP7_system.md before any result (A1-A6). Engineering step: no detection rate, no test data, no threshold re-fit.
- **Stream == batch, exactly** (A1 MET): GPS 210 val runs, CAN 6 val captures, V2X 4 val blocks (12 attack classes), cross 360 + 9 runs, LiDAR interim 34 scans: 0 alarm / reason mismatches, max score difference 0.0e+00.
- **Causality by truncation** (A2 MET) and **reset** (A3 MET) hold in every domain. Bus (A5 MET) and interim / placeholder labels (A6 MET) hold.
- **How**: the frozen GPS / CAN detectors are whole-run vectorised causal programs without a step() entry point, and V2X has no saved domain object. The runners keep the stream state and re-score the prefix (GPS per fix, CAN per completed second) or a bounded context table (V2X per message) with the FROZEN code, then take the new sample. Exact by construction, tested. The cross layer is a true per-second step. No folder of another WP was touched; optional follow-up in reports/REQUEST_WP7_incremental_entry_points.md.
- **Latency** (median / p99 ms, this loaded machine, 3 repetitions, spread in results/WP7/S1_tables.md): GPS fix 31.6 / 89.2 (v2 ~0.8; prefix re-score of 16 layers), CAN frame 0.0032 / 0.0084, amortised 0.044 per frame (v2 ~0.05), CAN 1 s window 96.0 / 212.3, V2X message 20.7 / 59.8, cross witness step 6.3 / 15.9, LiDAR interim scan 32.1 / 59.6 (v2 ~23). Network: placeholder in S1 (plumbing 0.0011 ms), replaced by the frozen-domain runner in S1b (section S1b); bus publish 0.8 us. Pre-registered real-time check (p99 < sample period): gps yes, can_window yes, v2x yes, cross_step yes, lidar_interim yes.
- GPS / CAN / V2X latency grows with the length of the run / capture / track so far (tables in S1_tables.md, section 4): these are upper bounds of an incremental implementation, not per-sample costs of one.
- **Built here**: V2X physics-only domain object (WP5 recipe; reproduces S6 layer thresholds to 0e+00 and the S6 validation FA 0.009967), cross runtime-test object (fitted on the WP6 S2b dev cache, in-sample, NOT the WP6 verdict model), LiDAR interim calibration (threshold equals WP3 S1 val_fpr_0.01).
- **Not frozen, so labelled**: LiDAR = WP3 S1 retrained v2 baseline (INTERIM); network = PLACEHOLDER in S1 (M1-NET was not frozen then); replaced in S1b by a runner over the frozen network domain.
- **Findings**: (1) cross: with bounded buffers the interval means differ by ~1e-13, which flips one ECDF step (3.7e-4 score) when z equals a calibration sample: the default keeps the whole history (bit-identical). (2) v2x.l3.birth_density counts equal-timestamp births that arrive later: a causal stream cannot; 0 equal timestamps in VeReMi validation (counted by the runner). (3) I wrote 210 validation runs for the cross level in the rule; the WP6 S2b cache holds 360 validation-part runs, all were used.
- Files: system/{bus,runner,gps_runner,can_runner,v2x_runner,cross_runner,placeholder_runners}.py, tests/system/ (21 tests), tools/WP7_S1_*.py, results/WP7/S1_*.json, S1_tables.md, notes/WP7_system.md, notes/WP7_brief.md.

## Goal of the step
Streaming runtime (workpackages/WP7_system.md S1): per-domain runners with all layers (stateful, reset per drive / capture), latency per sample and per domain against the v2 references, started early by the supervisor (ORCHESTRATOR 2026-10-22): GPS / CAN / V2X frozen, cross-domain from WP6, network when frozen (not yet), LiDAR placeholder = WP3 S1 baseline.

## Acceptance rule (notes/WP7_system.md, section 'S1 acceptance rule', written 2026-10-22 before any result)
A1 stream == batch (same count, ids, alarms, reasons; score diff <= 1e-9, LiDAR 1e-6) on validation data with minimum sizes; A2 truncation causality (>= 3 cuts); A3 reset; A4 latency median / p95 / p99 over >= 3 repetitions with spread, real-time check p99 < sample period (reported, not hidden); A5 bus; A6 labels. Verdicts: results/WP7/S1_acceptance.json.

## What was done
- Code: `system/` (bus, runner base + latency log, 5 runners + network placeholder), `tests/system/`. Frozen objects used: results/WP1/frozen_gps, results/WP2/s7_domain, results/WP3 retrained baseline (cache_v3), WP6 consistency code. Objects built: results/WP7/frozen_v2x, frozen_cross, frozen_lidar_interim.
- Data (validation only): KITTI val drives 0011 0035 0027 (WP1 stream, 210 runs; WP6 S2b cache val part); ROAD val captures (attack instance 2 + ambient val); VeReMi validation time blocks 1 3 4 6 (held-out types removed); WP3 S1 cache val drives. No test split was read.
- Run: tools/WP7_S1_run_all.sh (gps, can, cross, v2x, lidar one after the other so latency runs do not overlap), WP7_S1_bus.py, WP7_S1_report.py. Machine: shared, other workers running; latency numbers are an upper envelope.

## Results
Full tables: results/WP7/S1_tables.md (exactness, truncation / reset, latency with spreads, growth with context, objects, bus). Verdicts:

| Rule | GPS | CAN | V2X | Cross | LiDAR (interim) |
|---|---|---|---|---|---|
| A1 exactness | MET | MET | MET | MET | MET |
| A2 truncation | MET | MET | MET | MET | MET |
| A3 reset | MET | MET | MET | MET | MET |

| Latency (ms) | median | p95 | p99 | v2 reference |
|---|---|---|---|---|
| GPS fix | 31.6284 | 71.6240 | 89.2196 | ~0.8 ms |
| CAN frame | 0.0032 | 0.0057 | 0.0084 | ~0.05 ms per frame |
| CAN window | 95.9791 | 185.9791 | 212.2832 | - |
| V2X message | 20.6578 | 46.8913 | 59.7581 | - |
| Cross step | 6.3013 | 13.7202 | 15.9267 | - |
| LiDAR scan (interim) | 32.1404 | 51.6080 | 59.5723 | ~23 ms per scan |

Acceptance: MET.

## Ablation row(s)
None (engineering step: no detection numbers).

## Problems, surprises, open questions
- GPS / CAN / V2X per-sample cost is far above the v2 numbers because the frozen code has no incremental entry point (prefix re-score). Decision for the supervisor: accept as upper bound, or assign incremental entry points to the domain owners (reports/REQUEST_WP7_incremental_entry_points.md). Not needed for S2 on short streams.
- The V2X domain object and the cross object are WP7 re-creations of recipes (no saved frozen file existed): if WP5 / WP6 later save official objects, swap them in (runners take the object as argument).
- Network: wired in S1b to the frozen domain (section S1b); its windows close late (details['final']), the runner emits a flow when its window has closed.
- The CAN wheel-speed MotionEstimates are emitted by the CAN runner (pop_motion); gps / lidar / imu MotionEstimates come from their producers upstream. Feeding them to the cross runner end to end on live streams is S2.

## Proposed next step
S2 (simulation v3: all domains as real streams, persistent attacks, coordinated scenarios, first-alert delay) once the supervisor approves S1; it needs the NET and LiDAR domains frozen to be more than a plumbing test.

## S1b: network runner over the frozen network domain, and the equal-timestamp count (2026-10-24)

- **S1b MET.** `system/net_runner.py NetworkRunner` wraps the frozen `network/domain.py` (stack H, results/WP4/s7_domain, M1_NET section 9); the S1 placeholder is replaced (kept as NetworkPlaceholderRunner, unused).
- Stream == batch on D10 VALIDATION: 54420 flows in 4 thirty-minute slices (6 traffic families), 0 alarm mismatches, 0 reason mismatches, max score difference 0.0e+00 (combined and per-layer). Truncation 12 checks identical, reset identical. D10 test not read.
- **Semantics**: the frozen layers score a flow by its minute cell / 5-minute bin, so a flow's Evidence is final only when its window has closed. The runner appends flows and, when a flow of a later 5-minute bin arrives, re-scores the prefix and emits the flows of the closed bins (details['final'] = True); flush() emits the rest like the batch. The Evidence delay is therefore up to ~5 minutes of flow time (a property of the domain, not of the runner).
- **Latency** (this loaded machine, 3 repetitions): amortised 0.677 ms per flow (range 0.642-0.706; v2 ~1 ms), a push, all calls pooled 0.4641 ms median (mostly append + timestamp parsing), a bin-closing push 354 ms median / 1340 ms p99 (re-scores the whole buffer; grows with the capture, see S1_tables.md section 7). Repetition 3 overlapped with a unit-test run.
- **Equal-timestamp births (counting only, no scoring)**: VeReMi val: 0 non-causal pairs of 9477 births (0 messages share a timestamp); VeReMi test: 0 non-causal pairs of 26787 births (0 messages share a timestamp); Tampa val: 0 non-causal pairs of 10 births (0 messages share a timestamp); Tampa test: 0 non-causal pairs of 9 births (0 messages share a timestamp). So the non-causal use of equal-timestamp births in v2x.l3.birth_density is zero on VeReMi (validation and test) and Tampa v2 (genuine frame of validation and test vehicles); it would appear only on data with coarse timestamps.
- Tests: tests/system/test_net_runner.py (3, one on the frozen domain and a D10 validation slice). Files: system/net_runner.py, tools/WP7_S1b_{net,ties,report}.py, results/WP7/S1b_net.json, S1b_ties.json.
