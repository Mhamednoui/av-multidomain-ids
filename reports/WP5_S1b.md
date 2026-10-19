# WP5 S1b: Tampa deduplication, id linking, time-block re-split, S2 + S3 Tampa rerun

Date: 2026-10-20    Worker: sonnet (medium)

## Goal of the step
Supervisor decision 2026-10-20: coreData_id is per RSU, so the S1 split by id leaks and messages are double counted. Deduplicate the copies, link ids into physical vehicles, re-split Tampa by time block with buffers (VeReMi policy), re-inject the attacks, rerun the Tampa evaluations of S2 (v2x/l1.py) and S3 (v2x/l2.py) unchanged in method, map_road outside the deployable union, and report old vs new.

## Acceptance rule (notes/WP5_v2x.md, 'S1b ... acceptance rule' and its two AMENDMENTS, all written before any detection result)
(1) dedup rule measured and justified, linking with controls, split with guard and automatic checks; (2) false alarms on genuine test messages <= 2% for every deployable Tampa check and union, physical limits <= 0.1%; (3) old vs new tables from the JSON; (4) unit tests pass. Amendment 1 (after seeing the structure of the linked data): episode blocks instead of a fixed grid, smaller eligibility criteria. Amendment 2 (after the first split draw, before any detection run): episodes that contain the same physical vehicle are merged, so no vehicle is on two sides.

## What was done
- `v2x/tampa_link.py` (new): dedup, tier-1 / tier-2 linking, passages. `v2x/adapters.py`: `load_tampa()` is now the deduplicated passage table (default for all later steps); `load_tampa_v1()` keeps the old behaviour for the record. `v2x/splitting.py`: `tampa_episodes`, `tampa_time_block_split`, `min_gap_between_parts`.
- `tools/WP5_S1b_build.py` (dedup / linking / controls / old-split leakage / new split), `tools/WP5_S1b_rerun.py` (S2 + S3 Tampa on the new split; `--legacy` = same code on the old data and old split with map_road outside the union), `tools/WP5_S1b_report.py` (old vs new tables). `tools/WP5_S2_l1.py`, `tools/WP5_S3_l2.py`: the Tampa data file / loader are now module settings (default = new), S3 gets a "soft layer" notion (map_road scored and reported alone, not in the union or combiner). Methods in `v2x/l1.py`, `v2x/l2.py`, `v2x/attacks.py` are untouched. `tools/WP5_S1_build.py` and `tools/WP5_S3_diag.py` now call `load_tampa_v1`.
- `tests/v2x/test_tampa_link.py` (7 tests) + adapter tests updated: full suite 131 passed.
- Runs: one smoke run with the validation part standing in for test (files deleted), then ONE test run on the new split (`results/WP5/logs/s1b_v2_run1.log`) and one same-method run on the old split (`s1b_v1same_run1.log`). No re-tuning, no re-drawing after any detection result.

## Results

### 1. Duplicates (results/WP5/s1b_dedup_link.json)
- 34,464 rows are only 19,527 distinct over-the-air messages: 43.3% of the rows are copies (mean 1.76 copies per message; 8,661 messages heard by more than one RSU; up to 10 copies). The old S1 table counted 34,453 messages.
- Matching rule: same (msgCnt, generation time to the ms, lat, long, speed, heading). Checks: no id appears twice in a key; among the 8,661 (msgCnt, time) groups with several ids, 0 have different content, so putting content in the key never splits a true copy; the tolerance variant (|dt| <= 2 ms, position <= 1 m, speed <= 0.1 m/s, heading <= 1 deg, different id) finds 0 additional merges (0.0% of the messages; bound was 1%). A chance collision of two different vehicles on (msgCnt, ms of the minute, exact lat / long) is negligible.
- The kept copy is the one received first; its receive time gives age_s for the freshness layer.

