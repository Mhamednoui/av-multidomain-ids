# M1-NET: network intrusion detection by host time-window logic and flow shape (WP4, milestone report)

Date 2026-10-22. Status: **PARTIAL**. Met: false alarms (H 0.48%, O 0.48% against 2%), behavioural families (scan, brute force, floods) with zero attack training. NOT met: unseen Bot > 70% (0% for every stack), Web attacks / Slowloris zero-shot, cross-dataset transfer of the flag layer (FA 30%) and of the destination baseline (needs a warm-up). Rule written before any S7 result: `notes/WP4_network.md` "S7 plan" (G1, G2, G5-G7 met; G3, G4 NOT met). Self-contained; long tables: `results/WP4/s7_tables_d10.md`, `s7_tables_d23.md`; numbers: `s7_d10.json`, `s7_d23.json`, `s7_dev_val.json`, `s7_prep.json`; step reports `reports/WP4_S1..S7.md`.

**Protocol.** D10 = CICIDS2017 flow CSVs (unofficial mirror, 2,830,743 labelled flows), D23 = CSE-CIC-IDS2018. Split by TIME inside every attack window (60/20/20 in time order, 1-min gaps, S1); fit on benign train, thresholds = tie-safe 1% of benign validation, one test run on the pre-dedup STAGE stream (585,951 flows; multiplicity matters for counts). Stacks (layer scores ECDF-calibrated on benign validation, combiner chosen on validation among `common/combiner.py` noisy-or (log form) / max / logistic on a family-balanced validation sample, groups = 10-min time blocks): **H** zero-shot, topology-free = tcp_flags + scan + trw + bruteforce (combiner chosen: max); **O** on-network = H + dos_rate (per-destination baseline learned on the benign warm-up) + L3 service profile + L3 autoencoder, all refit on the target warm-up (chosen: noisy-or). Optional rows only: slow, beacon, topology allow-lists (lab artefact), L4 XGBoost (supervised, seen families). Benign = published BENIGN minus the audited Infiltration file (below). CIs: bootstrap over 10-minute time blocks (2000 resamples). Test stage rows had been scored in S2-S6; this is the 6th exposure, no S7 choice used a test number.

## 1. What each layer catches, and why (D10 test, each layer at its own 1% threshold; detection %)

| layer | behaviour / protocol fact it counts | FA % | catches | misses |
|---|---|---|---|---|
| tcp_flags (L1) | a TCP flag combination (given packet count) that benign flows almost never show: probes, half-open, stalled flows | 0.88 | PortScan 96.7, SlowHTTP 75.3, Slowloris 34.7, Hulk 23.1 | Bot, Web, FTP/SSH 0 |
| scan (L2a) | one source touches many distinct ports / hosts in one minute | 0.00 | PortScan 97.4 | all single-target attacks |
| trw (L2a) | threshold random walk (Jung 2004): a source keeps failing first contacts | 1.77 | PortScan 97.4 (adds nothing over scan in the ablation) | benign hosts fail often: FA highest |
| bruteforce (L2a) | one source opens far more sessions to one (destination, service) than any benign source (port-specific benign 99.9th percentile) | 0.23 | FTP 100, SSH 98.6, LOIC 100, GoldenEye 100, Hulk 100, SlowHTTP 85.2 | Slowloris, Bot, Web (too few sessions) |
| dos_rate (L2a, warm-up) | flows per minute to one destination vs its own learned baseline | 0.46 | LOIC, GoldenEye, Hulk 100, SlowHTTP 85.2, PortScan 97.4 | low-rate attacks |
| l3_service / l3_ae (warm-up) | flow shape unusual for the service / poorly reconstructed by a benign autoencoder | 0.92 / 1.02 | AE: PortScan 98.5, SlowHTTP 97.1, Slowloris 78.0, LOIC 61.8; service: FTP 100, SlowHTTP 84.3 | Bot, Web-BF, Web-XSS 0 (they sit in the benign tail) |
| beacon / slow (optional) | periodic connections on a 1-min grid / half-open + stalled flows | 1.75 / 0.48 | Bot 36.0 (3 of 5 groups) / LOIC, Hulk 100, GoldenEye 60 | beacon precision low; Bot beacon period (~100 s) is at the edge of the 1-min grid |
| l4_xgb (optional, supervised) | learned flow classifier on 60 packet-size / timing columns | 1.23 | 11 of 11 families seen in training: macro 92.9 | unseen families (section 4) |

