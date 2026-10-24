# WP5 S3b: real V2X traffic with receiver positions (V2AIX): false alarms of the frozen physics stack, acceptance range, sudden appearance, injected attacks

Date: 2026-10-24    Worker: sonnet medium (T2)

## Summary (details and long tables below and in results/WP5/s3b_*.md)

1. KEY NUMBER, real genuine traffic (V2AIX test, scored once, 12 frozen physics checks L1+L2+L3, max combiner): with the VeReMi calibration (variant A) the stack flags 92.3% (Mobile) and 95.1% (Stationary) of genuine messages: it does not transfer (beacon_rate 88.8% / 92.0% because VeReMi beacons are 1 Hz; field_ranges 52% / 66%, implied_speed 56% / 76%, Kalman CUSUM 8% / 44%). Re-calibrated on V2AIX validation of the same environment (variant B, the on-deployment regime): 1.15% [0.50%, 1.93%] Mobile and 0.97% [0.61%, 1.51%] Stationary per message, i.e. 83 and 110 alarms per receiver-hour (23 / 30 alarm events per hour, same-sender alarms within 10 s merged; 0.60 and 3.82 receiver-hours of test).
   Per genuine sender: >= 3 alarms flags 7.6% (Mobile) / 13.2% (Stationary) of senders (k=3 is not a 1% rule, as in M1); with k chosen on validation (k=18 / 22) 0.0% / 1.0%.
   Where the alarms are: 89% of Stationary alarms sit in the 40 senders with >= 3 alarms; no GNSS jump (> 70 m/s implied) among them in test. Top senders (results/WP5/s3b_top_senders.md): fast A44 cars (median 42 m/s) whose reported speed disagrees with the position increments (CUSUM / implied speed), a parked or queuing car at Ponttor whose position wobbles (60 m/s implied at median speed 0.6 m/s), slow urban Cologne cars with heading noise (heading_rate / pos_heading). Nothing looks like an attack; these are the real-world false-alarm sources. The 3 speeds > 70 m/s (163.82, 108.46 twice, one sender, Ponttor, train split) are left in and all alarm.
2. Acceptance range: geometry gate E1-E4: Mobile EXPLAINED; Stationary NOT explained as pre-registered (E2 1.81% far vs 2.14% near, 1% clause), EXPLAINED with the post-hoc E2prime (generation-time dt: far 0.00%); E1 frame, E3 no relay latency, E4 free-space link budget (+6.7 / +10.0 dB at 6.6 / 8.1 km) pass. Relay cannot be excluded from CAM content. Pooled 1% threshold = 3.5 km (Mobile) / 4.3 km (Stationary); test FA 0.74% / 0.49% of messages with a receiver position.
   It catches FarPosOffset (a spoofed position 5-20 km away): 68.7% of all injected Mobile rows (essentially every row that has an ego pose: 68% of Mobile test messages do) and 98.6% Stationary, where the 12 physics checks catch 1.0% / 0.5%; on the mean over the other types it adds +1.6 / +0.2 points (mean over types 1-11 and 13-19, which excludes FarPosOffset).
3. Sudden appearance NOT useful on real data: threshold = 1% of genuine evaluable first messages (Mobile validation has 29, Stationary 217); test false alarms 6.2% of 32 (Mobile) / 0.0% of 262; the physical 300 m design value alarms 62% / 40% of genuine first messages (urban fixed units and moving egos hear new vehicles close by). Injected ghosts 20-150 m from the receiver: 21.1% of 19 ghost tracks (Mobile), 0.0% of 98 (Stationary).
4. Injected VeReMi-taxonomy attacks on real CAMs (test recordings, B thresholds, scored rows, types with >= 50 scored rows): mean detection 77.3% Mobile, 80.0% Stationary (VeReMi physics-only on the same types 86.3% / 80.9%; Tampa seen-class mean 81.7%); all rows 68.8% / 66.5%; sender level (k=3) 90.2% / 86.9%.
   Caught (Mobile / Stationary, scored rows): RandomPos 100.0% / 100.0%, RandomPosOffset 100.0% / 100.0%, RandomSpeed 99.3% / 99.4%, Disruptive, DoSRandom, DoSDisruptive all >= 100.0%; ConstSpeed 82.2% / 87.4% (VeReMi 99.9%), DataReplay 77.6% / 94.9% (VeReMi 98.2%).
   NOT caught: DoS x2 6.4% / 9.0% (VeReMi 100%: the 1 Hz rate check is blind to an irregular real CAM stream; Tampa 6.4% as well), GridSybil 2.7% / 11.8% per message (sender level k=3 100% / 100%), ConstPosOffset 1.2% / 1.0%, EventualStop all rows 3.1% / 1.8% (its few scored rows are the stop jump itself), GhostNearReceiver 0.9% / 1.2%.
   Delay: a burst that keeps its content but arrives 3 s late is invisible to the 12 checks (1.1% / 1.1%) and caught 100% by the freshness check (relative latency age_s), at +1% budget (1.2% FA Stationary); a constant delay of every message is not detectable (clock offset).
