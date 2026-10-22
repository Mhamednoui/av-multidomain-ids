Budget 1.0% false alarms on validation normal data. Domain: s5_d10_l3_only.

| configuration | AUC | detection | false alarms | det Bot | det DDoS-LOIC-HTTP | det DoS-GoldenEye | det DoS-Hulk | det DoS-SlowHTTPTest | det DoS-Slowloris | det FTP-Patator | det PortScan | det SSH-Patator | det Web-BruteForce | det Web-XSS | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.939 | 49.9% | 1.04% | 0.0% | 55.9% | 31.2% | 65.0% | 98.3% | 64.9% | 0.1% | 7.7% | 1.8% | 0.0% | 0.0% | 0.0 |
| only_net.l3_ae | 0.869 | 59.2% | 1.03% | 0.0% | 62.6% | 32.4% | 59.6% | 97.1% | 78.9% | 0.1% | 98.5% | 1.8% | 0.0% | 0.0% | 0.0 |
| only_net.l3_iforest | 0.899 | 14.9% | 1.19% | 0.0% | 11.4% | 23.2% | 20.2% | 79.5% | 15.3% | 0.0% | 0.3% | 0.0% | 0.0% | 0.0% | 0.0 |
| only_net.l3_service | 0.950 | 41.8% | 0.95% | 0.0% | 25.4% | 18.3% | 64.0% | 84.3% | 49.7% | 100.0% | 2.3% | 51.3% | 0.0% | 0.0% | 0.0 |
| all_but_net.l3_ae | 0.944 | 40.5% | 1.12% | 0.0% | 30.7% | 28.6% | 63.5% | 84.8% | 42.7% | 49.5% | 1.1% | 1.6% | 0.0% | 0.0% | 0.0 |
| all_but_net.l3_iforest | 0.957 | 59.2% | 0.94% | 0.0% | 44.1% | 31.3% | 65.2% | 98.6% | 98.1% | 100.0% | 98.7% | 19.2% | 0.0% | 0.0% | 0.0 |
| all_but_net.l3_service | 0.897 | 52.3% | 1.13% | 0.0% | 65.4% | 31.3% | 59.2% | 96.9% | 48.0% | 0.0% | 23.5% | 1.0% | 0.0% | 0.0% | 0.0 |
