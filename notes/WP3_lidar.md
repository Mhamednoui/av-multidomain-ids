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
