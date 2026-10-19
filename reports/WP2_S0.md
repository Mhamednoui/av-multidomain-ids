# WP2 S0: download and verify D11 can-train-and-test

Date: 2026-10-19    Worker: sonnet

## Goal of the step
Download D11 (pre-approved, RULES 3.4), check the licence, verify integrity, record it.

## Acceptance rule (notes/WP2_can.md, "S0 start", written before results)
Licence allows research use; file size and MD5 equal the published ones; extraction leaves
>= 15 GB free; every CSV parses (columns, rows, labels); DATASETS.md updated.

## What was done
- Downloaded figshare 24805533 (one zip) to ../data_extra/D11_can-train-and-test/raw/, extracted
  next to it. Parsed all 236 CSV with python -I (tools/WP2_s0_verify.py).
- DATASETS.md: D11 row and new section 5 (layout). Notes: notes/WP2_can.md.

## Results (results/WP2/s0_inventory.json, s0_summary.txt, s0_extra.txt)
| Item | Value |
|---|---|
| Licence | CC BY 4.0 |
| Zip size / MD5 | 1,507,455,719 B / bd6509d670c0a0009cb3ecab34111bcd (= published) |
| Extracted | 7.47 GB, 236 CSV, 193,240,845 frames |
| Free disk after | 44 GB |
| Columns | timestamp, arbitration_id, data_field, attack (all files) |
| Labels | {0,1} only |
| Vehicles | Impala, Traverse, Silverado, Subaru (sets 01-04, known / unknown) |
| Distinct files | 174 of 236 (62 byte-identical duplicates across sets) |
Acceptance: MET

## Problems, surprises, open questions
- Site version is v1; the "v1.5" mentioned in DATASETS.md was not found on figshare.
- No DLC column (derive from data_field length); one odd 17-char hex length value to inspect.
- Timestamps: synthetic epoch start, sub-ms inversions around injected frames.
- Duplicate files across sets: S1 splits must not put a copy on both sides.
- Vehicle identity is only given at set level (known / unknown), not per file: S1 maps by set.

## Proposed next step
WP2 S1 (data layer) once M0 is done.
