# WP8 S8: post-M4 false-alarm diagnostic and sensor-health gate

Date: 2026-11-05    Worker: sonnet (high, T3)    Branch v3.1 (tag v3.0 untouched)    Rules and diagnosis: notes/WP8_S8.md (committed b1d2749 BEFORE any fix)

## Summary (<= 40 lines)

- **Root cause of the K false alarms (a data defect, not a detector bug).** H31 drive 2011_09_26_drive_0093 (clean GPS tick FA 94.4 %, cross 90.6 %, LiDAR scans 85.9 %) has a navigation record that never converged: OXTS `pos_accuracy` 29.6 m mean / 44.3 m max on every frame (all 35 other drives <= 1.62 m), `vel_accuracy` up to 1.17 m/s, 2-7 satellites, no GNSS position on 258 of 433 frames, orientation mode 0 on all frames, lateral velocity up to 14.1 m/s, heading off the course over ground by up to 160 deg. The sim derives GPS, compass, wheel speed, gyro and the LiDAR ego pose from that record, so every layer that compares them with the real LiDAR fires. The LiDAR odometry is healthy (step error vs OXTS 0.99 m on 0093, 0.007-0.09 m on the other 22 drives). Timestamps, scan counts and point counts are clean; speed and yaw rate are inside the training envelope.
- **Other items (descriptive, no fix):** without 0093 the K clean FA is GPS 0.7 %, cross 1.2 % (start-up transients of drives 0047 / 0009), LiDAR scans 2.6 % (L2a intensity episodes on 0009 / 0064, L2d on 0004: scene-specific, pose healthy, intensity inside the envelope): a genuine drive-level tail of tile statistics (no data defect, no bug; the drives are inside the envelope, so this is "(b) genuine" but not "out of envelope"). V2AIX Stationary FA 2.26 %: concentrated in a few site-days (top 10 % of recordings carry 69 % of the alarms; Theaterstrasse 3.2 %), class (b), day-to-day shift of the 1 % budget.
- **Fix (F1, pre-registered): reference-health gate** (system/health31.py). A frame is degraded if the unit's own `pos_accuracy` > 5.0 m or `vel_accuracy` > 0.5 m/s (3 x the largest value on any train / V31_val drive; 5 sigma / 10 sigma of the detectors' receiver-noise model). Degraded ticks withhold the GPS-domain and cross-domain verdicts and mask the pose layers L2c / L2d of the LiDAR union; they publish `sensor_health = reference degraded`. This is a sensor-health signal, NOT an attack verdict; no threshold, ECDF, combiner or correlator changed.
- **V31_val (rule A1, A2):** the gate fires on 0 of 2085 OXTS frames of the 10 V31_val drives and 0 of 2588 of the 13 train drives; gated and ungated system results are identical and equal the frozen in-sample check (K FA 1.80 %, 4.53 events/h, detection 72.9 %). Detection change 0.0 pts (tolerance 1.0). A3: ungated H31 run equals the S7 v3.1 numbers on all keys: True.
- **H31 re-scoring, ONE run, labelled "re-used hold-out, exposure 2 (post-M4 fix), NOT fresh"** (frozen v3.1 vs v3.1 + S8, same composites, paired bootstrap over clean timelines / groups, B = 2000, seed 31): K clean tick FA 12.2 % -> **4.7 %** [4.2, 5.4] (paired -7.5 pts [-9.5, -5.3]; on evaluable ticks 5.1 %); events per clean hour 24.8 -> 22.4; SAFE_STOP per clean hour 6.43 -> 0.88; K event detection (single-domain) 87.1 % -> 84.6 % (paired -2.5 pts [-3.9, -1.3]); held-out 90.8 % -> 86.8 % (paired -4.0 [-9.0, 0.0]). Comma unchanged (gate fires 0 times).
- **Against the unchanged M4 bounds (for information; the S7 M4 verdict stands):** K FA 4.7 % vs 3 %: NOT MET; events 22.4/h vs 10: NOT MET; SAFE_STOP 0.88/h vs 1: now MET (was 6.43); LiDAR clean scan FA 8.4 % -> 2.43 % vs 1.5 %: NOT MET; PointDrop per scan 66.1 % -> 59.4 % vs 65 %: NOT MET. The pre-registered expectation (K FA about 4.5 %, events about 24/h, LiDAR scan FA about 3 %) held. The fix repairs the 0093 defect; v3.1 still does not meet M4.
- **The previous "PointDrop 66.1 %" and the K detection 87.1 % were partly flood effects:** on 0093 the alarm rate was so high that attack composites overlapping its gated ticks were "detected" 100 % of the time (153 single-domain composites); with the gate 38.6 %; on the 1793 other composites detection is identical (87.9 %). PointDrop per scan on the 12 healthy drives is 63.8 % either way.
- **Attack windows and the gate:** 6.8 % of the K attack-labelled ticks are gated (6369 of 93990), all on drive 0093 (the simulated attacks never touch the accuracy fields). In deployment the fields are receiver output: a spoofer that controls the receiver can claim a poor accuracy and blind the GNSS-based checks (discussion below). CAN, network, V2X and LiDAR L1 / L2a keep running.
- Not fixed, stated: LiDAR L2a drive-level episodes, V2AIX Stationary day shift, comma clean FA 6.1 % (V2X / CAN / network own alarms), start-up transients of the speed edges. Remaining K clean events come from CAN, V2X, LiDAR, cross and network own alarms (table 6).
- Statistical caveat: the improvement rests on ONE drive (0093); a drive-cluster bootstrap over the 13 H31 drives gives for the LiDAR clean scan FA a paired CI touching 0 (-6.0 pts [-19.8, 0.0]). The system-level CIs above resample clean timelines / composites, not drives.
- Files: notes/WP8_S8.md, system/health31.py, tests/v31/test_s8_health.py (4 tests), tools/WP8_S8_*.py, results/WP8/S8/*.json, scores results/WP8/scores/S8/.

## 1. Per-drive false alarms, by layer (frozen detectors, saved S7 / S2 / S3 scores; results/WP8/S8/fa_by_drive.json, gps_layers.json)

Table 1: clean-tick false alarms per drive (H31 and V31_val). GPS = combined GPS-domain alarm; cross = combined cross-domain alarm; LiDAR = combined scan alarm; L1 / L2a / L2c / L2d = layer over its own threshold (V31_val: frozen thresholds on the leave-one-drive-out raw scores, in-sample reference, indicative).

| set | drive | ticks | GPS | cross | scans | LiDAR | L1 | L2a | L2c | L2d |
|---|---|---|---|---|---|---|---|---|---|---|
| H31 | 0004 | 352 | 0.0 % | 0.0 % | 338 | 6.2 % | 0.0 % | 0.0 % | 0.0 % | 6.2 % |
| H31 | 0009 | 462 | 0.6 % | 2.6 % | 442 | 8.8 % | 0.0 % | 8.4 % | 0.2 % | 0.2 % |
| H31 | 0016 | 290 | 0.0 % | 0.3 % | 278 | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| H31 | 0023 | 491 | 0.6 % | 0.2 % | 473 | 1.3 % | 0.0 % | 0.0 % | 1.3 % | 0.0 % |
| H31 | 0026 | 164 | 0.0 % | 0.0 % | 157 | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| H31 | 0032 | 404 | 0.2 % | 0.0 % | 389 | 1.5 % | 0.0 % | 0.0 % | 0.5 % | 1.0 % |
| H31 | 0047 | 867 | 1.4 % | 5.0 % | 836 | 1.7 % | 0.0 % | 0.1 % | 1.6 % | 0.0 % |
| H31 | 0056 | 303 | 0.0 % | 0.0 % | 293 | 1.7 % | 0.0 % | 0.0 % | 0.0 % | 1.7 % |
| H31 | 0061 | 727 | 0.4 % | 1.2 % | 702 | 2.3 % | 0.0 % | 1.9 % | 0.4 % | 0.0 % |
| H31 | 0064 | 589 | 0.2 % | 0.2 % | 569 | 6.5 % | 0.0 % | 6.5 % | 0.0 % | 0.0 % |
| H31 | 0084 | 396 | 0.8 % | 0.3 % | 382 | 0.8 % | 0.0 % | 0.0 % | 0.8 % | 0.0 % |
| H31 | 0093 | 448 | 94.4 % | 90.6 % | 432 | 85.9 % | 0.0 % | 0.0 % | 12.0 % | 85.9 % |
| H31 | 0101 | 967 | 1.7 % | 0.7 % | 935 | 0.4 % | 0.0 % | 0.0 % | 0.2 % | 0.3 % |
| V31_val | 0001 | 111 | 0.0 % | 0.0 % | 107 | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| V31_val | 0005 | 159 | 1.9 % | 0.6 % | 153 | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| V31_val | 0011 | 241 | 0.8 % | 0.0 % | 232 | 1.7 % | 0.0 % | 0.9 % | 0.0 % | 0.9 % |
| V31_val | 0027 | 194 | 2.6 % | 2.1 % | 187 | 3.2 % | 0.0 % | 0.0 % | 3.2 % | 0.0 % |
| V31_val | 0028 | 445 | 1.6 % | 0.2 % | 429 | 0.2 % | 0.0 % | 0.0 % | 0.0 % | 0.2 % |
| V31_val | 0035 | 135 | 0.7 % | 0.0 % | 130 | 1.5 % | 0.0 % | 1.5 % | 0.0 % | 0.0 % |
| V31_val | 0039 | 407 | 0.7 % | 1.7 % | 394 | 1.0 % | 0.0 % | 1.0 % | 0.0 % | 0.0 % |
| V31_val | 0052 | 80 | 0.0 % | 0.0 % | 77 | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| V31_val | 0079 | 103 | 0.0 % | 0.0 % | 99 | 0.0 % | 0.0 % | 0.0 % | 0.0 % | 0.0 % |
| V31_val | 0095 | 277 | 3.2 % | 0.4 % | 267 | 1.1 % | 0.0 % | 0.0 % | 1.1 % | 0.0 % |
| H31 without 0093 (pooled) | - | 6012 | 0.7 % | 1.2 % | 5794 | 2.6 % | - | 1.5 % | 0.5 % | 0.6 % |
| V31_val (pooled) | - | 2152 | 1.4 % | 0.7 % | 2075 | 1.0 % | - | - | - | - |

Table 2: cross edges and GPS-domain layers on drive 0093 (share of clean ticks that alarm), against the pooled rate over the 12 other H31 drives.

| layer | 0093 | other 12 H31 drives (pooled) |
|---|---|---|
| cross edge gps-lidar speed | 75.9 % | 0.3 % |
| cross edge gps-can speed | 52.5 % | 0.1 % |
| cross edge lidar-can speed | 83.5 % | 0.9 % |
| cross edge gps-lidar lateral | 87.1 % | 0.0 % |
| cross edge compass-lidar yaw | 0.0 % | 0.1 % |
| cross edge compass-gyro yaw | 0.0 % | 0.1 % |
| cross edge gyro-lidar yaw | 0.0 % | 0.0 % |
| GPS layer max_speed | 0.0 % | 0.00 % |
| GPS layer long_accel | 6.7 % | 0.00 % |
| GPS layer lat_accel | 2.7 % | 0.00 % |
| GPS layer jerk | 1.8 % | 0.00 % |
| GPS layer yaw_rate | 2.7 % | 0.00 % |
| GPS layer vel_pos_consistency | 52.5 % | 0.82 % |
| GPS layer dr_resid_10 | 88.4 % | 1.21 % |
| GPS layer ekf_nis | 95.5 % | 0.55 % |
| GPS layer cusum_ekf | 72.8 % | 0.90 % |
| GPS layer cusum_dr | 94.4 % | 0.88 % |
| GPS layer lidar_z_1 | 93.3 % | 0.78 % |
| GPS layer lidar_z_3 | 94.4 % | 0.80 % |
| GPS layer lidar_z_10 | 94.4 % | 1.46 % |
| GPS layer lidar_resid_1 | 92.6 % | 0.80 % |
| GPS layer lidar_resid_3 | 92.9 % | 1.03 % |
| GPS layer lidar_course | 14.5 % | 0.80 % |

## 2. Data quality of the recordings (results/WP8/S8/dq.json; OXTS dataformat fields)

Table 3: receiver / record fields, 0093 against the other H31 drives (min - max over the 12) and the 23 V31_val + train drives (min - max).

| field | 0093 | other 12 H31 (range) | V31_val + train 23 (range) |
|---|---|---|---|
| OXTS frames / velodyne scans | 433 / 433 | - | - |
| pos_accuracy max (m) | 44.35 | 0.112 - 0.887 | 0.017 - 1.62 |
| vel_accuracy max (m/s) | 1.165 | 0.0304 - 0.0979 | 0.0113 - 0.156 |
| numsats mean (min) | 4.5 (2) | 6.48 - 11.8 | 2.04 - 13.3 |
| share of frames with posmode 0 (no GNSS position; not discriminating alone) | 0.60 | 0 - 0.0366 | 0 - 1 |
| leftward velocity, abs max (m/s) | 14.12 | 0.0327 - 0.26 | 0.00658 - 0.235 |
| OXTS dt max (s) | 0.120 | 0.11 - 0.13 | 0.11 - 0.14 |
| scan dt max (s) | 0.104 | 0.104 - 0.517 | 0.103 - 0.106 |
| duplicate timestamps (OXTS / scan) | 0 / 0 | - | - |
| scan points mean | 117667 | 1.11e+05 - 1.26e+05 | 1.08e+05 - 1.25e+05 |
| mean speed / max speed (m/s) | 4.0 / 8.7 | 6.47 - 18.5 | 0.00289 - 22 |
| yaw rate, abs p95 / max (rad/s) | 0.355 / 0.516 | 0.0082 - 0.544 | 0.00133 - 0.66 |

Physics of the record: yaw minus course over ground atan2(vn, ve) 9 deg at t = 0-3 s, 67 deg at 15 s, 124 deg mean at 27 s (up to 160 deg), back to -26 deg at 33-42 s; forward velocity vf (the projection on that heading) 3.2-5 m/s where |v| = 8-14 m/s and -6.2 m/s at t = 27 s; position-difference speed 22 m/s at t = 15 s (receiver re-acquisition); LiDAR ICP speed 5.3-6.3 m/s with lateral step 0.009 m. Mean OXTS-vs-ICP pose step error per scan: 0093 0.99 m (p95 1.99 m), the other 22 drives 0.007-0.09 m; L2d fires on scans with 1.11 m mean error vs 0.25 m without. (Ad-hoc scripts of the analysis are summarised in notes/WP8_S8.md; the table above is generated from dq.json.)

## 3. Classification

| cause | class | evidence | action |
|---|---|---|---|
| 0093: non-converged OXTS navigation record (GPS, cross, LiDAR L2d / L2c) | (a) data defect in the recording, amplified by the sim (every non-LiDAR channel derived from OXTS) | Tables 1-3 | gate F1 |
| other-drive cross FA (0047 5.0 %, 0009 2.6 %) | (b) start-up transients of the speed edges, first 30 s | alarms 30/300, 12/300 ticks in the first 30 s | none |
| LiDAR L2a episodes (0009, 0064), L2d (0004) | (b) genuine tail (inside the envelope; no defect, no bug): scene-specific episodes, pose healthy, intensity inside envelope | OXTS-vs-ICP error 0.027-0.049 m in firing scans | none |
| V2AIX Stationary FA 2.26 % | (b) day-to-day shift concentrated in few site-days | per-recording table in v2aix_fa.json | none |
| detector bug | (c) none found: the same layers stay near the 1 % budget on the 35 drives with a healthy reference | - | - |

## 4. Fix F1 and acceptance (rules A1-A5 as pre-registered in notes/WP8_S8.md)

Table 4: where the gate fires (results/WP8/S8/gate_stats.json).

| set | drives | drives gated | OXTS frames | degraded frames | gated 1 Hz ticks (10 phases) |
|---|---|---|---|---|---|
| V31_val | 10 | 0 | 2085 | 0 | 0.0 % |
| train | 13 | 0 | 2588 | 0 | 0.0 % |
| H31 | 13 | 1 | 6243 | 433 | 6.9 % |

Sensitivity (description, not a choice): the gated set is the same for any `pos_accuracy` threshold between 1.62 m (largest value on a drive that is not gated) and 18.67 m (smallest value on drive 0093).

Table 5: rule check.

| rule | result | verdict |
|---|---|---|
| A1 V31_val no harm (gate <= 0.5 % of ticks and scans; K detection drop <= 1.0 pt; FA / events not up) | gate 0 ticks; detection 72.9 % -> 72.9 %; FA 1.80 % -> 1.80 %; events/h 4.53 -> 4.53 | MET (no-op on V31_val by construction; stated) |
| A2 gate precision on healthy drives (<= 0.5 %) | 0 of 4673 frames | MET |
| A3 regression: ungated == S7 frozen v3.1 | equal on all keys (K and C): True; v3 / S7 files untouched (git diff --name-status v3.0 HEAD on the v3 packages lists only added v3.1 files, no modified v3 file; tests/v31 65 pass) | MET |
| A4 H31 exposure 2: one re-scoring, side by side, paired | Table 6 | done (ONE run) |
| A5 attack windows and gate | Table 7 and discussion | reported |

## 5. H31 re-scoring, exposure 2 (re-used hold-out, post-M4 fix, NOT fresh)

Table 6: K = KITTI H31 vehicle block + re-used CAN / network / V2X streams (partially fresh). Paired = v3.1 + S8 minus frozen v3.1, same composites, bootstrap over clean timelines (FA, events) and over groups inside each type (detection, blame), B = 2000, seed 31.

| metric (K) | frozen v3.1 | v3.1 + S8 | paired difference [95 % CI] | M4 bound |
|---|---|---|---|---|
| clean tick FA | 12.2 % [9.7, 14.5] | 4.7 % [4.2, 5.4] | -7.5 pts [-9.5, -5.3] | <= 3.0 %: NOT MET |
| clean tick FA on evaluable (non-gated) ticks | - | 5.1 % | - | - |
| alert events per clean hour | 24.83 22.7-26.7 | 22.44 19.9-24.8 | -2.39 [-3.71, -1.11] | <= 10: NOT MET |
| SAFE_STOP per clean hour | 6.43 | 0.88 [0.17, 1.76] | -5.55 | <= 1: MET (upper CI > 1) |
| mean event detection, single-domain types | 87.1 % [85.5, 88.6] | 84.6 % [82.6, 86.5] | -2.5 pts [-3.9, -1.3] | >= 70 %: MET |
| held-out types | 90.8 % [89.6, 91.5] | 86.8 % [81.6, 90.8] | -4.0 pts [-9.0, 0.0] | >= 60 %: MET |
| blame correct / wrong | 75.0 % / 18.7 % | 76.7 % / 16.9 % | +2.2 / -2.2 pts | >= 75 / <= 10: NOT MET |
| health-flag ticks (blind share) / episodes per clean hour | - | 8.4 % / 5.8 | - | reported separately, not alerts |
| comma C (clean FA / events per hour / detection) | 6.1 % / 22.6 / 92.5 % | identical | 0 | unchanged |

By attacked domain (K event detection of single-domain types; paired gated - ungated):

| domain | frozen v3.1 | v3.1 + S8 | paired [95 % CI] (pts) |
|---|---|---|---|
| can | 90.9 % | 90.9 % | +0.0 [0.0, 0.0] |
| cross | 81.3 % | 74.7 % | -6.5 [-12.4, -1.9] |
| gps | 96.2 % | 89.0 % | -7.1 [-14.8, -1.5] |
| lidar | 44.9 % | 38.5 % | -6.4 [-12.8, -1.3] |
| network | 86.7 % | 83.3 % | -3.3 [-10.0, 0.0] |
| v2x | 99.1 % | 99.1 % | +0.0 [0.0, 0.0] |

Table 7: attack-labelled ticks of the K composites that are gated (all on drive 0093) and detection on composites overlapping them (single-domain composites).

| attacked domain | composites | labelled ticks | gated labelled ticks | composites with a gated labelled tick |
|---|---|---|---|---|
| can | 11 | 244 | 0 (0.0 %) | 0 |
| cross | 780 | 36420 | 2508 (6.9 %) | 60 |
| gps | 520 | 24280 | 1672 (6.9 %) | 40 |
| gps+can | 130 | 6070 | 418 (6.9 %) | 10 |
| lidar | 117 | 4056 | 282 (7.0 %) | 9 |
| multi | 22 | 956 | 45 (4.7 %) | 1 |
| network | 17 | 4380 | 186 (4.2 %) | 6 |
| v2x | 540 | 17584 | 1258 (7.2 %) | 41 |

Single-domain composites overlapping gated ticks: 153: event detection 100 % (ungated) -> 38.6 % (gated). Not overlapping: 1793: 87.9 % -> 87.9 % (identical). The gate counts as a miss there; no credit is given.

Table 8: own-alarm share of clean ticks per domain (K clean timelines): where the remaining false alarms come from.

| domain | frozen v3.1 | v3.1 + S8 |
|---|---|---|
| gps | 8.6 % | 0.7 % |
| cross | 8.7 % | 1.1 % |
| lidar | 15.7 % | 8.2 % |
| can | 3.8 % | 3.8 % |
| network | 4.8 % | 4.8 % |
| v2x | 9.6 % | 9.6 % |

Table 9: LiDAR domain, H31 scan level (results/WP8/S8/lidar_domain.json; frozen union thresholds, L2c / L2d masked at gated scans). Paired = gated - ungated, bootstrap over the 13 drives (B = 2000, seed 31); only one drive changes, so the CI touches 0.

| subset | scans | gated scans | ungated | gated | paired [95 % CI] (pts) | ungated excl. 0093 |
|---|---|---|---|---|---|---|
| clean scans (FA) | 6226 | 432 | 8.38 % | 2.43 % | -5.96 [-19.79, 0.00] | 2.61 % |
| IntensitySpoof | 2080 | 144 | 52.74 % | 50.14 % | -2.60 [-8.63, 0.00] | 49.43 % |
| PointDrop | 2080 | 144 | 66.11 % | 59.38 % | -6.73 [-22.37, 0.00] | 63.79 % |
| ph_budget_far | 2080 | 144 | 8.41 % | 2.50 % | -5.91 [-19.65, 0.00] | 2.69 % |
| ph_budget_near | 2080 | 144 | 8.46 % | 2.55 % | -5.91 [-19.65, 0.00] | 2.74 % |
| ph_replace_far | 2080 | 144 | 8.46 % | 2.55 % | -5.91 [-19.65, 0.00] | 2.74 % |
| ph_replace_near | 2080 | 144 | 27.79 % | 21.68 % | -6.11 [-20.29, 0.00] | 23.30 % |
| ep_PointDrop (episodes) | 1170 | 90 | 10.17 % | 4.53 % | -5.64 [-16.92, 0.00] | 4.91 % |

## 6. Can an attacker exploit the gate?

The gate withholds verdicts that depend on the navigation record when the record's own accuracy fields are bad. Honest assessment:
1. It creates a blind spot exactly where GNSS spoofing is detected. In the simulation the fields are never attacked, so the measured cost (8.4 % blind clean ticks, all on one drive; detection on the 153 composites that overlap gated ticks 100 % -> 38.6 %, where the 100 % was the false-alarm flood) is the cost of a genuine outage, not of an adversary.
2. In deployment `pos_accuracy` is receiver output. A spoofer or jammer that makes the receiver report a poor fix (or a spoofer that sets large accuracy fields) can switch the GNSS-based checks off. Jamming / denial is itself an attack on availability, and the gate publishes it as `sensor_health` (reason: reported accuracy), so it is visible, but it is not scored as a verdict.
3. What remains active while gated: CAN, network, V2X, LiDAR L1 geometry and L2a intensity, and in a real vehicle the LiDAR-odometry-vs-wheel-speed edge (independent of the GNSS unit; in this sim it is switched off too because the wheel speed is derived from OXTS). A takeover that needs a GNSS lie to be plausible is therefore not hidden from those domains.
4. Recommended hardening (NOT implemented, not tested, outside the pre-registered rules): cap the withheld time (a degraded episode longer than a few minutes, or one that starts with no environmental cause such as a satellite-count drop at an open-sky position, escalates to DEGRADE as a sensor-health alarm); require the unit's accuracy to agree with an independent estimate (LiDAR-odometry drift, speed residual) before accepting a very large claimed error; use `numsats` / signal strength as a second, harder-to-forge witness when available.
5. The gate never turns an alarm into a detection and never lowers a threshold; the worst case of a forged health field is the unchanged v3.1 minus the GNSS-dependent verdicts for the forged duration.

## 7. What S8 does and does not change

- Changes: one new module (system/health31.py, 4 tests), tools and results in WP8 folders. Frozen v3 and v3.1 objects, thresholds, ECDFs, correlator, S7 caches and S7 results untouched (S7 caches are read-only inputs; the gated sources are built in memory).
- H31 is now exposure 2 for the K vehicle block. The S8 H31 numbers are descriptive of a fix that was designed after seeing the failure; the evidence for the fix is (i) the physical diagnosis (Table 3), (ii) the zero-effect check on V31_val and train, (iii) that the pre-registered thresholds lie in a wide interval (1.62 - 18.67 m) that gives the same result.
- The M4 verdict (7 of 18, NOT MET) is not rewritten. A defensible reading: the K false-alarm failure of M4 was dominated by a defective recording; with the sensor-health gate the K FA is 4.7 %, still above the bound; the remaining excess is CAN, V2X, network and LiDAR own alarms on re-used streams and the LiDAR drive-level variance, which S8 did not and could not fix without tuning on H31.

## Open points for the supervisor

- Decide whether the gate is adopted as v3.1 + S8 (a 'sensor-health' layer) and whether the hardening of section 6 point 4 is pre-registered for a later step.
- The sim couples CAN wheel speed, IMU and GPS to one OXTS record; for 0093 this over-counts alarming edges relative to a real vehicle. A decoupled evaluation (real CAN logs for KITTI do not exist) is not possible with this data.
- LiDAR scan FA (2.4 %) and the drive-level variance of L2a remain above the 1.5 % rule; a per-drive budget would need a rule chosen without H31.
- C (comma) clean FA 6.1 % and V2AIX Stationary 2.26 % are untouched.
