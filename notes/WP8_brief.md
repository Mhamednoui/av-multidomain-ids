# WP8 brief (<= 60 lines; each worker edits only its own lines)

## S0 (hold-out + pre-registration, worker opus) - REVIEW 2026-11-03
- Locks: locks/H31.json (scored ONCE in S7, by v3 and v3.1), locks/V31_val.json (all S2-S6 choices). Rules: notes/WP8_v31.md (G1-G10, S1-S6, M4-1..15), committed 1eca013.
- H31: KITTI 13 fresh drives (9 same-day + 4 other-day) FRESH; comma Chunk_2 RAV4 + Chunk_4 Civic FRESH; V2AIX 674 unextracted recordings FRESH; CAN / VeReMi re-used + small fresh parts; network RE-USED (exposure 7).
- V31_val = v3 val + v3 test of KITTI / comma Chunk_1 / V2AIX; CAN / NET / VeReMi only their v3 val splits.
- S1: results/WP8/S0/S1_download_list.json (13.0 GB transfer, 17.3 GB disk); tools/WP8_S0_*.py; report reports/WP8_S0.md.
- Pitfalls: V2AIX recordings share site + day with train; Civic wheel speed not at 0xAA; OTIDS / normal_run not in DATASETS.md; never commit V2AIX data or per-message scores.

## P1 (paper analysis, worker sonnet) - REVIEW 2026-11-03
- Output results/WP8/P1/ (tables md/csv, ROC png/pdf), tools/WP8_P1_curves.py, reports/WP8_P1.md.
- GPS AUC 0.895 (row level), det 68.8% @1% FA, 74.7% @5%; LiDAR AUC 0.750 (9 attacks), 18.3% @1%, 38.5% @5%. CAN partial (raw S3 columns). Net: operating-point table only. V2X / fusion: not available without a re-run.

## S5 (CAN incremental + V2X single ego, worker sonnet) - REVIEW 2026-11-03
- Code: can/incremental.py (IncrementalCan), v2x/ego_stream.py (EgoStream), tools/WP8_S5_{can,v2x,report}.py, tests/v31/test_s5_incremental.py; results results/WP8/S5/ (S5_acceptance.json, parts/), scores results/WP8/scores/S5/; report reports/WP8_S5.md. v3 frozen files untouched; suite 494 pass.
- CAN: 13 captures / 14.0 M frames / 5,892 windows, 0 mismatches, max diff 0.0; p99 window 24-41 ms (limit 150); growth ratio 0.91 on the longest (8.8 M frames; limit 1.5). C1, C2 MET.
- V2X: 64 egos (55 V2AIX Mobile val, 9 VeReMi val views): compute <= 0.027 s per stream s (limit 0.5), p99 msg <= 10.6 ms; identical on 61/64 egos; 3 V2AIX egos differ on 6 rows from CAMs received out of generation order (batch sorts by t, stream cannot). V1 MET except literal 0-mismatch (decision for supervisor).
- Pitfalls: results/WP7/frozen_v2x is untracked in git (used read-only); only 55 of 152 Mobile val recordings have a full ego pose.

- S7 owns the system/ runner wrapper for IncrementalCan and EgoStream.

## S4 (network streaming Evidence + unseen Bot, worker sonnet) - REVIEW 2026-11-03
- Code: network/stream31.py (RunningState, Stream31 = Evidence at arrival, Stream31Final = at tick close), tools/WP8_S4_{prep,eval,stream_check,final_check,bot,report}.py, tests/v31/test_s4_{stream,regression}.py; results results/WP8/S4/, scores results/WP8/scores/S4/ (git add -f, npz ignored); report reports/WP8_S4.md. v3 files untouched; WP4 caches were deleted -> D10 rebuilt (counts equal), only train+val loaded.
- Val (D10, 11 families): v3 macro 58.3 / FA 0.96 (reproduced exactly from the stored WP4 S7 val view). Running statistics alone (R5/R2/R1) fail N2 (-7.6/-11.8/-11.2). With one-tick carry RC5: 55.4 (-2.90 paired, margin 0.10, CI excludes 0), FA 0.93, delay 0 -> chosen by the pre-registered rule. F1 (tick-final, TRW 1 min): 57.9 (-0.34), delay 60 s median / 76 s max (v3 flow level 120 / 307 s).
- N3: RC5 push p99 5.1 ms (v3 stall 1.4 s); stream == batch exact on real val slices. Sub-minute ticks not validated (only D23 has seconds, H31).
- Bot: nothing counts; Bot sits in the benign bulk of every H layer, shape also on 120 benign-labelled flows (precision <= 47.6 %); beacon 27.5 % alone, size regularity 71.6 % alone (shape-dependent, 2.1 % precision), added to H at 1 % budget Bot stays 5.5 %.
- Open for supervisor: RC5 vs F1 for S7; fusion network ECDF / tick model must be recalibrated (S2/S7). Pitfall: results/WP4/s1_clean_D10.json is rewritten by the WP4 build (key order only): restore with git checkout.


## S3 (LiDAR in-stack + speed, worker sonnet) - REVIEW 2026-11-03
- Code: lidar/fast.py (v3-identical statistics, one ring assignment, voxel clustering flag), lidar/combine31.py (union with per-layer budgets), lidar/domain31.py (Domain31, stream), tools/WP8_S3_*.py, tests/v31/test_{fast,domain31}.py; results results/WP8/S3/, scores results/WP8/scores/S3/lidar_val.npz; report reports/WP8_S3.md. v3 lidar files untouched; suite 514 pass; run_all --check OK.
- Protocol: layer references leave-one-drive-out (stricter than v3 S9): v3 rule gives FA 2.70 % and PointDrop 4.3 % there. Chosen by the registered rule (3 logged rounds): tail2h|zmulti|E7, B = 1 %: FA 0.96 %, PointDrop 67.5 % [64.0, 70.0], episodes 23/30, IS 61.2, near replace 23.6, all kinds within 2 points. L3 NOT MET (70 / 80 %); B = 1.25 %: 74.4 % (frozen_lidar31_B125, supervisor decision). L2 MET (exact). L1 speed NOT MET: median 0.14-0.18 s, p99 0.24-0.27 s (v3 1.2-1.8 s).
- Pitfalls: exact v3 clustering = 2.4 s on dense scans (voxel 0.1 flag replaces it); L2a count statistics are drive dependent (drive 0027); sensor-fixed PointDrop is invisible after the onset scan; frozen domain 58 MB not committed (sha256 in report); parts/ and frame.pkl not committed (rebuild 16 min + 2 min).

## S1 (download, worker haiku) - REVIEW 2026-11-03
- H31 downloaded: KITTI 13 drives (11.88 GB), comma Chunk_2/4/3 (4.58 GB), V2AIX 674 extracted (0.82 GB); ~17.3 GB on disk; free 88.99 GB. Sizes/CRC/counts match locks; sha256 filled in locks (calib zips left null).
- Decision 3: no move (V31_val has 21 Civic routes). Decision 4: DATASETS D28 + D02n added.
- OPEN: calibration zips list 4100 B vs server 4068-4075 B (stopped; orchestrator decides). reports/WP8_S1.md, notes/WP8_S1_download.md.
