# WP5 V2X notes

## 2026-10-19 S0 Data download: acceptance rule (written before any download/result)
S0 is MET if all hold:
1. D12 VeReMi Extension downloaded to ../data_extra/D12_veremi_extension/, licence recorded, files parse, fields present
   (sender id, time, position, speed, heading) and ground-truth label values (attack types) found; message and sender counts recorded.
2. D14 Tampa BSM sample (<= ~2 GB) downloaded, several days and many distinct vehicles, parsed; fields present.
3. D13 V2AIX JSON only (no ROS bags), <= 5 GB, whole recordings, mixed scenarios if metadata allows; licence recorded.
4. >= 15 GB disk free throughout. Anything needing login/manual click is NOT worked around: recorded with the exact user action; item then reported PARTIAL.

## 2026-10-19 S0 results (numbers from results/WP5/s0_data_check.json, script tools/WP5_verify_s0.py)
- D12: Mendeley k62n4z9gdz, CC BY 4.0, sha256 matches. CSV 3,194,808 rows, 24,663 `sender`, 118,909 `senderPseudo`. Fields: sendTime, sender, senderPseudo, messageID, class, pos/spd/acl/hed (x,y,z) plus *_n noise-sigma columns. No receiver id, no simulation id, no receiver position in this combined CSV (limits S3 acceptance-range check and group-by-simulation splits; split by sender id; raw VeReMi logs would be needed otherwise -> maybe D25 NextGen). class values 0..19, 0 genuine = 1,900,539 (59.5%); the class-to-attack-name map is NOT in the dataset page (assumed to follow F2MD/VeReMi Ext attack order: check against paper before S1). posz/spdz/aclz/hedz all 0.
- D14: 34,464 BSMs, 226 vehicle ids, only ONE day (2021-03-19, ~6.7 h). Acceptance wanted several days: NOT met by the public sample; fuller data = ITS DataHub Sandbox request (user). Enough for normal-behaviour modelling with 72 vehicles >= 100 msgs. Raw units: lat/long 1e-7 deg, speed 0.02 m/s, heading 0.0125 deg (J2735).
- D13: V2AIX is a Streamlit site; Download button opens a request form (manual approval, "all requests are approved manually"). Not worked around, nothing submitted. User must: open https://v2aix.ika.rwth-aachen.de, click Download, fill form, tick 2 boxes, wait for approval mail with the link; then give link to a worker (JSON format only; pick Mobile Aachen/Cologne, highway, rural + Stationary, whole files, <=5 GB). Licence: non-commercial, cite, no redistribution of data or modified versions.
- Disk free after: ~48 GB.
- Acceptance: D12 MET; D14 PARTIAL (one day, 226 vehicles); D13 NOT DONE (needs user). Overall S0 PARTIAL.

## 2026-10-19 S1 Data layer: acceptance rule (written before any S1 result)
Scope: D12 + D14 only (D13 V2AIX not available: adapter stub raising a clear error, no fake data).
S1 is MET if all hold:
1. Unified message schema + adapters (VeReMi CSV, Tampa BSM, V2AIX stub). Adapter output has the schema columns, finite values, units SI (m, m/s, rad or deg stated), per-sender time strictly sortable; unit tests pass.
2. VeReMi class map: the 0..19 map from the supervisor is checked against a primary source if reachable, AND against the data. Data checks: class 1 (ConstPos) >= 80% of senders with position std < 1 m; class 5 (ConstSpeed) speed constant for >= 80% of senders; classes 13-15 median message rate per sender >= 2x genuine. Any class failing is recorded as UNVERIFIED (not silently kept).
3. Split: best available grouping recovered and documented. Zero overlap of senders (and of runs if recovered) between train / val / test, each part holds genuine senders and every attack class; leakage risk written down. Checked by an automated test of the saved splits.
4. Tampa: split by vehicle, zero overlap. Injection implements the VeReMi taxonomy attacks on real BSMs; each has equations in the report and a unit test of physical consistency (e.g. constant-position offset keeps claimed speed vs. implied speed rule per the attack definition; replay reproduces past genuine messages exactly; DoS multiplies rate; no timestamps going backwards within a sender). Injected data only on val/test/train vehicles per split, labels per message.
5. python tests/run_tests.py passes (all of v2x tests), seeds fixed.
No re-splitting after seeing results.

