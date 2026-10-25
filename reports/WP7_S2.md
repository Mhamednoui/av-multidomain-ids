# WP7 S2: Simulation v3 on the frozen system v2 (closes M3)

Date: 2026-10-25    Worker: sonnet (WP7, high, T3)

## Summary (verdict first)
- **Verdict: acceptance rows A1-A5 MET, system bounds B1, B2, B3, B6 NOT MET, B4, B5, B7 MET. M3 = NOT MET (8 of 12 rows).** The numbers are in `results/WP7/S2_acceptance.json`, `S2_results.json`, tables in `results/WP7/S2_tables.md`. The rule was written in `notes/WP7_system.md` ("S2 start") before any test stream was run; the expectation written there (B1, B2, B3 fail, B6 close for C) came out as predicted.
- **Frozen**: `fusion.system.load_system(2)` (sha256 b090485d1597... of results/WP6/system_v2.pkl, thresholds K 0.69634, C 0.70317, correlator m2 w5 gap15, majority_decided, SAFE_STOP needs 2 domains). Nothing tuned. **5th scoring of fusion test data** (S3, S4, S5, S5b before); one run; seed `[42, 77, 2, ord(family)]`.
- **What was run**: every domain's TEST material went through its S1 runner sample by sample (GPS fixes, LiDAR scans at their real cost, 4.0 M ROAD CAN frames, 709,430 VeReMi messages, 585,951 D10 flows, KITTI / comma witness streams). 213,744 attack composites (K 107,229 / C 106,515; 134 attack types, ALL test episodes, no random subset) and 32 clean timelines (16 per family, 7.93 h each) were replayed through the new `FusionRunner` second by second (frozen system, availability times, correlator, response).
- **Headline (test, one run)**:

| | K (KITTI based) | C (comma based) | bound |
|---|---|---|---|
| clean tick false alarms (B1) | 3.31% [2.82, 4.15] | 6.15% [5.16, 7.34] | <= 3% |
| alert events per clean hour (B2) | 18.4 [16.3, 20.4] | 27.5 [24.5, 30.6] | <= 10 |
| WARN / DEGRADE / SAFE_STOP per clean hour | 12.9 / 5.2 / 0.38 [0.10, 0.72] | 13.7 / 12.1 / 1.64 [0.27, 2.49] | SAFE_STOP <= 1 (B6) |
| mean event detection over single-domain types (B3) | 60.8% [58.8, 62.9] (55 types) | 95.5% [92.8, 98.3] (46 types, not informative: 27 events per clean hour) | >= 70% |
| held-out (zero-day) types (B4) | 71.1% [65.0, 75.8] (12 types) | 92.9% | >= 60% |
| blame of detected events, equal weight per type (B5) | 78.5 / 9.7 / 11.8% correct / wrong / undecided | 86.9 / 8.9 / 4.2% | >= 75 / <= 10 |
| events with an explanation (B7) | 201,637 of 201,637 (all attack composites and timelines) | | 100% |

- **Streams equal batch end to end (A1)**: FusionRunner final alarms and events equal `SystemV2.run` for all 213,744 + 32 composites (0 mismatches). **Live co-simulation (A3)**: 6 composites (five of them with GPS, cross, LiDAR, CAN and V2X live at once, one network block, one comma window) equal the replay, 0 mismatches; two had alert events (11 s KITTI gps_can, 120 s comma gnss_can), four had none (limit, see below).
- **Real time (A4)**: LiDAR 1.98 s per scan on a lightly loaded machine (19x slower than the 0.103 s scan period; 3.98 s median under the 13-process load of the passes, 39x): **does not keep up**. V2X whole-block stream (all senders) 1.9 compute s per stream s on the loaded machine: does not keep up; one ego hears 7.4 messages/s (p95 12.8). CAN windows 0.14 s median below 100k frames, 2.3 s above 600k frames (prefix re-score grows with the capture): fails the 1 s period on long captures. GPS 58.5 ms median per fix (p99 137 ms), cross witness step p99 16 ms, network flow push 1.2 ms (stall 1.4 s median, 7.7 s max at each 5-minute bin close): keep up.
- **Network delay**: the real 5-minute bin plus the one-minute hold gives a visible-tick delay of 66 s median, 242 s max; available delay from the true attack start 120 s median over the 10 K network types (82 s for C), event detection 93.3% (K) / 83.3% (C).