## 2. Final numbers (D10 test, published labels, detection %; FA = headline benign; brackets 95% block bootstrap)

| stack | FA % | macro of 11 % | Bot | LOIC | GoldenEye | Hulk | SlowHTTP | Slowloris | FTP | SSH | PortScan | Web-BF | Web-XSS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **H** zero-shot | 0.48 [0.36, 0.64] | 65.9 [39.5, 76.5] | 0 | 100 | 100 | 100 | 94 | 35 | 100 | 99 | 98 | 0 | 0 |
| **O** on-network | 0.48 [0.29, 0.73] | 63.5 [35.7, 72.9] | 0 | 100 | 100 | 100 | 99 | 98 | 98 | 5 | 99 | 0 | 0 |
| O + L4 (supervised, in-window ceiling) | 0.85 [0.75, 0.96] | 94.0 [76.3, 98.4] | 98 | 100 | 100 | 100 | 100 | 99 | 100 | 52 | 100 | 89 | 97 |
| O + topology (lab artefact) | 1.02 [0.85, 1.29] | 90.9 [85.7, 90.9] | 0 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |

Per family for H with intervals (n flows / 10-min blocks holding the family / detection [CI]): Bot 308 / 9 / 0 [0, 0]; LOIC 25,655 / 1 / 100 [100, 100]; GoldenEye 3,347 / 1 / 100; Hulk 48,337 / 2 / 100 [0, 100]; SlowHTTP 1,191 / 2 / 94 [20, 95]; Slowloris 1,278 / 1 / 35 [35, 35]; FTP 2,049 / 3 / 100 [98, 100]; SSH 1,639 / 2 / 99 [97, 100]; PortScan 5,150 / 3 / 98 [0, 100]; Web-BF 321 / 2 / 0; Web-XSS 132 / 1 / 0. **Read the intervals as "one attack run per family"**: most families sit in 1-3 blocks, so a family CI is degenerate ([35, 35]) or [0, 100] when a tiny undetected segment is resampled alone; the macro and FA intervals are the informative ones. Delay (minutes from the first attack flow of a test segment to the first combined alarm, 1-min resolution): H and O 0 for LOIC, GoldenEye, Hulk, SlowHTTP, Slowloris, SSH; FTP 2 and 0; PortScan 0 in the two large segments, never in the 1-flow segment; Bot and Web never (H, O).
AUC (attack vs benign): H 0.9954, O 0.9972, O+L4 0.9998. Dedup-rows view (rows of the de-duplicated table, PortScan keeps ~1% of its flows): H FA 0.51 / macro 61.0 (PortScan 46.9), O 0.54 / 61.6, O+L4 0.86 / 98.4.
**Infiltration label audit.** The Thursday-afternoon Infiltration file labels BENIGN the compromised host's own network scan (2,033 flows, 1,008 ports in one minute). Excluding those benign flows (as decided in S3, before any verdict): H FA 0.48%; with the published labels H FA **5.82%** (the audit file alone: 30.7% of its benign flows are alarmed), O 5.80%, O+L4 6.16%. Infiltration has 6 test flows (not evaluable; H 33%).
**Bot label correction** (dataset documentation: Ares victims 192.168.10.5/.8/.9/.14/.15, C2 205.174.165.73:8080; 216 test and 156 validation BENIGN flows between them relabelled Bot, none carries another attack label; rule never from model output): Bot published (n=308) vs corrected (n=524): H 0 vs 5.7 [0, 18.1], O 0 vs 0.2, O+beacon 1.0 vs 1.7, O+L4 97.7 vs 92.9; FA unchanged to 0.05 point (O+L4 0.85 vs 0.80). L4 detects the unlabelled beacons too (it learned the Ares C2 signature, S6).

