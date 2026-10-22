# WP6 cross-domain brief (state at end of S2b, 2026-10-22: S2b in REVIEW)

## Current state
- S1 APPROVED with miss (sigma honesty). S2 "which domain lies" done, report reports/WP6_S2.md, verdict NOT MET
  (results/WP6/s2_acceptance.json; run 1 = s2_*_run1.json). Test exposures in S2: KITTI 1 (re-run identical), comma 2
  (run 2 = labelled second exposure after a setup-rate bug fix).
- Layer: crossdomain/consistency.py WhichDomainLies: train-fitted z per edge (design R; comma per setup), two-sided CUSUM,
  per-edge ECDF on clean val, tie-safe 1% tau on the max; blame = unique 1-node minimum vertex cover with >= 2 alarming
  partners that agree on an observed edge, else "undecided". Evidence(domain "cross", layer "L2", "cross.which_domain_lies").
- Key numbers (test): KITTI FA 4.42%, mean det 74.4%, blame 49% correct / 6% wrong / 45% undecided (k = inst).
  comma (run 2) FA 5.36% (all from the gnss-imu yaw edge; continuous full-route 35.7%), det 100%, blame 97% / 0% / 3%.
  Coordinated gps_can: GPS domain 50% vs cross 81% (cross catches 22/35 GPS-domain misses); blame goes to the honest LiDAR.
- Open for supervisor: bias-tolerant CUSUM (EWMA bias tracker) + LODO/LORO calibration as S2b (val only); can/wheel as
  one domain or two messages; accept comma run 2.

- S2 APPROVED with misses (comma run 2 official). S2b (VALIDATION ONLY, reports/WP6_S2b.md, results/WP6/s2b_*): LODO/LORO
  thresholds over dev groups, out-of-fold sigma models, domain-level blame (comma can + wheel = one CAN domain; KITTI
  compass + gyro = IMU). Chosen for S3: inst |z| (no CUSUM met FA): held-out FA KITTI 1.24%, comma continuous 1.10%;
  detection KITTI 57.5%, comma 88.1%; wrong blame 3.4% / 1.4%. Best bias-tolerant CUSUM R2_wu60_k1_tb300 (warm-up 60 s +
  clipped bias tracker): comma FA 1.85% (val routes continuous 0.11%), not chosen. Frozen choice: s2b_choice_r2.json.
  Its test number comes once in S3 (labelled).

## Binding decisions / conventions
- comma's two CAN speed messages = ONE domain; blame at domain level (supervisor 2026-10-22).
- Grid 1 Hz, quantity = mean over (t-1, t]; inst sources via cumulative trapezoid; gap > 1.5 s drops the point.
- Splits: KITTI = WP1 drive split; comma = by route sorted by date, 13 / 4 / 4. comma S2 episodes = 120 s windows.
- Design R + per-setup sigma (comma setup from UNIQUE-timestamp sample rates: gyro 10 vs ~100 Hz, GNSS 5 vs 10 Hz).
- Acceptance rules written in notes/WP6_crossdomain.md before results; test once per step.

## Pitfalls
- KITTI val = 3 drives, KITTI drives 5-90 s: short runs, noisy val statistics, val thresholds do not transfer (FA 4.4%).
- comma: old routes duplicate gyro timestamps; gyro bias drifts per route (yaw edge); per-setup speed sigma ~0.08 m/s
  makes a 0.1-0.2% CAN scale difference a visible bias.
- Low-k CUSUM integrates any sensor bias; a bias FROZEN while suspicious never adapts (S2b round 1); warm-up +
  clip-bounded tracking works on comma, not on KITTI (short drives; drive 0070 degenerate ICP = witness quality problem).
- comma route 2018-07-29--12-02-42: can-wheel glitches (z mean -31).
- comma: "|" in route names -> "_"; read arrays with np.load(allow_pickle=False), python -I for the fetcher.

## File map
- crossdomain/: witness.py, kitti.py, can_sim.py, comma.py, v2x_self.py (S1); consistency.py (+ S2b drift_cusum, robust_cusum,
  blame_domain_pattern), attacks.py (S2); __init__.py.
- tools/WP6_S1_*.py; tools/WP6_S2_kitti.py, WP6_S2_comma.py (build), WP6_S2_gpsdomain.py, WP6_S2_eval.py (dev/test), WP6_S2_tables.py; S2b: WP6_S2_kitti/comma.py build_dev,
  WP6_S2b_eval.py [1|2], WP6_S2b_tables.py.
- results/WP6/: s1_*; s2_dev.json, s2_choices.json, s2_test.json, s2_acceptance.json, s2_tables.md (+ *_run1), logs/.
- Cache ../data_extra/cache_v3/WP6 (95 MB): s1_*, s2_kitti.pkl, s2_comma.pkl, s2_gpsdomain.pkl, s2b_kitti.pkl, s2b_comma.pkl.
