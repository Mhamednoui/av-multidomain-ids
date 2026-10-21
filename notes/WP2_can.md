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

## 2026-10-21 S3 start: L2a ECU clock-skew fingerprinting (CIDS). Design + acceptance rule, written BEFORE any skew result
Data caveat check (label/timestamp structure only, no skew number seen yet; script output in results/WP2/s3_road_masq_timestamps.json):
- ROAD masquerade logs = the attack log with the legitimate frames of the injected ID REMOVED post hoc (readme: "identical
  log with the conflicting non-injected messages removed"). The injected frames keep their ORIGINAL logger timestamps (100%
  identical to the same frames in the non-masquerade capture). So timestamps are NOT copied from the legit ECU: they are the
  receive times of the real attacker transmitter (laptop / injector via OBD) with its own clock and jitter. Skew can see them
  in principle; but the "ECU silenced" part is an edit (a real attacker would have to suppress the ECU, e.g. bus-off).
  Injected gap statistics vs pre-attack: median gaps equal to 0.1-1% (10.00-10.09 ms vs 9.8-10.4 ms), jitter std sometimes
  larger (correlated_signal 3.7 vs 2.0 ms), coolant 113.9 ms vs 100.0 ms (only 43 frames).
- Car-Hacking injected frames are software timed (known); D11 timestamps have a synthetic epoch and inversions: only dt_clipped.
Method (Cho & Shin 2016), per periodic ID i (periodic = L1 definition: IQR(gap) <= 0.5 median, n >= 30; scored only if >= 20
calibration batches after warm-up), per capture, streaming and causal, gaps g = dt_clipped to the previous frame of the same ID,
clipped to <= 3 T_i. Batch k = N consecutive gaps. Offset O_k = (1/N) sum_j c_j, c_j = sum_{i<=j}(g_i - mu_T) (mu_T = T_i, the
calibrated mean period ("drift" form) or the batch mean gap ("paper" form, accumulate |O|)). A_k = sum_m O_m (accumulated offset),
x_k = elapsed time. Skew S_k by scalar RLS without intercept, forgetting lambda = 0.99, A_k = S x_k:
K = P x/(lambda + x^2 P); S <- S + K (A_k - S x_k); P <- (P - K x P)/lambda. Identification error e_k = A_k - S_{k-1} x_k ("acc",
paper) or the increment form (A_k - A_{k-1}) - S_{k-1}(x_k - x_{k-1}) ("inc"). z_k = (e_k - median_i)/(1.4826 MAD_i) with median / MAD of
the clean calibration traffic; two-sided CUSUM on clip(z,+-10): C+ = max(0, C+ + z - kappa), C- = max(0, C- - z - kappa), kappa = 1,
score = max(C+, C-); first W = 10 batches of every ID in every capture are not scored (RLS warm-up). Frame score = CUSUM
state after the last closed batch of its ID (causal); window score = max over the window's frames. Fixed: lambda, kappa, clip, W.
Selected on VALIDATION (8 variants: form {drift, paper} x N {20, 50} x error {acc, inc}), by mean window recall at the 1% window
budget over the validation MASQUERADE captures (ROAD), over all attack types (Car-Hacking, D11 training vehicle); ties -> first.
Calibration: ECDF + tie-safe 1% budget at each unit on clean validation frames / windows (extra points: 0.1%; 1 FA/h from the ROAD test).
Statistics (median, MAD, T_i) from clean TRAIN frames (ROAD: lead of train captures; Car-Hacking: batches wholly inside fit-role clean blocks;
D11 regime A: train files; regime B: first 30 s). The filter runs continuously over each capture (as in deployment);
Car-Hacking block roles only select which batches/windows are used for stats / calibration / test.
ACCEPTANCE RULE S3. MET if all hold (ROAD test, window level, thresholds from validation, run once):
 1. Layer L2a implemented as a Layer (CanRule subclass), calibrated on attack-free data only, causal, dt_clipped only, tie-safe
    1% budget, unit tests pass with the whole suite, own files committed, caches <= 3 GB.
 2. Masquerade: L2a alone detects (>= 1 alarmed attack window) at least 3 of the 5 ROAD test masquerade captures
    (correlated_signal_3, max_speedometer_3, reverse_light_off_3, reverse_light_on_3, coolant), with false alarms on clean
    test windows <= 2% (limit 2x the budget because S2 showed test-ambient shift) for L2a alone. If detection is < 3/5 the plain
    statement is "skew does not catch ROAD masquerade".
 3. Combination L1 + L2a (harness, ablation vs L1 alone): keeps the 5 v2-detected captures (delay <= 2 s) and does not raise
    clean-window FA above 4.5% (L1 alone was 3.4%); the gain on masquerade is reported either way.
 4. Car-Hacking and D11 (both regimes, 4 sets x 4 subsets): reported (per-attack window recall, FA clean, delay, coverage of
    periodic IDs); no numeric gate.
