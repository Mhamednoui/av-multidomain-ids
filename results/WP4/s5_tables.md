# WP4 S5 tables (all numbers from results/WP4/s5_*.json; detection in %, 1% tie-safe budget on benign validation unless stated)

## 1. Selection grid on validation (D10; blind4 = mean over Bot, Web-XSS, Web-BruteForce, Slowloris; macro = 11 evaluable families)
| layer | params | blind4 | macro | macro AUC | Bot AUC | Web-XSS AUC | Web-BF AUC | Slowloris det |
|---|---|---|---|---|---|---|---|---|
| service | {"mode": "hbos", "bins": 16} | 0.0 | 0.0 | 0.479 | 0.51 | 0.20 | 0.26 | 0.0 |
| service | {"mode": "hbos", "bins": 32} | 0.0 | 0.0 | 0.478 | 0.64 | 0.21 | 0.26 | 0.0 |
| service | {"mode": "rz_mean", "floor": 0.1} | 0.2 | 0.1 | 0.647 | 0.98 | 0.17 | 0.25 | 0.0 |
| service | {"mode": "rz_mean", "floor": 0.3} | 0.2 | 0.1 | 0.658 | 0.95 | 0.21 | 0.29 | 0.0 |
| service | {"mode": "rz_top3", "floor": 0.1} | 0.0 | 0.0 | 0.641 | 0.84 | 0.16 | 0.23 | 0.0 |
| service | {"mode": "rz_top3", "floor": 0.3} | 0.0 | 0.0 | 0.669 | 0.86 | 0.18 | 0.26 | 0.0 |
| service | {"mode": "maha", "floor": 0.1} | 9.3 | 12.4 | 0.861 | 0.98 | 0.61 | 0.67 | 36.4 |
| service | {"mode": "maha", "floor": 0.3} | 9.3 | 18.1 | 0.868 | 0.99 | 0.66 | 0.70 | 36.4 |
| iforest | {"max_samples": 256, "max_features": 1.0} | 6.6 | 6.8 | 0.834 | 0.94 | 0.88 | 0.84 | 26.6 |
| iforest | {"max_samples": 2048, "max_features": 1.0} | 6.6 | 9.7 | 0.862 | 0.96 | 0.83 | 0.79 | 26.6 |
| iforest | {"max_samples": 256, "max_features": 0.5} | 6.6 | 6.8 | 0.841 | 0.93 | 0.89 | 0.84 | 26.6 |
| iforest | {"max_samples": 2048, "max_features": 0.5} | 6.6 | 10.4 | 0.866 | 0.96 | 0.82 | 0.78 | 26.6 |
| ae | {"hidden": [32, 12, 32]} | 22.5 | 37.3 | 0.833 | 0.94 | 0.70 | 0.66 | 90.1 |
| ae | {"hidden": [48, 16, 6, 16, 48]} | 15.7 | 29.0 | 0.861 | 0.93 | 0.82 | 0.76 | 62.7 |
| service | {"mode": "maha", "floor": 0.1, "svc_norm": true} | 9.3 | 32.5 | 0.866 | 0.98 | 0.44 | 0.52 | 36.4 |
| service | {"mode": "maha", "floor": 0.3, "svc_norm": true} | 9.3 | 32.4 | 0.871 | 0.98 | 0.47 | 0.55 | 36.4 |
| service | {"mode": "rz_mean", "floor": 0.3, "svc_norm": true} | 0.0 | 9.1 | 0.567 | 0.92 | 0.10 | 0.16 | 0.0 |
| iforest | {"max_samples": 2048, "max_features": 0.5, "svc_norm": true} | 6.6 | 7.1 | 0.771 | 0.90 | 0.77 | 0.72 | 26.6 |
| iforest | {"max_samples": 256, "max_features": 1.0, "svc_norm": true} | 0.0 | 4.4 | 0.726 | 0.88 | 0.85 | 0.77 | 0.0 |
| ae | {"hidden": [32, 12, 32], "svc_norm": true} | 22.5 | 38.3 | 0.776 | 0.91 | 0.53 | 0.51 | 90.1 |