### 2. Physical vehicles (linking)
- 226 ids -> 48 components (tier 1, certain: ids that share a bit-identical message; largest component 32 ids, 16 RSUs) -> 38 physical vehicles after 10 tier-2 links -> 40 passages (a silence > 120 s starts a new passage; 27 passages have >= 50 messages).
- msgCnt is a per-vehicle counter: inside tier-1 components 99.4% of consecutive pairs advance by 10 per second within +-1, so it survives an id change and is used as a linking cue together with position, speed and heading.
- Tier 2 (confidence high, not certain): unique mutual continuity candidate, gap <= 5 s. Positive control on real data (192 random cuts of tier-1 vehicles with 0.5-5 s holes, matched among all other components): 128 re-linked correctly, 0 wrong links (95% upper bound on the wrong-link rate about 2.3%), 64 missed (recall 67%), 0 ambiguous. Negative control (msgCnt shuffled): 0.23 links on average (max 1) against 10 real links. 3 ambiguous candidate pairs (fragments of 1-2 messages) were left unlinked. A missed link only splits one vehicle into two passages.
- So the sample contains 38 physical vehicles, not 226. One bus (V027) is 24% of all messages.

### 3. How much the old split leaked (measured)
- 33.0% of the distinct messages were heard under ids of more than one old part. 68.0% of the old TEST rows (6,033 of 8,870) had a bit-identical copy under a train or val id: 67.5% in train, 1.5% in val. Inside the old test part itself the 8,870 rows are only 6,820 distinct messages (23% double counted).
- 23 of 38 physical vehicles had ids in more than one old part; 39 of the 45 old test ids (87%, 92% of old test rows) belonged to vehicles that also own ids in train or val.

### 4. New split (results/WP5/splits_tampa_v2.json, s1b_split_info.json; old splits_tampa.json kept)
- Unit = passage; blocks = 11 episodes (cuts only where the whole corridor is silent for >= 60 s = 2 x 30 s guard; nothing is dropped; the VeReMi fixed grid would have dropped the biggest bus); episodes holding the same vehicle merged. Shuffled 60/20/20 with common.config.SEED as the first seed: seeds 42-47 failed the pre-registered size criteria (shares / eligible passages), seed 48 is the first that passes and is used as is.
- train 30 passages (13,200 messages, 19 eligible), val 6 (2,094, 4), test 4 (4,225, 4). Time gap between parts: train-val 801 s, train-test 2,042 s, val-test 79 s (required >= 60 s). 0 shared passages, 0 physical vehicles in two parts, all 19 types present in train / val / test (attackers per type 10 / 2 / 2). Held-out types 6, 12, 17 unchanged.
- The test part is 3 physical vehicles (V000 with two passages, V002, V003) with 2 attackers per type. Validation has 2,094 genuine messages, so a 1% budget is 21 messages.

### 5. Acceptance
| item | result |
|---|---|
| 1 dedup rule + linking with controls + split checks | MET |
| 2a physical limits <= 0.1% on genuine val and test | MET (0.000% everywhere) |
| 2b FA <= 2% on genuine test messages, every deployable check and union | NOT MET for one check: heading_rate 2.7% (CI 1-5%). L2 union 1.8%, L1+L2 union 1.8%, combined 1.7%, all other checks <= 1.4%. Not retuned. |
| 3 old vs new tables from the JSON | MET (below and results/WP5/s1b_compare.json) |
| 4 tests | MET (131 passed) |

S1b: PARTIAL (only the heading_rate FA bound missed, on a validation set of 2,094 messages).

### 6. Old vs new, in plain words
Columns in the tables: old = S2 / S3 as reported (map_road inside the L2 union); v1same = same code on the OLD data and split, map_road outside the union; new = deduplicated passages and the new split, map_road outside the union.

