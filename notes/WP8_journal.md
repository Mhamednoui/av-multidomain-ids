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