5. Acceptance (rule in notes/WP5_v2x.md, written before any number): F1 MET; F2 MET (trivially); R1 Mobile explained; Stationary explained only with the amended E2prime; R2 MET; R3 NOT MET (appearance FA Mobile and ghost detection); I1 MET. Overall PARTIAL.
6. Sim-to-real: FA at the 1% budget holds after re-calibration (0.97%-1.15% vs VeReMi 1.1%, Tampa 3.0%), and the structure of what is caught agrees with VeReMi / Tampa for position and speed randomisation; rate-based and overlap-based detections (DoS, GridSybil) do not transfer to irregular real CAM rates; the VeReMi calibration itself does not transfer. Thresholds MUST be re-fitted per deployment (and per environment): this is the on-deployment regime the system architecture already assumes.

## Goal of the step
Run the frozen V2X physics-only stack (L1+L2+L3) on real V2AIX CAMs with the ego GNSS pose as receiver; implement and evaluate the deferred acceptance-range and sudden-appearance checks; inject the VeReMi-taxonomy attacks on real CAMs; compare with VeReMi and Tampa. Mobile and Stationary separately, thresholds on each one's own validation.

## Acceptance rule (written in notes/WP5_v2x.md on 2026-10-24 before any S3b number; amendments logged there)
F1 variant B FA per message <= 1.5% each environment and genuine senders at k val <= 3%; F2 (expectation) variant A FA > 2% in one environment; R1 geometry gate E1-E4 per environment before any acceptance-range calibration; R2 range FA <= 1.5%, FarPosOffset detection and value over physics reported; R3 appearance FA <= 2% of evaluable genuine first messages and ghost detection >= 50% in one environment; I1 mean scored-row detection of the types with >= 50 scored rows >= 60% in both environments; I2 honest sim-to-real comparison.

## What was done
- Code: v2x/l_rx.py (AcceptanceRange, AppearanceData, first-message flags), v2x/v2aix_inject.py (types 1-19 via v2x/attacks.py plus 12b DelayedBurst, 20 GhostNearReceiver, 21 FarPosOffset), v2x/v2aix_eval.py (raw scores with the reception clock for the cross-sender checks, variants A and B, rates), v2x/v2aix.py (+ column recv_s), tests/v2x/test_s3b.py (10 tests).
- Tools: tools/WP5_S3b_{cache,geometry,lib,clean,senders,inject,tables,report}.py. Results: results/WP5/s3b_{geometry,clean,top_senders,inject_Mobile,inject_Stationary,acceptance}.json and .md, s3b_tables.md; smoke runs on validation (plumbing) s3b_*_smoke.*; logs in results/WP5/logs/.
- Data: V2AIX (D13) 1,515 recordings with CAMs; splits by recording (splits_v2aix.json); test = 304 recordings (Mobile 4,338 msgs, Stationary 43,087). Test was scored once (clean run and injection run; the injection script crashed once on a NaN heading of an attacker before finishing and was re-run after the fix, no number was looked at or changed; the clean script was re-run once to add the distance / gap breakdown, identical scoring).
- Frozen stack = results/WP7/frozen_v2x (12 checks, VeReMi calibration, read only). Clock: per-track checks use the generation time, overlap and track_birth use the reception time per recording (generation times of different senders are 0-65 s apart).

## Results (copied from the JSON; long tables in results/WP5/s3b_tables.md and s3b_clean.md)

### Geometry gate (train + validation recordings)

