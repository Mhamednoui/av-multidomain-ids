Budget 1.0% false alarms on validation normal data. Domain: road_A.

| configuration | AUC | detection | false alarms | det correlated_signal | det correlated_signal_masquerade | det fuzzing | det max_engine_coolant_temp | det max_engine_coolant_temp_masquerade | det max_speedometer | det max_speedometer_masquerade | det reverse_light_off | det reverse_light_off_masquerade | det reverse_light_on | det reverse_light_on_masquerade | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.722 | 50.8% | 3.38% | 100.0% | 0.0% | 100.0% | 100.0% | 16.7% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0 |
| only_can.l1_bus_load | 0.677 | 48.9% | 1.38% | 100.0% | 0.0% | 100.0% | 33.3% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0 |
| only_can.l1_dlc | 0.500 | 0.0% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | nan |
| only_can.l1_flood | 0.494 | 0.4% | 0.00% | 0.0% | 0.0% | 50.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.5 |
| only_can.l1_id_allow | 0.504 | 0.8% | 0.00% | 0.0% | 0.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| only_can.l1_period | 0.650 | 5.0% | 4.41% | 0.0% | 0.0% | 50.0% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| all_but_can.l1_bus_load | 0.629 | 3.8% | 2.55% | 0.0% | 0.0% | 100.0% | 100.0% | 33.3% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| all_but_can.l1_dlc | 0.722 | 50.8% | 3.38% | 100.0% | 0.0% | 100.0% | 100.0% | 16.7% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0 |
| all_but_can.l1_flood | 0.724 | 50.8% | 3.58% | 100.0% | 0.0% | 100.0% | 100.0% | 16.7% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0 |
| all_but_can.l1_id_allow | 0.722 | 50.8% | 3.38% | 100.0% | 0.0% | 100.0% | 100.0% | 16.7% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0 |
| all_but_can.l1_period | 0.678 | 48.9% | 1.38% | 100.0% | 0.0% | 100.0% | 33.3% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 100.0% | 0.0% | 0.0 |
