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

## S5 (2026-10-24, worker sonnet): L2b free space / occlusion per object
Design: lidar/occlusion.py (see-through returns: far returns between two returns of one cluster, same laser/neighbouring azimuths (row) or same azimuth/neighbouring lasers (column), counted per tile), lidar/occlusion_build.py, tools/WP3_S5_*.py. Attacks: the 9 S4 attacks (same seeds, scans identical to S4) + 4 best-case attacker phantoms fl_{replace,budget}_{near,far} (return on EVERY ray through the silhouette, no dropout; seeds [97,d,i]); episodes: S4 kinds + epfl_replace near/far.
Physics prediction (written before any result): with single-return physics a complete phantom removes the real returns behind it, so the frustum behind it is empty: fl_* phantoms are consistent and predicted at FA. The calibrated generator drops rays (Beta dropout); a dropped ray keeps its REAL farther return, visible through the silhouette: predicted detectable ONLY because of those holes (a property of the attack design, not general). A real object's missing return gives no return at all. PointDrop/IntensitySpoof predicted at FA.
### S5 ACCEPTANCE RULE (written before results)
- Choice on validation (3 val drives, attacks every 3rd scan): variant (margin in {0.5,1,2} m, gap in {0.5,1} deg) = highest mean detection at 1 % val scan FA over {4 calibrated phantoms, single-return box cloud}; scan statistics tot/maxf/cnt/maxn, union of clean-ECDF ranks (like L2a).
- Threshold: pooled over the 16 train+val clean drives (tie-safe 1 %), nested per-drive LODO FA reported as spread. Test run ONCE.
- B1 clean test FA <= 2.5 %.
- B2 physics: fl_* phantoms <= FA + 10 points; PointDrop, IntensitySpoof <= FA + 10; calibrated phantoms with dropout and box cloud: reported, no threshold (any gain is attributed to holes and stated as generator-dependent).
- B3 WP-file targets (50-400 added points >= 60 %, near sparse > 50 %) reported met / not met.
- B4 tile level (phantom tiles = >= 50 % injected) reported. B5 harness L1 + L2a_int + L2b (noisy_or, 1 % budget): combination loses <= 3 points vs best single layer on any attack. B6 episodes within 3 s with false-episode rate. B7 tests pass, extra cache <= 2 GB, cost/scan.

