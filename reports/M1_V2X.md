# M1-V2X: detecting misbehaving V2X senders from received BSM / CAM messages (WP5, milestone report)

Date 2026-10-21. Status: **PARTIAL** (acceptance rule: notes/WP5_v2x.md, S6 section, written before any result). Self-contained; long tables: `results/WP5/s6_tables_veremi.md`, `s6_tables_tampa.md`; numbers: `s6_veremi.json`, `s6_tampa.json`, `s6_dev.json`, `s6_acceptance.json`.

**Protocol.** Benchmark = VeReMi Extension (D12, 19 attack types, simulated, 1 Hz): split by 1800 s time block (60/20/20, no sender or co-alive sender in two parts); every threshold, feature set, hyperparameter and combiner method chosen on validation; false-alarm budget 1% of genuine messages (domain budget). Types 6, 12, 17 were never in a fit, calibration, selection or combiner. **The VeReMi test split was already used in S5: this run is its SECOND exposure** (one run, nothing chosen after it). CIs are 95% block bootstrap over the 10 test time blocks (B=1000); they measure traffic variability, not training variance, and are wide on purpose. Test: 718,851 messages, 424,428 genuine. Real-message check = Tampa BSMs (D14) with injected attacks, 3 test vehicles: illustration only, no CIs.

## 1. What each layer catches (VeReMi test, scored rows = message has a moving predecessor in its track; each layer at its own 1% budget)

| layer | checks | catches (message detection, scored rows) | sender level (k val) |
|---|---|---|---|
| L1 rules | beacon rate, field ranges | DoS 13-15: 100.0% (rate); speed outside the legal range: ConstSpeed 5 71.3%, RandomSpeed 7 70.5%; Sybil 18 70.2% | 54.7% mean seen |
| L2 plausibility | position vs speed, heading, speed change, implied speed, heading rate, acceleration, overlap | random / offset position and speed 92.8%-100.0%; DataReplay 11: 69.9%; GridSybil 16: 70.9% | 74.3% |
| L3 Kalman | NIS, CUSUM-hi, track birth | adds memory: DataReplay 98.1%, class 12 jump (artefact), birth rule: Sybil 18/19 message 38.4%/42.8%, sender level 100.0% / 100.0% (k=3) | 86.1% |
| L4 xgboost, scored rows only | 10 rate-free residual features (84% of gain = CUSUM state) | equals the physics on seen classes (83.1% vs 82.7%); only gain: class 17 (48.9% alone vs 19.9%) | 68.0% |

Deployable L4 = trained and scored only on scored rows (first messages / gaps / exact repeats get score 0 and never alarm; new identities go to the sender-level birth rule). Feature set chosen on validation among rate-invariant candidates: **S2_resid** (time-window variant +0.12 point on validation, below the 1-point margin; the unrestricted 27-feature set would add only 0.2 point on seen classes).

## 2. Final numbers: ablation of the deployable stack (VeReMi test)

Combiner (common/combiner.py) chosen per configuration on group-split validation halves; the full stack chose `max`. Means are over the 13 seen classes with >= 50 scored test rows; k val = alarm count per sender chosen on validation (<= 1% of genuine validation senders).

