# system (H31, H31 scoring (frozen v3 vs frozen v3.1, one run))

| subset | exposure | n_pos | n_neg | auc | det@1.0% | det@2.0% | op_fa | op_det |
|---|---|---|---|---|---|---|---|---|
| system K v3: all attacked ticks | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 93990 | 28560 | 0.762 [0.727, 0.797] | 0.019 [0.009, 0.035] | 0.025 [0.013, 0.049] | 0.124 | 0.399 |
| system K v3: veh composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 66770 | 28560 | 0.760 | 0.006 | 0.012 | 0.124 | 0.400 |
| system K v3: lidar composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 4056 | 28560 | 0.518 | 0.004 | 0.009 | 0.124 | 0.115 |
| system K v3: can composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 244 | 28560 | 0.811 | 0.008 | 0.012 | 0.124 | 0.430 |
| system K v3: v2x composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 17584 | 28560 | 0.848 | 0.068 | 0.073 | 0.124 | 0.502 |
| system K v3: net composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 4380 | 28560 | 0.685 | 0.024 | 0.029 | 0.124 | 0.200 |
| system K v3: multi composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 956 | 28560 | 0.761 | 0.061 | 0.103 | 0.124 | 0.531 |
| system K v3.1: all attacked ticks | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 93990 | 28560 | 0.834 [0.806, 0.862] | 0.018 [0.007, 0.036] | 0.018 [0.007, 0.036] | 0.122 | 0.731 |
| system K v3.1: veh composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 66770 | 28560 | 0.839 | 0.001 | 0.001 | 0.122 | 0.744 |
| system K v3.1: lidar composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 4056 | 28560 | 0.606 | 0.000 | 0.000 | 0.122 | 0.181 |
| system K v3.1: can composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 244 | 28560 | 0.875 | 0.000 | 0.000 | 0.122 | 0.742 |
| system K v3.1: v2x composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 17584 | 28560 | 0.891 | 0.093 | 0.093 | 0.122 | 0.934 |
| system K v3.1: net composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 4380 | 28560 | 0.731 | 0.000 | 0.000 | 0.122 | 0.201 |
| system K v3.1: multi composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 956 | 28560 | 0.883 | 0.000 | 0.000 | 0.122 | 0.815 |
| system C v3: all attacked ticks | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 210819 | 28560 | 0.813 [0.794, 0.836] | 0.060 [0.022, 0.113] | 0.134 [0.068, 0.213] | 0.060 | 0.372 |
| system C v3: veh composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 174798 | 28560 | 0.791 | 0.031 | 0.072 | 0.060 | 0.273 |
| system C v3: can composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 262 | 28560 | 0.927 | 0.153 | 0.290 | 0.060 | 0.725 |
| system C v3: v2x composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 31379 | 28560 | 0.942 | 0.222 | 0.479 | 0.060 | 0.925 |
| system C v3: net composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 4380 | 28560 | 0.794 | 0.064 | 0.135 | 0.060 | 0.341 |
| system C v3.1: all attacked ticks | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 210819 | 28560 | 0.892 [0.880, 0.905] | 0.581 [0.547, 0.612] | 0.588 [0.552, 0.618] | 0.061 | 0.732 |
| system C v3.1: veh composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 174798 | 28560 | 0.883 | 0.586 | 0.592 | 0.061 | 0.703 |
| system C v3.1: can composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 262 | 28560 | 0.968 | 0.027 | 0.760 | 0.061 | 0.763 |
| system C v3.1: v2x composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 31379 | 28560 | 0.957 | 0.639 | 0.646 | 0.061 | 0.928 |
| system C v3.1: net composites | partially fresh (vehicle block fresh, CAN / network / V2X streams re-used) | 4380 | 28560 | 0.804 | 0.008 | 0.025 | 0.061 | 0.468 |