## Goal of the step
Simulation v3 (workpackages/WP7_system.md S2): all five domains as real streams, persistent attacks starting at block starts, coordinated multi-domain scenarios, first-alert delay per block, representative attack sampling (all test episodes); LiDAR at its real cost; the motion-critical SAFE_STOP rule only as a labelled design variant.

## Acceptance rule (notes/WP7_system.md "S2 start", written 2026-10-25 before any S2 test pass)
A1 stream integrity (0 mismatches), A2 coverage (every enumerated test episode is a composite), A3 live co-simulation (>= 6 composites equal replay), A4 timing table from measured passes, A5 completeness, B1-B7 = the M2 / S5b bounds, M3 = all 12. Verdicts: `results/WP7/S2_acceptance.json` (make_report slot "M3 simulation").
One interpretation choice made after seeing the pooled value: B5 is judged with equal weight per attack type (V2X episodes are 80% of the composites; the pooled K blame is 99.4% correct / 0.06% wrong / 0.57% undecided, dominated by V2X). The stricter number decides; both pass.

## What was done
- New code (WP7 files only): `system/lidar_runner.py` (frozen LiDAR domain as a runner), `system/fusion_runner.py` (1 Hz fusion with availability times, event timeline, `replay`), `tools/WP7_S2_{lib,lidar,veh,can,net,v2x,sim,sim_main,live,report,finalize,check_can,check_lidar}.py`, tests `tests/system/test_{fusion_runner,lidar_runner,s2_sim}.py` (10 tests).
- Passes (caches `../data_extra/cache_v3/WP7`, 288 MB): LiDAR 63 jobs (7 clean drives, 6 per-scan kinds x 7 drives, 168 episodes; 13,024 scans); KITTI GPS + cross (7 drives x 10 phases x 12 families, onset at fix 3); comma 304 windows (16 clean + 288 attacked, onset +3 s); ROAD CAN 15 captures; VeReMi 10 blocks, ALL 3,108 genuine ego views (6,209 series); D10 31 blocks.
- Integrity of the passes against the M2 packs on identical input (`S2_check_*.json`): GPS 350 runs max score diff 0.0, 0 alarm mismatches; cross 70 runs, 1512 ticks, 0.0 / 0 / 0; CAN 15 of 15 captures 0.0 / 0; network 17 of 18 compared blocks 0.0 (block 2017-07-03|0: 60 alarm ticks and a 0.056 score difference in one minute, an ordering effect at equal flow timestamps in the largest block); LiDAR clean 7 drives: 0 alarm mismatches, score differences 0.0 on 4 drives and up to 0.11 on 3 (first scan of a drive, tick maximum); V2X: stream scores equal batch (S1), 0 equal-timestamp ties.

## Results
Full tables (per type: detection, delays, blame, response, time to DEGRADE / SAFE_STOP): `results/WP7/S2_tables.md`. Summary:

| attacked domain (K, equal weight per type) | types | event detection | first-alarm delay (ticks, median) | available delay (s, median) |
|---|---|---|---|---|
| GPS (4 types) | 4 | 69.6% | 6 | 7 |
| cross-only (LiDAR-odometry / CAN wheel spoofs) | 6 | 32.1% | 9 | 12 |
| LiDAR | 6 | 9.5% | 1 | 4 |
| CAN (ROAD, 11 captures) | 11 | 45.5% | 1 | 4 |
| V2X | 18 | 76.8% | 1 | 4 |
| network | 10 | 93.3% | 15 | 120 |

