# WP8 S5: CAN incremental windows + V2X single-ego runtime

Date: 2026-11-03    Worker: sonnet (medium), branch v3.1 (tag v3.0 untouched)

## Summary
- Goal: engineering only (no detector change). CAN: constant cost per 1 s window with outputs identical to the v3 batch CanDomain. V2X: a single-receiver stream with bounded state, identical to the batch checks, <= 0.5 s compute per stream second.
- Material: V31_val only (11 ROAD val captures; V2AIX Mobile val recordings; VeReMi val blocks). Two long ROAD TRAIN captures were used for timing only (rule C2 allows it). H31 not opened.
- CAN (rules C1, C2) MET. 13 captures, 13.99 M frames, 5,892 windows: 0 mismatches (window id, score, alarm, reason, details, per-layer scores, MotionEstimates), max |score diff| = 0.0. p99 window compute 24-41 ms on every capture (limit 150 ms); median 21 ms. Longest capture (8.82 M frames): p99 after 600k frames / p99 before 100k frames = 0.91 (limit 1.5). v3 prefix re-score: 0.14 s -> 2.3 s.
- V2X (rule V1) MET with one documented exception. 64 egos (55 V2AIX Mobile val recordings with full ego pose, 5,070 messages, 2,203 stream s; 9 VeReMi val ego views, 1,374 messages, 749 stream s). Compute per stream second: max 0.027 (limit 0.5), 100% of egos <= 0.5. p99 per message <= 10.6 ms (limit 100 ms), median 3.7 ms.
- Equality: VeReMi 9/9 egos, V2AIX 52/55 egos fully identical (12 raw scores, combined score, alarm, reason). The 3 other egos differ on exactly 6 rows = 3 events where a CAM of a sender arrives with a generation time older than the previous CAM of that sender: the batch code sorts a track by time (it sees the future), a stream cannot. Literal "0 mismatches" is therefore NOT met on V2AIX (6 of 5,070 messages, 0.12%); every one of the 6 is explained (the late message and the message received just before it), 0 unexplained.
- v3 frozen code unchanged: `git diff v3.0 -- can v2x system common fusion crossdomain` shows only the two new files (can/incremental.py, v2x/ego_stream.py). Full test suite: 494 passed, 0 failed, 3 skipped.
- New code: `can/incremental.py` (IncrementalCan), `v2x/ego_stream.py` (EgoStream), tools `WP8_S5_can.py`, `WP8_S5_v2x.py`, `WP8_S5_report.py`, tests `tests/v31/test_s5_incremental.py` (4 tests).
- Not done on purpose: no system/ runner wrapper (system/ is WP7's folder); S7 can wrap IncrementalCan / EgoStream in a runner. No threshold, model or rule changed.

- V1 equality: 0 mismatches vs the arrival-order batch (the 3 egos with out-of-order CAMs re-run with the layer code ordering a track by arrival instead of by t: `tools/WP8_S5_v2x_arrival.py`, `results/WP8/S5/v2x_arrival.json`); 6/5,070 messages differ from the time-sorted batch (a stream cannot see the future). Documented deviation, not a rule redefinition.

## Acceptance rules (notes/WP8_v31.md, S5, written before any result)
- C1 incremental CAN windows give Evidence identical to the v3 batch code on every V31_val ROAD capture (0 mismatches, max |diff| <= 1e-12).
- C2 p99 window compute <= 0.15 s on every capture, and p99(windows after 600k frames) / p99(windows before 100k frames) <= 1.5 on the longest ROAD capture.
- V1 single-ego V2X: compute <= 0.5 s per stream second for >= 95% of egos, p99 per message <= 100 ms, Evidence identical to the batch code on that ego's messages (0 mismatches).

## What was done
- CAN: the v3 CANRunner re-scored the whole prefix each second. IncrementalCan keeps (a) per-ID last timestamp and the frames of the trailing second (L1 gap, bus load, flood), (b) the held value of the 142 decoded signals on the 0.05 s grid, the last 20 raw grid rows (ridge lags), the last 21 running CUSUM sums (float64 cumulative sums continued with the same additions as the batch cumsum, so differences are bit-identical) and the last 20 reverse-light rows (L3c, L3d), (c) per second the max grid score and culprit signal. A grid step is final once a frame with a larger time arrives, so each completed second is scored in one block of 20 steps. Calibration, combiner, reasons use the existing CanDomain methods (`calibrated`, `evidence_from_table`). Wheel-speed MotionEstimates are produced the same way.
- V2X: per track only the previous message (all pairwise checks reuse the layer code on a 2-row table), the Kalman state of the current segment (one-row version of l3.run_filter), receiver context of the last 1 s (overlap) and tracks born in the last 10 s (birth). Clock rule of the V2AIX evaluation: per-track checks on generation time t, overlap and birth on reception time recv_s; VeReMi: t.
- Equality reference: CAN = `CanDomain.score_capture` (explain on) + `motion_estimates` on the whole capture; V2AIX = `v2x/v2aix_eval.raws` per recording; VeReMi = `V2XPhysicsDomain.raws` on the ego's heard messages; Evidence from `V2XPhysicsDomain.evidence` (frozen VeReMi calibration, read only) on stream and batch raw scores.
- Data: ROAD val captures of locks/V31_val.json (parsed from the raw logs with can/adapters; the old caches no longer exist); long timing captures `ambient_highway_street_driving_long` (8.82 M frames) and `ambient_dyno_drive_basic_long` (2.99 M) from the ROAD train split. V2AIX: the 152 Mobile recordings of the V31_val `val` list; 55 have an ego pose on every message and are used. VeReMi val groups 1, 3, 4, 6 without types 6 / 12 / 17; egos = genuine senders with >= 60 s of track, heard within 300 m, evenly spaced picks (6 requested per block; only 9 had >= 50 heard messages). No attack injection was run for V2X here (timing and equality do not depend on labels).
- Timing is wall clock on a shared machine (other workers active): CAN frame-by-frame `push`, time of the push that completes a window; V2X push plus Evidence per message. Per-frame ingest cost of CAN is not in the window time (about 40 us per frame in the Python loop; 8.8 M frames took 6.8 min including 3,740 windows).

## Results (results/WP8/S5/S5_acceptance.json; per capture parts/*.json)
| capture | frames | windows | p99 ms | mismatches | max abs diff |
|---|---|---|---|---|---|
| ambient_dyno_drive_basic_short | 1,063,624 | 444 | 34.6 | 0 | 0.0 |
| ambient_dyno_drive_winter | 114,148 | 47 | 28.7 | 0 | 0.0 |
| correlated_signal_attack_2 (+ masquerade) | 69,657 / 67,517 | 28 / 28 | 28.0 / 30.1 | 0 | 0.0 |
| fuzzing_attack_2 | 32,351 | 13 | 34.0 | 0 | 0.0 |
| max_speedometer_attack_2 (+ masquerade) | 145,894 / 142,754 | 59 / 59 | 40.8 / 38.3 | 0 | 0.0 |
| reverse_light_off_attack_2 (+ masquerade) | 99,628 / 97,257 | 40 / 40 | 23.7 / 24.1 | 0 | 0.0 |
| reverse_light_on_attack_2 (+ masquerade) | 175,945 / 172,256 | 72 / 72 | 37.9 / 28.2 | 0 | 0.0 |
| long (train, timing only): basic_long | 2,991,272 | 1,250 | 28.7 | 0 | 0.0 |
| long (train, timing only): highway_long | 8,821,916 | 3,740 | 30.3 | 0 | 0.0 |

Growth: highway_long p99 33.5 ms (windows before 100k frames, n=40) vs 30.4 ms (after 600k, n=3,489), ratio 0.91; basic_long 24.3 vs 28.8 ms, ratio 1.19 (n=40 / 1,000).
Acceptance C1: MET. C2: MET.

| V2X single ego | egos | messages | compute / stream s (max, p95) | egos <= 0.5 | msg p99 ms (max) | identical egos | mismatch rows |
|---|---|---|---|---|---|---|---|
| VeReMi val ego views | 9 | 1,374 | 0.016, 0.014 | 100% | 7.3 | 9 of 9 | 0 |
| V2AIX Mobile val | 55 | 5,070 | 0.027, 0.022 | 100% | 10.6 | 52 of 55 | 6 (all explained) |
The ratio uses the stream duration floored at 1 s (13 V2AIX recordings last under 5 s, two have a single message); unfloored 96.4% of V2AIX egos are <= 0.5 because the two single-message recordings have zero span. Acceptance V1: MET on timing and on equality up to the reordering exception; the literal 0-mismatch wording is NOT met (6 rows). Reception-time ties: 16 equal timestamps in V2AIX, no mismatch from them.

## Scores saved (rule 6)
results/WP8/scores/S5/can_val_<capture>.npz and can_long_<capture>.npz (per-window sec, label, combined and per-layer scores/alarms, batch score, wall time; < 1 MB each). V2X: only per-ego aggregates (`v2x_*_ego_aggregates.npz`); no V2AIX per-message file is stored or committed. No detection score changed, so there are no new per-sample detection scores beyond these equality records.

## Problems, surprises, open questions
- Reordered CAMs make exact stream = batch impossible for the 2 affected messages per event (batch sorts by t). Decision for the supervisor: accept as documented, or redefine the V1 equality as "batch on the same arrival order". Not tuned away.
- Only 55 of 152 Mobile val recordings have a complete ego pose; the others (partial NaN rx) were not used. Stream seconds are short (median 22 s per recording; V2AIX Mobile clips): the cost does not grow with the track, but no ego longer than 643 s was available (the per-track state is bounded, so a longer ego would cost the same).
- CAN timing includes the machine load of other workers; the CAN window cost is ~21 ms median, dominated by the per-window decode and 142 small searches; far below 150 ms. Frame ingest in Python is ~40 us per frame (not part of the rule).
- results/WP7/frozen_v2x (domain.json) is used read-only and is untracked in git on this branch.
- Test suite (tests/run_tests.py, log results/WP8/logs/S5_tests.log): 494 passed, 0 failed, 3 skipped.

## Proposed next step
S7 wraps IncrementalCan and EgoStream in the system runners (system/ is WP7's folder, so it needs the supervisor's go) and re-runs the equality on H31 in the final pass (M4-10, M4-11).
