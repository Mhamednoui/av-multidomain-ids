# WP0 S1: Repository and environment

Date: 2026-10-19    Worker: sonnet (WP0)

## Goal of the step
Local git repository, `.gitignore`, pinned `requirements.txt`, environment check, review of all docs, first commit.

## Acceptance rule (written in notes/WP0_foundation.md before any check)
1. git log shows `[WP0.S1] repository, docs`. 2. tf-env versions equal RULES.md section 4 and all requirements import. 3. Report lists doc issues.

## What was done
- `git init -b main` in codes_v3 (local, no remote); `.gitignore`; `requirements.txt` (byte copy of ../codes_v2/requirements.txt); `locks/.gitkeep` (git ignores empty folders and `locks/` must exist for the gpu.lock protocol).
- Environment check with `C:\Users\nouir\miniconda3\envs\tf\python.exe` (script outside the repo).
- All docs read (START_HERE, RULES, STATUS, ROADMAP, ARCHITECTURE, DATASETS, ORCHESTRATION, notes/ORCHESTRATOR, reports/README, WP0-WP7).
- No download, nothing in ../codes or ../codes_v2 touched. Disk free 52 GB.

## Results
| Package | RULES.md | Found | OK |
|---|---|---|---|
| Python | 3.9.21 | 3.9.21 | yes |
| numpy | 1.23.5 | 1.23.5 | yes |
| pandas | 2.2.3 | 2.2.3 | yes |
| xgboost | 2.1.4 | 2.1.4 | yes |
| scikit-learn | 1.6.1 | 1.6.1 | yes |
| scipy | 1.13.1 | 1.13.1 | yes |
| imbalanced-learn / shap / matplotlib / seaborn / joblib | requirements.txt | 0.12.4 / 0.49.1 / 3.9.4 / 0.13.2 / 1.4.2 | yes |

Acceptance: MET (commit verified with `git log`, see below).

## Doc issues found (docs not edited; proposed fixes)
1. Dates inconsistent: DATASETS/ROADMAP/WP5 say "20 Oct 2026" and STATUS rows say 2026-10-20, but ORCHESTRATOR decisions and the machine date are 2026-10-19. Propose: use one date convention (real date).
2. DATASETS.md header and RULES 3.4 say downloads need the user's approval of the size; ORCHESTRATOR.md (19 Oct) says downloads are pre-approved with >= 15 GB free. DATASETS section 4 says keep >= 10 GB free. Propose: align RULES 3.4 and DATASETS to "pre-approved, >= 15 GB free, log size and licence".
3. WP0 S3 says "detection per attack type" matching v2 `detection_by_attack`, but that JSON has two versions: row level (drift 0.336, accel 0.458, jump 0.719, freeze 0.866) and run level (drift 0.386 ...). WP1 baseline quotes run-level numbers (jump 100%, freeze 89%). Propose: S3 states which one (row level `detection_by_attack` and `false_alarm_rate_clean_runs` 0.0158 are the natural ones).
4. WP0 S3 says "same KITTI tracks and split"; the split is only defined in v2 `lidar/train.py` (train 13 / val 3 / test 7); WP1 S1 lists the test and val drive ids explicitly, WP0 does not. Propose: list them in WP0 S3 (or ARCHITECTURE).
5. `.gitignore` spec "model files > 50 MB" cannot be a pattern; I added extensions (*.joblib, *.h5, *.keras, *.pt, *.onnx) and rely on a pre-commit size check by hand. `*.npz`/`*.pkl` ignored means test fixtures in those formats cannot be committed (use csv/json fixtures). Propose: add to RULES section 7.
6. Git does not track empty folders: the owner folders (gps/, can/, ...) have no content yet; only `locks/.gitkeep` was added (my paths). Owners add files when they start.
7. ARCHITECTURE section 4 says "DATA = ../codes/data" but D04 (21 KITTI drives) and D05/D06 live in ../data_extra; config.py (S2) must expose per-dataset paths. Gap only, not contradiction.
8. ARCHITECTURE section 3: `Layer.score(samples) -> list[Evidence]` "batch or one sample; causal only": batch scoring of a whole file with a stateful layer needs a defined `reset()` per group; not specified who calls reset between drives (harness?). Propose: S2 harness resets per group; document in evaluate.py.
9. START_HERE does not list ORCHESTRATION.md (fine for workers) and ROADMAP is item 7 although workers need its section 5 targets; no contradiction.

## Problems, surprises, open questions
None blocking. Question for supervisor: accept items 3 and 4 as clarifications for S3 (needed before S3 starts).

## Proposed next step
WP0 S2 (common code), after review.
