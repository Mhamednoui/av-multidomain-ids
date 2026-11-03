# WP8 S1 download notes (2026-11-03, worker haiku)

## What was done
- Source of the list: results/WP8/S0/S1_download_list.json (21 items). Method: HTTP range requests through each zip
  directory, only the listed members (tools/WP8_S1_fetch.py, HttpFile copied from tools/WP6_S1_comma_fetch.py),
  python -I. Member size, compressed size and CRC32 checked against the member list before and after each file.
- KITTI: 13 drives fetched (9 same-day 2011_09_26, 4 other-day). Files in data_extra/D04b_kitti_raw_v31/<drive>_sync/.
  Manifests (path, bytes, sha256 per file) in results/WP8/S1/items/. Checks in tools/WP8_S1_locks.py: 6,239 velodyne
  scans and oxts counts equal the lock.
- comma2k19 Chunk_2 (RAV4), Chunk_4 (Civic), Chunk_3 (Civic, V31_val): processed_log CAN / GNSS / IMU + global_pose.
  Route and segment counts equal the lock (Chunk_2 21/194, Chunk_4 16/205, Chunk_3 21/202).
- V2AIX: 674 H31 recordings extracted from the local zip to data_extra/D13_v2aix/extracted_v31/ (not committed).
  Zip sha256 and each recording's sha256 and CRC32 match the lock.
- Locks: sha256 filled for the 13 KITTI drives, rav4 and civic (H31), civic_chunk3 (V31_val). Value = sha256 of the
  per-file manifest (rule written in each manifest). Calibration zips left null (see problems).
- Decision 3 (Civic): V31_val already holds 21 Civic routes on disk (Chunk_3, dongle 99c94dc769b5d96e); none overlap
  H31 Civic routes (Chunk_4, 16 routes, same dongle). No move performed. Recorded in results/WP8/S1/S1_check.json.
- Decision 4: DATASETS.md rows D28 (OTIDS) and D02n (Car-Hacking normal_run). Source page URLs marked "to confirm".
  Sizes match the lock byte-for-byte; sha256 re-checked: 5/5 match.
- G1 guard: tools/WP8_lib.py assert_not_h31, tests/v31/test_h31_guard.py (6 tests pass). Known limit (in the docstring):
  files shared by time split (D10 CSVs, VeReMi, OTIDS Attack_free, V2AIX zip) are not blocked at file level.

## Problems (for the orchestrator)
1. Calibration zips (4 files): the list says 4100 B each; the server gives 4068 (2011_09_26), 4071 (09_29),
   4073 (09_30), 4075 (10_03). Stopped: not extracted, no lock sha256. Decision needed (the list values are
   estimates; fix the list or accept the server sizes as the new lock values).
2. Process mistakes, no data affected: one KITTI argument typo (2011_09_26_drive_0026 instead of 2011_09_29_drive_0026)
   stopped one process after drive 0084; the correct drive was fetched in a separate run. Logged in the journal.
3. Transfer totals differ from the list: HTTP bytes include block-cache overhead (KITTI 11.66 GB, comma 1.71 GB).
   On-disk sizes match the list (KITTI 11.88 GB, comma 4.58 GB, V2AIX 0.82 GB).

## Disk
- Free before: 109.1 GB. Free at the S1 check: 88.99 GB (above the 15 GB floor, checked before each file).
- Downloaded and extracted: about 17.3 GB on disk (13.4 GB HTTP transfer).

## Next
- Decision on the calibration zips (problem 1); then sha256 for the 4 calibration zips and their extraction.

## Calibration zips: resolved (orchestrator decision, 2026-11-03)
- S1 list sizes corrected to the server values (4068 / 4071 / 4073 / 4075 B), with a note in the list.
- Extracted to calib/<day>/<day>/ (zip's own folder): calib_cam_to_cam.txt, calib_imu_to_velo.txt, calib_velo_to_cam.txt.
- Content check: 12 of 12 files parse; expected keys present; all values numeric.
- Comparison with v3 calibration: none found on disk (search of the PFE tree), so nothing to compare.
- Lock locks/H31.json calibration_zips sha256 filled (zip sha256 of the 4 zips).