If 2 or 3 fails the step is reported NOT MET with the reason; nothing re-tuned on test.

## 2026-10-21 S3 RUN 1 (design exactly as pre-registered above) - frozen as the verdict run
Run 1 executed end to end on ROAD (this also scored the test set; per RULES 5.2 this is the single test use of the
pre-registered design). Files: results/WP2/s3_run1_frozen/ (s3_road.json, harness/, windows, log).
Result run 1: validation selected drift_N20_acc but ALL 8 variants had validation masquerade recall 0.0. Test: L2a alone detects
0 of 5 masquerade captures; clean test windows FA 3.9% (limit 2%): acceptance item 2 NOT MET in run 1; L1+L2a FA 6.6% (L1 3.5%).
It does detect the non-masquerade attacks late (delay 6.5-7.5 s). Validation-only diagnosis (no test labels): (i) the accumulated
error e_acc is a random walk whose scale grows with capture length, so the pooled sigma is set by the long ambient captures and
the 60 s attack captures never exceed kappa (CUSUM identically 0 on 3 val masquerade captures); (ii) in the long clean val capture a few IDs
(0xA7 ...) drift and reach CUSUM 400-700, so the window max over ~100 IDs is dominated by them and the 1% window threshold is above any
masquerade score. The raw signal exists: in val masquerade captures the identification error of the injected ID is shifted by 5-20 x its
pre-attack std (e.g. max_speedometer_2 masquerade: +0.025 s vs pre-attack sd 0.0014 s; reverse_light_on_2: -0.020 s).
## 2026-10-21 S3 RUN 2 (revised design, validation-driven; NOT independent: test labels of ROAD were seen in run 1)
Changes decided from validation / training diagnostics only: (1) per-ID scale c_i = 0.99-quantile of the CUSUM state of ID i over the
clean calibration batches (floor 2), score = CUSUM / c_i, so no single unstable ID sets the window maximum; (2) otherwise identical
(8 variants, same selection rule, same budget). Run 1 remains the verdict for acceptance items 2 and 3; run 2 is reported as
"revised design". Car-Hacking and D11 are run once, with the revised design.

## 2026-10-21 S3 RUN 2a / 2b log (all after the test set was seen in run 1)
- Run 2a (per-ID CUSUM scale c_i only) was started by me before looking at its validation numbers; it wrote s3_road.json with
  test results, which I did NOT inspect (overwritten by run 2b). Its validation selection again gave recall 0.0 for all 8 variants.
- Validation / train diagnosis (scripts in the scratchpad, no test labels): the clean TRAIN CUSUM state is huge (per-ID 0.99-quantile
  median 320-780): the pooled-normalised identification error is autocorrelated and drifts (long ambient captures, logger bursts), so a CUSUM
  with a fixed pooled sigma integrates the drift. Per-ID scaling therefore makes all scores tiny.
- Run 2b design (final revised design, decided on validation/train only): add a LOCAL baseline option (norm = 1): the mean and variance of
  the identification error of each ID come from the same capture (Welford over 10 batches after warm-up, then EWMA beta = 0.98 with the error
  winsorised at 4 sd; sd floor 0.5 x the burn-in sd), so slow drifts are absorbed and a CUSUM fires on abrupt changes (the masquerade onset). 16 variants
  now (8 pooled + 8 local), same selection rule (validation masquerade recall at 1% window budget), per-ID scale kept.
- Diagnostic tools/WP2_S3_masq_shift.py (results/WP2/s3_road_masq_shift.json): the masquerade streams differ from the legitimate
  stream in mean period by -2131 .. +210 ppm (median |.| ~ 60 ppm, coolant -2131) while the per-gap jitter of the logged timestamps is
  12-28% of the period (115,000-277,000 ppm) and 10 s segment means of clean ambient traffic spread by 1.6-2.8%: the clock-rate signal is far below what the
  receive timestamps of ROAD can resolve (resolution of a skew estimate over a 20 s attack ~ 100 ppm at best, with iid jitter).
  Expectation written before run 2b: skew will not catch ROAD masquerade at a 1% budget, except possibly coolant (2131 ppm, 43 frames).

## 2026-10-21 S3 results (report reports/WP2_S3.md, tables results/WP2/s3_tables.md)
Verdict NOT MET. Run 1 (frozen): 0/5 ROAD test masquerade, FA 3.9%. Run 2b (revised): AUC 0.458, FA 35%, 1/5 partly. Car-Hacking: L2a useless (recall <= 3%).
D11: weaker than L1, FA higher in regime B. ID-known upper bound AUC about 1.0 on 8/12 masquerade captures (onset transient): a change signal exists, not deployable.
Full suite 190 passed. No new cache.