| environment | E1 frame (ratio far) | E2 as pre-registered (far / near) | E2prime generation-time dt, post-hoc (far / near) | E3 relay (far age p99 vs 2 x near; recordings; top share) | E4 link margin | verdict pre-registered | verdict with E2prime |
|---|---|---|---|---|---|---|---|
| Mobile | PASS (0.999-1.045) | PASS (0.02% / 0.72%) | PASS (0.04% / 0.57%) | PASS (0.29 s vs 1.98 s; 4 rec; 37%) | PASS (+6.7 dB) | EXPLAINED | EXPLAINED |
| Stationary | PASS (0.997-0.999) | FAIL (1.81% / 2.14%) | PASS (0.00% / 0.24%) | PASS (1.78 s vs 3.36 s; 158 rec; 6%) | PASS (+10.0 dB) | NOT explained | EXPLAINED |

E1 frame, E3 latency and E4 link budget pass in both; the pre-registered E2 fails for Stationary only because it pairs the sender position (generation clock) with the reception-time difference (fixed unit: the ego pose is static, so no pose misalignment is possible; with the generation-time difference the violation share is <= 0.4% everywhere). The range check is therefore evaluated for both environments, the Stationary one flagged as passing the gate only with the amended E2prime. Caveats: relay / forwarding cannot be excluded (no RSSI or hop field in the data); the Mobile far-range evidence is 14 senders in 4 recordings (Highway, Rural). Plausible reading: 5.9 GHz clear-line-of-sight highway reception with a high-gain roadside antenna (free-space link budget positive up to ~8 km at the lowest data rate), short range at urban intersections (70-330 m).

### Real genuine traffic (test)

| environment | variant | FA per message [CI] | alarms per receiver-hour | alarm events per hour | genuine senders k=3 | genuine senders k val (k) |
|---|---|---|---|---|---|---|
| Mobile | A: frozen VeReMi calibration | 92.30% [87.97%, 97.17%] | 6676 | 177 | 89.1% (82/92) | n/a |
| Mobile | B: re-calibrated on V2AIX validation | 1.15% [0.50%, 1.93%] | 83 | 23 | 7.6% (7/92) | 0.0% (k=18) |
| Mobile | B + range OR appearance | 1.31% [0.58%, 2.22%] | 95 | 27 | 6.5% (6/92) | 1.1% (k=16) |
| Mobile | B + freshness | 1.15% [0.50%, 1.93%] | 83 | 23 | 7.6% (7/92) | 0.0% (k=83) |
| Stationary | A: frozen VeReMi calibration | 95.12% [92.16%, 96.77%] | 10740 | 96 | 87.1% (264/303) | n/a |
| Stationary | B: re-calibrated on V2AIX validation | 0.97% [0.61%, 1.51%] | 110 | 30 | 13.2% (40/303) | 1.0% (k=22) |
| Stationary | B + range OR appearance | 0.83% [0.54%, 1.31%] | 93 | 31 | 12.2% (37/303) | 0.3% (k=22) |
| Stationary | B + freshness | 2.12% [1.59%, 2.72%] | 240 | 52 | 23.4% (71/303) | 1.3% (k=38) |

More: per check, per location, by distance and by gap, flagged senders: results/WP5/s3b_clean.md; top senders described: results/WP5/s3b_top_senders.md.

### Injected attacks per type, test, B thresholds

Columns: scored = detection on rows with a moving predecessor (as M1); all rows includes first messages and exact repeats; L1 / L2 / L3 / fresh / range = message detection of that group alone at its own 1% budget; appear (tracks) = share of injected tracks whose first message alarms; VeReMi / Tampa = physics-only (L1+L2+L3) scored-row detection of the same type from reports/M1_V2X.md.

#### Mobile

