Budget 1.0% false alarms on validation normal data. Domain: harness_L1_L2a_L2b.

| configuration | AUC | detection | false alarms | det IntensitySpoof | det PointDrop | det cmp_boxcloud | det cmp_mradd_far | det cmp_mradd_near | det ph_budget_far | det ph_budget_near | det ph_replace_far | det ph_replace_near | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.697 | 24.5% | 1.37% | 51.4% | 1.6% | 24.1% | 67.6% | 65.9% | 2.0% | 2.0% | 2.9% | 2.9% | 0.0 |
| only_L1 | 0.558 | 10.0% | 1.63% | 1.4% | 1.4% | 16.1% | 62.5% | 1.4% | 1.8% | 1.4% | 3.1% | 1.4% | 0.0 |
| only_L2a_int | 0.551 | 5.7% | 0.20% | 51.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| only_L2b | 0.638 | 13.2% | 0.26% | 0.4% | 0.4% | 16.9% | 27.3% | 68.4% | 0.4% | 0.6% | 0.4% | 4.3% | 0.0 |
| all_but_L1 | 0.677 | 18.2% | 0.33% | 53.5% | 0.6% | 14.5% | 24.3% | 66.1% | 0.6% | 0.8% | 1.0% | 2.4% | 0.0 |
| all_but_L2a_int | 0.659 | 21.2% | 1.83% | 1.8% | 1.8% | 31.2% | 75.7% | 67.8% | 2.2% | 2.0% | 3.7% | 4.9% | 0.0 |
| all_but_L2b | 0.602 | 15.6% | 1.83% | 52.5% | 1.4% | 14.5% | 62.5% | 1.4% | 1.8% | 1.4% | 3.1% | 1.4% | 0.0 |
