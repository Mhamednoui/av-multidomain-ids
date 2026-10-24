# AV-IDS v3: multi-domain intrusion detection for an autonomous vehicle

v3 is the physics-first redesign of the AV-IDS prototype built in `../codes` (v1) and `../codes_v2`. Each of five domains (GPS, CAN, LiDAR, network, V2X) has independent layers: specification
rules (L1), physics and consistency checks (L2), models of normal behaviour fitted on clean data only (L3) and, optionally, supervised models (L4). A combiner per domain produces one
`Evidence` record (score in [0, 1], alarm flag, the layer that fired and why). Above the domains, a cross-domain layer compares the vehicle's motion as measured by CAN, GPS/IMU and LiDAR
("the witness that disagrees is the attacked one"), a label-free fusion, a temporal correlator and a response policy produce alert events. The design is in `ARCHITECTURE.md`, the plan in
`ROADMAP.md`, the rules every worker followed in `RULES.md`, and the state in `STATUS.md`.

## Honest summary

- Results are in **`RESULTS_v3.md`**, generated from the JSON files by `make_report.py`. Every number in it is traced to a file and key path in its appendix. Read it, not this README, for numbers.
- Every domain milestone that is closed is closed **PARTIAL**: some pre-registered targets were met, others were not, and the report says which. The system milestone M2 is **NOT MET**
  (false alarms do not transfer from validation to test; far too many alert events per clean hour). LiDAR (M1) is still open, so the fusion uses an interim LiDAR input.
- Two claims from earlier drafts are **corrected** (RESULTS_v3.md section 1): physics layers are not "the zero-day defence"; physics/rule layers and normal-only models are complementary.
  A V2X detector calibrated on simulated traffic flags nearly all genuine real traffic and needs per-deployment calibration.
- Evaluation protocol: splits by group (drive, capture, time block), choices on validation, thresholds at a fixed false-alarm budget, test sets scored once per step and counted
  (RESULTS_v3.md section 10). Attacks are synthetic or injected and non-adaptive; no public dataset has all five domains on one vehicle, so system results use composite streams.
- v2 numbers are shown next to v3 only with their comparability caveats (RESULTS_v3.md section 9).

## Install

Python 3.9 with the pinned packages of `requirements.txt` (numpy 1.23.5, pandas 2.2.3, scikit-learn 1.6.1, scipy 1.13.1, xgboost 2.1.4, ...). The project uses the conda environment `tf`:

```
C:\Users\nouir\miniconda3\envs\tf\python.exe -m pip install -r requirements.txt     # only for a fresh environment
```

Never use another interpreter (files written by Python 3.13 / numpy 2 cannot be read by the tf environment); `run_all.py` refuses to run steps with another Python. Run every command from this
folder (`codes_v3/`). A GPU is only needed for the LiDAR and some network steps.

## Data

Nothing is downloaded by the code. `run_all.py --list` shows, for every step, which dataset folder must exist (ids are those of `DATASETS.md`, which lists sources, sizes and checks) and whether it is present;
steps with missing data are skipped, never failed. Data folders sit next to this one: `../data_extra/<id>_<name>/` (and `../codes/data/` for the three v1 datasets).

| id | dataset | licence / terms (as recorded in DATASETS.md) |
|---|---|---|
| D02 | Car-Hacking (HCRL) | HCRL terms |
| D03 | AV-GPS-Dataset | see its paper |
| D04 | KITTI raw (23 drives of one day) | CC BY-NC-SA 3.0 (non-commercial) |
| D05 | ROAD (ORNL) | CC BY 4.0 |
| D06 | UAV Attack Dataset (live flights) | IEEE DataPort open access |
| D10 | CICIDS2017 labelled flows | **unofficial mirror** (the UNB page was restricted when downloaded); counts and keys were checked against the official labelled files, but the v2 sample is not a subset of either official file set; CIC/UNB research terms |
| D11 | can-train-and-test (DTU) | CC BY 4.0 |
| D12 | VeReMi Extension | CC BY 4.0 |
| D13 | V2AIX (real ETSI CAMs) | **non-commercial research use only, cite the paper, do NOT redistribute the dataset or modified / per-message derived files**; only abstract derivatives such as trained models and aggregate tables are allowed. The repository contains none of its data. |
| D14 | Tampa CV Pilot BSM sample | CC BY-SA 4.0 |
| D15, D27 | OpenStreetMap highways (Karlsruhe, Tampa) | ODbL 1.0, attribution (c) OpenStreetMap contributors |
| D22 | comma2k19 (one chunk) | MIT |
| D23 | CSE-CIC-IDS2018 processed CSVs | CIC research terms, cite Sharafaldin et al. 2018 |

Not available: the automotive-Ethernet dataset (IEEE DataPort login required), so there is no claim about in-vehicle Ethernet attacks.

## How to run

```
python run_all.py --list                    # every step, kind, dependencies, data needed
python run_all.py --dry-run                 # the commands that would run, in order (nothing is executed)
python run_all.py --check                   # read-only: frozen objects load and reproduce their saved freeze values (no fit, no data needed)
python run_all.py                           # default: regression, table regeneration from saved JSON, unit tests, streaming-runtime checks (validation data), RESULTS_v3.md, full test suite
python run_all.py --only WP4 --from wp4.tables
python run_all.py --refit --dry-run         # also list the re-fit / one-shot test steps
python make_report.py                       # regenerate RESULTS_v3.md only
python tests/run_tests.py                   # all unit tests
```

Default runs never re-fit a model and never score a test set that is not already a regression check. `--refit` re-runs the preparation, development, freeze and the one-shot test steps (hours); each test step
adds a labelled test exposure, so it is for reproduction, not for improving a number. Logs go to `results/WP7/logs/run_all/`. `../codes` and `../codes_v2` are never touched.

## Where things are

| path | content |
|---|---|
| `RESULTS_v3.md` | generated results document (tables, verdicts, side-by-sides, exposure counts, negative results, artefacts, limits, number trace) |
| `reports/` | milestone reports (`M1_GPS.md`, `M1_CAN.md`, `M1_NET.md`, `M1_V2X.md`, `M2.md`) and one report per step |
| `results/WP<n>/` | all result JSON; frozen domain objects in `results/WP1/frozen_gps`, `WP2/s7_domain`, `WP4/s7_domain`, `WP6/m2_system.pkl` |
| `results/WP7/S3_registry.json` | the few curated inputs of the report (rule thresholds, exposure counts, v2 reference numbers), each with its source |
| `common/`, `gps/`, `can/`, `lidar/`, `network/`, `v2x/`, `crossdomain/`, `fusion/`, `system/` | code (contracts in `common/`; streaming runtime in `system/`) |
| `tools/` | the scripts each step ran (`WP<n>_S<k>_*.py`); `tests/` unit tests; `notes/` dated working logs |

## Using the frozen domains

```
from gps.domain import GPSDomain;       d = GPSDomain.load("results/WP1/frozen_gps")
from can.domain import CanDomain;       d = CanDomain.load("results/WP2/s7_domain")
from network.domain import NetworkDomain; d = NetworkDomain.load("results/WP4/s7_domain")
from fusion.system import load_m2;      m2 = load_m2()      # {"K": system with LiDAR, "C": system without}
```

Each domain returns `Evidence` records; the input formats are described in the "frozen deployable output" section of its milestone report. Fitted objects belong to the vehicle or network they were
fitted on (the CAN models are specific to the ROAD vehicle, the network flag layer to its flow-extractor run, the V2X stack must be calibrated per deployment).
