# WP8 journal (append-only; format: ISO time | step | what | state/next)

2026-11-03T00:00 | ORCH | v3.1 started: tag v3.0, branch v3.1, plan workpackages/WP8_v31.md | S0 + P1 launched
2026-11-03T16:38:20+01:00 | S0 | worker start: reading context (START_HERE, RULES, WP8, STATUS, registry, M3) | inventory next
2026-11-03T16:41 | P1 | start: inventory done (GPS s8_raw.pkl+frozen calibrators, LiDAR S9/test_scores.csv.gz, CAN S3 windows partial; NET/V2X/fusion per-sample scores gone) | writing tools/WP8_P1_curves.py
2026-11-03T16:42 | P1 | running tools/WP8_P1_curves.py (gps first), log results/WP8/logs/P1.log | next: check outputs
2026-11-03T16:44:05+01:00 | S0 | launch remote zip directory listing (kitti, comma) tools/WP8_S0_remote_list.py, logs results/WP8/logs/S0_remote_{kitti,comma}.log | resumable, outputs results/WP8/S0/remote/
2026-11-03T16:44 | P1 | done: outputs + reports/WP8_P1.md written, STATUS row P1 -> REVIEW | committing, stop
2026-11-03T00:30 | ORCH | P1 approved; rule 6 (keep scores in results/WP8/scores) added to WP8 plan | S0 running
2026-11-03T16:48:35+01:00 | S0 | inventory done: fresh = KITTI other drives (S3, no login), comma Chunk_2 (RAV4) + Chunk_3/4 (Civic, 2nd car), V2AIX 674 unextracted recordings in zip, ROAD accel x4, OTIDS (Kia) + Car-Hacking normal_run on ../codes/data; NET none; decision: v3 test of KITTI/comma/V2AIX becomes V31_val, v3 test of CAN/NET/VeReMi stays H31 (re-used) | write locks next
2026-11-03T16:50:21+01:00 | S0 | launch tools/WP8_S0_locks.py (sha256 of on-disk H31/V31 files, ~20 GB read), log results/WP8/logs/S0_locks.log | resumable via results/WP8/S0/sha256_cache.json
2026-11-03T16:51:01+01:00 | S0 | locks/H31.json + locks/V31_val.json written and committed (13 KITTI drives 6,239 scans, comma RAV4 Chunk_2 + Civic Chunk_4, V2AIX 674 rec, CAN fresh parts) | pre-registration next
2026-11-03T16:54:35+01:00 | S0 | pre-registration written (notes/WP8_v31.md: G1-G10, S1-S7 rules, M4-1..15) + S1 list (results/WP8/S0/S1_download_list.json); committing before any v3.1 result | brief, report, STATUS next
2026-11-03T16:54:44+01:00 | S0 | run test suite tests/run_tests.py, log results/WP8/logs/S0_tests.log | -
2026-11-03T16:56:57+01:00 | S0 | tests 484 passed / 0 failed / 3 skipped; report reports/WP8_S0.md, brief, STATUS S0 -> REVIEW | committed, stop
2026-11-03T01:00 | ORCH | S0 approved, amendments in notes/WP8_v31.md; S1, S3, S5 launched | -
2026-11-03T16:58 | S3 | worker start: reading context (WP3 brief, S9, M1_LiDAR) | next: understand lidar code
2026-11-03T16:58:40+01:00 | S5 | worker start: reading briefs/code | next: CAN runner
2026-11-03T17:02:26+01:00 | S1 | worker start (haiku): read RULES 3/3.4, WP8 plan, S1 list, locks, S0 remote lists; Decision 3 pre-check: V31_val civic_chunk3 has 21 Civic routes (dongle 99c94dc769b5d96e) | writing tools/WP8_S1_fetch.py (range fetch + per-member CRC, resumable), then run
2026-11-03T17:02:56+01:00 | S3 | profiled v3 domain (1.16 s/scan: ring assign x3 ~0.9 s, object rows 0.1 s, pair 0.05); writing lidar/fast.py (shared assign, labels without object table) | next: stats equality test vs v3
2026-11-03T17:03:05+01:00 | S5 | wrote can/incremental.py + tools/WP8_S5_can.py; smoke test on fuzzing_attack_2 | then full val run
2026-11-03T17:03:13+01:00 | S1 | start fetch calib_2011_09_26 calib_2011_09_29 calib_2011_09_30 calib_2011_10_03 | running
2026-11-03T17:03:13+01:00 | S1 | before calib_2011_09_26 | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_calib.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31\calib\2011_09_26 | downloading (resumable)
2026-11-03T17:03:13+01:00 | S1 | STOP calib_2011_09_26 | zip size 4068 differs from list 4100
2026-11-03T17:03:16+01:00 | S5 | smoke exact (0 diff); launching full val run: tools/WP8_S5_can.py, log results/WP8/logs/S5_can_val.log | resumable (parts)
2026-11-03T17:03:33+01:00 | S1 | DECISION: calib zips STOPPED (list says 4100 B, server Content-Length 4068 for 2011_09_26; 4071/4073/4075 for the other days): list sizes are estimates, not substituted; zips kept unextracted, no lock change; reported to orchestrator | launching KITTI drives and comma chunks + V2AIX in background (logs results/WP8/logs/S1_kitti.log, S1_comma.log)
2026-11-03T17:03:34+01:00 | S1 | start fetch Chunk_2 Chunk_4 Chunk_3 v2aix_h31 | running
2026-11-03T17:03:34+01:00 | S1 | before Chunk_2 | 7074 members, 1.368 GB on disk, 367.2 MB transfer | https://huggingface.co/datasets/commaai/comma2k19/resolve/main/raw_data/Chunk_2.zip -> C:\Users\nouir\PFE\data_extra\D22_comma2k19\Chunk_2 | fetching (range requests)
2026-11-03T17:03:34+01:00 | S1 | start fetch 2011_09_26_drive_0009 2011_09_26_drive_0023 2011_09_26_drive_0032 2011_09_26_drive_0056 2011_09_26_drive_0061 2011_09_26_drive_0064 2011_09_26_drive_0084 2011_09_26_drive_0093 2011_09_26_drive_0101 2011_09_29_drive_0004 2011_09_29_drive_0026 2011_09_30_drive_0016 2011_10_03_drive_0047 | running
2026-11-03T17:03:34+01:00 | S1 | before 2011_09_26_drive_0009 | 895 members, 0.823 GB on disk, 822.6 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0009/2011_09_26_drive_0009_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:06:27+01:00 | S5 | CAN val run finished? check; v2x/ego_stream.py + tools/WP8_S5_v2x.py written, smoke next (--max-v2aix 2)
2026-11-03T17:06:35+01:00 | S1 | KITTI run stopped by worker (own process) to split into 3 parallel processes (per-connection rate ~1.5-2 MB/s); each drive resumes per member | launching kitti A/B/C, logs results/WP8/logs/S1_kitti_A|B|C.log
2026-11-03T17:06:35+01:00 | S1 | start fetch 2011_09_26_drive_0061 2011_09_26_drive_0064 2011_09_26_drive_0093 2011_09_29_drive_0004 | running
2026-11-03T17:06:35+01:00 | S1 | start fetch 2011_09_26_drive_0009 2011_09_26_drive_0023 2011_09_26_drive_0032 2011_09_26_drive_0056 2011_09_26_drive_0084 2011_09_26_drive_0026 | running
2026-11-03T17:06:35+01:00 | S1 | start fetch 2011_09_26_drive_0101 2011_09_30_drive_0016 2011_10_03_drive_0047 | running
2026-11-03T17:06:35+01:00 | S1 | before 2011_09_26_drive_0061 | 1411 members, 1.386 GB on disk, 1386.1 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0061/2011_09_26_drive_0061_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:06:35+01:00 | S1 | before 2011_09_26_drive_0101 | 1877 members, 1.731 GB on disk, 1730.6 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0101/2011_09_26_drive_0101_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:06:35+01:00 | S1 | before 2011_09_26_drive_0009 | 895 members, 0.823 GB on disk, 822.6 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0009/2011_09_26_drive_0009_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:07:22+01:00 | S5 | CAN val done (11 captures, see parts); V2X smoke exact; launching full V2X then CAN long (timing growth): log results/WP8/logs/S5_v2x_long.log
2026-11-03T17:14:53+01:00 | S1 | after Chunk_2 | written 7074, already present 0, http bytes 553.7 MB, 675 s | files on disk; manifest next
2026-11-03T17:15:08+01:00 | S1 | manifest Chunk_2 | 7074 files, 1.368 GB, manifest_sha256 693758eb69f699db67010a9c86fa46871f7c3b7a8de89bdac41c8690964ead87 | written to results/WP8/S1/items
2026-11-03T17:15:08+01:00 | S1 | before Chunk_4 | 7543 members, 1.615 GB on disk, 372.5 MB transfer | https://huggingface.co/datasets/commaai/comma2k19/resolve/main/raw_data/Chunk_4.zip -> C:\Users\nouir\PFE\data_extra\D22_comma2k19\Chunk_4 | fetching (range requests)
2026-11-03T17:16:01+01:00 | S3 | lidar/fast.py (exact v3 statistics, fast path) + tools/WP8_S3_{lib,build}.py written; starting build smoke test on one small drive
2026-11-03T17:17:45+01:00 | S5 | CAN long done (highway 8.8M frames growth 0.91, basic_long 1.19; all exact); rerunning 3 reordered V2X egos then report
2026-11-03T17:19:04+01:00 | S3 | launched tools/WP8_S3_build.py --procs 3 (clean 23 drives, att + pdep 10 val drives; voxel 0.1 clustering since exact v3 clustering costs 2.4 s/scan on dense scans), log results/WP8/logs/S3_build.log | resumable, rerun same command; next: pre-registration + eval tool
2026-11-03T17:19:12+01:00 | S1 | after 2011_09_26_drive_0009 | written 309, already present 586, http bytes 571.8 MB, 755 s | files on disk; manifest next
2026-11-03T17:19:15+01:00 | S1 | manifest 2011_09_26_drive_0009 | 895 files, 0.823 GB, manifest_sha256 5128e8552294c4553073cbf1fe42880b41afd6c378bfa451e573a9f45752b1a6 | written to results/WP8/S1/items
2026-11-03T17:19:15+01:00 | S1 | before 2011_09_26_drive_0023 | 953 members, 0.884 GB on disk, 884.3 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0023/2011_09_26_drive_0023_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:19:37+01:00 | S5 | V2X final + acceptance json done (C1 met, C2 met, V1 met w/ reorder exception); running full test suite log results/WP8/logs/S5_tests.log, then report
2026-11-03T17:22:45+01:00 | S3 | lidar/fast.py, combine31.py, domain31.py, tools/WP8_S3_{lib,build,an,profile}.py, tests/v31/test_fast.py (9 pass) committed; build running
2026-11-03T17:23:31+01:00 | S5 | report, brief, STATUS REVIEW written; committing; stop
2026-11-03 | ORCH | S5 approved (3/9) | S1, S3, S4 running
2026-11-03T17:25:57+01:00 | S4 | start; WP4 caches are empty (deleted): rebuilding D10 stage+final via tools/WP4_s1_build.py D10 (resumable) then a D10-only stage prep; log results/WP8/logs/S4_rebuild.log | running
2026-11-03T17:28:11+01:00 | S4 | D10 stage+final rebuilt (log results/WP8/logs/S4_rebuild.log); running tools/WP8_S4_prep.py (S3-style stage, D10 only, train+val copy) log results/WP8/logs/S4_prep.log | running
2026-11-03T17:28:32+01:00 | S1 | after Chunk_4 | written 7543, already present 0, http bytes 571.4 MB, 800 s | files on disk; manifest next
2026-11-03T17:29:42+01:00 | S1 | manifest Chunk_4 | 7543 files, 1.615 GB, manifest_sha256 955d1c5d2540b01309e3e25f66d78d31d4eea5124d4e99f905be82b62039952f | written to results/WP8/S1/items
2026-11-03T17:29:42+01:00 | S1 | before Chunk_3 | 7474 members, 1.600 GB on disk, 380.2 MB transfer | https://huggingface.co/datasets/commaai/comma2k19/resolve/main/raw_data/Chunk_3.zip -> C:\Users\nouir\PFE\data_extra\D22_comma2k19\Chunk_3 | fetching (range requests)
2026-11-03T17:30:09+01:00 | S4 | pre-registration written to notes/WP8_v31.md (definitions, R5/R2/R1 grid, selection, N4 candidates BOT-A..D) BEFORE any score; next network/stream31.py + tests
2026-11-03T17:33:58+01:00 | S4 | stream31 + tests committed; launching tools/WP8_S4_eval.py (v3 vs R5/R2/R1/F1 on D10 val), log results/WP8/logs/S4_eval.log, parts results/WP8/S4/parts (resumable) | running
2026-11-03T17:35:07+01:00 | S3 | build done (43 parts, 0 failed, 16 min); running tools/WP8_S3_eval.py (26 candidates + M0, LODO), log results/WP8/logs/S3_eval.log | next: read selection
2026-11-03T17:36:15+01:00 | S1 | after 2011_09_26_drive_0061 | written 1411, already present 0, http bytes 1388.7 MB, 1779 s | files on disk; manifest next
2026-11-03T17:36:21+01:00 | S1 | manifest 2011_09_26_drive_0061 | 1411 files, 1.386 GB, manifest_sha256 326b6454d8674800767ff9e2aca2543ebecee476cf607816b47ebcaaf4630cdc | written to results/WP8/S1/items
2026-11-03T17:36:21+01:00 | S1 | before 2011_09_26_drive_0064 | 1145 members, 1.118 GB on disk, 1117.7 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0064/2011_09_26_drive_0064_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:37:33+01:00 | S1 | after 2011_09_26_drive_0023 | written 953, already present 0, http bytes 887.1 MB, 1097 s | files on disk; manifest next
2026-11-03T17:37:39+01:00 | S1 | manifest 2011_09_26_drive_0023 | 953 files, 0.884 GB, manifest_sha256 a88924e803a64719e389775a365927d4704b464d623ccbff27b1bdd430bd8bc0 | written to results/WP8/S1/items
2026-11-03T17:37:39+01:00 | S1 | before 2011_09_26_drive_0032 | 785 members, 0.737 GB on disk, 737.0 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0032/2011_09_26_drive_0032_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:37:59+01:00 | S3 | eval first pass: LODO at layer level gives M0 FA 2.70% (drive 0027 16.6%: L2a cnt_* drive shift) and M0 PointDrop 4.3% (v3 test 27.6%); checking pipeline vs frozen v3 on 150 scans: tools/WP8_S3_equiv.py log results/WP8/logs/S3_equiv.log
2026-11-03T17:39:06+01:00 | S4 | round 1+2 done (RC5 chosen by rule: macro -2.90, delay 0; F1 fallback -0.34, 60 s); running tools/WP8_S4_stream_check.py RC5 (stream==batch on real val slices, N3 timing), log results/WP8/logs/S4_stream_check.log | running
2026-11-03T17:39:46+01:00 | S3 | round 1 results saved as candidates_r1/selection_r1.json (no feasible candidate); round 2 logged in notes; launching eval tag r2 (144 candidates), log results/WP8/logs/S3_eval_r2.log
2026-11-03T17:42:41+01:00 | S4 | launching tools/WP8_S4_bot.py (Part A explanation + BOT-A..D on val), log results/WP8/logs/S4_bot.log | running
2026-11-03T17:44:24+01:00 | S3 | round 2 done (r2 json); round 3 logged in notes (multi-window z stats for L2c); parts moved to parts_r1, rerunning tools/WP8_S3_build.py --procs 3 -> results/WP8/logs/S3_build_r3.log (16 min)
2026-11-03T17:45:13+01:00 | S1 | after Chunk_3 | written 7474, already present 0, http bytes 583.1 MB, 926 s | files on disk; manifest next
2026-11-03T17:45:17+01:00 | S4 | stream check done (E1 real exact, push p99 5.1 ms), Bot analysis done (nothing counts); running full test suite + run_all --check (logs results/WP8/logs/S4_tests.log, S4_check.log); next tables + report
2026-11-03T17:45:27+01:00 | S1 | manifest Chunk_3 | 7474 files, 1.600 GB, manifest_sha256 e5ffaa1f81ba3b0617eb691ce7bc217764e5068a5a51fecb2ceda3aeacd74d74 | written to results/WP8/S1/items
2026-11-03T17:45:27+01:00 | S1 | before v2aix_h31 | local zip C:\Users\nouir\PFE\data_extra\D13_v2aix\v2aix_json.zip (sha256 check) -> C:\Users\nouir\PFE\data_extra\D13_v2aix\extracted_v31, 674 recordings, extraction only, never committed | hashing zip
2026-11-03T17:45:27+01:00 | S1 | after 2011_09_26_drive_0101 | written 1877, already present 0, http bytes 1733.8 MB, 2331 s | files on disk; manifest next
2026-11-03T17:45:33+01:00 | S1 | manifest 2011_09_26_drive_0101 | 1877 files, 1.731 GB, manifest_sha256 b27f4f70bfb33872648e83c23a24bf936878b7ee63764d3b3126bffddd8d10df | written to results/WP8/S1/items
2026-11-03T17:45:33+01:00 | S1 | before 2011_09_30_drive_0016 | 563 members, 0.561 GB on disk, 561.1 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_30_drive_0016/2011_09_30_drive_0016_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:45:34+01:00 | S1 | after v2aix_h31 | extracted 674, present 0, 6 s | checking manifest
2026-11-03T17:45:34+01:00 | S1 | manifest v2aix_h31 | 674 recordings verified (sha256 + CRC32 vs lock), data folder only | done
2026-11-03T17:45:34+01:00 | S1 | end fetch Chunk_2 Chunk_4 Chunk_3 v2aix_h31 | done
