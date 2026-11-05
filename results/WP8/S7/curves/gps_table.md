# gps (H31, H31 scoring (frozen v3 vs frozen v3.1, one run))

| subset | exposure | n_pos | n_neg | auc | det@1.0% | det@2.0% | op_fa | op_det |
|---|---|---|---|---|---|---|---|---|
| gps drift [all] | fresh H31 (all) | 6070 | 6460 | 0.905 [0.791, 0.965] | 0.000 [0.000, 0.853] | 0.000 [0.000, 0.872] | 0.072 | 0.837 |
| gps accel_drift [all] | fresh H31 (all) | 6070 | 6460 | 0.923 [0.841, 0.965] | 0.000 [0.000, 0.900] | 0.000 [0.000, 0.907] | 0.072 | 0.888 |
| gps doppler_spoof [all] | fresh H31 (all) | 6070 | 6460 | 0.902 [0.786, 0.967] | 0.000 [0.000, 0.890] | 0.000 [0.000, 0.899] | 0.072 | 0.860 |
| gps meaconing [all] | fresh H31 (all) | 6070 | 6460 | 0.894 [0.776, 0.966] | 0.000 [0.000, 0.889] | 0.000 [0.000, 0.900] | 0.072 | 0.866 |
| gps gps_can [all] | fresh H31 (all) | 6070 | 6460 | 0.857 [0.748, 0.924] | 0.000 [0.000, 0.649] | 0.000 [0.000, 0.700] | 0.072 | 0.613 |
| gps pooled attacks [all] | fresh H31 (all) | 30350 | 6460 | 0.896 [0.789, 0.955] | 0.000 [0.000, 0.826] | 0.000 [0.000, 0.847] | 0.072 | 0.813 |
| gps drift [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.889 | 0.000 | 0.000 | 0.095 | 0.850 |
| gps accel_drift [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.916 | 0.000 | 0.000 | 0.095 | 0.898 |
| gps doppler_spoof [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.880 | 0.000 | 0.000 | 0.095 | 0.856 |
| gps meaconing [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.885 | 0.000 | 0.000 | 0.095 | 0.883 |
| gps gps_can [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 4517 | 4787 | 0.839 | 0.000 | 0.000 | 0.095 | 0.599 |
| gps pooled attacks [same_day_2011_09_26] | fresh H31 (same_day_2011_09_26) | 22585 | 4787 | 0.882 | 0.000 | 0.000 | 0.095 | 0.817 |
| gps drift [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.956 | 0.814 | 0.836 | 0.007 | 0.800 |
| gps accel_drift [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.947 | 0.865 | 0.872 | 0.007 | 0.861 |
| gps doppler_spoof [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.965 | 0.876 | 0.882 | 0.007 | 0.872 |
| gps meaconing [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.918 | 0.822 | 0.833 | 0.007 | 0.816 |
| gps gps_can [other_day] | fresh H31 (other_day) | 1553 | 1673 | 0.914 | 0.692 | 0.733 | 0.007 | 0.652 |
| gps pooled attacks [other_day] | fresh H31 (other_day) | 7765 | 1673 | 0.940 | 0.814 | 0.831 | 0.007 | 0.800 |
