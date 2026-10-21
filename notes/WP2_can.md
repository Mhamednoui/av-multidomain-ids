# Notes WP2 CAN

## 2026-10-19 S0 start: acceptance rule (written before results)
S0 is MET if: (1) licence read from the source page and allows research use; (2) all files of
the DTU article 24805533 are in ../data_extra/D11_can-train-and-test/ with sizes equal to the
published sizes and MD5 equal to the published checksums (if published); (3) archives
extracted with >= 15 GB free left on disk; (4) at least one CSV per vehicle/attack family
parses with python -I (columns, row count, label values listed); (5) DATASETS.md D11 row and
a layout section updated. If disk would breach 15 GB: stop after download+verify and ask.

## 2026-10-19 S0 results
- Licence: CC BY 4.0 (DTU page / figshare API) -> research use allowed.
- Source: figshare article 24805533, one file can-train-and-test.zip, 1,507,455,719 B, published
  MD5 bd6509d670c0a0009cb3ecab34111bcd; local md5sum identical; zipfile.testzip() = None.
  Version on the site is v1 (2023-12-15). The "7.5 GB" in DATASETS.md is the extracted size
  (7,471,445,612 B in the zip listing; 7,471,443,340 B of CSV on disk). Download took ~45 min
  (curl -C -, ~0.5 MB/s). Disk after extraction: 44 GB free (>= 15 GB kept). Zip kept in raw/.
- Extracted with Python zipfile under -I; nothing executed. 236 CSV + README, 193,240,845 frames.
- All 236 files: header timestamp,arbitration_id,data_field,attack; labels only {0,1}; no NaN
  timestamps; data_field hex length 2..17 chars (DLC 1..8, a 17-char = odd length value exists:
  to look at in S1); all start at 1672531200.0 (synthetic epoch).
- Many files have tiny timestamp inversions (<= 0.15 ms, e.g. rpm-3: 100 inversions, 56 on attack
  rows): float precision of epoch seconds; S1 must sort stably or use relative time.
- 174 distinct files of 236 (62 duplicate groups across sets, e.g. set_01 test_02 DoS-3 ==
  set_03 train_01 DoS-3): a vehicle/capture must be assigned to ONE side in S1 splits.
- Accessory captures (accessory-*) have no attack frames (like ROAD accessory); also
  set_04/test_04/force-neutral-2.csv has none. Test sets contain no attack-free file: normal
  frames are inside the attack captures (before/after the attack).
- Files: tools/WP2_s0_verify.py, WP2_s0_summary.py, WP2_s0_extra.py; results/WP2/s0_inventory.json,
  s0_summary.txt, s0_duplicates.json, s0_extra.txt.
- Acceptance rule (1)-(5): all MET (parsed ALL files, not just one per family).

## 2026-10-19 S1 start: acceptance rule (written before results)
S1 (data layer) is MET if all hold:
1. Unified frame format (t, id, dlc, b0..b7, label, attack, capture, vehicle) produced by three
   adapters (ROAD, Car-Hacking, D11); `validate_frame` passes on every capture / file.
2. ROAD: frame count and injected-frame count of each of the 45 captures used by v2 equal the
   numbers in ../codes_v2/results/road_external.log (exact, parsed from that log by a tool);
   label check vs signal_extractions gives the same ours / ROAD numbers as v2 (13 masquerade
   captures, difference <= 2 frames each).
3. Car-Hacking: rows per file == raw line count, injected rows == count of flag T; bytes beyond
   DLC are absent (-1).
4. D11: rows and label counts of each of the 236 files equal results/WP2/s0_inventory.json;
   dlc == len(data_field)/2 (after stripping whitespace); re-encoding the byte columns gives
   back data_field exactly for all files; content-hash groups = 174 distinct / 62 duplicate pairs
   (as S0); in every split no content hash is on both sides; every D11 file is in exactly one
   role per set; the vehicle column is set-level (README) and every contradiction found by the
   ID-set fingerprint check is reported, not hidden.