| type | name | injected msgs | attackers | scored share | physics scored [CI] | physics all rows | sender k=3 | sender k val | L1 | L2 | L3 | fresh | range | appear (tracks) | physics+rx | VeReMi scored | Tampa scored |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ConstPos | 2854 | 32 | 0% | - | 92.8% | 100.0% | 93.8% (k=18) | 0.5% | 79.1% | 92.3% | 0.0% | 61.4% | 0.0% | 97.9% | - | - |
| 2 | ConstPosOffset | 2829 | 32 | 91% | 1.4% [0.5%, 2.9%] (n=2576) | 1.2% | 12.5% | 0.0% (k=18) | 0.5% | 1.4% | 0.4% | 0.0% | 0.8% | 0.0% | 1.6% | 0.8% | 3.9% |
| 3 | RandomPos | 2711 | 32 | 98% | 100.0% [100.0%, 100.0%] (n=2654) | 97.9% | 100.0% | 100.0% (k=18) | 0.5% | 97.9% | 97.9% | 0.0% | 1.7% | 0.0% | 97.9% | 100.0% | 100.0% |
| 4 | RandomPosOffset | 2044 | 32 | 97% | 100.0% [100.0%, 100.0%] (n=1992) | 97.5% | 100.0% | 100.0% (k=18) | 0.6% | 97.5% | 97.7% | 0.0% | 0.0% | 2.1% | 97.5% | 100.0% | 100.0% |
| 5 | ConstSpeed | 1774 | 32 | 89% | 82.2% [69.6%, 92.3%] (n=1580) | 81.7% | 93.8% | 84.4% (k=18) | 0.3% | 53.4% | 85.7% | 0.0% | 0.0% | 0.0% | 81.3% | 99.9% | 99.1% |
| 6 | ConstSpeedOffset | 1951 | 32 | 92% | 92.9% [85.2%, 97.1%] (n=1801) | 91.0% | 100.0% | 90.6% (k=18) | 0.1% | 60.8% | 91.9% | 0.0% | 0.0% | 0.0% | 90.9% | 99.8% | 99.4% |
| 7 | RandomSpeed | 2486 | 32 | 94% | 99.3% [98.7%, 99.6%] (n=2338) | 97.3% | 100.0% | 100.0% (k=18) | 0.2% | 96.1% | 91.8% | 0.0% | 0.9% | 0.0% | 97.4% | 100.0% | 100.0% |
| 8 | RandomSpeedOffset | 2708 | 32 | 90% | 91.4% [89.0%, 93.7%] (n=2426) | 89.8% | 100.0% | 96.9% (k=18) | 0.1% | 85.3% | 55.9% | 0.0% | 0.8% | 0.0% | 89.8% | 99.8% | 100.0% |
| 9 | EventualStop | 973 | 32 | 3% | 96.7% [90.3%, 100.0%] (n=30) | 3.1% | 0.0% | 0.0% (k=18) | 0.0% | 3.0% | 3.0% | 0.0% | 0.0% | 0.0% | 3.1% | 0.9% | 100.0% |
| 10 | Disruptive | 2443 | 32 | 98% | 100.0% [100.0%, 100.0%] (n=2382) | 97.7% | 100.0% | 100.0% (k=18) | 0.5% | 97.5% | 97.2% | 0.0% | 58.9% | 0.0% | 99.1% | 99.2% | 100.0% |
| 11 | DataReplay | 1856 | 32 | 92% | 77.6% [64.8%, 88.2%] (n=1708) | 75.5% | 100.0% | 78.1% (k=18) | 0.2% | 37.4% | 72.9% | 0.0% | 54.2% | 0.0% | 94.7% | 98.2% | 99.1% |
| 12 | DelayedMessages | 1544 | 32 | 62% | 94.4% [87.4%, 98.0%] (n=960) | 92.7% | 100.0% | 71.9% (k=18) | 0.1% | 58.9% | 92.3% | 0.0% | 0.9% | 0.0% | 93.0% | 100.0% | 47.6% |
| 13 | DoS | 4726 | 32 | 89% | 6.4% [2.9%, 8.3%] (n=4197) | 5.7% | 37.5% | 12.5% (k=18) | 9.2% | 5.9% | 0.5% | 0.0% | 0.0% | 0.0% | 5.5% | 100.0% | 6.4% |
| 14 | DoSRandom | 6308 | 32 | 98% | 100.0% [100.0%, 100.0%] (n=6203) | 98.3% | 100.0% | 100.0% (k=18) | 62.7% | 98.3% | 98.4% | 0.0% | 2.2% | 0.0% | 98.4% | 100.0% | 100.0% |
| 15 | DoSDisruptive | 8816 | 32 | 98% | 100.0% [100.0%, 100.0%] (n=8632) | 98.0% | 100.0% | 100.0% (k=18) | 42.7% | 97.9% | 97.7% | 0.0% | 84.4% | 0.0% | 99.9% | 100.0% | 100.0% |
| 16 | GridSybil | 16290 | 32 | 91% | 2.7% [0.7%, 4.6%] (n=14850) | 3.6% | 100.0% | 21.9% (k=18) | 0.1% | 2.6% | 2.1% | 0.0% | 0.8% | 0.0% | 4.1% | 76.1% | 39.1% |
| 17 | DataReplaySybil | 1775 | 32 | 95% | 83.2% [75.6%, 88.9%] (n=1692) | 79.7% | 100.0% | 81.2% (k=18) | 0.5% | 34.4% | 81.9% | 0.0% | 37.6% | 0.0% | 89.3% | 19.9% | 29.1% |
| 18 | DoSRandomSybil | 4372 | 32 | 22% | 100.0% [100.0%, 100.0%] (n=946) | 48.5% | 100.0% | 100.0% (k=18) | 0.1% | 21.6% | 54.4% | 0.0% | 2.1% | 0.1% | 48.7% | - | 100.0% |
| 19 | DoSDisruptiveSybil | 2894 | 32 | 23% | 99.9% [99.5%, 100.0%] (n=671) | 37.1% | 100.0% | 78.1% (k=18) | 0.2% | 24.5% | 51.4% | 0.0% | 69.3% | 0.0% | 83.1% | 100.0% | 96.5% |
| 12b | DelayedBurst | 1149 | 32 | 89% | 1.3% [0.0%, 3.3%] (n=1019) | 1.1% | 3.1% | 0.0% (k=18) | 0.1% | 1.2% | 0.4% | 100.0% | 0.0% | 0.0% | 0.7% | - | - |
| 20 | GhostNearReceiver | 1495 | 19 | 85% | 0.9% [0.0%, 1.2%] (n=1276) | 0.9% | 5.3% | 0.0% (k=18) | 0.0% | 0.8% | 1.2% | 0.0% | 0.0% | 21.1% | 0.9% | - | - |
| 21 | FarPosOffset | 2737 | 32 | 90% | 1.1% [0.1%, 2.5%] (n=2462) | 1.0% | 6.2% | 0.0% (k=18) | 0.6% | 1.0% | 0.4% | 0.0% | 68.7% | 0.0% | 68.8% | - | - |

