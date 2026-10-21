# WP2 S2: L1 specification rules (ID allow-list, DLC, period, bus load, flood)

## Summary
Verdict: **NOT MET** by the pre-registered rule (item 2b fails). Items 1, 3, 4, 5 are met.
Design and acceptance rule: notes/WP2_can.md "S2 start" (written before results). Code: can/l1.py, can/l1_exp.py,
tools/WP2_S2_cache.py, tools/WP2_S2_run.py, tests/can/test_l1.py (154 tests pass).

- ROAD, run 1 (frozen design, the verdict): the 5 captures that the v2 timing model detects (fuzzing, correlated_signal,
  max_speedometer, reverse_light_off, reverse_light_on) are all detected, delay 0.17-0.93 s (item 2a met), mostly by
  the bus-load rule. Reverse driving: 0 alerts (met). But combined false alerts on clean test windows are 3.4%
  (122/h) and 49/1316 ambient windows (3.7%) against the 1% limit (item 2b FAILS). Period rule alone 4.4%.
- ROAD, run 2 (IQR periodic test, a validation-driven fix; NOT independent, test was seen in run 1): the period rule
  now catches coolant (frame recall 1.0) and gets 0.6-0.8 window recall on speedometer/reverse_light, but clean-window
  FA stays 3.5% (127/h). Masquerade captures are not detected (frame recall 0-30%): specification rules cannot see
  same-ID same-period masquerade; the "masquerade <= 1 false alert/hour" target is NOT claimed by L1.
- Why FA > 1%: per-rule thresholds calibrated at 1% on ~1450 clean val windows, the noisy-or of five rules adds up,
  and two test ambient drives (benign_anomaly, extended_short) differ from val (most of the false windows are there;
  highway and reverse captures give 0). A 0.1% budget still gives 2.5-2.8%: a distribution shift, not calibration size.
- Car-Hacking (block split, window level, 1% budget): window recall DoS 100%, Fuzzy 100%, RPM 99.5%, Gear 99.5%
  (item 3 met); false alerts on clean test windows 1.0% (36/h). Frame recall 100/99.6/96.8/93.6%.
- D11 zero-shot (regime A, profile + thresholds from the training vehicle): every attack file is detected in all 16
  test subsets (median delay 0.3-0.8 s), but on an UNKNOWN vehicle the rules alarm on almost every window (clean-window
  FA 100%; id_allow and dlc fire on vehicle-specific IDs/DLCs). Same-vehicle subsets: FA 0.6-3.4% of clean windows.
  Zero-shot transfer across vehicles fails for specification rules.
- D11 on-vehicle (regime B, 30 s profile + 30 s thresholds from the first minute of each test file): unknown vehicles
  drop to FA 1.2-5.9% of clean windows (21-212/h), window recall 0.78-1.0 (lowest: Traverse set_02 test_03,
  force-neutral/rpm). One bad cell: Subaru set_04 test_01 (only 3 eligible files): FA 20%.
- Bottom line for the fusion: L1 is a cheap, strong detector of injected/flood/fuzzing traffic (Car-Hacking, D11, ROAD
  non-masquerade) but needs about a minute of on-vehicle calibration; its clean-window FA is 1-4%, not 1%, so the fusion
  must treat L1 as a first-stage signal and not as a final alarm.
Per-layer and harness ablation tables: results/WP2/s2_run1_frozen/harness/, s2_run2_iqr/harness/, s2_harness/
(Car-Hacking and D11 files). Full D11 table: results/WP2/s2_d11_tables.md. JSON: results/WP2/s2_*.json.

## What was changed after seeing results (honest list)
1. Run 1 -> run 2: periodic test q95-q05 -> interquartile range (decided from VALIDATION recall of the period rule
   on ROAD, applied unchanged to Car-Hacking and D11). Run 1 stays the verdict.
2. Empty-fit guard in ProfileBuilder.add (D11 train files with no clean frame crashed set_03; no effect on results).
3. Cache blunder: the first cache wrote 39 GB (per-frame strings) and filled disk C: for some minutes; deleted and
   rebuilt as int8 codes (3.4 GB).
Nothing was tuned on test labels. Windows are 1 s; D11 regime B scored frames after t = 60 s only.
