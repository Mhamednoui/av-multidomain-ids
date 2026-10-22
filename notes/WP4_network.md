# WP4 Network: notes

## 2026-10-21 S0 data download: acceptance rule (written BEFORE any download)

Scope: D10 CICIDS2017 GeneratedLabelledFlows, D23 CSE-CIC-IDS2018 processed CSVs (size-limited),
D24 TOW-IDS only if downloadable without login.

Acceptance S0 is MET only if all hold:
1. D10: the complete GeneratedLabelledFlows set is present (8 day/session CSVs), each file
   parses with `python -I` and has the columns Flow ID, Source IP, Source Port, Destination IP,
   Destination Port, Protocol, Timestamp and a Label column. Row counts per file are reported
   and the total is compared with the published total (2,830,743 rows, CICFlowMeter-V3 labelled
   flows, as listed by UNB). Label values must be a subset of the 15 known CICIDS2017 labels.
   Any mismatch is reported as a finding, not silently accepted.
2. D10 source: a login-free source is used (UNB direct link or a reputable mirror, recorded with
   URL and date). If none exists, S0 for D10 is NOT MET and the user action is written.
3. D23: files listed in the public bucket; download of each chosen CSV completes with size equal
   to the listing size (and ETag MD5 where the ETag is a plain MD5). Total downloaded <= 10 GB
   (if the full set is > 10 GB, only the days needed to cover every attack family are taken and
   the covered families are recorded). Hard cap for the step: 15 GB total.
   Each file must parse with `python -I` (header + row count recorded).
4. D24: downloaded only if no login is needed; otherwise recorded as user action (not a failure).
5. Disk: `df -h /c` shows >= 15 GB free before each download; if not, the download stops.
6. Licence recorded for each dataset (research use must be allowed).
7. DATASETS.md rows D10/D23/D24 updated (only those rows); notes and report written; WP4 STATUS
   row set to REVIEW.

Not a criterion: the content of the data (no modelling in S0).

## 2026-10-21 S0 results (after the acceptance rule above was written)

### D10 CICIDS2017 GeneratedLabelledFlows
- Source: unofficial HF mirror https://huggingface.co/datasets/bencorn/CICIDS2017, file csvs/GeneratedLabelledFlows.zip,
  283,876,488 B, downloaded 2026-10-21 18:51 (curl). sha256 7bdbef286f8893f31c6db12105fa097fa5c2dcc6733179037a08129d150ea27a
  equals the LFS oid in the HF tree API (integrity against the mirror only). Official UNB page: "temporarily restricted"
  for off-campus users on 2026-10-21, so no check against UNB was possible.
- Licence: mirror card says "other"; original CIC/UNB terms (research, cite Sharafaldin et al. 2018). Not verified further.
- Extracted with tools/WP4_s0_extract_d10.py (zip members have a trailing space in the folder name, stripped; header names stripped).
- 8 CSVs present, 85 columns each, required columns present (Flow ID, Source/Destination IP and Port, Protocol, Timestamp, Label).
- Rows per file (results/WP4/s0_d10_inventory.json): Monday 529,918; Tuesday 445,909; Wednesday 692,703;
  Thu-Morning-WebAttacks 458,968; Thu-Afternoon-Infilteration 288,602; Fri-Morning 191,033; Fri-PortScan 286,467; Fri-DDos 225,745.
  Total 3,119,345 rows.
- FINDING: Thu-Morning-WebAttacks has 288,602 contiguous all-empty separator rows (",,,,") after 170,366 labelled rows
  (tools/WP4_s0_inspect_blank_rows.py -> results/WP4/s0_d10_blank_label_check.json). Labelled total = 2,830,743, which is the
  total I wrote in the acceptance rule. Correction to my own rule: 2,830,743 is the labelled-row count, not the raw file total;
  the raw total is 3,119,345 including the 288,602 empty rows. Empty rows are dropped in S1.
- Labels (all 15 known CICIDS2017 names; Web Attack labels have a non-ASCII dash in the file): BENIGN, DoS Hulk, DoS GoldenEye,
  DoS slowloris, DoS Slowhttptest, Heartbleed, FTP-Patator, SSH-Patator, Web Attack Brute Force, Web Attack XSS,
  Web Attack Sql Injection, Infiltration, Bot, DDoS, PortScan.
