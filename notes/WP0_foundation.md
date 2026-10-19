# Notes WP0 Foundation

## 2026-10-19 S1 start (worker sonnet)

Acceptance rule (written before any check was run), from workpackages/WP0_foundation.md S1:
1. `git log` shows the commit `[WP0.S1] repository, docs`.
2. Package versions in the tf env equal RULES.md section 4 (Python 3.9.21, numpy 1.23.5,
   pandas 2.2.3, xgboost 2.1.4, scikit-learn 1.6.1, scipy 1.13.1) and every package of
   requirements.txt imports.
3. The report lists doc issues (or says "none").
Extra checks: .gitignore patterns work; requirements.txt identical to ../codes_v2/requirements.txt;
nothing in ../codes or ../codes_v2 modified; no download in this step.

2026-10-19 S1 results: git init (branch main, local); .gitignore, requirements.txt (copy of v2),
locks/.gitkeep created. tf env versions all match RULES.md section 4 (Python 3.9.21, numpy
1.23.5, pandas 2.2.3, xgboost 2.1.4, sklearn 1.6.1, scipy 1.13.1) and the 5 other pinned
packages import with the pinned versions. Doc review: 9 items listed in reports/WP0_S1.md
(main ones: v2 B2 numbers exist at row level and run level, S3 must pick; KITTI split ids not in
WP0; downloads policy differs between RULES/DATASETS and ORCHESTRATOR). No download. Disk 52 GB free.
Acceptance rule items 1-3: met (commit hash in report/log).