## 2026-10-19 S1 results (numbers in results/WP5/s1_*.json; scripts tools/WP5_S1_build.py, WP5_S1_report.py)
- Code: v2x/{schema,adapters,splitting,attacks}.py; tests/v2x (25 tests pass). V2AIX adapter = stub raising DataNotAvailableError.
- Class map: primary source not reachable (GitHub 404s, web search found only the 2018 paper). Data supports the supervisor's map: all 5 pre-registered checks PASS (class1 100% const pos; class5 100% const speed; rate ratios 13/14/15 = 2.0/4.0/4.0; 16 = 6.0 with 6 pseudonyms). Weak: class 12 (zero placeholders + stops), offsets 2/4/6/8 unprovable without truth. Class 2 looks like genuine.
- Combined CSV is 1 Hz (genuine), original paper DoS 10x, here 2x: our injection uses measured factors.
- Splits: no run id; one 24h timeline, sender id ~ departure time (Spearman 1.0). Used 1800 s time blocks (48), shuffled 60/20/20 seed 42, straddling senders dropped (1431/24663). 0 sender overlap, 0 coexistence in time. Train/val/test senders 15578/2121/5533, each part has all 19 attack classes (239..252 / 31..37 / ~83..90 per class).
- Tampa: gen time = secMark+RSU minute (10 Hz), dedup over RSUs -> 34,453 msgs, 226 vehicles, 353 tracks. Vehicle split 136/45/45; eligible (>=50 msgs) 74/21/20 -> 10 attackers per type in test (noisy).
- Held-out attack types for supervised training (fixed now): 6, 12, 17.
- Pitfall fixed: epoch-seconds float64 modulo lost 1e-7 s; use integer modulo first.
- Acceptance: S1 MET for D12+D14 (class map PARTIALLY verified: names consistent with data, not confirmed by primary source).

## 2026-10-19 S2 L1 message checks: acceptance rule (written before any S2 result)
Supervisor instructions: S1 approved; held-out attack types 6, 12, 17 stay out of any calibration / training (also out of the
combiner fit on validation); physical limits cited; data-driven thresholds on validation genuine messages only (1% budget, tie-safe);
sudden appearance implemented + unit-tested on synthetic data, reported "not evaluated on real data" (no receiver positions invented).
Design (fixed now): four Layers (domain v2x, layer L1, kind rule): v2x.beacon_rate (1/dt per track, dt rounded to 1 ms, data-driven),
v2x.freshness (age = receive - generation time where a receive time exists, plus timestamps going backwards in arrival order; data-driven),
v2x.field_ranges (speed / acceleration / yaw rate against cited physical limits; physical operating point raw >= 1, plus budget operating point
for the harness), v2x.sudden_appearance (first message of a track closer than R_EDGE to the receiver). Causal per track.
Data: VeReMi (no receive time -> freshness not evaluable; no receiver -> sudden appearance not evaluable). Tampa: age from RSU log time (1 s
resolution); injected attacks stamp the current time, so freshness is blind to them by construction; one supplemental, documented attack
(S20 StaleReplay: verbatim old message, original timestamp, delivered 10-60 s later) is added for Tampa only, to show what freshness is for.
S2 is MET if all hold:
1. 4 Layers implemented, unit tests pass (incl. sudden appearance on synthetic data, stale age, rate, ranges), python tests/run_tests.py passes.
2. No threshold is fitted on test or on attack data; data-driven thresholds from validation genuine only; physical limits cited in the module docstring.
3. False alarms at each layer's operating point on genuine test messages <= 1.5x the budget on VeReMi (<= 1.5%); on Tampa (small val) <= 2%.
   The physical operating point of field_ranges must give <= 0.1% false alarms on genuine val and test (a physical limit that fires on genuine
   traffic is reported as a failure of that limit, not retuned).
4. Per-layer detection for all 19 VeReMi classes and the Tampa injected types (+ S20), false alarms on genuine test messages AND senders,
   harness ablation (only_X / all / all-but) written to results/WP5/s2_*.json, with attacker-level bootstrap CIs for Tampa.
