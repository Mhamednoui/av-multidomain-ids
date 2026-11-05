# network (H31, H31 scoring (frozen v3 vs frozen v3.1, one run))

| subset | exposure | n_pos | n_neg | auc | det@1.0% | det@2.0% | op_fa | op_det |
|---|---|---|---|---|---|---|---|---|
| v3 Bot | re-used test (exposure n+1) | 308 | 408781 | 0.148 | 0.000 | 0.000 | 0.005 | 0.000 |
| v3 DDoS-LOIC-HTTP | re-used test (exposure n+1) | 25655 | 408781 | 1.000 | 1.000 | 1.000 | 0.005 | 1.000 |
| v3 DoS-GoldenEye | re-used test (exposure n+1) | 3347 | 408781 | 1.000 | 1.000 | 1.000 | 0.005 | 1.000 |
| v3 DoS-Hulk | re-used test (exposure n+1) | 48337 | 408781 | 1.000 | 1.000 | 1.000 | 0.005 | 1.000 |
| v3 DoS-SlowHTTPTest | re-used test (exposure n+1) | 1191 | 408781 | 0.995 | 0.935 | 0.935 | 0.005 | 0.935 |
| v3 DoS-Slowloris | re-used test (exposure n+1) | 1278 | 408781 | 0.974 | 0.347 | 0.347 | 0.005 | 0.347 |
| v3 FTP-Patator | re-used test (exposure n+1) | 2049 | 408781 | 0.999 | 1.000 | 1.000 | 0.005 | 1.000 |
| v3 SSH-Patator | re-used test (exposure n+1) | 1639 | 408781 | 0.996 | 0.986 | 0.986 | 0.005 | 0.986 |
| v3 PortScan | re-used test (exposure n+1) | 5150 | 408781 | 0.997 | 0.980 | 0.980 | 0.005 | 0.980 |
| v3 Web-BruteForce | re-used test (exposure n+1) | 321 | 408781 | 0.822 | 0.000 | 0.000 | 0.005 | 0.000 |
| v3 Web-XSS | re-used test (exposure n+1) | 132 | 408781 | 0.809 | 0.000 | 0.000 | 0.005 | 0.000 |
| v3 pooled 11 families | re-used test (exposure n+1) | 89407 | 408781 | 0.995 [0.963, 0.999] | 0.980 [0.839, 0.995] | 0.980 [0.840, 0.995] | 0.005 | 0.659 |
| F1 Bot | re-used test (exposure n+1) | 308 | 408781 | 0.165 | 0.000 | 0.003 | 0.007 | 0.000 |
| F1 DDoS-LOIC-HTTP | re-used test (exposure n+1) | 25655 | 408781 | 1.000 | 1.000 | 1.000 | 0.007 | 1.000 |
| F1 DoS-GoldenEye | re-used test (exposure n+1) | 3347 | 408781 | 1.000 | 1.000 | 1.000 | 0.007 | 1.000 |
| F1 DoS-Hulk | re-used test (exposure n+1) | 48337 | 408781 | 1.000 | 1.000 | 1.000 | 0.007 | 1.000 |
| F1 DoS-SlowHTTPTest | re-used test (exposure n+1) | 1191 | 408781 | 0.995 | 0.935 | 0.935 | 0.007 | 0.935 |
| F1 DoS-Slowloris | re-used test (exposure n+1) | 1278 | 408781 | 0.980 | 0.347 | 0.347 | 0.007 | 0.347 |
| F1 FTP-Patator | re-used test (exposure n+1) | 2049 | 408781 | 0.999 | 1.000 | 1.000 | 0.007 | 1.000 |
| F1 SSH-Patator | re-used test (exposure n+1) | 1639 | 408781 | 0.995 | 0.986 | 0.986 | 0.007 | 0.986 |
| F1 PortScan | re-used test (exposure n+1) | 5150 | 408781 | 0.997 | 0.980 | 0.980 | 0.007 | 0.980 |
| F1 Web-BruteForce | re-used test (exposure n+1) | 321 | 408781 | 0.841 | 0.000 | 0.000 | 0.007 | 0.000 |
| F1 Web-XSS | re-used test (exposure n+1) | 132 | 408781 | 0.822 | 0.000 | 0.000 | 0.007 | 0.000 |
| F1 pooled 11 families | re-used test (exposure n+1) | 89407 | 408781 | 0.996 [0.964, 0.999] | 0.980 [0.839, 0.995] | 0.980 [0.841, 0.995] | 0.007 | 0.659 |
| RC5 Bot | re-used test (exposure n+1) | 308 | 408781 | 0.152 | 0.000 | 0.000 | 0.007 | 0.000 |
| RC5 DDoS-LOIC-HTTP | re-used test (exposure n+1) | 25655 | 408781 | 0.999 | 0.987 | 0.988 | 0.007 | 0.986 |
| RC5 DoS-GoldenEye | re-used test (exposure n+1) | 3347 | 408781 | 0.991 | 0.902 | 0.904 | 0.007 | 0.892 |
| RC5 DoS-Hulk | re-used test (exposure n+1) | 48337 | 408781 | 1.000 | 0.993 | 0.993 | 0.007 | 0.992 |
| RC5 DoS-SlowHTTPTest | re-used test (exposure n+1) | 1191 | 408781 | 0.985 | 0.799 | 0.799 | 0.007 | 0.796 |
| RC5 DoS-Slowloris | re-used test (exposure n+1) | 1278 | 408781 | 0.969 | 0.347 | 0.347 | 0.007 | 0.347 |
| RC5 FTP-Patator | re-used test (exposure n+1) | 2049 | 408781 | 0.998 | 0.971 | 0.972 | 0.007 | 0.968 |
| RC5 SSH-Patator | re-used test (exposure n+1) | 1639 | 408781 | 0.996 | 0.948 | 0.949 | 0.007 | 0.941 |
| RC5 PortScan | re-used test (exposure n+1) | 5150 | 408781 | 0.996 | 0.980 | 0.980 | 0.007 | 0.980 |
| RC5 Web-BruteForce | re-used test (exposure n+1) | 321 | 408781 | 0.850 | 0.000 | 0.000 | 0.007 | 0.000 |
| RC5 Web-XSS | re-used test (exposure n+1) | 132 | 408781 | 0.811 | 0.000 | 0.000 | 0.007 | 0.000 |
| RC5 pooled 11 families | re-used test (exposure n+1) | 89407 | 408781 | 0.995 [0.960, 0.998] | 0.966 [0.800, 0.985] | 0.966 [0.809, 0.986] | 0.007 | 0.628 |