5. ROAD split: every masquerade capture on the same side as its original; split = v2 split.
6. Unit tests in tests/can/ pass together with the whole suite.
Validation for choices: the only choices made in S1 are the D11 validation hold-out (rule fixed
now: within train_01 of a set, for each attack family with >= 2 captures the highest-numbered
capture goes to val, others stay train) and the Car-Hacking block split (v2, copied). No model
is trained, so no test-set use. Test data are only counted, never scored.

## 2026-10-20 S1 results (numbers from results/WP2/s1_*.json)
- Code: can/frames.py (format, hex<->bytes vectorised, validate_frame, dt_clipped), can/adapters.py
  (ROAD, Car-Hacking, D11), can/splits.py; tools/WP2_S1_{d11_scan,d11_splits,road_carhacking}.py;
  tests/can/test_frames_adapters.py (14 tests; whole suite 133 pass).
- Format: t, id, dlc, b0..b7 (-1 beyond DLC), label, attack, capture, vehicle. Recorded order kept.
- ROAD: 41 usable captures (45 in the table minus 4 accelerator captures with no injected frames; my
  acceptance rule said "45", v2 log lists 41 = correct): frames and injected counts of 41/41 equal the
  v2 log (27,415,983 frames, 62,547 injected); parts equal v2. Label check vs signal_extractions is
  identical to v2's dict (13 masquerade captures, max |diff| 2 frames). Signal CSVs: 105 of 106 IDs,
  ~94% of the log rows; Label sums equal v2's road_signal_labels.
- Car-Hacking: rows == raw lines and injected == T count for all 4 files (= v2). Block split
  reproduces v2 exactly for val, test and train attacks; train normal 9,954,533 here vs 2,488,177 in
  v2 because v2 kept a random 25% of train normal (9,954,533 * 0.25 = 2,488,633). Not a mismatch.
  Timestamps monotone in all 4 files.
