# WP0 S4: combiner noisy_or in log space

Date 2026-10-21. Request: reports/REQUEST_WP1_combiner_noisy_or.md. Acceptance rule written first in notes/WP0_foundation.md (section "S4").

## Change (common/combiner.py)
- `noisy_or_stat(X) = -sum log1p(-clip(s_i, 0, 1-1e-16))` (= -log prod(1 - s_i)); `noisy_or_score(X) = S / (S + n_layers)`.
- `_combine("noisy_or")` now returns `noisy_or_score`. Method name, inputs, outputs (Evidence score in [0,1]) unchanged.
- Output range: still [0,1) but VALUES differ from 1 - prod(1 - s) (strictly increasing transform of it: same ranking). Thresholds still come from
  `budget_threshold` on this same score, in `fit` and in `_select`, so nothing else changes. Why not 1 - exp(-S): it saturates at 1.0 again for S > 37.

## Acceptance
(a) MET. Random non-saturated inputs: Spearman 1.0 (to 1e-12), identical argsort, identical alarm sets at quantile thresholds mapped through the transform and at the 1% budget threshold fitted on each score.
(b) MET. 16 correlated layers, 4% extreme rows: old form ties at the max on >1% of rows and its tie-safe threshold is above every score (0 alarms); new form has top-tie fraction <= 1% and 0 < alarm rate <= 1% at the budget threshold.
(c) MET. `python tests/run_tests.py`: 196 passed, 0 failed (2 new tests in tests/common/test_common.py).
(d) MET. tests/common/test_regression_b2.py unchanged, 3 tests pass (B2 does not use the combiner).
(e) MET, trivially. gps/domain.py uses `gps.stack.noisy_or_log` directly, not common noisy_or; frozen files in results/WP1/frozen_gps/ untouched and tests/gps/test_domain.py (round trip, noisy_or_log ranking) pass. I did not re-run tools/WP1_S8_freeze.py (it re-fits and overwrites the frozen files).

## Side effects / notes
- gps/stack.py `MatrixCombiner` imports `_combine`; its method "noisy_or" now also uses the log form, so re-running WP1 dev tools would give a non-degenerate noisy_or (the old 0% result is a saturation artefact). Frozen results in results/WP1 are not recomputed.
- Saturation warning proposed in the request was not added (would change the interface); not needed since the score no longer ties from float saturation. Correlated layers still may tie legitimately if inputs tie.
- WP2/WP5 reproduced numbers that used noisy_or would change values only through the monotone map; detection at budget identical up to float ties. Not re-run.