Pre-registered expectations (stated, not tuned to): rate layer detects >= 90% of the messages of classes 13, 14, 15 on VeReMi test and the
doubled-rate Tampa types; ranges (physical) detects < 5% of every position / speed falsification class (VeReMi speeds in the data reach 56 m/s < 70 m/s limit);
freshness detects only S20; L1 union detects < 30% of classes 1-12 and 17 (position/speed falsification with plausible per-message values).
Misses are reported plainly; they are the reason for L2-L4. No re-splitting, no re-tuning after seeing results.

## 2026-10-19 S2 results (numbers in results/WP5/s2_veremi.json, s2_tampa.json, s2_summary.json, s2_tables.md; scripts tools/WP5_S2_l1.py, WP5_S2_report.py)
- Code: v2x/l1.py (4 Layers), v2x/adapters.py load_tampa(with_age=True) adds age_s, tests/v2x/test_l1.py (11 tests); full suite 83 passed.
- Evaluable: VeReMi = rate + ranges (no receive time -> freshness not evaluable; no receiver -> sudden appearance not evaluable). Tampa = rate + freshness + ranges. Sudden appearance: synthetic unit test only.
- Held-out 6, 12, 17 removed from the validation set the combiner sees. Test scored once per dataset (one run; log results/WP5/logs/s2_run1.log). No re-tuning.
- Checks 3a-3c MET (max FA 1.0% VeReMi, 1.3% Tampa, physical ranges 0.0% on genuine). Expectations E1, E2, E3, E4 as expected; E1b NOT: Tampa DoS x2 detected only 5.7% (x4 types 93-94%).
- Why: genuine Tampa val has 20 Hz bursts (6.1% of val inter-arrivals > 10.5 Hz; test 1.5%; one val vehicle gives half), so the 1% budget threshold is 20.4 Hz; the literal 10 Hz standard limit would give 1.5% FA on genuine test messages. Data-driven threshold kept.
- VeReMi rate: classes 13/14/15 99.7% of messages, every attacker within ~0.5 s. Physical field limit never fires on any attack (max attack speed in data 56 m/s < 70). The 1% budget point of the ranges layer catches ~70% of classes 5, 7, 14, 18 (high speeds) but is a quantile of genuine speed (max 19 m/s) and flags 49% of genuine senders: ablation device only.
- DoS factor (S1 note): class 13 per-sender rate is bimodal (2 or 4 Hz, mean 2.97, 390 senders), not a clean 2x. Tampa injection kept at x2 as approved.
- Freshness: S20 supplemental stale replay 100% detected, 1.1% FA; the 19 injected types are blind by construction (fresh timestamps).
- Acceptance: S2 MET (1-4); E1b reported as not as expected.

