# WP8 S6: blame fixes (KITTI gps_can, comma GNSS spoofs)

Date: 2026-11-04    Worker: sonnet (high)    Verdict: PARTIAL (B2, B3, C3, B4 met by the selected candidate A1; B1 NOT MET)

## Summary (<= 40 lines)
- Method: new module `crossdomain/blame31.py` (v3 files untouched): fault isolation by hypothesis scoring on a CHANNEL graph (which measurement channels are faulty), costs fixed a priori, 2-of-5 edge persistence,
  margin 1.0 vs hypotheses with another blamed domain. Candidates: V3 (reference), A1 (channel graph, equal costs), A2 (A1 + attack-surface prior gps 2 < can 3 < lidar 4 < imu 5), A3 (A2 + blame-only accelerometer-anchored inertial edges, K).
- Evaluation: V31_val only (K: 10 drives x 10 phases x 12 families = 1,200 runs, fits on the 13 v3 train drives; comma Chunk_1: 8 val + test routes, 665 windows, fits on the 13 train routes), vehicle block alone with the v3 correlator
  and v3 tick_blame; detection is identical for all candidates (B4 = 0.0 points). Three logged rounds (notes/WP8_v31.md): round 1 pre-registered; round 2 fixed three defects (NaN bug, missing bearing channel, margin rule); round 3 fixed the CAN inertial anchor.
- Results round 3 (blame of detected events, % correct / wrong; 95 % CI over drives / routes):
| row | V3 | A1 | A2 | A3 |
|---|---|---|---|---|
| B1 K gps_can correct / wrong / undec (detected 88 of 100) | 17 [6, 29] / 60 [41, 76] / 23 | 7 [1, 14] / 75 [57, 90] / 18 | 25 [16, 34] / 66 [49, 80] / 9 | 43 [27, 57] / 41 [22, 60] / 16 |
| B3 K 10 vehicle types, mean correct / wrong | 73 [67, 77] / 5 [0, 11] | 79 [73, 83] / 5 [0, 11] | 81 [77, 83] / 11 [6, 16] | 81 [77, 83] / 11 [6, 16] |
  - B1 (K gps_can wrong <= 25, correct >= 40): V3 17 / 60; A1 7 / 75; A3 43 [27, 57] / 41 [22, 60] -> NOT MET for every candidate (A3 meets correct only).
  - B2 (comma GNSS drift / meaconing / doppler mean correct >= 60, wrong <= 15, each wrong <= 25): V3 0 / 0 (100 % undecided); A1 77 [69, 86] / 0 [0, 0]; A2 88 / 0 -> MET by A1 (accel_drift, reported only: 99 / 0).
  - B3 (K single-domain, equal weight per type, correct >= 75, wrong <= 10): V3 73 / 5 (not met on this reduced evaluation); A1 79 / 5; A2, A3 81 / 11 -> MET by A1.
  - C3 (comma CAN types + gnss_can correct >= v3 - 5): 80 vs 80 -> met. B4: detection change 0.0 -> met.
- Selected (registered rule: most rules met, 4 of 5): A1. A3 is a labelled alternative, not adopted: it halves the wrong rate of gps_can but fails B1 and costs B3 (lone LiDAR scale / bias mis-blamed 28 - 35 %).
- Regression: `fusion.system.load_system(2)` reproduces the stored v3 fixture exactly (max |diff| <= 1e-12); fusion/ and the v3 cross-domain files have an empty `git diff v3.0`; full test suite passes (log results/WP8/logs/S6_tests.log).

## Acceptance rules (written before the numbers, notes/WP8_v31.md "S6 round 1", amendment A, "round 2 plan", "round 3 plan")
B1-B4 as in section 2 of the notes, plus C3 and the evaluation protocol of round 1. Every round's plan was committed before its numbers (commit hashes in git log, journal lines in notes/WP8_journal.md).

## What was done
- Code: crossdomain/blame31.py, tools/WP8_S6_{kitti,comma,eval,table,fixture}.py, tests/v31/test_s6_{blame31,regression}.py.
- Data (all V31_val or v3 train; G1 guard on every input): data_extra/cache_v3/WP8/S6/ (not committed). Results: results/WP8/S6/{r1,r2,r3}_eval.json, regression_fixture.json; scores (rule 6, per run per tick edge scores, alarms, labels, blame of every candidate): results/WP8/scores/S6/{kitti,comma}_val_{r1,r2,r3}.npz (1.2 MB total).

## Results (round 3, copied from results/WP8/S6/r3_eval.json via tools/WP8_S6_table.py)
Evaluation r3 (V31_val, vehicle block; K runs 1200, C runs 665); blame of detected events, % correct / wrong / undecided; 95 % CI over drives / routes in brackets

