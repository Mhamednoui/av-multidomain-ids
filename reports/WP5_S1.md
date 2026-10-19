# WP5 S1: Data layer (unified messages, VeReMi class map, splits, injection)

Date: 2026-10-19    Worker: sonnet

## Goal of the step
Unified V2X message format with adapters (VeReMi, Tampa, V2AIX stub), group splits, and VeReMi-taxonomy misbehaviour injection on real BSMs. D13 V2AIX is not available (user must request access): its adapter is a stub raising `DataNotAvailableError`; no fake data.

## Acceptance rule (notes/WP5_v2x.md, section 'S1 Data layer: acceptance rule', written before any S1 result)
1 schema + adapters + tests; 2 class map checked against a primary source if reachable AND the data (class 1 >= 80% senders pos std < 1 m; class 5 >= 80% speed std < 0.1; classes 13-15 rate >= 2x genuine); 3 split with zero sender overlap, every class in each part, leakage written down; 4 Tampa split by vehicle + 19 injected attacks with equations and physical unit tests; 5 tests pass.

## What was done
- `v2x/schema.py` (columns, units, validate, class names), `v2x/adapters.py` (VeReMi, Tampa, V2AIX stub), `v2x/splitting.py`, `v2x/attacks.py` (injection, equations in its docstring and below).
- `tools/WP5_S1_build.py` (evidence, splits, summaries), `tools/WP5_S1_report.py` (this file), tests `tests/v2x/test_adapters_splits.py`, `tests/v2x/test_attacks.py` (25 tests).
- Results: `results/WP5/s1_classmap_evidence.json`, `splits_veremi.json`, `splits_tampa.json`, `s1_split_info.json`, `s1_injection_summary.json`, `s1_adapters.json`.

### Unified message schema
`msg_id, source, sender, pseudo, track, t, x, y, speed, vx, vy, heading, acl, yaw_rate, pos_sigma, spd_sigma, acl_sigma, rx_id, rx_x, rx_y, lat, lon, label, attack, injected`. SI units; x, y metres (local East-North); heading radians, 0 = East, counter-clockwise; acl along the heading; yaw_rate counter-clockwise rad/s; `track` = one continuous stream to be processed with state (sender/pseudonym for VeReMi, vehicle/segment for Tampa, new segment after a gap > 5 s). `sender` is the physical emitter (group for splits), `pseudo` the claimed identity. NaN where a source lacks a field (VeReMi: yaw_rate, receiver, lat/lon; Tampa: sigmas, receiver position, because RSU positions are unknown).

Adapters: VeReMi 3,194,808 messages, 24,663 senders, 119,285 tracks. Tampa 34,453 messages after removing duplicates heard by two RSUs, 226 vehicle ids, 353 tracks. Tampa generation time = secMark (10 Hz BSMs, 0.1 s steps) combined with the RSU record time (record time is only 1 s resolution, so absolute time has about 1 s uncertainty; relative time inside a vehicle is exact).

## VeReMi class map: evidence
Primary source: NOT reached (GitHub josephkamel/VeReMi-Extension and F2MD raw files returned 404 / no list; a web search found only the original VeReMi paper with 5 attackers). The map below is the supervisor's (Kamel et al. 2020 ordering), checked on the data only. The class names are therefore 'consistent with the data', not 'confirmed by the authors'.

Pre-registered checks:

- class1_ConstPos_frac_pos_std_lt_1m_ge_0.8: PASS
- class5_ConstSpeed_frac_speed_std_lt_0.1_ge_0.8: PASS
- class13_rate_ge_2x: PASS
- class14_rate_ge_2x: PASS
- class15_rate_ge_2x: PASS

Additional qualitative checks (not pre-registered thresholds):

- class9_EventualStop_majority_stopped: PASS
- class3_RandomPos_jump_gt_100m: PASS
- class7_RandomSpeed_speed_std_gt_2x_genuine: PASS
- class16_GridSybil_gt_1_pseudonyms_and_rate_gt_4x: PASS
- classes17_18_19_many_pseudonyms: PASS
- class10_Disruptive_jump_gt_100m: PASS
- class11_DataReplay_implied_speed_mismatch_gt_5: PASS
- class12_DelayedMessages_majority_stopped_or_zero_start: PASS
- class6_8_speed_offset_mean_speed_gt_genuine: PASS