Mean over the types with >= 50 scored rows (2, 3, 4, 5, 6, 7, 8, 10, 11, 13, 14, 15, 16, 17, 18, 19): physics scored-row detection 77.3%; physics + receiver layers 79.0%; all rows 68.8%; sender k=3 90.2%; sender k val 77.7%; VeReMi physics-only on the same types 86.3% (VeReMi seen-class mean 82.7%), Tampa seen-class mean 81.7%.

#### Stationary

| type | name | injected msgs | attackers | scored share | physics scored [CI] | physics all rows | sender k=3 | sender k val | L1 | L2 | L3 | fresh | range | appear (tracks) | physics+rx | VeReMi scored | Tampa scored |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | ConstPos | 21802 | 102 | 0% | - | 85.1% | 90.2% | 57.8% (k=22) | 0.7% | 89.9% | 89.4% | 1.0% | 17.1% | 0.5% | 92.6% | - | - |
| 2 | ConstPosOffset | 21335 | 102 | 93% | 1.0% [0.4%, 2.0%] (n=19935) | 1.0% | 13.7% | 2.0% (k=22) | 0.4% | 0.7% | 1.5% | 1.3% | 0.3% | 0.0% | 0.8% | 0.8% | 3.9% |
| 3 | RandomPos | 19798 | 102 | 99% | 100.0% [100.0%, 100.0%] (n=19619) | 99.1% | 100.0% | 95.1% (k=22) | 0.2% | 99.1% | 99.1% | 1.1% | 13.1% | 0.0% | 99.1% | 100.0% | 100.0% |
| 4 | RandomPosOffset | 22419 | 102 | 99% | 100.0% [100.0%, 100.0%] (n=22190) | 99.1% | 100.0% | 97.1% (k=22) | 0.7% | 99.0% | 99.0% | 1.4% | 0.5% | 0.0% | 99.1% | 100.0% | 100.0% |
| 5 | ConstSpeed | 22023 | 102 | 95% | 87.4% [81.6%, 92.6%] (n=20958) | 87.2% | 93.1% | 84.3% (k=22) | 0.5% | 34.9% | 91.7% | 1.3% | 0.2% | 0.0% | 86.5% | 99.9% | 99.1% |
| 6 | ConstSpeedOffset | 24637 | 102 | 94% | 84.6% [80.1%, 87.9%] (n=23192) | 84.4% | 95.1% | 77.5% (k=22) | 5.7% | 34.3% | 92.7% | 1.5% | 0.5% | 0.0% | 83.6% | 99.8% | 99.4% |
| 7 | RandomSpeed | 19511 | 102 | 95% | 99.4% [99.0%, 99.6%] (n=18581) | 98.4% | 100.0% | 93.1% (k=22) | 0.6% | 97.4% | 95.1% | 1.2% | 0.7% | 0.0% | 98.4% | 100.0% | 100.0% |
| 8 | RandomSpeedOffset | 20328 | 102 | 94% | 91.4% [89.0%, 93.1%] (n=19010) | 88.8% | 100.0% | 90.2% (k=22) | 3.6% | 89.0% | 68.1% | 1.1% | 0.5% | 0.0% | 88.2% | 99.8% | 100.0% |
| 9 | EventualStop | 11507 | 102 | 1% | 96.7% [91.8%, 100.0%] (n=90) | 1.8% | 4.9% | 1.0% (k=22) | 0.6% | 0.8% | 1.4% | 1.2% | 0.0% | 0.7% | 1.3% | 0.9% | 100.0% |
| 10 | Disruptive | 19952 | 102 | 99% | 100.0% [100.0%, 100.0%] (n=19754) | 99.2% | 100.0% | 98.0% (k=22) | 0.9% | 99.0% | 98.9% | 1.0% | 37.0% | 0.6% | 99.6% | 99.2% | 100.0% |
| 11 | DataReplay | 20390 | 102 | 97% | 94.9% [91.5%, 96.9%] (n=19819) | 92.9% | 96.1% | 75.5% (k=22) | 0.4% | 59.3% | 93.8% | 1.3% | 21.3% | 0.0% | 94.5% | 98.2% | 99.1% |
| 12 | DelayedMessages | 17238 | 102 | 61% | 77.5% [63.9%, 85.1%] (n=10544) | 74.3% | 70.6% | 43.1% (k=22) | 0.3% | 50.3% | 76.6% | 1.1% | 0.6% | 0.0% | 74.2% | 100.0% | 47.6% |
| 13 | DoS | 41084 | 102 | 94% | 9.0% [6.8%, 12.1%] (n=38449) | 9.3% | 77.5% | 42.2% (k=22) | 10.4% | 6.7% | 2.0% | 0.9% | 0.4% | 0.0% | 9.0% | 100.0% | 6.4% |
| 14 | DoSRandom | 85528 | 102 | 99% | 100.0% [100.0%, 100.0%] (n=84629) | 99.8% | 100.0% | 100.0% (k=22) | 77.6% | 98.9% | 98.9% | 1.1% | 14.8% | 0.0% | 99.8% | 100.0% | 100.0% |
| 15 | DoSDisruptive | 89724 | 102 | 98% | 100.0% [100.0%, 100.0%] (n=88338) | 99.8% | 100.0% | 100.0% (k=22) | 77.0% | 98.5% | 98.4% | 1.3% | 36.6% | 0.5% | 99.9% | 100.0% | 100.0% |
| 16 | GridSybil | 133116 | 102 | 94% | 11.8% [10.2%, 13.7%] (n=125663) | 11.8% | 100.0% | 67.6% (k=22) | 0.7% | 10.8% | 2.8% | 1.2% | 0.5% | 0.2% | 10.8% | 76.1% | 39.1% |
| 17 | DataReplaySybil | 22574 | 102 | 84% | 84.1% [79.7%, 87.0%] (n=19067) | 77.3% | 96.1% | 81.4% (k=22) | 0.7% | 45.1% | 79.3% | 1.5% | 56.6% | 0.0% | 88.9% | 19.9% | 29.1% |
| 18 | DoSRandomSybil | 46398 | 102 | 32% | 100.0% [100.0%, 100.0%] (n=15019) | 39.6% | 100.0% | 100.0% (k=22) | 0.2% | 32.4% | 43.2% | 1.0% | 14.0% | 0.0% | 42.1% | - | 100.0% |
| 19 | DoSDisruptiveSybil | 40328 | 102 | 31% | 99.9% [99.8%, 99.9%] (n=12413) | 40.6% | 100.0% | 96.1% (k=22) | 0.2% | 31.1% | 44.5% | 1.2% | 36.0% | 0.4% | 62.5% | 100.0% | 96.5% |
| 12b | DelayedBurst | 12111 | 102 | 94% | 1.0% [0.2%, 2.6%] (n=11357) | 1.1% | 8.8% | 1.0% (k=22) | 0.8% | 0.6% | 1.4% | 100.0% | 0.1% | 0.0% | 1.0% | - | - |
| 20 | GhostNearReceiver | 21859 | 98 | 95% | 1.0% [0.3%, 2.0%] (n=20687) | 1.2% | 20.4% | 3.1% (k=22) | 0.7% | 0.5% | 1.8% | 1.1% | 10.1% | 0.0% | 1.9% | - | - |
| 21 | FarPosOffset | 20603 | 102 | 92% | 0.5% [0.3%, 0.8%] (n=18922) | 0.5% | 13.7% | 0.0% (k=22) | 0.4% | 0.7% | 0.4% | 1.0% | 98.6% | 0.0% | 96.3% | - | - |

