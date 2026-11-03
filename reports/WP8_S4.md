# WP8 S4: network streaming sub-bin Evidence and the unseen-Bot analysis

Date: 2026-11-03    Worker: sonnet (high), branch v3.1 (tag v3.0 untouched)

## Summary
- Goal: cut the network Evidence latency (v3: a flow's Evidence exists only when its 5-minute TRW bin has closed; M3 quotes 66 s median / 242 s max at the system tick) without losing stack H detection (macro >= v3 - 3 points, paired), and explain why unseen Bot is 0%. V31_val only (D10 val); D10 test rows and D23 were never loaded (the WP4 caches had been deleted: D10 rebuilt with the unchanged WP4 code, counts equal results/WP4/s3_prep.json).
- New code (v3 files untouched): `network/stream31.py` (RunningState, Stream31 = Evidence at flow arrival, Stream31Final = Evidence at tick close), tools `WP8_S4_{prep,eval,stream_check,final_check,bot,report}.py`, tests `tests/v31/test_s4_{stream,regression}.py`. No new fitted parameter: the fitted v3 layer objects are reused; only the per-layer ECDF calibrators and the combined 1% threshold are re-fitted on the benign val stream.
- Mechanism: window statistics are recomputed per arriving flow from the flows seen so far (scan: distinct ports / hosts; bruteforce: flows per (src,dst,port); TRW: peak of the walk so far; tcp_flags unchanged). In the last flow of a cell the running value equals the v3 cell value (tested), so "running" reveals the v3 statistic causally. D10 timestamps are whole minutes (attack files), so tick = 60 s; sub-minute (10-30 s) ticks cannot be validated on V31_val (only D23 Tue-20-02 has seconds, and it is H31): `tick_s` is a parameter, nothing sub-minute is claimed.
- Round 1 (pre-registered grid R5/R2/R1, running statistics): Evidence delay 0 but macro 50.7 / 46.5 / 47.0 against v3 58.3 (paired -7.6 / -11.8 / -11.2): N2 NOT MET for all. Cause: flows before the threshold-crossing flow of a window are not alarmed (FTP 100 -> 81, SSH 100 -> 60, SlowHTTP 97 -> 70).
- Round 2 (logged, V31_val only, rule written before the numbers): one-tick carry (a key's statistic is at least its own peak of the previous tick). RC5 (carry, TRW bin 5 min): macro 55.4, paired -2.90 points [-4.49, -0.34], FA 0.93 %, Evidence delay 0 (at flow arrival): FEASIBLE and chosen by the pre-registered rule (lowest delay, then macro, G8). The margin to the -3.0 bound is 0.10 points and the paired CI excludes 0: RC5 is measurably a little worse than v3, not equivalent.
- F1 (v3 statistics, TRW bin 1 min, Evidence at tick close = Stream31Final): macro 57.9, paired -0.34 [-1.14, 0.00], FA 0.96 %, flow-level delay median 60 s / max 76 s (v3 emulated at flow level: 120 s / 307 s; attack flows 60 / 300 s). Also feasible, with a 2.7-point margin; it meets the amended D10 target (<= 60 / 120 s) but not the D23 Tue target (<= 15 / 45 s) unless the tick is shortened (S7, not validated here).
- N1 (D10 val, target median <= 60 s, max <= 120 s): RC5 0 / 0 s (emission at arrival), F1 60 / 76 s, v3 120 / 307 s. Alarm lag (first available alarm after the first attack flow, median over families): v3 120 s, F1 60 s, RC5 0 s; but only 46 % of the attack flows of a segment's first minute are alarmed under RC5 (v3 and F1: 59 %): "delay 0" does not mean every attack flow is alarmed on arrival.
- N2: FA 0.93 % (RC5) and 0.96 % (F1) on the val mixed stream (bound 1.0 %). N3: per-push compute RC5 median 2.75 ms, p99 5.1 ms, max 116 ms (75,000 flows, other workers running); F1 median 0.88 ms, p99 2.3 ms, max 765 ms (the tick flush); v3 stall 1.4 s median / 7.7 s max at every bin close. Stream == batch exactly (max score diff 0.0, 0 alarm mismatches) on three real val slices of 25,000 flows and on synthetic tables; causality (prefix == full run) holds.
- Regression (G7 R1): the frozen v3 domain reloaded on the rebuilt val cache reproduces the stored WP4 S7 val view of stack H exactly (FA 0.0095996177, macro 0.5825676723, every family); freeze_check unchanged; `run_all.py --check` all OK; full suite 512 passed, 0 failed, 2 skipped (run before the last test was added; the six S4 stream tests pass on their own).
- Unseen Bot (N4, no binding target): nothing counts. Bot is 0% under leave-one-attack-out because (a) the Bot flows lie in the benign bulk of every H layer (AUC 0.57 / 0.36 / 0.44 / 0.17 for tcp_flags / scan / trw / bruteforce; 1-1.4 flows per active minute from 5 bots to one endpoint), (b) the Ares beacon shape also occurs in 120 BENIGN-labelled val flows (116 from the Bot hosts to the C2: label noise), so an exact-shape detector has precision <= 47.6 %, (c) the ~100 s period falls on the 1-2 minute gaps of the 1-minute grid. Label-free candidates: net.beacon 27.5 % of Bot flows at 0.98 % FA alone (3 of 6 groups, AUC 0.62), persistent-rare-endpoint 0 %, byte-size regularity 71.6 % at 0.99 % FA (5 of 6 groups, AUC 0.81, precision 2.1 %) but shape-dependent and not counted; added to H at a constant 1 % budget none lifts Bot above 5.5 %, and the beacon costs 16 macro points (budget dilution).
- Recommendation for S7 (decision for the supervisor): freeze RC5 only if zero emission delay (the D23 Tue target) matters more than a 0.10-point margin on a re-used test set; otherwise freeze F1. Either way the system integration needs the fusion's network ECDF / tick model recalibrated for the new score distribution (S2 / S7); this step does not touch fusion.

## Acceptance rules (notes/WP8_v31.md, S4 section, written 2026-11-03 before any v3.1 network number; the round-2 rule was written after round 1 and before any round-2 number)
N1 delay (D10 val median <= 60 s, max <= 120 s, amended by the orchestrator), N2 non-inferiority (stack H macro over the 11 families >= v3 - 3 points paired; FA <= 1.0 %), N3 stall (per-update p99 <= 1.0 s), N4 unseen Bot (reported). The D23 half of N1 is S7.
Verdicts on V31_val: N1 MET (RC5, F1), N2 MET (RC5 with a 0.10-point margin, F1 with 2.7), N3 MET, N4 reported: no gain counts.

## What was done
- D10 rebuilt (tools/WP4_s1_build.py D10, then tools/WP8_S4_prep.py: counts equal v3, train 1,623,768 / val 502,291 rows); S4 tools read a train+val copy only. The rebuild rewrote results/WP4/s1_clean_D10.json (key order only); restored with git checkout.
- Candidates evaluated by tools/WP8_S4_eval.py (parts resumable in results/WP8/S4/parts), selection logged in results/WP8/S4/s4_val_candidates.json ("selection"). Per-flow scores and labels: results/WP8/scores/S4/network_val.npz (13 MB; v3, R5, R2, R1, RC5, RC2, RC1, F1 scores, alarms, layer matrices, family, block, time) and network_bot_val.npz (candidate scores), committed with `git add -f` (npz is gitignored).
- Fitted objects: results/WP8/S4/parts/stream31_RC5.pkl (20 MB) and stream31_F1.pkl (not committed: *.pkl is gitignored; rebuild with the eval and final_check tools, resumable).
- Machine note: all timings on a shared machine (S1 downloads and S3 LiDAR running; system CPU 35 % during the RC5 timing).

## Results (generated from the JSON by tools/WP8_S4_report.py; same tables in results/WP8/S4/s4_tables.md)

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


## Ablation / reading
- Round-1 loss by layer: bruteforce carries H (SSH, FTP, floods); a count that must reach its benign 99.9th-percentile reference is not reached by the first flows of a minute. The one-tick carry recovers FTP 80.6 -> 97.7 and SSH 60.4 -> 95.5, but not SlowHTTPTest (75.3 vs 97.4); that residual was not analysed further.
- TRW bin under carry: 5 min (v3) is best (macro 55.4 vs 52.5 for 2 min and 52.6 for 1 min; Slowloris 37.3 -> 9.9 with the shorter bins).
- Adding any Bot candidate to H at a constant 1 % budget moves the combined threshold from 0.99607 to 0.9970-0.9974 and displaces other families (SSH or SlowHTTP fall below the line).

## Problems, surprises, open questions
- Delay metric: the 66 / 242 s of M3 are tick-level numbers of the M2 minute-hold model; the flow-level emulation of the v3 runner on D10 val gives 120 / 307 s (attack flows 60 / 300 s). D10 timestamps are minute-truncated, so any emission at the next minute shows 60 s; the real delay lies between 0 and 60 s. Maxima measured on slices that cross recording periods (6,960 s) are an artifact of a flush triggered only by the next arriving flow; a clock timer closes the tick.
- Thin margin: RC5 passes N2 by 0.10 points on a validation set in which every family is one attack run (1-3 blocks): not a robust margin. S7 scores D10 test again (exposure 8): non-inferiority only, no improvement claim for the network (G4).
- Combined threshold of the frozen v3 domain (0.996067) vs re-derived from the rebuilt benign val stream (0.995701): a tie-order difference for Monday flows inside a minute; FA and macro of v3 on val are nevertheless identical to the stored values (test).
- The carry rule was added after round 1 (allowed by the round-1 rule); the F1 reference was pre-registered as information only and became a candidate in round 2 (stated before the numbers). Two rounds, no third.
- results/WP4/s1_gate2.log is untracked and not mine.

## Proposed next step
S2 / S7: decide RC5 vs F1; recalibrate the fusion's network ECDF and minute-hold tick model for the chosen score; for D23 Tue (second resolution, H31) S7 runs Stream31 with a tick pre-declared there, not tuned on D23.