Per class (senders with >= 5 messages), from `s1_classmap_evidence.json`:

| id | name | senders | frac pos std<1m | frac speed std<0.1 | rate / genuine | median jump m | frac msgs stopped | pseudonyms/sender |
|---|---|---|---|---|---|---|---|---|
| 0 | Genuine | 17138 | 0.00 | 0.00 | 1.00 | 12.3 | 0.10 | 1 |
| 1 | ConstPos | 386 | 1.00 | 0.00 | 1.00 | 0.0 | 0.10 | 1 |
| 2 | ConstPosOffset | 387 | 0.00 | 0.00 | 1.00 | 12.3 | 0.09 | 1 |
| 3 | RandomPos | 389 | 0.00 | 0.00 | 1.00 | 765.8 | 0.10 | 1 |
| 4 | RandomPosOffset | 388 | 0.00 | 0.00 | 1.00 | 36.7 | 0.11 | 1 |
| 5 | ConstSpeed | 389 | 0.00 | 1.00 | 1.00 | 12.3 | 0.00 | 1 |
| 6 | ConstSpeedOffset | 385 | 0.00 | 0.00 | 1.00 | 12.4 | 0.00 | 1 |
| 7 | RandomSpeed | 383 | 0.00 | 0.00 | 1.00 | 12.4 | 0.00 | 1 |
| 8 | RandomSpeedOffset | 388 | 0.00 | 0.00 | 1.00 | 12.3 | 0.00 | 1 |
| 9 | EventualStop | 387 | 0.15 | 0.02 | 1.00 | 0.0 | 0.72 | 1 |
| 10 | Disruptive | 388 | 0.00 | 0.00 | 1.00 | 320.6 | 0.11 | 1 |
| 11 | DataReplay | 389 | 0.00 | 0.00 | 1.00 | 14.6 | 0.11 | 1 |
| 12 | DelayedMessages | 388 | 0.17 | 0.17 | 1.00 | 0.0 | 0.66 | 1 |
| 13 | DoS | 390 | 0.00 | 0.00 | 2.00 | 0.0 | 0.10 | 1 |
| 14 | DoSRandom | 388 | 0.00 | 0.00 | 4.00 | 768.5 | 0.00 | 1 |
| 15 | DoSDisruptive | 388 | 0.00 | 0.00 | 4.00 | 262.7 | 0.11 | 1 |
| 16 | GridSybil | 387 | 0.00 | 0.00 | 6.00 | 11.7 | 0.16 | 6 |
| 17 | DataReplaySybil | 385 | 0.00 | 0.00 | 1.00 | 8.2 | 0.12 | 58 |
| 18 | DoSRandomSybil | 387 | 0.00 | 0.00 | 2.00 | 765.0 | 0.00 | 100 |
| 19 | DoSDisruptiveSybil | 387 | 0.00 | 0.00 | 2.00 | 346.2 | 0.11 | 100 |

Reading: class 1 constant position, 5 constant speed, 3 / 14 / 18 teleporting positions, 7 / 14 / 18 random speeds, 9 stops (72% of messages with speed < 0.1), 10 / 15 / 19 jumps between other vehicles' places, 13 / 14 / 15 send 2x / 4x / 4x the genuine rate (genuine = 1.0 Hz in this data), 16 sends 6x with 6 pseudonyms (attacker + 5 ghosts), 17 / 18 / 19 use dozens of pseudonyms. Class 12 (DelayedMessages) is only weakly confirmed: its senders begin with (0, 0) placeholders (66% of messages have speed 0), which is what a delay queue not yet filled looks like, then follow plausible tracks; the delay itself cannot be seen without ground truth. Classes 2, 4, 6, 8 (offsets) cannot be confirmed individually without the true position / speed: only that they differ from genuine (class 4 jumps of 36.7 m, classes 6 / 8 higher mean speed than genuine). Class 2 (constant offset) is statistically indistinguishable from genuine in this CSV; it needs map or cross-vehicle checks. Rates: the original paper's DoS is 10x; this combined CSV shows 2x for class 13, so the CSV is a (possibly thinned) variant: our injection uses the measured factors.

