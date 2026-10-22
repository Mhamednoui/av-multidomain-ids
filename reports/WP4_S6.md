# WP4 S6: L4 supervised XGBoost (v2 network model retrained on the v3 time split)

Date: 2026-10-22    Worker: sonnet high (WP4 S6)

## Summary (tables: results/WP4/s6_tables.md; numbers: s6_d10.json, s6_loao.json, s6_d23.json, s6_dev_val.json, s6_acceptance.json, s6_bot_benign_shape.json)
- Layer net.l4_xgb (network/l4.py, layer_id L4): binary XGBoost on the 60 clean features (no IPs, Flow ID, timestamp, ports, TCP-stack columns; v2 had no port column either). Trained on the 1,178,110 de-duplicated TRAIN flows of the time split (182,714 attack), search on validation (6 trials of the v2 space, restricted for run time), chosen: depth 3, lr 0.2, 616 trees; threshold = 1% of benign validation (tie-safe). ONE test run.
- NOT comparable with v2: v2's 99.73% was D01 (a different CICFlowMeter run, S1 gate G1 failed), random split, 7 classes, 69 features. Binary operating point p=0.5 on the v3 dedup test: accuracy 99.67% / F1 99.0%: shown for orientation only, not a target.
- D10 test, in-distribution (headline = de-duplicated rows, benign without the audited Infiltration file): FA 1.00% (all stream rows 1.23%, published labels 1.30%), macro over 11 families 98.0% (all stream rows 92.9%), AUC 0.999. Bot 98.1%, Web-XSS 98.5, Web-BruteForce 92.9, GoldenEye 95.2, SSH 96.4, others >= 98.5.
  Read this as the in-window ceiling, NOT as generalisation: the time cut falls inside every attack window, so the same attack session is on both sides.
- Acceptance (rule in notes/WP4_network.md "S6 plan", written before any score): E1 FA <= 2% MET (1.00%); E2 null control MET: shuffled train labels, 5 seeds, mean flow-level AUC 0.477 (bound 0.55; real 0.9997);
  E3 no red flag: top feature Bwd Pkt Len Std 24.7% (< 30%), then Pkt Len Var 14.2, Bwd Pkt Len Mean 9.1, Fwd Header Len 6.6, Fwd IAT Mean 5.7 = packet-size spread and IAT/header timing; E4 statement below; E5 preview below (target Bot > 70% unseen: NOT MET, 0%);
  E6 cross-dataset NOT MET (zero-shot FA 5.17% > 5%, AUC 0.741); E7 "adds >= 5 points": MET in-distribution (+32.8 macro points), see the limits below.
- Bot (E4, per-family signature check): L4 detects 98.1% of the 308 test Bot flows, but only because it learned the Ares C2 beacon: Bot flows of the beacon shape (3 fwd / 3 bwd packets, 0.99-1.03 s, 260 flows) 100%, other Bot flows 87.5%; the flows of that shape labelled BENIGN (167) are alarmed 98.8%;
  by the rule fixed in advance (AUC of Bot vs benign of the same shape 0.548 < 0.7) the reading is "shape only". Found while checking: ALL benign-labelled flows of that shape (train 403, val 101, test 165) are from the five Bot hosts to the C2 205.174.165.73:8080 inside the Friday PortScan / DDoS files, i.e. unlabelled bot beacons
  (CICIDS label noise, byte-identical lengths: 98.8% share the Bot byte lengths); so L4 is right on them and the S5 statement "benign has the same shape" was these beacons. Conclusion: a SIGNATURE of one botnet implementation, not beaconing behaviour; leave-one-out confirms it: train without Bot, unseen Bot 0% (AUC 0.81).