- The map_road decision explains most of the old headline: old L1+L2 union 54.4% mean detection at 7.6% FA (6.7% harness combined); without the map, on the same old data, 47.4% at 2.3% FA. About 7 points of the old detection were bought with 3x the false-alarm budget.
- New (deduplicated, clean split): L1+L2 union 44.7% mean detection at 1.8% FA, harness combined 45.1% at 1.7%. From v1same to new: -2.7 points of detection, FA 2.3% -> 1.8%.
- The leak had little effect on the S2 / S3 numbers themselves, because those layers are thresholds fitted on validation only (nothing is trained on train): only 1.5% of old test rows had an identical copy in val. The rest of the leak (67.5% of old test rows with a copy in train, 87% of old test ids from vehicles that also have ids in train / val) matters for the learned layers (S4 tracker, S5 supervised model) and for the replay / disruptive pools, which must use splits_tampa_v2.json. I cannot give one number for "inflation of S2/S3": the differences between v1same and new mix the removal of the leak with a completely different and much smaller evaluation set (3 test vehicles instead of 45 ids).
- Per type, large moves in both directions (L1+L2 union, v1same -> new): ConstSpeed 42.9 -> 3.5, ConstSpeedOffset* 13.1 -> 3.5, DataReplaySybil* 22.6 -> 5.1, ConstPos 10.5 -> 10.4, DoS 7.2 -> 10.9, DoSRandomSybil 47.9 -> 57.8, DataReplay 3.6 -> 8.1. With 2 attackers per type and 3 test vehicles these moves are within what a different sample can do; they are not evidence of the leak alone. The bootstrap CIs over 2 attackers in the tables are NOT valid intervals (nearly degenerate): do not quote them.
- Unchanged by the new data: DoSRandom and DoSDisruptive 99.8-99.9%, RandomPos / RandomPosOffset ~99.7%, RandomSpeed 96%, Disruptive 97.7%, stale replay (S20) 100% (L1 freshness); falsification with plausible values (EventualStop, GridSybil, DelayedMessages, DataReplay) stays below 11%.
- Pre-registered expectation (new FA >= old FA for the data-driven checks): true for pos_speed 0.2 -> 0.5, pos_heading 0.8 -> 1.4, implied_speed 0.2 -> 0.5, heading_rate 0.9 -> 2.7, yaw 0.6 -> 1.2, L2 union 1.0 -> 1.8; not true for beacon rate and freshness (0.0%), speed_change and accel (about equal). Partly as expected.
- map_road as a soft layer: FA 7.8% on genuine test messages (CI 0-19%); detects ConstPosOffset 62%, RandomPos 63%, RandomPosOffset 70%, DataReplaySybil 60% (old/v1same: FA 5.5%, 37 / 47 / 44 / 22%). It stays out of the deployable union; "L1+L2 union OR map_road" has FA 9.1% (reported only).
- Ablation (harness, AUC / detection at 1% / FA): L1 0.671 / 21.1% / 0.5%, L2 0.764 / 47.2% / 1.8%, L1+L2 0.798 / 48.7% / 1.7% (v1same 0.629 / 18.4%, 0.735 / 48.0%, 0.756 / 46.6%; old with map 0.754 / 52.6% / 6.3%, 0.781 / 53.3% / 6.7%). Best single layers on the new data: pos_speed 0.751 / 43.3%, implied_speed 0.669 / 39.7%, accel_consistency 0.672 / 37.3%, speed_change 0.643 / 36.9%. Leave-one-out: removing pos_speed hurts most (AUC 0.764 vs 0.798), then beacon_rate (0.781), field_ranges (0.789), overlap (0.790).
- Sender level: 3 of the 4 genuine test passages have >= 3 alarms in the L1+L2 union (75%; old 35.6% of 45 ids). A per-message 1% budget does not control per-vehicle false alarms. Reported as a failure of this view, not retuned.

## Problems, surprises, open questions
1. The public Tampa sample is far smaller than S1 suggested: 38 physical vehicles, 19.5k distinct messages, one day, one bus = 24%. After a clean split the Tampa test has 3 vehicles and 2 attackers per type. Tampa numbers are now an illustration, not a statistic. Request for the user: the fuller ITS DataHub Sandbox Tampa data (several days) would fix this.
2. heading_rate misses the 2% FA bound (2.7%); the checks are calibrated on only 21 validation messages per 1%. A larger validation part is the cure, not a retune.
3. DATASETS.md row D14 should say "226 ids = 38 physical vehicles" (shared file, not edited by me).
4. Tier-2 linking recall is 67% on the control; a missed link splits a vehicle into two passages. Residual risk: a vehicle whose passages were never linked could sit on two sides; the only unresolved candidates were 3 ambiguous pairs of 1-2 message fragments.
5. The overlap check is now global (rx_id is NaN after dedup; the same-receiver restriction of S3 existed only because of the copies). Genuine overlap FA: val 0.19%, test 0.0%.
6. The first split draw (episodes only, seed 42) left bus V027 in train and val; replaced by the vehicle-merge rule before any detection run (see notes).