## Split

**VeReMi: no simulation id and no receiver id exist in the combined CSV.** What the data shows: one 24 h timeline (t = 241..86400 s) with no time reset or large gap (max gap in the whole stream 353 s), each sender has one class (max classes per sender = 1) and a short life (median ~110 s), sender ids grow with departure time (Spearman 1.000000). Separate runs cannot be recovered. Best grouping available: time blocks of 1800 s (48 blocks), shuffled 60/20/20 with seed 42; a sender whose life crosses a block end is dropped (guard): 1431 of 24663 senders (5.8%, attackers and genuine alike; per class in s1_split_info.json). No sender of one part is alive at the same time as a sender of another part (checked in the data: 0 for train-val, train-test, val-test).

| part | senders | messages | genuine senders | senders per attack class (min..max) |
|---|---|---|---|---|
| train | 15578 | 1980937 | 10902 | 239..252 (19 classes) |
| val | 2121 | 267553 | 1486 | 31..37 (19 classes) |
| test | 5533 | 718851 | 3873 | 83..90 (19 classes) |

Leakage risk, honestly: (i) all parts come from the same simulated city and the same day, so road geometry is shared (genuine tracks of the test period follow roads that train tracks also used); (ii) blocks that are neighbours in time are in different parts, separated only by the guard (no coexistence, but similar traffic density); (iii) the attack parameters (offset ranges, fixed positions) are the same simulation configuration in every part, so a supervised model sees the same attack generator in test; (iv) 1 pseudonym id is shared between two senders (negligible). Consequence: VeReMi test numbers are an upper bound on generalisation; the Tampa injection test and the held-out attack types below are the stricter checks.

Tampa: split by vehicle id (60/20/20, seed 42), `results/WP5/splits_tampa.json`:

| part | vehicles | messages | eligible attackers (>= 50 msgs) |
|---|---|---|---|
| train | 136 | 21092 | 74 |
| val | 45 | 4491 | 21 |
| test | 45 | 8870 | 20 |

The J2735 temporary id may rotate, so one physical car could appear under two ids in two parts (cannot be checked; small risk). Only 20 eligible vehicles in test: per-attack-type numbers in S6 will be noisy (10 attackers per type); confidence intervals must be reported. Attack types held out of any supervised training in S5 (decided now): [6, 12, 17] (ConstSpeedOffset, DelayedMessages, DataReplaySybil).

## Injection on real Tampa BSMs
A scenario = the vehicles of one split; a random half of the eligible vehicles become attackers of ONE attack type for their whole life; the others stay genuine and are the only source of replayed / disruptive content (no cross-split leakage). Label = attack id for every falsified message, 0 otherwise. Notation: p_i = (x_i, y_i) claimed position, v_i speed, h_i heading, u_i = (cos h_i, sin h_i), n_i = (-sin h_i, cos h_i). An attacker can choose any content it transmits, but not the true motion of its car, not past transmissions, and not other vehicles' radio identities (only pseudonyms it generates itself).

