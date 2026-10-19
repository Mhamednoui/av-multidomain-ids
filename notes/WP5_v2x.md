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