Chosen: {"service": {"params": {"mode": "maha", "floor": 0.1, "svc_norm": true}, "blind4": 0.0933952728969056, "macro": 0.32512660968116713}, "iforest": {"params": {"max_samples": 2048, "max_features": 0.5}, "blind4": 0.06638418079096045, "macro": 0.10351624617889045}, "ae": {"params": {"hidden": [32, 12, 32], "svc_norm": true}, "blind4": 0.2252824858757062, "macro": 0.3825966630949009}}

## 2. D10 test, per layer (flow unit, clean features). n = test flows
| family | n | service det | iforest det | ae det | service AUC | iforest AUC | ae AUC |
|---|---|---|---|---|---|---|---|
| Bot | 308 | 0.0 | 0.0 | 0.0 | 96.8 | 94.7 | 90.3 |
| DDoS-LOIC-HTTP | 25655 | 22.3 | 11.2 | 61.8 | 96.9 | 96.0 | 98.5 |
| DoS-GoldenEye | 3347 | 15.7 | 23.1 | 32.3 | 93.2 | 92.7 | 92.5 |
| DoS-Hulk | 48337 | 63.3 | 18.6 | 59.6 | 94.6 | 86.4 | 77.2 |
| DoS-SlowHTTPTest | 1191 | 84.3 | 79.5 | 97.1 | 99.2 | 99.4 | 99.5 |
| DoS-Slowloris | 1278 | 49.7 | 15.3 | 78.0 | 97.4 | 94.8 | 99.2 |
| FTP-Patator | 2049 | 100.0 | 0.0 | 0.1 | 99.7 | 86.4 | 54.0 |
| Infiltration | 6 | 100.0 | 66.7 | 33.3 | 99.6 | 98.9 | 94.4 |
| PortScan | 5150 | 2.1 | 0.3 | 98.5 | 93.4 | 86.5 | 99.6 |
| SSH-Patator | 1639 | 51.3 | 0.0 | 1.8 | 87.4 | 59.8 | 45.5 |
| Web-BruteForce | 321 | 0.0 | 0.0 | 0.0 | 52.3 | 78.8 | 51.7 |
| Web-XSS | 132 | 0.0 | 0.0 | 0.0 | 45.3 | 82.1 | 54.8 |

| layer | FA benign test (headline) | FA published labels | FA on audited file (%) | macro 11 | blind4 | macro AUC | FA at the 5% budget | epochs |
|---|---|---|---|---|---|---|---|---|
| net.l3_service | 0.92% | 1.01% | 1.4 | 35.3 | 12.4 | 0.869 | 5.22% | None |
| net.l3_iforest | 1.12% | 1.06% | 0.8 | 13.5 | 3.8 | 0.871 | 5.20% | None |
| net.l3_ae | 1.02% | 5.90% | 28.6 | 39.0 | 19.5 | 0.784 | 4.57% | 60 |

### 2b. Diagnostics: detection at a 5% budget, and median benign-rank of each family (1.0 = above every benign flow)
| family | service det@5% | iforest det@5% | ae det@5% | service rank | iforest rank | ae rank |
|---|---|---|---|---|---|---|
| Bot | 98.1 | 96.1 | 1.0 | 0.98 | 0.96 | 0.92 |
| DDoS-LOIC-HTTP | 85.6 | 79.9 | 92.8 | 0.97 | 0.98 | 0.99 |
| DoS-GoldenEye | 33.7 | 32.2 | 38.7 | 0.93 | 0.92 | 0.94 |
| DoS-Hulk | 65.8 | 59.8 | 60.9 | 0.99 | 0.97 | 1.00 |
| DoS-SlowHTTPTest | 99.5 | 98.4 | 97.7 | 0.99 | 1.00 | 1.00 |
| DoS-Slowloris | 73.8 | 63.5 | 91.9 | 0.98 | 0.96 | 1.00 |
| FTP-Patator | 100.0 | 0.0 | 12.7 | 1.00 | 0.93 | 0.92 |
| Infiltration | 100.0 | 100.0 | 50.0 | 1.00 | 0.99 | 0.96 |
| PortScan | 23.5 | 1.6 | 98.8 | 0.92 | 0.86 | 1.00 |
| SSH-Patator | 52.5 | 1.0 | 9.0 | 0.99 | 0.86 | 0.79 |
| Web-BruteForce | 14.3 | 4.7 | 0.0 | 0.44 | 0.83 | 0.55 |
| Web-XSS | 2.3 | 2.3 | 0.0 | 0.44 | 0.82 | 0.55 |

