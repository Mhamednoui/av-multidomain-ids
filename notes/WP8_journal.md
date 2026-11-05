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
2026-11-03T17:48:57+01:00 | S4 | added Stream31Final (tick-final emission = candidate F1) + test; running tools/WP8_S4_final_check.py, log results/WP8/logs/S4_final_check.log
2026-11-03T17:54:13+01:00 | S4 | DONE: report reports/WP8_S4.md, brief, STATUS S4 -> REVIEW; committing; stop
2026-11-03T18:00 | ORCH | S4 approved, F1 primary / RC5 variant (decision in notes/WP8_v31.md) | S1, S3 running
2026-11-03T17:55:34+01:00 | S1 | after 2011_09_26_drive_0032 | written 785, already present 0, http bytes 739.1 MB, 1074 s | files on disk; manifest next
2026-11-03T17:55:37+01:00 | S1 | manifest 2011_09_26_drive_0032 | 785 files, 0.737 GB, manifest_sha256 85a5f766f86a65ba83f53647ed12db230d3913e964acc454b7f7a9ab36c232ab | written to results/WP8/S1/items
2026-11-03T17:55:37+01:00 | S1 | before 2011_09_26_drive_0056 | 593 members, 0.576 GB on disk, 575.6 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0056/2011_09_26_drive_0056_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T17:57:37+01:00 | S1 | after 2011_09_30_drive_0016 | written 563, already present 0, http bytes 563.5 MB, 722 s | files on disk; manifest next
2026-11-03T17:57:42+01:00 | S1 | manifest 2011_09_30_drive_0016 | 563 files, 0.561 GB, manifest_sha256 625725250d587fb02873af0e3ba29b79d0e20a233b14d3147a65a0019aa6fef3 | written to results/WP8/S1/items
2026-11-03T17:57:42+01:00 | S1 | before 2011_10_03_drive_0047 | 1679 members, 1.596 GB on disk, 1595.8 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_10_03_drive_0047/2011_10_03_drive_0047_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T18:01:48+01:00 | S1 | after 2011_09_26_drive_0064 | written 1145, already present 0, http bytes 1120.3 MB, 1525 s | files on disk; manifest next
2026-11-03T18:01:53+01:00 | S1 | manifest 2011_09_26_drive_0064 | 1145 files, 1.118 GB, manifest_sha256 80494b61f7ea45ceaa040b0bf3005a299036f8bd83a7ab176337758ceab54d66 | written to results/WP8/S1/items
2026-11-03T18:01:53+01:00 | S1 | before 2011_09_26_drive_0093 | 871 members, 0.815 GB on disk, 815.4 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0093/2011_09_26_drive_0093_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T18:02:31+01:00 | S3 | r3 build done (0 failed); running tools/WP8_S3_eval.py --tag r3 (plan already logged and committed), log results/WP8/logs/S3_eval_r3.log
2026-11-03T18:05:15+01:00 | S3 | r3 result: registered rule chooses tail2h|zmulti|E7 at B=1% (FA 0.96, PointDrop 67.5, nr 23.6, IS 61.2, 23/30 episodes) -> L3 not met at 1%; exploratory B=1.25: tail2h|zmulti|E6@1.25 PD 74.4 FA 1.30; freezing both (frozen_lidar31, frozen_lidar31_B125), scores saved to results/WP8/scores/S3/lidar_val.npz
2026-11-03T18:05:30+01:00 | S3 | frozen domains saved; running speed + stream==batch: tools/WP8_S3_speed.py --tag load (other worker running), log results/WP8/logs/S3_speed_load.log
2026-11-03T18:06:39+01:00 | S1 | after 2011_09_26_drive_0056 | written 593, already present 0, http bytes 578.4 MB, 660 s | files on disk; manifest next
2026-11-03T18:06:43+01:00 | S1 | manifest 2011_09_26_drive_0056 | 593 files, 0.576 GB, manifest_sha256 5eed3ef7c7f797319d729ac6f9d907961d420d447eff01cc503f6a1a7cbfd8fd | written to results/WP8/S1/items
2026-11-03T18:06:43+01:00 | S1 | before 2011_09_26_drive_0084 | 771 members, 0.725 GB on disk, 725.5 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_drive_0084/2011_09_26_drive_0084_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T18:11:42+01:00 | S3 | assign window W_ITER=1 (exact on 144 scans), rerunning speed light: tools/WP8_S3_speed.py --tag light log results/WP8/logs/S3_speed_light.log
2026-11-03T18:19:30+01:00 | S3 | speed measured (median 141-178 ms depending on machine load, L1 not met; stream==batch exact on 1113 scans); extra.json written; running full test suite (log results/WP8/logs/S3_tests.log) and run_all --check
2026-11-03T18:19:57+01:00 | S1 | after 2011_09_26_drive_0093 | written 871, already present 0, http bytes 818.1 MB, 1083 s | files on disk; manifest next
2026-11-03T18:20:02+01:00 | S1 | manifest 2011_09_26_drive_0093 | 871 files, 0.815 GB, manifest_sha256 a1ed60278f9dcd3c1cc4a6d8f925feee681281c03249e3d4ff5a4118de08197a | written to results/WP8/S1/items
2026-11-03T18:20:02+01:00 | S1 | before 2011_09_29_drive_0004 | 683 members, 0.651 GB on disk, 650.6 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_29_drive_0004/2011_09_29_drive_0004_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T18:23:38+01:00 | S1 | after 2011_09_26_drive_0084 | written 771, already present 0, http bytes 728.0 MB, 1014 s | files on disk; manifest next
2026-11-03T18:23:42+01:00 | S1 | manifest 2011_09_26_drive_0084 | 771 files, 0.725 GB, manifest_sha256 dede20a1d0a43124097a6600fea8a29611940aebdfe301ce72b4747a2ace7b1f | written to results/WP8/S1/items
2026-11-03T18:24:03+01:00 | S3 | done: report reports/WP8_S3.md, brief, STATUS S3 -> REVIEW, suite 514 pass, run_all --check OK | committing, stop
2026-11-03T18:30 | ORCH | S3 approved; S3b + S6 launched; decisions in notes/WP8_v31.md | S1 downloading
2026-11-03T18:25:32+01:00 | S3b | start: reading fast.py, speed tool; plan numba kernels in lidar/fast_nb.py
2026-11-03T18:27:54+01:00 | S1 | after 2011_10_03_drive_0047 | written 1679, already present 0, http bytes 1598.6 MB, 1810 s | files on disk; manifest next
2026-11-03T18:28:03+01:00 | S1 | manifest 2011_10_03_drive_0047 | 1679 files, 1.596 GB, manifest_sha256 5f5c73c5e5c90c8ffd0f3e2b07d51e8b0818aeac2cc7ea8f4b13124a35119046 | written to results/WP8/S1/items
2026-11-03T18:28:03+01:00 | S1 | end fetch 2011_09_26_drive_0101 2011_09_30_drive_0016 2011_10_03_drive_0047 | done
2026-11-03T18:28:28+01:00 | S3b | wrote lidar/fast_nb.py + dispatch in fast.py; next kernel-level equality check on a few scans (tools/WP8_S3b_kern.py)
2026-11-03T18:29:20+01:00 | S1 | after 2011_09_29_drive_0004 | written 683, already present 0, http bytes 653.3 MB, 557 s | files on disk; manifest next
2026-11-03T18:29:24+01:00 | S1 | manifest 2011_09_29_drive_0004 | 683 files, 0.651 GB, manifest_sha256 c6b54d541fdd54bc616ad11a9e019abe7256af74a6e3350f387e250d7766f35a | written to results/WP8/S1/items
2026-11-03T18:29:24+01:00 | S1 | end fetch 2011_09_26_drive_0061 2011_09_26_drive_0064 2011_09_26_drive_0093 2011_09_29_drive_0004 | done
2026-11-03T18:30:23+01:00 | S3b | kernels equal at kernel level (89 scans, 0 mismatches); running full speed+equality: tools/WP8_S3b_speed.py --tag run1, log results/WP8/logs/S3b_speed_run1.log
2026-11-03T18:30:34+01:00 | S1 | process A crashed after drive 0084 (KeyError: my argument typo 2011_09_26_drive_0026; the real drive is 2011_09_29_drive_0026, not yet downloaded). No data affected; launching 2011_09_29_drive_0026 alone | log results/WP8/logs/S1_kitti_D.log
2026-11-03T18:30:35+01:00 | S1 | start fetch 2011_09_29_drive_0026 | running
2026-11-03T18:30:35+01:00 | S1 | before 2011_09_29_drive_0026 | 321 members, 0.282 GB on disk, 281.8 MB transfer | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_29_drive_0026/2011_09_29_drive_0026_sync.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31 | fetching (range requests)
2026-11-03T18:33:32+01:00 | S1 | after 2011_09_29_drive_0026 | written 321, already present 0, http bytes 284.1 MB, 176 s | files on disk; manifest next
2026-11-03T18:33:34+01:00 | S1 | manifest 2011_09_29_drive_0026 | 321 files, 0.282 GB, manifest_sha256 4e10c911445f9d076dda99d3f8fa21b7a1303d44c93ff50fc75ccee214d4d11f | written to results/WP8/S1/items
2026-11-03T18:33:34+01:00 | S1 | end fetch 2011_09_29_drive_0026 | done
2026-11-03T18:33:49+01:00 | S1 | locks filled | H31.json drives + rav4 + civic sha256; V31_val civic_chunk3 sha256; calibration zips left null (stopped)
2026-11-03T18:33:54+01:00 | S3b | run1 numba: median 75.8 ms p99 109.6 ms; S3 npz not the right comparator (LODO refs) -> running numpy path same frozen domain: --numpy --tag np1, log results/WP8/logs/S3b_speed_np1.log, then compare
2026-11-03T18:34:29+01:00 | S1 | locks filled | H31.json drives + rav4 + civic sha256; V31_val civic_chunk3 sha256; calibration zips left null (stopped)
2026-11-03T18:37:54+01:00 | S6 | worker start: read rules/brief/M2/M3/WP6 brief/crossdomain+fusion code; plan = hypothesis-based channel-level blame (crossdomain/blame31.py), K accelerometer-anchored inertial edges, reduced vehicle-block evaluation on V31_val; writing round-1 pre-registration to notes/WP8_v31.md | commit pre-registration BEFORE any S6 number
2026-11-03T18:39:29+01:00 | S6 | round-1 pre-registration + v3 fixture committed (git log head) | next: data builders tools/WP8_S6_build_kitti.py / _comma.py
2026-11-03T18:40:34+01:00 | S6 | test run tools/WP8_S6_kitti.py on drive 0001 (builder only, no blame numbers) | then all 23 drives in background log results/WP8/logs/S6_kitti.log
2026-11-03T18:40:39+01:00 | S3b | equality numba vs numpy: 0 alarm diffs, max diff 0.0 on 2085 scans (and first 1113); repeat timing run2 (tag run2), log results/WP8/logs/S3b_speed_run2.log
2026-11-03T18:42:09+01:00 | S1 | ORCH decision: accept server sizes for KITTI calib zips; list corrected (note added); extracting to calib/<day>/, content check, lock sha256 | running
2026-11-03T18:42:09+01:00 | S1 | start fetch calib_2011_09_26 calib_2011_09_29 calib_2011_09_30 calib_2011_10_03 | running
2026-11-03T18:42:09+01:00 | S1 | before calib_2011_09_26 | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_26_calib.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31\calib\2011_09_26 | downloading (resumable)
2026-11-03T18:42:09+01:00 | S1 | after calib_2011_09_26 | zip 4068 B, sha256 e0108cfd000cf802c14ed94fba38601185c792e5640abba015a34b7a85b812e0, members ['2011_09_26/calib_cam_to_cam.txt', '2011_09_26/calib_imu_to_velo.txt', '2011_09_26/calib_velo_to_cam.txt'] | extracted; manifest written
2026-11-03T18:42:09+01:00 | S1 | before calib_2011_09_29 | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_29_calib.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31\calib\2011_09_29 | downloading (resumable)
2026-11-03T18:42:09+01:00 | S1 | after calib_2011_09_29 | zip 4071 B, sha256 260fb836916ac3cbbab7104e253531239a0191b87c411fa60b99178abbb8c40d, members ['2011_09_29/calib_cam_to_cam.txt', '2011_09_29/calib_imu_to_velo.txt', '2011_09_29/calib_velo_to_cam.txt'] | extracted; manifest written
2026-11-03T18:42:09+01:00 | S1 | before calib_2011_09_30 | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_09_30_calib.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31\calib\2011_09_30 | downloading (resumable)
2026-11-03T18:42:09+01:00 | S1 | after calib_2011_09_30 | zip 4073 B, sha256 2ed01563b616baec14f25659671bd9a77810bd87752d709d184fe304ff7258e3, members ['2011_09_30/calib_cam_to_cam.txt', '2011_09_30/calib_imu_to_velo.txt', '2011_09_30/calib_velo_to_cam.txt'] | extracted; manifest written
2026-11-03T18:42:09+01:00 | S1 | before calib_2011_10_03 | https://s3.eu-central-1.amazonaws.com/avg-kitti/raw_data/2011_10_03_calib.zip -> C:\Users\nouir\PFE\data_extra\D04b_kitti_raw_v31\calib\2011_10_03 | downloading (resumable)
2026-11-03T18:42:10+01:00 | S1 | after calib_2011_10_03 | zip 4075 B, sha256 67f1f4dcfff4370f8ad1ccaf4fb013fca3f02abd650115f318ce9b1d0991a58c, members ['2011_10_03/calib_cam_to_cam.txt', '2011_10_03/calib_imu_to_velo.txt', '2011_10_03/calib_velo_to_cam.txt'] | extracted; manifest written
2026-11-03T18:42:10+01:00 | S1 | end fetch calib_2011_09_26 calib_2011_09_29 calib_2011_09_30 calib_2011_10_03 | done
2026-11-03T18:43:04+01:00 | S1 | calib zips done: list sizes corrected (note), 4 zips extracted to calib/<day>/<day>/, 12/12 files parse, no v3 copy to compare, H31 lock calib sha256 filled | commit, S1 stays REVIEW
2026-11-03T18:43:22+01:00 | S6 | K builder done (23 drive pickles in data_extra/cache_v3/WP8/S6, log results/WP8/logs/S6_kitti.log); running comma builder tools/WP8_S6_comma.py in background, log results/WP8/logs/S6_comma.log
2026-11-03 | ORCH | S1 approved (6/10) | S3b, S6 running
2026-11-03T18:43:56+01:00 | S3b | done: report reports/WP8_S3b.md, brief, STATUS S3b -> REVIEW; running full test suite then commit
2026-11-03 | ORCH | S3b approved (7/10) | S6 running
2026-11-03T18:48:09+01:00 | S6 | round-1 evaluation start: tools/WP8_S6_eval.py r1 (log results/WP8/logs/S6_eval_r1.log), pre-registration + amendment A committed before | output results/WP8/S6/r1_eval.json
2026-11-03T18:51:37+01:00 | S6 | round 1 done (no candidate passes; defects a/b/c found); round-2 plan committed in notes/WP8_v31.md | implementing corrections then running r2
2026-11-03T18:51:58+01:00 | S6 | round-2 evaluation start: tools/WP8_S6_eval.py r2 (log results/WP8/logs/S6_eval_r2.log) | plan + corrections committed before
2026-11-04T16:24:10+01:00 | B0 | resumed after limit reset; nothing on disk yet; collected CAN refs (can-train-and-test, ROAD, Song/Hoang) in memory; next: network/V2X/GPS/LiDAR searches then write files | commit per dataset
2026-11-04T16:24:27+01:00 | S6 | resumed after usage reset; r2 numbers exist (results/WP8/S6/r2_eval.json); found CAN inertial anchor all-NaN (CAN grid speed NaN on ticks 0-2): writing round-3 plan before running r3
2026-11-04T16:24:42+01:00 | S6 | round-3 evaluation start: tools/WP8_S6_eval.py r3 (log results/WP8/logs/S6_eval_r3.log), plan committed before
2026-11-04T16:25:27+01:00 | S6 | round 3 done (A1 selected by rule; A3 alternative); writing report/brief/STATUS; running full test suite log results/WP8/logs/S6_tests.log
2026-11-04T16:28:49+01:00 | B0 | literature md+json written and committed (CAN, network, V2X, GPS, LiDAR); next: B0_splits_proposal.md, report, STATUS
2026-11-04T16:28:50+01:00 | S6 | DONE: report reports/WP8_S6.md, brief, STATUS S6 -> REVIEW, suite 529 pass; committing, stop
2026-11-04 | ORCH | S6 approved (A1 freeze); S2 launched | B0 running
2026-11-04T16:29:45+01:00 | B0 | done: report reports/WP9_B0.md, STATUS B0 -> REVIEW, committed
2026-11-04T16:30:56+01:00 | B1 | start: reading WP9/RULES/briefs, then plan CAN benchmark (Car-Hacking, ROAD, D11) | next: inspect can/ adapters + split files
2026-11-04T16:31:12+01:00 | B2 | start: reading rules/briefs; checking corrected CICIDS2017 availability | next: inspect data, lock splits
2026-11-04T16:31:55+01:00 | B2 | download start: WTMC2021 dataset.zip (334MB) -> ../data_extra/D10e_cicids2017_wtmc2021/raw, CNS2022 CSECICIDS2018_improved.zip (9.7GB) -> ../data_extra/D23e_cse-cic-ids2018_improved_cns2022/raw; resumable curl -C -; logs results/WP9/logs/B2_dl_*.log | no login needed (open http)
2026-11-04T16:33:54+01:00 | B1 | plan: tools/WP9_B1_lib.py (parse+dedup+features), WP9_B1_lock.py (locks/WP9_{carhacking,road,d11}.json), then build/fit/test; correction to proposal: D11 test_03/04 = UNSEEN attack families (not seen rows) | next: write lib and lock tool
2026-11-04T16:35:09+01:00 | B2 | design+rules written notes/WP9_B2.md (committed); downloads running; next: inspect WTMC2021 zip when done
2026-11-04T16:35:32+01:00 | S2 | worker start: read rules/brief/S0-S6 decisions/M3/WP7_S2; plan = V31_val composites (WP7 S2 construction) from saved v3.1 domain outputs, 2-fold group cross-fitting, fusion/system31.py; inspecting data structure (no fusion number) then writing round-1 pre-registration | commit pre-registration BEFORE any S2 number
2026-11-04T16:36:09+01:00 | B1 | launching lock tool carhacking, road, d11 sequentially in background: log results/WP9/logs/B1_lock.log (resumable; parsed cache data_extra/cache_v3/WP9/B1/parsed)
2026-11-04T16:37:23+01:00 | B1 | lock carhacking: parse DoS
2026-11-04T16:37:31+01:00 | B1 | lock carhacking: parse Fuzzy
2026-11-04T16:37:39+01:00 | B1 | lock carhacking: parse RPM
2026-11-04T16:37:49+01:00 | B1 | lock carhacking: parse Gear
2026-11-04T16:37:59+01:00 | B1 | lock carhacking: parse normal_run
2026-11-04T16:38:04+01:00 | B1 | lock carhacking: written locks/WP9_carhacking.json
2026-11-04T16:38:05+01:00 | B1 | lock road: parse ambient_dyno_drive_basic_long
2026-11-04T16:38:19+01:00 | B1 | lock road: parse ambient_dyno_drive_basic_short
2026-11-04T16:38:24+01:00 | B1 | lock road: parse ambient_dyno_drive_benign_anomaly
2026-11-04T16:38:27+01:00 | B1 | lock road: parse ambient_dyno_drive_extended_long
2026-11-04T16:38:33+01:00 | B1 | lock road: parse ambient_dyno_drive_extended_short
2026-11-04T16:38:36+01:00 | B2 | build D10o table: tools/WP9_B2_build.py D10o (log results/WP9/logs/B2_build_D10o.log) | -> cache WP9/B2/D10o.pkl
2026-11-04T16:38:36+01:00 | B2 | build D10e table: tools/WP9_B2_build.py D10e (log results/WP9/logs/B2_build_D10e.log) | -> cache WP9/B2/D10e.pkl
2026-11-04T16:38:36+01:00 | B1 | lock road: parse ambient_dyno_drive_radio_infotainment
2026-11-04T16:38:41+01:00 | B1 | lock road: parse ambient_dyno_drive_winter
2026-11-04T16:38:41+01:00 | B1 | lock road: parse ambient_dyno_exercise_all_bits
2026-11-04T16:39:02+01:00 | B1 | lock road: parse ambient_dyno_idle_radio_infotainment
2026-11-04T16:39:09+01:00 | B1 | lock road: parse ambient_dyno_reverse
2026-11-04T16:39:09+01:00 | B1 | lock road: parse ambient_highway_street_driving_diagnostics
2026-11-04T16:39:14+01:00 | B1 | lock road: parse ambient_highway_street_driving_long
2026-11-04T16:39:18+01:00 | S2 | round-1 pre-registration committed (8bf6910) | next: fusion/system31.py + tools/WP8_S2_build.py
2026-11-04T16:40:00+01:00 | B1 | lock road: parse correlated_signal_attack_1
2026-11-04T16:40:00+01:00 | B1 | lock road: parse correlated_signal_attack_1_masquerade
2026-11-04T16:40:00+01:00 | B1 | lock road: parse correlated_signal_attack_2
2026-11-04T16:40:00+01:00 | B1 | lock road: parse correlated_signal_attack_2_masquerade
2026-11-04T16:40:01+01:00 | B1 | lock road: parse correlated_signal_attack_3
2026-11-04T16:40:01+01:00 | B1 | lock road: parse correlated_signal_attack_3_masquerade
2026-11-04T16:40:01+01:00 | B1 | lock road: parse fuzzing_attack_1
2026-11-04T16:40:01+01:00 | B1 | lock road: parse fuzzing_attack_2
2026-11-04T16:40:01+01:00 | B1 | lock road: parse fuzzing_attack_3
2026-11-04T16:40:01+01:00 | B1 | lock road: parse max_engine_coolant_temp_attack
2026-11-04T16:40:02+01:00 | B1 | lock road: parse max_engine_coolant_temp_attack_masquerade
2026-11-04T16:40:02+01:00 | B1 | lock road: parse max_speedometer_attack_1
2026-11-04T16:40:03+01:00 | B1 | lock road: parse max_speedometer_attack_1_masquerade
2026-11-04T16:40:03+01:00 | B1 | lock road: parse max_speedometer_attack_2
2026-11-04T16:40:04+01:00 | B1 | lock road: parse max_speedometer_attack_2_masquerade
2026-11-04T16:40:04+01:00 | B1 | lock road: parse max_speedometer_attack_3
2026-11-04T16:40:05+01:00 | B1 | lock road: parse max_speedometer_attack_3_masquerade
2026-11-04T16:40:06+01:00 | B1 | lock road: parse reverse_light_off_attack_1
2026-11-04T16:40:06+01:00 | B1 | lock road: parse reverse_light_off_attack_1_masquerade
2026-11-04T16:40:07+01:00 | B1 | lock road: parse reverse_light_off_attack_2
2026-11-04T16:40:07+01:00 | B1 | lock road: parse reverse_light_off_attack_2_masquerade
2026-11-04T16:40:07+01:00 | B1 | lock road: parse reverse_light_off_attack_3
2026-11-04T16:40:08+01:00 | B1 | lock road: parse reverse_light_off_attack_3_masquerade
2026-11-04T16:40:09+01:00 | B1 | lock road: parse reverse_light_on_attack_1
2026-11-04T16:40:09+01:00 | B1 | lock road: parse reverse_light_on_attack_1_masquerade
2026-11-04T16:40:10+01:00 | B1 | lock road: parse reverse_light_on_attack_2
2026-11-04T16:40:10+01:00 | B1 | lock road: parse reverse_light_on_attack_2_masquerade
2026-11-04T16:40:11+01:00 | B1 | lock road: parse reverse_light_on_attack_3
2026-11-04T16:40:12+01:00 | B1 | lock road: parse reverse_light_on_attack_3_masquerade
2026-11-04T16:40:12+01:00 | B1 | lock road: written locks/WP9_road.json
2026-11-04T16:40:14+01:00 | B1 | lock d11: parse set_01/train_01/DoS-1
2026-11-04T16:40:14+01:00 | B1 | lock d11: parse set_01/train_01/accessory-1
2026-11-04T16:40:14+01:00 | B1 | lock d11: parse set_01/train_01/attack-free-1
2026-11-04T16:40:17+01:00 | B1 | lock d11: parse set_01/train_01/force-neutral-1
2026-11-04T16:40:18+01:00 | B1 | lock d11: parse set_01/train_01/rpm-1
2026-11-04T16:40:20+01:00 | B1 | lock d11: parse set_01/train_01/standstill-1
2026-11-04T16:40:23+01:00 | B1 | lock d11: parse set_01/train_01/DoS-2
2026-11-04T16:40:23+01:00 | B1 | lock d11: parse set_01/train_01/accessory-2
2026-11-04T16:40:23+01:00 | B1 | lock d11: parse set_01/train_01/attack-free-2
2026-11-04T16:40:25+01:00 | B1 | lock d11: parse set_01/train_01/force-neutral-2
2026-11-04T16:40:27+01:00 | B1 | lock d11: parse set_01/train_01/rpm-2
2026-11-04T16:40:28+01:00 | B1 | lock d11: parse set_01/train_01/standstill-2
2026-11-04T16:40:30+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/DoS-3
2026-11-04T16:40:30+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/DoS-4
2026-11-04T16:40:32+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/force-neutral-3
2026-11-04T16:40:33+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/force-neutral-4
2026-11-04T16:40:34+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/rpm-3
2026-11-04T16:40:36+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/rpm-4
2026-11-04T16:40:37+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/standstill-3
2026-11-04T16:40:38+01:00 | B1 | lock d11: parse set_01/test_01_known_vehicle_known_attack/standstill-4
2026-11-04T16:40:39+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/DoS-3
2026-11-04T16:40:41+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/DoS-4
2026-11-04T16:40:42+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/force-neutral-3
2026-11-04T16:40:43+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/force-neutral-4
2026-11-04T16:40:45+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/rpm-3
2026-11-04T16:40:46+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/rpm-4
2026-11-04T16:40:48+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/standstill-3
2026-11-04T16:40:48+01:00 | B1 | lock d11: parse set_01/test_02_unknown_vehicle_known_attack/standstill-4
2026-11-04T16:40:49+01:00 | B1 | launching build carhacking+road (bg), log results/WP9/logs/B1_build.log; locks carhacking+road committed, d11 lock still running
2026-11-04T16:40:50+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/double-3
2026-11-04T16:40:50+01:00 | B1 | build carhacking: start (resumable)
2026-11-04T16:40:51+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/double-4
2026-11-04T16:40:52+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/fuzzing-3
2026-11-04T16:40:53+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/fuzzing-4
2026-11-04T16:40:54+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/interval-3
2026-11-04T16:40:55+01:00 | B1 | build carhacking: done (195 segments)
2026-11-04T16:40:55+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/interval-4
2026-11-04T16:40:57+01:00 | B1 | build road: start (resumable)
2026-11-04T16:40:57+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/speed-3
2026-11-04T16:40:58+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/speed-4
2026-11-04T16:40:59+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/systematic-3
2026-11-04T16:41:00+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/systematic-4
2026-11-04T16:41:01+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/triple-3
2026-11-04T16:41:03+01:00 | B1 | lock d11: parse set_01/test_03_known_vehicle_unknown_attack/triple-4
2026-11-04T16:41:04+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/double-3
2026-11-04T16:41:06+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/double-4
2026-11-04T16:41:07+01:00 | B1 | build road: done (41 segments)
2026-11-04T16:41:08+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/fuzzing-3
2026-11-04T16:41:09+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/fuzzing-4
2026-11-04T16:41:10+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/interval-3
2026-11-04T16:41:11+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/interval-4
2026-11-04T16:41:13+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/speed-3
2026-11-04T16:41:17+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/speed-4
2026-11-04T16:41:20+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/systematic-3
2026-11-04T16:41:21+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/systematic-4
2026-11-04T16:41:22+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/triple-3
2026-11-04T16:41:25+01:00 | B1 | lock d11: parse set_01/test_04_unknown_vehicle_unknown_attack/triple-4
2026-11-04T16:41:26+01:00 | B1 | lock d11: parse set_02/train_01/accessory-1
2026-11-04T16:41:26+01:00 | B1 | lock d11: parse set_02/train_01/attack-free-1
2026-11-04T16:41:28+01:00 | B1 | lock d11: parse set_02/train_01/double-1
2026-11-04T16:41:29+01:00 | B1 | lock d11: parse set_02/train_01/fuzzing-1
2026-11-04T16:41:31+01:00 | B1 | lock d11: parse set_02/train_01/interval-1
2026-11-04T16:41:32+01:00 | B1 | lock d11: parse set_02/train_01/speed-1
2026-11-04T16:41:35+01:00 | S2 | build start: tools/WP8_S2_build.py can kveh cveh net lidar v2x (background), log results/WP8/logs/S2_build.log | output ../data_extra/cache_v3/WP8/S2/
2026-11-04T16:41:37+01:00 | B1 | lock d11: parse set_02/train_01/systematic-1
2026-11-04T16:41:37+01:00 | B1 | lock d11: parse set_02/train_01/triple-1
2026-11-04T16:41:41+01:00 | B1 | lock d11: parse set_02/train_01/accessory-2
2026-11-04T16:41:41+01:00 | B1 | lock d11: parse set_02/train_01/attack-free-2
2026-11-04T16:41:42+01:00 | B1 | lock d11: parse set_02/train_01/double-2
2026-11-04T16:41:43+01:00 | B1 | lock d11: parse set_02/train_01/fuzzing-2
2026-11-04T16:41:45+01:00 | B1 | lock d11: parse set_02/train_01/interval-2
2026-11-04T16:41:47+01:00 | B1 | lock d11: parse set_02/train_01/speed-2
2026-11-04T16:41:52+01:00 | B1 | lock d11: parse set_02/train_01/systematic-2
2026-11-04T16:41:52+01:00 | B1 | lock d11: parse set_02/train_01/triple-2
2026-11-04T16:41:53+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/double-3
2026-11-04T16:41:55+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/double-4
2026-11-04T16:41:57+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/fuzzing-3
2026-11-04T16:41:58+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/fuzzing-4
2026-11-04T16:41:59+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/interval-3
2026-11-04T16:42:00+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/interval-4
2026-11-04T16:42:02+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/speed-3
2026-11-04T16:42:06+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/speed-4
2026-11-04T16:42:09+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/systematic-3
2026-11-04T16:42:10+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/systematic-4
2026-11-04T16:42:11+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/triple-3
2026-11-04T16:42:14+01:00 | B1 | lock d11: parse set_02/test_01_known_vehicle_known_attack/triple-4
2026-11-04T16:42:15+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/double-3
2026-11-04T16:42:16+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/double-4
2026-11-04T16:42:17+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/fuzzing-3
2026-11-04T16:42:18+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/fuzzing-4
2026-11-04T16:42:19+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/interval-3
2026-11-04T16:42:19+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/interval-4
2026-11-04T16:42:21+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/speed-3
2026-11-04T16:42:22+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/speed-4
2026-11-04T16:42:23+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/systematic-3
2026-11-04T16:42:24+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/systematic-4
2026-11-04T16:42:27+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/triple-3
2026-11-04T16:42:28+01:00 | B1 | lock d11: parse set_02/test_02_unknown_vehicle_known_attack/triple-4
2026-11-04T16:42:29+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/DoS-3
2026-11-04T16:42:30+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/DoS-4
2026-11-04T16:42:31+01:00 | B1 | build done carhacking+road; launching fit carhacking (bg) log results/WP9/logs/B1_fit_carhacking.log (no test segment read)
2026-11-04T16:42:31+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/force-neutral-3
2026-11-04T16:42:33+01:00 | B1 | fit carhacking: start (K+1=5); log results/WP9/logs/B1_fit_carhacking.log
2026-11-04T16:42:39+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/force-neutral-4
2026-11-04T16:42:44+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/rpm-3
2026-11-04T16:42:46+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/rpm-4
2026-11-04T16:42:49+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/standstill-3
2026-11-04T16:42:50+01:00 | B1 | lock d11: parse set_02/test_03_known_vehicle_unknown_attack/standstill-4
2026-11-04T16:42:52+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/DoS-3
2026-11-04T16:42:52+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/DoS-4
2026-11-04T16:42:54+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/force-neutral-3
2026-11-04T16:42:55+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/force-neutral-4
2026-11-04T16:42:57+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/rpm-3
2026-11-04T16:42:59+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/rpm-4
2026-11-04T16:43:01+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/standstill-3
2026-11-04T16:43:03+01:00 | B1 | lock d11: parse set_02/test_04_unknown_vehicle_unknown_attack/standstill-4
2026-11-04T16:43:04+01:00 | B1 | lock d11: parse set_03/train_01/DoS-3
2026-11-04T16:43:07+01:00 | B1 | lock d11: parse set_03/train_01/accessory-3
2026-11-04T16:43:07+01:00 | B1 | lock d11: parse set_03/train_01/attack-free-3
2026-11-04T16:43:12+01:00 | B1 | lock d11: parse set_03/train_01/double-3
2026-11-04T16:43:13+01:00 | B1 | lock d11: parse set_03/train_01/force-neutral-3
2026-11-04T16:43:15+01:00 | B1 | lock d11: parse set_03/train_01/fuzzing-3
2026-11-04T16:43:15+01:00 | B1 | lock d11: parse set_03/train_01/triple-3
2026-11-04T16:43:17+01:00 | B1 | lock d11: parse set_03/train_01/DoS-4
2026-11-04T16:43:19+01:00 | B1 | lock d11: parse set_03/train_01/accessory-4
2026-11-04T16:43:20+01:00 | B1 | lock d11: parse set_03/train_01/attack-free-4
2026-11-04T16:43:23+01:00 | B1 | lock d11: parse set_03/train_01/double-4
2026-11-04T16:43:27+01:00 | B1 | lock d11: parse set_03/train_01/force-neutral-4
2026-11-04T16:43:30+01:00 | B2 | splits for D10o: tools/WP9_B2_splits.py D10o -> locks/WP9_D10o.json (before any training)
2026-11-04T16:43:31+01:00 | B1 | lock d11: parse set_03/train_01/fuzzing-4
2026-11-04T16:43:33+01:00 | B1 | lock d11: parse set_03/train_01/triple-4
2026-11-04T16:43:35+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/DoS-1
2026-11-04T16:43:35+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/DoS-2
2026-11-04T16:43:37+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/double-1
2026-11-04T16:43:41+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/double-2
2026-11-04T16:43:44+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/force-neutral-1
2026-11-04T16:43:48+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/force-neutral-2
2026-11-04T16:43:50+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/fuzzing-1
2026-11-04T16:43:53+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/fuzzing-2
2026-11-04T16:43:55+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/triple-1
2026-11-04T16:43:56+01:00 | B1 | lock d11: parse set_03/test_01_known_vehicle_known_attack/triple-2
2026-11-04T16:43:58+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/DoS-1
2026-11-04T16:43:59+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/DoS-2
2026-11-04T16:44:01+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/double-1
2026-11-04T16:44:04+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/double-2
2026-11-04T16:44:05+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/force-neutral-1
2026-11-04T16:44:06+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/force-neutral-2
2026-11-04T16:44:07+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/fuzzing-1
2026-11-04T16:44:09+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/fuzzing-2
2026-11-04T16:44:10+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/triple-1
2026-11-04T16:44:11+01:00 | B1 | lock d11: parse set_03/test_02_unknown_vehicle_known_attack/triple-2
2026-11-04T16:44:12+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/interval-1
2026-11-04T16:44:14+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/interval-2
2026-11-04T16:44:16+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/rpm-1
2026-11-04T16:44:17+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/rpm-2
2026-11-04T16:44:19+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/rpm-accessory-1
2026-11-04T16:44:20+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/rpm-accessory-2
2026-11-04T16:44:20+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/speed-1
2026-11-04T16:44:22+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/speed-2
2026-11-04T16:44:24+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/speed-accessory-1
2026-11-04T16:44:25+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/speed-accessory-2
2026-11-04T16:44:25+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/standstill-1
2026-11-04T16:44:26+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/standstill-2
2026-11-04T16:44:28+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/systematic-1
2026-11-04T16:44:30+01:00 | B1 | lock d11: parse set_03/test_03_known_vehicle_unknown_attack/systematic-2
2026-11-04T16:44:31+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/interval-1
2026-11-04T16:44:33+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/interval-2
2026-11-04T16:44:34+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/rpm-1
2026-11-04T16:44:34+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/rpm-2
2026-11-04T16:44:36+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/rpm-accessory-1
2026-11-04T16:44:36+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/rpm-accessory-2
2026-11-04T16:44:36+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/speed-1
2026-11-04T16:44:38+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/speed-2
2026-11-04T16:44:39+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/speed-accessory-1
2026-11-04T16:44:40+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/speed-accessory-2
2026-11-04T16:44:40+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/standstill-1
2026-11-04T16:44:41+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/standstill-2
2026-11-04T16:44:42+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/systematic-1
2026-11-04T16:44:43+01:00 | B1 | lock d11: parse set_03/test_04_unknown_vehicle_unknown_attack/systematic-2
2026-11-04T16:44:45+01:00 | B1 | lock d11: parse set_04/train_01/accessory-3
2026-11-04T16:44:45+01:00 | B1 | lock d11: parse set_04/train_01/attack-free-3
2026-11-04T16:44:46+01:00 | B1 | lock d11: parse set_04/train_01/interval-3
2026-11-04T16:44:47+01:00 | B1 | lock d11: parse set_04/train_01/rpm-3
2026-11-04T16:44:48+01:00 | B1 | lock d11: parse set_04/train_01/rpm-accessory-3
2026-11-04T16:44:48+01:00 | B1 | lock d11: parse set_04/train_01/speed-3
2026-11-04T16:44:50+01:00 | B1 | lock d11: parse set_04/train_01/speed-accessory-3
2026-11-04T16:44:50+01:00 | B1 | lock d11: parse set_04/train_01/standstill-3
2026-11-04T16:44:52+01:00 | B1 | lock d11: parse set_04/train_01/systematic-3
2026-11-04T16:44:54+01:00 | B1 | lock d11: parse set_04/train_01/accessory-4
2026-11-04T16:44:54+01:00 | B1 | lock d11: parse set_04/train_01/attack-free-4
2026-11-04T16:44:54+01:00 | B1 | lock d11: parse set_04/train_01/interval-4
2026-11-04T16:44:56+01:00 | B1 | lock d11: parse set_04/train_01/rpm-4
2026-11-04T16:44:57+01:00 | B1 | lock d11: parse set_04/train_01/rpm-accessory-4
2026-11-04T16:44:58+01:00 | B1 | lock d11: parse set_04/train_01/speed-4
2026-11-04T16:44:59+01:00 | B1 | lock d11: parse set_04/train_01/speed-accessory-4
2026-11-04T16:44:59+01:00 | B1 | lock d11: parse set_04/train_01/standstill-4
2026-11-04T16:45:00+01:00 | B1 | lock d11: parse set_04/train_01/systematic-4
2026-11-04T16:45:02+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/interval-1
2026-11-04T16:45:04+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/interval-2
2026-11-04T16:45:05+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/rpm-1
2026-11-04T16:45:06+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/rpm-2
2026-11-04T16:45:07+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/rpm-accessory-1
2026-11-04T16:45:07+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/rpm-accessory-2
2026-11-04T16:45:07+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/speed-1
2026-11-04T16:45:09+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/speed-2
2026-11-04T16:45:10+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/speed-accessory-1
2026-11-04T16:45:11+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/speed-accessory-2
2026-11-04T16:45:11+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/standstill-1
2026-11-04T16:45:12+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/standstill-2
2026-11-04T16:45:13+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/systematic-1
2026-11-04T16:45:14+01:00 | B1 | lock d11: parse set_04/test_01_known_vehicle_known_attack/systematic-2
2026-11-04T16:45:16+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/interval-1
2026-11-04T16:45:17+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/interval-2
2026-11-04T16:45:20+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/rpm-1
2026-11-04T16:45:27+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/rpm-2
2026-11-04T16:45:27+01:00 | S2 | build done (6 stage pickles in ../data_extra/cache_v3/WP8/S2, L100 LODO == S3 score file); committing fusion/system31.py + builder | next: tools/WP8_S2_sim.py
2026-11-04T16:45:31+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/rpm-accessory-1
2026-11-04T16:45:32+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/rpm-accessory-2
2026-11-04T16:45:33+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/speed-1
2026-11-04T16:45:38+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/speed-2
2026-11-04T16:45:43+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/speed-accessory-1
2026-11-04T16:45:44+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/speed-accessory-2
2026-11-04T16:45:45+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/standstill-1
2026-11-04T16:45:47+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/standstill-2
2026-11-04T16:45:49+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/systematic-1
2026-11-04T16:45:50+01:00 | B1 | lock d11: parse set_04/test_02_unknown_vehicle_known_attack/systematic-2
2026-11-04T16:45:51+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/DoS-1
2026-11-04T16:45:52+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/DoS-2
2026-11-04T16:45:53+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/double-1
2026-11-04T16:45:56+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/double-2
2026-11-04T16:45:57+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/force-neutral-1
2026-11-04T16:45:58+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/force-neutral-2
2026-11-04T16:45:59+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/fuzzing-1
2026-11-04T16:46:00+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/fuzzing-2
2026-11-04T16:46:02+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/triple-1
2026-11-04T16:46:03+01:00 | B1 | lock d11: parse set_04/test_03_known_vehicle_unknown_attack/triple-2
2026-11-04T16:46:04+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/DoS-1
2026-11-04T16:46:05+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/DoS-2
2026-11-04T16:46:06+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/double-1
2026-11-04T16:46:08+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/double-2
2026-11-04T16:46:09+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/force-neutral-1
2026-11-04T16:46:10+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/force-neutral-2
2026-11-04T16:46:11+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/fuzzing-1
2026-11-04T16:46:13+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/fuzzing-2
2026-11-04T16:46:15+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/triple-1
2026-11-04T16:46:19+01:00 | B1 | lock d11: parse set_04/test_04_unknown_vehicle_unknown_attack/triple-2
2026-11-04T16:46:20+01:00 | B1 | lock d11: written locks/WP9_d11.json
2026-11-04T16:46:27+01:00 | B1 | build d11: start (resumable)
2026-11-04T16:47:26+01:00 | B2 | splits for D10e -> locks/WP9_D10e.json
2026-11-04T16:47:34+01:00 | B1 | found float32 threshold-rounding bug in summarize/decide (FPR 1.06% vs 1% budget), fixed to float64; carhacking fit will be re-run; launching road fit (bg) log results/WP9/logs/B1_fit_road.log
2026-11-04T16:47:37+01:00 | B1 | fit road: start (K+1=10); log results/WP9/logs/B1_fit_road.log
2026-11-04T16:47:47+01:00 | B1 | build d11: done (236 segments)
2026-11-04T16:49:07+01:00 | S2 | round-1 evaluation start (48fc9af): tools/WP8_S2_sim.py --tag r1 (background), log results/WP8/logs/S2_sim_r1.log, pre-registration 8bf6910 | output results/WP8/S2/r1_eval.json
2026-11-04T16:49:15+01:00 | B1 | fit carhacking: done, chosen W_rf_generic; results/WP9/B1_carhacking_selection.json
2026-11-04T16:49:21+01:00 | B1 | rerunning fit carhacking after float64 decide fix (run1 log kept as ..._run1_buggy_decide.log; no test read)
2026-11-04T16:49:23+01:00 | B1 | fit carhacking: start (K+1=5); log results/WP9/logs/B1_fit_carhacking.log
2026-11-04T16:50:57+01:00 | B2 | start val-only runs (cand,select,control) D10o T,G,B: tools/WP9_B2_driver.sh D10o cand select control (log results/WP9/logs/B2_D10o_val.log); resumable (parts/ json skip) | test stage NOT included
2026-11-04T16:51:27+01:00 | B1 | fit road: done, chosen Fb; results/WP9/B1_road_selection.json
2026-11-04T16:53:06+01:00 | B1 | road fit done (selection json written; controls: Fb frame shuffled AUC 0.28 FAIL, W_rf_ids 0.73 FAIL -> reported); launching d11 fits set_01..04 sequentially (bg), logs results/WP9/logs/B1_fit_d11_set_0N.log
2026-11-04T16:53:09+01:00 | B1 | fit d11_set_01: start (K+1=5); log results/WP9/logs/B1_fit_d11_set_01.log
2026-11-04T16:55:21+01:00 | B1 | fit d11_set_01: done, chosen W_xgb_a_ids; results/WP9/B1_d11_set_01_selection.json
2026-11-04T16:55:24+01:00 | B1 | fit d11_set_02: start (K+1=7); log results/WP9/logs/B1_fit_d11_set_02.log
2026-11-04T16:58:17+01:00 | B1 | fit carhacking: done, chosen W_rf_generic; results/WP9/B1_carhacking_selection.json
2026-11-04T16:58:27+01:00 | B1 | selection jsons carhacking+road committed; running test scoring ONCE: carhacking then road (bg) logs results/WP9/logs/B1_test_<ds>.log
2026-11-04T16:58:30+01:00 | B1 | test carhacking: START scoring test once with ['W_rf_generic'] (selection json committed before)
2026-11-04T16:58:45+01:00 | B1 | test road: START scoring test once with ['Fb'] (selection json committed before)
2026-11-04T16:59:14+01:00 | B1 | fit d11_set_02: done, chosen E; results/WP9/B1_d11_set_02_selection.json
2026-11-04T16:59:15+01:00 | B1 | fit d11_set_03: start (K+1=6); log results/WP9/logs/B1_fit_d11_set_03.log
2026-11-04T16:59:33+01:00 | S2 | round 1 done: chosen MX|L100|b2|m2w5|g15|d0|k1, acceptance MET (results/WP8/S2/r1_eval.json); next: reproducibility re-run (tag r1chk, log results/WP8/logs/S2_sim_r1chk.log) + freeze (tools/WP8_S2_freeze.py, log results/WP8/logs/S2_freeze.log)
2026-11-04T16:59:50+01:00 | B1 | test script bugs fixed (group array, frame_matrix args; first carhacking attempt crashed in aggregation before any output, road in val reproduction); rerunning test carhacking, road
2026-11-04T16:59:53+01:00 | B1 | test carhacking: START scoring test once with ['W_rf_generic'] (selection json committed before)
2026-11-04T17:00:10+01:00 | B1 | test carhacking: DONE results/WP9/B1_carhacking_test.json; exposure registered
2026-11-04T17:00:12+01:00 | B1 | test road: START scoring test once with ['Fb'] (selection json committed before)
2026-11-04T17:02:04+01:00 | B1 | carhacking test DONE (results/WP9/B1_carhacking_test.json); road test aborted by the validation-reproduction guard (xgb booster used all trees, not best iteration): fixed with iteration_range, rerunning road test
2026-11-04T17:02:06+01:00 | B1 | test road: START scoring test once with ['Fb'] (selection json committed before)
2026-11-04T17:02:29+01:00 | B1 | test road: DONE results/WP9/B1_road_test.json; exposure registered
2026-11-04T17:04:05+01:00 | B1 | fit d11_set_03: done, chosen F_noid; results/WP9/B1_d11_set_03_selection.json
2026-11-04T17:04:07+01:00 | B1 | fit d11_set_04: start (K+1=6); log results/WP9/logs/B1_fit_d11_set_04.log
2026-11-04T17:05:00+01:00 | S2 | r1chk reproduces r1 exactly; freeze done (sha256 a8994883...); round-1 result written to notes; running full test suite (log results/WP8/logs/S2_tests.log) + run_all --check
2026-11-04T17:07:13+01:00 | B1 | fit d11_set_04: done, chosen E; results/WP9/B1_d11_set_04_selection.json
2026-11-04T17:09:00+01:00 | B1 | d11 selections committed; running d11 tests set_01..04 once (bg) logs results/WP9/logs/B1_test_d11_set_0N.log
2026-11-04T17:09:02+01:00 | B1 | test d11_set_01: START scoring test once with ['W_xgb_a_ids', 'W_xgb_a_generic'] (selection json committed before)
2026-11-04T17:09:34+01:00 | S2 | DONE: report reports/WP8_S2.md, brief, STATUS S2 -> REVIEW, suite 542 pass, run_all --check OK; committing, stop
2026-11-04T17:09:34+01:00 | B1 | launching control2 (within-capture label permutation, validation only) for all tags, log results/WP9/logs/B1_control2.log
2026-11-04T17:09:36+01:00 | B1 | control2 carhacking: start units ['W_rf_generic']
2026-11-04T17:09:52+01:00 | B1 | control2 carhacking: done results/WP9/B1_carhacking_control2.json
2026-11-04T17:09:54+01:00 | B1 | control2 road: start units ['Fb']
2026-11-04T17:10:22+01:00 | B1 | test d11_set_01: DONE results/WP9/B1_d11_set_01_test.json; exposure registered
2026-11-04T17:10:25+01:00 | B1 | test d11_set_02: START scoring test once with ['E', 'W_xgb_c_generic'] (selection json committed before)
2026-11-04T17:10:46+01:00 | B2 | queued D10e val-only runs (cand select control, T G B) to start after D10o finishes: log results/WP9/logs/B2_D10e_val.log
2026-11-04T17:11:28+01:00 | B1 | control2 road: done results/WP9/B1_road_control2.json
2026-11-04T17:11:30+01:00 | B1 | control2 d11_set_01: start units ['W_xgb_a_ids']
2026-11-04T17:11:40+01:00 | B1 | control2 d11_set_01: done results/WP9/B1_d11_set_01_control2.json
2026-11-04T17:11:43+01:00 | B1 | control2 d11_set_02: start units ['Fb', 'W_xgb_c_ids']
2026-11-04T17:12:48+01:00 | B1 | control2 d11_set_02: done results/WP9/B1_d11_set_02_control2.json
2026-11-04T17:12:51+01:00 | B1 | control2 d11_set_03: start units ['F_noid']
2026-11-04T17:13:43+01:00 | B1 | control2 d11_set_03: done results/WP9/B1_d11_set_03_control2.json
2026-11-04T17:13:46+01:00 | B1 | control2 d11_set_04: start units ['Fb', 'W_xgb_c_generic']
2026-11-04T17:13:50+01:00 | B1 | test d11_set_02: DONE results/WP9/B1_d11_set_02_test.json; exposure registered
2026-11-04T17:13:52+01:00 | B1 | test d11_set_03: START scoring test once with ['F_noid', 'W_rf_generic'] (selection json committed before)
2026-11-04T17:15:06+01:00 | B1 | control2 d11_set_04: done results/WP9/B1_d11_set_04_control2.json
2026-11-04T17:16:35+01:00 | B1 | test d11_set_03: DONE results/WP9/B1_d11_set_03_test.json; exposure registered
2026-11-04T17:16:37+01:00 | B1 | test d11_set_04: START scoring test once with ['E', 'W_xgb_c_generic'] (selection json committed before)
2026-11-04T17:19:01+01:00 | B1 | test d11_set_04: DONE results/WP9/B1_d11_set_04_test.json; exposure registered
2026-11-04T17:20:09+01:00 | S7 | step 0 done: system/runners31.py + tests/v31/test_s7_runners.py (6 pass); next: write S7 tools, dry-run on V31_val, freeze.json, commit BEFORE any H31 file | log notes
2026-11-04T17:23:46+01:00 | B1 | DONE: all test scored once, report reports/WP9_B1.md, STATUS B1 -> REVIEW; committing
2026-11-04T17:24:12+01:00 | B2 | CSECICIDS2018_improved.zip downloaded sha256 7f7b6f80...f6e (10,426,851,729 B), no login; reading members straight from the zip (no extraction)
2026-11-04T17:26:01+01:00 | S7 | network val: start (v3 batch, F1, RC5) | out C:\Users\nouir\AppData\Local\Temp\claude\c--Users-nouir-PFE\157466ee-99c5-4ed8-8a90-0a01fa05dcf5\scratchpad\net_val
2026-11-04T17:26:09+01:00 | B2 | D23x build pass1 (stream zip, resumable per member): tools/WP9_B2_build23.py pass1 (log results/WP9/logs/B2_build_D23x.log); then pass2 assemble | benign 1-in-10 by feature hash, weight 10
2026-11-04T17:26:26+01:00 | S7 | network val: done | v3 macro 0.5826, F1 0.5791, RC5 0.5535
2026-11-04T17:27:58+01:00 | B2 | run/report tools patched (weights for sampled benign, class cap for D23x, cached feature matrix); D10 numbers unaffected (weights 1, caps not binding)
2026-11-04T17:28:36+01:00 | B3 | start: reading briefs done; D12 is ONE 24 h timeline (no run/file id recoverable), WP5 time-block split (1800 s) is the run-level equivalent; writing lock + pre-registration | next: tools/WP9_B3_lock.py, notes/WP9_B3.md, commit BEFORE training
2026-11-04T17:28:58+01:00 | S7 | system simulation valdry: start | material val; chunks results/WP8/S7/parts/sim_valdry_*; log results/WP8/logs/S7_sim_valdry.log
2026-11-04T17:28:59+01:00 | S7 | sim valdry v31 K: start | chunk sim_valdry_v31_K.pkl
2026-11-04T17:29:00+01:00 | S7 | sim valdry v31 K: done | chunk sim_valdry_v31_K.pkl
2026-11-04T17:29:15+01:00 | S7 | sim valdry v31 C: start | chunk sim_valdry_v31_C.pkl
2026-11-04T17:29:16+01:00 | S7 | sim valdry v31 C: done | chunk sim_valdry_v31_C.pkl
2026-11-04T17:29:29+01:00 | S7 | sim valdry v31_RC5 K: start | chunk sim_valdry_v31_RC5_K.pkl
2026-11-04T17:29:30+01:00 | S7 | sim valdry v31_RC5 K: done | chunk sim_valdry_v31_RC5_K.pkl
2026-11-04T17:29:47+01:00 | S7 | sim valdry v31_RC5 C: start | chunk sim_valdry_v31_RC5_C.pkl
2026-11-04T17:29:48+01:00 | S7 | sim valdry v31_RC5 C: done | chunk sim_valdry_v31_RC5_C.pkl
2026-11-04T17:30:01+01:00 | S7 | sim valdry v31_mcSS K: start | chunk sim_valdry_v31_mcSS_K.pkl
2026-11-04T17:30:02+01:00 | S7 | sim valdry v31_mcSS K: done | chunk sim_valdry_v31_mcSS_K.pkl
2026-11-04T17:30:18+01:00 | S7 | sim valdry v31_mcSS C: start | chunk sim_valdry_v31_mcSS_C.pkl
2026-11-04T17:30:18+01:00 | S7 | sim valdry v31_mcSS C: done | chunk sim_valdry_v31_mcSS_C.pkl
2026-11-04T17:30:51+01:00 | S7 | freeze: fit cross recipe (V31 train only) + b1.5 system | tools/WP8_S7_freeze.py fit
2026-11-04T17:31:24+01:00 | S7 | V2X VeReMi val: start | parts C:\Users\nouir\AppData\Local\Temp\claude\c--Users-nouir-PFE\157466ee-99c5-4ed8-8a90-0a01fa05dcf5\scratchpad\v2x_val\v2x_parts
2026-11-04T17:31:25+01:00 | S7 | vehicle sources val: start | 10 drives, 8 routes
2026-11-04T17:31:27+01:00 | S7 | vehicle sources val: done | K runs 1200, C windows 665
2026-11-04T17:31:52+01:00 | S7 | system simulation valdry: done | results/WP8/S7/system_valdry.json
2026-11-04T17:32:05+01:00 | S7 | V2X VeReMi val: done | 409 ego series
2026-11-04T17:32:10+01:00 | B3 | lock + pre-registration committed (locks/WP9_veremi.json, notes/WP9_B3.md) | next: tools/WP9_B3_build.py features (cache ../data_extra/cache_v3/WP9/B3), then fit candidates
2026-11-04T17:32:33+01:00 | B3 | launch build train+val features (tracker refit ~10 min): log results/WP9/logs/B3_build.log; cmd: python -I -u -W ignore tools/WP9_B3_build.py --parts train val
2026-11-04T17:34:33+01:00 | S7 | regression check fusion: start | tools/WP8_S7_regress.py
2026-11-04T17:34:35+01:00 | S7 | regression check fusion: done | pass=True
2026-11-04T17:34:35+01:00 | S7 | regression check gps: start | tools/WP8_S7_regress.py
2026-11-04T17:34:43+01:00 | S7 | regression check gps: done | pass=True
2026-11-04T17:34:43+01:00 | S7 | regression check comma: start | tools/WP8_S7_regress.py
2026-11-04T17:34:45+01:00 | S7 | regression check comma: done | pass=True
2026-11-04T17:34:45+01:00 | S7 | regression check lidar: start | tools/WP8_S7_regress.py
2026-11-04T17:35:37+01:00 | S7 | regression check lidar: done | pass=True
2026-11-04T17:35:37+01:00 | S7 | regression check can: start | tools/WP8_S7_regress.py
2026-11-04T17:35:37+01:00 | S7 | regression check can: done | pass=True
2026-11-04T17:35:37+01:00 | S7 | regression check network: start | tools/WP8_S7_regress.py
2026-11-04T17:35:37+01:00 | S7 | regression check network: done | pass=True
2026-11-04T17:35:37+01:00 | S7 | regression check v2x: start | tools/WP8_S7_regress.py
2026-11-04T17:35:38+01:00 | S7 | regression check v2x: done | pass=True
2026-11-04T17:40:15+01:00 | S7 | pre-freeze: tools written (lib, odom, kitti, comma, lidar, lidar_check, can, net, v2x, veh, blame, domains, sim, regress, freeze); dry runs on V31_val: net/veh/v2x sources reproduce S4/S2 caches exactly, sim in-sample reproduces frozen_system31 check (K FA 1.80 %, 4.53/h, det 72.87 %), regression R2 all pass (results/WP8/S7/regression.json); running full test suite + run_all --check (logs results/WP8/logs/S7_tests.log, S7_runall_check.log); next: freeze.json hash, commit, then H31 verify
2026-11-04T17:45:11+01:00 | S7 | V2AIX dry run on v3 test recordings (V31_val), not H31 | 12 per environment
2026-11-04T17:45:11+01:00 | S7 | V2AIX H31: start | 24 recordings, 24 same site-day as a v3 train recording; out results/WP8/S7/v2aix.json
2026-11-04T17:45:38+01:00 | S7 | V2AIX H31: done | FA physics Mobile 0.0000, egos 3
2026-11-04T17:45:53+01:00 | B3 | features built (train 1.36M, val 325k; tracker refit sa=1.99); launching candidate fits: log results/WP9/logs/B3_fit.log cmd: python -I -u -W ignore tools/WP9_B3_fit.py --select
2026-11-04T17:45:55+01:00 | B3 | fit xgb_A_plaus_d6: START (log results/WP9/logs/B3_fit.log)
2026-11-04T17:46:14+01:00 | S7 | freeze.json written | 610 code files, parent commit 35e62750
2026-11-04T17:46:22+01:00 | S7 | FREEZE committed: results/WP8/S7/freeze.json (sha256 of 39 artefact files + 610 code files, parent commit 35e6275); no H31 file opened before this commit; next: verify H31 sha256 vs locks, then odometry / LiDAR / CAN / network / V2X / V2AIX builds, then ONE scoring
2026-11-04T17:46:30+01:00 | S7 | verify H31 files against locks/H31.json: start | tools/WP8_S7_verify.py; result results/WP8/S7/h31_verify.json
2026-11-04T17:50:10+01:00 | B3 | fit xgb_A_plaus_d6: DONE val macro-F1 0.8489 FPR 0.0100
2026-11-04T17:50:10+01:00 | B3 | fit xgb_A_plaus_d8: START (log results/WP9/logs/B3_fit.log)
2026-11-04T17:52:12+01:00 | S7 | verify H31 files: done | all_ok=True, 43 items
2026-11-04T17:53:46+01:00 | B3 | fit xgb_A_plaus_d8: DONE val macro-F1 0.8494 FPR 0.0100
2026-11-04T17:53:46+01:00 | B3 | fit xgb_A_noT_d6: START (log results/WP9/logs/B3_fit.log)
2026-11-04T17:58:05+01:00 | B3 | fit xgb_A_noT_d6: DONE val macro-F1 0.8299 FPR 0.0100
2026-11-04T17:58:05+01:00 | B3 | fit xgb_A_noT_d8: START (log results/WP9/logs/B3_fit.log)
2026-11-04T18:01:44+01:00 | B3 | fit xgb_A_noT_d8: DONE val macro-F1 0.8297 FPR 0.0100
2026-11-04T18:01:44+01:00 | B3 | fit xgb_B_plaus_ps_d6: START (log results/WP9/logs/B3_fit.log)
2026-11-04T18:05:56+01:00 | B3 | fit xgb_B_plaus_ps_d6: DONE val macro-F1 0.8051 FPR 0.0100
2026-11-04T18:05:56+01:00 | B3 | fit xgb_B_plaus_ps_d8: START (log results/WP9/logs/B3_fit.log)
2026-11-04T18:09:33+01:00 | B3 | fit xgb_B_plaus_ps_d8: DONE val macro-F1 0.8061 FPR 0.0100
2026-11-04T18:09:33+01:00 | B3 | fit xgb_C_raw_d6: START (log results/WP9/logs/B3_fit.log)
2026-11-04T18:16:30+01:00 | B3 | fit xgb_C_raw_d6: DONE val macro-F1 0.5256 FPR 0.0100
2026-11-04T18:16:30+01:00 | B3 | fit xgb_C_raw_d8: START (log results/WP9/logs/B3_fit.log)
2026-11-04T18:22:56+01:00 | B3 | fit xgb_C_raw_d8: DONE val macro-F1 0.5269 FPR 0.0100
2026-11-04T18:22:56+01:00 | B3 | fit xgb_D_all_d6: START (log results/WP9/logs/B3_fit.log)
2026-11-04T18:39:36+01:00 | B3 | fit xgb_D_all_d6: DONE val macro-F1 0.9173 FPR 0.0100
2026-11-04T18:39:36+01:00 | B3 | fit xgb_D_all_d8: START (log results/WP9/logs/B3_fit.log)
2026-11-04T18:51:57+01:00 | B3 | fit xgb_D_all_d8: DONE val macro-F1 0.9186 FPR 0.0100
2026-11-04T18:51:57+01:00 | B3 | fit xgb_D_noT_d6: START (log results/WP9/logs/B3_fit.log)
2026-11-04T19:08:17+01:00 | B3 | fit xgb_D_noT_d6: DONE val macro-F1 0.9174 FPR 0.0100
2026-11-04T19:08:17+01:00 | B3 | fit xgb_D_noT_d8: START (log results/WP9/logs/B3_fit.log)
2026-11-04T19:18:23+01:00 | B3 | fit xgb_D_noT_d8: DONE val macro-F1 0.9178 FPR 0.0100
2026-11-04T19:18:23+01:00 | B3 | fit rf_A_plaus: START (log results/WP9/logs/B3_fit.log)
2026-11-04T19:22:10+01:00 | B3 | fit rf_A_plaus: DONE val macro-F1 0.8466 FPR 0.0100
2026-11-04T19:22:10+01:00 | B3 | fit rf_D_all: START (log results/WP9/logs/B3_fit.log)
2026-11-04T19:26:50+01:00 | B3 | fit rf_D_all: DONE val macro-F1 0.9014 FPR 0.0100
2026-11-04T19:27:02+01:00 | B3 | select: chosen xgb_D_noT_d6 val macro-F1 0.9174; results/WP9/B3_selection.json
2026-11-05T17:21:51+01:00 | B3 | controls: START chosen-unit importance + shuffled + within-block permutation (log results/WP9/logs/B3_controls.log)
2026-11-05T17:21:52+01:00 | B2 | resumed after limit reset: D10o + D10e val/control done (all 3 protocols), D23x pass1 parts done; next: fix labels, pass2, D23x splits+lock, D23x val, then test stages
2026-11-05T17:21:59+01:00 | S7 | resume after usage limit: freeze 8aac3dd committed, H31 verify all_ok=True (43 items), NO H31 chunk scored yet (parts empty); starting odometry (3 procs, bg) log results/WP8/logs/S7_odom.log; next kitti/comma/lidar/can/net/v2x/v2aix builds
2026-11-05T17:21:59+01:00 | B2 | D23x pass2 start (log results/WP9/logs/B2_build_D23x_pass2.log)
2026-11-05T17:22:28+01:00 | S7 | CAN capture ambient_dyno_drive_benign_anomaly: start (IncrementalCan vs batch) | part can_test_ambient_dyno_drive_benign_anomaly.json
2026-11-05T17:22:38+01:00 | B2 | D10e G registered control FAILED the max-AUC rule (rf_c60: AUC 0.52/0.56/0.62, macro-F1 0.085 vs real 0.994); registered verdict stays FAIL; diagnostic amendment: 7 more seeds, tools/WP9_B2_ctl_extra.py D10e G (log results/WP9/logs/B2_ctl_extra.log)
2026-11-05T17:23:54+01:00 | S7 | CAN capture ambient_dyno_drive_benign_anomaly: done | mismatches 0/0, p99 178.4 ms
2026-11-05T17:23:54+01:00 | S7 | CAN capture ambient_dyno_drive_extended_short: start (IncrementalCan vs batch) | part can_test_ambient_dyno_drive_extended_short.json
2026-11-05T17:25:16+01:00 | S7 | CAN capture ambient_dyno_drive_extended_short: done | mismatches 0/0, p99 171.1 ms
2026-11-05T17:25:16+01:00 | S7 | CAN capture ambient_dyno_reverse: start (IncrementalCan vs batch) | part can_test_ambient_dyno_reverse.json
2026-11-05T17:25:29+01:00 | S7 | CAN capture ambient_dyno_reverse: done | mismatches 0/0, p99 194.8 ms
2026-11-05T17:25:29+01:00 | S7 | CAN capture ambient_highway_street_driving_diagnostics: start (IncrementalCan vs batch) | part can_test_ambient_highway_street_driving_diagnostics.json
2026-11-05T17:27:21+01:00 | S7 | CAN capture ambient_highway_street_driving_diagnostics: done | mismatches 0/0, p99 183.0 ms
2026-11-05T17:27:21+01:00 | S7 | CAN capture correlated_signal_attack_3: start (IncrementalCan vs batch) | part can_test_correlated_signal_attack_3.json
2026-11-05T17:27:25+01:00 | S7 | CAN capture correlated_signal_attack_3: done | mismatches 0/0, p99 161.6 ms
2026-11-05T17:27:25+01:00 | S7 | CAN capture correlated_signal_attack_3_masquerade: start (IncrementalCan vs batch) | part can_test_correlated_signal_attack_3_masquerade.json
2026-11-05T17:27:29+01:00 | S7 | CAN capture correlated_signal_attack_3_masquerade: done | mismatches 0/0, p99 156.3 ms
2026-11-05T17:27:29+01:00 | S7 | CAN capture fuzzing_attack_3: start (IncrementalCan vs batch) | part can_test_fuzzing_attack_3.json
2026-11-05T17:27:30+01:00 | S7 | CAN capture fuzzing_attack_3: done | mismatches 0/0, p99 49.1 ms
2026-11-05T17:27:30+01:00 | S7 | CAN capture max_engine_coolant_temp_attack: start (IncrementalCan vs batch) | part can_test_max_engine_coolant_temp_attack.json
2026-11-05T17:27:36+01:00 | S7 | CAN capture max_engine_coolant_temp_attack: done | mismatches 0/0, p99 168.8 ms
2026-11-05T17:27:36+01:00 | S7 | CAN capture max_engine_coolant_temp_attack_masquerade: start (IncrementalCan vs batch) | part can_test_max_engine_coolant_temp_attack_masquerade.json
2026-11-05T17:27:41+01:00 | S7 | CAN capture max_engine_coolant_temp_attack_masquerade: done | mismatches 0/0, p99 125.5 ms
2026-11-05T17:27:41+01:00 | S7 | CAN capture max_speedometer_attack_3: start (IncrementalCan vs batch) | part can_test_max_speedometer_attack_3.json
2026-11-05T17:28:00+01:00 | S7 | CAN capture max_speedometer_attack_3: done | mismatches 0/0, p99 138.9 ms
2026-11-05T17:28:00+01:00 | S7 | CAN capture max_speedometer_attack_3_masquerade: start (IncrementalCan vs batch) | part can_test_max_speedometer_attack_3_masquerade.json
2026-11-05T17:28:17+01:00 | S7 | CAN capture max_speedometer_attack_3_masquerade: done | mismatches 0/0, p99 129.8 ms
2026-11-05T17:28:17+01:00 | S7 | CAN capture reverse_light_off_attack_3: start (IncrementalCan vs batch) | part can_test_reverse_light_off_attack_3.json
2026-11-05T17:28:28+01:00 | S7 | CAN capture reverse_light_off_attack_3: done | mismatches 0/0, p99 117.3 ms
2026-11-05T17:28:28+01:00 | S7 | CAN capture reverse_light_off_attack_3_masquerade: start (IncrementalCan vs batch) | part can_test_reverse_light_off_attack_3_masquerade.json
2026-11-05T17:28:39+01:00 | S7 | CAN capture reverse_light_off_attack_3_masquerade: done | mismatches 0/0, p99 109.9 ms
2026-11-05T17:28:39+01:00 | S7 | CAN capture reverse_light_on_attack_3: start (IncrementalCan vs batch) | part can_test_reverse_light_on_attack_3.json
2026-11-05T17:28:52+01:00 | S7 | CAN capture reverse_light_on_attack_3: done | mismatches 0/0, p99 104.5 ms
2026-11-05T17:28:52+01:00 | S7 | CAN capture reverse_light_on_attack_3_masquerade: start (IncrementalCan vs batch) | part can_test_reverse_light_on_attack_3_masquerade.json
2026-11-05T17:29:04+01:00 | S7 | CAN capture reverse_light_on_attack_3_masquerade: done | mismatches 0/0, p99 114.3 ms
2026-11-05T17:29:04+01:00 | S7 | CAN capture accelerator_attack_drive_2: start (IncrementalCan vs batch) | part can_test_accelerator_attack_drive_2.json
2026-11-05T17:29:06+01:00 | S7 | comma Chunk_2 builder start (bg) log results/WP8/logs/S7_comma.log; resumable per route
2026-11-05T17:29:21+01:00 | S7 | CAN capture accelerator_attack_drive_2: done | mismatches 0/0, p99 149.0 ms
2026-11-05T17:29:21+01:00 | S7 | CAN capture accelerator_attack_reverse_2: start (IncrementalCan vs batch) | part can_test_accelerator_attack_reverse_2.json
2026-11-05T17:29:43+01:00 | S7 | CAN capture accelerator_attack_reverse_2: done | mismatches 0/0, p99 151.9 ms
2026-11-05T17:30:44+01:00 | S7 | odometry done (13 drives); starting KITTI vehicle records (log S7_kitti.log) and LiDAR per-scan scoring (3 procs, log S7_lidar.log, chunks results/WP8/S7/parts/lidar_*.pkl)
2026-11-05T17:33:30+01:00 | S7 | network test: start (v3 batch, F1, RC5) | out C:\Users\nouir\PFE\codes_v3\results\WP8\S7
2026-11-05T17:34:12+01:00 | S7 | network test: done | v3 macro 0.6589, F1 0.6589, RC5 0.6276
2026-11-05T17:34:52+01:00 | B2 | D23x pass2 done (7.6M stored rows); splits -> locks/WP9_D23x.json
2026-11-05T17:35:27+01:00 | S7 | V2X VeReMi test: start | parts C:\Users\nouir\PFE\data_extra\cache_v3\WP8\S7\v2x_parts
2026-11-05T17:36:24+01:00 | B2 | D23x lock committed; start D23x val-only runs (cand select control; T G B), log results/WP9/logs/B2_D23x_val.log
2026-11-05T17:36:40+01:00 | B2 | TEST stage (scored once each) D10o then D10e, protocols T G B: log results/WP9/logs/B2_D10_test.log; run.py refuses rescoring if *_test.json exists; resumable
2026-11-05T17:36:59+01:00 | S7 | V2X VeReMi test: done | 728 ego series
2026-11-05T17:38:40+01:00 | S7 | vehicle sources h31: start | 13 drives, 21 routes
2026-11-05T17:38:49+01:00 | S7 | vehicle sources h31: done | K runs 1560, C windows 1577
2026-11-05T17:41:00+01:00 | S7 | scored so far (each ONCE, chunks on disk): CAN 17 captures (parts/can_test_*), network D10 test (network.json, net.pkl), VeReMi test ego sources (v2x.pkl), KITTI vehicle records 13 drives, comma Chunk_2 21 routes, kveh/cveh sources; LiDAR running (3 procs, chunks parts/lidar_*). Addendum: tools/WP8_S7_pack.py (CAN pack, format only) hash in freeze_addendum.json. CAN p99 > 150 ms on several captures under 5-process load: labelled idle timing re-run planned (Evidence identical). Starting V2AIX full run (bg, log S7_v2aix.log)
2026-11-05T17:41:21+01:00 | S7 | V2AIX H31: start | 674 recordings, 672 same site-day as a v3 train recording; out results/WP8/S7/v2aix.json
2026-11-05T17:45:03+01:00 | S7 | blame rows (M4-12/13): start | tools/WP8_S7_blame.py
2026-11-05T17:45:55+01:00 | S7 | blame rows: done | results/WP8/S7/blame.json
2026-11-05T17:46:34+01:00 | S7 | domain rows gps: start | tools/WP8_S7_domains.py
2026-11-05T17:46:39+01:00 | S7 | domain rows gps: done | 18 rows
2026-11-05T17:46:39+01:00 | S7 | domain rows cross: start | tools/WP8_S7_domains.py
2026-11-05T17:46:45+01:00 | S7 | domain rows cross: done | 36 rows
2026-11-05T17:46:45+01:00 | S7 | domain rows can: start | tools/WP8_S7_domains.py
2026-11-05T17:46:46+01:00 | S7 | domain rows can: done | 1 rows
2026-11-05T17:46:46+01:00 | S7 | domain rows network: start | tools/WP8_S7_domains.py
2026-11-05T17:46:55+01:00 | S7 | V2AIX H31: done | FA physics Mobile 0.0065, egos 7
2026-11-05T17:46:57+01:00 | S7 | domain rows network: done | 36 rows
2026-11-05T17:46:57+01:00 | S7 | domain rows v2x: start | tools/WP8_S7_domains.py
2026-11-05T17:46:59+01:00 | S7 | domain rows v2x: done | 19 rows
2026-11-05T17:47:41+01:00 | B2 | report fix: bootstrap macro-F1 skipped eligible classes absent in a resample (D10o T CI [0.43,0.83] excluded point 0.838); CIs to be recomputed from saved scores (no rescoring) via tools/WP9_B2_recompute.py
2026-11-05T18:05:23+01:00 | B2 | D10o+D10e tests done (6 scored once), committed; waiting for D23x val (log results/WP9/logs/B2_D23x_val.log), then D23x test
2026-11-05T18:13:13+01:00 | B3 | controls: DONE all_pass=False red_flag=False; results/WP9/B3_controls.json
2026-11-05T18:13:20+01:00 | B3 | controls done: shuffled rows AUC 0.496 pass; within-block perm 0.377 FAIL; see log; launching post-hoc seeds diagnostic results/WP9/logs/B3_control_seeds.log
2026-11-05T18:15:47+01:00 | B3 | controls committed; building test features then single test scoring: python -I -u -W ignore tools/WP9_B3_build.py --parts test ; then tools/WP9_B3_test.py (log results/WP9/logs/B3_test.log)
2026-11-05T18:16:52+01:00 | B3 | test: START single scoring (chosen xgb_D_noT_d6)
2026-11-05T18:17:22+01:00 | B3 | test: DONE results/WP9/B3_test.json, exposure registered
2026-11-05T18:17:27+01:00 | B3 | test DONE (single scoring): results/WP9/B3_test.json; exposure registered; next tables + report
2026-11-05T18:18:09+01:00 | B3 | restarted seeds diagnostic (40 trees, 4 seeds, within-block + global sender perm; was too slow); log results/WP9/logs/B3_control_seeds.log
2026-11-05T18:19:23+01:00 | S7 | LiDAR H31 chunks complete (39 parts, each scored once); assembling lidar.pkl then system simulation (tag h31), domains lidar+system, then idle timing (lidar speed, CAN p99)
2026-11-05T18:19:34+01:00 | S7 | domain rows lidar: start | tools/WP8_S7_domains.py
2026-11-05T18:19:35+01:00 | S7 | system simulation h31: start | material h31; chunks results/WP8/S7/parts/sim_h31_*; log results/WP8/logs/S7_sim_h31.log
2026-11-05T18:19:36+01:00 | S7 | sim h31 v31 K: start | chunk sim_h31_v31_K.pkl
2026-11-05T18:19:38+01:00 | S7 | sim h31 v31 K: done | chunk sim_h31_v31_K.pkl
2026-11-05T18:19:41+01:00 | S7 | domain rows lidar: done | 26 rows
2026-11-05T18:20:02+01:00 | S7 | sim h31 v31 C: start | chunk sim_h31_v31_C.pkl
2026-11-05T18:20:03+01:00 | S7 | sim h31 v31 C: done | chunk sim_h31_v31_C.pkl
2026-11-05T18:20:27+01:00 | S7 | sim h31 v3 K: start | chunk sim_h31_v3_K.pkl
2026-11-05T18:20:30+01:00 | S7 | sim h31 v3 K: done | chunk sim_h31_v3_K.pkl
2026-11-05T18:20:54+01:00 | S7 | sim h31 v3 C: start | chunk sim_h31_v3_C.pkl
2026-11-05T18:20:57+01:00 | S7 | sim h31 v3 C: done | chunk sim_h31_v3_C.pkl
2026-11-05T18:21:06+01:00 | B2 | D23x T test start (log results/WP9/logs/B2_D23x_T_test.log)
2026-11-05T18:21:25+01:00 | S7 | sim h31 v31_RC5 K: start | chunk sim_h31_v31_RC5_K.pkl
2026-11-05T18:21:27+01:00 | S7 | sim h31 v31_RC5 K: done | chunk sim_h31_v31_RC5_K.pkl
2026-11-05T18:21:56+01:00 | S7 | sim h31 v31_RC5 C: start | chunk sim_h31_v31_RC5_C.pkl
2026-11-05T18:21:58+01:00 | S7 | sim h31 v31_RC5 C: done | chunk sim_h31_v31_RC5_C.pkl
2026-11-05T18:22:26+01:00 | S7 | sim h31 v31_blameA3 K: start | chunk sim_h31_v31_blameA3_K.pkl
2026-11-05T18:22:27+01:00 | S7 | sim h31 v31_blameA3 K: done | chunk sim_h31_v31_blameA3_K.pkl
2026-11-05T18:22:56+01:00 | S7 | sim h31 v31_blameA3 C: start | chunk sim_h31_v31_blameA3_C.pkl
2026-11-05T18:22:58+01:00 | S7 | sim h31 v31_blameA3 C: done | chunk sim_h31_v31_blameA3_C.pkl
2026-11-05T18:23:28+01:00 | S7 | sim h31 v31_b15 K: start | chunk sim_h31_v31_b15_K.pkl
2026-11-05T18:23:29+01:00 | S7 | sim h31 v31_b15 K: done | chunk sim_h31_v31_b15_K.pkl
2026-11-05T18:23:59+01:00 | S7 | sim h31 v31_b15 C: start | chunk sim_h31_v31_b15_C.pkl
2026-11-05T18:24:00+01:00 | S7 | sim h31 v31_b15 C: done | chunk sim_h31_v31_b15_C.pkl
2026-11-05T18:24:04+01:00 | B2 | D23x T test scored (0.9257). Amendment diagnostics: XGB shuffled controls for failed RF controls (tools/WP9_B2_ctl_xgb.py D10e G; D23x T), log results/WP9/logs/B2_ctl_xgb.log
2026-11-05T18:24:28+01:00 | S7 | sim h31 v31_mcSS K: start | chunk sim_h31_v31_mcSS_K.pkl
2026-11-05T18:24:29+01:00 | S7 | sim h31 v31_mcSS K: done | chunk sim_h31_v31_mcSS_K.pkl
2026-11-05T18:24:59+01:00 | S7 | sim h31 v31_mcSS C: start | chunk sim_h31_v31_mcSS_C.pkl
2026-11-05T18:25:01+01:00 | S7 | sim h31 v31_mcSS C: done | chunk sim_h31_v31_mcSS_C.pkl
2026-11-05T18:31:21+01:00 | B3 | DONE: report reports/WP9_B3.md, brief, STATUS B3 -> REVIEW; committing
2026-11-05T18:31:37+01:00 | S7 | system simulation h31: done | results/WP8/S7/system_h31.json
2026-11-05T18:31:38+01:00 | S7 | domain rows system: start | tools/WP8_S7_domains.py
2026-11-05T18:31:45+01:00 | S7 | domain rows system: done | 24 rows
2026-11-05T18:32:07+01:00 | S7 | system simulation h31 DONE (system_h31.json; scores/S7/system_*), domain rows done; running lidar_check speed+v3sample (idle machine) then CAN idle timing re-run (labelled), then report generation
2026-11-05T18:32:08+01:00 | S7 | lidar check speed: start | tools/WP8_S7_lidar_check.py
2026-11-05T18:36:12+01:00 | S7 | lidar check speed: done | {"scans": 1297, "warmup_excluded": 3, "median_ms": 111.88509999999496, "p95_ms": 131.28689999998642, "p99_ms": 141.62465200000497, "max_ms": 153.0963000000014, "rule": "median <= 100 ms, p99 <= 250 ms
2026-11-05T18:36:12+01:00 | S7 | lidar check v3sample: start | tools/WP8_S7_lidar_check.py
2026-11-05T18:39:27+01:00 | B4 | run tools/WP9_B4_lock.py (AV-GPS + KITTI locks) | write notes/WP9_B4.md pre-registration, commit locks+notes before any training
2026-11-05T18:40:45+01:00 | B4 | pre-registration notes/WP9_B4.md + locks written; committing | build LiDAR descriptor rows (3 procs, resumable) and AV-GPS fit
2026-11-05T18:41:13+01:00 | B4 | LiDAR descriptor build smoke test on drive 0048 | full build 3 procs if ok
2026-11-05T18:41:30+01:00 | S7 | lidar check v3sample: done | {"scans": 104, "alarm_disagreements": 0, "max_abs_stat_diff": 0.009282970550576142, "median_abs_stat_diff": 0.0, "label": "sample check of the fast-path v3 columns against the literal frozen v3 LidarD
2026-11-05T18:41:41+01:00 | B4 | LiDAR descriptor build FULL start (bg, log results/WP9/logs/B4_lidar_build.log, resumable per drive) | meanwhile AV-GPS lib
2026-11-05T18:41:55+01:00 | S7 | decision before the repeats: M4-8 speed and M4-10 p99 are JUDGED on the first runs (lidar median 111.9 ms with 2 other python processes; CAN p99 > 150 ms on several captures under load). Repeat timings (LiDAR speed_run2, CAN idle) are labelled re-runs of timing only, reported next to the first runs, not used to flip a verdict
2026-11-05T18:41:57+01:00 | S7 | lidar check speed: start | tools/WP8_S7_lidar_check.py
2026-11-05T18:42:46+01:00 | B4 | AV-GPS fit/selection on validation (tools/WP9_B4_gps_fit.py) | controls script
2026-11-05T18:44:04+01:00 | B4 | AV-GPS controls on validation (tools/WP9_B4_gps_controls.py) | commit, then v3 GPS layers script
2026-11-05T18:47:05+01:00 | B2 | D23x G test start (log results/WP9/logs/B2_D23x_G_test.log)
2026-11-05T18:47:33+01:00 | B4 | AV-GPS amendments 1 (extra sets F_kin_noVS, F_pos after proxy-only AUC 0.997) and 2 (row-shuffle with fixed rounds); re-run fit + controls on validation | commit, then v3 GPS layers + test
2026-11-05T18:55:18+01:00 | B4 | AV-GPS controls done, amendments 1+2 written; committing selection+controls before test | run tools/WP9_B4_gps_test.py and tools/WP9_B4_gps_v3.py (test, once)
2026-11-05T18:55:27+01:00 | B4 | AV-GPS TEST scoring (supervised Case I+II) | v3 GPS layers test
2026-11-05T18:56:02+01:00 | S7 | lidar check speed: done | {"scans": 1297, "warmup_excluded": 3, "median_ms": 147.8506000000266, "p95_ms": 188.78261999997792, "p99_ms": 210.08420800000292, "max_ms": 254.07859999995708, "rule": "median <= 100 ms, p99 <= 250 ms
2026-11-05T18:56:09+01:00 | S7 | CAN idle timing ambient_dyno_drive_benign_anomaly: start | other python processes 7
2026-11-05T18:57:37+01:00 | S7 | CAN idle timing ambient_dyno_drive_extended_short: start | other python processes 7
2026-11-05T18:59:04+01:00 | S7 | CAN idle timing ambient_dyno_reverse: start | other python processes 6
2026-11-05T18:59:14+01:00 | B4 | AV-GPS supervised test done (B4_gps_test.json); running v3 GPS layers on case I (tools/WP9_B4_gps_v3.py, bg, log B4_gps_v3.log) | LiDAR fit when build done
2026-11-05T18:59:17+01:00 | S7 | CAN idle timing ambient_highway_street_driving_diagnostics: start | other python processes 7
2026-11-05T19:00:16+01:00 | B4 | AV-GPS tests done (supervised + v3 layers); committing results | LiDAR fit after build finishes
2026-11-05T19:01:14+01:00 | S7 | CAN idle timing correlated_signal_attack_3: start | other python processes 6
2026-11-05T19:01:19+01:00 | S7 | CAN idle timing correlated_signal_attack_3_masquerade: start | other python processes 6
2026-11-05T19:01:23+01:00 | S7 | CAN idle timing fuzzing_attack_3: start | other python processes 6
2026-11-05T19:01:25+01:00 | S7 | CAN idle timing max_engine_coolant_temp_attack: start | other python processes 6
2026-11-05T19:01:31+01:00 | S7 | CAN idle timing max_engine_coolant_temp_attack_masquerade: start | other python processes 6
2026-11-05T19:01:38+01:00 | S7 | CAN idle timing max_speedometer_attack_3: start | other python processes 6
2026-11-05T19:01:59+01:00 | S7 | CAN idle timing max_speedometer_attack_3_masquerade: start | other python processes 6
2026-11-05T19:02:22+01:00 | S7 | CAN idle timing reverse_light_off_attack_3: start | other python processes 6
2026-11-05T19:02:38+01:00 | S7 | CAN idle timing reverse_light_off_attack_3_masquerade: start | other python processes 6
2026-11-05T19:02:53+01:00 | S7 | CAN idle timing reverse_light_on_attack_3: start | other python processes 6
2026-11-05T19:03:10+01:00 | S7 | CAN idle timing reverse_light_on_attack_3_masquerade: start | other python processes 6
2026-11-05T19:03:27+01:00 | S7 | CAN idle timing accelerator_attack_drive_2: start | other python processes 7
2026-11-05T19:03:47+01:00 | S7 | CAN idle timing accelerator_attack_reverse_2: start | other python processes 6
2026-11-05T19:04:20+01:00 | S7 | CAN idle timing: done | p99 max 304.8 ms
2026-11-05T19:04:35+01:00 | S7 | timing repeats done (LiDAR median 111.9 ms first run / 147.9 repeat with 2 / 7 other python processes; CAN p99 max 195 ms loaded / 305 ms repeat with up to 7 other processes; Evidence identical). Post-hoc diagnostic without KITTI drive 0093 running (labelled, not a verdict). M4 verdict by make_report_v31.py: see results/WP8/S7/m4_verdict.json
2026-11-05T19:04:37+01:00 | S7 | POST-HOC diagnostic (labelled, not a verdict): sim without KITTI drive 0093, tag h31_no0093 | tools/WP8_S7_posthoc.py
2026-11-05T19:04:39+01:00 | S7 | system simulation h31_no0093: start | material h31; chunks results/WP8/S7/parts/sim_h31_no0093_*; log results/WP8/logs/S7_sim_h31_no0093.log
2026-11-05T19:04:41+01:00 | S7 | sim h31_no0093 v31 K: start | chunk sim_h31_no0093_v31_K.pkl
2026-11-05T19:04:42+01:00 | S7 | sim h31_no0093 v31 K: done | chunk sim_h31_no0093_v31_K.pkl
2026-11-05T19:05:09+01:00 | S7 | sim h31_no0093 v31 C: start | chunk sim_h31_no0093_v31_C.pkl
2026-11-05T19:05:10+01:00 | S7 | sim h31_no0093 v31 C: done | chunk sim_h31_no0093_v31_C.pkl
2026-11-05T19:05:21+01:00 | B4 | LiDAR rows built (46 pkl); LiDAR fit on validation (bg, log B4_lidar_fit.log) | controls, commit, then test
2026-11-05T19:05:35+01:00 | S7 | sim h31_no0093 v3 K: start | chunk sim_h31_no0093_v3_K.pkl
2026-11-05T19:05:37+01:00 | S7 | sim h31_no0093 v3 K: done | chunk sim_h31_no0093_v3_K.pkl
2026-11-05T19:06:01+01:00 | S7 | sim h31_no0093 v3 C: start | chunk sim_h31_no0093_v3_C.pkl
2026-11-05T19:06:04+01:00 | S7 | sim h31_no0093 v3 C: done | chunk sim_h31_no0093_v3_C.pkl
2026-11-05T19:07:25+01:00 | S7 | system simulation h31_no0093: done | results/WP8/S7/system_h31_no0093.json
2026-11-05T19:10:22+01:00 | B4 | LiDAR fit done (chosen trial 7); controls on validation (bg, log B4_lidar_controls.log) | commit then test
2026-11-05T19:12:10+01:00 | S8 | start: reading S7 inputs (kitti tool, parts) for drive 0093 diagnosis | root-cause table
2026-11-05T19:13:40+01:00 | S8 | data-quality table (OXTS fields, timestamps, scan counts) for H31 + V31_val + train drives | tools/WP8_S8_dq.py -> results/WP8/S8/dq.json
2026-11-05T19:17:35+01:00 | B2 | D23x B test start (log results/WP9/logs/B2_D23x_B_test.log)
2026-11-05T19:17:44+01:00 | B2 | XGB named controls D23x G, D23x B (log results/WP9/logs/B2_ctl_xgb2.log)
2026-11-05T19:18:32+01:00 | B4 | LiDAR full model RED FLAG (temporal gain 0.91); amendment 3 = static 211-column candidate; committing record, then fit static (bg) | controls static, commit, test
2026-11-05T19:18:56+01:00 | S8 | GPS-domain per-layer clean FA per drive (H31 + V31_val; frozen_gps; clean runs only, 10 phases) | tools/WP8_S8_gps_layers.py -> results/WP8/S8/gps_layers.json (bg, log results/WP8/logs/S8_gps_layers.log)
2026-11-05T19:20:38+01:00 | B4 | LiDAR static fit done (val mean TPR10 0.467); static controls (bg) | commit, then test
2026-11-05T19:21:07+01:00 | B4 | static LiDAR controls ok (no flag); committing then LiDAR TEST scoring (tools/WP9_B4_lidar_test.py, bg) | tables + report
2026-11-05T19:21:39+01:00 | S8 | V2AIX Stationary genuine FA per recording / site (H31, scoring-only diagnostic, no per-message files written) | tools/WP8_S8_v2aix_fa.py -> results/WP8/S8/v2aix_fa.json
2026-11-05T19:22:59+01:00 | B4 | LiDAR test done; generating tables (tools/WP9_B4_report.py), exposure | write reports/WP9_B4.md, brief, STATUS, commit
2026-11-05T19:24:17+01:00 | B4 | report, brief, STATUS REVIEW written; final commit | stop, handback