- D11: 236 files, 193,240,845 frames, 1,884,401 injected: rows and labels of every file equal the S0
  inventory; re-encoding bytes reproduces data_field in all files; dlc 0..8 (32,378 frames with an
  empty data_field, all in fuzzing files; S0's "hex length 2..17" missed the empty ones); one file
  (set_03/train_01/fuzzing-3) has a trailing TAB in a data_field (the "17 chars"): stripped.
  174 distinct sha256 / 62 duplicate pairs, same pairs as S0.
- Timestamp inversions: 12,527 in 100 files (S0 also 100 files), min dt = -7.9 ms (S0 said <= 0.15 ms).
  12,394 of 12,527 involve an injected frame next to a normal one. Stable re-sorting would move 30,641
  frames (max 14 positions) and change the label sequence at 24,784 positions: it would reshuffle
  injected frames against their context. Decision: keep recorded order, provide dt_clipped(t)
  (negative gaps -> 0). For S2: clip dt, never use the sign of dt as a feature (leak).
- Vehicle check (ID-set Jaccard >= 0.8 clusters over non-fuzzing files, s1_d11_vehicle_check.json):
  4 big clusters = Subaru 71 files, Traverse 56, Silverado 40, Impala 28. They match the README
  mapping EXCEPT set_01/test_04 (README: unknown = Silverado): its 12 files are byte copies of
  set_02/test_01 (known = Traverse) and cluster with Traverse. So set_01/test_04 is Traverse (still
  unseen by the set_01 model trained on Impala; only the README name is wrong). Per-file table
  s1_d11_vehicles.json: 195 files by fingerprint, 41 (fuzzing / systematic / other: random IDs make the ID
  set uninformative) by majority of their (set, subset); 12 files disagree with the README.
- D11 splits (splits_d11.json): one experiment per set; val hold-out = highest-numbered capture of
  each family with >= 2 captures in train_01 (rule fixed before results). No duplicates inside any
  set (excluded_duplicates empty), check_d11_split passes. Cross-set copies exist (62 pairs): do not
  pool sets without dedup by hash.
- Gotcha: background python started with & / Start-Process died twice silently (cause unknown). The
  scan is resumable (cache in ../data_extra/D11_can-train-and-test/s1_scan_cache/, not committed) and
  was finished in the foreground.
- Acceptance rule 1-6: all MET (reports/WP2_S1.md).

## 2026-10-20 S2 start: design and acceptance rule (written before any S2 result)
Step: L1 specification rules as v3 Layers (domain "can", layer "L1", kind "rule"): id_allow (ID allow-list),
dlc (allowed DLC set per ID), period (per periodic ID, early and late arrival vs the learned period, per-ID
tolerance), bus_load (bits in the trailing 1 s), flood (frames with ID <= lowest legit ID in the trailing 1 s).
Data prepared: per-capture compact cache (t, id, dlc, label) in ../data_extra/WP2_S2_cache (tools/WP2_S2_cache.py).
Design decisions fixed before results:
- Unit 1 = frame (causal, recorded order, dt_id = gap to the previous frame of the same ID with dt_clipped; the
  sign of dt is never a feature; trailing-1 s sums use the running maximum of t). Unit 2 = 1 s window
  (floor of the running max t, per capture); window raw score of a rule = max of its frame raw scores in the
  window; window label = holds >= 1 injected frame (as v2 road_windows).
- "Clean" frames (attack-free traffic, the only data rules may calibrate on): ROAD all frames of ambient captures +
  attack captures before the first injected frame minus 1 s; D11 same rule (attack-free / accessory files fully);
  Car-Hacking: blocks of the v2 block split that contain no injected frame.
- Profile (allow-list, DLC sets, periods, tolerances) fitted on clean TRAIN frames; thresholds (ECDF calibration +
  tie-safe 1% budget, Layer.calibrate) on clean VALIDATION frames / windows, separately for the frame unit and the
  window unit. The only hyper-parameter choice, the tolerance variant (quantile q of the training early / late
  deviation and its floor): grid [(0.99, 0.05), (0.999, 0.05), (0.99, 0.25), (0.999, 0.25)], chosen on the validation
  captures of the experiment by the mean window recall of the period layer over the non-masquerade attack types at
  the 1% window budget; ties -> first in grid order. Event-triggered IDs (n < 30 or (q95-q05)/median > 0.5) get no
  timing rule.
- Combined = noisy-or of the calibrated layer scores (frame level, arrays); window level through the common
  harness (common/evaluate.evaluate_domain, method auto on ROAD / Car-Hacking / D11 regime a; noisy_or on regime b
  because the clean calibration has no attack windows).
- ROAD: v2 split (train 15 / val 11 / test 15 captures), profile = clean train frames, thresholds = clean val frames.
- Car-Hacking: v2 block split (splits_carhacking.json), profile = clean train blocks, thresholds = clean val blocks.
- D11, one experiment per set (splits_d11.json). Regime (a) ZERO-SHOT: profile from the set's train files (clean
  parts), thresholds from the set's val hold-out files (clean parts); applied unchanged to all four test subsets
  (known and unknown vehicle). Regime (b) ON-VEHICLE, fixed now: per (set, test subset), from every test file whose
  first injected frame is at t >= 60 s: frames with t < 30 s fit the profile, frames with 30 <= t < 60 s set the
  thresholds (pooled over those files); tolerance variant = the one chosen in regime (a) on the training vehicle's
  validation (no labelled data of the target vehicle exists). Scored frames in BOTH regimes (so they are comparable):
  files with first injection >= 60 s: t >= 60 s only; other files: whole file. A subset with < 3 eligible files is
  reported as "no on-vehicle calibration".
- Metrics: frame level (detection per attack = alarmed injected frames / injected frames; FA = alarmed clean normal
  frames / clean normal frames, and FA on all label-0 frames) and window level (per attack window recall; per
  capture detected? and delay = end of first alarmed attack window - first injected frame; FA windows on clean test
  windows and false alerts per hour). Budgets: 1% at the unit (primary); extra operating points 0.1% and <= 1 false
  alert per hour (~0.028% windows) on ROAD, thresholds still from validation.