- LiDAR single-return phantoms: per scan 3.6% event detection (28 composites), persistent episodes 0.6% (168), IntensitySpoof 42.9%, PointDrop 0%. The 30-scan episodes last 3 s; the correlator needs two alarm ticks.
- Coordinated: KITTI gps_can detected 71.4% but blamed on the honest sensor 70% (correct 12%), SAFE_STOP 48% of the composites; comma gnss_can 100% detected, correct blame 100%, SAFE_STOP 91%; can_bus blame wrong 53%. Two-domain blocks on the same car: CAN attack + GPS attack 11 of 11 detected (SAFE_STOP 6), CAN attack + PointDrop 10 of 11 (blame correct).
- Response (K single-domain detected events, worst response): WARN 10.9%, DEGRADE 89.0%, SAFE_STOP 0.08%. Clean: SAFE_STOP per hour 0.38 (K) / 1.64 (C). **Design variant** (second domain must be GPS, LiDAR, CAN or cross): C clean 0.63 per hour [0.0, 0.93] (bound would be met), K unchanged (0.38); on attacked C composites it lowers the worst response SAFE_STOP share (can_offset 94% -> 78%, can_freeze 84% -> 69%, can_bus 31% unchanged), at the price of fewer SAFE_STOP for real CAN spoofs; per-type columns in the tables. Not the headline.
- Clean-event diagnosis (K): events involve can in 89, v2x 82, gps 63, lidar 42, cross 41, network 26 events; blame undecided 46, can 50, gps 23, network 16, v2x 8, lidar 3 (of 146).
- v2 side by side (not like-for-like): v2 accuracy 91.67%, false alarms 1.90%, recall 84.17% on 7,800 rows; per block flagged GPS 96.8%, CAN DoS 100%, network DoS 99.8%, LiDAR phantom 8.3% (first alert after 38 rows), CAN + GPS 100%, stealthy CAN + LiDAR 100%, normal blocks 0.2-4.3%. v3 analogues: GPS 69.6% event / 45.7% of attack ticks flagged; network DoS 100% (7 composites, available delay 165 s); LiDAR phantom 3.6% per scan, 0.6% episodes; CAN + GPS 100%; CAN + PointDrop 91%; clean 3.31% tick FA and 18.4 events per hour. v2's phantom / box-cloud attacks added multi-return clouds that a single-return HDL-64E cannot produce, v2 scored single rows with a supervised meta-classifier, long blocks and random halves; v3 uses persistent drives, label-free fusion, group splits. v3 is not better than v2 on v2's own view.

## Ablation row(s)
None added (S5b ablation stands: `results/WP6/s5b_test.json`); the correlator-off and rule variants were not re-run (system frozen).

## Problems, surprises, open questions
1. **Alert rate**: 18-27 events per clean hour, 3.3-6.2% tick FA: the M2 problem is unchanged on streams (K FA 3.31% vs 3.50% in S5b, events 18.4 vs 17.5). With the network 5-minute delay modelled, nothing improved or worsened measurably.
2. **LiDAR**: not real time (19x) and nearly blind to single-return phantoms; the coupling to OXTS pose was not re-run.
3. **V2X** and CAN long captures: whole-stream cost grows (prefix re-score); an incremental entry point (reports/REQUEST_WP7_incremental_entry_points.md) is the fix, the supervisor has not assigned it.
4. **Short composites carry no network Evidence** (bin longer than the block); network attacks run as long blocks with clean vehicle domains chained under them.
5. Live coverage: 4 of 6 live composites had no alert event (the selection took the first candidate with an event in the replay, falling back to the first); alarms and per-tick values still equal.
6. Network ordering effect at equal flow timestamps in the largest block (see above); LiDAR clean-pass tick differences in 3 drives.
7. Timing numbers come from a machine with 13 python processes; the LiDAR figure on a lightly loaded machine is 1.98 s.

## Proposed next step
Supervisor review; M3 closed NOT MET; RESULTS_v3.md to be regenerated by the orchestrator (`python make_report.py`); then S3 sign-off / S4 (publication, user approval needed).
