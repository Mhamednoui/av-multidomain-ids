## T1 Candidates on D10 validation (stack H, mixed val stream, 11 families; delay = flow level; lag = first alarm available after the first attack flow, median over families)

| candidate | Evidence emitted | macro % | paired diff to v3 (points) [95% CI] | FA % | delay median / max s | lag s | first-tick attack flows alarmed | N1 | N2 FA | N2 macro |
|---|---|---|---|---|---|---|---|---|---|---|
| v3 | 5-minute bin close (NetworkRunner) | 58.3 | - | 0.96 | 120 / 307 | 120.0 | 0.59 | - | - | - |
| R5 | flow arrival (running statistics) | 50.7 | -7.60 [-13.27, -2.73] | 1.00 | 0 / 0 | 0.0 | 0.49 | yes | yes | NO |
| R2 | flow arrival (running statistics) | 46.5 | -11.79 [-16.59, -6.53] | 0.99 | 0 / 0 | 0.0 | 0.44 | yes | yes | NO |
| R1 | flow arrival (running statistics) | 47.0 | -11.22 [-16.10, -6.19] | 1.00 | 0 / 0 | 0.0 | 0.45 | yes | yes | NO |
| RC5 | flow arrival (running statistics) | 55.4 | -2.90 [-4.49, -0.34] | 0.93 | 0 / 0 | 0.0 | 0.46 | yes | yes | yes |
| RC2 | flow arrival (running statistics) | 52.5 | -5.74 [-8.38, -0.88] | 0.95 | 0 / 0 | 0.0 | 0.42 | yes | yes | NO |
| RC1 | flow arrival (running statistics) | 52.6 | -5.65 [-8.23, -0.83] | 0.99 | 0 / 0 | 0.0 | 0.42 | yes | yes | NO |
| F1 | minute close | 57.9 | -0.34 [-1.14, 0.00] | 0.96 | 60 / 76 | 60.0 | 0.59 | yes | yes | yes |

Round 1 (R5/R2/R1) feasible: none. Round 2 feasible: ['RC5', 'F1']; chosen by the pre-registered rule (lowest median delay, then macro, G8): **RC5**. FA bound 1.0 %.

## T2 Detection per family on D10 validation, % of flows (n = val flows)

| family | n | v3 | R5 | RC5 | RC2 | RC1 | F1 |
|---|---|---|---|---|---|---|---|
| Bot | 109 | 5.5 | 3.7 | 5.5 | 1.8 | 2.8 | 1.8 |
| DDoS-LOIC-HTTP | 19035 | 100.0 | 95.6 | 98.1 | 98.1 | 98.1 | 100.0 |
| DoS-GoldenEye | 312 | 0.6 | 8.0 | 0.6 | 0.6 | 0.6 | 0.6 |
| DoS-Hulk | 37843 | 100.0 | 97.9 | 99.1 | 99.1 | 99.1 | 100.0 |
| DoS-SlowHTTPTest | 1418 | 97.4 | 70.1 | 75.3 | 75.3 | 75.3 | 97.4 |
| DoS-Slowloris | 708 | 37.3 | 41.2 | 37.3 | 9.9 | 9.9 | 37.3 |
| FTP-Patator | 1418 | 100.0 | 80.6 | 97.7 | 97.7 | 97.7 | 100.0 |
| SSH-Patator | 1055 | 100.0 | 60.4 | 95.5 | 95.5 | 95.5 | 100.0 |
| PortScan | 2011 | 100.0 | 99.8 | 99.8 | 99.7 | 99.7 | 99.9 |
| Web-BruteForce | 317 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Web-XSS | 97 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| macro | | 58.3 | 50.7 | 55.4 | 52.5 | 52.6 | 57.9 |
| FA % | | 0.96 | 1.00 | 0.93 | 0.95 | 0.99 | 0.96 |

v3 reproduction: frozen domain on the rebuilt val cache gives FA 0.0095996177, macro 0.5825676723 (stored WP4 S7 val view: identical, tests/v31/test_s4_regression.py); combined threshold re-derived from the rebuilt benign val stream 0.995701 vs frozen 0.996067.

## T3 Streaming object RC5 on real val flows (one flow at a time)

| val slice | flows | families | max abs score diff stream vs batch | alarm mismatches | prefix == full | Evidence t == flow ts |
|---|---|---|---|---|---|---|
| 2017-07-04 | 25000 | BENIGN 23582, FTP-Patator 1418 | 0 | 0 | True | True |
| 2017-07-05 | 25000 | BENIGN 19392, DoS-Hulk 3482, DoS-SlowHTTPTest 1418, DoS-Slowloris 708 | 0 | 0 | True | True |
| 2017-07-07 | 25000 | BENIGN 24954, Bot 46 | 0 | 0 | True | True |