## Proposed next step
S3b (acceptance range / sudden appearance) still waits for receiver positions. For S4 / S5 use `splits_tampa_v2.json` and `adapters.load_tampa()`; the VeReMi split is unchanged and remains the main benchmark with statistical power. If the user can obtain the larger Tampa data, re-run `tools/WP5_S1b_build.py` and `tools/WP5_S1b_rerun.py` (criteria and seed list are fixed in the code).

## Old vs new tables (generated from the JSON by tools/WP5_S1b_report.py; copy of results/WP5/s1b_tables.md)

**Tampa data, old vs new**

| | old (S1) | new (S1b) |
|---|---|---|
| rows in the CSV | 34464 | 34464 |
| distinct over-the-air messages | (34,453 counted, copies kept) | 19527 |
| grouping unit | 226 coreData_ids (per RSU) | 40 passages of 38 physical vehicles |
| split | by id 136 / 45 / 45 | time blocks (episodes) seed 48: 30 / 6 / 4 passages |
| genuine val / test messages scored | 4491 / 8870 | 2094 / 4225 |
| attackers per type val / test | 10 / 10 | 2 / 2 |

**False alarms on genuine test messages (95% vehicle/passage bootstrap CI for new)**

| operating point | old | v1same | new |
|---|---|---|---|
| beacon rate (L1) | 0.2% | 0.2% | 0.0% [0-0] |
| freshness (L1) | 1.1% | 1.1% | 0.0% [0-0] |
| field ranges, budget (L1) | 0.3% | 0.3% | 0.5% [0-1] |
| field ranges, physical | 0.0% | 0.0% | 0.0% [0-0] |
| L1 union | 1.3% | 1.3% | 0.0% [0-0] |
| pos_speed | 0.2% | 0.2% | 0.5% [0-1] |
| pos_heading | 0.8% | 0.8% | 1.4% [1-2] |
| speed_change | 0.7% | 0.7% | 0.6% [0-1] |
| implied_speed | 0.2% | 0.2% | 0.5% [0-2] |
| heading_rate | 0.9% | 0.9% | 2.7% [1-5] |
| accel_consistency | 0.7% | 0.7% | 0.7% [0-1] |
| yaw_consistency | 0.6% | 0.6% | 1.2% [0-2] |
| overlap | 0.0% | 0.0% | 0.0% [0-0] |
| L2 physical union | 0.0% | 0.0% | 0.0% [0-0] |
| L2 union (deployable; old = with map) | 6.3% | 1.0% | 1.8% [0-4] |
| L1 + L2 union (deployable; old = with map) | 7.6% | 2.3% | 1.8% [0-4] |
| harness combined, all layers | 6.7% | 1.3% | 1.7% [0-3] |
| map_road alone (soft layer) | 5.5% | 5.5% | 7.8% [0-19] |
| L1 + L2 union OR map_road | - | 7.7% | 9.1% [0-23] |

**Physical limits, false alarms on genuine val / test** (bound 0.1%)

| limit | old | v1same | new |
|---|---|---|---|
| v2x.field_ranges | 0.000% / 0.000% | 0.000% / 0.000% | 0.000% / 0.000% |
| v2x.speed_change | 0.000% / 0.023% | 0.000% / 0.023% | 0.000% / 0.000% |
| v2x.implied_speed | 0.000% / 0.000% | 0.000% / 0.000% | 0.000% / 0.000% |
| v2x.heading_rate | 0.000% / 0.000% | 0.000% / 0.000% | 0.000% / 0.000% |
| L2_physical_union | 0.000% / 0.023% | 0.000% / 0.023% | 0.000% / 0.000% |

