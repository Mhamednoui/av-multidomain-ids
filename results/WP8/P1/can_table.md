# CAN: raw rule columns of the S3 window tables (partial)

**re-analysis of v3 test outputs (no refit).** Source files: results/WP2/s3_road_windows_test_A.csv.gz, results/WP2/s3_carhacking_windows_test.csv.gz (S3 raw window tables: L1 rule columns + L2a skew); headline stack numbers from results/WP2/s7_test.json

These are the single raw L1 rule values (id allow-list, DLC, period, bus load, flood) and the L2a skew value that were saved with the S3 window tables. They are NOT the final v3 CAN stack (L1 + L3c + L3d, combiner max): its per-window scores are not available without a re-run. Many windows tie at zero for the rule columns, so detection at low FA is a lower bound set by ties (tie-safe: strictly above the threshold).

| subset | n pos / n neg | AUC [95% CI] | det@0.5% FA | det@1% FA | det@2% FA | det@5% FA | op. point (FA / det) |
|---|---|---|---|---|---|---|---|
| ROAD test (run 1 table) / l1_id_allow / all attacks | 262 / 1451 | 0.504 [0.500, 0.517] | 0.8% [0%, 3%] | 0.8% [0%, 3%] | 0.8% [0%, 3%] | 0.8% [0%, 3%] |  |
| ROAD test (run 1 table) / l1_id_allow / plain injection captures | 132 / 1451 | 0.508 [0.500, 0.554] | 1.5% [0%, 11%] | 1.5% [0%, 11%] | 1.5% [0%, 11%] | 1.5% [0%, 11%] |  |
| ROAD test (run 1 table) / l1_id_allow / masquerade captures | 130 / 1451 | 0.500 [0.500, 0.500] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] |  |
| ROAD test (run 1 table) / l1_dlc / all attacks | 262 / 1451 | 0.500 [0.500, 0.500] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] |  |
| ROAD test (run 1 table) / l1_dlc / plain injection captures | 132 / 1451 | 0.500 [0.500, 0.500] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] |  |
| ROAD test (run 1 table) / l1_dlc / masquerade captures | 130 / 1451 | 0.500 [0.500, 0.500] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] |  |
| ROAD test (run 1 table) / l1_period / all attacks | 262 / 1451 | 0.824 [0.653, 0.934] | 0.0% [0%, 48%] | 0.0% [0%, 58%] | 0.0% [0%, 71%] | 51.9% [0%, 88%] |  |
| ROAD test (run 1 table) / l1_period / plain injection captures | 132 / 1451 | 0.953 [0.914, 0.998] | 0.0% [0%, 99%] | 0.0% [0%, 99%] | 0.0% [0%, 100%] | 99.2% [0%, 100%] |  |
| ROAD test (run 1 table) / l1_period / masquerade captures | 130 / 1451 | 0.693 [0.449, 0.878] | 0.0% [0%, 7%] | 0.0% [0%, 23%] | 0.0% [0%, 31%] | 3.8% [0%, 48%] |  |
| ROAD test (run 1 table) / l1_bus_load / all attacks | 262 / 1451 | 0.677 [0.403, 0.926] | 48.1% [10%, 84%] | 48.1% [11%, 85%] | 48.9% [11%, 86%] | 50.0% [12%, 87%] |  |
| ROAD test (run 1 table) / l1_bus_load / plain injection captures | 132 / 1451 | 0.995 [0.971, 1.000] | 95.5% [77%, 100%] | 95.5% [78%, 100%] | 97.0% [83%, 100%] | 99.2% [95%, 100%] |  |
| ROAD test (run 1 table) / l1_bus_load / masquerade captures | 130 / 1451 | 0.354 [0.176, 0.594] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 1%] |  |
| ROAD test (run 1 table) / l1_flood / all attacks | 262 / 1451 | 0.501 [0.478, 0.541] | 0.4% [0%, 2%] | 0.4% [0%, 2%] | 0.4% [0%, 2%] | 0.4% [0%, 2%] |  |
| ROAD test (run 1 table) / l1_flood / plain injection captures | 132 / 1451 | 0.502 [0.473, 0.573] | 0.8% [0%, 5%] | 0.8% [0%, 5%] | 0.8% [0%, 5%] | 0.8% [0%, 5%] |  |
| ROAD test (run 1 table) / l1_flood / masquerade captures | 130 / 1451 | 0.500 [0.468, 0.559] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 0%] |  |
| ROAD test (run 1 table) / l2a_skew / all attacks | 262 / 1451 | 0.458 [0.248, 0.716] | 10.3% [0%, 39%] | 11.1% [0%, 40%] | 12.2% [0%, 40%] | 14.5% [0%, 43%] |  |
| ROAD test (run 1 table) / l2a_skew / plain injection captures | 132 / 1451 | 0.550 [0.250, 0.890] | 20.5% [0%, 72%] | 22.0% [0%, 72%] | 24.2% [0%, 74%] | 28.8% [0%, 75%] |  |
| ROAD test (run 1 table) / l2a_skew / masquerade captures | 130 / 1451 | 0.365 [0.166, 0.748] | 0.0% [0%, 0%] | 0.0% [0%, 0%] | 0.0% [0%, 4%] | 0.0% [0%, 32%] |  |
| Car-Hacking test / l1_id_allow / all attacks | 976 / 300 | 0.791 [0.500, 1.000] | 58.3% [0%, 100%] | 58.3% [0%, 100%] | 58.3% [0%, 100%] | 58.3% [0%, 100%] |  |
| Car-Hacking test / l1_dlc / all attacks | 976 / 300 | 0.510 [0.500, 0.528] | 2.0% [0%, 6%] | 2.0% [0%, 6%] | 2.0% [0%, 6%] | 2.0% [0%, 6%] |  |
| Car-Hacking test / l1_period / all attacks | 976 / 300 | 0.996 [0.994, 0.999] | 86.5% [78%, 99%] | 92.3% [87%, 100%] | 94.6% [90%, 100%] | 99.6% [97%, 100%] |  |
| Car-Hacking test / l1_bus_load / all attacks | 976 / 300 | 0.446 [0.213, 0.771] | 44.3% [21%, 77%] | 44.4% [21%, 77%] | 44.4% [21%, 77%] | 44.4% [21%, 77%] |  |
| Car-Hacking test / l1_flood / all attacks | 976 / 300 | 0.375 [0.097, 0.827] | 28.7% [0%, 80%] | 28.7% [0%, 80%] | 28.7% [0%, 80%] | 28.7% [0%, 80%] |  |
| Car-Hacking test / l2a_skew / all attacks | 976 / 300 | 0.150 [0.000, 0.266] | 0.8% [0%, 16%] | 0.8% [0%, 16%] | 0.8% [0%, 17%] | 0.8% [0%, 17%] |  |