| configuration | FA msgs | FA scored msgs | scored: mean seen | scored: 6* | scored: 17* | sender k=3: FA / mean seen | sender k val: FA / mean seen (k) |
|---|---|---|---|---|---|---|---|
| L1 | 1.0% [0.9, 1.1] | 1.0% [0.9, 1.1] | 38.1% [37.6, 38.8] | 9.6% [5.7, 12.4] | 2.2% [1.4, 3.1] | 18.1% / 64.9% | 0.3% / 54.7% (5) |
| L2 | 1.2% [1.1, 1.3] | 1.2% [1.1, 1.3] | 78.4% [77.9, 78.7] | 93.9% [91.2, 95.7] | 29.1% [26.6, 32.0] | 15.8% / 75.7% | 1.1% / 74.3% (9) |
| L3 | 1.0% [0.9, 1.1] | 0.3% [0.2, 0.4] | 82.3% [81.9, 82.5] | 99.2% [99.0, 99.5] | 17.6% [14.1, 22.2] | 2.1% / 87.3% | 0.7% / 86.1% (11) |
| L4-scored | 1.4% [1.2, 1.5] | 1.4% [1.2, 1.5] | 83.1% [82.9, 83.3] | 100.0% [100.0, 100.0] | 48.9% [45.8, 52.0] | 16.7% / 69.0% | 1.7% / 68.0% (12) |
| L1+L2+L3+L4 | 1.1% [1.0, 1.2] | 0.9% [0.9, 1.0] | 83.0% [82.7, 83.1] | 100.0% [100.0, 100.0] | 27.8% [24.7, 31.8] | 11.7% / 88.5% | 1.0% / 86.6% (9) |
| all but L1 | 1.2% [1.1, 1.3] | 0.5% [0.4, 0.5] | 82.8% [82.5, 83.0] | 100.0% [100.0, 100.0] | 28.9% [25.2, 33.4] | 7.3% / 87.4% | 1.2% / 86.7% (6) |
| all but L2 | 1.1% [1.0, 1.2] | 0.8% [0.7, 0.9] | 83.0% [82.8, 83.2] | 100.0% [100.0, 100.0] | 34.0% [30.3, 38.3] | 11.5% / 87.8% | 1.1% / 86.6% (8) |
| all but L3 | 1.0% [1.0, 1.1] | 1.0% [1.0, 1.1] | 83.0% [82.8, 83.2] | 100.0% [100.0, 100.0] | 28.9% [26.1, 32.5] | 12.0% / 86.7% | 1.0% / 84.1% (8) |
| all but L4 (= L1+L2+L3) | 1.1% [1.0, 1.1] | 0.9% [0.8, 0.9] | 82.7% [82.4, 82.9] | 99.8% [99.7, 99.9] | 19.9% [16.6, 24.2] | 11.3% / 88.5% | 0.8% / 86.5% (9) |

## 3. Full stack per class (scored rows, all rows, sender level, delay)

| class | scored share | msg, scored rows | msg, all rows | sender k=3 | sender k val | delay to 3rd alarm s (median) |
|---|---|---|---|---|---|---|
| 01_ConstPos | 0.0% | - (n=0) | 98.1% [97.6, 98.5] | 97.8% [95.3, 100.0] | 97.8% [95.2, 100.0] | 4.0 |
| 02_ConstPosOffset | 99.1% | 0.8% [0.6, 1.0] | 1.0% [0.7, 1.2] | 14.4% [9.0, 19.4] | 0.0% [0.0, 0.0] | 94.0 |
| 03_RandomPos | 99.1% | 100.0% [100.0, 100.0] | 99.2% [99.1, 99.3] | 98.9% [96.0, 100.0] | 98.9% [96.2, 100.0] | 3.0 |
| 04_RandomPosOffset | 99.1% | 100.0% [100.0, 100.0] | 99.3% [99.2, 99.4] | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 3.0 |
| 05_ConstSpeed | 99.1% | 100.0% [99.9, 100.0] | 99.8% [99.7, 99.8] | 100.0% [100.0, 100.0] | 97.7% [95.5, 100.0] | 2.0 |
| 06_ConstSpeedOffset * | 99.1% | 100.0% [100.0, 100.0] | 99.3% [99.2, 99.4] | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 3.0 |
| 07_RandomSpeed | 99.2% | 100.0% [100.0, 100.0] | 99.8% [99.7, 99.9] | 100.0% [100.0, 100.0] | 98.9% [96.5, 100.0] | 2.0 |
| 08_RandomSpeedOffset | 99.1% | 100.0% [100.0, 100.0] | 99.3% [99.2, 99.4] | 100.0% [100.0, 100.0] | 98.8% [96.9, 100.0] | 3.0 |
| 09_EventualStop | 20.7% | 0.8% [0.5, 1.2] | 1.1% [1.0, 1.3] | 6.9% [1.6, 12.1] | 0.0% [0.0, 0.0] | 57.0 |
| 10_Disruptive | 96.5% | 99.3% [97.8, 100.0] | 98.6% [97.1, 99.3] | 100.0% [100.0, 100.0] | 98.9% [95.7, 100.0] | 3.0 |
| 11_DataReplay | 84.5% | 98.7% [98.1, 99.1] | 98.1% [97.5, 98.7] | 98.8% [96.7, 100.0] | 98.8% [96.7, 100.0] | 3.0 |
| 12_DelayedMessages * | 48.1% | 100.0% [100.0, 100.0] | 48.2% [43.1, 52.8] | 77.0% [73.6, 81.9] | 71.3% [67.8, 75.4] | 63.0 |
| 13_DoS | 32.9% | 100.0% [100.0, 100.0] | 99.8% [99.7, 99.8] | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 0.9 |
| 14_DoSRandom | 99.7% | 100.0% [100.0, 100.0] | 99.9% [99.9, 100.0] | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 1.0 |
| 15_DoSDisruptive | 96.7% | 100.0% [100.0, 100.0] | 99.7% [99.7, 99.8] | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 1.5 |
| 16_GridSybil | 96.9% | 79.2% [76.2, 81.8] | 77.4% [74.5, 80.0] | 98.9% [96.6, 100.0] | 97.7% [95.2, 100.0] | 1.5 |
| 17_DataReplaySybil * | 32.0% | 27.8% [24.7, 31.8] | 51.4% [46.3, 55.5] | 98.8% [95.9, 100.0] | 95.3% [87.2, 100.0] | 6.0 |
| 18_DoSRandomSybil | 0.0% | - (n=0) | 71.8% [71.3, 72.2] | 100.0% [100.0, 100.0] | 97.8% [94.7, 100.0] | 1.5 |
| 19_DoSDisruptiveSybil | 0.2% | - (n=28) | 47.3% [44.9, 50.5] | 100.0% [100.0, 100.0] | 100.0% [100.0, 100.0] | 3.0 |