| row | V3 | A1 | A2 | A3 |
|---|---|---|---|---|
| B1 K gps_can correct / wrong / undec (detected 88 of 100) | 17 [6, 29] / 60 [41, 76] / 23 | 7 [1, 14] / 75 [57, 90] / 18 | 25 [16, 34] / 66 [49, 80] / 9 | 43 [27, 57] / 41 [22, 60] / 16 |
| B3 K 10 vehicle types, mean correct / wrong | 73 [67, 77] / 5 [0, 11] | 79 [73, 83] / 5 [0, 11] | 81 [77, 83] / 11 [6, 16] | 81 [77, 83] / 11 [6, 16] |
| K drift (det 85) | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 |
| K accel_drift (det 87) | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 |
| K doppler_spoof (det 84) | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 |
| K meaconing (det 79) | 100 / 0 / 0 | 99 / 0 / 1 | 99 / 0 / 1 | 99 / 0 / 1 |
| K lidar_scale (det 66) | 67 / 5 / 29 | 83 / 2 / 15 | 64 / 35 / 2 | 64 / 35 / 2 |
| K lidar_bias (det 94) | 61 / 2 / 37 | 68 / 1 / 31 | 57 / 29 / 14 | 59 / 28 / 14 |
| K lidar_yaw (det 11) | 0 / 45 / 55 | 0 / 45 / 55 | 0 / 45 / 55 | 0 / 45 / 55 |
| K can_scale (det 69) | 62 / 0 / 38 | 72 / 1 / 26 | 99 / 0 / 1 | 99 / 0 / 1 |
| K can_offset (det 82) | 59 / 1 / 40 | 74 / 1 / 24 | 91 / 1 / 7 | 91 / 1 / 7 |
| K can_freeze (det 94) | 80 / 1 / 19 | 88 / 1 / 11 | 97 / 0 / 3 | 97 / 0 / 3 |

| row (comma) | V3 | A1 | A2 |
|---|---|---|---|
| B2 GNSS drift / meaconing / doppler mean correct / wrong | 0 [0, 0] / 0 [0, 0] | 77 [69, 86] / 0 [0, 0] | 88 [83, 93] / 0 [0, 0] |
| C drift (det 45 of 70) | 0 / 0 / 100 | 69 / 0 / 31 | 69 / 0 / 31 |
| C accel_drift (det 70 of 70) | 0 / 0 / 100 | 99 / 0 / 1 | 99 / 0 / 1 |
| C doppler_spoof (det 68 of 70) | 0 / 0 / 100 | 91 / 0 / 9 | 94 / 0 / 6 |
| C meaconing (det 70 of 70) | 0 / 0 / 100 | 70 / 0 / 30 | 100 / 0 / 0 |
| C can_scale (det 70 of 70) | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 |
| C can_offset (det 70 of 70) | 100 / 0 / 0 | 100 / 0 / 0 | 99 / 1 / 0 |
| C can_freeze (det 70 of 70) | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 |
| C can_bus (det 70 of 70) | 0 / 0 / 100 | 0 / 29 / 71 | 0 / 100 / 0 |
| C gnss_can (det 70 of 70) | 100 / 0 / 0 | 100 / 0 / 0 | 100 / 0 / 0 |
| C3 CAN types + gnss_can mean correct | 80 | 80 | 80 |

Rules met (B1 B2 B3 C3 B4): V3: B1=n B3=n B2=n C3=Y B4=Y; A1: B1=n B3=Y B2=Y C3=Y B4=Y; A2: B1=n B3=n B2=Y C3=Y B4=Y; A3: B1=n B3=n B2=Y C3=Y B4=Y

## Problems, surprises, open questions
- B1 NOT MET. Physics: with three speed sources (GPS, LiDAR odometry, CAN) a coordinated GPS + CAN lie is the same graph as a lone LiDAR fault; the only independent fourth witness is the accelerometer. In 8 - 50 s runs whose cross alarm starts 3 - 4 s after the onset
  the accelerometer-anchored edges arrive late (A3 43 % correct); the attack-surface prior then trades gps_can against lone LiDAR faults (B3). The simulated accelerometer noise (white 0.05 m/s^2, bias 0.01) is an assumption.
- The evaluation is the vehicle block alone (no filler domains): the 70 - 88 % wrong blame of the M3 composites for comma GNSS came from the fallback of tick_blame onto unrelated own alarms; in this evaluation v3 is 100 % undecided there. The fallback is unchanged (S7 must re-measure
  in M3-style composites; with correct cross verdicts the decided majority should now win).
- Prior side effect: A2 turns the symmetric comma can_bus case into 100 % wrong blame (A1: 71 % undecided / 29 % wrong); another reason to select A1.
- K lidar_yaw: only 11 of 100 runs detected; its blame wrong (45 %, same for all candidates incl. v3) is the GPS-domain fallback, not the cross rule.
- Design was shaped by the failures seen in M3 on these drives (now V31_val); fresh numbers come only from H31 in S7 (M4-12 / M4-13).
- Round 1 A3 was invalid (NaN anchor bug) and is reported as such; three rounds were used.

## Proposed next step
Supervisor decision on B1 (accept A3 with its B3 cost, or document gps_can as a symmetric-ambiguity limit); S7 wires `crossdomain.blame31.selected_blamers()` into the runner behind a version flag and scores H31 once.
