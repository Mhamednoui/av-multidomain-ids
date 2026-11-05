# cross (H31, H31 scoring (frozen v3 vs frozen v3.1, one run))

| subset | exposure | n_pos | n_neg | auc | det@1.0% | det@2.0% | op_fa | op_det |
|---|---|---|---|---|---|---|---|---|
| cross lidar_scale [all] | fresh H31 (all) | 6070 | 6460 | 0.881 [0.786, 0.943] | 0.000 [0.000, 0.755] | 0.000 [0.000, 0.784] | 0.074 | 0.707 |
| cross lidar_bias [all] | fresh H31 (all) | 6070 | 6460 | 0.904 [0.795, 0.966] | 0.000 [0.000, 0.787] | 0.000 [0.000, 0.822] | 0.074 | 0.765 |
| cross lidar_yaw [all] | fresh H31 (all) | 6070 | 6460 | 0.794 [0.710, 0.858] | 0.000 [0.000, 0.062] | 0.000 [0.000, 0.133] | 0.074 | 0.083 |
| cross can_scale [all] | fresh H31 (all) | 6070 | 6460 | 0.868 [0.773, 0.931] | 0.000 [0.000, 0.724] | 0.000 [0.000, 0.757] | 0.074 | 0.692 |
| cross can_offset [all] | fresh H31 (all) | 6070 | 6460 | 0.897 [0.793, 0.954] | 0.000 [0.000, 0.807] | 0.000 [0.000, 0.843] | 0.074 | 0.816 |
| cross can_freeze [all] | fresh H31 (all) | 6070 | 6460 | 0.903 [0.811, 0.953] | 0.000 [0.000, 0.863] | 0.000 [0.000, 0.877] | 0.074 | 0.831 |
| cross gps_can [all] | fresh H31 (all) | 6070 | 6460 | 0.917 [0.821, 0.969] | 0.000 [0.000, 0.863] | 0.000 [0.000, 0.895] | 0.074 | 0.864 |
| cross drift [all] | fresh H31 (all) | 6070 | 6460 | 0.716 [0.657, 0.770] | 0.000 [0.000, 0.263] | 0.000 [0.000, 0.311] | 0.074 | 0.254 |
| cross accel_drift [all] | fresh H31 (all) | 6070 | 6460 | 0.902 [0.810, 0.947] | 0.000 [0.000, 0.824] | 0.000 [0.000, 0.847] | 0.074 | 0.814 |
| cross doppler_spoof [all] | fresh H31 (all) | 6070 | 6460 | 0.806 [0.716, 0.870] | 0.000 [0.000, 0.499] | 0.000 [0.000, 0.542] | 0.074 | 0.469 |
| cross meaconing [all] | fresh H31 (all) | 6070 | 6460 | 0.682 [0.626, 0.737] | 0.000 [0.000, 0.302] | 0.000 [0.000, 0.342] | 0.074 | 0.323 |
| cross pooled attacks [all] | fresh H31 (all) | 66770 | 6460 | 0.843 [0.760, 0.888] | 0.000 [0.000, 0.588] | 0.000 [0.000, 0.626] | 0.074 | 0.602 |
| cross lidar_scale [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.874 | 0.000 | 0.000 | 0.091 | 0.710 |
| cross lidar_bias [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.893 | 0.000 | 0.000 | 0.091 | 0.769 |
| cross lidar_yaw [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.782 | 0.000 | 0.000 | 0.091 | 0.101 |
| cross can_scale [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.865 | 0.000 | 0.000 | 0.091 | 0.709 |
| cross can_offset [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.880 | 0.000 | 0.000 | 0.091 | 0.807 |
| cross can_freeze [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.898 | 0.000 | 0.000 | 0.091 | 0.838 |
| cross gps_can [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.908 | 0.000 | 0.000 | 0.091 | 0.855 |
| cross drift [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.712 | 0.000 | 0.000 | 0.091 | 0.289 |
| cross accel_drift [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.894 | 0.000 | 0.000 | 0.091 | 0.827 |
| cross doppler_spoof [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.793 | 0.000 | 0.000 | 0.091 | 0.465 |
| cross meaconing [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.665 | 0.000 | 0.000 | 0.091 | 0.314 |
| cross pooled attacks [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 49687 | 4787 | 0.833 | 0.000 | 0.000 | 0.091 | 0.608 |
| cross lidar_scale [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.901 | 0.305 | 0.621 | 0.026 | 0.701 |
| cross lidar_bias [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.937 | 0.346 | 0.709 | 0.026 | 0.751 |
| cross lidar_yaw [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.829 | 0.010 | 0.021 | 0.026 | 0.030 |
| cross can_scale [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.874 | 0.275 | 0.579 | 0.026 | 0.643 |
| cross can_offset [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.946 | 0.408 | 0.779 | 0.026 | 0.844 |
| cross can_freeze [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.915 | 0.703 | 0.771 | 0.026 | 0.813 |
| cross gps_can [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.946 | 0.603 | 0.867 | 0.026 | 0.890 |
| cross drift [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.728 | 0.010 | 0.059 | 0.026 | 0.153 |
| cross accel_drift [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.925 | 0.500 | 0.718 | 0.026 | 0.776 |
| cross doppler_spoof [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.844 | 0.012 | 0.328 | 0.026 | 0.482 |
| cross meaconing [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.736 | 0.037 | 0.267 | 0.026 | 0.349 |
| cross pooled attacks [other_day] | fresh H31 (other_day) | 17083 | 1673 | 0.871 | 0.292 | 0.520 | 0.026 | 0.585 |
