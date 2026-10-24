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

## 2026-10-20 S0b more Tampa BSM data (worker sonnet)
Acceptance rule (written before the source probes were interpreted): MET if a public no-login source gives >= 7 different days of daytime Tampa BSMs, >= 300 physical vehicles (tampa_link dedupe+linking), <= 3 GB, licence allows research use, fields as S1 schema, >= 15 GB disk free. If every source needs login / registration / sandbox request: NOT MET, write exactly what the user must do, no workaround, stop.
Probes (all 2026-10-20, no login):
- Socrata nm7w-nvbm: $select=count(*) = 34,464 rows = exactly the file already held (D14); min/max metadata_recordGeneratedAt 2021-03-19T00:17:15 / 06:59:43. The Socrata dataset is a fixed sample (rowsUpdatedAt 1755807917 = 2025-08-21), so $where/$offset paging cannot return more.
- Socrata catalog search "Tampa": only BSM sample nm7w-nvbm, SPaT sample xn7c-yu2n, TIM sample in46-gmir, and 5 aggregated BSM maps (speed / acceleration, no per-message data); none is more BSM data. Dataset description: "The full set of raw BSM data from Tampa CV Pilot can be requested from the ITS DataHub Sandbox" (https://its.dot.gov/data/data-request).
- S3 bucket usdot-its-cvpilot-publicdata (and usdot-its-cvpilot-public-data, the name in older metadata): both listing requests (prefix TAMPA/, list-type=2, index.html) return AccessDenied (403); the other guessed names do not exist (404). The bucket is closed to anonymous listing; guessing object keys would be working around the access control, not done.
- catalog.data.gov: only points back to the Socrata sample.
Result: S0b NOT MET, nothing downloaded, D14 unchanged. User action needed (see reports/WP5_S0b.md).

## 2026-10-20 S4 L3 per-sender Kalman tracker: acceptance rule (written before any S4 detection result)
Supervisor: S3, S1b approved; S0b closed. VeReMi = primary benchmark; Tampa (splits_tampa_v2.json, 3 test vehicles) = illustration, no statistical claims.
Pre-run look (TRAIN split only, no test, no calibration): VeReMi genuine consecutive-beacon displacement matches speed x dt to a median 0.14 m although
the stated position noise is sigma ~4 m, so the position error is strongly time-correlated (not white). Class 9 EventualStop: position repeated EXACTLY and speed 0
after the stop. Class 12 (as in the CSV): long runs of exactly (0, 0, speed 0). Class 17: median track length 1 message (pseudonym changes about every message,
59 tracks per sender), class 18/19: 2 messages per track 50 s apart. Class 2: consistent track, only shifted. (Disclosure: this look included train rows of
held-out types 12 and 17; they were NOT used in any fit or calibration, but the idea of the "too consistent" low-side test was motivated by seeing the exact repeats.)
Design (module v2x/l3.py, fixed now). Per track (pseudonym), segment restarts when dt > 5 s or dt <= 0 (same gap rule as L2). State s = [x, y, vx, vy]; message
measurement z = [x, y, vx, vy] (position, velocity = speed x heading unit vector), H = I.
  predict: s- = F s, F = [[I, dt I],[0, I]];  P- = F P F^T + Q;  Q = sigma_a^2 * [[dt^3/3 I, dt^2/2 I],[dt^2/2 I, dt I]]  (white-noise acceleration, i.e. constant-velocity model)
  innovation nu = z - s-,  S = P- + R,  R = diag(sp^2, sp^2, sv^2, sv^2);  NIS = nu^T S^-1 nu  ~ chi2(4) if the model is right.  update: K = P- S^-1, s = s- + K nu, P = (I-K) P-.
  init at segment start: s = z, P = R (the first message of a segment is not scored, raw = 0). CTRA not implemented: no attack of the targeted classes is about turn dynamics;
  the velocity measurement corrects the heading each beacon. Revisit only if val consistency is poor.
Noise fit (genuine TRAIN senders only): maximum likelihood of the innovations, theta = (sp, sv, sigma_a), sum 0.5 (ln det S + NIS) over a fixed random subsample of train
genuine tracks (seed common.config.SEED), floors sp >= 0.05 m, sv >= 0.02 m/s. Separate fit for Tampa (train passages). Nothing from val, test or any attack is used.
Layers (domain v2x, layer L3, kind normal_model; all need no attack data):
  v2x.kf_nis        raw = NIS of the message (two-sided in spirit; this layer is the upper tail).
  v2x.kf_cusum_hi   raw = per-track CUSUM C_k = max(0, C_(k-1) + NIS_k - k_hi), k_hi = chi2(4).ppf(0.95) = 9.488 (fixed, not tuned): catches sustained inconsistency.
  v2x.kf_cusum_lo   raw = per-track CUSUM C_k = max(0, C_(k-1) + k_lo - NIS_k), k_lo = chi2(4).ppf(0.25) = 1.923 (fixed): catches "too consistent" tracks (position and velocity
                    repeated with no measurement noise: stuck / frozen / replayed-verbatim streams). Relies on genuine senders having fresh noise every beacon: true on VeReMi
                    (zero displacement in 0.45% of genuine pairs), to be checked on Tampa val; the val threshold takes whatever the genuine data gives.
  v2x.track_birth   optional: for the first message of a track, number of OTHER track births in the same 300 m claimed-position cell during the same or previous 5 s slot; 0 for
                    other messages. No receiver position needed. Calibrated like the others (1% of genuine MESSAGES, which is lenient because births are ~1% of messages: the
                    false-alarm rate per genuine BIRTH is reported next to it).
Operating points: each layer at the 1% budget on genuine VALIDATION messages (held-out types 6, 12, 17 removed from the validation frame, tie-safe via common.metrics);
L3 union = max of calibrated L3 scores at ONE 1% budget (kf_nis, cusum_hi, cusum_lo; birth separately and in the union only if it is reported as part of L3 - decision: reported
alone and as "L3 + birth" union). Harness ablation: groups L1, L2, L3, L1+L2, L1+L2+L3 (map_road not in any union), plus all-but-one. L1, L2 calibrated exactly as in S3.
Filter consistency on genuine VALIDATION (reported, no tuning): mean NIS vs 4, fraction above chi2(4) 95% (9.488) vs 5%, fraction below chi2 5% (0.711), for VeReMi and Tampa.
Test used once per dataset. S4 is MET if all hold:
 1. Filter, equations, 4 layers + tests implemented; noise parameters fitted on genuine TRAIN senders only (checked by a unit test that fit() takes only the rows it is given and by the
    log of the sender ids used); held-out types 6, 12, 17 absent from every calibration.
 2. Consistency on genuine val reported (VeReMi); stated plainly if NIS mean is outside [3.0, 5.0] or the fraction above 95% is outside [2%, 10%].
 3. False alarms on genuine TEST messages <= 1.5% (VeReMi) / <= 2% (Tampa) for every L3 check and the L3 union.
 4. Per-class detection (message and sender level), delay per attacker, FA on genuine messages and senders, harness ablation on top of L1+L2 (VeReMi and Tampa), all from the JSON.
 5. Value: L1+L2+L3 combined (harness) beats L1+L2 by >= 3 points of mean detection over the 19 VeReMi classes at <= 1.5% FA. If not, stated as "L3 does not add value".
 6. python tests/run_tests.py passes.
Pre-registered expectations (stated, not tuned to), message level at the 1% budget, VeReMi test:
 K1 ConstPosOffset (2): < 5% by every L3 check (consistent track, only shifted; the tracker has no absolute reference).
 K2 EventualStop (9): cusum_lo catches the frozen stream: >= 30% of the falsified messages; < 10% would be reported as a failure of the idea.
 K3 DelayedMessages (12, held out), as it appears in this CSV (zero placeholders): similar to K2 (>= 30%) if cusum_lo works; reported either way.
 K4 DataReplay (11) and GridSybil (16): the tracker re-catches what L2 already caught (>= 50% each, as VeReMi's own attacks are kinematically inconsistent); no gain expected over L2.
 K5 DataReplaySybil (17, held out): <= 30% from the tracker (tracks are 1-2 messages); the birth check may add some.
 K6 DoSRandomSybil / DoSDisruptiveSybil (18/19): ~0% from the tracker (one message per pseudonym within 5 s), birth density: random claimed positions fall in different cells, so < 20% expected.
 K7 Genuine val NIS mean in [3.0, 5.0] but the upper tail heavier than chi2 (stops, junctions): fraction above 95% in [5%, 10%].
Misses are reported plainly. No re-splitting, no re-tuning after seeing results.

## 2026-10-20 S4 results (numbers in results/WP5/s4_summary.json, s4_veremi.json, s4_tampa.json, s4_diag.json; scripts tools/WP5_S4_l3.py, WP5_S4_diag.py, WP5_S4_report.py; logs results/WP5/logs/s4_dev1.log, s4_run1.log)
- Code v2x/l3.py (4 layers), tests/v2x/test_l3.py (11), suite 144 passed. Report reports/WP5_S4.md (summary) + results/WP5/s4_report_details.md (full).
- Noise fit VeReMi (sp 0.05 floor, sv 0.02 floor, sa 1.94; 9.5 min); Tampa sp 0.37, sv 0.02 floor, sa 1.16. Consistency val: VeReMi NIS mean 4.15, 7.0% > chi2 95%, median 0.19 (poor shape); Tampa mean 2.10.
- FA test: VeReMi all L3 <= 0.9%; Tampa cusum_lo 13.5%, L3 union 14.8% (NOT MET); kf_nis 0.6, cusum_hi 1.8, birth 0.0.
- Value VeReMi: combined L1+L2 68.0% -> L1+L2+L3 78.4% mean detection, FA 0.98 -> 1.08%.
- Per class: 2 nothing; 9 11% (cusum_lo 18.7%); 11 98%; 12* 48% (placeholder jump + CUSUM memory); 16 73%; 17* 53% (birth); 18/19 tracker blind, birth 38/43%, sender >=3 alarms 98/100%.
- Expectations K2 not met, K3 right number wrong reason. Acceptance: PARTIAL. Decisions pending: drop cusum_lo? learned road-occupancy prior?
- Pitfalls: CUSUM memory inflates message-level detection after one jump; cusum_lo FA does not transfer to real standing vehicles; sender >=1 alarm is useless at per-message 1% budget.

## 2026-10-21 S5 L4 supervised model on L1-L3 plausibility features: acceptance rule (written before any S5 result)
Supervisor (S4 APPROVED partial): kf_cusum_lo dropped from the deployable L3 (diagnostic only; NOT a feature of L4 either). L4 = gradient boosting (xgboost 2.1.4, CPU, n_jobs=4)
on per-message and per-sender-window PLAUSIBILITY features computed by L1-L3 (residuals, NIS, CUSUM state, beacon rate, birth density), NOT on raw position / speed / sender id / time.
Design (module v2x/l4.py, fixed now). Feature groups (all causal, track = claimed pseudonym stream):
  M  per message : pos_speed, pos_heading, speed_change, implied_speed, heading_rate, accel_consistency, overlap (L2 raw scores), kf_nis, kf_cusum_hi (L3), beacon rate (L1, Hz/10),
                   field_violation (L1 field_ranges raw >= 1, binary; the continuous raw is mostly speed/V_MAX and is not used).
  W  window      : trailing 10 messages of the same track: max and mean of nis, pos_speed; max of pos_heading, implied_speed, speed_change, heading_rate, mean of accel_consistency;
                   number of window messages with NIS > chi2(4) 95%; max beacon rate.
  N  network     : birth_density of the track's first message (L3 track_birth) for the first message and carried forward along the track (causal), is_first.
  T  time/id     : track_pos (index of the message in its track, capped at 30), dt_prev (s). These two are sender/time-derived; they are in the model but ablated (see below).
Training: VeReMi TRAIN split (splits_veremi.json), rows of attack types 6, 12, 17 REMOVED from the frame (so also from neighbour features), genuine rows all. Hyperparameters:
a fixed grid of 8 configs (depth {3,5,8} x min_child_weight {1,50}, plus 2 shrinkage/subsample variants), early stopping on validation aucpr, choice = mean detection over the 16 seen
attack classes at the validation 1% genuine budget (VALIDATION, held-out types removed from the validation frame, grouped by the time-block split). Threshold: genuine validation, 1% budget,
tie-safe (common.metrics.budget_threshold). Test is scored ONCE (final run); no choice after it. Tracker noise parameters are those of S4 (fit on genuine train only), no refit.
Reported (test, VeReMi): per-class detection (16 seen + unseen 6, 12, 17 separately: the key result), FA on genuine messages and senders, harness ablation on top of the deployable
L1+L2+L3 (groups L1+L2+L3, L4, L1+L2+L3+L4, plus max-union versions at one 1% budget), AUC.
Leakage checks: (a) gain importance of the final model, red flag if one feature has > 50% of the gain and it is not a physical residual; (b) ablation A1 = no T group, A2 = no T group and no
rate / birth features (residuals only), same hyperparameters, refit; (c) shuffled-label control (train labels permuted, same hyperparameters): test AUC must be in [0.45, 0.55]
and detection at the 1% budget <= 2%; (d) class 12: reported with the full model, with a model without the memory features (kf_cusum_hi and all W features), and split into rows at the
zero placeholder (x = y = 0, post-hoc diagnostic only, never a feature) vs rows after the jump; class 12 is NOT claimed as delay detection in the headline.
Tampa (illustration, 3 test vehicles): the VeReMi-trained model is applied unchanged. The features come from the Tampa tracker of S4 (normal-model noise fit on Tampa TRAIN passages,
no labels) and the S4 Tampa L1/L2/L3 calibration; yaw_consistency is not a feature. Two thresholds reported: (i) threshold transferred from VeReMi validation (no Tampa data at all),
(ii) 1% of genuine Tampa validation messages. No retraining, no Tampa test choice. Expected: drop (sim-to-real).
S5 is MET if all hold:
 1. v2x/l4.py, features from L1-L3 only (no x, y, speed, sender id, t), tests pass (python tests/run_tests.py); held-out types absent from training, validation frame and selection (asserted).
 2. FA on genuine VeReMi TEST messages <= 1.5% for the L4 operating point and for L1+L2+L3+L4.
 3. Value: L1+L2+L3+L4 (harness combiner) beats L1+L2+L3 (deployable, no cusum_lo) by >= 3 points of mean detection over the 19 classes at <= 1.5% FA.
 4. Unseen generalisation (reported plainly either way): L4 alone mean detection over the unseen types 6 and 17 >= the deployable L1+L2+L3 union on the same types, and >= 50%.
    Class 12 reported separately, no pass/fail.
 5. Leakage checks (a)-(c) pass: no red-flag dominant feature, shuffled-label control at chance, A1 changes mean detection over seen classes by <= 5 points (a larger drop is reported as
    dependence on sender / time structure, not hidden).
Pre-registered expectations (not tuned to): E1 L4 alone seen-class mean detection 80-90%; E2 class 6 (sibling 5 ConstSpeed seen) >= 80%; E3 class 17 (siblings 11, 16 seen, 1-message tracks)
only 40-70% (limited by the features, not by the model); E4 class 12 full model >= 40% (placeholder jump + memory), without memory features < 15%; E5 classes 2 (ConstPosOffset) and 9 (EventualStop)
stay low (< 30%) because no plausibility feature exposes them; E6 A2 (residuals only) loses mainly the DoS classes 13-15 and Sybil 18/19; E7 Tampa mean detection < VeReMi's by >= 20 points.
Misses are reported plainly. No re-splitting, no re-tuning after seeing the test.

## 2026-10-21 S5 results, first look (numbers: results/WP5/s5_dev.json, s5_summary.json, s5_tables.md; scripts tools/WP5_S5_dev.py, tools/WP5_S5_l4.py; logs results/WP5/logs/s5_dev1.log, s5_run1.log)
- Dev (validation only): 8 configs all within 0.91-0.911 mean detection of the seen classes (plateau, AUC 0.973-0.975); chosen d5_mcw1, 120 trees (criterion fixed in advance). Features train 1.9 M rows (held-out types removed), 27 features.
- Test (scored once): L4 alone mean detection seen-16 91.3%, unseen 6 / 17 = 100.0% / 91.9% (deployable L1L2L3 union 99.1% / 46.4%), class 12 100.0% (union 48.2%), FA genuine msgs 1.1%,
  genuine senders >= 3 alarms 1.8% (union 10.5%). Harness: L1+L2+L3 78.1% -> L1+L2+L3+L4 91.5% mean over 19, FA 1.1% -> 1.2%. AUC pooled 0.893 -> 0.968.
- Leakage: A1 (no time/track) 91.2% seen, A2 (residuals only) 91.2%: unchanged. Shuffled labels: test AUC 0.475 but detection at 1% FA 4.1% pooled (my rule said <= 2%: NOT MET, the noise model's tail still picks outlier rows that attacks are more often).
  Gain: cusum_hi 55.5% (a physical state, but dominant).
- RED FLAG found while reading the tables: L4 detects class 9 EventualStop (79% vs 1%), class 12 zero-placeholder rows (100%, residual-only model too) and the one-message Sybil tracks 17/18/19 (92/100/100%).
  Common cause suspected: these rows have an EXACTLY ZERO residual vector (unscored first message of a track; exactly repeated message) - genuine VeReMi senders always carry measurement noise, so "exact zero" separates them in the simulation
  (same artefact the supervisor dropped cusum_lo for) and the 1% per-message budget lets the model flag all genuine first messages (~1% of genuine messages). Diagnostics (not model selection, post-hoc, labelled as such): tools/WP5_S5_diag.py.

## 2026-10-21 S5 final results and diagnosis (files: results/WP5/s5_summary.json, s5_tables.md, s5_diag.json, s5_diag.md, s5_tampa_frozen.json; report reports/WP5_S5.md)
- Final run (test once, 212 s): see the first-look entry above for the headline; harness L1+L2+L3 78.1% -> +L4 91.5% (mean over 19), unseen 6 / 17 / 12 = 100.0 / 91.9 / 100.0% (union 99.1 / 46.4 / 48.2%).
- Post-hoc diagnostic (same saved model, same test rows; NOT used to select anything; one extra diagnostic model trained on scored train rows): row kinds from l2.Pairs: scored (predecessor and moved) / unscored (first message, gap) / frozen (exact repeat).
  Genuine VeReMi rows: 99.1% scored, 0.9% unscored, 0.0% frozen. Attack rows (test): 68.5 / 15.5 / 16.0%. Headline L4 flags 100% of unscored and 100% of frozen rows, only 0.2% of scored genuine rows;
  84.3% of its genuine false alarms are first messages. Genuine Tampa frozen share 10.6-20.6% (s5_tampa_frozen.json). Conclusion: part of the headline gain is the zero-residual-vector shortcut (simulation artefact: noise-free repeats; new identity alarms for every genuine birth).
  Scored rows only: seen 83.0% (headline) / 83.5% (diagnostic model) / 82.7% (baseline); unseen 6 and 17: 87.4 / 98.2 / 59.9%; class 17 scored rows 74.8 / 96.3 / 19.9% (the real gain, replay-Sybil learned from classes 11 and 16).
- Shuffled control: AUC 0.475 (pass) but detection 4.1% pooled at 1.1% FA (rule: <= 2%, not met): the score tail of a noise model selects outlier rows.
- Tampa: VeReMi scale does not transfer (FA 100% at VeReMi threshold: 10 Hz beacons); at the Tampa-val 1% threshold mean detection 77.6% at 0.3% FA (baseline 71.3% at 3.0%), unseen 6 and 17 55.1% (baseline 64.2%), StaleReplay 0%.
- Pitfalls: (1) per-message 1% budget lets the model spend the whole budget on genuine first messages (~0.9% of messages); report FA per genuine first message and scored-row FA next to the message FA. (2) Zero residuals encode "first message" and "exact repeat"; do not give them a class meaning (the same reason cusum_lo was dropped). (3) Class 12 gain = frozen placeholder rows + CUSUM memory, not delay detection. (4) xgboost wrapper refits are deterministic (test AUC reproduced to 1e-16 from the saved model).
- Acceptance S5: PARTIAL (see report). Not done: a pre-registered scored-rows-only L4 test evaluation (needs the supervisor's go, test already used).

## 2026-10-21 S6 (M1-V2X) acceptance rule (written BEFORE any S6 result; no dev result seen yet)
Supervisor decisions (binding, ORCHESTRATOR 2026-10-21): (1) deployable L4 = xgboost trained and scored ONLY on "scored rows" (message has a predecessor in its track within DT_MAX AND moved;
kinds from l2.Pairs: 0 scored / 1 first-or-gap / 2 exact repeat); L4 raw score = 0 on kinds 1 and 2 (never alarms); new identities are left to the sender-level birth rule (L3 track_birth, >= 3 alarms);
exact repeats and class 12 are never claimed as detections of L4. (2) Tampa-bound features must be beacon-rate invariant; decided on VeReMi VALIDATION only. (3) shuffled-label control re-run on scored rows,
bound NOT lowered: detection of a null model within 1 point of its FA (pooled scored attack rows vs scored genuine test rows); pass/fail reported. (4) VeReMi test was seen in S5: the S6 run is a SECOND
exposure; to be said in reports/M1_V2X.md. Headline claims: unseen-type generalisation (6, 17; 12 excluded as an artefact) and the scored-row analysis.
Design (fixed now). Row kinds: as tools/WP5_S5_diag.py (moved to v2x/l4.row_kinds). Candidate feature sets for the scored-row L4 (all trained on scored TRAIN rows only, types 6, 12, 17 removed from train,
validation and neighbour features):
  S0_full27   : the 27 S5 features (count windows of 10 messages, rate, birth, track_pos, dt_prev). REFERENCE ONLY (not rate invariant).
  S1_noT_noRate: S0 minus T, N groups, rate, w_rate_max (count windows). REFERENCE ONLY (windows are 10 messages = 10 s at 1 Hz but 1 s at 10 Hz: not invariant).
  S2_resid    : 10 per-message features (L2 residuals, nis, cusum_hi, field_violation); no rate, no windows, no T, no N. ELIGIBLE (no time scale in the features).
  S3_timewin  : S2 + the 10 window aggregates computed over a TIME window of 10 s: window length in messages = clip(round(10 s / nominal_dt), 3, 100), nominal_dt = median of the first <= 5 positive
                intervals of the track (the sender's own nominal beacon interval; it only sizes the window), w_rate_max dropped. ELIGIBLE.
Selection on VeReMi VALIDATION (fixed criterion): mean detection over the seen classes (16) with >= 50 scored validation rows, on scored attack rows, at the 1% budget of scored genuine validation rows.
Among ELIGIBLE sets the one with the best criterion wins, but S2 wins if S3 is better by < 1.0 point (simplicity). Hyperparameters: grid of 4 (d3_mcw1, d5_mcw1, d5_mcw50, d8_mcw50) for the eligible sets;
references with d5_mcw1 only. S0 / S1 are reported to show the price of invariance, never selected. Combiner method per configuration by group-split validation halves (common/combiner.py, "auto").
Deployable stack: L1 (beacon_rate, field_ranges), L2 (7 checks, no map_road, no yaw/freshness), L3 (kf_nis, kf_cusum_hi, track_birth; no kf_cusum_lo), L4-scored. Each layer calibrated on genuine validation
rows (1%, tie-safe), as in S5. Ablation (test, once): each group alone, all four, all-but-one; message level (all rows and scored rows) and sender level (>= 3 alarms), delay per attacker
(first falsified message to the 3rd alarm, and to the 1st alarm), FA on genuine test messages / scored genuine messages / genuine senders. 95% CIs: block bootstrap over the VeReMi TEST time blocks (1000
resamples, seed SEED), no CIs for Tampa. Tampa (illustration, 3 vehicles): VeReMi-trained L4 frozen, S4 Tampa tracker and Tampa L1-L3 calibrations, stack = parameter-free combiner (the VeReMi-chosen method if
noisy_or / max, else max), thresholds on Tampa genuine validation only.
S6 / M1-V2X is MET if all hold:
 1. Scored-row L4 + invariant features implemented, selection logged from validation only, tests pass (python tests/run_tests.py), held-out types absent from every fit and validation frame.
 2. FA of the full stack on genuine VeReMi TEST: <= 1.5% of messages and <= 1.5% of scored genuine messages; genuine senders with >= 3 alarms <= 5% (reported plainly if not).
 3. Value on SCORED test rows: mean detection of the full stack over the seen classes (>= 50 scored rows) is >= that of L1+L2+L3 minus 1 point (no loss), AND on the unseen class 17 the stack beats L1+L2+L3
    by >= 10 points; unseen class 6 >= 95%.
 4. Shuffled-label control on scored rows: detection within 1 point of FA. Pass / fail reported (bound not changed).
 5. Block-bootstrap CIs for every headline number; Tampa labelled as illustration, no CIs.
Pre-registered expectations (not tuned to): E1 class 2 ConstPosOffset <= 5% and class 9 EventualStop <= 10% on scored rows for every group; E2 sender-level (>= 3 alarms) 18 and 19 >= 90% via track_birth;
E3 the stack's scored-row mean over seen classes is within +-3 points of 83% (S5 diagnostic); E4 removing L2 costs the most, removing L1 costs only the DoS classes 13-15 (message level), removing L4-scored
changes the seen-class mean by < 2 points and class 17 by >= 10 points; E5 shuffled control does NOT pass at 1 point (outlier tail seen in S5: 3.4% on seen classes), reported plainly; E6 Tampa FA of the stack
<= 3% at its 1% val budget (3 vehicles, wide uncertainty), Tampa detection below VeReMi's on scored rows; E7 S2 vs S3 differ by < 1 point on validation (S2 chosen).
Misses are reported plainly. No re-splitting, no re-seeding, no re-tuning after the test.

## 2026-10-21 S6 dev result and plumbing addendum (still before the test run)
Dev (validation only; results/WP5/s6_dev.json, logs/s6_dev1.log): criterion (mean detection, 16 seen classes with >= 50 scored val rows, 1% of scored genuine val rows): S0_full27 0.8410, S1_noT_noRate 0.8399,
S2_resid best 0.8388 (d5_mcw1, 139 trees), S3_timewin best 0.8399 (d5_mcw1). S3 - S2 = +0.12 points < 1.0 -> S2_resid chosen (E7 right). Price of rate invariance on the seen classes: 0.2 point.
Smoke run on the VALIDATION split as stand-in test (plumbing only, results/WP5/s6_*_smoke.*): pipeline works; sender-level FA with the supervisor's k = 3 rule is 9-13% for the combined stack / L4 (message FA 1%,
alarms spread over long genuine tracks), so acceptance item 2 (<= 5% genuine senders at k = 3) will very likely be missed: reported plainly. Additions fixed now (nothing about the test is known):
 (a) a second sender-level rule chosen on VALIDATION: k_val = smallest k >= 1 such that <= 1% of genuine VALIDATION senders have >= k alarms of that configuration (the domain budget at sender level); reported next to k = 3;
 (b) reference rows (never selected, never deployable for Tampa): L4-scored with feature sets S0_full27 and S1_noT_noRate (count windows, d5_mcw1, trees from s6_dev.json) alone and S0 inside the full stack,
     to show the price of beacon-rate invariance (S5 diagnostic: class 17 scored rows 96% with the unrestricted model).
 (c) stackeval.sender_table keys senders by (sender, attack type) (Tampa re-uses vehicle ids across scenarios).
Expectation E8: class 17 on scored rows is clearly lower with the invariant L4 than with S0 (rate / dt features carry it); the acceptance item 3b (class 17: stack beats L1+L2+L3 by >= 10 points) is at risk.

## 2026-10-21 S6 final results (VeReMi test, SECOND exposure, scored once; files: results/WP5/s6_dev.json, s6_veremi.json, s6_tampa.json, s6_acceptance.json, s6_tables_*.md; reports/M1_V2X.md, reports/WP5_S6.md; logs s6_dev1, s6_smoke2, s6_run1)
- Code: v2x/l4.py (row_kinds, window_lengths, time_window_s option, SCORED_SETS, L4Scored), v2x/stackeval.py (block bootstrap, sender table, delays), tools/WP5_S6_{dev,run,report}.py. Suite 185 pass.
- Dev: S2_resid chosen (val criterion 0.8388; S3 +0.12 pt; S0_full27 0.8410). Final stack combiner: max (val-half detection 82.8 vs logistic 79.5, noisy_or 73.5).
- Test (full stack = L1+L2+L3+L4-scored): FA msgs 1.1%, scored msgs 0.9%, genuine senders k=3 11.7% (k val = 9: 1.0%). Scored-row mean over 13 seen classes 83.0% [82.7, 83.1] vs L1+L2+L3 82.7% [82.4, 82.9]; class 6 100%; class 17 27.8% [24.7, 31.8] vs 19.9% [16.6, 24.2] (+8.0, rule +10: NOT met);
  L4 alone on 17: 48.9%; unrestricted S0 L4: 96.5% (S1 52.9%): the extra points come from track-position / interval / rate / birth features. Sender level (k val): seen mean 86.6%, 17: 95.3% [87.2, 100], 18/19: 97.8/100%.
- Acceptance: 1 met, 2a met, 2b (k=3 senders <= 5%) NOT met (11.7%), 3a met, 3b NOT met, 3c met, 4 shuffled NOT met (+2.3 points: null model 3.3% at 1.1% FA, AUC 0.511; excess on classes 11, 12, 14, 15, 17), 5 met. Overall PARTIAL.
- Expectations: E1, E2, E3, E5, E6, E7, E8 as expected; E4 wrong (L2 / L3 removal changes nothing on scored rows; on all rows L3 matters most: 78.4 -> 74.2%; L4 removal -0.3 points seen, -8.0 points class 17).
- Tampa (illustration): stack FA 2.8%, scored seen 81.8% (physics 81.7%), class 17 29.0% (29.1%), L4 alone FA 0.1%, 80.2%.
- Pitfalls: (1) sender-level k=3 at a 1% message budget flags 11.7% of genuine senders; use a validation-chosen k. (2) Max combiner chosen on validation without class 17 dilutes the only L4 gain (class 17). (3) bash heredoc turned a double backslash-n into a real newline in a generated file: use chr(92) in edit scripts. (4) tests/run_tests.py filters on the Windows path string: use "test_l4", not "v2x/test_l4".
- Feature cache (0.5 GB) deleted after the run. Smoke result files deleted.

## 2026-10-24 S0c V2AIX (D13): plan and acceptance rule (written BEFORE downloading)
Licence: non-commercial research, cite arXiv 2403.10221 (Hoffmann et al., V2AIX), NO redistribution: data and derived per-message files stay in ../data_extra/D13_v2aix/ and are never committed.
Disk rule: >= 15 GB free at all times (47 GB free at start). Untrusted data: read with python -I, nothing executed.
Extraction choice rule (fixed before looking at any message content; only archive listing metadata = paths and sizes): whole recordings (one scenarios/<ts>.json = one recording; joined.json files are NOT extracted
unless small) until ~5 GB total. Stratify by path strata (Mobile/Stationary x V2X-only/V2X-with-Sensor-Context x location): round-robin over strata, within a stratum take recordings in a seeded random
order (SEED 42), skipping any single file > 1 GB; stop at 5 GB. Splits 60/20/20 by recording, seed 42, stratified by (Mobile/Stationary, location) where a stratum has >= 3 recordings.
Acceptance (S0c):
 A1 archive downloaded completely (size equals Content-Length, zip test OK) and inventoried (recordings, scenarios, sizes, message types, ego pose and ego own CAMs present or not);
 A2 extracted subset <= 5.5 GB, covers >= 2 path strata if the archive has them; free disk >= 15 GB throughout;
 A3 adapter yields a table passing v2x.schema.validate; unit conversions tested (ETSI scaled integers); no negative speed; no duplicated msg_id;
 A4 splits disjoint by recording, sizes 60/20/20 +- one recording, deterministic;
 A5 plausibility (reported, not a pass/fail on values): speed 0..~70 m/s, heading in [0, 360), lat/lon within the region, sender-ego distance quantiles (radio range) for stationary-vs-mobile; field completeness per field.
 A6 no detection run; no data or per-message file in git.
Misses are reported plainly.

## 2026-10-24 S0c V2AIX results (files: results/WP5/s0c_inventory.md, s0c_selection.json, s0c_verify.json, s0c_tables.md, splits_v2aix.json; logs s0c_verify.log, s0c_tests.log)
- Download: v2aix_json.zip 1,007,346,151 bytes (equals Content-Length), zipfile testzip OK, 2,228 files, 22.16 GB uncompressed. Free disk 47 -> 40 GB after extraction (>= 15 GB kept).
- Archive layout: json/{Mobile,Stationary}/{V2X-only,V2X-with-Sensor-Context}/<location>/{joined.json, scenarios/<UTC timestamp>.json}; joined.json = all scenarios of a location concatenated (5.2 GB for Mobile Aachen): not extracted.
  1,540 scenario files in the selection = 13 strata (Mobile V2X-only: Aachen, Highway, Rural; Mobile Sensor-Context: Aachen, Cologne, Dusseldorf, Highway, Rural; Stationary V2X-only: Heinrichsallee, Monheimsallee, Ponttor, Theaterstrasse; Stationary Sensor-Context: A44-Jackerath).
- Topics: /v2x/cam (parsed ETSI CAM v2: header.station_id, generation_delta_time, basic container with reference position + confidence ellipse, high-frequency container, low-frequency container with path history), /v2x/raw (same packets as bytes, ignored),
  /gps/cohda_mk5/fix (ego GNSS of the OBU, 5-10 Hz; ONE fix for stationary units), /gps/oxts_rt3000/{fix,status,odom} (ego reference INS, ~100 Hz, Sensor-Context mobile only), /tf_static. No DENM in this JSON release. Only station type 5 (passenger car) appears; no RSU CAMs.
- Ego's own CAMs are NOT in /v2x/cam: no mobile sender has a median distance to the ego below 20 m (s0c_verify.json own_cam_check: 0.3% of messages within 3 m = vehicles passing the ego). So no V2X self-report witness for WP6 from V2AIX; the ego GNSS (cohda / oxts) is the only ego pose.
- Extraction (rule above, applied on paths and sizes only): 1,540 recordings, 4.999 GB (budget 5 GB), seeded round-robin over the 13 strata; the small strata are fully included.
- Parsed: 212,303 CAMs after dropping duplicates (sender, t) and rows without finite t, x, y, speed; 1,515 of 1,540 recordings contain at least one CAM; 1,956 (recording, station) senders. Splits 60/20/20 by recording, seed 42:
  train 907 rec / 123,593 msgs / 1,181 senders; val 304 / 41,285 / 380; test 304 / 47,425 / 395. Disjoint by construction (asserted). Mobile messages are only 12-15% of each split (18.5k / 7.4k / 4.3k): Stationary A44-Jackerath alone holds 135k messages.
- Units: ETSI scaled integers (documented in the v2x/v2aix.py docstring and unit-tested): lat/lon 1e-7 deg, heading 0.1 deg clockwise from north -> schema math heading (pi/2 - rad), speed 0.01 m/s, longitudinal acceleration 0.1 m/s^2, yaw rate 0.01 deg/s clockwise -> CCW positive, unavailable codes -> NaN.
- Time: CAM generation_delta_time is the sender clock (mod 65536 ms); its offset to the logger clock is a different constant per recording / sender. t = recv - latency with the latency unwrapped around the per-(recording, sender) median;
  age_s is the relative latency (median 0.025 s, p99 1.5 s, max 3.6 s). The absolute sender-clock delay cannot be recovered, so delayed-message checks can only use age_s as a relative quantity.
- Field completeness (finite share): speed, position, acl, yaw_rate, pos_sigma 1.0; heading 0.997; spd_sigma 0.48; acl_sigma 0.0 (always the unavailable code 102); rx_x / rx_y 0.955 (the NaN are Mobile V2X-only clips whose cohda fix is more than 2 s away: Highway 42%, Rural 40%, Aachen 13%; Sensor-Context 0-3%).
- Plausibility: speed median 29.4 m/s (0..163.82; 3 values above 70 m/s, all in Stationary Ponttor: 163.82 = raw 16382, and 108.46 twice; left in: real-data glitches, to be reported in S3b); 5.1% of messages at speed 0;
  yaw rate p1/p99 -0.285 / 0.211 rad/s (extremes -5.2 / +3.6 at low speed); acl p1/p99 -2.0 / 2.1 m/s^2 (range +-9.9); lat 47.17-51.24, lon 6.05-12.48 (some Highway drives leave the Aachen area; one fixed local origin, error < 0.5% inside the area).
  Implied speed from consecutive positions agrees with the reported speed only roughly (|diff| p50 0.39, p90 4.1, p99 12.9 m/s at dt < 1.5 s): position quantisation / GNSS noise (pos_sigma median 2.8 m) and the CAM generation rule make the consistency checks look very different from VeReMi.
  Sender-to-ego distance (radio range, needed by S3b): Mobile p50 172 m, p95 3.9 km, p99 5.0 km, max 6.6 km; Stationary p50 590 m, p99 4.2 km, max 8.05 km (A44-Jackerath p50 1.0 km, p99 4.3 km; urban Aachen stationary sites p99 70-270 m, max 327 m;
  Mobile Rural p50 3.5 km). The acceptance range must be calibrated per environment from genuine validation data: a VeReMi-style few-hundred-metre threshold would reject most genuine highway CAMs.
- Median inter-message time per track 0.35 s (p5 0.12, p95 1.18 s): CAM generation rule 0.1-1 s, neither 1 Hz nor 10 Hz.
- Acceptance: A1 met, A2 met (4.999 GB, all 13 strata, free disk >= 40 GB), A3 met (validate passes; 7 unit tests; 386 tests pass), A4 met (907/304/304 recordings = 60/20/20), A5 reported, A6 met.
- Pitfalls: (1) generation_delta_time offsets are per-recording constants, never an absolute time. (2) Mobile V2X-only clips are 2-3 s long and the cohda fix stops early: rx NaN, not extrapolated (no approximations). (3) The Bash tool breaks on some heredocs with quotes: write files with the Write tool.
- Licence reminder: data, cache/ and per-message tables are not in git; only code, tests, aggregate JSON / MD and split lists (recording ids) are.
