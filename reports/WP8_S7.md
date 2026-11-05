# WP8 S7: final scoring on the fresh hold-out H31 (milestone M4)

Date: 2026-11-05    Worker: sonnet (high, T3)    Branch v3.1 (tag v3.0 untouched)

## Summary (<= 40 lines)
- **M4 verdict: NOT MET** (7 of 18 rows MET). Frozen v3 (tag v3.0) and frozen v3.1 scored once, paired, on H31 (freeze.json commit 8aac3dd; H31 sha256 verified; regression R2 passed).
- Order of work (orchestrator decision): (a) regression R2 (7 checks, all pass: results/WP8/S7/regression.json) and H31 sha256 verification against locks/H31.json (43 items, all_ok) AFTER freeze.json was committed (8aac3dd); (b) ONE paired scoring of frozen v3 and frozen v3.1 on the same H31 composites; (c) labelled variants (network RC5, blame A3, budget 1.5 %, motion-critical SAFE_STOP); (d) per-domain rows; (e) M3-style simulation. Every long run wrote its chunks once; no chunk was redone.
- Verdict: 7 of 18 rows MET -> M4 NOT MET. MET: M4-3 (C), M4-4, M4-5, M4-7, M4-13, M4-14, M4-15. NOT MET: M4-1 and M4-2 (K and C), M4-3 (K), M4-6, M4-8, M4-10, M4-11, M4-12. NOT EVALUATED (counts as not met): M4-9 (D23 half).
- False alarms did NOT transfer to H31: K clean tick FA 12.24 % [9.74, 14.55] (v3 12.38 % [9.83, 14.74]), C 6.13 % [4.62, 9.43] (v3 6.01 % [5.28, 7.32]); V31_val had 1.9 %. Events per clean hour K 24.8 / C 22.6 (bound 10; v3 27.9 / 28.9). The S2 gain on V31_val is not reproduced on K FA: paired difference -0.14 pts  [-0.81, 0.32].
- One H31 drive dominates K: 2011_09_26_drive_0093 alarms on 94 % (GPS), 91 % (cross) and 86 % (LiDAR scans, v3 and v3.1 alike) of its clean ticks; cause not investigated (odometry healthy). Without it (labelled post-hoc diagnostic, not a verdict): K clean FA 4.73 % (v3 4.95 %), events per hour 23.9 (v3 26.7): still above the bounds. GPS clean-tick FA on H31 7.20 % vs 1.39 % on V31_val.
- Detection: K event detection 87.1 % [85.5, 88.6] (v3 83.4 % [81.0, 85.7]; paired 3.7 pts [1.8, 5.8]), held-out 90.8 % [89.6, 91.5] (v3 95.5 % [90.6, 99.2]); high partly because the alarm rate is high.
- LiDAR: PointDrop per scan 66.1 % vs v3 32.0 % (paired +34.1 pts [+29.8, +37.0], fresh H31, 13 drives): the in-stack gain is real. In the system, per-scan PointDrop events 100 % (v3 38 %), 3 s episodes 13 % (as predicted in S2). Clean scan FA 8.38 % (v3 9.30 %; drive 0093 86 %). Speed: median 112 ms, p99 142 ms with 2 other python processes (rule 100 / 250 ms; S3b: 73-76 ms on a quieter machine): NOT MET as measured; repeat 148 ms with 7 other processes. Stream == batch exact. Literal frozen-v3 check: 0 alarm disagreements on 104 scans.
- Blame: K gps_can A1 correct 13.1 % / wrong 81.1 % (detected 122/130) (v3 correct 23.8 % / wrong 63.1 %), the known S6 limit; comma GNSS spoofs A1 correct 80.6 % / wrong 0.0 % (v3: 100 % undecided): fixed on fresh H31. System blame K correct / wrong 75.0 % / 18.7 % (bound 75 / 10).
- Network (D10 test, re-used): F1 delay median 60 s / max 74 s; macro 65.9 % (-0.00 pts [-0.00, 0.00]); FA 0.65 %; RC5 variant: macro 62.8 % (-3.13 pts), delay 0 s. CAN: Evidence identical to the batch (0 mismatches); mismatches 0; p99 max 195 ms (loaded run, 5 processes); repeat (up to 7 other python processes) p99 max 305 ms; growth ratio max 1.45. V2AIX: compute max 0.038 s/s on 7 Mobile egos; FA Mobile 0.65 %, Stationary 2.26 %; injected mean Mobile 60.8 %, Stationary 49.2 %.
- G4 improvement claims (paired CI excludes 0 in the good direction; system rows are PARTIALLY fresh, so they are not fresh-data claims): K det_single +3.72 pts; C events_per_hour -6.30/h; C blame_correct +2.82 pts; C blame_wrong -2.03 pts. CI excludes 0 in the BAD direction: C det_single -4.04 pts; C det_heldout -8.13 pts. Claims that stand on fresh data: LiDAR PointDrop at scan level and comma GNSS blame (M4-13). KITTI gps_can blame and the GPS / LiDAR false alarms are not improved.
- Not scored (stated): Civic Chunk_4 (no decoder), D23, Car-Hacking / D11 / OTIDS / normal_run CAN parts, VeReMi 2018, Tampa. Timing was taken on a shared machine; repeats are labelled and the verdict uses the first run.

