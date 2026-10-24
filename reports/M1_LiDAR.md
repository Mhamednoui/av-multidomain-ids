# M1-LiDAR: LiDAR spoofing detection by sensor physics (WP3, milestone report)

Date 2026-10-25. Status: **PARTIAL** (rules written before any S9 result: notes/WP3_lidar.md "S9 design and ACCEPTANCE RULE"; verdicts: results/WP3/S9/acceptance.json). Self-contained; long tables: `results/WP3/S9/S9_tables.md`; numbers: `dev.json` (validation), `final.json` (test, one run), `freeze_check.json`, `test_scores.csv.gz`; earlier steps: reports/WP3_S1 ... S7.

**Protocol.** KITTI raw, Velodyne HDL-64E, 23 drives: 13 train, 3 validation, 7 test (0001 0005 0095 0039 0079 0028 0052). There is no labelled attack and no labelled object, so attacks are generated: calibrated ray-cast phantoms (exact laser rays; return probability and intensity fitted on real KITTI objects, S2) under SINGLE-RETURN physics (one return per beam: an injected return replaces the real one behind it, S2b), replace (full box) / budget (50-400 points) x near (5-15 m) / far (15-40 m); PointDrop (random thinning of a 10-60 deg sector); IntensitySpoof (bright sector). 510 attacked scans per attack (every 3rd scan of the 7 test drives); persistent episodes of 30 scans, 21 per kind, sensor-fixed (placed relative to the sensor) and world-fixed (placed in the world, parked-car-like); episode alarm = v2 rolling log-odds over 1 s above the 99th percentile of clean windows, within 3 s. Rows marked * (multi-return add, single-return box cloud) are comparison rows: physically impossible or crude on a single-return sensor, never headline.
**Stack (zero-shot, no attack label in any fit).** Headline = L1 sensor geometry + L2a object intensity + L2c background model + L2d ego-compensated tracking. Combiner chosen on validation by the label-free rule (clean false-alarm control first, then detection): max of ECDF ranks (split and noisy-or tested: noisy-or eliminated, worst-drive LODO FA 9.5% against 3.6%; split 18.3% vs max 20.4% mean validation detection). Density part of L2a NOT kept (-1.2 points on validation). Thresholds: 1% TOTAL scan budget, tie-safe, from the out-of-fold clean scores of the 16 train+val drives (object model refitted leave-one-drive-out; L1, L2c, L2d have no learned parameter). Optional rows (never headline): L2b occlusion, L4 supervised descriptor model (seen families only). L3 dropped (S7).

## 1. What each layer catches, and why (test, scan level, each layer at its OWN 1% threshold; FA of the clean scans)

| layer | physics | FA | PointDrop | IntensitySpoof | replace near | far / budget phantoms |
|---|---|---|---|---|---|---|
| L1 | L1 geometry: each return lies on one of 64 laser rings and a beam has one return; a point injected off its ring, or a second return in a beam, breaks the sensor model | 0.13 | 0.0 | 0.0 | 0.0 | 0.2 |
| L2a | L2a intensity: the mean intensity of a patch of a surface depends on range and material; a bright sector (spoofed reflectivity) is outside what clean objects give | 0.98 | 0.6 | 65.3 | 0.8 | 0.8 |
| L2c | L2c background: the previous scan moved by the ego pose predicts which ring / azimuth windows return; a removed sector leaves them empty | 2.10 | 87.3 | 1.8 | 1.8 | 1.8 |
| L2d | L2d tracking: a surface that appears in free space, or stays fixed to the sensor while the car moves, is no static or moving object | 0.20 | 0.2 | 0.2 | 32.5 | 0.2 |
| L2b (optional) | free space: far returns seen between returns of one object mean it is not solid | 0.46 | 0.6 | 0.6 | 6.3 | 1.0 |
| L4 (seen families only) | XGBoost on the v2 descriptor, trained on our own PointDrop / IntensitySpoof / phantom generator | 0.72 | 90.8 | 100.0 | 19.2 | 0.8 |

Comparison rows (impossible on a single-return sensor): L1 alone catches the multi-return add far at 62.2% (two returns in one beam), L2d the multi-return add near at 34.5%, L2b the same at 69.4%: the layers behave as designed on the attack they were designed for, and that attack cannot exist on this sensor.

## 2. Final numbers (test, stack at 1% total budget; 95% intervals = bootstrap over the 7 test drives)

