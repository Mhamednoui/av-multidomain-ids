# WP2 S1: CAN data layer (unified frame format, adapters, splits)

Date: 2026-10-20    Worker: sonnet (medium)

## Goal of the step
Unified frame format (t, id, dlc, bytes, label, attack, capture, vehicle); adapters for ROAD,
Car-Hacking and can-train-and-test (D11); splits (ROAD by capture as v2, D11 own known/unknown sets).

## Acceptance rule (notes/WP2_can.md, "S1 start", written 2026-10-19 before results)
1. Format + three adapters + validate_frame on every capture.
2. ROAD frames / injected equal v2 for each capture; label check as v2 (diff <= 2).
3. Car-Hacking rows == raw lines, injected == count of T.
4. D11 rows and labels == S0 for 236 files; dlc == len/2; byte round trip exact; 174 distinct / 62 duplicate
   pairs; no hash on two sides; vehicle column set-level with contradictions reported.
5. ROAD masquerade with originals; split == v2.
6. Unit tests pass.
Correction: the rule said "45 captures" for ROAD; v2 uses 41 (45 in the table minus 4 accelerator captures).

## What was done
- can/frames.py, can/adapters.py, can/splits.py; tools/WP2_S1_d11_scan.py, WP2_S1_d11_splits.py,
  WP2_S1_road_carhacking.py; tests/can/test_frames_adapters.py (14 tests; full suite 133 pass).
- ROAD parse / label / split code copied from codes_v2/can/road_external.py (stated in the file header);
  decoded signals: signal_extractions/*.csv (no new package). Car-Hacking loader copied from
  codes_v2/can/features.py.
- Results: results/WP2/s1_road.json, s1_carhacking.json, s1_d11_scan.json, s1_d11_acceptance.json,
  s1_d11_dedup.json, s1_d11_vehicle_check.json, s1_d11_vehicles.json, splits_{road,carhacking,d11}.json.
  Derived cache (not committed): ../data_extra/D11_can-train-and-test/s1_scan_cache/.

## Results
| Check | Result | Source |
|---|---|---|
| ROAD captures matching v2 (frames, injected, part) | 41 / 41 (27,415,983 frames, 62,547 injected) | s1_road.json |
| ROAD label check vs signal_extractions | identical to v2; max abs diff 2 frames (13 masquerade captures) | s1_road.json |
| ROAD split | train 15, val 11, test 15 captures; 13 masquerade pairs on the same side | splits_road.json |
| Car-Hacking rows / injected | DoS 3,665,771 / 587,521; Fuzzy 3,838,860 / 491,847; RPM 4,621,702 / 654,897; Gear 4,443,142 / 597,252; equal raw lines and v2 | s1_carhacking.json |
| Car-Hacking block split vs v2 | val, test, train attacks identical; train normal 9,954,533 (v2 kept 25%: 2,488,177) | s1_carhacking.json |
| D11 rows / labels vs S0 | 236 / 236 files equal; 193,240,845 frames, 1,884,401 injected | s1_d11_acceptance.json |
| D11 byte round trip, dlc | exact for all files; dlc 0..8 (32,378 empty payloads, all in fuzzing files) | s1_d11_acceptance.json |
| D11 duplicates | 174 distinct, 62 pairs, same as S0; none inside any set; check_d11_split passes | s1_d11_dedup.json, splits_d11.json |
| D11 injected frames per attack (236 files / 174 distinct) | DoS 684,739 / 483,764; fuzzing 385,356 / 224,403; interval 257,890 / 135,139; triple 214,163 / 111,650; systematic 130,149 / 65,970; double 72,123 / 41,376; speed 43,059 / 24,902; standstill 29,938 / 19,130; rpm 23,555 / 16,811; force-neutral 22,335 / 19,148; rpm-accessory 12,050 / 10,487; speed-accessory 9,044 / 7,524 | s1_d11_acceptance.json |
| Unit tests | 133 passed, 0 failed (14 new) | tests/run_tests.py |

Acceptance: MET (all six items).

## Findings the next steps must know
1. D11 timestamp inversions are not tiny and not random: 12,527 in 100 files, min -7.9 ms (S0 wrote
   <= 0.15 ms), 12,394 of them next to an injected frame. Sorting would move 30,641 frames and change the
   label sequence at 24,784 positions, so the recorded order is kept and `dt_clipped` is provided. The sign
   of dt must not be a feature (it nearly identifies attack frames); L1 timing rules must clip.
2. The README vehicle mapping contradicts the data once: set_01/test_04 (README: Silverado) is a byte copy
   of set_02/test_01 (Traverse) and fingerprints as Traverse. It is still unseen by the set_01 model
   (Impala). The `vehicle` column uses the checked name (s1_d11_vehicles.json); 41 fuzzing / systematic / other
   files could not be fingerprinted (random IDs) and take their subset's majority vehicle (source recorded
   per file).
3. Cross-set copies: pooling D11 sets leaks (e.g. set_01 test_02 = set_03 train). Splits are per set; use
   the sha256 in s1_d11_scan.json before any pooling.
4. Fuzzing files contain frames with an empty data_field (dlc 0); one data_field has a trailing tab.
5. ROAD decoded signals cover 105 of 106 IDs and ~94% of the log rows (IDs without DBC signals are absent).
6. D11 has no attack-free test file: normal frames sit inside attack captures. The val hold-out also
   contains attack-free / accessory captures.

## Problems, surprises, open questions
- Background python jobs of this session died silently twice (not a code error); the scan was made
  resumable and run in the foreground.
- DATASETS.md section 5 (supervisor-owned) needs the corrections in findings 1, 2, 4; I did not edit it.
  The Progress section of workpackages/WP2_can.md is supervisor-owned; not edited.
- Question: the D11 val hold-out uses the same vehicle as train (fine for choosing thresholds, says nothing
  about cross-vehicle choice). Keep, or hold out a vehicle in a later step?

## Proposed next step
S2: L1 specification rules calibrated per vehicle on normal traffic (ROAD ambient train; D11 train per set).
