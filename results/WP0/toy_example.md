Budget 1.0% false alarms on validation normal data. Domain: toy_example.

| configuration | AUC | detection | false alarms | det alpha | det beta | det gamma | median delay (s) |
|---|---|---|---|---|---|---|---|
| all | 0.955 | 51.5% | 1.09% | 56.9% | 55.0% | 42.5% | 1.0 |
| only_toy.f1 | 0.742 | 26.9% | 0.99% | 73.1% | 0.0% | 7.5% | 1.5 |
| only_toy.f2 | 0.746 | 24.2% | 0.83% | 5.6% | 66.2% | 0.6% | 3.0 |
| only_toy.f3 | 0.654 | 21.2% | 1.04% | 0.6% | 1.2% | 61.9% | 0.0 |
| all_but_toy.f1 | 0.862 | 37.1% | 1.20% | 3.1% | 60.0% | 48.1% | 2.0 |
| all_but_toy.f2 | 0.815 | 40.4% | 1.15% | 60.6% | 0.6% | 60.0% | 1.0 |
| all_but_toy.f3 | 0.871 | 43.8% | 0.99% | 68.1% | 58.8% | 4.4% | 1.0 |