**Tampa test, message-level detection, L1 union** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 0.6% | 0.6% | 0.0% [0-0] | 2 |
| 02_ConstPosOffset | 1.2% | 1.2% | 0.0% [0-0] | 2 |
| 03_RandomPos | 1.5% | 1.5% | 0.0% [0-0] | 2 |
| 04_RandomPosOffset | 1.7% | 1.7% | 0.0% [0-0] | 2 |
| 05_ConstSpeed | 0.4% | 0.4% | 0.0% [0-0] | 2 |
| 06_ConstSpeedOffset * | 0.7% | 0.7% | 0.0% [0-0] | 2 |
| 07_RandomSpeed | 0.3% | 0.3% | 0.0% [0-0] | 2 |
| 08_RandomSpeedOffset | 2.1% | 2.1% | 0.0% [0-0] | 2 |
| 09_EventualStop | 0.3% | 0.3% | 0.0% [0-0] | 2 |
| 10_Disruptive | 0.8% | 0.8% | 0.0% [0-0] | 2 |
| 11_DataReplay | 0.0% | 0.0% | 0.0% [0-0] | 2 |
| 12_DelayedMessages * | 0.0% | 0.0% | 0.0% [0-0] | 2 |
| 13_DoS | 5.7% | 5.7% | 5.6% [5-6] | 2 |
| 14_DoSRandom | 94.3% | 94.3% | 96.4% [94-99] | 2 |
| 15_DoSDisruptive | 92.8% | 92.8% | 96.4% [94-99] | 2 |
| 16_GridSybil | 0.6% | 0.6% | 0.0% [0-0] | 2 |
| 17_DataReplaySybil * | 1.4% | 1.4% | 0.0% [0-0] | 2 |
| 18_DoSRandomSybil | 1.3% | 1.3% | 0.0% [0-0] | 2 |
| 19_DoSDisruptiveSybil | 1.3% | 1.3% | 0.0% [0-0] | 2 |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% [100-100] | 2 |

**Tampa test, message-level detection, L2 union** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 15.0% | 10.0% | 10.4% [4-18] | 2 |
| 02_ConstPosOffset | 37.2% | 0.7% | 1.1% [0-2] | 2 |
| 03_RandomPos | 99.8% | 99.6% | 99.8% [100-100] | 2 |
| 04_RandomPosOffset | 99.7% | 99.4% | 99.7% [100-100] | 2 |
| 05_ConstSpeed | 54.3% | 42.5% | 3.5% [3-6] | 2 |
| 06_ConstSpeedOffset * | 28.7% | 12.4% | 3.5% [2-5] | 2 |
| 07_RandomSpeed | 97.6% | 97.6% | 96.0% [95-97] | 2 |
| 08_RandomSpeedOffset | 90.3% | 89.3% | 86.7% [85-89] | 2 |
| 09_EventualStop | 3.1% | 0.2% | 0.1% [0-0] | 2 |
| 10_Disruptive | 94.4% | 94.4% | 97.7% [98-98] | 2 |
| 11_DataReplay | 11.4% | 3.6% | 8.1% [7-9] | 2 |
| 12_DelayedMessages * | 10.4% | 3.6% | 6.1% [1-9] | 2 |
| 13_DoS | 2.5% | 1.9% | 6.6% [4-10] | 2 |
| 14_DoSRandom | 99.8% | 99.6% | 97.9% [96-100] | 2 |
| 15_DoSDisruptive | 95.2% | 95.1% | 95.9% [94-98] | 2 |
| 16_GridSybil | 5.1% | 2.0% | 2.1% [2-2] | 2 |
| 17_DataReplaySybil * | 39.6% | 21.8% | 5.1% [4-6] | 2 |
| 18_DoSRandomSybil | 71.0% | 47.2% | 57.7% [57-59] | 2 |
| 19_DoSDisruptiveSybil | 64.0% | 63.7% | 60.2% [59-62] | 2 |
| S20_StaleReplay | 78.9% | 76.9% | 35.0% [33-37] | 2 |

