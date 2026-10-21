# WP2 S3: L2a ECU clock-skew fingerprinting (CIDS)

Date: 2026-10-21    Worker: sonnet (medium)

## Summary
Verdict: **NOT MET** (acceptance item 2 fails in the frozen run 1 and in the revised run 2b). Plain answer: **clock skew does NOT catch
ROAD masquerade at a usable false-alarm budget.** Rule and design: notes/WP2_can.md "S3 start" (written before results). Tables: results/WP2/s3_tables.md.
- Data caveat (a): ROAD masquerade logs = attack log with the legitimate frames of the injected ID removed after the fact. The injected frames keep
  their original logger timestamps (100% identical): they are real attacker receive times, NOT copied from the legit ECU, so skew is testable.
  But the clock-rate difference attacker vs ECU is only -2131..+210 ppm (median |.| about 60 ppm; coolant -2131 ppm, 43 frames) while per-gap jitter of the
  logged timestamps is 12-28% of the period and 10 s segment means of clean traffic spread 1.6-2.8%: below what the receive timestamps resolve
  (results/WP2/s3_road_masq_timestamps.json, s3_road_masq_shift.json). (b) D11: dt_clipped only. (c) Car-Hacking injection is software timed.
- Method (equations in the can/l2a_skew.py docstring and in the notes): per periodic ID, batches of N gaps, accumulated offset, scalar RLS skew (lambda 0.99),
  identification error, normalised, two-sided CUSUM (kappa 1, clip 10), per-ID scale from clean train; frame score = CUSUM state, window = max.
  16 variants (form x N x error x baseline), chosen on validation.
- ROAD run 1 (pre-registered design = verdict): validation masquerade recall 0.0 for all 8 variants; test: L2a detects 0/5 masquerade captures, clean-window FA 3.9%
  (limit 2%); L1+L2a FA 6.6% (L1 alone 3.5%). Cause (validation/train only): the accumulated error is a random walk whose scale grows with capture length; the pooled sigma is set by long
  ambient captures; a few drifting IDs reach CUSUM 400-700 and dominate the window max.
- ROAD run 2b (revised: per-ID scale + local in-capture baseline; NOT independent, test seen in run 1; run 2a was an intermediate whose test numbers I did not inspect):
  chosen paper_N50_acc_loc (val recall 0.41). Test: L2a alone AUC 0.458, clean-window FA 35% (1260/h), masquerade windows detected: reverse_light_off_3 64% (delay 9.5 s), others 0%
  (coolant 0.17 only in the combination). L1+L2a: FA 33% vs L1 alone 3.5%. Validation FA (1%) did not transfer: the test ambient drives shift the CUSUM.
- Upper bound with the attacked ID known (descriptive, s3_road_masq_id.json): AUC of injected-ID attack frames vs its own pre-attack frames reaches 0.99-1.0 (best of 16 variants)
  on 8 of 12 non-coolant captures (test: reverse_light_off_3 1.0, reverse_light_on_3 0.94, max_speedometer_3 0.71, correlated_3 0.53), but this includes onset transients, is the best of
  16 variants chosen with labels, and says nothing about false alarms over about 100 IDs. Skew carries a within-capture change signal, not a deployable detector with ROAD timestamps.
- Car-Hacking (window, 1% budget): L2a alone recall 0-3%, AUC 0.156 (FA 8.3%): useless there; L1+L2a 99.7% at FA 0.7% vs L1 99.8% at FA 1.0%: no gain.
- D11 (4 sets x 4 subsets x 2 regimes, results/WP2/s3_tables.md): L2a alone is weaker than L1 (recall 0.00-0.99, FA 0-53%); L1+L2a changes the number of detected files in 1 of 32 cells
  (set_03 test_03 B: 13/14 vs 14/14), window recall mostly equal, FA mostly higher in regime B.
- Harness ablation on top of L1 (ROAD regime A): without skew AUC 0.753, FA 3.5%; with skew AUC 0.688, FA 33%. Car-Hacking: AUC 1.000 both.
- Recommendation: leave L2a out of the default CAN stack; masquerade on ROAD needs payload / signal layers (S4, S5), not timing. Keep L2a as a documented negative result.
Acceptance: item 1 met (layer, causal, dt_clipped, tie-safe 1% budget, 190/190 tests, no new cache); item 2 NOT MET (0/5 run 1; 1/5 at FA 35% run 2b);
item 3 NOT MET (FA 6.6% run 1 / 33% run 2b vs 4.5%); item 4 met (reported).

## Acceptance rule (notes/WP2_can.md, "S3 start", before any skew result)
1 Layer, causal, calibrated on clean data, tests, commit. 2 L2a alone detects at least 3 of 5 ROAD test masquerade captures with clean FA <= 2%. 3 L1+L2a keeps the 5 v2 captures
(delay <= 2 s) and FA <= 4.5%. 4 Car-Hacking and D11 reported.

## What was done
- Files: can/l2a_skew.py, can/l2a_exp.py, tools/WP2_S3_run.py, WP2_S3_d11.py, WP2_S3_tables.py, WP2_S3_masq_timestamps.py, WP2_S3_masq_shift.py, WP2_S3_masq_id.py,
  tests/can/test_l2a_skew.py (6 tests). Uses the S2 cache (no new cache). Data: ROAD v2 split, Car-Hacking block split, D11 splits and both regimes as in S2.
- Results: results/WP2/s3_road.json (run 2b), s3_run1_frozen/ (verdict run), s3_carhacking.json, s3_d11_set_0N.json, s3_tables.md, s3_harness/.

## What changed after seeing results (honest list)
1. Run 1 -> 2a (per-ID scale) -> 2b (local baseline, 8 more variants): decided from validation / train diagnostics after run 1 had scored the test set. Run 1 is the verdict.
2. Run 2a overwrote its own outputs; its test numbers were not inspected.
3. The D11 job produced an empty log and no process remained (the supervisor note about a killed python process may refer to it); no set had finished, so it was restarted from scratch and completed.

## Problems / open questions
- ROAD validation has only 2 clean ambient captures and the test ambient drives shift: calibration does not transfer (same pattern as S2).
- The CIDS error normalisation is not fully specified in my reading of the paper; a different skew estimator might do better, but the ppm analysis says the signal is below the timestamp resolution.

## Proposed next step
S4 (signal physics on decoded ROAD signals); drop L2a from the default combiner.
