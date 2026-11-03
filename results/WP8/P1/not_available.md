# Not available without a re-run

All entries: "re-analysis of v3 test outputs (no refit)" cannot be produced because the per-sample scores were stored only in caches deleted on 2026-10-25
(data_extra/cache_v3, data_extra/WP2_S*_cache; notes/ORCHESTRATOR.md) or were never stored. No test data was re-scored for this step.

| domain | what is missing | what exists instead |
|---|---|---|
| CAN, final stack | per-window scores of L3c (per-signal predictors), L3d (reverse-light rule) and the max combiner on ROAD test | raw L1 rule / L2a columns of the S3 window tables (partial curves, can_*); operating-point tables in results/WP2/s7_test.json |
| Network | per-flow / per-5-minute-bin scores of the host-window logic and flow-shape layers (D10, D23) | operating-point detection per family, seen and leave-one-attack-out (net_seen_unseen.*) |
| V2X | per-message / per-sender scores on VeReMi test, Tampa, V2AIX (results/WP7/frozen_v2x/domain.json holds only the calibration table) | operating-point tables in RESULTS_v3.md section 5 and results/WP5/*.json |
| Fusion / system | per-tick domain scores and fused scores of the M2 system on the K and C simulation timelines (results/WP6, WP7 S2) | per-run detection, delay and blame at the frozen operating point (results/WP6/s5b_test.json, results/WP7/S2_results.json); no curve possible |
| GPS UAV / AV-GPS external tests | per-fix scores | operating-point numbers in results/WP1/S8_external.json |
| LiDAR episodes | per-episode scores are in S9/test_scores.csv.gz but v3 scores episodes with its own episode rule | S9/final.json `episodes` |

To obtain these curves a re-run of the corresponding test scoring (new test exposure) would be needed; that is outside P1.