## S6 L2c background model + L2d ego-compensated tracking (worker sonnet, 2026-10-24, parallel with S5)
### 2026-10-24 S6 design and ACCEPTANCE RULE (written before any validation / test result; only a 5-scan smoke timing of drive 0011 was seen)
Design: lidar/background.py (Img: count / nearest return per 64 ring-bins x 1 deg azimuth, previous scan moved by OXTS planar pose, miss_* statistics = 1 - min window ratio / median window ratio of observed to expected returns, 10 / 20 deg windows, all rings or groups of 8 rings; Poisson shortfall miss_z20), lidar/track.py (cell-level hypotheses static-world / sensor-fixed / new / gone: app_*, fix_*, van_* counts and largest blob), lidar/background_build.py (features of clean, attacked (S4 attack set, seeds [83,d,i]), persistent episodes: S4 sensor-fixed (seeds [89,d]) and NEW world-fixed episodes (seeds [97,d]; phantom box moved with the ego-motion = a parked-car-like persistent phantom)). Layers = StatUnion (max of clean-ECDF ranks), L2c = miss_*, L2d = app_*, fix_*, van_*. Thresholds: pooled clean scans of the 16 train+val drives (parameter-free statistics, so pooled = out of fold), tie-safe 1 %; plus leave-one-drive-out FA on those 16 drives. Choices on validation: which statistics enter each union (rule: keep a statistic only if it raises mean detection of its target attacks by >= 3 points on validation at the pooled threshold, FA_val <= 2 %), episode statistic = v2 rolling log-odds W = 10. Test: ONE verdict run.
Acceptance:
- A1 clean test scan FA of each layer (L2c, L2d) <= 2.5 %, worst drive reported (not a pass criterion).
- A2 L2c PointDrop >= 30 % at test (scan level, 1 % budget).
- A3 physics-bound check: L2c on replace / budget phantoms and IntensitySpoof within FA + 10 points (removal model must not see them). L2d on onset phantoms is predicted ABOVE the bound for large near replace phantoms (new surface in free space): reported as a genuine appearance detection, not an artefact, because the check is pure geometry; prediction: near replace >= 30 %, far budget at most FA + 10.
- A4 sensor-fixed persistent episodes (S4 kinds, 21 each): L2d detects >= 50 % within 3 s on episodes with ego displacement > 0.5 m per scan; world-fixed persistent episodes: no pass criterion, PREDICTED that detection comes from the first scans (appearance) only and sustained-scan detection equals FA (physics statement: a well-made persistent phantom is not caught by tracking alone). Report onset (step 1), sustained (steps 2-30), within-3 s episode detection and median delay.
- A5 false-episode rate on clean test windows <= 10 %.
- A6 harness ablation on top of L1 + L2a(intensity): L1, L2a_int, L2c, L2d, combinations (common/evaluate, noisy_or fixed beforehand); the full combination must not lose more than 3 points against the best single layer on any attack, combined FA <= 3 %.
- A7 tests pass (full suite), added cache <= 2 GB, scoring cost per scan reported.
### 2026-10-24 S6 validation rounds (results/WP3/S6/dev_round1.*, dev.*; logs/dev2.log)
Build: all clean scans (23 drives), val attacks (every 3rd scan), val episodes (2 per kind and drive, sensor-fixed + world-fixed) in ../data_extra/cache_v3/WP3/S6 (a few MB); 0.08 s/scan clean, 1.3 s per full attack set.
Round 1 (single statistics, threshold = 1 % of pooled clean train+val): miss_w20 PointDrop 91.4 % (val FA 0.9 %), miss_w10 81.6, miss_z20 77.3; the ring-group variants miss_g10 / miss_g20 SATURATE at 1.0 on clean scans (some ring group has zero returns in a window: elevation-bin edges vs pitch) = ties, detect 0 %: discarded by the rule. app_cc: near replace phantom 60 %, multi-return near 44 %, everything else at FA; fix_tot sensor-fixed episodes 59 % near replace only. LODO-FA worst drive up to 14 % (miss_w10) / 7.8 % (app_cc) / 41 % (fix_tot): drive-level shifts (see report). World-fixed episodes: sustained steps at FA for every statistic (physics prediction).
Round 2: my selection objective for L2d had ignored the persistence (scan-level attacks have a clean predecessor, so fix_* can never fire there). Changed BEFORE any test scoring, validation only: L2d objective = mean of the 4 phantom scan attacks and the sustained steps of the 4 sensor-fixed validation episode kinds (ego displacement > 0.5 m). Chosen: L2c = {miss_w20}; L2d = {app_cc, fix_tot} (dev.json).
### Sat Oct 24 14:46:19 WCAST 2026 S6 VERDICT run started (test, once)

### 2026-10-24 S6 VERDICT (test once; results/WP3/S6/final.json, S6_tables.md, harness_*.json/md; reports/WP3_S6.md)
L2c = {miss_w20}, L2d = {app_cc, fix_tot}; thresholds = pooled clean train+val 1 % (tie-safe). Test FA L2c 2.10 % (worst drive 0039 6.1 %), L2d 0.20 %. PointDrop 87.3 % (L2c). Phantoms and IntensitySpoof in L2c at FA (1.8 %); L2d: near replace 32.5 %, multi-return near 34.5 %, far/budget 0.2 %, box cloud 2.5 %. Episodes (3 s, 21 per kind): sensor-fixed near replace L2d 11/21 (8/14 with ego moving), all other sensor-fixed kinds 0/21; world-fixed: sustained steps at FA (0.0-0.2 %), the near-replace detections (10/21) are the appearance scan only. False-episode rate L2c 10.4 %, L2d 2.1 %. Harness (noisy_or fixed beforehand): the 4-layer combination loses PointDrop (6.9 vs 87.5 alone) and IntensitySpoof (28.6 vs 51): A6 NOT MET; the noisy_or sum of four moderate clean scores raises the 1 % threshold on 3 validation drives (see report). Acceptance: A1 MET, A2 MET, A3 MET, A4 NOT MET (one of four kinds), A5 L2c 10.4 % NOT MET (marginal) / L2d MET, A6 NOT MET, A7 MET. Pitfalls: ring-group statistics miss_g* saturate at 1.0 on clean scans (ties); LODO-FA of single small drives (0048 has 21 scans, 0013) is 14-29 %: drive-level shifts; noisy_or with several layers dilutes a strong single layer: S9 should compare max vs noisy_or on validation.