### 2c. Detection on the flows that survive de-duplication / on all pre-dedup flows
| family | service | iforest | ae |
|---|---|---|---|
| Bot | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| DDoS-LOIC-HTTP | 22.3 / 22.3 | 11.2 / 11.2 | 61.8 / 61.8 |
| DoS-GoldenEye | 15.7 / 15.7 | 23.1 / 23.1 | 32.3 / 32.3 |
| DoS-Hulk | 88.3 / 63.3 | 26.1 / 18.6 | 83.2 / 59.6 |
| DoS-SlowHTTPTest | 82.5 / 84.3 | 78.1 / 79.5 | 96.9 / 97.1 |
| DoS-Slowloris | 45.4 / 49.7 | 16.6 / 15.3 | 84.7 / 78.0 |
| FTP-Patator | 100.0 / 100.0 | 0.0 / 0.0 | 0.2 / 0.1 |
| Infiltration | 100.0 / 100.0 | 66.7 / 66.7 | 33.3 / 33.3 |
| PortScan | 42.7 / 2.1 | 8.9 / 0.3 | 58.9 / 98.5 |
| SSH-Patator | 96.3 / 51.3 | 0.0 / 0.0 | 3.3 / 1.8 |
| Web-BruteForce | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |
| Web-XSS | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 |

## 3. Hygiene: clean vs all 76 columns, D10 test
| layer | FA clean | FA all | macro clean | macro all | blind4 clean | blind4 all | macro AUC clean | macro AUC all |
|---|---|---|---|---|---|---|---|---|
| net.l3_service | 0.92 | 0.97 | 35.3 | 35.1 | 12.4 | 12.4 | 0.869 | 0.865 |
| net.l3_iforest | 1.12 | 1.14 | 13.5 | 9.1 | 3.8 | 3.7 | 0.871 | 0.873 |
| net.l3_ae | 1.02 | 1.00 | 39.0 | 35.3 | 19.5 | 22.4 | 0.784 | 0.832 |

## 4. Harness ablation (tcp_flags + L2a + L3, logistic combiner, subsample as S3 / S4), D10 test
| configuration | combined FA | detection (all attack flows) | macro 11 | blind4 | Bot | DDoS-LOIC-HTTP | DoS-GoldenEye | DoS-Hulk | DoS-SlowHTTPTest | DoS-Slowloris | FTP-Patator | SSH-Patator | PortScan | Web-BruteForce | Web-XSS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 0.33% | 93.1 | 54.2 | 2.1 | 0.0 | 100.0 | 100.0 | 100.0 | 93.5 | 8.5 | 97.1 | 0.1 | 97.4 | 0.0 | 0.0 |
| base_svc | 0.53% | 94.0 | 57.5 | 9.9 | 0.0 | 100.0 | 100.0 | 100.0 | 94.5 | 39.4 | 98.0 | 3.1 | 97.8 | 0.0 | 0.0 |
| base_if | 0.60% | 93.1 | 54.2 | 2.1 | 0.0 | 100.0 | 100.0 | 100.0 | 93.5 | 8.5 | 97.1 | 0.1 | 97.4 | 0.0 | 0.0 |
| base_ae | 0.57% | 94.4 | 59.2 | 13.9 | 0.0 | 100.0 | 100.0 | 100.0 | 98.2 | 55.6 | 97.1 | 1.2 | 99.0 | 0.0 | 0.0 |
| base_l3 | 0.74% | 94.9 | 61.0 | 18.0 | 0.0 | 100.0 | 100.0 | 100.0 | 99.2 | 71.9 | 98.0 | 2.7 | 99.0 | 0.0 | 0.0 |
| l3_only | 1.04% | 49.9 | 29.5 | 16.2 | 0.0 | 55.9 | 31.2 | 65.0 | 98.3 | 64.9 | 0.1 | 1.8 | 7.7 | 0.0 | 0.0 |

Ablation inside base_l3 (each layer alone / all but one): results/WP4/s5_d10_base_l3.md.