Mean over the types with >= 50 scored rows (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19): physics scored-row detection 80.0%; physics + receiver layers 80.3%; all rows 66.5%; sender k=3 86.9%; sender k val 76.5%; VeReMi physics-only on the same types 80.9% (VeReMi seen-class mean 82.7%), Tampa seen-class mean 81.7%.

### Ablation (mean scored-row detection over the types with >= 50 scored rows)

| configuration | Mobile | Stationary |
|---|---|---|
| L1 | 7.4% | 10.6% |
| L2 | 67.6% | 69.6% |
| L3 | 74.5% | 76.5% |
| physics | 77.3% | 80.0% |
| fresh | 0.0% | 1.2% |
| range | 19.1% | 13.2% |
| range_loc | 20.0% | 17.0% |
| appear | 0.0% | 0.0% |
| rx | 19.1% | 13.2% |
| physics+range | 79.0% | 80.3% |
| physics+fresh | 77.3% | 80.2% |
| physics+rx | 79.0% | 80.3% |

Detection of the receiver-aware types (all injected rows; appearance = share of ghost TRACKS whose first message alarms):

| env | type | range | range per location | appear (tracks) | physics | physics+rx | fresh | physics+fresh |
|---|---|---|---|---|---|---|---|---|
| Mobile | 20 GhostNearReceiver | 0.0% | 3.7% | 21.1% (19 tracks) | 0.9% | 0.9% | 0.0% | 0.9% |
| Mobile | 21 FarPosOffset | 68.7% | 68.7% | 0.0% (51 tracks) | 1.0% | 68.8% | 0.0% | 1.0% |
| Mobile | 12b DelayedBurst | 0.0% | 0.3% | 0.0% (42 tracks) | 1.1% | 0.7% | 100.0% | 100.0% |
| Mobile | 2 ConstPosOffset | 0.8% | 0.8% | 0.0% (51 tracks) | 1.2% | 1.6% | 0.0% | 1.2% |
| Mobile | 3 RandomPos | 1.7% | 2.8% | 0.0% (52 tracks) | 97.9% | 97.9% | 0.0% | 97.9% |
| Mobile | 4 RandomPosOffset | 0.0% | 0.4% | 2.1% (48 tracks) | 97.5% | 97.5% | 0.0% | 97.5% |
| Stationary | 20 GhostNearReceiver | 10.1% | 8.4% | 0.0% (98 tracks) | 1.2% | 1.9% | 1.1% | 2.3% |
| Stationary | 21 FarPosOffset | 98.6% | 98.0% | 0.0% (187 tracks) | 0.5% | 96.3% | 1.0% | 1.5% |
| Stationary | 12b DelayedBurst | 0.1% | 0.1% | 0.0% (147 tracks) | 1.1% | 1.0% | 100.0% | 100.0% |
| Stationary | 2 ConstPosOffset | 0.3% | 13.0% | 0.0% (182 tracks) | 1.0% | 0.8% | 1.3% | 2.2% |
| Stationary | 3 RandomPos | 13.1% | 31.3% | 0.0% (179 tracks) | 99.1% | 99.1% | 1.1% | 99.1% |
| Stationary | 4 RandomPosOffset | 0.5% | 10.1% | 0.0% (193 tracks) | 99.1% | 99.1% | 1.4% | 99.1% |

