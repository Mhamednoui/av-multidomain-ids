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