Genuine senders flagged: k=3 11.7% [10.3, 12.9] (k=3 flags 11.7% of genuine senders, so sender rates below ~12% at k=3 are chance level, e.g. classes 2 and 9); k val=9 1.0% [0.7, 1.3].

## 4. Headline claims (with the second-exposure caveat)

1. **Unseen attack types.** Class 6 ConstSpeedOffset (sibling of seen 5): 100.0% [100.0, 100.0] on scored rows. Class 17 DataReplaySybil: message level on scored rows 27.8% [24.7, 31.8] (L1+L2+L3 19.9% [16.6, 24.2]; L4 alone 48.9% [45.8, 52.0], the gain is real but modest and the max combiner dilutes it); sender level 95.3% [87.2, 100.0] at 1.0% genuine-sender FA (k val), 98.8% [95.9, 100.0] at k=3. Class 12 is excluded (artefact, section 6).
2. **Scored-row analysis.** On the 13 seen classes the full stack detects 83.0% [82.7, 83.1] of falsified scored messages at 0.9% [0.9, 1.0] false alarms; the physics-only stack gives 82.7% [82.4, 82.9]: the supervised L4 adds nothing on seen classes. At sender level (k val) the stack finds 86.6% [86.2, 87.0] of seen-class attackers at 1.0% [0.7, 1.3] genuine senders flagged.
3. Delay (median over detected attackers, first falsified message to the 3rd alarm): 2-3 s for position / speed falsifications and replay, 0.9-1.5 s for DoS, GridSybil 16 1.5 s, class 17 6.0 s, Sybil 18 / 19 1.5 / 3.0 s (full table: section 3 and results).

## 5. What is NOT caught