Per-push compute (n = 75000, includes the one-row tcp_flags frame; system CPU 35 % with other workers running): median 2.75 ms, p95 3.92 ms, p99 5.14 ms, max 116.2 ms (N3 limit p99 <= 1000 ms: True; v3 stall 1.4 s median / 7.7 s max at each bin close).

### T3b Streaming object F1 (Stream31Final: tick-final emission)

Fitted on the benign val stream it reproduces the F1 row of T1 (macro 0.5791, FA 0.0096; max abs score diff to the float32 saved scores 3.0e-08, alarm mismatches 0). Streaming == batch on the same three slices: max abs score diff [0.0], alarm mismatches [0]; stream-time delay median 60 s (emission when the first flow of the next tick arrives); the maximum 6960 s of the slices is the gap between recording periods in which no flow arrives to trigger the flush (a clock timer closes the tick: delay <= 1 tick). Per-push compute (incl. the tick flush): median 0.88 ms, p99 2.27 ms, max 765 ms.

## T4 Unseen Bot, part A: where the Bot flows (val, published labels, n = 109; corrected by the documented rule n = 265) sit in the H layers

| layer | AUC Bot vs benign | median calibrated score of Bot | Bot flows above the layer's 1% threshold | median raw Bot | median raw benign | p99 raw benign |
|---|---|---|---|---|---|---|
| net.tcp_flags | 0.565 | 0.455 | 0.0 % | 0.407 | 0.407 | 2.41 |
| net.scan | 0.356 | 0.308 | 0.0 % | 1.09 | 1.82 | 4.39 |
| net.trw | 0.440 | 0.000 | 5.5 % | 0 | 0 | 22.2 |
| net.bruteforce | 0.165 | 0.135 | 0.0 % | -1.48 | -0.574 | 0.862 |

Flow shape: 3 distinct Bot shapes (fwd/bwd packets, fwd/bwd bytes, dst port); every Bot flow has its shape among the BENIGN-labelled headline flows; 120 BENIGN-labelled val flows carry a Bot shape (116 from an Ares victim to the C2: the label noise of WP4 S6), so an exact-shape detector has precision at most 47.6 %.

| Bot group (published labels) src -> dst:port | flows | active minutes | median gap (min) | span (min) | flows per active minute |
|---|---|---|---|---|---|
| 192.168.10.15 -> 205.174.165.73:8080 | 31 | 22 | 1.0 | 26 | 1.41 |
| 192.168.10.8 -> 205.174.165.73:8080 | 31 | 22 | 1.0 | 26 | 1.41 |
| 192.168.10.14 -> 205.174.165.73:8080 | 15 | 15 | 2.0 | 25 | 1.00 |
| 192.168.10.5 -> 205.174.165.73:8080 | 15 | 15 | 2.0 | 25 | 1.00 |
| 192.168.10.9 -> 205.174.165.73:8080 | 15 | 15 | 2.0 | 25 | 1.00 |
| 192.168.10.17 -> 52.7.235.158:8080 | 2 | 2 | 1.0 | 2 | 1.00 |

## T5 Unseen Bot, part B: label-free candidates (fit on benign train, 1% of benign val; added to H at a constant 1% combined budget)

| candidate | alone: Bot published % | Bot corrected % | groups hit | FA % | AUC | precision | + H: Bot % | + H: macro % (diff) | + H: FA % | counts for N4 |
|---|---|---|---|---|---|---|---|---|---|---|
| BOT-A | 27.5 | 11.3 | 3 / 6 | 0.98 | 0.618 | 0.8 % | 5.5 | 42.2 (-16.0) | 0.76 | False |
| BOT-B | 0.0 | 0.0 | 0 / 6 | 0.00 | 0.389 | 0.0 % | 5.5 | 58.3 (0.0) | 1.00 | False |
| BOT-C | 71.6 | 59.6 | 5 / 6 | 0.99 | 0.805 | 2.1 % | 5.5 | 55.8 (-2.5) | 0.84 | False |
| BOT-D | 71.6 | 59.6 | 5 / 6 | 0.99 | 0.794 | 2.1 % | 5.5 | 55.8 (-2.5) | 0.84 | False |

H reference on the same stream: Bot 5.5 %, macro 58.3 %, FA 0.96 %. BOT-C uses the byte count of the flows of a group (the fixed shape of the Ares beacon): shape-dependent by construction, reported but never counted for N4. BOT-A / BOT-B use only counts of active minutes, gaps and sources: no port, address or size identity.

