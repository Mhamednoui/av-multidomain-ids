# WP7 S3: run_all.py, make_report.py, RESULTS_v3.md, README (started early)

Date: 2026-10-24    Worker: sonnet (medium, T2)    State: REVIEW. No test set was scored in this step.

## Summary
- `run_all.py` runs every step in dependency order (WP0 regression, WP1..WP5 tools, WP6 fusion, WP7 runtime checks and report, full tests). Flags `--list`, `--dry-run`, `--only`, `--from`, `--refit`, `--keep-going`, `--check`.
  Default = regression, table regeneration from saved JSON, unit tests, streaming-runtime checks (validation data), report. Prep / dev / build / eval steps (re-fits, one-shot test runs) need `--refit` and
  print that each eval step adds a test exposure. Missing data is printed with its DATASETS id and the step is SKIPPED (nothing downloaded; `../codes`, `../codes_v2` never written). Refuses non-3.9 Python.
- `--check` is read-only and passes: GPS / CAN / network frozen objects load and equal their saved freeze checks (score difference 0, alarm mismatches 0), V2X runtime thresholds equal WP5 S6, M2 system loads and equals its config, WP7 S1 acceptance all MET, report inputs complete.
- `make_report.py` writes `RESULTS_v3.md` from results JSON only (+ `results/WP7/S3_registry.json` for curated inputs: rule thresholds, exposure counts, v2 reference numbers, each with a source).
  786 printed values, each traced in Appendix A (file, key path, kind json / curated / derived); a scan finds no untracked number; 0 missing keys in closed milestones; second run byte-identical.
- Sections: status and the two corrected claims; M1-GPS, M1-CAN, M1-NET, M1-V2X (+V2AIX) with rule verdict tables (MET / NOT MET), headline tables with CIs, layer tables, ablations; M1-LiDAR, M2 addendum,
  M3 simulation = PENDING (they fill from `results/WP3/S9/acceptance.json`, `results/WP6/s5b_acceptance.json`, `results/WP7/S2_acceptance.json` as soon as those exist); M2; v2 side-by-sides with caveats;
  test-exposure counts; negative results; artefacts; data limits.
- README.md written (what v3 is, install, data and licences incl. V2AIX non-commercial / no redistribution and the CICIDS mirror caveat, how to run, where results are, honest summary).
- Tests: `tests/system/test_run_all.py` (10), `test_make_report.py` (8). Full suite: 440 passed, 0 failed.

## Acceptance (rule written before the report existed: notes/WP7_system.md "S3 start")
| item | result |
|---|---|
| R1 run_all: --list, --dry-run (nothing executed, tested by patching subprocess), valid topological and WP order, scripts exist, no ../codes writes, no refit by default, --only / --from, --check | MET |
| R2 make_report: JSON only, deterministic, every number traced (scan + appendix), PENDING sections, verdicts from acceptance JSON or computed against registry thresholds | MET |
| R3 tests incl. full suite | MET |
| R4 README content | MET |

## Findings / open points
- Rule counts in the status table are rows of the generated tables (GPS 6 of 10, CAN 3 of 5, NET 1 of 3, V2X 5 of 8, M2 1 of 7); the milestone reports group rules differently (e.g. WP4 G1..G7), so the counts differ by design. CAN and NET rules without an acceptance JSON are computed from saved numbers against thresholds in the registry (sources: M1 reports).
- Convention for the open sections (supervisor / WP3 / WP6 to confirm): the acceptance file names above. A different name needs one line in `PENDING_FILES` of make_report.py.
- `--check` does not re-score data (that needs the data and is the `runtime` step / `--refit`); the stored freeze checks are compared instead.
- `tests/system/test_make_report.py::test_committed_report_is_current` SKIPS (does not fail) when RESULTS_v3.md is stale after an input JSON changed: regenerate with `python make_report.py`.
- The run_all step table lists tool entry points by their header docstrings; `wp5.s3b_*` and `wp2.fit` order was taken from those headers and was not executed here (no refit was run).

## Files
`run_all.py`, `make_report.py`, `RESULTS_v3.md`, `README.md`, `results/WP7/S3_registry.json`, `tests/system/test_run_all.py`, `tests/system/test_make_report.py`, `notes/WP7_system.md`, `notes/WP7_brief.md`, `workpackages/WP7_system.md` (Progress line).
