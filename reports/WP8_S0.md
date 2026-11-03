# WP8 S0: fresh hold-out H31 inventory and pre-registration

Date: 2026-11-03    Worker: opus (WP8 v3.1, step S0)

## Summary
- Checked on disk (tools/WP8_S0_inventory.py) and on the public servers (HEAD + zip directory reads only,
  tools/WP8_S0_remote_list.py) which test material v3 never scored. Facts in results/WP8/S0/inventory.json and
  results/WP8/S0/remote/*.json.
- H31 per domain (locks/H31.json):
  - GPS / LiDAR / cross K: FRESH. 13 KITTI raw drives v3 never saw: 9 from 2011_09_26 (4,626 scans; city 0009 0056
    0084 0093, residential 0023 0061 0064, road 0032 0101) + 4 from other days (1,613 scans; 09_29 0004 / 0026,
    09_30 0016, 10_03 0047). Public, no login (avg-kitti S3).
  - comma C: FRESH. Chunk_2 (RAV4, same car, 21 routes, all later than Chunk_1) = primary; Chunk_4 (Honda Civic,
    a car v3 never saw, 16 routes) = cross-vehicle stratum C2. Chunk_3 (Civic) = validation, clean use only.
  - CAN: MIXED. Re-used ROAD test (exposure 7), Car-Hacking (>= 4), D11 (>= 5). Fresh, capture level only: ROAD
    accelerator drive_2 / reverse_2, Car-Hacking normal_run_data.txt, OTIDS Kia Soul (on disk since v1, never
    used in v3; no frame labels).
  - network: RE-USED (D10 test exposure 7, D23 >= 4). No fresh CIC-format traffic without a login.
  - V2X: MIXED. Fresh: 674 V2AIX recordings never extracted (0.82 GB, inside the zip on disk). Re-used: VeReMi
    test (exposure 3), Tampa.
  - system simulation: PARTIALLY FRESH (fresh vehicle block, re-used CAN / NET / V2X streams).
- V31_val (locks/V31_val.json): v3 test material of domains that have a fresh H31 (KITTI 7 drives, comma Chunk_1
  4 routes, V2AIX 304 recordings) moves into validation, together with the v3 val splits. v3 test material of
  domains without fresh data stays in H31 and is not validation.
- Locks: sha256 for every on-disk file (282 files plus the 674 V2AIX zip members, hashed by streaming); for
  downloads: URL, zip bytes, member list with CRC32 and sizes (sha256 filled in S1).
- Pre-registered (notes/WP8_v31.md, committed 1eca013 before any v3.1 result): general rules G1-G10 (H31 guard,
  one scoring by v3 and v3.1 side by side, improvement only on fresh H31 with a paired group-bootstrap CI,
  keep-scores rule 6, regression R1 every step / R2 before H31), step rules S1-S6 on V31_val, M4 rows M4-1..15.
- Key targets: system clean FA <= 3%, <= 10 events/h, SAFE_STOP <= 1/h (S2 must reach 2.5% / 8 / 0.8 on
  validation), K detection >= 70%, held-out >= 60%; LiDAR <= 0.10 s/scan and PointDrop in-domain >= 70% (val) /
  >= 65% (H31); network Evidence delay median <= 30 s, max <= 75 s (1-minute timestamp floor of D10); CAN
  window p99 <= 0.15 s with growth ratio <= 1.5; V2X single ego <= 0.5 compute s per stream s; gps_can wrong
  blame <= 25%; comma GNSS spoof blame correct >= 60%. Phantoms: no target (physics limit).
- S1 list (results/WP8/S0/S1_download_list.json): 13.0 GB transfer, 17.3 GB on disk. Free disk measured
  103-109 GB (not ~47 GB as in the task).
- Tests: python tests/run_tests.py = 484 passed, 0 failed, 3 skipped (cache-dependent).

## Goal of the step
Inventory of fresh hold-out material, lock H31 and V31_val, pre-register every S2-S7 acceptance rule.

## Acceptance rule
WP8 file: "H31 + rules committed before any S2-S7 work". Commits: 64ee899 (locks), 1eca013 (rules, S1 list).

## What was done
- tools/WP8_S0_inventory.py, WP8_S0_remote_list.py, WP8_S0_locks.py, WP8_S0_s1list.py (read only, python -I).
- results/WP8/S0/{inventory.json, remote/*.json (18 MB), sha256_cache.json, S1_download_list.json}.
- locks/H31.json, locks/V31_val.json; notes/WP8_v31.md (inventory table, rules, S1 list); notes/WP8_brief.md S0
  lines; journal lines in notes/WP8_journal.md.

## Results
Acceptance: MET (locks and rules committed; no S2-S7 work exists). Tests 484 passed, 0 failed, 3 skipped.

## Problems, surprises, open questions
1. V2AIX H31 is fresh per recording (the v3 grouping), but 672 of 674 recordings share site and day with a v3
   train recording. Stated as a caveat; no stronger day-level split exists for these strata.
2. Civic CAN wheel speed is not at the Toyota address 0xAA used by crossdomain/comma.py: a Civic decoder must be
   written on V31_val Chunk_3, otherwise C2 uses GNSS / IMU / CAN speed only.
3. OTIDS (Kia Soul) and Car-Hacking normal_run are in ../codes/data and not in DATASETS.md: S1 should register
   them (proposed id D30 OTIDS; D02 addendum for normal_run). Licence: HCRL research terms.
4. Network has no fresh data: its S7 numbers are "re-used test, exposure 7" and cannot be called improvements.
5. N1 network latency target is bounded by D10's 1-minute timestamps; D23 Tue has second resolution but is H31.
6. Supervisor decision: accept moving v3 test material (KITTI, comma Chunk_1, V2AIX) into V31_val.

## Proposed next step
S1: download / extract per results/WP8/S0/S1_download_list.json, verify against the locks, add the H31 guard.