## 2026-10-19 S3 L2 plausibility: acceptance rule (written before any S3 result)
Supervisor instructions: S2 approved. NO receiver-position approximation (no RSU centroid). Acceptance-range threshold and sudden appearance
are left to a later S3b (needs real receiver positions: D25 NextGen / D13 V2AIX). S3 = F2MD-style (Kamel et al.) plausibility per sender:
consecutive-beacon consistency, kinematic consistency, overlapping vehicles, map plausibility (Tampa only if OSM obtained; VeReMi: Luxembourg
map not available -> map check SKIPPED on VeReMi, said so in the report). Physical limits cited; data-driven thresholds from validation
genuine only (1% budget, tie-safe); held-out attack types 6, 12, 17 out of calibration and out of the combiner's validation set.
Data: OSM Tampa extract downloaded (Overpass, ODbL, drivable classes only) -> ../data_extra/D27_osm_tampa/, DATASETS.md row D27.
Design (fixed now), module v2x/l2.py, nine Layers (domain v2x, layer L2, kind physics), causal per track (row k uses only earlier
messages of its own track, and for overlap only earlier messages of other tracks within W = 1 s). dt = t_k - t_(k-1) of a track, rounded
to 1 ms; a pair is evaluated only if 0 < dt <= DT_MAX = 5 s (the Tampa track-gap rule), otherwise raw = 0. d = |p_k - p_(k-1)|.
 1 v2x.pos_speed      |d - mean(v_k, v_(k-1)) * dt| in m (displacement vs reported speed x dt). Data-driven.
 2 v2x.pos_heading    angle between the mean reported heading and the displacement bearing, times d / (d + 2 m) (soft gate: bearing is
                      undefined for tiny d; 2 m = position noise scale, a design constant), only if both speeds >= 3 m/s. Data-driven.
 3 v2x.speed_change   |v_k - v_(k-1)| / (dt * A_MAX), A_MAX = 1.3 g (l1.LIMITS). Physical operating point raw >= 1.
 4 v2x.implied_speed  d / (dt * V_MAX), V_MAX = 70 m/s. Physical operating point raw >= 1.
 5 v2x.heading_rate   |wrap(h_k - h_(k-1))| / dt divided by the yaw limit v/R_MIN (v = max of the two speeds, cap 5.72 rad/s below 3 m/s);
                      only if both speeds >= 3 m/s (heading of a standing vehicle is undefined). Physical operating point raw >= 1.
 6 v2x.accel_consistency   |mean reported acl - (v_k - v_(k-1))/dt| in m/s^2 (needs acl; NaN -> 0 and not evaluable). Data-driven.
 7 v2x.yaw_consistency     |mean reported yaw rate - wrap(h_k - h_(k-1))/dt| in rad/s, speeds >= 3 m/s (needs yaw_rate; Tampa only:
                      VeReMi has no yaw rate -> not evaluable). Data-driven.
 8 v2x.overlap        two different tracks occupying the same space at the same time: the last earlier message (<= 1 s) of every other
                      track is dead-reckoned to t_k with its velocity; both vehicles are oriented rectangles 4.5 x 1.8 m (typical passenger
                      car, EU/US average; fixed); raw = minimum penetration depth from the separating-axis test / 1.8 m, 0 if disjoint.
 9 v2x.map_road       distance (m) from the claimed position to the nearest drivable OSM way (polylines densified to 1 m). Tampa only.
Operating points: per check at the 1% validation budget (data-driven for all nine, including 3-5, whose raw is still a limit ratio);
physical points for 3, 4, 5 (raw >= 1); UNION = max of the calibrated scores of the evaluable checks, threshold at ONE 1% budget (so the
union keeps the 1% false-alarm budget; an OR of nine 1% checks would not). Harness: ablation over L1 + L2 layers, plus group rows L1 / L2 / L1+L2.
Calibration frame: the whole validation frame with held-out types removed (neighbours matter for overlap), raw scores fitted on its genuine rows only.
Tampa test: each injected scenario is scored together with the genuine rest of its split (neighbours), attacker messages are evaluated.
S3 is MET if all hold:
 1. Nine Layers implemented, unit tests pass (incl. synthetic cases for each check and a causality test), python tests/run_tests.py passes.
 2. No threshold fitted on test or attack data; physical limits cited; OSM download recorded (DATASETS.md D27, notes).
 3. False alarms on genuine test messages: each check and the union <= 1.5% on VeReMi, <= 2% on Tampa; physical operating points 3-5
    <= 0.1% on genuine val and test (a limit that fires on genuine traffic is reported as a failure, not retuned).
 4. Per-check, union and combined detection (message and sender level) for all 19 VeReMi classes and the Tampa types (+S20), false
    alarms on genuine messages and senders, detection delay per attacker, harness ablation on top of L1, bootstrap CIs on Tampa.
