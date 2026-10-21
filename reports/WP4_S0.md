# WP4 S0: data download (D10, D23; D24 not downloaded)

Date: 2026-10-21    Worker: worker haiku (WP4 S0 session)

## Goal of the step
Download the network datasets for WP4: D10 CICIDS2017 GeneratedLabelledFlows (full flows with IPs, ports, timestamps),
D23 CSE-CIC-IDS2018 processed CSVs (cross-dataset test), D24 TOW-IDS only if login-free.

## Acceptance rule (as written in notes/WP4_network.md BEFORE the download, 2026-10-21 18:47 +01:00)
Summarised: D10 complete (8 CSVs, columns present, row counts reported, labels from the known set); login-free source;
D23 all files with size = listing size, total <= 10 GB (else day subset), cap 15 GB; D24 only if login-free; disk >= 15 GB
free before each download; licence recorded; DATASETS rows, notes, report, STATUS.

## What was done
- D10: unofficial mirror https://huggingface.co/datasets/bencorn/CICIDS2017 (csvs/GeneratedLabelledFlows.zip, 283,876,488 B).
  The official UNB site was not reachable (unb.ca "temporarily restricted" for off-campus users).
  Extracted to ../data_extra/D10_cicids2017_generated_flows/extracted/TrafficLabelling/ (1.2 GB).
- D23: all 10 processed CSVs from the public bucket over HTTPS, 6,886,649,507 B total (under the 10 GB limit, so no day subset).
  One transfer was interrupted (curl rc 56) and resumed with curl -C -; final sizes equal the S3 listing for all 10 files.
- D24: not downloaded. The IEEE DataPort page shows "LOGIN TO ACCESS DATASET FILES".

## Results (from results/WP4/*.json)
| Check | Result |
|---|---|
| D10 files present / parse / required columns | 8 / yes / yes (Flow ID, Source & Destination IP and Port, Protocol, Timestamp, Label) |
| D10 labelled rows (sum of 8 files minus empty rows) | 2,830,743 (raw 3,119,345; 288,602 empty separator rows in Thu-Morning-WebAttacks) |
| D10 label values | 15 known CICIDS2017 labels only |
| D10 sha256 vs mirror LFS record | match (7bdbef28...); not checked against UNB (site unavailable) |
| D23 sizes vs S3 listing | 10 / 10 equal |
| D23 data rows total | 16,232,943 |
| D23 columns | 80 in 9 files, 84 in Thuesday-20-02 (different header names: Flow ID, Src IP, ...) |
| Disk free | 72 GB at start, 62 GB at the end (>= 15 GB rule met) |

Acceptance: MET with caveats.
- D10 is from an unofficial mirror (licence card "other"); its integrity is only shown against the mirror's own LFS record.
  The supervisor must decide whether this mirror is acceptable for WP4.
- The row total I wrote in the rule (2,830,743) is the labelled-row count; the raw file total is 3,119,345 because of the
  288,602 empty separator rows. Labelled rows match the rule's number exactly.
- D23: 7 of 10 files sit at the spreadsheet row limit (6 at exactly 1,048,575 data rows, Fri 16-02 at 1,048,574).
  This suggests truncation in the processed files; it must be checked before time splits (S1).

## Ablation row(s) for the layer(s) of this step
Not applicable (data step).

## Problems, surprises, open questions
1. D10 source: official UNB unavailable; mirror is unofficial. Question for the supervisor: accept the mirror, or wait for UNB?
2. D10 empty-row block (288,602 rows) in Thursday-Morning-WebAttacks: dropped in S1.
3. D23 truncation at the Excel row limit (7 of 10 files) and the 84-column Tue 20-02 file: needs S1 handling and a
   comparison with the known per-day counts.
4. D23 repeated header rows inside files (1 to 33 per file) and one 4 GB file that needed a resume.
5. D24 needs the user to log in to IEEE DataPort (see below).

## User action required
- D24 TOW-IDS: log in to IEEE DataPort (https://ieee-dataport.org/documents/tow-ids-automotive-ethernet-intrusion-dataset)
  and download the files into ../data_extra/D24_tow-ids/, or say that D24 is out of scope for WP4.
- D10: decide whether the unofficial HF mirror is acceptable (or ask for the official UNB files when the site is back).

## Proposed next step (or changes to the plan)
S1 data layer on D10 + D23 (time split, duplicate and label cleaning, Excel-limit check on D23).
