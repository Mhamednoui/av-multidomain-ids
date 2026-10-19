# Architecture v3: system, contracts, ownership

The contracts in sections 2-4 are implemented by WP0 in `common/` and are FROZEN after M0.
Changes only through `reports/REQUEST_*.md` and the supervisor.

## 1. System

```
                 raw domain streams (one sample unit per domain, time-stamped)
 network: flow (+ host time window) | CAN: frame (+ 1 s window) | GPS: fix at 1 Hz + IMU |
 LiDAR: scan at 10 Hz | V2X: received message (BSM / CAM)
          │
          ▼  per domain, in parallel, all stateful layers support reset()
   L1 rules ─┐
   L2 physics├──► Evidence list ──► DomainCombiner ──► domain Evidence (layer="combined")
   L3 normal ┤                                               │
   L4 superv ┘                                               │
          │ MotionEstimate (CAN wheel speed, GPS/IMU, LiDAR odometry, V2X self-reports)
          ▼                                                  ▼
   crossdomain/ motion witnesses ──► cross-domain Evidence ──► fusion/ (system score,
                                                                 2% FA budget, explanation)
                                                                         │
                                                       temporal correlator ──► response
```

## 2. Evidence (common/evidence.py)

```python
@dataclass
class Evidence:
    domain: str      # "network" | "can" | "gps" | "lidar" | "v2x" | "cross"
    layer: str       # "L1" | "L2a" | "L2b" | ... | "L3" | "L4" | "combined"
    name: str        # stable id of the check, e.g. "gps.cusum_innovation"
    t: float         # stream time of the sample (seconds)
    score: float     # 0..1, monotone in "attack-ness"; calibrated on validation (see 4)
    alarm: bool      # score >= this check's threshold at the agreed false-alarm budget
    reason: str      # one plain sentence when alarm is True, else ""
    details: dict    # numbers behind the decision (observed, expected, residual, ...)
    sample_id: str   # links back to the sample (e.g. "<drive>/<scan>", "<capture>:<row>")
```

## 3. Layer and combiner (common/layer.py, common/combiner.py)

```python
class Layer:
    domain: str; name: str
    kind: str                     # "rule" | "physics" | "normal_model" | "supervised"
    needs_attack_data: bool
    def fit(self, train, val=None): ...            # rules may only calibrate on normal data
    def calibrate(self, val_normal, budget): ...   # sets self.threshold (tie-safe, see 4)
    def reset(self): ...                           # clear stream state (new drive / capture)
    def score(self, samples) -> list[Evidence]: ...  # batch or one sample; causal only
    def save(self, folder) / load(folder): ...

class DomainCombiner:
    # inputs: Evidence of all layers of one domain for the same sample
    # methods (chosen on validation): "noisy_or" of calibrated scores, "logistic" (fitted on
    # validation, group-aware halves), "max"; output Evidence(layer="combined") whose reason
    # lists the layers that fired, strongest first.
```

`MotionEstimate` (common/motion.py): `t, source, speed, yaw_rate, displacement(dx, dy over
the last second), sigma` published by any domain that observes ego motion.

## 4. Shared conventions

- Budgets: domain layers and combiners: 1% of normal samples on validation; system: 2%.
- Threshold rule (v2 bug fix): threshold = value just above the (1 - budget) quantile of the
  validation normal scores (`np.nextafter`), so ties cannot exceed the budget.
- Validation used for combiners / fusion is split into halves BY GROUP (drive, session,
  capture), never by random rows (v2: random halves let a meta-classifier memorise drives).
- Score calibration: each layer maps its raw statistic to 0..1 by the empirical CDF of the
  validation normal scores (score = fraction of normal samples below) unless it has a natural
  probability; this makes layers comparable inside a combiner.
- Evaluation harness (common/evaluate.py): given Evidence for val + test with labels and
  groups, writes `results/<WP>/<name>.json` with, per layer and combined: AUC, detection per
  attack type at the budget, false alarms on test normal data, detection delay for streams,
  and the ablation (each layer alone, all, all-but-one).
- Splits: stored as lists of group ids in `results/<WP>/splits.json`; never by row.
- Paths (common/config.py): DATA = ../codes/data (env AVIDS_DATA), DATA_EXTRA = ../data_extra
  (env AVIDS_DATA_EXTRA), RESULTS = results/, SEED = 42.

## 5. Reuse from v2 (copy, never import, never modify ../codes_v2)

| Need | v2 source |
|---|---|
| metrics, train_xgb (GPU random search), seeds | codes_v2/common/ |
| CAN stream features (batch == streaming, tested) | codes_v2/can/features.py |
| ROAD parsing, labels (checked vs ROAD's own labels), window alerts | codes_v2/can/road_external.py, road_windows.py |
| GPS features, KITTI OXTS 1 Hz resampling, receiver noise, attacks, dead reckoning | codes_v2/gps/features.py, kitti_external.py |
| UAV case study (GPS vs IMU) | codes_v2/gps/uav_case_study.py |
| LiDAR descriptor, patch features, ray-cast phantoms, drive split, sequences | codes_v2/lidar/features.py, train.py, raycast_test.py, sequence.py |
| network cleaning (duplicates, conflicting labels) | codes_v2/network/train.py |
| fusion (budget, group-aware halves, tie fix), correlator, response | codes_v2/fusion/, temporal/, response/ |
| test runner | codes_v2/tests/run_tests.py |

## 6. Folder ownership

| Folder | Owner | Notes |
|---|---|---|
| common/, tests/common/, tests/run_tests.py | WP0 | frozen after M0 |
| gps/, tests/gps/ | WP1 | |
| can/, tests/can/ | WP2 | |
| lidar/, tests/lidar/ | WP3 | |
| network/, tests/network/ | WP4 | |
| v2x/, tests/v2x/ | WP5 | new domain |
| crossdomain/, fusion/, tests/crossdomain/, tests/fusion/ | WP6 | |
| system/, tests/system/ | WP7 | runtime, simulation, response |
| results/WP<n>/, notes/WP<n>_*, reports/WP<n>_*, tools/WP<n>_* | that WP | |
| STATUS.md | each WP its own row; supervisor the rest | |
| START_HERE, RULES, ROADMAP, ARCHITECTURE, DATASETS, ORCHESTRATION, workpackages/ | supervisor | workers propose changes via REQUEST files |
| locks/ | everyone | gpu.lock protocol (RULES 3.1) |