- **ConstPosOffset (2):** 0.8% [0.6, 1.0] of messages, 0.0% [0.0, 0.0] of senders: a consistent track that is only shifted looks like a real vehicle (needs an absolute reference: receiver position, map, other sensors; see WP6). **EventualStop (9):** 0.8% [0.5, 1.2] scored, 0.0% [0.0, 0.0] of senders (78% of its rows are exact repeats: a stopped car).
- **Sybil with a new pseudonym per message at message level (18, 19; 17 partly):** 18 / 19 have (almost) no scored rows (one message per identity), message detection 71.8% [71.3, 72.2] / 47.3% [44.9, 50.5] comes from field ranges and the birth rule; only the sender-level rule is reliable (97.8% [94.7, 100.0] / 100.0% [100.0, 100.0]).
- **Delayed messages:** VeReMi has no message age, so delay is not testable; the 48% on class 12 is an artefact. On Tampa the freshness check catches the injected stale replays (100.0% with L1).
- GridSybil 16 79.2% [76.2, 81.8] per message (sender 97.7% [95.2, 100.0]); DataReplay 11 98.7% [98.1, 99.1].

## 6. Artefacts found (reported so nobody re-discovers them)

- **Zero placeholder (class 12):** x=y=0 rows (4888 of 9421) look like a simulator placeholder, not delay. The S5 L4 flagged them 100%; the scored-row stack flags 0.2%; the 48.2% on class 12 comes entirely from rows after the jump (CUSUM memory, 100.0%). Not claimed.
- **Exact repeats:** 0% of genuine VeReMi rows but 99% of class 1, 78% of class 9, 67% of class 13, 14% of class 17 are exact repeats of the previous position (the reason kf_cusum_lo was dropped in S4); genuine Tampa has 12.4% (standing vehicles). A model fed zero residuals turns this into an attack flag (S5: 100% of repeats); scored-row L4 never sees them.
- **Track-first messages:** the S5 L4 flagged 100% of genuine first messages (84% of its false alarms); scored-row L4 scores them 0 (FA 0.0%); the full stack still flags 22.3% of genuine first messages (birth rule, field ranges).
- **Tampa RSU-copy leak (S1b):** 43% of raw Tampa rows were the same message heard by several RSUs and the S1 split put copies on both sides (68% of old test rows); fixed by dedup and a time-block split.
- **Rate-dependent features carry class 17 in VeReMi:** with the unrestricted 27 features the scored-row L4 gets 96.5% [95.5, 97.1] on class 17 (features: position in track, interval, rate, birth), against 48.9% [45.8, 52.0] with the rate-free set; the extra points come from identity-churn structure of the simulator and do not transfer to 10 Hz beacons.
- **Null model on the label shuffle:** see section 7. The CIs are narrow because the test classes are large and detection is near 0 or 100% for most; with 10 blocks they say nothing about simulator-vs-real shift.

## 7. Controls and acceptance

- Shuffled-label control on scored rows (bound not lowered): null model detects 3.3% at 1.1% FA (+2.3 points; AUC 0.511): **FAIL** (1 point). The excess sits on classes with out-of-range feature values (11, 12, 14, 15, 17: 5-8%): likely cause (not tested): tree models send inputs beyond the training range to an arbitrary leaf, and attacks produce such inputs more often than genuine traffic. AUC is at chance; the control shows the tail, not leakage.
- Acceptance: FA messages 1.1% / scored 0.9% (<= 1.5%: met); genuine senders at k=3 11.7% (<= 5%: NOT met; k val 1.0%); no loss on seen scored rows (+0.3 points: met); class 17 gain +8.0 points (>= 10: NOT met); class 6 100.0% (met); shuffled control FAIL; CIs reported (met). Overall **PARTIAL**.
- Pre-registered expectations: E1 yes, E2 yes, E3 yes, E4a NO, E4b NO, E5 yes, E6 yes, E7 yes, E8 yes. E4a/E4b miss: removing L2 or L3 does not change scored-row detection (the max combiner finds the same messages through L3 / L4); on all rows L3 matters most (mean over 19 classes 78.4% -> 74.2% without L3, 79.0% without L2, 77.3% without L1; L1 matters for Sybil 18 / 19 and range-visible speeds).

## 8. Real messages (Tampa BSMs, injected attacks, 3 test vehicles; illustration, no CIs)

