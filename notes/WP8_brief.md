# WP8 brief (<= 60 lines; each worker edits only its own lines)

## S0 (hold-out + pre-registration, worker opus) - REVIEW 2026-11-03
- Locks: locks/H31.json (scored ONCE in S7, by v3 and v3.1), locks/V31_val.json (all S2-S6 choices). Rules: notes/WP8_v31.md (G1-G10, S1-S6, M4-1..15), committed 1eca013.
- H31: KITTI 13 fresh drives (9 same-day + 4 other-day) FRESH; comma Chunk_2 RAV4 + Chunk_4 Civic FRESH; V2AIX 674 unextracted recordings FRESH; CAN / VeReMi re-used + small fresh parts; network RE-USED (exposure 7).
- V31_val = v3 val + v3 test of KITTI / comma Chunk_1 / V2AIX; CAN / NET / VeReMi only their v3 val splits.
- S1: results/WP8/S0/S1_download_list.json (13.0 GB transfer, 17.3 GB disk); tools/WP8_S0_*.py; report reports/WP8_S0.md.
- Pitfalls: V2AIX recordings share site + day with train; Civic wheel speed not at 0xAA; OTIDS / normal_run not in DATASETS.md; never commit V2AIX data or per-message scores.

## P1 (paper analysis, worker sonnet) - REVIEW 2026-11-03
- Output results/WP8/P1/ (tables md/csv, ROC png/pdf), tools/WP8_P1_curves.py, reports/WP8_P1.md.
- GPS AUC 0.895 (row level), det 68.8% @1% FA, 74.7% @5%; LiDAR AUC 0.750 (9 attacks), 18.3% @1%, 38.5% @5%. CAN partial (raw S3 columns). Net: operating-point table only. V2X / fusion: not available without a re-run.
