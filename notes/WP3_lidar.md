# WP3 LiDAR notes (worker log, dated)

## 2026-10-21 S1 start: data layer + attack generator
Read: RULES, STATUS, WP3 file, WP1 brief (split, pitfalls), ORCHESTRATOR DECISION rows
(test-exposure: test used once per step, a revised design afterwards only on VAL and a second test
look must be labelled "second exposure"; LODO policy is WP1's; WP3 S1 has no tuned threshold on
test: operating points come from the VAL drives, as in v2).
Copied (header says so): lidar/features.py <- ../codes_v2/lidar/features.py (unchanged);
row logic of lidar/train.py, raycast_test.py, sequence.py -> lidar/build.py. Never imports v2.

### Acceptance rule for S1 (written 2026-10-21 BEFORE any v3 result was computed)
A1 Layer identity: the v3 4-class tables (drive, scan, cls, mode + 429 feature columns) equal
   ../codes_v2/splits/lidar_{train,val,test}.pkl row by row (np.allclose rtol 1e-5, atol 1e-6,
   same row order after v2's sort). If not, explain exactly.
A2 v2 model on the v3 layer: ../codes_v2/lidar/model.json scores the v3 test rows with
   accuracy 90.19% (+-0.05) and attack-vs-normal AUC 0.9696 (+-0.001); detection at the two
   val-chosen operating points (v2 val_fpr 0.01 / 0.02) within +-0.5 point of
   ../codes_v2/results/lidar_operating_points.json.
A3 Baseline retrained in v3 (same search: 20 random trials, seed 42, weight_power 0.5, both
   variants, deployed = higher val macro-F1): test accuracy within +-1.5 points of 90.19% and AUC
   within +-0.01 of 0.970 (GPU xgboost is not bit-reproducible; any larger gap must be explained).
A4 v2 ray-cast numbers reproduced with the v2 model and its val threshold (val_fpr 0.02 =
   ~1% test FA): add onset/sustained 39.1/30.2, budget_add 8.8/4.5, replace ~1.05, each +-1 point
   (../codes_v2/results/lidar_raycast_test.json).
A5 Split saved in results/WP3/split.json: groups "<drive>/<file>", all 23 drives, no drive on
   two sides, scans per part = file counts (train 2588, val 552, test 1533).
A6 Physics unit tests pass (tests/lidar/test_physics.py): ray-cast occlusion / first return,
   points on the box surface, point count ~270 at 30 m (150-450) on an ideal 64-ring scene and
   ~1/r^2 (log-log slope between -2.6 and -1.5, 10-40 m), intensity in [0, 1], PointDrop removes
   only points inside its sector, IntensitySpoof changes intensity only.
A7 Cache <= 5 GB.
Verdict MET only if A1-A7 hold; otherwise report which fails and why.

### 2026-10-22 S1 results (numbers: results/WP3/S1_reproduction.json, S1_acceptance.json; readable: S1_tables.md)
- Build: tools/WP3_S1_build.py (4 workers, resumable). Cache ../data_extra/cache_v3/WP3 = 0.17 GB
  (train4 23 drives, rayv2 / rayw3 / episodes for the 10 val+test drives). A first train4 cache
  was built with a bug (rows stored only the 218 temporal columns, not 211 + 218); caught by the
  shape check, fixed in lidar/build.py, rebuilt before any result was computed.
- A1 MET: v3 rows equal v2 splits/lidar_{train,val,test}.pkl exactly (max abs diff 0.0; 18025 /
  2196 / 6104 rows; same seeds [42, drive]).
- A2 MET: v2 model.json on the v3 rows: test accuracy 90.1868 %, AUC 0.96959, all operating-point
  detections identical to v2 (val FA 1%: PD 82.2, IS 99.9, box cloud 46.4, test FA 0.79 %;
  val FA 2%: 83.9 / 99.9 / 51.4, test FA 1.05 %). The "~1% FA, PointDrop 83.9" figure of the WP file is
  the val_fpr 0.02 operating point (test FA 1.05 %).
- A3 MET: the retrained baseline (GPU xgboost, 20 trials, seed 42) is bit-identical: deployed
  temporal, test acc 90.1868 %, AUC 0.96959 (xgboost GPU hist is deterministic here).
- A4 MET: v2 ray-cast protocol reproduced exactly (add 39.1 / 30.2, budget_add 8.8 / 4.5,
  replace and budget 1.05 = FA) with the v2 model and its val threshold (val_fpr 0.02).
- A5 MET: results/WP3/split.json; train 13 drives 2588 scans, val 3 / 552, test 7 / 1533 files.
- A6 MET: 11 physics tests (tests/lidar/test_physics.py). Ideal 64-ring scene: mean points on a
  car-sized box 385 / 205 at 30 / 40 m (3293 at 10 m), log-log slope about -1.9 over 10-40 m. The
  v2 figure "~270 at 30 m" is the real KITTI median (dropouts, occlusion); the ideal scene is the
  upper bound, hence the test band 150-450.
- A7 MET: cache 0.17 GB.
- New baseline for later steps (v2 model, threshold val 1%, test, tools/WP3_S1_reproduce.py): WP3 phantoms,
  onset / sustained: add far (15-40 m) 20.6 / 14.2, add near (5-15 m) 74.4 / 59.6 (median 2200
  points: a full car at 5-15 m is dense), budget_add far 7.7 / 4.7, budget_add near (50-400 pts, the
  sparse near target of WP3) 6.8 / 3.5; replace and budget = FA (0.8 %: physics bound).
  Persistent episodes (v2 sequence logic, 3 s): box-cloud 9/14 (reproduces v2), ray-cast
  budget_add near 4/21, far 2/21, budget replace near 2/21, far 0/21.
- Pitfall: raycast_ghost(retry=True) shifts the azimuth internally; lidar.raycast.phantom returns
  the parameters actually used (needed to check the box surface).
- Next (not started): S2 L1 sensor geometry. Tuning of anything on test did not occur in S1; the
  only test pass is the reproduction of fixed v2 models.

## 2026-10-22 S2 start (worker sonnet medium): generator calibration (Part A) + L1 sensor geometry (Part B)
Pre-result exploration (train drives only, no judged number): KITTI .bin files are written ring by ring
(65 azimuth-wrap runs: runs 0-63 = the 64 lasers, the 65th a fragment). Each laser lies on a line z = v_k + s_k * rho
(laser vertical offset v_k ~0.1-0.25 m, tan elevation s_k); after removing a per-scan, per-azimuth common offset
(vehicle pitch / heave during the sweep, ~0.03 m) the residual is ~0.01-0.03 m. No tracklets exist under the raw drives
(only velodyne_points + oxts), so real objects are car-like clusters (ground removal + connected components), documented.
Consequence for the generator: the v2/S1 ray-cast uses the ray from the sensor ORIGIN to the real return; the real laser
sits at height v_k above it, so a shortened phantom return is up to -v_k*(1 - rho'/rho) (~0.1 m) off its own ring. The
calibrated generator uses the laser origin (0, 0, h) of each ray (h = z - s_k*rho of the real return).

### ACCEPTANCE RULE S2 (written 2026-10-22 before any calibration / L1 result)
Part A (generator calibration; fitted on TRAIN scans, model form / constants chosen with VAL, test not used for A):
- A1 Real-object table exists (car-like clusters on TRAIN scans, no labels: documented limits). Point count and
  occupancy q = n / (rings spanned x azimuth extent / 0.179 deg) measured vs range; model: per-phantom return
  probability ~ Beta(mean p(rho), concentration kappa), per-point intensity from a library of real objects of the same range band.
- A2 On VAL (3 drives, real car-like clusters vs calibrated phantoms of car size, ranges 8-45 m): two-sample KS statistic
  D <= 0.20 for q and for intensity in EVERY range bin with >= 30 real clusters (effect-size criterion; p-values are
  reported but with thousands of points a p-value criterion rejects any model), and the ratio of median point counts
  phantom / real within 0.8-1.25 in every such bin. The UNcalibrated generator is reported with the same statistics.
- A3 Calibrated phantom at 30 m median point count within +-20 % of the real measured median at 30 m (reported, whichever it is).
- A4 Unit tests: ray-exactness (spoofed points on their ring: residual vs the ring line <= 0.02 m), first-return/occlusion,
  Beta/thinning statistics (mean kept fraction = p), intensity from library, determinism with a seed.
- A5 Regenerated evaluation phantoms re-scored with the v2 model: VAL numbers (threshold from val 1% / val-2%) then TEST ONCE; old vs
  calibrated side by side. No acceptance level on detection (it is a measurement); the old S1 numbers stay as they were.
Part B (L1 sensor geometry, v3 Layers, domain "lidar", layer "L1"):
- B0 Rules: (r1) ring: points whose z-residual to the nearest of the 64 ring lines (after the per-azimuth common-mode removal)
  exceeds 3 x 0.02 m (spec range accuracy 2 cm, HDL-64E manual) in 8-80 m; raw = count (and 10-degree-sector maximum);
  (r2) range / FOV limits: range > 120 m or < train minimum, elevation outside [-24.8, +2.0] +- tolerance; (r3) intensity outside [0, 1];
  (r4) single-return: two returns on the same laser within half an azimuth step (0.09 deg) at different range
  (duplicate direction / point behind a closer return in the same bin). Thresholds: physics constants where they exist (r2, r3,
  the 6 cm of r1), otherwise clean VAL scans, union budget 1% (tie-safe, Layer.calibrate), nothing tuned on test.
- B1 FA: false alarms on clean TEST scans <= 2.0 % (1 % budget + sampling slack; 7 unseen drives); per-drive FA spread reported.
- B2 Predicted detection (stated before the run, a prediction, not a target): box cloud >= 90 %; ray-cast ADD (real return kept = multi-return
  assumption) caught by r4 (>= 90 %, it is physically impossible for a single-return sensor); ray-cast REPLACE and BUDGET (budget 50-400)
  at most FA + 3 points (physics bound: a phantom on its ring and replacing the return is a legal single-return scan);
  PointDrop and IntensitySpoof at most FA + 5 points (removal and in-range intensity do not violate sensor geometry).
  Deviations are reported plainly, and a high detection of a ray-cast phantom is treated as a generator artefact to explain, not a success.
- B3 Harness ablation: v2 descriptor model alone, each L1 rule alone, L1 union, v2 + L1 (OR at the common 1 % / 2 % budget), via common/evaluate.py.
- B4 Tests pass (full suite), cache <= 3 GB under ../data_extra/cache_v3/WP3/. Test exposure: L1 verdict = ONE run on test, labelled FIRST exposure of L1.

### 2026-10-22 S2 Part A results (results/WP3/S2/calib_report.json, ring_table_report.json)
- Ring table (lidar/geometry.py, 128 train scans): 64 lines z = v_k + s_k rho, elevations +1.95 .. -24.9 deg (spec +2.0 / -24.8), v_k 0.09-0.25 m.
  Common-mode removal (per 2 deg azimuth bin, per scan) cuts the 99 % |residual| from 0.097 to 0.040 m on clean train scans (0.091 -> 0.039 val);
  0.28 % (train) / 0.24 % (val) of 8-80 m points exceed 6 cm. KITTI max range in the files = 80 m, min 1.46 m, intensity 0-0.99.
- Duplicate rule needed a design fix found on TRAIN/VAL clean scans before any attack result: neighbouring lasers fire at nearly the same azimuth, so at
  short range (ring spacing < residual noise) 'same ring, same azimuth' pairs are common (1700/scan); restricted to unambiguous lasers (runner-up ring
  >= 7.5 cm away) and 0.02 deg: ~2.5/scan at >=15 m. True same-laser gaps < 0.02 deg: 0.03 % of 359k train pairs (7 % of gaps are 0.09 deg).
- Real objects: no tracklets; 6453 car-like clusters (train, every 3rd scan), 2176 (val). Real median points at ~30 m: 53 (not the ~270 quoted
  from v2: that figure is not reproduced by car-like clusters; clusters are partial / occluded views). Real occupancy q = 0.34-0.54.
- S1-type phantom (ideal density): q 0.52-0.91, point count 1.8-3.7x real (unconditional), 1.3-1.9x at equal angular size.
- Fit (train): p(range) = 0.59-0.73, Beta concentration kappa = 7.2. Variant chosen on VAL: beta (max D_q 0.216 vs 0.333 Bernoulli).
- A2 (as written): D_int max 0.157 <= 0.20 OK; D_q max 0.216 (bin 6-12 m) just above 0.20 NOT strictly met; unconditional count ratio 1.28-1.75 NOT MET
  (real clusters are smaller angular views than a full 4 x 1.8 m box); at EQUAL angular size (terciles) ratios 0.8-1.3 in 16 of 19 strata (3 strata with
  n<=12 phantoms at 2.2-3.0). A3: 80 vs 53 points at 30-35 m unconditional (+50 %), NOT within 20 %: stated plainly.

### 2026-10-22 S2 Part B + A5 results (ONE test run: results/WP3/S2/final.json, tables.md, L1_ablation.md) - FIRST test exposure of L1
- Build (tools/WP3_S2_build.py): v2l1 rows aligned with the S1 train4 cache (n_pts asserted equal), ray tables old+calibrated, every 2nd scan; cache 0.25 GB.
- dev (VAL only, no design change after it): union FA 0.9 %, replace/budget ~FA, add far 60 %, box cloud 47 %. Final test run done once, no re-tuning.
- TEST FA clean scans: L1 union 1.57 % (ring_sector 1.57, ring_total 0.13, single_return/range/intensity 0.0); v2 0.79 %; v2 OR L1 2.36 %.
  Per-drive FA union: 0001 1.9, 0005 5.9, 0028 0, 0039 2.8, 0052 0, 0079 0, 0095 0.7 (spread large: sector rule fires on a few drives).
- Detection test (L1 union): BoxCloud 46.9 (v2 46.3, v2 OR L1 65.7), PointDrop 1.4, IntensitySpoof 1.6, cal add far 60.2 / near 1.7, cal budget_add far 58.3 / near 1.7,
  cal replace 1.7-2.4, cal budget 1.7-2.2 (= FA, physics bound). Old S1 generator: replace far 11.3, budget far 6.9 (off-ring artefact of origin rays; gone with exact rays).
- Predictions B2: box cloud >= 90 % FAILED (47 %: a uniformly random z is within 6 cm of a ring for much of the time at 20-40 m where the ring spacing is only 12-20 cm,
  and the scan-level rule is limited by 1 % FA); add caught by duplicates only far (>=~20 m, laser unambiguous): 60 % far, 0 % near; replace / budget at FA: MET;
  PointDrop / IntensitySpoof at FA: MET.
- A5: v2 on calibrated phantoms (test, val-1 %): add near onset 75.3 -> 61.9, add far 20.5 -> 13.0, budget_add near 5.4 -> 6.5, far 6.9 -> 5.2; replace/budget = FA both.
  Calibrated phantoms are thinner (median 1298 vs 2340 near add, 122 vs 188 far add), so the earlier numbers were inflated by density, as suspected.
- Test exposure: this is the first L1 test run; v2 model/threshold on test was already exposed in S1 (reproduction) and is used here unchanged.

## 2026-10-22 S3 (with S2b) - ACCEPTANCE RULE (written before any S2b / S3 result)

### S2b single-return generator fix
Physics: KITTI's HDL-64E reports one return per beam (laser k, azimuth step 0.1728 deg). A phantom return therefore
occupies a beam and the real return behind it in the same beam cannot also be reported. Fix: lidar/singlereturn.py drops, for
every injected point, the real points of the same laser and azimuth (|d az| < 0.04 deg, laser = nearest ring line after the common
mode) that lie BEHIND it. Calibrated ray-cast phantoms sit exactly on the real return's own ray: add == replace by
construction (budget_add == budget). No rng draw is added, so placements are identical to the S2 tables (paired comparison).
- F1 Physics unit test: after every attack (PointDrop, IntensitySpoof, box cloud, all 4 ray-cast modes, both generators) the number
  of beams carrying two returns does not exceed that of the clean scan (synthetic scene: 0). Test must pass.
- F2 VALIDATION only (3 drives; test not scored, no test attack table is built): regenerate box cloud and ray-cast attacks,
  re-score v2 (threshold = val 1 % / 2 % of clean val scans, as in S2 dev) and L1 (same layers/thresholds as S2, calibrated on
  clean val), side by side old (S2 tables) vs fixed. No detection target. Prediction written now: L1 single_return detection of
  far add/budget_add drops from ~60 % to <= FA + 5 points (it was an artefact of the multi-return assumption); L1 box-cloud
  detection unchanged within 5 points (ring rule); v2 on add/budget_add changes by less than 10 points (descriptor effects only).
  If far-add collapses this confirms the artefact; if it does not, explain.

### S3 object segmentation (data step, no detection verdict)
- Pipeline: ground removal -> clustering -> object table. Parameters chosen on VALIDATION drives (3), train used for
  fitting/inspection, test never used for choices; no labels exist (no tracklets), so the choice criteria are proxies, fixed now:
  * ground: candidates = local-grid minimum filter (S2 objects.ground_height, cell 2 m) with height thresholds h0 in
    {0.15, 0.20, 0.30} m, and RANSAC plane (fit on points < 25 m, inlier 0.12 m) + grid. Chosen: highest median number of
    car-like clusters per scan among variants whose ground fraction is in 35-65 % of points < 40 m (KITTI urban scenes) and
    whose flat-wide leakage (cluster with height < 0.5 m and footprint > 4 m) <= 2 % of clusters.
  * clustering: Euclidean link radius eps(r) = e0 + e1 * r (cKDTree, no new packages), min points 5. Grid e0 in {0.4,0.6,0.8},
    e1 in {0.0, 0.01, 0.02}. Chosen on val: maximise frame-to-frame match rate at 10-40 m (association by nearest centroid after
    OXTS ego-motion compensation, distance <= 1.0 m) subject to oversize clusters (longest side > 8 m) <= 5 % of clusters.
- S1 Sanity numbers on clean train/val (and, unchanged parameters, test): ground fraction, objects per scan by range bin
  (0-10, 10-20, 20-30, 30-40, 40-60 m), median points per object by range, match rate between consecutive scans by range, ratio of
  point counts of matched objects, centroid residual after ego-motion (median, p90).
- S2 Acceptance: (a) match rate at 10-30 m >= 60 % on val at chosen parameters; (b) median centroid residual of matched
  objects <= 0.5 m; (c) oversize clusters <= 5 %; (d) car-like clusters per scan from the table within +-25 % of the S2 objects.clusters
  count on the same val scans; (e) phantom appearance (val, calibrated single-return phantoms, near/far, add/replace): >= 70 % of
  phantoms appear as ONE object (an object holding >= 60 % of the phantom points, centroid within 2 m of the phantom centre); the
  share merged with real structure and the share split are reported (not thresholds).
- S3 Runtime: median seconds per scan reported (target <= 1.0 s single process).
- S4 Tests pass (full suite); object-table cache <= 3 GB total under ../data_extra/cache_v3/WP3/.
- Ego-motion: velocity-free pose from OXTS lat/lon/yaw (Mercator, as WP1), IMU->velodyne offset from the KITTI calibration
  (T = (-0.8087, 0.3196, -0.7997), R = I; same for the whole 2011_09_26 date).

### 2026-10-22 S2b + S3 results (reports/WP3_S3.md; numbers in results/WP3/S2b/val_old_vs_fixed.json, results/WP3/S3/{choice,sanity,phantom_appearance}.json)
- S2b: lidar/singlereturn.py, phantom(single_return=True): add == replace. VAL: L1 far add 60.0 -> 1.5 %, near add v2 86.2 -> 8.7 %, box cloud v2 65.1 -> 25.7 / L1 45.6 -> 21.0. Far-add was a multi-return artefact (confirmed). Predictions: L1 far-add MET, box cloud within 5 pts NOT MET, v2 add within 10 NOT MET.
- S3 choice on val: grid ground h0 0.30 (frac 0.42, leak 0.8 %), cluster e0 0.4 e1 0.0 (all settings 57-64 % match; e1>0 only increases oversize). Sanity: a MET (60.4/63.8), b MET (0.13-0.19 m), c MET (1.6 %), d MET (ratio 1.09), e NOT MET (62 % far / 43 % near add), runtime 0.68 s/scan single process.
- Pitfalls: query_ball_point with per-point radius is too slow (6M neighbours/scan): use shell-wise query_pairs; multiprocessing under `timeout` in Git Bash fails (WinError 5); pgrep is missing in Git Bash.

## 2026-10-22 S4 L2a density / intensity vs range per object - ACCEPTANCE RULE (written before any S4 result)

Supervisor instructions (S3 approved): evaluation attacks = single-return calibrated phantoms (replace == add; budget; near 5-15 / far 15-40 m;
onset / sustained / persistent) + PointDrop + IntensitySpoof. Old multi-return add and the box cloud are v2-comparison rows only, labelled "physically
impossible on a single-return sensor" (box cloud shown single-return enforced, as in S2b). Physics stated plainly: a phantom made with the calibrated
generator matches real density BY CONSTRUCTION at equal angular size, so L2a can only catch uncalibrated / crude spoofs (dense far, sparse near, wrong
intensity) and removal / intensity attacks; it cannot see a density-matched phantom. Not seeing it is the expected, honest result.

### Method (fixed now)
- Object = row of the S3 object table. Sensor grid cells of an object (angular footprint): slots = (ring_max - ring_min + 1) * (az_span / 0.1728 + 1)
  (HDL-64E manual: 64 lasers, 0.1728 deg azimuth step at 10 Hz; 0.08-0.35 deg over 5-20 Hz; vertical ~0.4 deg between lasers).
- Expected count E = slots * p(range), p from the S2 calibrated return probability (calibration_beta.npz, 0.59-0.73). Density residual
  u = log((n + 1) / (E + 1)). Intensity statistic = int_mean. Both are turned into an improbability score by the empirical conditional CDF of CLEAN
  objects (fitted on clean train drives, cells = range bin x slots bin; object filter n >= nmin, 4 <= range <= 60 m): dens_hi = -log10(1 - F) (too dense),
  dens_lo = -log10(F) (too sparse), int_hi, int_lo likewise. Scan score = max over objects (per-object scores kept for object-level detection).
- Layers (common.layer.Layer, domain "lidar", layer_id "L2a"): dens_hi, dens_lo, int_hi, int_lo, union = max over the validation-ECDFs of the four
  scan scores (like L1Union). Threshold = 1 % of clean validation scans, tie-safe (Layer.calibrate). Object-level detection uses the same threshold on the
  object score (the injected object = the object holding the most phantom points, >= 50 % of them).

### Choices on VALIDATION only (3 drives; fixed procedure)
1. Near-phantom merging: segmentation variants S3 (e0 = 0.4 m), B (tight link 0.25 m below 20 m range), C (0.15 m below 20 m), D (B + points above 2.2 m
   ignored). Measured on validation phantoms (stride 12, calibrated, replace + budget, near + far) with the S3 definition of "appears as ONE object".
   Adopt the variant with the highest near one-object rate if it gains >= 10 points over S3 AND the far rate loses <= 5 points AND car-like objects per scan stay
   within +-25 % of S3 and oversize clusters <= 5 %; otherwise keep S3 (no further segmentation work).
2. nmin in {10, 20, 40} (object filter): maximise the MEAN validation detection over {PointDrop, IntensitySpoof, box cloud (single-return), 4 calibrated
   phantoms} at 1 % scan FA (ties -> larger nmin).
3. Thresholds: val-only vs LODO. LODO (clean train+val drives, fold = drive, object model refitted per fold, pooled out-of-fold scan scores -> tie-safe 1 %
   threshold) is adopted as primary if, on the pooled out-of-fold scores at the pooled threshold, the worst drive FA exceeds 3 % (3 x budget); otherwise the
   val-only threshold stays primary. Both are reported on test.

### Acceptance (test, ONE run; FA = clean test scans)
- A1 FA: test scan FA of the L2a union <= 2.5 % at the chosen operating point; per-drive FA reported (spread stated, no retune).
- A2 crude / removal attacks (the layer's job): IntensitySpoof >= 50 %, PointDrop >= 30 %, box cloud (single-return) >= 50 % at 1 % FA (scan level).
- A3 physics bound: calibrated replace / budget phantoms (near + far) at most FA + 10 points (matched density). A higher number is treated as a generator
  artefact (unconditional 1.5x density gap) and explained, not as a success. WP-file targets (50-400 added points >= 60 %, near sparse > 50 %) are
  predicted NOT MET for L2a alone (physics bound) and will be reported as such.
- A4 object level: for phantom attacks the caught-object rate is reported next to the scan rate (no threshold).
- A5 harness ablation on top of L1 (L1 union, each L2a part, union, L1 + L2a, via common/evaluate.py, noisy_or combiner chosen now): the combination must
  not lose more than 3 points of detection against the better single layer on any attack; FA of the combination reported.
- A6 persistent episodes (calibrated budget / replace near + far, 30 scans, 21 per class on test; v2 rolling-log-odds rule W = 10, threshold = 99th percentile of
  the statistic on clean validation sequences): detection within 3 s and median delay reported with the false-episode rate on clean test sequences. Predicted at
  chance for density-matched phantoms.
- A7 tests pass (full suite), cache <= 3 GB, L2a scoring cost per scan reported.

### 2026-10-22 S4 choice 1 result (results/WP3/S4/variants.json, validation, 47 scans, 94 phantoms per band)
Near one-object: S3 53.2 %, B 58.5, C 62.8, D 59.6; far: 51.1 / 48.9 / 52.1 / 48.9. Best gain (C) = +9.6 points < 10 required: rule => S3 kept (variant_choice.json). Merging of near phantoms stays open (documented miss); L2a works on the angular footprint of whatever cluster results.

### 2026-10-22 S4 dev round 1 (validation; results/WP3/S4/dev.json, first version) - model-form fix
First dev run: the empirical-tail score is capped at ~log10(2n) per cell and many CLEAN validation scans reach the cap (val objects outside the train range), so the scan maxima tie at the cap and the 1 % threshold cannot separate: IntensitySpoof 1 % / PointDrop 1.6 % / phantoms 0.5-1 % (= FA) for nmin 10, 20; IntensitySpoof 61 % only for nmin 40. Fix (validation-only reasoning, no test table read): beyond the reference extremes the score keeps growing with the excess in units of the cell inter-quartile range (density.tail_scores). nmin and LODO decisions re-run with the same pre-declared rules.

### 2026-10-22 S4 dev round 2 (validation) - clusters are the wrong unit; tiles (split by angular footprint)
After tail extension + n-conditioned intensity (nmin 10/20/40 on S3 clusters): IntensitySpoof 18 / 17 / 49 %, PointDrop 1 %, box cloud 5-6 %, phantoms 0.5-1 % at FA 0.7 %. Diagnosis (tmp debug on val): the injected object is a MERGED giant cluster (main phantom object: 1,100-25,000 points, ring span of the whole scene) for 7 of 12 inspected near phantoms and for box clouds, so object footprint scores are meaningless; sector attacks (PointDrop, IntensitySpoof) change a tiny part of a giant cluster. Supervisor allows splitting by angular footprint: L2a unit becomes the TILE = (cluster, 2 deg azimuth, group of 8 lasers (3.2 deg), 2 m range cell), >= 8 returns. Fixed slots per tile (8 x 2/0.1728), E = slots x p(range), same conditional-ECDF model. The segmentation-variant choice (S3 kept) is unchanged; the tile is applied on top of the S3 clusters. The object/cluster results above (dev round 1-2) are kept as "cluster-level L2a" in the report. Cache rebuilt as ../data_extra/cache_v3/WP3/S4/S3_t (pickles with objs + tiles); old S4/S3 kept for the cluster-level numbers. Nothing from test used.

### 2026-10-22/24 S4 dev rounds 3-4 (validation; results/WP3/S4/dev.json, logs/dev3.log, dev4.log) - FROZEN design before the test build
Round 3 (tiles, max only, tile nmin 8/16/32): IntensitySpoof 8 %, PointDrop 1 %, box cloud 6 %, phantoms ~1 % (FA 0.7 %). Max over ~1500 tiles per scan is dominated by clean outliers; a sector attack moves many tiles a little. Round 4 adds the count statistics cnt_* (number of tiles with improbability >= 2, ie. p < 1 %) to the union (four max + four counts, 8 stats):
val detection (1 % scan budget, nmin 8 / 16 / 32): IntensitySpoof 48.6 / 38.4 / 22.7 %, PointDrop 1.1 / 0.5 / 1.1 %, box cloud 4.3 / 3.8 / 3.8 %, phantoms 0.5-1.6 % (= FA), multi-return add near ~21 % (comparison). FA_val 0.7-0.9 %. => nmin = 8 (rule: highest mean of the 7 choice attacks).
Why box cloud and PointDrop stay low: the box cloud spreads <= 1500 points over a 4 x 1.8 x 1.5 m volume (several range cells, ~8-100 returns per 2 deg x 3.2 deg tile) - per tile not denser than a real wall; PointDrop removes returns so thin tiles fall below the 8-return validity threshold and vanish instead of looking sparse (selection effect).
LODO decision: pooled OOF FA 0.86 %, worst drive 13.6 % (> 3 %) => primary threshold = LODO (rule). Design frozen; test attack tables built next (att_test, ep_test), then ONE final run.
### Sat Oct 24 08:33:12 WCAST 2026 S4 VERDICT run started (test, once)
Run 1 crashed (KeyError cnt_* in tile-level code, before any output written); fixed object_raw to use the four per-tile max statistics only (counts exist only per scan); rerun of the same deterministic pipeline.

### 2026-10-24 S4 VERDICT (test once; results/WP3/S4/final.json, S4_tables.md, reports/WP3_S4.md)
LODO primary: clean test FA 1.63 % (A1 MET). IntensitySpoof 56.5 (MET), PointDrop 1.2 and box cloud 3.9 (NOT MET), calibrated phantoms 1.0-1.2 % (A3 MET, physics bound), multi-return add near 29.2 (comparison). Tile-level phantom detection 0.0 %. Episodes at chance (false-episode rate 16.7 % vs 0-5/21 detected). Val-only threshold FA 20.4 % on test (count statistics drift). Harness (val-only layer, pre-declared) A5 NOT MET. Pitfalls: giant merged clusters; tiles lose the attacked region when removal drops them below 8 returns; background launch in Git Bash needs nohup ... & in a single call.