- Layout note: Monday timestamps are dd/mm/yyyy HH:MM:SS, the other days d/m/yyyy H:MM.

### D23 CSE-CIC-IDS2018 processed CSVs
- Listing: results/WP4/s0_d23_s3_listing_raw.xml (ListObjectsV2 over HTTPS), parsed to results/WP4/s0_d23_listing.json by
  tools/WP4_s0_d23_listing.py. 10 CSVs, total 6,886,649,507 B < 10 GB, so all days downloaded (all attack families covered).
- Download: ../data_extra/D23_cse-cic-ids2018/download_d23.sh (curl -C - -L --retry 5). One transfer
  (Thuesday-20-02) stopped at 3,960,847,732 B (curl rc 56); resumed with curl -C - to 4,054,925,350 B = listing size.
- Inventory (tools/WP4_s0_check_d23.py -> results/WP4/s0_d23_inventory.json): all local sizes = listing sizes.
  Rows: Fri 02-03 1,048,575; Fri 16-02 1,048,574; Fri 23-02 1,048,575; Tue 20-02 7,948,748; Thu 01-03 331,100;
  Thu 15-02 1,048,575; Thu 22-02 1,048,575; Wed 14-02 1,048,575; Wed 21-02 1,048,575; Wed 28-02 613,071. Total 16,232,943.