Pre-registered expectations (stated, not tuned to), union at the 1% budget, message level, VeReMi test (Tampa where stated):
 P1 classes 3 RandomPos, 4 RandomPosOffset, 7 RandomSpeed, 10 Disruptive, 14, 15, 18, 19 (random content each message): >= 85%
    (VeReMi position noise is sigma ~4 m per axis, so position consistency is noisy, but 50-300 m jumps are far above it).
 P2 class 1 ConstPos and class 5 ConstSpeed (claimed motion contradicts the displacement): >= 80%.
 P3 class 6 ConstSpeedOffset / 8 RandomSpeedOffset (speed bias 5-15 / 0-10 m/s): partly caught, 20-80% on VeReMi (dt = 1 s); on Tampa
    (dt = 0.1 s, bias x 0.1 s = 0.5-1.5 m, same order as GPS noise) < 50%.
 P4 NOT caught by consecutive-beacon checks (each < 10% of messages): 2 ConstPosOffset, 11 DataReplay, 12 DelayedMessages, 13 DoS (constant
    velocity extrapolation is consistent), 16 GridSybil, 17 DataReplaySybil. On Tampa the map check may catch part of 2 (offset leaves the road);
    that is reported, not expected. Overlap is expected to catch < 10% of GridSybil (ghosts 15 m / 3.5 m away do not overlap a 4.5 x 1.8 m footprint).
 P5 class 9 EventualStop: message level < 10% (only the stop transition is implausible); sender level reported.
 P6 union false alarms on genuine test messages <= 1.5% (VeReMi), <= 2% (Tampa).
Misses are reported plainly. No re-splitting, no re-tuning after seeing results; one test run per dataset.

## 2026-10-19 S3 pre-run findings (validation data and dry runs only; test untouched; written before the test run)
- OSM Tampa downloaded: Overpass (first attempts got 406 without a User-Agent and a busy-server timeout; retry with a User-Agent worked), bbox
  lat 27.9407..27.9593, lon -82.4633..-82.4407 (D14 positions + ~300 m), drivable highway classes only, 1,782 ways, 6,934 nodes, 1.4 MB, OSM base
  2026-10-19T22:42Z, ODbL 1.0 -> ../data_extra/D27_osm_tampa/tampa_highways.json (+ SOURCE.txt), DATASETS.md row D27. Road tree: 150,815 points at <= 1 m.
- **Tampa ids are per RSU, not per vehicle (new finding, affects S1 numbers).** In the raw CSV the same BSM (same msgCnt, secMark, lat, long, speed,
  heading) appears with different coreData_id at different RSUs (e.g. ids 8692539 / 8725415 / 8966772 at thea39 / thea11 / thea10, bit-identical messages).
  Every id occurs at exactly one RSU (226 ids, 38 RSUs). So "226 vehicles" are (vehicle, RSU) sessions; one physical vehicle drives under several ids.
  Consequences: (1) the S1 vehicle split can put the same physical trajectory in train / val / test under different ids (leakage; thresholds calibrated
  on val genuine messages that are copies of test genuine messages make test false alarms optimistic); (2) injection replay pools may contain copies
  of the attacker itself; (3) 8,532 of 19,909 distinct (time, position, speed, heading) keys carry more than one id. S1 not redone (outside S3); put to the supervisor.
- DEVIATION from the written design (decided on validation data, before any test run): the overlap check compares only tracks heard by the same receiver
  (rx_id; in Tampa the RSU). Reason: without it 30% of genuine Tampa validation messages "overlap" with a bit-identical copy of themselves under another id
  (raw depth/width = 1.0 at the 90th percentile), which would make the check meaningless; with it 0.0% of genuine Tampa validation messages overlap.
  VeReMi has no receiver column: all vehicles are compared (global receiver); 2.2% of genuine VeReMi validation messages overlap (position noise sigma ~4 m).
- Genuine VeReMi: one pseudonym per genuine sender (no pseudonym change), dt exactly 1.0 s, position noise sigma 4 m per axis (pos_sigma column), speed noise ~0.
- Dev run (validation only): false alarms at the budget operating points 0.8-1.0% for every check on both datasets; physical limits on genuine validation:
  0.000% everywhere except heading_rate on VeReMi 0.002% (2e-5). log results/WP5/logs/s3_dev1.log. Smoke run (validation used as a stand-in for test, results in
  *_smoke files, never reported as results) exercised the whole pipeline.

