# WP8 S1 report: downloads and extraction (2026-11-03)

Status: REVIEW, with one open decision (calibration zips). Details: notes/WP8_S1_download.md.

## Done
- 13 KITTI H31 drives (9 same-day, 4 other-day), velodyne + oxts members: 11.88 GB on disk.
- comma2k19 Chunk_2 (RAV4), Chunk_4 (Civic), Chunk_3 (Civic, V31_val): 4.58 GB on disk.
- V2AIX: 674 H31 recordings extracted from the local zip: 0.82 GB (not committed).
- Total on disk about 17.3 GB; 13.4 GB transferred over HTTP.
- Checks: every member's size and CRC32 equal the member list. Counts equal the locks: 6,239 KITTI scans, comma
  routes and segments (21/194, 16/205, 21/202), 674 V2AIX recordings. V2AIX sha256 per recording equal the lock.
- Locks: sha256 filled for 13 drives, rav4, civic (H31) and civic_chunk3 (V31_val). Value = sha256 of the per-file
  manifest in results/WP8/S1/items/. Calibration zips left null.
- Decision 3 (Civic): no move. V31_val holds 21 Civic routes on disk (Chunk_3, dongle 99c94dc769b5d96e); no overlap
  with H31 Civic routes. results/WP8/S1/S1_check.json.
- Decision 4: DATASETS.md rows D28 (OTIDS) and D02n (Car-Hacking normal_run); sizes and sha256 match the lock (5 of 5).
- G1 guard: tools/WP8_lib.py assert_not_h31, tests/v31/test_h31_guard.py (6 pass).

## Problems and open questions
1. Calibration zips (4): the list says 4100 B; the server gives 4068, 4071, 4073, 4075 B. Not extracted, no lock
   value. Question for the orchestrator: correct the list to the server sizes, and then extract and lock them?
2. One KITTI argument typo stopped one process after drive 0084 (no data affected); the missing drive was fetched
   separately.
3. HTTP totals exceed the list's transfer because of block-cache overhead (KITTI 11.66 GB, comma 1.71 GB).

## Disk
Free: 88.99 GB at the S1 check (15 GB floor checked before each file; start 109.1 GB).

## Results files
- results/WP8/S1/S1_check.json (checks, Civic decision, V2AIX count)
- results/WP8/S1/items/*.json (per-file manifests for the 16 KITTI and comma items)
- Logs: results/WP8/logs/S1_*.log (not committed; ignored by git)