## 3. Ablation (D10 test, macro of 11 % / FA %; combiner re-selected on validation for every sub-stack; full per-family tables `s7_tables_d10.md` section 5)

| H | macro / FA | O | macro / FA |
|---|---|---|---|
| all | 65.9 / 0.48 | all | 63.5 / 0.48 |
| alone tcp_flags / scan / trw / bruteforce | 21.1 / 8.9 / 8.9 / 53.1 (FA 0.88 / 0.00 / 1.77 / 0.23) | alone dos_rate / service / AE | 43.9 / 35.3 / 39.0 (FA 0.46 / 0.92 / 1.02) |
| all but tcp_flags | 61.9 / 0.34 | all but tcp_flags / scan / trw | 69.9 / 0.90; 66.4 / 0.97; 69.9 / 1.28 |
| all but scan / trw | 65.9 / 0.48; 65.9 / 0.71 | all but bruteforce | 49.1 / 0.67 |
| all but bruteforce | 21.3 / 0.77 | all but dos_rate / service / AE | 72.1 / 0.18; 68.3 / 1.00; 57.5 / 0.54 |

bruteforce carries H (SSH, FTP, every flood); tcp_flags adds Slowloris / SlowHTTP; scan and trw are redundant with tcp_flags + bruteforce on D10 (a PortScan-only gain would need data where the scan is not also a flag pattern). O is not better than H in macro: noisy-or over 7 layers dilutes SSH (98.6 -> 4.6) because the small scores of the other layers raise the combined benign tail. The validation selection between noisy-or and logistic for O was a tie (0.832 vs 0.829); the logistic would have given 72.1 / 0.19 on test (`s7_tables_d10.md` section 7); adopting it now would be a choice made on test. OR of the layers' own alarms (budgets add up): H FA 2.86 / 66.0, O 4.37 / 72.6.

## 4. Leave-one-attack-out (the generalisation number; held-out family removed from the combiner selection and, for L4, from training; thresholds 1% of benign validation)

| held out | H | O | O+L4 | L4 alone |
|---|---|---|---|---|
| Bot (n 308) | 0 | 0 | 0 | 0 |
| FTP / SSH | 100 / 99 | 98 / 5 | 98 / 3 | 1 / 4 |
| PortScan | **0** (98 seen) | 0 (99 seen) | 2 (100 seen) | 2 (100 seen) |
| Web-BF / Web-XSS | 0 / 0 | 0 / 0 | 84 / 97 | 85 / 97 |
| group DoS-4 / WebAttack / BruteForce | 98 / 0 / 99 | 99 / 0 / 56 | 99 / 55 / 56 | 4.5 / 81 / 1.0 |
| macro of the 11 single hold-outs (seen) | 57.0 (65.9) | 54.5 (63.5) | 68.7 (94.0) | 45.0 (92.9) |

Reading: the benign-fitted rule layers detect a family without having seen it, because they count what the attack must do (retries to one service, fan-out, rate). H loses only PortScan, and only through the COMBINER SELECTION: validation without PortScan selects the learned logistic, which gives the scan layers no weight; the frozen parameter-free max keeps 98%. The rule layers' windows and N_MIN were chosen on validation with all families visible (S3/S4), so even this is not a fully blind test. The supervised layer transfers only between look-alike families (Web attacks resemble the HTTP DoS flows: 80-97%) and not at all across behaviours (FTP/SSH 1-4%, DoS group 4.5%, **Bot 0%**). Target "unseen Bot > 70% at the same FA": **NOT MET** for all stacks (Bot has no behaviour the layers see: the Ares C2 beacon is a fixed 3/3-packet 1-s flow on port 8080 that L4 learns as a signature, and the 1-min grid hides its ~100 s period).