## S7 L3 normal-only object statistics + L4 retrained v2 descriptor model (worker sonnet high, 2026-10-24, parallel with S5)
### 2026-10-24 S7 design and ACCEPTANCE RULE (written before any L3 / L4 result; only timing of describe() and of the S4 attack generator was seen: 33 ms per scan, 1.2 s per 9-attack scan)
Files (all new): lidar/learned.py (L3), lidar/learned_l4.py (L4 rows, XGBoost, controls), lidar/learned_eval.py (stack combination), tools/WP3_S7_*.py, tests/lidar/test_learned*.py, results/WP3/S7/, cache ../data_extra/cache_v3/WP3/S7 (<= 2 GB).
L3 (normal-only, fitted on CLEAN scans only, no labels): unit = S3 cluster ("object", >= 10 points; S4 tile tables carry only 3 statistics, already modelled conditionally by L2a, so a tile model would repeat L2a). Features: range, log point count, count residual u = log((n+1)/(E+1)) (E from the S2 calibration, as in L2a), extent (length, width, height, z_bottom), angular footprint (az_span, elev_span), ring coverage (n_rings, n_rings / ring span), intensity mean / std, carlike flag, track class (matched to the previous scan after OXTS ego-motion: matched flag, displacement, log count ratio; lidar.assoc). Three models (robust-covariance Mahalanobis, isolation forest, small autoencoder = sklearn MLPRegressor) x two feature sets (with / without track class). Scan score = max object score and the number of objects above the clean-object 99.9 % quantile, ECDF union (like L2a). Choice among the 6 on VALIDATION: model fitted on the 13 train drives, threshold 1 % of val clean scans, criterion = mean detection over the six physically consistent attacks (ph_replace/budget x near/far, PointDrop, IntensitySpoof). Verdict threshold: LODO, 16 train+val drives, pooled out-of-fold clean scores, 1 %, tie-safe.
L4: the v2 descriptor (211 + 218 scan-to-scan features, copied lidar.features) + XGBoost 4 classes (Normal, PointDrop, IntensitySpoof, Phantom) trained ONLY on the physically consistent attack set: calibrated single-return phantoms (replace / budget, near / far; all four merged in the class Phantom, type tag kept), PointDrop, IntensitySpoof; onset / sustained 50 %/50 % as in v2; every 2nd scan of the train drives, one draw per type. Multi-return add and box cloud are NEVER training data (comparison rows only). Score = 1 - P(Normal). Hyperparameters: random search (12 configs, seed 42) on validation, criterion mean detection of the six physical attacks at the val 1 % point. Threshold: LODO over train+val (16 folds, a model per fold, out-of-fold clean scores pooled), 1 %, tie-safe; final model refit on train+val with the chosen hyperparameters and number of trees. Comparison rows (not part of the stack): L4_v2 (v2 training classes incl. box cloud, same pipeline), L4_nophantom (Normal + PointDrop + IntensitySpoof only: tests the v2 pitfall "a class physically indistinguishable from normal must not be a training class").
Leakage controls (fixed now): (C1) scan-level shuffled-label null control: labels of all training rows (Normal and attack) permuted, 5 seeds (11..15), same hyperparameters, AUC (attack vs normal, eval-val set); BOUND mean AUC <= 0.55. L3 uses no labels, so a null control does not apply; its analogue is the FA/AUC on clean drives. (C2) feature importance (XGBoost gain, total and per class via one-vs-Normal sub-models, by feature group): RED FLAG if one feature holds >= 25 % of the total gain, or if the top-3 features of the Phantom class cannot be explained by the physics of a single-return phantom; plus an ablation (retrain without the top-5 features; if validation detection falls by more than half, report as dependence on a few features). (C3) leave-one-attack-type-out on validation: types {Phantom (all four), PointDrop, IntensitySpoof} plus the pair "budget phantoms" (train without ph_budget_*): train without the type, score it at the val 1 % point; COLLAPSE if held-out detection <= val FA + 5 points while the in-distribution detection is >= 3x higher; then the model learned the generator, and it is reported as such.
Acceptance (test, ONE verdict run; FA = clean test scans):
- A1 L3 and L4 clean test FA <= 2.5 % at the LODO threshold; per-drive spread reported.
- A2 L4 in-distribution: PointDrop >= 60 %, IntensitySpoof >= 80 %. PREDICTED: single-return phantoms (replace / budget, near / far) at FA + 10 points or less (physics bound; anything above is not credited as physics but flagged and checked with C3).
- A3 C1 mean null AUC <= 0.55 (validation). A4 C2 no red flag. A5 C3 reported for every type; collapse stated plainly.
- A6 L3: predicted IntensitySpoof detectable (intensity statistics), near replace phantoms only through merged-cluster extent, far / budget at FA + 10, PointDrop <= 30 %. No pass threshold, reported against the prediction.
- A7 "Adds beyond the physics layers": physics stack = L1 + L2a(intensity) + L2c + L2d (S6 harness layers; S5 only if committed before the verdict, otherwise stated), label-free combiner (max or noisy_or, chosen on validation), threshold 1 % of pooled out-of-fold clean scans. X (L3, L4, L3 + L4) ADDS if physics + X beats physics by >= 3 points on at least one of the six physical attacks, paired bootstrap 95 % CI of the difference excludes 0, and the combined test FA stays <= 2.5 %.
- A8 persistent sensor-fixed episodes (S4 kinds, 21 each, 3 s rule, threshold = 99th percentile of clean out-of-fold windows): detection per kind and false-episode rate (target <= 10 %), reported; a kind counts as detected if >= 50 %.
- A9 WP-file targets (50-400 added points >= 60 %, near sparse > 50 %): reported met / not met, predicted NOT MET (physics bound).
- A10 full test suite passes, S7 cache <= 2 GB, scoring cost per scan reported.
### 2026-10-24 S7 build + L3 validation round (S7 worker)
Machine saturated (9 python processes on 6 cores / 12 threads, mine get ~0.45 CPU each): L4 row build (tools/WP3_S7_build_l4.py, 3 procs) and L1 train statistics (tools/WP3_S7_l1train.py, 2 procs; the S4 clean tables hold L1 statistics only for val / test drives) run in the background, expected ~1 h.
Checks before any result: regenerated S4 evaluation attacks (seeds [83, d, i]) match the S4 tables exactly (n_inj equal for 234/234 scans of test drive 0052; sensor-fixed episodes 360/360), so L4 rows and the S4 / S6 / L3 scores refer to the same attacked scans (tests/lidar/test_learned.py::test_eval_rows_reproduce_s4_attack_draws).
L3 features built from the S4 object tables (tools/WP3_S7_build_l3.py, 14 s, cache 0.2 GB): 17 columns (14 single-scan + 3 track class: matched 71 % of clean objects, displacement, log count ratio).
L3 validation round (results/WP3/S7/dev_l3.json, logs/dev_l3.log; fitted on the 13 train drives, threshold 1 % of val clean scans, val FA 0.7-0.9 %): mean detection of the six physical attacks cov 1.6 %, iforest 2.3 %, AE 6.3 % (base), with track class 1.6 / 1.8 / 2.3 %. Chosen by the pre-declared rule: base features + autoencoder (IntensitySpoof 29 %, PointDrop 5 %, phantoms 0.5-1.6 % = FA). Object-level exploration (validation only, not a choice criterion): AUC of phantom objects vs clean objects with n >= 50 points: near replace 0.83 (AE), far 0.52, budget near 0.65, budget far 0.51 - the far phantoms are matched to real objects, as the physics bound says; the scan maximum over ~225 objects dilutes the near signal below the 1 % FA threshold.
### 2026-10-24 S5 build + validation round (results/WP3/S5/dev.json, logs/dev.log)
Design notes: first smoke test (gap 1 deg, column span 4) gave huge clean see-through counts (laser assignment is ambiguous for nearby lasers; neighbours at 1 deg cross whole structures); tightened BEFORE any attack table build: row gap {0.4, 0.8} deg (a dropped ray = one missing beam = span 0.36 deg), column span 2 lasers, plus a strict same-surface flag (|dr| <= 0.25 + 0.01 r). Tile tables of 23 clean drives and 3 val drives x 13 attacks built (4 procs, ~2 h on the loaded machine).
Validation (3 drives, 185 source scans per attack, FA_val 0.7 %): all 12 variants, chosen (margin 0.5 m, gap 0.8 deg, loose) objective 0.086 = mean of ph_replace_near 20.0, far 0.5, ph_budget_near 4.3, far 0.5, box cloud 17.8 %. Others: fl_* (best-case attacker) 0.5 % (= FA, as predicted), PointDrop 0.5, IntensitySpoof 0.5, multi-return add (comparison, impossible) near 82.7 / far 38.4 (the original CARLO case). Stat alone (maxn) near-replace 28.6 %. No further tuning (rule). Cache shrunk to the chosen variant's columns afterwards (tools/WP3_S5_shrink.py), att_test + ep_test then built with shrink on.
Dry run of tools/WP3_S5_final.py on validation drives (S5_DRY=1, no test data read) passed (dry_final.json): confirms code paths only. Nested LODO FA on held-out drives is very uneven (0027: 100 %, 0013: 13 %, others <= 2.4 %): two drives (0027 road with fences / 0013) carry far more see-through returns than the rest.
### 2026-10-24 S7 L4 validation round (results/WP3/S7/dev_l4.json, dev_stack.json, logs/dev_l4.log, dev_stack.log; test not read)
Rows: 10321 training rows (2575 Normal, 1291 PointDrop, 1291 IntensitySpoof, 5164 Phantom), built in 100 min on the saturated machine (tools/WP3_S7_build_l4.py; regenerated S4 attacks reproduce n_inj exactly, episodes 360/360).
Search (12 configs, criterion mean detection of the six physical attacks at val 1 %): best depth 8, lr 0.2, colsample 0.5, 18 trees (all configs val FA 1.1 %); chosen model on validation: PointDrop 95.7 %, IntensitySpoof 100 %, near replace phantom 41.6 %, far replace 1.6 %, budget near/far 2.7 / 0.5 % (FA 1.1 %), AUC 0.752 over the six. Comparison attacks: box cloud 13.0 %, multi-return add near/far 24.9 / 4.3 %.
C1 null control (5 seeds): AUCs 0.517 0.505 0.521 0.505 0.532, mean 0.516 <= 0.55: MET.
C2 importance: per class one-vs-Normal. PointDrop: sect_2nd_min_ratio 32.8 %, sect_min_ratio 12.5 %, n_sparse_sect 10.1 % (sector counts: exactly the physics of a blind sector). IntensitySpoof: sect_hifrac_max 45.2 %, sect_imean_peak 23.6 % (bright sector). Phantom: spread (top feature d_double_return_frac 4.3 %); the top features are the double-return / patch features and scan-to-scan differences, i.e. range discontinuities next to the injected surface; no single feature dominates (total top-1 share in importance_dev.csv / dev_l4.json). Ablation (retrain without the top-5): mean detection 46.2 % vs 40.4 % with them (does not collapse).
C3 leave-one-type-out (val): PointDrop 95.7 -> 0.0 %, IntensitySpoof 100 -> 0.0 %, replace phantoms near 41.6 -> 0.5 %: COLLAPSE (held-out <= FA + 5 with in-distribution >= 3x). As expected for a supervised multi-class model: it detects the families it was trained on and nothing else. Budget phantoms (2.7 % in-distribution) are at FA either way.
Variants (val): L4_nophantom (no phantom class): near replace 2 %, PointDrop 97 %, IntensitySpoof 100 %, i.e. the 42 % near-replace detection exists only because the Phantom class was trained, and it is concentrated on the dense near replace phantom (the S2 generator is ~1.5x denser than real objects). L4_v2 (box-cloud class): PointDrop 87 %, IntensitySpoof 100 %, near-replace 2 %, box cloud 26 %, multi-return add near 71 %.
Stack (dev_stack.json, train-fitted models, reference = val clean): label-free max of ECDF ranks wins over noisy_or (mean over four stacks and six attacks 28.4 vs 24.4 %): COMBINER = max. FINDING before any test result: the max over four layers at 1 % TOTAL false alarms gives each layer only ~0.25 % FA, so the physics stack loses PointDrop (L2c alone 91 % at its own 1 % -> 0.5 % in the stack on this small 549-scan reference): the dilution found in S6, now with max. Added a reference row to A7 (decided before the verdict run, validation evidence only): X alone against the BEST SINGLE physics layer per attack (each at its own 1 %), paired bootstrap, so that an attack lost to dilution is not credited to L3 / L4.
Bugs fixed on the way: fit_xgb failed when a class was missing (leave-one-type-out): labels are remapped contiguous (class 0 = Normal stays 0).