## 2026-10-21 S4 start: L2b signal physics on decoded ROAD signals. Design + acceptance rule, written BEFORE any L2b score
Findings before design (descriptive, train ambient only; tools/WP2_S4_*.py, results/WP2/s4_signal_stats.json, s4_decode_check.json):
- anonymized.dbc: 105 IDs, 664 signals, ALL named Unknown_k (no physical names). Own decoder (can/signals.py, Motorola/Intel, signed) reproduces signal_extractions
  CSV exactly (3 captures, 7.4 M values, 0 mismatches), so L2b runs causally on raw frames of ANY capture (also non-masquerade ones, which have no CSV).
- Names are given by meaning from TRAIN attack metadata + train correlations: 0xd0 byte 5 (sig 5, 14 bit) = speedometer; 0xd0 sig 2 = reverse light bit (bit 0x08 of byte 2);
  0x6e0 sig 0..3 = four wheel speeds; 0x4e7 sig 1 (byte 5) = coolant temperature byte; 0x498.3, 0x20e.1 also correlate 1.0 with speed; 0x274.14, 0x295.0, 0xc0.0
  predict the reverse bit (conditional entropy < 0.002 bit) = gear / direction state candidates (learned, not asserted). No RPM/brake signal is named by the data: relations
  with RPM x gear ratio and brake vs deceleration are learned only if they emerge from the generic search (conditional linear relations NOT implemented: reported as not done).
- ambient_dyno_exercise_all_bits is clean vehicle data that exercises the full signal envelope: used in the FIT of every model, NOT as a held-out calibration fold (decision before results).
Model (fold = fit on a set of clean ambient captures; everything below from sufficient statistics, summable over captures):
 value check: cont (pooled > 32 distinct values): excess of v outside [min, max] / span; disc (<= 32): value count < ms (ms in {1, 10} frames) -> 1.
 rate check: cont signals, not noise-like (change fraction > 0.9 and >= half of 2^len values): |v - v_prev(same ID)| / max training step - 1 (>= 0); disc: transition (a->b) count < ms.
 linear relation: all pairs of cont signals (same or different ID) with |corr| >= rho on a 0.05 s sample-and-hold grid of the fold's captures (rho in {0.98, 0.995}), OLS y = a x + b,
   residual |r| / max training residual - 1 (>= 0), held value of the other signal at frame time (causal).
 joint support (state consistency): disc x disc pairs among slowly varying signals (<= 8 values, change fraction < 0.05) with normalised mutual information >= 0.7 in the fold;
   combination count (on the grid) < 10*ms/ms... fixed: count < ms_joint (10 grid samples = 0.5 s when ms = 10, 1 when ms = 1) -> 1.
 Component types: value, rate, linear, joint. Frame raw per type; per-type ECDF (fit on the LOCO clean frames) -> max over types = frame score; window score = max over frames (1 s windows, running-max t).
LOCO: folds = clean ambient captures of train+val except exercise_all_bits (7: basic_long, extended_long, radio_infotainment, idle_radio, highway_long, basic_short, winter); each held-out
 capture is scored by a model fit on the other 7 ambient + all_bits; LOCO scores are pooled; 1% tie-safe thresholds at frame and window level from the pool. Final model fit on all 8 ambient.
Hyper-parameters (4 variants: rho x ms) chosen on train+val masquerade captures (attack 1 and 2; model fit on ambient only, threshold from the pool): mean window recall over those 10 captures at 1%;
 ties -> first. Test sees: the chosen variant, once.
Test (ROAD test split, window level, 1 s): ambient_dyno_drive_benign_anomaly, extended_short, reverse, highway diagnostics (clean windows) and the attack captures of the test split.
ACCEPTANCE RULE S4. MET if all hold on the single test run:
 1 Layer implemented (Layer API, causal, decoded from raw frames), clean-only fit, LOCO calibration, tie-safe 1% budget at window and frame level, unit tests pass with the suite,
   own files committed, caches <= 3 GB, temporary files deleted.
 2 L2b alone detects (>= 1 alarmed attack window) at least 3 of the 5 ROAD test masquerade captures (correlated_signal_3, max_speedometer_3, reverse_light_off_3,
   reverse_light_on_3, coolant) with clean test window FA <= 2% for L2b alone. Fewer than 3 -> plain statement "signal physics does not catch ROAD masquerade".
 3 ambient_dyno_reverse (legitimate reverse driving) produces no L2b alert in more than 2% of its windows.
 4 L1 + L2b (OR of alarms; L1 = five S2 run-1 rules recomputed from stored windows) keeps the 5 v2-detected captures (delay <= 2 s) and clean-window FA <= 5.5% (L1 alone 3.4% + L2b 2%).
 5 Reported without gate: per-capture detection / delay / clean FA, ablation on top of L1, frame-level recall at 1% budget, which check fires per capture, physical explanation. Car-Hacking and D11:
   no decoded signals / no DBC -> "not evaluable" (stated, not faked).
