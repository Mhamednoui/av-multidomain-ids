Budget 1.0% false alarms on validation normal data. Domain: s2_d23_in_dataset_flag.

| configuration | AUC | detection | false alarms | det Bot | det DDoS-HOIC | det DDoS-LOIC-HTTP | det DDoS-LOIC-UDP | det DoS-GoldenEye | det DoS-Hulk | det DoS-SlowHTTPTest | det DoS-Slowloris | det FTP-Patator | det Infiltration | det SSH-Patator | det Web-BruteForce | det Web-SQLi | det Web-XSS | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.594 | 1.2% | 1.03% | 0.1% | 0.1% | 0.1% | 100.0% | 0.0% | 0.7% | 100.0% | 0.2% | 100.0% | 4.0% | 0.1% | 1.8% | 0.0% | 0.0% | 0.0 |
| only_net.flow_rate | 0.512 | 0.3% | 0.94% | 0.0% | 0.2% | 0.0% | 0.0% | 0.0% | 0.7% | 0.0% | 0.1% | 50.0% | 1.4% | 0.1% | 3.6% | 0.0% | 0.0% | 0.0 |
| only_net.proto_port | 0.594 | 0.7% | 0.84% | 0.1% | 0.0% | 0.1% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 1.2% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| only_net.tcp_flags | 0.575 | 0.7% | 0.96% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.2% | 100.0% | 3.7% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| all_but_net.flow_rate | 0.561 | 1.2% | 0.81% | 0.1% | 0.0% | 0.1% | 100.0% | 0.0% | 0.0% | 100.0% | 0.2% | 100.0% | 4.1% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| all_but_net.proto_port | 0.430 | 0.1% | 1.01% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.6% | 0.0% | 4.5% | 0.0% | 0.0% | 1.0 |
| all_but_net.tcp_flags | 0.675 | 0.9% | 0.98% | 0.2% | 0.6% | 0.1% | 100.0% | 0.0% | 2.1% | 100.0% | 0.2% | 100.0% | 2.2% | 0.1% | 5.5% | 10.0% | 5.7% | 0.0 |