### Sat Oct 24 19:39:21 WCAST 2026 S7 VERDICT run started (test, once): tools/WP3_S7_final.py; design frozen: L3 = base features + autoencoder, L4 = depth 8 / lr 0.2 / 18 trees, combiner = max, A7 supplemented by the best-single-physics-layer reference (all fixed on validation).
### 2026-10-24 S7 VERDICT (test once; results/WP3/S7/final.json, S7_tables.md, objects_final.json, cost.json; reports/WP3_S7.md)
Single layers at own 1 % LODO threshold (test FA / PointDrop / IntensitySpoof / near replace): L3 1.7 % (worst drive 0001 21.5 %) / 3.1 / 27.3 / 2.2; L4 0.7 % / 90.8 / 100.0 / 19.2 (far and budget phantoms 0.6-0.8 = FA); L4_nophantom 1.0 / 93.1 / 100 / 0.8; L4_v2 0.7 / 84.9 / 98.8 / 0.8. Physics layers: L2c PointDrop 87.3, L2a IntensitySpoof 65.3, L2d near replace 32.5.
Stacks (max, 1 %): physics FA 1.2 %, PointDrop 27.6, IntSpoof 51.6, near replace 17.8; + L4 FA 1.5 %: 85.7 / 99.4 / 22.4; + L3: PointDrop 6.3 (dilution), IntSpoof 54.7. Against the best single physics layer per attack: L4 PointDrop +3.5 [0.4, 6.7], IntensitySpoof +34.7, near replace -13.3; L3 below on every attack.
Leakage: null mean AUC 0.516 MET; top-1 importance 21.0 % (sect_hifrac_max, physical) no red flag; leave-one-type-out COLLAPSE (PointDrop, IntensitySpoof, near replace 41.6 -> 0.5 %). L4 near-replace detection exists only through the trained Phantom class (L4_nophantom 0.8 %), generator-dependent.
Episodes: near replace L4 8/21, L2d 11/21, physics stack 11/21, physics + L4 12/21; others <= 6/21. False-episode rates L3 8.3, L4 4.2, physics + L3 + L4 12.5 %.
Cost per scan: L3 7 ms (object scoring), L4 64 ms descriptor (loaded machine) + 0.8 ms predict.
Decision for S9 (worker proposal): L3 out; L4 optional (seen families only, not zero-shot); max at 1 % total FA dilutes strong layers - allocate FA per layer on validation. S5 not in the stack (not committed at the time).
### Sat Oct 24 21:53:39 WCAST 2026 S5 VERDICT run started (test, once)
### 2026-10-24 S5 VERDICT (test once; results/WP3/S5/final.json, S5_tables.md, reports/WP3_S5.md)
Clean test FA 0.46 % (B1 MET). fl_* 0.6 %, PointDrop 0.6, IntensitySpoof 0.6 (B2 MET). Calibrated replace near / far 6.3 / 0.8, budget 1.0 / 0.6 (B3 NOT MET, physics). Box cloud 18.8, multi-return add near / far 69.4 / 28.4 (comparison). Tile level ~0 for single-return phantoms. Episodes 3/21 replace near, others 0; false episodes 0/48. Harness all 3 layers FA 1.37 %, loses <= 2.5 points to the best single layer (B5 MET). Nested LODO FA bad for drives 0027 (100 %) and 0013 (13 %). Extra cache 0.79 GB, 0.39 s/scan. Tests 454/454.
