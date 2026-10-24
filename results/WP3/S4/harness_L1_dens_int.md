Budget 1.0% false alarms on validation normal data. Domain: harness_L1_dens_int.

| configuration | AUC | detection | false alarms | det IntensitySpoof | det PointDrop | det cmp_boxcloud | det cmp_mradd_far | det cmp_mradd_near | det ph_budget_far | det ph_budget_near | det ph_replace_far | det ph_replace_near | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.595 | 22.7% | 11.29% | 51.2% | 8.8% | 23.7% | 54.5% | 19.8% | 11.6% | 11.2% | 12.7% | 10.6% | 0.0 |
| only_L1 | 0.558 | 10.0% | 1.63% | 1.4% | 1.4% | 16.1% | 62.5% | 1.4% | 1.8% | 1.4% | 3.1% | 1.4% | 0.0 |
| only_L2a_dens | 0.515 | 22.4% | 20.03% | 19.8% | 16.3% | 22.4% | 22.2% | 43.5% | 20.0% | 19.4% | 19.8% | 18.6% | 0.0 |
| only_L2a_int | 0.548 | 7.9% | 1.04% | 62.0% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 0.0 |
| all_but_L1 | 0.555 | 28.5% | 20.35% | 71.6% | 16.7% | 22.0% | 22.4% | 43.7% | 20.6% | 20.0% | 20.4% | 19.2% | 0.0 |
| all_but_L2a_dens | 0.598 | 17.8% | 2.61% | 62.5% | 2.5% | 16.9% | 63.1% | 2.5% | 2.9% | 2.5% | 4.1% | 2.5% | 0.0 |
| all_but_L2a_int | 0.560 | 30.2% | 21.14% | 21.0% | 17.3% | 34.1% | 71.8% | 43.5% | 21.4% | 20.4% | 22.4% | 19.6% | 0.0 |