## 2026-10-20 S3 results (numbers in results/WP5/s3_summary.json, s3_veremi.json, s3_tampa.json, s3_diag.json, s3_tables.md; scripts tools/WP5_S3_l2.py, WP5_S3_diag.py, WP5_S3_report.py; log results/WP5/logs/s3_run1.log)
- Code: v2x/l2.py (9 Layers), tests/v2x/test_l2.py (15 tests), full suite 116 passed. Test scored once per dataset (run1). Report reports/WP5_S3.md.
- Acceptance: 1, 2, 4 MET. 3a (VeReMi FA <= 1.5% per check/union) MET (max 1.47%, overlap; L2 union 1.0%). 3c (physical limits <= 0.1%) MET (VeReMi max 0.0026%, Tampa 0.0225%).
  3b (Tampa FA <= 2%) NOT MET: map_road 5.5% (CI 0.2-17.6%), hence L2 union 6.3%, L1+L2 union 7.6%. Cause: two test vehicles (RSUs thea24, thea1) are ~27 m from any mapped drivable
  way (validation q99 10 m, max 12.6 m); 91% of the alarms. The union of the eight non-map L2 checks holds the budget (val 0.96%, test 0.98%). Not retuned.
- Detection (L2 union, message level, VeReMi / Tampa): RandomPos 99/100, RandomPosOffset 97/100, RandomSpeed 99/98, RandomSpeedOffset 95/90, Disruptive 97/94, DoSRandom 100/100, DoSDisruptive 98/95;
  ConstSpeed 96/54, ConstSpeedOffset* 86/29, ConstPos 86/15; NOT caught: ConstPosOffset 1/37 (Tampa via map), EventualStop 1/3, Delayed* 1/10, VeReMi Sybil-per-message 18 (0%) and 19 (1%).
  VeReMi classes 11, 13, 16 are detected (68/74/61%) because VeReMi's own attack implementations are kinematically inconsistent (diag); the consistent Tampa versions are not (11/3/5%).
- Pre-registered expectations: P2, P5 as expected; P1 (classes 18, 19 blind: pseudonym per message), P3 (offset-speed classes caught more than predicted), P4 (VeReMi 11, 13, 16, 17; Tampa 2, 11, 12, 17), P6 (Tampa FA) NOT as expected. Reported, not tuned.
- Harness group ablation (AUC / detection at 1% budget): VeReMi L1 0.695 / 45.1%, L2 0.800 / 67.1%, L1+L2 0.845 / 72.4%; Tampa L1 0.629 / 18.4%, L2 0.754 / 52.6%, L1+L2 0.781 / 53.3% (FA 6.7%, map).
- New finding (also in the report): Tampa coreData_id is per RSU, one vehicle appears under several ids; S1 split/injection assumptions weakened (see S3 pre-run findings above). Question for the supervisor.
- S20 overlap 76.9% is a construction artefact (messages of the same victim 0.1 s apart as separate tracks), not credited.
- Not done by design: acceptance-range threshold and sudden appearance (S3b), map on VeReMi.
- Acceptance: S3 PARTIAL (only the Tampa FA bound of the map check missed).