OR view (any layer alarms; the 1% budgets add up):
| view | FA benign | FA published | Bot | DDoS-LOIC-HTTP | DoS-GoldenEye | DoS-Hulk | DoS-SlowHTTPTest | DoS-Slowloris | FTP-Patator | SSH-Patator | PortScan | Web-BruteForce | Web-XSS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| base | 3.63% | 8.76% | 1.0 | 100.0 | 100.0 | 100.0 | 93.5 | 34.7 | 100.0 | 98.6 | 98.0 | 0.0 | 0.0 |
| base_l3 | 5.45% | 10.44% | 1.0 | 100.0 | 100.0 | 100.0 | 99.3 | 99.6 | 100.0 | 99.3 | 99.3 | 0.0 | 0.0 |
| l3 | 2.21% | 7.02% | 0.0 | 63.3 | 32.3 | 65.4 | 98.7 | 99.6 | 100.0 | 51.3 | 98.9 | 0.0 | 0.0 |

## 5. Bot: is a hit the fixed flow signature?
Signature from Bot TRAIN flows to port 8080: 4 fwd / 3 bwd packets, duration 61952-123488 us; 73.2% of the 840 train flows to 8080; shapes {'4/3': 615, '3/3': 77, '5/4': 70, '1/1': 32, '28/54': 3}.

Test: 308 Bot flows, 3 match the signature (shape + port 8080), 302 go to port 8080; benign flows matching the signature: 0 of 408781 (shape on any port: 11); benign share on port 8080: 0.07%.

| layer | Bot det | alarms | alarms matching signature | det on matching | det on non-matching | FA of benign matching signature | median benign-rank of Bot |
|---|---|---|---|---|---|---|---|
| net.l3_service | 0.0 | 0 | 0 | 0.0 | 0.0 | - | 0.98 |
| net.l3_iforest | 0.0 | 0 | 0 | 0.0 | 0.0 | - | 0.96 |
| net.l3_ae | 0.0 | 0 | 0 | 0.0 | 0.0 | - | 0.92 |

D23 sample (test side): 35623 Bot flows; same shape 0, shape and port 8080 0; benign with shape and port 8080: 0; Bot destination ports {'8080': 32155, '0': 97, '50994': 5}.

## 6. Feature attributions (top-5 features by mean share of the positive score contribution; top 200 alarmed flows per group; D10 test)
### net.l3_service
| group | flows | top features (share) |
|---|---|---|
| DDoS-LOIC-HTTP | 200 | Idle Std 0.21; Bwd Pkt Len Min 0.07; PSH Flag Cnt 0.06; ACK Flag Cnt 0.06; Idle Max 0.04 |
| DoS-GoldenEye | 200 | Bwd Pkt Len Min 0.12; Idle Min 0.08; Idle Mean 0.08; Idle Max 0.08; Fwd IAT Min 0.07 |
| DoS-Hulk | 200 | FIN Flag Cnt 0.92; PSH Flag Cnt 0.01; Idle Max 0.01; Idle Mean 0.01; Idle Min 0.01 |
| DoS-SlowHTTPTest | 200 | Fwd Pkt Len Min 0.35; SYN Flag Cnt 0.29; Bwd Pkts/s 0.07; Idle Std 0.03; Flow IAT Min 0.02 |
| DoS-Slowloris | 200 | SYN Flag Cnt 0.74; Fwd Pkt Len Min 0.03; Bwd IAT Min 0.02; Fwd IAT Std 0.02; Idle Min 0.02 |
| FTP-Patator | 200 | SYN Flag Cnt 0.92; Fwd IAT Min 0.01; Fwd Pkt Len Std 0.00; Fwd Act Data Pkts 0.00; Flow IAT Min 0.00 |
| Infiltration | 6 | SYN Flag Cnt 0.35; Fwd IAT Min 0.11; Bwd IAT Min 0.11; Pkt Len Min 0.05; Active Min 0.04 |
| PortScan | 108 | Bwd IAT Min 0.23; Fwd IAT Min 0.18; PSH Flag Cnt 0.08; ACK Flag Cnt 0.06; Flow IAT Min 0.06 |
| SSH-Patator | 200 | Fwd IAT Min 0.35; Bwd IAT Min 0.26; SYN Flag Cnt 0.05; Flow IAT Mean 0.05; Bwd IAT Mean 0.04 |
| BENIGN | 200 | Active Std 0.19; Idle Std 0.19; FIN Flag Cnt 0.10; Bwd Pkt Len Min 0.05; Bwd IAT Min 0.04 |