Acceptance: F1 MET (B FA 1.15% / 0.97%; genuine senders at k val 0.0% / 1.0%); F2 MET (A 92.3% / 95.1%); R1 Mobile explained; Stationary explained only with the amended E2prime; R2 MET; R3 NOT MET (appearance FA 6.2% of 32 Mobile, 0.0% of 262 Stationary; ghost tracks detected 21.1% / 0.0%); I1 MET (77.3% / 80.0%; Stationary mean includes EventualStop at 96.7% of only 90 scored rows, i.e. the stop jump; without it the mean is lower by about 1 point); I2 written below. Overall PARTIAL.

## Sim-to-real comparison (honest)
- False alarms: VeReMi test 1.1% of messages (0.9% scored rows, simulated, 1 Hz); Tampa test 3.0% (10 Hz BSM, 3 vehicles, RSU receivers); V2AIX B 1.15% / 0.97%. With the budget fitted on the deployment itself the rate is held; with the foreign (VeReMi) calibration it is 92% / 95%.
- Detection (physics-only, scored rows, same types): VeReMi 86.3% (types of the Mobile mean) / 80.9% vs V2AIX 77.3% / 80.0%. Same ordering of easy and hard attacks as in VeReMi and Tampa (random / offset position and speed, Disruptive, DoSRandom caught; ConstPosOffset and EventualStop not; Sybil only at sender level).
- Differences, with the likely reason (not tested separately): ConstSpeed and DataReplay are lower on real traffic because real speeds span 0-45 m/s so a constant 15-35 m/s is often plausible and real tracks are noisier (pos_sigma 2.8 m, speed vs position mismatch p99 12.9 m/s, so the thresholds are wider); DoS x2 and GridSybil collapse because they were found in VeReMi through the beacon rate and simulated overlaps; the irregular real CAM interval (median 0.35 s, 0.1-1 s) makes a doubled stream look normal; Tampa shows the same collapse for DoS (6.4%). The injected attacks are synthetic on real messages: they say what the checks can see, not how real attackers behave.
- Not comparable number-to-number: different splits (recording vs time block vs vehicle), different traffic (Aachen region, passenger cars, ITS-G5 CAM), 3 test vehicles in Tampa, confidence intervals here are cluster bootstraps over test recordings (Mobile 76 recordings with 92 senders: wide).