| id | name | physical description | test attackers | attacker msgs / genuine msgs |
|---|---|---|---|---|
| 1 | ConstPos | p_i' = P, P a position where another real vehicle was seen; speed / heading stay true | 10 | 1.00 |
| 2 | ConstPosOffset | p_i' = p_i + d, d fixed, |d| ~ U(100, 300) m, random direction | 10 | 1.00 |
| 3 | RandomPos | p_i' ~ U(bounding box of the split's traffic), fresh every message | 10 | 1.00 |
| 4 | RandomPosOffset | p_i' = p_i + r_i (cos a_i, sin a_i), r_i ~ U(50, 300) m, a_i ~ U(0, 2 pi) | 10 | 1.00 |
| 5 | ConstSpeed | v_i' = c ~ U(15, 35) m/s, velocity = v_i' u_i, acl = 0, position true | 10 | 1.00 |
| 6 | ConstSpeedOffset | v_i' = v_i + c, c ~ U(5, 15) m/s | 10 | 1.00 |
| 7 | RandomSpeed | v_i' ~ U(0, 35) m/s fresh every message | 10 | 1.00 |
| 8 | RandomSpeedOffset | v_i' = v_i + U(0, 10) m/s | 10 | 1.00 |
| 9 | EventualStop | from message k (30-60% of the life): p_i' = p_k, v' = 0, acl = 0, yaw = 0; earlier messages genuine (label 0) | 10 | 1.00 |
| 10 | Disruptive | kinematics of message i replaced by a random message of another vehicle, own timestamp | 10 | 1.00 |
| 11 | DataReplay | kinematic sequence of one other vehicle replayed in order on the attacker's own timestamps (exact copy) | 10 | 1.00 |
| 12 | DelayedMessages | state sent at t is the attacker's own state at t - D, D = 3 s; the first 3 s cannot be sent (queue empty) | 10 | 0.97 |
| 13 | DoS | rate x2: extra messages at t_i + j dt/2 with p = p_i + v_i (t' - t_i) (constant-velocity extrapolation of the true state) | 10 | 2.00 |
| 14 | DoSRandom | rate x4, RandomPos + RandomSpeed content | 10 | 4.00 |
| 15 | DoSDisruptive | rate x4, Disruptive content | 10 | 4.00 |
| 16 | GridSybil | 5 ghost pseudonyms at p_i + f u_i + l n_i, (f, l) in {(15,0), (-15,0), (0,3.5), (15,3.5), (-15,3.5)} m, same speed / heading; total rate x6 | 10 | 6.00 |
| 17 | DataReplaySybil | as 11, new pseudonym each time the replayed victim changes (every 50 messages) | 10 | 1.00 |
| 18 | DoSRandomSybil | rate x2, random position and speed, pseudonym drawn from 100 per message | 10 | 2.00 |
| 19 | DoSDisruptiveSybil | rate x2, Disruptive content, pseudonym drawn from 100 per message | 10 | 2.00 |

What a real attacker could not do and we do not model: change the true trajectory (so 'claimed vs true' inconsistency is the only handle), forge a valid certificate for a ghost (pseudonyms assumed to be obtainable, as in VeReMi), or know the receiver position (hence no 'sudden appearance' injection in S1: Tampa RSU positions are not in the public sample; it can be added in S2/S3 if the receiver is taken as the RSU centroid). Rate factors are those measured in the VeReMi CSV (not the 10x of the original paper). Unit tests (`tests/v2x/test_attacks.py`) check, per attack: constant / offset / range of the falsified field, that untouched fields stay true, velocity = speed * heading (speed attacks), eventual-stop label boundary, replay equals the victim's sequence exactly, delayed lag = v * 3 s, DoS message count = k x genuine and consistency with constant-velocity motion, Sybil ghosts keep constant relative offset and zero relative speed, pseudonym counts, timestamps never go backwards in a track, determinism, and that other vehicles stay unchanged and no vehicle outside the split is used.

## Results (from the JSON files)
Acceptance 1 (schema, adapters, tests): MET (25 v2x tests pass). 2 (class map): all 5 pre-registered data checks PASS; primary source NOT reached, so names are 'consistent with the data' (class 12 weakest, offsets 2 / 4 / 6 / 8 unprovable without truth). Recorded as PARTIALLY VERIFIED. 3 (split): MET with the time-block grouping (zero sender overlap, no coexistence in time, every class in every part). Runs could NOT be recovered. 4 (Tampa split + injection + physical tests): MET. 5: MET.

Overall S1: MET for D12 + D14; V2AIX adapter is a stub (D13 pending user action).

## Problems, surprises, open questions
- No primary source for the class map could be fetched; if the supervisor or user has the VeReMi Extension paper (ICC 2020, Table of attacks) please confirm the ids, in particular 12 and 17-19.
- VeReMi combined CSV: 1 Hz messages, no receiver, no run id; received-power / acceptance-range checks (S3) cannot be done on it; the original per-receiver logs or VeReMi NextGen (D25) would be needed.
- Tampa public sample: one day, 20 eligible test vehicles; injected results will have wide intervals.
- Tampa messages are 10 Hz, VeReMi 1 Hz: layers must use time-based (not message-count) windows.

## Proposed next step
S2 (L1 message checks) on the train / val / test splits above. Question for the user: submit the V2AIX request form so the CAM adapter can be implemented.
