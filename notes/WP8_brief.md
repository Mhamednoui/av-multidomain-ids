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

## S5 (CAN incremental + V2X single ego, worker sonnet) - REVIEW 2026-11-03
- Code: can/incremental.py (IncrementalCan), v2x/ego_stream.py (EgoStream), tools/WP8_S5_{can,v2x,report}.py, tests/v31/test_s5_incremental.py; results results/WP8/S5/ (S5_acceptance.json, parts/), scores results/WP8/scores/S5/; report reports/WP8_S5.md. v3 frozen files untouched; suite 494 pass.
- CAN: 13 captures / 14.0 M frames / 5,892 windows, 0 mismatches, max diff 0.0; p99 window 24-41 ms (limit 150); growth ratio 0.91 on the longest (8.8 M frames; limit 1.5). C1, C2 MET.
- V2X: 64 egos (55 V2AIX Mobile val, 9 VeReMi val views): compute <= 0.027 s per stream s (limit 0.5), p99 msg <= 10.6 ms; identical on 61/64 egos; 3 V2AIX egos differ on 6 rows from CAMs received out of generation order (batch sorts by t, stream cannot). V1 MET except literal 0-mismatch (decision for supervisor).
- Pitfalls: results/WP7/frozen_v2x is untracked in git (used read-only); only 55 of 152 Mobile val recordings have a full ego pose.