VeReMi-trained L4 frozen (rate-free features), Tampa tracker and Tampa layer calibrations, thresholds on Tampa genuine validation (1%); parameter-free `max` combiner. Full stack: FA 2.8% of genuine messages (4225 messages), scored-row mean detection 81.8% over seen classes (physics-only 81.7%), class 6 99.4%, class 17 29.0% (physics-only 29.1%), sender level (k=3) 90.6%. L4 alone: FA 0.1%, 80.2%. Genuine Tampa test rows: 12.4% exact repeats. The numbers are consistent with VeReMi but 3 vehicles and 2 attackers per type cannot support a claim; position-in-track and rate features were dropped, residual scales still differ (10 Hz vs 1 Hz).

## 9. Literature

VeReMi Extension papers (Kamel et al., ICC 2020 and follow-ups with ML detectors) usually report precision / recall / F1 per attack type, mostly with splits by message or by receiver log, so neighbouring messages of the same sender are on both sides. Ours splits by time block with zero shared senders and fixes the operating point at 1% genuine false alarms, so no number-to-number comparison is made; our split is stricter. Only the per-type structure (which attacks are easy: random / offset speed and position, DoS; hard: ConstPosOffset, EventualStop) agrees with the literature qualitatively.

## 10. Limits and next

- V2AIX (real CAMs) access form still pending; Tampa = one day, ~38 vehicles, 3 test vehicles. No receiver positions in either set: acceptance range and sudden-appearance checks are implemented but not evaluated.
- VeReMi is simulated; genuine position noise is time-correlated, classes 11 / 13 / 16 are kinematically inconsistent, class map partly verified (S1). Second exposure of the test split; CIs cover traffic variability only.
- Next (WP6): absolute-position witnesses (GPS / map / LiDAR) are the only route to ConstPosOffset and EventualStop; a Tampa-specific L4 needs more Tampa days (ITS DataHub request).

## V2AIX addendum (2026-10-24, WP5 S3b)

Does not change the M1 numbers above (VeReMi, Tampa). V2AIX = real ETSI CAMs (arXiv 2403.10221, non-commercial, no data in the repo), Aachen region, 212,303 CAMs, ego GNSS as receiver position; split by recording; Mobile (ego moving) and Stationary (fixed unit) always separate. Full report: reports/WP5_S3b.md, tables results/WP5/s3b_*.md.

- Real genuine traffic, frozen physics stack (L1+L2+L3, 12 checks): VeReMi calibration flags 92% (Mobile) / 95% (Stationary) of genuine test messages (does not transfer). Thresholds re-fitted on V2AIX genuine validation (on-deployment regime): 1.15% / 0.97% of messages = 83 / 110 alarms per receiver-hour (23 / 30 events per hour); genuine senders with >= 3 alarms 7.6% / 13.2%, at the validation-chosen k 0.0% / 1.0%. Alarm sources are noise statistics of fast cars, parked-car position wobble and slow-urban heading noise, not attacks.
- Injected VeReMi-taxonomy attacks on real CAMs (test, 1% budget from validation): mean scored-row detection 77.3% Mobile / 80.0% Stationary (VeReMi 82.7%, Tampa 81.7%); random position / speed, Disruptive, DoSRandom, DoSDisruptive 99%-100%; DoS x2 6.4% / 9.0% and GridSybil 2.7% / 11.8% per message (rate and overlap cues of VeReMi do not exist in irregular real CAM streams); ConstPosOffset and EventualStop remain unseen.
- Receiver-position checks, now evaluable: acceptance range (km-scale on V2AIX; explained by geometry and link budget, relay not excludable; Stationary passes the gate only with a post-hoc corrected clause) pooled threshold 3.5 / 4.3 km, FA 0.74% / 0.49%, catches a far-spoofed position (68.7% / 98.6% of injected rows), +1.6 / +0.2 points on the mean. Sudden appearance fails on real data (genuine first messages arrive close by; ghost tracks detected 21% / 0%). A 3 s latency step is caught 100% only by the freshness check (not in the frozen stack).
- Status: S3b PARTIAL; the M1-V2X status and numbers are unchanged.
