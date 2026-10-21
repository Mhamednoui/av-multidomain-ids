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