### net.l3_iforest
| group | flows | top features (share) |
|---|---|---|
| DDoS-LOIC-HTTP | 200 | Idle Std 0.14; ACK Flag Cnt 0.13; Pkt Len Std 0.08; Pkt Len Mean 0.07; Bwd Pkt Len Mean 0.07 |
| DoS-GoldenEye | 200 | Idle Mean 0.21; Idle Max 0.12; Idle Min 0.11; Fwd IAT Min 0.08; Fwd Pkt Len Max 0.06 |
| DoS-Hulk | 200 | Idle Mean 0.15; Idle Std 0.14; Idle Max 0.12; Idle Min 0.09; Active Max 0.05 |
| DoS-SlowHTTPTest | 200 | Idle Max 0.11; Idle Mean 0.10; Active Min 0.09; Active Max 0.09; Idle Std 0.09 |
| DoS-Slowloris | 196 | SYN Flag Cnt 0.12; Idle Min 0.09; Idle Max 0.08; ACK Flag Cnt 0.08; Bwd Pkt Len Mean 0.06 |
| Infiltration | 4 | SYN Flag Cnt 0.31; Idle Std 0.21; ACK Flag Cnt 0.12; Bwd Pkt Len Max 0.06; Bwd Pkt Len Mean 0.05 |
| PortScan | 17 | Bwd Pkt Len Mean 0.12; Bwd Pkts/s 0.09; Flow Byts/s 0.08; Fwd Pkt Len Mean 0.07; Pkt Len Var 0.07 |
| BENIGN | 200 | Active Max 0.12; Tot Fwd Pkts 0.08; Idle Min 0.07; Idle Std 0.07; Idle Max 0.06 |

### net.l3_ae
| group | flows | top features (share) |
|---|---|---|
| DDoS-LOIC-HTTP | 200 | Bwd IAT Min 0.14; ACK Flag Cnt 0.07; PSH Flag Cnt 0.07; Fwd Act Data Pkts 0.06; Pkt Len Max 0.04 |
| DoS-GoldenEye | 200 | Fwd IAT Std 0.16; Idle Min 0.14; Idle Mean 0.14; Idle Max 0.13; Bwd IAT Min 0.06 |
| DoS-Hulk | 200 | FIN Flag Cnt 0.16; Bwd IAT Min 0.11; Flow IAT Min 0.07; Fwd Act Data Pkts 0.06; Fwd Pkt Len Mean 0.05 |
| DoS-SlowHTTPTest | 200 | Fwd Pkt Len Min 0.13; Down/Up Ratio 0.08; Fwd Pkt Len Std 0.07; Pkt Len Min 0.05; Fwd Pkt Len Mean 0.04 |
| DoS-Slowloris | 200 | Flow IAT Min 0.07; Idle Min 0.07; Idle Max 0.07; Idle Mean 0.07; Fwd IAT Std 0.06 |
| FTP-Patator | 3 | Down/Up Ratio 0.26; Flow IAT Min 0.13; Fwd Header Len 0.11; Pkt Len Min 0.04; Fwd IAT Max 0.03 |
| Infiltration | 2 | Active Std 0.12; Bwd Pkt Len Max 0.12; Pkt Len Std 0.08; Pkt Len Var 0.08; Bwd Pkt Len Mean 0.04 |
| PortScan | 200 | PSH Flag Cnt 0.34; ACK Flag Cnt 0.25; Fwd IAT Min 0.06; Down/Up Ratio 0.03; Bwd Pkt Len Mean 0.02 |
| SSH-Patator | 29 | Fwd IAT Std 0.13; PSH Flag Cnt 0.10; ACK Flag Cnt 0.07; Flow IAT Min 0.05; Bwd IAT Std 0.04 |
| BENIGN | 200 | ACK Flag Cnt 0.08; Active Min 0.05; Bwd Pkt Len Min 0.05; Flow Pkts/s 0.05; Bwd Pkt Len Std 0.04 |