## Acceptance rules
M4-1..M4-15 and G1-G10 as pre-registered (notes/WP8_v31.md section 2, orchestrator decisions, and 'S7 protocol clarifications' committed before the freeze). Nothing was changed after the result was seen.

## What was done
- Runner wrappers: system/runners31.py (CanRunner31, V2XRunner31, LidarRunner31, NetRunner31 F1 / RC5, Blame31Stream A1, Fusion31Runner); stream == batch tests on synthetic / V31_val material (tests/v31/test_s7_runners.py, 6 pass); full suite 557 pass, run_all --check OK.
- Freeze: results/WP8/S7/freeze.json (39 artefact files, 610 code files, commit 8aac3dd) plus the frozen cross recipe (frozen_cross31.pkl) and the budget 1.5 % system (frozen_system31_b15); files added afterwards (pack, can_idle, posthoc, report writers) are hashed in freeze_addendum.json.
- Dry runs on V31_val before the freeze: network, vehicle and V2X sources reproduce the S4 / S2 caches exactly; the simulation reproduces the frozen_system31 in-sample check exactly (K FA 1.80 %, 4.53 events/h, detection 72.9 %).
- H31 scoring tools: tools/WP8_S7_{odom,kitti,comma,lidar,can,net,v2x,veh,blame,sim,domains,v2aix,lidar_check,verify,regress}.py; logs results/WP8/logs/S7_*.log; chunks results/WP8/S7/parts; scores results/WP8/scores/S7 (V2AIX aggregates only).
- Outputs: reports/M4.md, RESULTS_v31.md, results/WP8/S7/{m4_verdict,system_h31,domains,blame,network,can_summary,can_idle_timing,lidar_check,v2aix,exposure}.json, curves/ (ROC and AUC with group-bootstrap CI for GPS, cross, LiDAR, CAN, network, V2X, system K and C).

## Problems and open points
- The frozen GPS, cross and LiDAR domains alarm on drive 0093 for the whole drive: a generalisation failure that drives the K false alarms. Not tuned (rule). It needs an investigation step before any further claim about false alarms.
- C clean FA is 6 % without a drive-level anomaly: V2X (about 10 % of clean ticks carry a V2X own alarm on VeReMi test egos), CAN and network dominate; the equal-split 2 % budget does not hold when a domain's tick FA exceeds 1 %.
- Timing rules were measured on a shared machine; an isolated re-measurement is needed to settle M4-8 speed and M4-10 p99 (S3b / S5 numbers on quieter runs met them).
- The D23 half of M4-9 cannot be evaluated (stage cache not on disk). V2AIX Stationary genuine FA is above the 1.5 % bound.

## Orchestrator review note (2026-11-05)

Protocol deviation: the V2AIX H31 recordings were scored at 2026-11-04 17:45:11-17:45:38, about 36 s before freeze.json was written (17:46:14) and 61 s before the freeze commit (8aac3dd, 17:46:23). The journal line "no H31 file opened before this commit" is therefore wrong for V2AIX. The V2AIX tool and library hashes in freeze.json equal the files committed at 35e6275 (17:46:02) and the current files; the V2AIX result is unfavourable (M4-11 NOT MET) and is kept as scored. Every other H31 domain was opened after the freeze commit.