- Leave-one-attack-out preview on VALIDATION (threshold 1% of benign val; test never read), L4 unseen detection: Bot 0.0, FTP-Patator 1.2, SSH-Patator 0.6, DoS-SlowHTTPTest 29.4, PortScan 44.7, DDoS-LOIC 63.3, GoldenEye 92.6, Web-BruteForce 88.9, Web-XSS 99.0, Hulk 96.3, Slowloris 99.4 (macro 55.9% vs 61.5% for the benign-fitted base tcp_flags + L2a).
  Groups held out together: DoS-4 2.0% (GoldenEye 69, Slowloris 31, Hulk 0.6, SlowHTTP 1.9), BruteForce 0.4%, WebAttack 80.1% (unexpected, the two web attacks look like the HTTP DoS flows). Generalisation therefore depends on a similar family staying in training; none for Bot, FTP/SSH, DoS as a group.
- Does L4 add on top of the topology-free stack (harness, logistic combiner, dedup rows; FA %, macro11 %): tcp_flags + L2a 0.80 / 65.1 -> + L4 0.56 / 98.0; + beacon 1.05 / 63.6 -> 0.70 / 98.0; + on-network L3 (service + AE) 0.93 / 66.3 -> 0.77 / 98.4; L4 alone 1.02 / 98.0. All-stream rows: 54.2 -> 93.8 (+beacon 55.8, +L3 61.0 -> 94.0).
  L4 closes the rule-blind families (Bot, Web-XSS, Web-BruteForce 0 -> 97.7 / 97.0 / 91.7, PortScan 27.6 -> 99.5 on dedup rows; SSH-Patator slips 98.5 -> 94.3 in the combiner) but, as the preview shows, only because it saw them. For UNSEEN families its added value on top of the rules is: Web attacks (+80 to +99 points), GoldenEye (+92); nothing for Bot, nothing where the rules already see the family.
- Cross-dataset (D10-trained, D23 sample, 500,000 benign test flows): zero-shot FA 5.17% at the D10 threshold (days 02-22 / 02-23: 13.9 / 12.5%), macro9 detection 28.8%, macro9 AUC 0.741 (DDoS-LOIC-UDP 0.38 and Infiltration 0.42: below chance); re-calibrated threshold without refit: FA 0.09%, macro9 10.1%.
  Information only: on-network supervised refit on labelled D23 attack flows of an earlier window, threshold on D23 benign: FA 1.02%, macro9 79.4%, AUC 0.968. As in the v2 thesis: learned network models do not transfer, they have to be refit on the target network WITH labelled attacks.
- FA on benign test: 1.00% excluding the audited Infiltration file, 1.30% with published labels (dedup rows); 1.23% on all stream rows. False alarms are mostly ports 443 (21%), 80 (10%), 8080 (5%).

## Acceptance rule (notes/WP4_network.md, "S6 plan ... BEFORE any L4 score") and result
| rule | result |
|---|---|
| E1 FA <= 2% (dedup headline; stage and published labels also) | MET: 1.00 / 1.23 / 1.30% |
| E2 flow-level shuffled-label null, 5 seeds, mean AUC <= 0.55 | MET: 0.477 (0.497, 0.488, 0.424, 0.486, 0.489); null detection at its own 1% threshold 2.6-4.7% (small residual) |
| E3 no dominant non-physical feature (> 30% or capture-encoding in top 5) | no flag: 24.7% max; all top-5 are packet-length / IAT / header measurements; ablation not triggered |
| E4 Bot signature statement (rule: AUC < 0.7 shape only, >= 0.9 finer signature) | "shape only" (0.548) and, with the label-noise finding, a one-implementation C2-beacon signature; unseen Bot 0% |
| E5 LOAO preview on validation, Bot unseen > 70% | NOT MET (Bot 0.0%; other families 0.6-99%, table 6 of s6_tables.md) |
| E6 zero-shot D23 FA <= 5% | NOT MET: 5.17%; AUC 0.741 |
| E7 L4 adds >= 5 macro points on tcp_flags + L2a (dedup rows, FA <= 2%) | MET in-distribution: +32.8 (65.1 -> 98.0); unseen-family value limited (see above) |
| E8 honesty items | done (below) |