### Ports of the benign false alarms (D10 test)
| layer | false alarms | top ports (share) |
|---|---|---|
| net.l3_service | 3762 | 53 0.37; 443 0.25; 80 0.08; 8080 0.02; 22 0.01; 49666 0.01 |
| net.l3_iforest | 4593 | 443 0.32; 80 0.12; 0 0.05; 138 0.04; 389 0.03; 8080 0.01 |
| net.l3_ae | 4152 | 53 0.39; 443 0.24; 80 0.08; 22 0.01; 139 0.00; 21 0.00 |

## 7. D23 sample (test side test): zero-shot (D10 fit and threshold), threshold re-calibrated on D23 benign validation (no refit), refit on D23 benign
Test sample: 500000 benign, attacks {'Bot': 35623, 'DDoS-HOIC': 1444, 'DDoS-LOIC-HTTP': 60000, 'DDoS-LOIC-UDP': 351, 'DoS-GoldenEye': 11570, 'DoS-Hulk': 878, 'DoS-SlowHTTPTest': 3, 'DoS-Slowloris': 2326, 'FTP-Patator': 2, 'Infiltration': 18880, 'SSH-Patator': 20174, 'Web-BruteForce': 110, 'Web-SQLi': 20, 'Web-XSS': 53}.

### zero-shot
| layer | FA benign | macro 9 | macro 9 AUC | benign median score / D10-or-D23 val median | FA by day (max) |
|---|---|---|---|---|---|
| net.l3_service | 36.15% | 35.4 | 0.523 | 4.67 | 100.0% |
| net.l3_iforest | 6.54% | 21.8 | 0.683 | 1.11 | 14.7% |
| net.l3_ae | 14.15% | 40.1 | 0.603 | 2.96 | 97.1% |

| family | n | service det | iforest det | ae det | service AUC | iforest AUC | ae AUC |
|---|---|---|---|---|---|---|---|
| Bot | 35623 | 10.4 | 1.0 | 1.0 | 0.55 | 0.77 | 0.49 |
| DDoS-HOIC | 1444 | 0.0 | 0.0 | 0.0 | 0.13 | 0.36 | 0.10 |
| DDoS-LOIC-HTTP | 60000 | 18.1 | 30.4 | 93.7 | 0.45 | 0.85 | 0.93 |
| DDoS-LOIC-UDP | 351 | 99.7 | 99.4 | 100.0 | 0.97 | 0.96 | 0.99 |
| DoS-GoldenEye | 11570 | 5.4 | 10.1 | 24.1 | 0.31 | 0.64 | 0.60 |
| DoS-Hulk | 878 | 0.0 | 0.0 | 0.3 | 0.18 | 0.51 | 0.16 |
| DoS-SlowHTTPTest | 3 | 100.0 | 0.0 | 100.0 | 0.86 | 0.25 | 0.99 |
| DoS-Slowloris | 2326 | 38.3 | 20.6 | 95.6 | 0.69 | 0.90 | 0.97 |
| FTP-Patator | 2 | 100.0 | 0.0 | 100.0 | 0.86 | 0.37 | 0.99 |
| Infiltration | 18880 | 24.1 | 6.9 | 18.0 | 0.44 | 0.45 | 0.52 |
| SSH-Patator | 20174 | 99.2 | 0.0 | 0.0 | 0.68 | 0.55 | 0.26 |
| Web-BruteForce | 110 | 23.6 | 28.2 | 28.2 | 0.49 | 0.66 | 0.56 |
| Web-SQLi | 20 | 0.0 | 0.0 | 0.0 | 0.22 | 0.51 | 0.31 |
| Web-XSS | 53 | 7.5 | 7.5 | 7.5 | 0.45 | 0.66 | 0.46 |

### re-calibrated threshold, no refit
| layer | FA benign | macro 9 | macro 9 AUC | benign median score / D10-or-D23 val median | FA by day (max) |
|---|---|---|---|---|---|
| net.l3_service | 1.07% | 2.4 | 0.523 | 1.05 | 2.4% |
| net.l3_iforest | 1.05% | 3.1 | 0.683 | 1.00 | 2.1% |
| net.l3_ae | 1.02% | 28.1 | 0.603 | 1.01 | 2.6% |