ACCEPTANCE RULE S2. MET if all hold:
 1. Five rules implemented as Layer subclasses; calibrated on attack-free data only; tie-safe 1% budget at each unit;
    causal; dt_clipped only; unit tests pass with the whole suite; own files committed.
 2. ROAD test, window level, 1% budget from val: the L1 combination (a) detects the 5 captures that v2's timing model R1
    detected (fuzzing_attack_3, correlated_signal_attack_3, max_speedometer_attack_3, reverse_light_off_attack_3,
    reverse_light_on_attack_3) with delay <= 2 s each; (b) raises no alert in ambient_dyno_reverse (the reverse-driving
    false alarm of v2's payload model) and at most 1% of windows over the test ambient captures. Masquerade captures and
    the coolant capture: no requirement; they are reported, and if missed it is stated that specification rules cannot see
    same-ID same-period masquerade (so the WP target "masquerade <= 1 false alert/hour" is NOT claimed by L1).
 3. Car-Hacking test, 1% window budget: window recall >= 95% for each of DoS, Fuzzy, RPM, Gear.
 4. D11: both regimes reported for all 4 sets x 4 test subsets with per-attack frame and window numbers, FA on clean
    test, delay (no numeric gate; unknown-vehicle results are the deliverable).
 5. Per-layer and harness ablation tables produced for ROAD, Car-Hacking and D11.
If 2 or 3 fails the step is reported NOT MET with the reason (no re-tuning on test).

## 2026-10-20 S2 incident log (before the real run)
- Cache blunder: my first cache stored the attack name as a 40-char string per frame: 39 GB, disk 100% full
  (ENOSPC) for a few minutes (this may have hit other workers). Deleted the cache I had created, rebuilt with int8 attack
  codes: 3.4 GB total (../data_extra/WP2_S2_cache, 236 D11 + 41 ROAD + 4 Car-Hacking files). Free disk afterwards 26 GB.
- RUN 1 (design exactly as pre-registered above) was executed end to end on ROAD as a smoke test and it also scored
  the test captures. Per RULES 5.2 this is the single test use of the pre-registered design; the numbers are kept in
  results/WP2/s2_run1_frozen/ and reported as run 1. Run 1 result: the five captures v2's timing model catches are all
  detected (delay 0.17-0.93 s, by bus_load), reverse driving 0 alerts, but combined false alerts on clean test windows
  3.4% (period 4.4%, bus_load 1.4%): acceptance item 2(b) (<= 1%) fails under the frozen design.
- A VALIDATION finding in run 1 (not a test finding): on the val attack captures the period rule had recall ~0 for
  correlated_signal / max_speedometer / reverse_light although those attacks inject extra frames of an ID; the injected
  ID (0x6E0, p = 10 ms) was classified event-triggered because my periodic test used q95-q05 > 0.5 x median (0.61 on ROAD
  jitter). Change for RUN 2 (applies to ROAD, Car-Hacking and D11 alike, decided before looking at any Car-Hacking / D11
  number): periodic if the INTERQUARTILE range of the gaps <= 0.5 x median (robust to bursts). Nothing else changes.
  Run 2 on ROAD is NOT an independent test (test captures were seen in run 1): it is reported as "revised design",
  run 1 stays the verdict for acceptance item 2. Car-Hacking and D11 are run once, with the revised design.

## 2026-10-21 S2 results (numbers in reports/WP2_S2.md, results/WP2/s2_*.json, s2_d11_tables.md)
- Verdict NOT MET (item 2b): run 1 (frozen) combined FA on clean ROAD test windows 3.4%, ambient 49/1316, > 1%.
  Detection of the five captures with delay <= 1 s and zero alerts in reverse driving are met. Run 2 (IQR) 3.5% FA.
- Car-Hacking window recall DoS 1.0, Fuzzy 1.0, RPM 0.995, Gear 0.995; FA 1.0% (item 3 met).
- D11: regime A on an unknown vehicle alarms on ~100% of windows (ID/DLC allow-list is vehicle-specific); regime B
  brings FA to 1.2-5.9% (one cell 20%), recall 0.78-1.0, all attack files detected.
- Lesson: per-rule 1% budgets compound under noisy-or and the test ambient drives shift vs val: expect 3-4% FA.
- Unit tests tests/can/test_l1.py (causal prefix, calibration on clean); whole suite 154 passed.