## Problems, surprises, open questions
1. The VeReMi-calibrated stack is unusable on real CAMs (92-95% FA): the first thing a deployment must do is re-calibrate on its own genuine traffic; rate and range thresholds especially.
2. The pre-registered E2 was defective for fixed units (see notes/WP5_v2x.md, 2026-10-24 amendments). Supervisor decision needed: accept the Stationary acceptance-range evaluation (done, flagged) or declare it not evaluable on the pre-registered gate.
3. Radio range km-scale is explained only by geometry consistency and link budget; relay is not excludable from the data. The range threshold is 'what was ever heard' on 1,515 recordings, not a standard; it catches only very far claims (> a few km). Small injected offsets (50-300 m) are invisible to it, as is ConstPosOffset: still needs WP6 witnesses (LiDAR / GPS).
4. Sudden appearance: premise (a real vehicle enters at the edge of range) does not hold at urban fixed units (range 70-330 m, corners) or in 2-3 s Mobile clips (29 / 217 evaluable genuine first messages in validation, 32 / 262 in test, Mobile / Stationary); evaluable first messages are few, so its 1% budget is crude. Not recommended for the real-data stack.
5. Genuine senders at k=3 alarms: 7.6% / 13.2% (M1 VeReMi 11.3%): the validation-chosen k is the usable sender rule; with 92 test senders in Mobile the sender-level numbers have wide uncertainty.
6. Freshness (age_s) is not in the frozen VeReMi stack; V2AIX has relative latency only. It catches a latency step 100% at +1% budget; it cannot catch a constant delay. Whether to add it to the V2X domain for WP7 is a supervisor decision.
7. The EventualStop scored-row figure (97% of 30-90 rows) is the stop jump, not detection of the stopped vehicle (only a few % of its rows are scored; the rest are exact repeats of the stopped position): read the all-rows column.
8. Licence: no data, cache or per-message file committed; caches (../data_extra/D13_v2aix/cache) are ~100 MB.

## Proposed next step (or changes to the plan)
WP5 stays PARTIAL. The frozen V2X domain for WP6 / WP7 should be the VeReMi-recipe stack with deployment-fitted thresholds (variant B), optionally + range (+1.6 / +0.2 points) and + freshness for messages that carry an age; WP7 should treat 'calibrate on the first genuine hour at the receiver' as part of installation. If more real days are wanted: V2AIX full dataset (21 GB) would add Mobile hours (only 0.6 receiver-hours in test), the main weakness of the Mobile numbers.