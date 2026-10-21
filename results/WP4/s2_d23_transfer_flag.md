Budget 1.0% false alarms on validation normal data. Domain: s2_d23_transfer_flag.

| configuration | AUC | detection | false alarms | det Bot | det DDoS-HOIC | det DDoS-LOIC-HTTP | det DDoS-LOIC-UDP | det DoS-GoldenEye | det DoS-Hulk | det DoS-SlowHTTPTest | det DoS-Slowloris | det FTP-Patator | det Infiltration | det SSH-Patator | det Web-BruteForce | det Web-SQLi | det Web-XSS | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.682 | 38.7% | 15.98% | 98.8% | 20.2% | 49.9% | 0.0% | 1.4% | 0.3% | 33.3% | 51.3% | 0.0% | 29.1% | 0.0% | 50.9% | 80.0% | 54.7% | 0.0 |
| only_net.flow_rate | 0.512 | 0.0% | 0.10% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.2% | 0.0% | 0.1% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.0% | 3.0 |
| only_net.proto_port | 0.292 | 0.6% | 0.31% | 0.0% | 0.0% | 0.1% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.0% | 0.0% | 23.6% | 0.0% | 7.5% | 0.0 |
| only_net.tcp_flags | 0.589 | 40.1% | 30.76% | 98.8% | 20.2% | 49.9% | 0.0% | 0.0% | 0.0% | 100.0% | 21.1% | 100.0% | 40.7% | 0.0% | 50.9% | 70.0% | 47.2% | 0.0 |
| all_but_net.flow_rate | 0.693 | 38.7% | 15.89% | 98.8% | 20.2% | 49.9% | 0.0% | 1.4% | 0.3% | 100.0% | 51.3% | 100.0% | 29.0% | 0.0% | 50.9% | 80.0% | 75.5% | 0.0 |
| all_but_net.proto_port | 0.565 | 40.0% | 30.54% | 98.8% | 20.2% | 49.9% | 0.0% | 0.0% | 0.0% | 0.0% | 20.9% | 0.0% | 40.4% | 0.0% | 50.9% | 70.0% | 47.2% | 0.0 |
| all_but_net.tcp_flags | 0.624 | 13.2% | 3.42% | 0.0% | 0.0% | 41.9% | 0.0% | 19.6% | 0.3% | 0.0% | 69.4% | 0.0% | 1.8% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