| attack | detection | 95% CI | per-drive range | AUC |
|---|---|---|---|---|
| replace near | 17.8% | [15.2, 21.9] | 13.3-27.8% | 0.835 |
| replace far | 0.8% | [0.0, 1.6] | 0.0-2.3% | 0.549 |
| budget near | 0.8% | [0.0, 1.6] | 0.0-2.3% | 0.607 |
| budget far | 0.8% | [0.0, 1.6] | 0.0-2.3% | 0.528 |
| PointDrop | 27.6% | [25.1, 29.1] | 19.4-31.4% | 0.975 |
| IntensitySpoof | 51.6% | [42.0, 62.3] | 30.8-70.6% | 0.914 |
| box cloud* | 5.3% | [3.8, 6.9] | 3.0-8.3% | 0.649 |
| multi-return add near* | 23.5% | [18.8, 30.1] | 0.0-36.1% | 0.851 |
| multi-return add far* | 62.2% | [58.5, 68.5] | 51.5-84.6% | 0.840 |

Clean test FA **1.18%** [0.26, 2.02]; per drive 0001 1.9, 0005 0.0, 0028 0.2, 0039 2.5, 0052 0.0, 0079 0.0, 0095 1.9 (%); leave-one-drive-out FA on the 16 train+val drives: mean 1.31%, worst 3.58% (0070). Small drives move by several points (a single layer alone reaches 14.3% on the 21-scan drive 0048). The budget is shared by four layers: **the stack loses most of what a strong layer has alone** (PointDrop 27.6% against 87.3% for L2c alone; near replace 17.8% against 32.5% for L2d). With every layer at its own 1% (union, FA 3.41%) the same attacks reach 87.5% / 34.3%; a 2% total budget gives PointDrop 68.0%, IntensitySpoof 57.5% (FA 2.03%).

**Persistent episodes (21 per kind, stack, 3 s rule; delays = median first alert of the detected ones):**

| kind | sensor-fixed detected (delay s) | world-fixed detected (delay s) | scan alarm at onset / later steps, world-fixed |
|---|---|---|---|
| replace near | 11/21 (0.10) | 8/21 (0.10) | 23.8% / 2.1% |
| replace far | 2/21 (1.08) | 2/21 (1.81) | 0.0% / 2.0% |
| budget near | 0/21 (-) | 2/21 (0.15) | 0.0% / 0.5% |
| budget far | 1/21 (1.96) | 0/21 (-) | 0.0% / 0.5% |

False-episode rate on 48 clean windows (3 s each): 6.2%. Only the dense, near, replacing phantom is caught (L2d: it appears in free space; 11/21 sensor-fixed, exact 95% interval [30, 74]%), and a world-fixed one is caught at its FIRST scan only (scan alarm 23.8% at step 1, 2.1% afterwards): once it stands in the world like a parked car, the tracker sees a static object.

## 3. Ablation (test, same combiner, 1% total budget; detection %)

| configuration | FA | replace near | far / budget (max) | PointDrop | IntensitySpoof | box cloud* | mr-add near* | mr-add far* |
|---|---|---|---|---|---|---|---|---|
| **all four (headline)** | 1.18 | 17.8 | 0.8 | 27.6 | 51.6 | 5.3 | 23.5 | 62.2 |
| all but L1 | 1.11 | 20.8 | 0.8 | 36.3 | 51.6 | 1.8 | 25.1 | 0.8 |
| all but L2a | 1.05 | 20.8 | 0.8 | 36.3 | 0.8 | 5.7 | 25.1 | 62.2 |
| all but L2c | 0.39 | 20.0 | 0.0 | 0.0 | 51.0 | 5.1 | 24.5 | 62.0 |
| all but L2d | 1.18 | 0.8 | 0.8 | 36.3 | 51.6 | 4.7 | 0.8 | 62.2 |
| L1 alone (own 1%) | 0.13 | 0.0 | 0.2 | 0.0 | 0.0 | 4.1 | 0.0 | 62.2 |
| L2a alone (own 1%) | 0.98 | 0.8 | 0.8 | 0.6 | 65.3 | 0.8 | 0.8 | 0.8 |
| L2c alone (own 1%) | 2.10 | 1.8 | 1.8 | 87.3 | 1.8 | 1.8 | 1.8 | 1.8 |
| L2d alone (own 1%) | 0.20 | 32.5 | 0.2 | 0.2 | 0.2 | 2.5 | 34.5 | 0.2 |
| split combiner (1% total) | 1.18 | 16.9 | 0.8 | 15.9 | 51.6 | 5.3 | 22.5 | 61.8 |
| noisy-or combiner (1% total) | 0.07 | 3.7 | 0.6 | 3.7 | 8.4 | 1.6 | 5.9 | 23.3 |
| + L2b (optional) | 1.18 | 17.3 | 1.0 | 6.3 | 52.0 | 18.6 | 69.0 | 74.7 |
| + L4 (seen families, NOT zero-shot) | 1.51 | 22.4 | 1.0 | 85.7 | 99.4 | 7.3 | 24.9 | 62.0 |
| density part added to L2a | 1.97 | 18.2 | 1.4 | 19.2 | 50.4 | 7.1 | 44.1 | 64.7 |