## 5. Cross-dataset (D23 = CSE-CIC-IDS2018, whole dataset as external test; a different CICFlowMeter run)

- **Zero-shot (D10 layers, D10 thresholds, nothing refit).** The L2a layers need addresses: only Tue-20-02 has them (9 of 10 files have none; D23 Bot has none, so beaconing is not evaluable). net.tcp_flags (the only headline layer that runs on every day): FA **30.4%** [25.2, 38.2] (day 02-21: 99.5%): in D23 the RST/ECE flag columns are set on 22% of benign flows (D10: 0.03%), so the "rare combination" is not rare. H on Tue-20-02: FA **34.7%** (sample rows) / 23.5% (full stage stream): NOT MET (bound 5%). H without tcp_flags (pre-declared; the flag columns differ between the runs): FA 6.13% [5.19, 7.03] (sample) / 4.54% [3.83, 5.23] (stage): borderline, only the stage view meets 5%; DDoS-LOIC-HTTP 98.9-99.0%, carried by bruteforce alone (99.2% at FA 3.0%); scan and trw have nothing to detect that day and cost 2.5-3.9% and 3.1-3.4% FA.
- **On-network (warm-up = benign train split, calibration = benign validation, combiner noisy-or with a 1% benign threshold, no attack label).** Tue-20-02, O (7 layers): FA 1.67% [1.27, 2.13], LOIC-HTTP 100% [99.4, 100] (dos_rate alone 100% at 1.66%). Flow-level O (tcp_flags + service + AE) on all days: FA 1.08% [0.92, 1.28], macro of 9 families 25.7% [15.9, 36.7]: LOIC-UDP 100, Slowloris 100, Web-BF 25, Infiltration 4, GoldenEye 2, Bot 1, SSH 0, HOIC 0, LOIC-HTTP 0 (the volume signal needs dos_rate, which needs addresses). Warm-up length: the dos_rate baseline needs about 1.4 h of benign traffic on D23 (0.5 h: FA 44%, 4 known destinations; 1.4 h: 1.6%) and 2 h on D10 validation (126 min: FA 0.58%, LOIC/Hulk 100%).
- For reference (S6): supervised L4 refit on labelled D23 attacks reaches macro 79.4% at FA 1.0%; zero-shot it has FA 5.2% and AUC 0.74.

## 6. v2 side by side (NOT comparable: v2 used D01, a different CICFlowMeter run that is not a subset of D10; random split; 7 classes)

| | v2 (D01) | v3 (D10, time split) |
|---|---|---|
| headline | accuracy 99.73%, macro F1 99.60% (random split after dedup) | H FA 0.48%, macro 65.9% (zero-shot); L4 alone in-window ceiling 92.9% (S6, dedup rows 98.0%) |
| unseen Bot | supervised 0.0%, zero-day OCSVM 5.3% at FA 2.9% | LOAO 0% (every stack) at FA 0.5-1.4% |
| unseen WebAttack | supervised 1.2%, zero-day OCSVM 96.3% at FA 2.9% | H 0, normal-only AE 0, L4 retrained without the group 80.6% (looks like Hulk), O+L4 55% |
v2's 96.3% on unseen web attacks is not reproduced by any v3 benign-only layer (0% at 1% FA); with D01 features, another budget (2.9%) and another flow run the two claims cannot be reconciled; v3 does not claim the v2 figure. v2's near-perfect random-split accuracy was probably helped by flows of the same attack run on both sides of the split (S1: 22% duplicates); not tested.

## 7. NOT met / not caught

