# REQUEST (WP1 -> supervisor): numerical saturation of the noisy-or in common/combiner.py

Date: 2026-10-21    From: WP1 S8 worker    Status: request only, nothing in common/ was changed.

**Problem.** `common.combiner._combine("noisy_or")` computes `1 - prod(1 - s_i)`. With the 16 correlated, ECDF-calibrated GPS layers, `prod(1 - s_i)`
falls below float64 resolution (1e-16) on 1.66% of the NORMAL development rows (several layers are in their top 0.01% at once), so the combined score is exactly 1.0
on more rows than the 1% budget allows. The tie-safe threshold (`np.nextafter` above the tied value) then lies above every score: the method raises 0 alarms
(held-out FA 0.0%, detection 0.0% on the dev folds and on test; `results/WP1/S8_dev.json` -> `combiners_nested.noisy_or`, `S8_kitti.json` -> `combiners_test.noisy_or`).
The "auto" selection of the combiner therefore never picks noisy-or for this stack.

**Rank-equivalent fix.** Score `S = -sum_i log(1 - s_i)` (`gps.stack.noisy_or_log`, clip s_i at 1 - 1e-16), which has the same ordering as the noisy-or and does not saturate.
For an Evidence score in [0, 1] map S with the ECDF of S on the validation normal samples (what `gps/domain.py` does), or `1 - exp(-S / c)` with c of the order of the
number of layers. Unit test: `tests/gps/test_domain.py::test_noisy_or_log_ranks_like_noisy_or_and_does_not_saturate`.

**Proposed.** Replace the product by the log form (or add `"noisy_or_log"` to `METHODS`) in `common/combiner.py`, and add a saturation check ("fraction of normal validation
scores tied at the maximum > budget -> raise a warning"). WP5 (max chosen) and WP2 are probably unaffected at their layer counts; please check before changing.