**Tampa test, message-level detection, L1+L2 union** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 15.5% | 10.5% | 10.4% [4-18] | 2 |
| 02_ConstPosOffset | 37.6% | 1.9% | 1.1% [0-2] | 2 |
| 03_RandomPos | 99.8% | 99.6% | 99.8% [100-100] | 2 |
| 04_RandomPosOffset | 99.7% | 99.4% | 99.7% [100-100] | 2 |
| 05_ConstSpeed | 54.8% | 42.9% | 3.5% [3-6] | 2 |
| 06_ConstSpeedOffset * | 29.4% | 13.1% | 3.5% [2-5] | 2 |
| 07_RandomSpeed | 97.6% | 97.6% | 96.0% [95-97] | 2 |
| 08_RandomSpeedOffset | 90.5% | 89.5% | 86.7% [85-89] | 2 |
| 09_EventualStop | 3.4% | 0.6% | 0.1% [0-0] | 2 |
| 10_Disruptive | 94.5% | 94.5% | 97.7% [98-98] | 2 |
| 11_DataReplay | 11.4% | 3.6% | 8.1% [7-9] | 2 |
| 12_DelayedMessages * | 10.4% | 3.6% | 6.1% [1-9] | 2 |
| 13_DoS | 7.8% | 7.2% | 10.9% [8-14] | 2 |
| 14_DoSRandom | 99.9% | 99.8% | 99.9% [100-100] | 2 |
| 15_DoSDisruptive | 99.4% | 99.3% | 99.8% [100-100] | 2 |
| 16_GridSybil | 5.6% | 2.5% | 2.1% [2-2] | 2 |
| 17_DataReplaySybil * | 40.4% | 22.6% | 5.1% [4-6] | 2 |
| 18_DoSRandomSybil | 71.3% | 47.9% | 57.8% [57-60] | 2 |
| 19_DoSDisruptiveSybil | 64.4% | 64.1% | 60.2% [59-62] | 2 |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% [100-100] | 2 |

**Tampa test, message-level detection, map_road (soft)** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 5.3% | 5.3% | 0.0% [0-0] | 2 |
| 02_ConstPosOffset | 37.5% | 37.5% | 62.2% [49-77] | 2 |
| 03_RandomPos | 47.1% | 47.1% | 63.2% [63-63] | 2 |
| 04_RandomPosOffset | 44.3% | 44.3% | 69.7% [67-71] | 2 |
| 05_ConstSpeed | 14.1% | 14.1% | 0.9% [0-1] | 2 |
| 06_ConstSpeedOffset * | 17.7% | 17.7% | 14.0% [1-26] | 2 |
| 07_RandomSpeed | 7.1% | 7.1% | 0.6% [0-1] | 2 |
| 08_RandomSpeedOffset | 13.0% | 13.0% | 0.0% [0-0] | 2 |
| 09_EventualStop | 2.8% | 2.8% | 0.0% [0-0] | 2 |
| 10_Disruptive | 0.9% | 0.9% | 12.8% [13-13] | 2 |
| 11_DataReplay | 8.2% | 8.2% | 1.2% [1-1] | 2 |
| 12_DelayedMessages * | 7.1% | 7.1% | 17.8% [0-26] | 2 |
| 13_DoS | 0.8% | 0.8% | 12.5% [0-26] | 2 |
| 14_DoSRandom | 45.8% | 45.8% | 63.4% [63-63] | 2 |
| 15_DoSDisruptive | 5.9% | 5.9% | 17.2% [17-17] | 2 |
| 16_GridSybil | 3.3% | 3.3% | 0.5% [0-1] | 2 |
| 17_DataReplaySybil * | 22.1% | 22.1% | 59.6% [48-65] | 2 |
| 18_DoSRandomSybil | 45.3% | 45.3% | 63.5% [63-64] | 2 |
| 19_DoSDisruptiveSybil | 0.5% | 0.5% | 12.2% [11-13] | 2 |
| S20_StaleReplay | 11.9% | 11.9% | 14.5% [11-18] | 2 |