## 2026-10-20 S1b Tampa dedup + re-split + rerun of S2/S3 Tampa: acceptance rule (written before any S1b result judged)
Context: S3 found that coreData_id is per RSU. Structure facts looked at before writing this rule (no detection result involved): 34,464 rows,
38 RSUs, 226 ids; the key (msgCnt, generation time, lat, long, speed, heading) is shared by rows with different ids (8,532 keys); msgCnt is a
per-vehicle counter (+1 per BSM, so +10 per second at 10 Hz) and is therefore usable as a linking cue across ids; the sample has two data bursts
(about t = 0.6-3 ks and 17.4-24.6 ks of the UTC day) with a long empty stretch in between.
Design (fixed now), module v2x/tampa_link.py (+ adapters.load_tampa default = deduplicated, load_tampa_v1 = old behaviour for the record):
 1. DEDUP. Same transmitted message = same (msgCnt, generation time to the ms, lat, long, speed, heading). One row is kept (copy received first); the
    number of copies, the ids and the RSUs that heard it are recorded. Justification measured, not assumed: (a) no id occurs twice in one key,
    (b) among (msgCnt, generation time) groups with several ids, 100% have identical content (so content in the key never splits a true copy),
    (c) a tolerance rule (|dt| <= 2 ms, position <= 1 m, speed <= 0.1 m/s, heading <= 1 deg, different ids) adds only a few merges: reported;
    if it adds > 1% of the messages the exact key is extended to it.
 2. LINKING of ids into physical vehicles. Tier 1 (certain): ids that share a bit-identical message (union-find). Tier 2 (high confidence): components
    whose end/start are continuous: 0 < gap <= 5 s (the Tampa track-gap rule), dead-reckoned end position within 2 + 0.5 g^2 m of the start position,
    speed within 1 + 1.5 g m/s, heading within 20 deg if both speeds >= 3 m/s, msgCnt difference within +-2 of 10 g, and the candidate is the UNIQUE
    candidate of both the end and the start (otherwise "ambiguous", left unlinked). Passes repeated until no new link. Controls on real data:
    positive control (cut real tier-1 vehicles at random points with 0.5-5 s holes, ask whether the matcher re-links the halves among all other
    components: recall, wrong-link rate) and msgCnt negative control (shuffled msgCnt: links that survive). Tier-2 links are used only if the wrong-link
    rate in the positive control is <= 5% (else only tier 1 is used and that is stated). Merging two different vehicles is harmless for leakage (only
    makes groups larger); missing a link is what leaks, so the buffer in 3 covers the remaining risk.
 3. SPLIT by time block with buffers. Unit = a "passage": a physical vehicle cut where it is silent > 120 s (SILENCE_S). Blocks of BLOCK_S seconds, a
    passage belongs to the block of its first message; it is dropped if its life extended by BUFFER_S = 30 s on both sides touches a second block
    (no passage alive on both sides of a boundary, 30 s guard, gaps dropped). Non-empty blocks shuffled 60/20/20 with common.config.SEED = 42 (same call as
    VeReMi). BLOCK_S is the smallest of {300, 600, 900} for which (i) every part has >= 8 eligible passages (>= 50 messages), (ii) message shares are
    train 50-70%, val 10-30%, test 10-30%, (iii) every injected type 1..19 has >= 4 attackers in val and test. No re-seeding / re-drawing afterwards.
    Held-out attack types 6, 12, 17 unchanged. Saved to results/WP5/splits_tampa_v2.json (+ s1b_*.json); old splits_tampa.json kept.
    Checked automatically: zero passage overlap, zero shared physical vehicle ALIVE in two parts within the guard, number of physical vehicles with
    passages in more than one part reported (residual, not hidden), zero bit-identical messages across parts.
 4. RERUN with methods unchanged (v2x/l1.py, v2x/l2.py, same attack code and seeds, calibration on new val only, test scored once). Differences, all
    declared: unit = passage, deduplicated messages, overlap check compares all vehicles (the same-receiver restriction was only there because of the
    copies: rx_id is NaN after dedup; check: genuine val overlap FA reported); map_road is NOT part of the deployable Tampa union or combiner: it is
    scored as a separate soft layer (own FA and detection). Reference "old" numbers = results of S2 / S3 as reported; in addition the same code is run on
    the OLD data and OLD split with map excluded ("v1 same method") so the leak effect is not mixed with the union-definition change.