Bot 0% (zero-shot and unseen), Web-BruteForce / Web-XSS 0% for H and O (single-flow application attacks; the normal-only layers rank them inside the benign tail, per-family AUC 0.66-0.82, S5), Slowloris 35% for H (98% only with the on-network autoencoder), SSH under noisy-or O (5%), D23 transfer (tcp_flags FA 30%, destination baseline needs a warm-up, L2a needs addresses), unseen-family detection of the supervised layer, Infiltration (6 test flows, not evaluable). No claim about attacks against in-vehicle Ethernet (TOW-IDS needs an IEEE DataPort login: not available).

## 8. Artefacts and pitfalls found

- Provenance: D10 comes from an unofficial HF mirror (UNB page restricted); gates: G2 (per-day / per-label counts equal MachineLearningCVE) and G3 (key match 100%) passed, G1 (D01 rows found in MLCVE) failed at 33-39%: **D01 is not a subset of either file set**, v2 numbers are not v3 numbers.
- Timestamps carry no AM/PM in either dataset (hours 1-7 are +12 h, checked against the attack schedule); D10 time resolution is one minute.
- De-duplication (v2 style) removes 99% of PortScan (158,930 -> 1,851) and most D23 FTP / SlowHTTP flows: host-window layers must use the pre-dedup stream (stage); dedup view reported separately.
- Lab topology: 99.75% of D10 attack flows go to ONE server (192.168.10.50) that receives 0.83% of benign flows, from the single attacker address 172.16.0.1: the allow-list rows reach 90.9% macro at FA 1.02% only through that fact (and still 0% Bot); never quoted as detection.
- Label noise: the Infiltration file's benign scan (FA 0.48% vs 5.82%); unlabelled Bot beacons inside the Friday afternoon files (216 test flows).
- D23: seven of ten files end at 1,048,575 rows (Excel limit, as published; Fri-16-02 ends at 13:xx, Hulk has no validation part); Bot / most files have no addresses; Tue-20-02 has 84 columns; 33.3% duplicate flows, 43,572 conflicting labels.
- Every attack family is one run in the test window (1-3 blocks): intervals per family are not independent-sample intervals. Within-window time cuts put parts of the same run on both sides (in-distribution for the supervised layer: its 98% is a ceiling).

## 9. Frozen deployable network domain (for WP6 / WP7)

`network/domain.py`; fitted object `results/WP4/s7_domain/` (`domain.pkl` 14.6 MB, `domain.json`, `freeze_check.json`, fixture `example_evidence_portscan.json`): stack H on D10, combiner max, threshold 0.99607; reproduces the S7 verdict score and alarm of all 585,951 test flows exactly. Stack O is built per network by `NetworkDomain("O", method="noisy_or").fit(warm_up, calibration)` (saved/loaded with the AE weights; tested).
```
D = NetworkDomain.load("results/WP4/s7_domain")        # stack H
comb, per = D.score_stream(flows)                       # flows: DataFrame, columns RAW_COLUMNS (ts, src_ip, dst_ip, dst_port, protocol + CICFlowMeter columns); all flows of the buffer
```
Evidence: one per flow, `domain="network"`, `layer="combined"`, `name="network.combined"`, `t` = flow start (s), `score` in [0, 1] (max of the ECDF-calibrated layer scores), `alarm` = score >= 0.99607 (1% of benign validation; 0.48% on the D10 test; on D23 Tue 4.5-6.1% without tcp_flags and 23-35% with it (different CICFlowMeter run)), `reason` = behaviour sentence of the firing layers, `details` = {method, layer_scores, final}, `sample_id` = row position in the call; per-layer Evidence (`L1`, `L2a`) in `per`. NOT sample-causal: a flow is scored by the value of its minute cell (trw: its 5-minute bin), so its Evidence is final only when the window has closed (`details["final"]`, tested); feed a buffer of >= 5 minutes. Addresses only group flows (renaming all addresses changes nothing, tested). No MotionEstimate (network has none). Fitted objects belong to the network they were fitted on; the flag layer must be refit when the CICFlowMeter run changes.