L2a earns its place (50.8 points on IntensitySpoof), L2c (27.6 on PointDrop), L2d (17.1 on near replace); **L1 does not** (0.0 points on the single-return set: removing it even raises PointDrop to 36.3% and near replace to 20.8% because it frees budget). It stays in the headline by the supervisor's decision as the cheap sensor-integrity layer (it is the only layer that sees injection off the laser rings and duplicate beams, the comparison rows). Adding L2b dilutes PointDrop to 6.3%; adding L4 gives 85.7% / 99.4% but only on the families it was trained on (leave-one-type-out collapses, S7).

## 4. v2 side by side

v2 reported 90.19% accuracy / AUC 0.970 on its own attack mix (PointDrop, IntensitySpoof, a box-cloud ghost with up to 1,500 points where a real car at 30 m has ~50-270; the 4-class argmax has 21.5% false alarms on normal scans). That number is **inflated by the artefacts of section 7** and is not comparable with a per-attack detection at 1% FA. The S2b physics fix collapsed it on the validation drives: v2 near multi-return add 86.2 -> 8.7%, v2 box cloud 65.1 -> 25.7%, L1 far add 60.0 -> 1.5%. The same v2 model on the single-return test attacks (threshold validation 1%, test FA 0.79%):

| attack | v2 | v2 AUC | v3 stack | v3 AUC |
|---|---|---|---|---|
| replace near | 1.0% [0.1, 2.2] | 0.710 | 17.8% | 0.835 |
| replace far | 1.0% [0.1, 2.2] | 0.494 | 0.8% | 0.549 |
| budget near | 1.0% [0.1, 2.2] | 0.529 | 0.8% | 0.607 |
| budget far | 1.0% [0.1, 2.2] | 0.494 | 0.8% | 0.528 |
| PointDrop | 88.6% [85.0, 92.6] | 0.994 | 27.6% | 0.975 |
| IntensitySpoof | 100.0% [100.0, 100.0] | 1.000 | 51.6% | 0.914 |
| box cloud* | 18.8% [14.5, 23.6] | 0.875 | 5.3% | 0.649 |

On calibrated phantoms the two are equal (at the false-alarm level) except near replace where L2d helps (17.8% vs 1.0%). On PointDrop / IntensitySpoof v2 is **better** (88.6% / 100.0%): it is a supervised model trained on exactly those two generator attacks (seen families), and it gets the whole 1% budget; the label-free physics layers reach 87.3% / 65.3% each at their own 1% and 27.6% / 51.6% sharing one. v3 buys unseen-family coverage (L2d near phantoms, L2c removal of any shape) and honest attack physics, not a higher number.

## 5. Fundamentally invisible

- **A calibrated single-return phantom that replaces the real returns** (replace far, budget near / far: 0.8% = FA, AUC 0.55-0.61). On the laser's ray it is a legal scan: same ring, one return per beam, density matched to real objects, intensity from the real library, no free-space or occlusion contradiction (L2b on an attacker that fills every ray: 0.6% = FA). L4, a learned model, is at chance on them too. The WP target (50-400 points >= 60%) is therefore NOT MET and cannot be met by one LiDAR; it needs a second sensor (camera / radar cross-check, S8, not done).
- **A persistent world-fixed phantom** after its first scan (section 2): a parked car is a parked car.
- A near, dense, replacing phantom is the only single-return phantom with a physical footprint (it appears in free space, L2d): 17.8% at 1% total, 32.5% for L2d alone; the S2 generator is ~1.5x denser than real near objects, so this number is optimistic.

## 6. Negative results