If 2, 3 or 4 fails the step is NOT MET; revisions after the test run are evaluated on validation only and labelled second exposure.

## 2026-10-21 S4 design change 1 (before any test score; decided from LOCO + train/val attack diagnostics only)
First LOCO pass (per-type ECDF calibration, binary-ish scores): every held-out clean capture fired value / rate / joint checks in 100% of its windows
(results of tools/WP2_S4_trace.py on basic_short: signals 0x55c.3-5, 0x655.8, 0x3a2.1, 0x277.1, 0x207.5 hold session-specific states that are absent from the other
captures; 145 joint pairs built on them fire in every frame). Validation masquerade recall was 0.5 for all four variants (wheel-speed and speedometer captures 1.0,
both reverse-light captures 0.0) because the 1% window threshold was set by these persistent violations (threshold 0.98 on ECDF scores; joint violations of the reverse-light bit
had ECDF value below it). Cause: a check that fires on every held-out capture is not a physical relation, it is a session constant.
Change: each check gets a surprise weight w_c = -log2((violations + 1) / (frames + 2)) from the pooled LOCO held-out violation counts of the same variant;
frame score = max over violated checks of w_c * (1 + log1p(excess)/10); window = max; per-type ECDF removed; thresholds = tie-safe 1% on the LOCO pooled frames / windows.
Checks absent from the folds (new pairs in the final model) get w = 6.6 bits. The weights come from the same LOCO pool as the threshold (plug-in, as every earlier calibration);
reported as such. Old per-type ECDF cache (loco_b, attack) not used any more. Acceptance rule unchanged.

## 2026-10-21 S4 design change 2 (before any test score; decided from train/val attack-capture leads only)
Weighted LOCO scoring still alarmed on every clean window of the train/val ATTACK captures (final model fit on the 8 ambient captures): each ATTACK capture is another session with
states that the 7 ambient LOCO folds never showed (event IDs 0x32d, 0x2b4, 0x1d6 ... and a wheel-speed/speed gain shift; checks that never fire in LOCO fire persistently there; diag:
tools/WP2_S4_trace_attack.py on reverse_light_off_attack_2_masquerade and correlated_signal_attack_2_masquerade, train/val only). LOCO over ambient captures therefore under-estimates session shift.
Change: IN-SITU BASELINE (like D11 regime B): a check that violates at least once during the first 3 s of a capture is muted for the rest of that capture; frames of the first 3 s are not
scored and windows 0..3 are excluded from pools and from FA / recall. Causal (the decision uses only frames <= 3 s). Applied identically in LOCO (held-out captures), attack and test captures.
Weights recomputed from the muted LOCO traces. Consequence: attacks in the first 3 s are invisible (ROAD attack onsets are >= 4.3 s; I knew the onset list from the public
metadata when choosing 3 s; the value is not tuned). Acceptance rule unchanged. Variants and selection unchanged.

## 2026-10-22 S4 results (report reports/WP2_S4.md; verdict results/WP2/s4_test.json, tables s4_tables.md)
Verdict NOT MET. Variant 0 (rho 0.98, ms 1) chosen on validation (masq recall 0.75). TEST (single run): masquerade detected 4/5 (correlated_3 0.68 s, max_speedometer_3 0.48 s,
reverse_light_on_3 0.93 s, coolant 0.02 s; reverse_light_off_3 missed); checks: linear for wheel speeds / speedometer / coolant, joint (reverse bit vs gear) for reverse_on.
Clean-window FA 38.1% (benign_anomaly 64.2%, extended_short 71.1%, reverse 0, diagnostics 0); L1 5.2% (recomputed OR), L1+L2b 40.4%. Cause: single-value / rate checks on discrete signals flag
rare legitimate states (0x5e1.2, 0x107.3, 0x153.6, 0xc0.2) plus 1500 generic joint pairs. Second exposure R1 (joint only with reverse bit): validation identical, test FA 32.3%, same detection.
Ablation (validation): no joint -> reverse_on lost; linear only 0.5; joint only 0.25. Car-Hacking / D11 not evaluable (no decoded signals). 227 tests pass. Cache 673 MB.
Pitfalls: ECDF-per-type calibration with persistent session states -> every window alarms; LOCO over ambient does not represent a new session (attack captures); the first LOCO process of the old design could not be killed (permission denied).