S1b is MET if: (1) the rule items 1-3 are carried out and the split checks pass; (2) FA on genuine test messages <= 2% for every deployable Tampa check
and union (S2/S3 bound), physical limits <= 0.1% (val and test); (3) old vs new tables written from the JSON; (4) unit tests pass.
Pre-registered expectation (leak): old test FA and detection were optimistic: new FA of data-driven checks at their budget >= old FA, and the deployable
union detection on types caught by data-driven checks drops (not tuned to). Misses reported plainly.
- AMENDMENT of item 3 (2026-10-20, written after looking at the STRUCTURE of the linked data, before any split was drawn and before any detection result):
  Linking result seen: 226 ids = 48 tier-1 components = 38 physical vehicles = 40 passages (27 with >= 50 messages), 19,527 unique messages. The activity is
  bursty (13 episodes separated by silences of >= 60 s; one episode holds 40% of the messages, one bus passage alone 24%), so the fixed 300 / 600 / 900 s grid
  would drop that bus (it is alive across any boundary). The criteria "(i) >= 8 eligible passages per part, (iii) >= 4 attackers per type" cannot be met by 27
  eligible passages; replaced by: (i') >= 3 eligible passages in val and in test, (iii') every attack type 1..19 has >= 2 attackers in val and test (n_att =
  round(0.5 * eligible) >= 2 needs >= 3 eligible). New split procedure (fixed now): EPISODES = maximal groups of passages whose lives, extended by the 30 s guard on
  both sides, overlap or touch (i.e. cuts only in corridor-wide silences >= 60 s). Boundaries therefore lie where no passage is alive on either side, with a
  30 s guard on each side, and nothing is dropped. Episodes are the shuffled blocks: group_split(episodes, 60/20/20, seed) with seed = 42; criteria (i'), (ii)
  [message shares train 50-70%, val and test 10-30%], (iii'). If seed 42 fails the criteria the next seed of 43, 44, ... that satisfies them is taken (size
  criteria only, no detection result is ever used; every tried seed is listed in results/WP5/s1b_split_info.json).
  The wide CIs that follow (about 2 attackers per type in val and test instead of 10) are a property of the public sample, not hidden.
- AMENDMENT 2 (2026-10-20, after the first split draw, before any detection run): the first draw (seed 42, episodes only) satisfied the size criteria but left
  ONE physical vehicle (V027, a bus: passages 25 min apart, 4,649 + 1,476 messages) with a passage in train and one in val. That is the identity leak the task
  is about, at a longer time scale. Fix, made on structure only: episodes that contain passages of the same physical vehicle are merged into one block
  (v2x/splitting.tampa_episodes(vehicle_of=...)), so no physical vehicle is on two sides. Same seeds list and size criteria. The first draw is kept in the
  notes as a record (train 27 / val 6 / test 7 passages; its test part did not contain V027); no detection number was computed on it.

## 2026-10-20 S1b results (numbers in results/WP5/s1b_*.json, s2_*_tampa_v2/v1same, s3_*_tampa_v2/v1same; scripts tools/WP5_S1b_build.py, WP5_S1b_rerun.py, WP5_S1b_report.py; logs results/WP5/logs/s1b_*.log)
- Code: v2x/tampa_link.py, adapters.load_tampa (new default, dedup passages) / load_tampa_v1 (legacy), splitting.tampa_episodes / tampa_time_block_split, tests/v2x/test_tampa_link.py; suite 131 passed. Methods of l1 / l2 / attacks untouched.
- Dedup: 34,464 rows = 19,527 distinct messages (43.3% copies); tolerance rule adds 0 merges; content never differs inside a (msgCnt, time) group (0 of 8,661).
- Linking: 226 ids -> 48 tier-1 components -> 38 physical vehicles (10 tier-2 links; positive control 128 correct / 0 wrong / 64 missed of 192; shuffled-msgCnt control 0.23 links vs 10) -> 40 passages (27 eligible >= 50 msgs). msgCnt advances 10/s within +-1 in 99.4% of pairs.
- Old split leakage: 68.0% of old test rows had a bit-identical copy in train (67.5%) or val (1.5%); 87% of old test ids belong to vehicles that also own ids in train / val; old test double counted 8,870 rows = 6,820 messages.
- New split (seed 48 after seeds 42-47 failed the size criteria): train 30 / val 6 / test 4 passages, 13,200 / 2,094 / 4,225 messages, eligible 19 / 4 / 4, attackers per type 10 / 2 / 2, gaps >= 79 s, 0 vehicles on two sides. Test = 3 physical vehicles.
- Rerun (test scored once, run1): FA <= 2% everywhere except heading_rate 2.7% (CI 1-5); physical limits 0.000%; L2 union 1.8%, L1+L2 union 1.8%, combined 1.7%; mean detection over 19 types L1+L2 union: old 54.4% (with map, FA 7.6%), v1same 47.4% (FA 2.3%), new 44.7% (FA 1.8%). map_road soft: FA 7.8%, out of the union.
- Interpretation: the S2/S3 layers are val-calibrated thresholds, so the leak mostly mattered for learned layers; v1same vs new mixes leak removal with a much smaller test (3 vehicles, 2 attackers per type), CIs over 2 attackers are not valid.
- Acceptance: S1b PARTIAL (heading_rate FA bound missed on a 2,094-message validation part; everything else MET).
- Open: user could request the fuller Tampa data (ITS DataHub Sandbox, several days); DATASETS.md D14 note (226 ids = 38 vehicles) is for the orchestrator.