- **Density (L2a count / residual): no gain.** Validation -1.2 points (19.2 vs 20.4), worst LODO FA 3.8 vs 3.6%; on test 19.2% PointDrop at FA 1.97%. A calibrated phantom is density matched by construction (S4: 1.0-1.2% = FA).
- **Occlusion (L2b, CARLO):** single-return phantoms 6.3% near replace, best-case attacker 0.6%, only the impossible multi-return add shows (69.4%); LODO unstable (drive 0027 100%, 0013 13%).
- **L3 normal-only object statistics:** adds nothing; worst-drive FA 21.5% (0001). **L4:** leave-one-type-out collapses (PointDrop 95.7 -> 0.0, IntensitySpoof 100 -> 0.0 on validation, S7).
- **Noisy-or** of four layers: FA 0.07% but detection 3.7% / 3.7% (near replace / PointDrop); the equal budget split (each layer at 0.25%) is close to max but gives L2c a stricter share and loses PointDrop (15.9%).

## 7. Artefacts found

- **Multi-return add:** the HDL-64E reports one return per beam; "adding" a phantom next to the surviving real return is impossible. Under the fix (S2b) L1's 60% far-add detection fell to 1.5% and v2's near add from 86.2% to 8.7% (validation).
- **Density 2.1x:** the first generator gave 113 points at 30-35 m where real car-like clusters have 53 (S2); calibrated to ~1.5x (full box vs partial views; equal at equal angular size).
- **Ring offset:** shortening rays toward the sensor origin leaves the laser ring by up to ~0.1 m (ring-sector alarm 11% vs 2%); the generator now uses the exact laser ray.
- **Box cloud:** up to 1,500 points where a real car returns ~50-270, off the rings: easy for v2 and L1, meaningless physically; kept as a comparison row (5.3% here).

## 8. Data limits and test exposure

No labelled objects or attacks (generated attacks only; the generator is the limiting assumption: dense near phantoms favour L2d / L4); KITTI only (one sensor, one region, 2011); the ego pose comes from OXTS (a vehicle without INS must feed LiDAR odometry poses: untested); PointDrop removes 50-100% of a 10-60 deg sector (a small, thin removal would be harder); 7 test drives of 77-429 scans (FA per drive spread above); camera / radar cross-check (S8) not done. **Test exposure of the KITTI LiDAR test drives:** S1 (v2 reproduction), S2 (L1), S4 (L2a), S5 (L2b), S6 (L2c / L2d), S7 (L3 / L4 and the physics stack), S3 (segmentation sanity) and this step: the 7th exposure; the layer scores of S4 / S6 / S7 were re-used (identical to the S7 store, max difference 0.0); no S9 choice used a test number (validation rule), but the test is no longer independent for the project.

## 9. Frozen deployable LiDAR domain (for WP6 S5b / WP7)

`lidar/domain.py`; fitted object `results/WP3/S9/frozen_lidar/` (`domain.pkl`, `intensity_ecdf.npz`, `domain.json`, ring table, calibration; ~9 MB, fitted on clean train+val only).
```
d = LidarDomain.load('results/WP3/S9/frozen_lidar')
s = d.stream()                                    # one per drive; pose = (x, y, yaw) planar pose of the scan (KITTI: lidar.ego.poses)
comb, per = s.push(points, pose, t, sample_id)      # points float32 N x 4 (x fwd, y left, z up, intensity 0-1)
P, q = d.odometry(scan_paths); est = d.motion_estimates(t_fix, P, t_scan, q)   # MotionEstimate(source='lidar'), gps.lidar_odom passthrough
```
Evidence: one combined per scan (`domain=lidar`, `layer=combined`, `name=lidar.combined`, `t` = scan time, `score` in [0, 1] = ECDF of the max-rank statistic on clean scans, `alarm` = statistic >= 0.9968 (about 1% of clean scans; expect 1-3% on unseen drives, worst test drive 2.5%), `reason` = physics sentence of the dominant layer, `details` = method, stat, layer_scores, layer_raw, first_scan_no_previous) and one per layer (`L1`, `L2a`, `L2c`, `L2d`, own 1% threshold). Causal: a scan depends on itself and the previous scan; the first scan of a drive has no L2c / L2d (rank 0, flagged). MotionEstimate: body-frame displacement over 1 s, sigma model of WP1 S5 (x3 on ICP fallback); an independent witness against GPS and CAN speed. **Freeze check:** replayed from raw scans, 2381 test scans (1526 clean = all clean test scans, 855 attacked from drives 0052, 0079, 0001) reproduce the stored per-layer scores and the stack statistic with max difference 1.1e-16 and 0 alarm differences. Cost 1.84 s per scan (single process on the shared machine; segmentation dominates; NOT real time at 10 Hz: needs ~18 parallel workers or a faster segmenter).