**Tampa test, message-level detection, combined** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 14.8% | 9.6% | 8.9% [4-15] | 2 |
| 02_ConstPosOffset | 37.3% | 1.3% | 1.0% [0-2] | 2 |
| 03_RandomPos | 99.8% | 99.6% | 99.8% [100-100] | 2 |
| 04_RandomPosOffset | 99.7% | 99.5% | 99.7% [100-100] | 2 |
| 05_ConstSpeed | 52.4% | 39.4% | 3.3% [2-5] | 2 |
| 06_ConstSpeedOffset * | 34.4% | 17.8% | 14.8% [5-25] | 2 |
| 07_RandomSpeed | 97.5% | 97.2% | 96.3% [96-97] | 2 |
| 08_RandomSpeedOffset | 89.9% | 88.3% | 86.6% [85-89] | 2 |
| 09_EventualStop | 3.1% | 0.2% | 0.1% [0-0] | 2 |
| 10_Disruptive | 94.3% | 94.3% | 97.7% [98-98] | 2 |
| 11_DataReplay | 11.4% | 3.4% | 7.9% [7-9] | 2 |
| 12_DelayedMessages * | 10.3% | 3.4% | 5.1% [1-7] | 2 |
| 13_DoS | 4.2% | 3.4% | 9.9% [7-13] | 2 |
| 14_DoSRandom | 99.9% | 99.8% | 99.9% [100-100] | 2 |
| 15_DoSDisruptive | 99.4% | 99.3% | 99.8% [100-100] | 2 |
| 16_GridSybil | 4.9% | 1.7% | 1.9% [2-2] | 2 |
| 17_DataReplaySybil * | 39.7% | 21.3% | 5.1% [4-6] | 2 |
| 18_DoSRandomSybil | 71.5% | 48.3% | 61.8% [61-64] | 2 |
| 19_DoSDisruptiveSybil | 64.4% | 64.1% | 57.4% [57-59] | 2 |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% [100-100] | 2 |

**Mean detection over the 19 injected types (unweighted), test**

| operating point | old | v1same | new |
|---|---|---|---|
| L1 union | 10.9% | 10.9% | 10.4% |
| L2 union | 53.6% | 46.6% | 44.1% |
| L1+L2 union | 54.4% | 47.4% | 44.7% |
| map_road (soft) | 17.3% | 17.3% | 24.8% |
| combined | 54.1% | 47.0% | 45.1% |

**Harness group ablation, AUC / detection at the 1% validation budget / test FA** (old L2 and L1+L2 contain map_road; v1same and new do not)

| group | old | v1same | new |
|---|---|---|---|
| L1 | 0.629 / 18.4% / FA 0.9% | 0.629 / 18.4% / FA 0.9% | 0.671 / 21.1% / FA 0.5% |
| L2 | 0.754 / 52.6% / FA 6.3% | 0.735 / 48.0% / FA 1.3% | 0.764 / 47.2% / FA 1.8% |
| L1+L2 | 0.781 / 53.3% / FA 6.7% | 0.756 / 46.6% / FA 1.3% | 0.798 / 48.7% / FA 1.7% |

**Each layer alone in the S3 harness (AUC / detection at 1% budget / test FA)**

| layer | old | v1same | new |
|---|---|---|---|
| v2x.accel_consistency | 0.624 / 29.6% / 0.7% | 0.624 / 29.6% / 0.7% | 0.672 / 37.3% / 0.7% |
| v2x.beacon_rate | 0.527 / 16.3% / 0.2% | 0.527 / 16.3% / 0.2% | 0.594 / 25.9% / 0.0% |
| v2x.field_ranges | 0.604 / 1.0% / 0.3% | 0.604 / 1.0% / 0.3% | 0.562 / 2.9% / 0.5% |
| v2x.freshness | 0.499 / 1.4% / 1.1% | 0.499 / 1.4% / 1.1% | 0.508 / 0.3% / 0.0% |
| v2x.heading_rate | 0.443 / 2.1% / 0.9% | 0.443 / 2.1% / 0.9% | 0.449 / 9.2% / 2.7% |
| v2x.implied_speed | 0.619 / 34.0% / 0.2% | 0.619 / 34.0% / 0.2% | 0.669 / 39.7% / 0.5% |
| v2x.map_road | 0.572 / 18.3% / 5.5% | - | - |
| v2x.overlap | 0.517 / 3.5% / 0.0% | 0.517 / 3.5% / 0.0% | 0.511 / 2.1% / 0.0% |
| v2x.pos_heading | 0.546 / 18.0% / 0.8% | 0.546 / 18.0% / 0.8% | 0.557 / 26.5% / 1.4% |
| v2x.pos_speed | 0.690 / 39.8% / 0.2% | 0.690 / 39.8% / 0.2% | 0.751 / 43.3% / 0.5% |
| v2x.speed_change | 0.611 / 28.9% / 0.7% | 0.611 / 28.9% / 0.7% | 0.643 / 36.9% / 0.6% |
| v2x.yaw_consistency | 0.511 / 3.4% / 0.6% | 0.511 / 3.4% / 0.6% | 0.541 / 12.2% / 1.2% |