## What was done
- network/l4.py (XGBNet layer, class weights, v2 search space), tests/network/test_l4.py (5 tests; full suite 315/315), tools/WP4_S6_lib.py, _dev.py (search on validation), _base.py (scores of the base stack and L3), _loao.py, _verdict.py, _tables.py, _botlabels.py.
- Data: D10 stage stream of S3-S5 with the 76-feature matrix (S5 cache) and the dedup mask of the S1 final tables; D23 sample of S5. Cache ../data_extra/cache_v3/WP4/S6 (base score tables, model, dedup mask; 0.13 GB); WP4 cache 6.1 GB (<= 7 GB). results/WP4/smoke deleted.
- Rows: train = split train AND in the de-duplicated final table (earliest copy of a feature vector, conflicts dropped; as v2), minus the benign flows of the audited Infiltration file; test headline = dedup rows (no exact copy of an earlier flow on the other side of the split); the full stream rows (S3-S5 view, containing exact copies) reported next to it.
- Harness base layers (tcp_flags, 5 L2a, beacon, L3 service + AE) are exactly those of S3-S5 (same fit, thresholds, configs; nothing re-chosen; the base reproduces 54.2% on the stream rows).

## Ablation (harness, FA % / macro11 %; full per-family tables in s6_tables.md section 7)
| config | dedup rows | all stream rows |
|---|---|---|
| tcp_flags + L2a (base) | 0.80 / 65.1 | 0.33 / 54.2 |
| base + L4 | 0.56 / 98.0 | 0.57 / 93.8 |
| base + beacon | 1.05 / 63.6 | 0.57 / 55.8 |
| base + beacon + L4 | 0.70 / 98.0 | 0.67 / 93.8 |
| base + L3 (service, AE; on-network) | 0.93 / 66.3 | 0.63 / 61.0 |
| base + L3 + L4 | 0.77 / 98.4 | 0.75 / 94.0 |
| L4 alone | 1.02 / 98.0 | 0.98 / 92.3 |

## Problems, surprises, open questions
1. In-window ceiling: every number above for seen families is in-distribution (same attack sessions on both sides of the time cut). Do not quote 98% as network detection; quote the preview (unseen: Bot 0, FTP/SSH about 1, DoS group 2, Web 80) and the D23 result.
2. Run time: the full v2 search (10 trials) was aborted by me after 25 min on the loaded machine; restarted with 6 trials and lr {0.1, 0.2}, depth {3,4,5,6,8}. Trials differ by <= 0.9 macro points (validation noise level), so the choice is not sensitive.
3. Label noise in Bot: unlabelled bot beacons inside the Friday afternoon files (above). Counting them as false alarms would add 165 of 347,880 benign test flows (0.05%); they are in the 1.00% FA as it stands. A relabelled Bot would only change the Bot row of the preview marginally; I did not relabel anything (a choice on data).
4. The null control passes at the flow level (mean AUC 0.477 < 0.55), but the null models still alarm 2.6-4.7% of attack flows at 1% FA: a small residue of the out-of-range-leaf effect seen in WP5; it does not affect the verdict.
5. Stream rows vs dedup rows: Hulk 78.6% vs 99.7%, SSH 63.1% vs 96.4%: the stream-only rows are exact feature copies of earlier flows; I did not investigate why they score lower (hypothesis, not verified: their feature vectors also occur in label-conflict groups removed from training).
6. OR views in s6_tables.md add the 1% budgets of the layers (FA 3.7-6.5%): use the harness rows for the combined FA.
7. WebAttack held out as a group still 80%: probably HTTP-like shape shared with Hulk / GoldenEye (not tested); it should not be read as a general web-attack detector (3 attack windows, 403 validation flows).
8. Question for the supervisor: L4 as a layer of the network stack needs an explicit scope statement (like CAN S6): proposal = OPTIONAL, labelled "supervised, seen families only, needs refit per network", outside the zero-shot headline stack.

## Proposed next step
S7: combiner + ablation + leave-one-attack-out + cross-dataset -> M1-NET. Headline stack = tcp_flags + L2a (topology-free, zero-shot transferable only partly: scan / trw / bruteforce) + optional on-network layers (dos_rate online baseline, service / AE refit on the target's benign warm-up) + optional supervised L4 (seen families, refit per network). Test-side LOAO for the final numbers (with the preview as the validation protocol); do not claim Bot or web-attack generalisation from L4.