- FINDINGS: 6 files have exactly 1,048,575 data rows and Fri 16-02 has 1,048,574 (Excel's row limit minus header): the files were probably
  truncated by a spreadsheet export; so 7 of 10 files are at the spreadsheet limit. Needs a check
  against the known per-day counts before using them for time splits. Tue 20-02 has 84 columns and different header names
  (Flow ID, Src IP, Src Port, Dst IP, Dst Port, ...). Repeated header rows inside files (1 to 33 per file); removed in S1.
- Labels per file: Bot; DoS attacks-Hulk / -SlowHTTPTest; Brute Force -Web / -XSS, SQL Injection; DoS attacks-GoldenEye /
  -Slowloris; FTP-BruteForce, SSH-Bruteforce; DDoS attacks-LOIC-HTTP; DDOS attack-LOIC-UDP / -HOIC; Infilteration.

### D24 TOW-IDS
- IEEE DataPort page (https://ieee-dataport.org/documents/tow-ids-automotive-ethernet-intrusion-dataset) shows
  "LOGIN TO ACCESS DATASET FILES". Not downloaded. User action required (see report reports/WP4_S0.md).

### Disk
- D10 folder 1.49 GB (zip + extracted), D23 folder 6.89 GB. Free after: 62 GB on C:.

## 2026-10-21 S1 gate: D10 mirror vs D01 (acceptance rule, written BEFORE the comparison)

D01 = ../codes/data/CICIDS2017_sample.csv (56,661 rows, 77 features + grouped Label, no ids). v2 cleaning of D01 = drop
exact duplicates (features+Label) and conflicting-label feature rows -> 44,039 rows (results/network.json).
Gate MET only if: of the v2-clean D01 rows, >= 99% have a D10 row (labelled rows, same 77 feature columns, exact
float equality after inf->NaN in both) whose D10 label maps to the same D01 class (DoS = Hulk/GoldenEye/slowloris/Slowhttptest;
BruteForce = FTP/SSH-Patator; WebAttack = the 3 web labels; others by name). Also report the match rate on all 56,661 raw
rows, and the rate with features only (label ignored). If < 99%: stop, write why, ask; do not build the data layer.

## 2026-10-21 S1 acceptance rule for the data layer (written BEFORE building it)
1. D10 and D23 each reduced to one unified table (timestamp, src_ip, dst_ip, src_port, dst_port, protocol, 77 flow
   features, label, family, day, file, attacker/victim flags). D23 Tue 20-02 mapped by an explicit 84->canonical map with a
   test; after mapping, columns are the same set as the other D23 files.
2. Row counts per file before / after each cleaning step (empty/header rows, unparseable, exact duplicates, conflicting
   labels) are in results/WP4/s1_*.json. Cleaning rules as v2 (dup on features+label; conflicts = same features, different
   labels) but computed on the feature columns only (ids/timestamps excluded, as in v2).
3. Split by time only: every flow in exactly one of train/val/test, parts separated by time gaps; every family used for
   evaluation has >= 100 flows in test (and >= 30 in val where it exists on more than one block). Counts per part x family reported.
   Families with too few flows are listed as "not evaluable" rather than forced.
4. v2 numbers reproduced where applicable: D01 raw rows 56,661 / dup 12,598 / conflicts 24 / clean 44,039 reproduced by the
   same code on D01; D10 duplicate rate reported against D01's 22%.
5. Held-out families for leave-one-attack-out in S7 fixed now (list in the brief).
6. Derived caches (parquet) under ../data_extra/cache_v3/WP4/, <= 5 GB. Tests in tests/network/ pass.

## 2026-10-21 S1 gate RESULT: NOT MET -> STOP, asking the supervisor
Source: results/WP4/s1_gate_d10_vs_d01.json, s1_gate_diag.json (tools/WP4_s1_gate.py, WP4_s1_gate_diag.py).
- v2 cleaning of D01 reproduced exactly: 56,661 raw, 12,598 duplicates, 24 conflicting, 44,039 clean (matches results/network.json).
- Strict match (all 77 features equal, label mapped to the D01 class) of the 44,039 clean D01 rows in D10 (2,830,743 labelled rows):
  14,655 = 33.3% (features only 39.2%). On all 56,661 raw rows: 46.5% (features only 51.2%). Required >= 99%.
- Not a label problem: features-only is also low. Not a loading problem: every D01 row matches D10 on 5 key columns
  (Flow Duration, Fwd/Bwd packets, Fwd/Bwd total length), but 25 further columns differ in 2-10% of the key-matched rows (IAT stats,
  header lengths, Init_Win_bytes, min_seg_size_forward, URG count; diag json). Matching on the 55 columns that do not
  involve IAT / header / window / URG still finds only 55.4% of raw D01 rows.
- Interpretation (not verified): D01 (MTH-IDS) very probably comes from the "MachineLearningCVE" CSVs, i.e. a different
  CICFlowMeter run / flow set than GeneratedLabelledFlows; D10 and D01 are the same pcaps but not the same flow records, so D01 cannot certify D10.
  It does not show D10 is corrupt: all 5 key columns agree, label set and total (2,830,743) are the published ones.
- Decision needed from supervisor: (a) accept D10 anyway (the gate as defined cannot be met by any copy of GeneratedLabelledFlows if D01 comes
  from MachineLearningCVE), or (b) fetch MachineLearningCVE (also mirrored) and run the gate against it, or (c) wait for UNB.
  Per instructions the data layer was NOT built.

## 2026-10-21 S1 gate v2 (supervisor decision (b); written BEFORE downloading / comparing MachineLearningCVE)
Download MachineLearningCVE (CICIDS2017) to ../data_extra/D10_cicids2017_generated_flows/MachineLearningCVE/ (source + sha256 recorded).
All three must hold: G1 >= 99% of v2-clean D01 rows found in MLCVE with identical features and mapped label.
G2 per-day file row counts and per-label counts of D10 (labelled rows) equal those of MLCVE.
G3 on the 5 key columns (Flow Duration, Total Fwd/Bwd Packets, Total Length Fwd/Bwd), >= 99% of MLCVE rows are found in D10 with the same label.
All pass -> D10 accepted as source of IPs/timestamps/labels, with the caveat that timing/header features come from a different CICFlowMeter run
(list the differing features). Any fail -> stop and report.

## 2026-10-21 S1 gate v2 RESULT: G1 FAILS, G2 and G3 pass -> STOP, asking
MLCVE downloaded: bencorn/CICIDS2017 csvs/MachineLearningCSV.zip, 235,102,953 B, sha256 c3f26274...f728 = HF LFS oid;
extracted to ../data_extra/D10_cicids2017_generated_flows/MachineLearningCVE/ (8 CSV). Result file results/WP4/s1_gate2.json (tools/WP4_s1_gate2.py).
- G1: 17,065 of 44,039 clean D01 rows found in MLCVE with identical 77 features + mapped label = 38.7% (< 99%) -> FAIL. All D01 feature names exist in MLCVE.
  So D01 does NOT reproduce from MLCVE either; D01 is not a verbatim subset of either published file set (it likely went through
  the MTH-IDS preprocessing or a different CICFlowMeter run; unknown).
- G2: PASS. All 8 files have identical row counts (labelled rows) and identical per-label counts in D10 and MLCVE (total 2,830,743).
- G3: PASS. 100.0% of MLCVE rows found in D10 on the 5 key columns with the same label (all 8 files 1.0).
- Reading: D10 and MLCVE are the same flows (G2, G3) from the same official CIC family; the mirror is consistent with the other official file
  set (strong evidence the mirror is genuine). D01's own provenance is the unresolved part; G1 as written cannot be passed by any official file set.

## 2026-10-21 S1 supervisor decision on the gate
D10 ACCEPTED on G2+G3 (two file sets agree on every flow and label; published total matches). G1 recorded as FAILED: D01 (v2 sample, MTH-IDS
preprocessing) is not a verbatim subset of D10 nor MLCVE, so v2 numbers based on D01 are NOT directly comparable with v3. Differing features:
results/WP4/s1_gate_diag.json (IAT stats, Fwd/Bwd Header Length, Init_Win_bytes_*, min_seg_size_forward, URG Flag Count, ...). Caveat kept:
both file sets come from one unofficial mirror. D01 provenance is not investigated further. Continuing S1.
Extra rules fixed before building (additions to the S1 acceptance rule above): split = per day, periods = contiguous attack windows (family
timestamp clusters, gap > 30 min separates windows, 1st-99th percentile) and the benign stretches between them; each period is cut by TIME into
first 60% train, 20% val, 20% test with 2-minute gaps dropped (rows kept, split="gap"); periods shorter than 10 min -> train. Held-out families for
S7 leave-one-attack-out = every attack family with >= 100 test flows and >= 30 val flows after cleaning (decided from the counts, listed in the brief).
D23 timestamps are 24 h; D10 timestamps have no AM/PM: hours 1-7 are afternoon (+12 h), documented CICIDS2017 behaviour.

## 2026-10-21 S1 split design change BEFORE any model result (first D10 split showed GoldenEye 100% train (window < 10 min) and PortScan val = 2 flows)
No model has been trained, so this is data-layer design, not tuning on results. Changes: cut points are flow-count quantiles (60/20/20) of each
period instead of clock-time fractions, gap 1 minute (was 2), short-period limit 5 minutes (was 10). The first D10 stage-2 output is overwritten.

## 2026-10-21 correction: D23 timestamps also lack AM/PM
My earlier note ("D23 timestamps are 24 h") was wrong. Hour histograms of attack flows (tools/WP4_s1_hours_d23.py) show D23 attack flows at hours 1-5 (e.g. Fri 02-03
Bot at 14:24-15:55 appears as 2-3 h; Fri 16-02 Hulk 13:45 appears as 1 h; Wed 21 HOIC 14:05 as 2 h) and nothing at 13-23. Same 12-hour fold as D10, so hours 1-7 get +12 h
for D23 as well (applied in stage 2; the first D23 split, made without the fix, is overwritten). Also: 12 D23 rows have epoch-1970 timestamps: treated as NaT (split "gap").

## 2026-10-21 S1 results (final)
D10: 3,119,345 lines -> 288,602 empty -> 2,830,743; 596,376 duplicates; 542 conflicts; 2,233,825 clean; split 1,259,486 / 410,760 / 470,829 / gap 92,750.
D23: 16,233,002 lines -> 59 repeated headers -> 16,232,943; 5,410,812 duplicates; 43,572 conflicts; 10,778,559 clean; split 6,620,892 / 1,897,210 / 2,019,464 / gap 240,993 (+14 bad ts).
Evaluable families, held-out list, host labels: notes/WP4_brief.md, results/WP4/s1_tables.md, s1_heldout.json, s1_hosts_*.json. Acceptance MET (G1 recorded failed). 8 tests pass.

## 2026-10-22 S2 start (sonnet medium): L1 allow-list / protocol / TCP-state rules. ACCEPTANCE RULE (written before any score of these layers)
Looked at so far (benign TRAIN descriptives only, no scores): D10 flag columns are 0/1 presence flags (not counts) and several are known CICFlowMeter
artefacts (Fwd PSH Flags == SYN Flag Cnt; URG on ~10% benign TCP flows), so "impossible flag combination" is learned as rare-combination frequency, not
asserted from RFC per-packet logic. 224 benign-train flows already have 172.16.0.1 as source (so even the attacker IP is not perfectly novel).
Layers (all Layer subclasses, fit on BENIGN TRAIN only, threshold = tie-safe 1% budget on BENIGN VALIDATION, ECDF calibration via common/):
 net.allow_pair (src,dst,port/proto novelty, Witten-Bell backoff), net.allow_service (dst,port/proto only, no source identity), net.proto_port
 (protocol given port; RFC 768/791/9293/6335 limits), net.tcp_flags (flag-combination rarity), net.flow_rate (packet/byte rate vs physical limit).
Data: D10 main (stage = final, cleaned; flow level, dedup removed 99% of PortScan - the final cache has 1,851 PortScan flows: stated). D23: flag/protocol layers
on all 10 files, allow-list only on Tue-20-02 (only file with IPs).
Acceptance (A1-A4), fixed now:
 A1 False alarms: each layer and the combination <= 2.0% on D10 BENIGN TEST (budget 1% on val; 2x allowed for the time drift test vs val). Else reported as NOT MET.
 A2 Value: the combination WITHOUT source identity (all layers except net.allow_pair) detects >= 50% of test flows at the 1% budget in >= 3 of the 11 evaluable
    D10 families. net.allow_pair is reported separately because the lab has ONE external attacker IP (172.16.0.1): perfect detection by it would be an artefact
    (a real attacker is not a never-seen address), so it cannot count for A2.
 A3 Honesty: the report lists which families the rules cannot see (expected: Bot, Web-*, Infiltration, Slowloris-type application-layer attacks to allowed services),
    harness ablation (each layer alone, all, all-but-one) on a fixed subsample, and the exact FA.
 A4 Transfer D10 -> D23 (rules + thresholds from D10, no refit): flag/protocol/rate layers FA on D23 benign test <= 5% (different CICFlowMeter version/network);
    allow-list expected to FAIL (FA >> 5%) - reported, not a criterion.
One verdict run on test (D10 and D23 test splits, in-dataset and transfer); revisions afterwards are judged on validation only.

## 2026-10-22 S2 development on VALIDATION (D10), before the verdict run
Files: tools/WP4_S2_dev.py, results/WP4/s2_dev_val.json (first grid: rare-port pool 1/5/50 x host support 50/200/1000), s2_dev_val_grid2.json (50/200/1000 x 1000/3000/10000).
- First version (no pooling of rare ports): allow-list FA 0 and detection 0 on val: >1% of benign val flows go to a destination port never seen in train
  (random high ports, 1.9%), they tie at the top raw score, so the tie-safe threshold sits above them. Fix = pool port/proto keys seen < N times into their class bucket.
- Grid on val (mean detection over the 11 evaluable families at 1% FA): service layer 0.785 at support >= 3000 (rare >= 50, flat), pair layer 0.948 at support 10000.
  Chosen (val only, grid edge, no further search): rare_port = 1000, min_support = 10000 for both allow layers -> 15 known hosts. Frozen in network/l1.py.
- Other layers unchanged from the first version: proto_port (val AUC 0.08: attacks look MORE ordinary than benign in port/protocol terms), tcp_flags (DoS Hulk 35%, SlowHTTP 49%,
  Slowloris 32%, PortScan 16% on val), flow_rate (0% everywhere on val, AUC 0.23: attacks have LOWER rates than benign).
- Smoke run (pipeline check with the validation split in the test slot, results/WP4/smoke/) passed D10 and D23; it reads no test data.
- Open caveat decided now: net.allow_pair uses the attacker address 172.16.0.1 (a known host, since it appears in benign flows) as source in a (src,dst,port) combination never seen
  in benign: detection by it is lab-specific and must not count for A2.
Next: ONE verdict run: python tools/WP4_S2_run.py verdict.

## 2026-10-22 S2 VERDICT (one test run, results/WP4/logs/s2_verdict.log; tables results/WP4/s2_tables.md; report reports/WP4_S2.md)
D10 test FA on benign: allow_pair 1.17%, allow_service 0.93%, proto_port 0.69%, tcp_flags 1.14%, flow_rate 0.96%; harness combinations FA 1.07% (5 layers, max) and 1.20% (4 layers without allow_pair, logistic).
Source-agnostic stack detection: Bot 98.1, DDoS-LOIC-HTTP 100, GoldenEye 100, Hulk 99.8, SlowHTTP 99.3, Slowloris 100, FTP 74.4, PortScan 64.6, SSH 0, Web-BF 100, XSS 100 (%).
Diagnostic (train/val only, s2_diag_val.json): 99.75% of attack val flows go to 192.168.10.50 which gets 0.83% of benign flows -> detection is the rarity of the victim server.
PortScan pre-dedup (154,913 flows in test window): tcp_flags 99.1%, allow_service 20.9%, allow_pair 100%, proto_port 14.9%, flow_rate 0.9%.
D23 in-dataset: flag layers FA ~1%, detection ~0 (except tiny families, DDoS-LOIC-UDP via proto_port); allow-list on Tue 20-02: DDoS-LOIC-HTTP 0.0 / 0.1%.
Transfer D10 -> D23: allow-list FA 96.9% / 66.5%; tcp_flags FA 30.6% (RST/ECE flag semantics differ), proto_port 0.3%, flow_rate 0.1%.
Acceptance: A1 MET, A2 MET numerically (topology caveat), A3 MET, A4 NOT MET. No layer removed or inverted after the verdict; proto_port and flow_rate stay as reported negatives.
Cache S2: ../data_extra/cache_v3/WP4/S2/ (compact D10 / D23 tables, ~1.7 GB; WP4 cache total 4.9 GB). Smoke outputs deleted.

## 2026-10-22 S3 plan and acceptance rule (written BEFORE any L2a score was computed)
Data: PRE-DEDUP stage caches (flow multiplicity matters: dedup removed 99% of PortScan and most FTP/Slow flows), tools/WP4_S3_prep.py -> ../data_extra/cache_v3/WP4/S3/
(D10_stage 2,830,743 flows, D23tue_stage 7,948,748 flows). Stage ts needed the S1 +12 h fix (hours 1-7); split looked up from the final tables' (day, period, split) time intervals
(self-check: all 2,141,075 D10 and 5,327,506 D23 final rows keep their split and ts; flows in the 1-min gaps = "gap", never scored). D10 time resolution is ONE MINUTE (Monday: seconds),
so windows are whole minutes; D23 has seconds but is binned to the same minute grid.
Layers (network/l2a.py, topology-free: IPs only GROUP flows, no address identity, no lists of known hosts):
  net.scan       distinct dst ports per (src,dst) and distinct dst hosts per src in a trailing window of W minutes (sliding, via interval-union events)
  net.trw        threshold random walk (Jung 2004), theta0=0.8, theta1=0.2, first contacts per (src,dst,port) in a tumbling window of W min, success/failure from packet counts
                 (failure: no reply packet, or TCP with exactly 1 forward + 1 backward packet and no payload either way = SYN answered by a bare RST); score = peak log-likelihood ratio
  net.bruteforce flows (sessions) per (src,dst,dst_port) in the trailing window, scored as the benign tail probability of that count for that port (frequent ports own table, rest pooled)
  net.dos_rate   flows per (dst) in the trailing window / that destination's own benign median per-minute rate (learned on benign train; unseen destination -> pooled fallback)
  net.slow       half-open (no reply) + stalled (>= 5 s with <= 2 packets/s) flows per dst in the window, benign tail probability (pooled)
Scores are per flow = value of its cell (key, minute) = alarm at the end of the window. Fit: benign TRAIN stream (attack flows removed before computing the features: the
fitted statistics describe attack-free traffic). Calibration: benign VAL stream, tie-safe 1% budget (common.Layer.calibrate, flow unit) and, separately, the same budget on benign
(key, minute) cells (window unit). Test: the full mixed stream (attack flows present, they inflate the counts as they would in reality); FA counts every benign flow / benign cell.
Only choice made on val: window W in {1, 5} min per layer (max mean detection over the families the layer targets at 1% FA); nothing else is tuned.
Harness: topology-free stack = net.tcp_flags (L1, refit on stage benign train/val) + the 5 L2a layers, logistic combiner, subsample of the test stream AFTER the features are computed.
Acceptance (fixed now; one verdict run on test):
 B1 FA <= 2% on benign test, flow unit AND window unit, for every L2a layer and the stack.
 B2 PortScan (pre-dedup flows) >= 80%, SSH-Patator >= 50%, FTP-Patator >= 50% of test flows detected by some L2a layer at its 1% budget.
 B3 DoS: the L2a layers detect >= 50% of the flows of >= 3 of the 5 DoS/DDoS families (Hulk, GoldenEye, Slowloris, SlowHTTPTest, DDoS-LOIC-HTTP).
 B4 Added value over the topology-free L1: macro mean detection over the 11 evaluable families of (tcp_flags + L2a) exceeds tcp_flags alone by >= 20 points (harness ablation).
 B5 Transfer to D23 Tue-20-02 without refit (D10 tables, thresholds): FA <= 5% on benign test flows and DDoS-LOIC-HTTP detection >= 50% (dos layers). Refit-on-D23 shown separately.
 B6 Honesty: list families time windows cannot see (single-flow application attacks: Web-XSS, Web-SQLi, Heartbleed, Infiltration, Bot unless it shows up as repetition), delay from
    attack-window start per family, FA split into "benign flows in attack cells" and others.

## 2026-10-22 S3 development on VALIDATION (D10), before the verdict run (tools/WP4_S3_dev.py, results/WP4/s3_dev_val.json, log results/WP4/logs/s3_dev.log)
Findings that changed the design (all on train / val, test never read):
1. Reversed flows: CICFlowMeter reports many flows with the server as "source" and an ephemeral client port as "destination"; a busy server then "contacts" 1000+ distinct ports
   in a minute. Fix (fixed rule): scan and TRW count only service-directed flows (dst port < 32768); TRW only TCP connection attempts (Jung 2004).
2. TRW success / failure: the "bare RST" reply carries 6 payload bytes (Ethernet padding counted by CICFlowMeter), so a refused SYN is 1 fwd + 1 bwd packet with <= 6 B per direction.
3. Brute force: a tail probability saturates at 1/N and favoured ports with many benign cells (SSH / FTP val detection 0); replaced by log10(count / benign 99.9th percentile of that port).
4. LABEL PROBLEM in D10 (benign validation): Thursday 2017-07-06 15:23, one benign-labelled host sends 2,033 flows (1,008 distinct ports) in ONE minute = a port scan by the compromised
   Infiltration victim (the Infiltration file has 36 Infiltration labels but this scanning is labelled BENIGN). With published labels the scan thresholds sit above the real PortScan
   (913 vs 909 ports) and every layer's 1% budget is eaten by it. DECISION (made on val, before the verdict): the whole D10 file Thursday-Afternoon-Infilteration is AUDITED: its benign
   flows are excluded from fit, calibration and the headline FA, but stay in the stream (they still contribute to window counts). The FA with the published labels is reported next to the headline.
   Acceptance B1 therefore reads: headline FA = benign test flows outside the audited file; FA with published labels reported as well (not a criterion).
5. Window W (val rule fixed above): scan 1, trw 5, bruteforce 1, dos_rate 1, slow 5 (PortScan val 100% by scan W=1 and TRW; SSH / FTP 100% by bruteforce; DDoS-LOIC / Hulk by dos_rate and
   bruteforce; Slowloris only partly by bruteforce; GoldenEye by nothing on val (312 flows in one minute, below the busiest benign server's rate)). No other parameter was tuned.
   Classic TRW threshold ln(99) (diagnostic): FA 10% on benign val (benign hosts fail first contacts often) -> a budget threshold is needed.

## 2026-10-22 S3 VERDICT (one test run: results/WP4/logs/s3_verdict.log; tables s3_tables.md; report reports/WP4_S3.md)
B1 MET (layer FA 0.00-1.77%, window FA 0.07-0.90%, stack 0.33%). B2 MET (PortScan 97.4, SSH 98.6, FTP 99.95). B3 MET (4/5 DoS >= 50; Slowloris 0). B4 MET (macro 21.1 -> 54.2; L2a alone 61.9).
B5 NOT MET: transfer to D23 Tue-20-02 FA of OR 46.6% (dos_rate 39.7%, slow 7.7%; scan 2.5, trw 3.1, bruteforce 2.2); LOIC 99.7%. Refit: LOIC 100%, OR FA 5.5%. B6 done (report caveats).
Surprises: the learned logistic combiner kills SSH (0.1%) when tcp_flags and slow are in the stack; PortScan on dedup survivors only 40.6% vs 97.4% pre-dedup (multiplicity matters).
No layer, threshold or window changed after the verdict. S2/D23.pkl deleted (cache 4.7 GB).