**Leave-one-out (all-but-X) in the S3 harness (AUC / detection)**

| removed | old | v1same | new |
|---|---|---|---|
| all_but_v2x.accel_consistency | 0.781 / 53.1% | 0.757 / 46.6% | 0.796 / 48.6% |
| all_but_v2x.beacon_rate | 0.765 / 52.9% | 0.739 / 46.2% | 0.781 / 47.7% |
| all_but_v2x.field_ranges | 0.776 / 53.1% | 0.739 / 46.6% | 0.789 / 48.1% |
| all_but_v2x.freshness | 0.778 / 53.0% | 0.760 / 46.6% | 0.796 / 48.5% |
| all_but_v2x.heading_rate | 0.782 / 53.2% | 0.758 / 46.7% | 0.807 / 48.6% |
| all_but_v2x.implied_speed | 0.781 / 53.2% | 0.756 / 46.7% | 0.798 / 48.7% |
| all_but_v2x.map_road | 0.756 / 46.6% | - | - |
| all_but_v2x.overlap | 0.770 / 51.7% | 0.744 / 45.1% | 0.790 / 48.5% |
| all_but_v2x.pos_heading | 0.781 / 53.2% | 0.757 / 46.7% | 0.797 / 48.5% |
| all_but_v2x.pos_speed | 0.763 / 50.9% | 0.741 / 44.3% | 0.764 / 47.7% |
| all_but_v2x.speed_change | 0.781 / 53.3% | 0.758 / 46.8% | 0.804 / 48.7% |
| all_but_v2x.yaw_consistency | 0.782 / 53.2% | 0.758 / 46.7% | 0.797 / 48.6% |

**S2 (L1) on Tampa, false alarms on genuine test messages**

| | old | v1same | new |
|---|---|---|---|
| beacon rate FA | 0.2% | 0.2% | 0.0% |
| freshness FA | 1.1% | 1.1% | 0.0% |
| field ranges (budget) FA | 0.3% | 0.3% | 0.5% |
| field ranges (physical) FA | 0.0% | 0.0% | 0.0% |
| L1 union FA | 1.3% | 1.3% | 0.0% |
| S2 combined FA | 0.9% | 0.9% | 0.5% |

**S2 (L1 union) on Tampa, message-level detection per type**

| type | old | v1same | new |
|---|---|---|---|
| 01_ConstPos | 0.6% | 0.6% | 0.0% |
| 02_ConstPosOffset | 1.2% | 1.2% | 0.0% |
| 03_RandomPos | 1.5% | 1.5% | 0.0% |
| 04_RandomPosOffset | 1.7% | 1.7% | 0.0% |
| 05_ConstSpeed | 0.4% | 0.4% | 0.0% |
| 06_ConstSpeedOffset | 0.7% | 0.7% | 0.0% |
| 07_RandomSpeed | 0.3% | 0.3% | 0.0% |
| 08_RandomSpeedOffset | 2.1% | 2.1% | 0.0% |
| 09_EventualStop | 0.3% | 0.3% | 0.0% |
| 10_Disruptive | 0.8% | 0.8% | 0.0% |
| 11_DataReplay | 0.0% | 0.0% | 0.0% |
| 12_DelayedMessages | 0.0% | 0.0% | 0.0% |
| 13_DoS | 5.7% | 5.7% | 5.6% |
| 14_DoSRandom | 94.3% | 94.3% | 96.4% |
| 15_DoSDisruptive | 92.8% | 92.8% | 96.4% |
| 16_GridSybil | 0.6% | 0.6% | 0.0% |
| 17_DataReplaySybil | 1.4% | 1.4% | 0.0% |
| 18_DoSRandomSybil | 1.3% | 1.3% | 0.0% |
| 19_DoSDisruptiveSybil | 1.3% | 1.3% | 0.0% |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% |