| family | n | service det | iforest det | ae det | service AUC | iforest AUC | ae AUC |
|---|---|---|---|---|---|---|---|
| Bot | 35623 | 0.0 | 0.2 | 0.1 | 0.55 | 0.77 | 0.49 |
| DDoS-HOIC | 1444 | 0.0 | 0.0 | 0.0 | 0.13 | 0.36 | 0.10 |
| DDoS-LOIC-HTTP | 60000 | 0.0 | 0.0 | 40.4 | 0.45 | 0.85 | 0.93 |
| DDoS-LOIC-UDP | 351 | 0.0 | 0.0 | 100.0 | 0.97 | 0.96 | 0.99 |
| DoS-GoldenEye | 11570 | 0.0 | 0.0 | 19.7 | 0.31 | 0.64 | 0.60 |
| DoS-Hulk | 878 | 0.0 | 0.0 | 0.0 | 0.18 | 0.51 | 0.16 |
| DoS-SlowHTTPTest | 3 | 0.0 | 0.0 | 66.7 | 0.86 | 0.25 | 0.99 |
| DoS-Slowloris | 2326 | 20.4 | 0.0 | 65.0 | 0.69 | 0.90 | 0.97 |
| FTP-Patator | 2 | 0.0 | 0.0 | 100.0 | 0.86 | 0.37 | 0.99 |
| Infiltration | 18880 | 1.5 | 4.2 | 4.4 | 0.44 | 0.45 | 0.52 |
| SSH-Patator | 20174 | 0.0 | 0.0 | 0.0 | 0.68 | 0.55 | 0.26 |
| Web-BruteForce | 110 | 0.0 | 23.6 | 23.6 | 0.49 | 0.66 | 0.56 |
| Web-SQLi | 20 | 0.0 | 0.0 | 0.0 | 0.22 | 0.51 | 0.31 |
| Web-XSS | 53 | 0.0 | 7.5 | 7.5 | 0.45 | 0.66 | 0.46 |

### refit on D23
| layer | FA benign | macro 9 | macro 9 AUC | benign median score / D10-or-D23 val median | FA by day (max) |
|---|---|---|---|---|---|
| net.l3_service | 0.96% | 24.0 | 0.850 | 1.00 | 1.7% |
| net.l3_iforest | 1.00% | 18.6 | 0.840 | 1.00 | 2.2% |
| net.l3_ae | 1.03% | 27.8 | 0.775 | 1.03 | 2.1% |

| family | n | service det | iforest det | ae det | service AUC | iforest AUC | ae AUC |
|---|---|---|---|---|---|---|---|
| Bot | 35623 | 0.9 | 0.5 | 0.9 | 0.97 | 0.90 | 0.95 |
| DDoS-HOIC | 1444 | 0.0 | 0.0 | 0.0 | 0.64 | 0.71 | 0.51 |
| DDoS-LOIC-HTTP | 60000 | 3.2 | 0.1 | 42.1 | 0.91 | 0.91 | 0.89 |
| DDoS-LOIC-UDP | 351 | 100.0 | 100.0 | 100.0 | 1.00 | 0.99 | 1.00 |
| DoS-GoldenEye | 11570 | 4.8 | 1.5 | 2.8 | 0.87 | 0.75 | 0.89 |
| DoS-Hulk | 878 | 0.3 | 0.0 | 0.0 | 0.51 | 0.85 | 0.64 |
| DoS-SlowHTTPTest | 3 | 0.0 | 0.0 | 0.0 | 0.47 | 0.95 | 0.65 |
| DoS-Slowloris | 2326 | 79.1 | 37.4 | 77.0 | 0.99 | 0.97 | 1.00 |
| FTP-Patator | 2 | 0.0 | 0.0 | 0.0 | 0.55 | 0.95 | 0.69 |
| Infiltration | 18880 | 3.1 | 3.9 | 2.6 | 0.57 | 0.60 | 0.54 |
| SSH-Patator | 20174 | 0.0 | 0.0 | 0.0 | 0.89 | 0.89 | 0.52 |
| Web-BruteForce | 110 | 24.5 | 23.6 | 24.5 | 0.80 | 0.83 | 0.66 |
| Web-SQLi | 20 | 0.0 | 0.0 | 0.0 | 0.89 | 0.79 | 0.76 |
| Web-XSS | 53 | 45.3 | 7.5 | 45.3 | 0.93 | 0.93 | 0.77 |
