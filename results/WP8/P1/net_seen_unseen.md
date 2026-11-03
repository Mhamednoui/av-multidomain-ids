# Network (CIC-IDS2017, D10): seen vs unseen family, operating point only

**re-analysis of v3 test outputs (no refit).** Source: results/WP4/s7_d10.json (`stacks/<stack>/published/detection` = trained-on-all test; `loao/<family>/stacks/<stack>/detection` = that family held out). Only operating-point detection was saved (no per-flow or per-bin scores): no ROC / AUC is possible without a re-run. FA = flow-level false-alarm rate of the stack at its pre-registered operating point.

| stack | family | n_flows | seen_detection_test | unseen_detection_loao | fa_published_stack | loao_fa |
|---|---|---|---|---|---|---|
| H | Bot | 308 | 0.000 | 0.000 | 0.005 | 0.005 |
| H | DDoS-LOIC-HTTP | 25655 | 1.000 | 1.000 | 0.005 | 0.005 |
| H | DoS-GoldenEye | 3347 | 1.000 | 1.000 | 0.005 | 0.005 |
| H | DoS-Hulk | 48337 | 1.000 | 1.000 | 0.005 | 0.005 |
| H | DoS-SlowHTTPTest | 1191 | 0.935 | 0.935 | 0.005 | 0.005 |
| H | DoS-Slowloris | 1278 | 0.347 | 0.347 | 0.005 | 0.005 |
| H | FTP-Patator | 2049 | 1.000 | 1.000 | 0.005 | 0.005 |
| H | SSH-Patator | 1639 | 0.986 | 0.986 | 0.005 | 0.005 |
| H | PortScan | 5150 | 0.980 | 0.000 | 0.005 | 0.003 |
| H | Web-BruteForce | 321 | 0.000 | 0.000 | 0.005 | 0.005 |
| H | Web-XSS | 132 | 0.000 | 0.000 | 0.005 | 0.005 |
| H | Infiltration | 6 | 0.333 |  | 0.005 |  |
| O | Bot | 308 | 0.000 | 0.000 | 0.005 | 0.002 |
| O | DDoS-LOIC-HTTP | 25655 | 1.000 | 1.000 | 0.005 | 0.005 |
| O | DoS-GoldenEye | 3347 | 1.000 | 1.000 | 0.005 | 0.005 |
| O | DoS-Hulk | 48337 | 1.000 | 1.000 | 0.005 | 0.005 |
| O | DoS-SlowHTTPTest | 1191 | 0.992 | 0.992 | 0.005 | 0.007 |
| O | DoS-Slowloris | 1278 | 0.984 | 0.984 | 0.005 | 0.005 |
| O | FTP-Patator | 2049 | 0.977 | 0.977 | 0.005 | 0.005 |
| O | SSH-Patator | 1639 | 0.046 | 0.046 | 0.005 | 0.005 |
| O | PortScan | 5150 | 0.990 | 0.000 | 0.005 | 0.009 |
| O | Web-BruteForce | 321 | 0.000 | 0.000 | 0.005 | 0.005 |
| O | Web-XSS | 132 | 0.000 | 0.000 | 0.005 | 0.005 |
| O | Infiltration | 6 | 0.333 |  | 0.005 |  |
| O+slow | Bot | 308 | 0.000 |  | 0.004 |  |
| O+slow | DDoS-LOIC-HTTP | 25655 | 1.000 |  | 0.004 |  |
| O+slow | DoS-GoldenEye | 3347 | 1.000 |  | 0.004 |  |
| O+slow | DoS-Hulk | 48337 | 1.000 |  | 0.004 |  |
| O+slow | DoS-SlowHTTPTest | 1191 | 0.982 |  | 0.004 |  |
| O+slow | DoS-Slowloris | 1278 | 0.992 |  | 0.004 |  |
| O+slow | FTP-Patator | 2049 | 0.971 |  | 0.004 |  |
| O+slow | SSH-Patator | 1639 | 0.022 |  | 0.004 |  |
| O+slow | PortScan | 5150 | 0.988 |  | 0.004 |  |
| O+slow | Web-BruteForce | 321 | 0.000 |  | 0.004 |  |
| O+slow | Web-XSS | 132 | 0.000 |  | 0.004 |  |
| O+slow | Infiltration | 6 | 0.333 |  | 0.004 |  |
| O+beacon | Bot | 308 | 0.010 |  | 0.005 |  |
| O+beacon | DDoS-LOIC-HTTP | 25655 | 1.000 |  | 0.005 |  |
| O+beacon | DoS-GoldenEye | 3347 | 1.000 |  | 0.005 |  |
| O+beacon | DoS-Hulk | 48337 | 1.000 |  | 0.005 |  |
| O+beacon | DoS-SlowHTTPTest | 1191 | 0.992 |  | 0.005 |  |
| O+beacon | DoS-Slowloris | 1278 | 0.982 |  | 0.005 |  |
| O+beacon | FTP-Patator | 2049 | 0.977 |  | 0.005 |  |
| O+beacon | SSH-Patator | 1639 | 0.046 |  | 0.005 |  |
| O+beacon | PortScan | 5150 | 0.990 |  | 0.005 |  |
| O+beacon | Web-BruteForce | 321 | 0.000 |  | 0.005 |  |
| O+beacon | Web-XSS | 132 | 0.000 |  | 0.005 |  |
| O+beacon | Infiltration | 6 | 0.500 |  | 0.005 |  |
| O+topology | Bot | 308 | 0.000 | 0.000 | 0.010 | 0.010 |
| O+topology | DDoS-LOIC-HTTP | 25655 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | DoS-GoldenEye | 3347 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | DoS-Hulk | 48337 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | DoS-SlowHTTPTest | 1191 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | DoS-Slowloris | 1278 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | FTP-Patator | 2049 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | SSH-Patator | 1639 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | PortScan | 5150 | 1.000 | 1.000 | 0.010 | 0.014 |
| O+topology | Web-BruteForce | 321 | 1.000 | 0.978 | 0.010 | 0.007 |
| O+topology | Web-XSS | 132 | 1.000 | 1.000 | 0.010 | 0.010 |
| O+topology | Infiltration | 6 | 1.000 |  | 0.010 |  |
| O+L4 | Bot | 308 | 0.977 | 0.000 | 0.008 | 0.009 |
| O+L4 | DDoS-LOIC-HTTP | 25655 | 1.000 | 1.000 | 0.008 | 0.009 |
| O+L4 | DoS-GoldenEye | 3347 | 1.000 | 1.000 | 0.008 | 0.008 |
| O+L4 | DoS-Hulk | 48337 | 1.000 | 1.000 | 0.008 | 0.008 |
| O+L4 | DoS-SlowHTTPTest | 1191 | 1.000 | 0.994 | 0.008 | 0.009 |
| O+L4 | DoS-Slowloris | 1278 | 0.991 | 0.720 | 0.008 | 0.009 |
| O+L4 | FTP-Patator | 2049 | 1.000 | 0.981 | 0.008 | 0.008 |
| O+L4 | SSH-Patator | 1639 | 0.516 | 0.027 | 0.008 | 0.009 |
| O+L4 | PortScan | 5150 | 1.000 | 0.019 | 0.008 | 0.008 |
| O+L4 | Web-BruteForce | 321 | 0.891 | 0.844 | 0.008 | 0.008 |
| O+L4 | Web-XSS | 132 | 0.970 | 0.970 | 0.008 | 0.008 |
| O+L4 | Infiltration | 6 | 1.000 |  | 0.008 |  |
| L4 alone | Bot | 308 | 0.981 | 0.000 | 0.012 | 0.014 |
| L4 alone | DDoS-LOIC-HTTP | 25655 | 0.999 | 0.560 | 0.012 | 0.012 |
| L4 alone | DoS-GoldenEye | 3347 | 0.952 | 0.740 | 0.012 | 0.013 |
| L4 alone | DoS-Hulk | 48337 | 0.786 | 0.619 | 0.012 | 0.012 |
| L4 alone | DoS-SlowHTTPTest | 1191 | 0.986 | 0.177 | 0.012 | 0.013 |
| L4 alone | DoS-Slowloris | 1278 | 0.992 | 0.964 | 0.012 | 0.013 |
| L4 alone | FTP-Patator | 2049 | 1.000 | 0.013 | 0.012 | 0.013 |
| L4 alone | SSH-Patator | 1639 | 0.631 | 0.035 | 0.012 | 0.012 |
| L4 alone | PortScan | 5150 | 1.000 | 0.021 | 0.012 | 0.013 |
| L4 alone | Web-BruteForce | 321 | 0.907 | 0.850 | 0.012 | 0.012 |
| L4 alone | Web-XSS | 132 | 0.985 | 0.970 | 0.012 | 0.013 |
| L4 alone | Infiltration | 6 | 1.000 |  | 0.012 |  |