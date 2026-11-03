# WP8 S4 notes (network streaming Evidence, unseen Bot)

Rules: notes/WP8_v31.md (S4 pre-registration + round-2 addendum). Report: reports/WP8_S4.md. Journal: notes/WP8_journal.md.

## 2026-11-03
- The WP4 caches (../data_extra/cache_v3/WP4/*) were empty. Rebuilt D10: `tools/WP4_s1_build.py D10` (stage + final) and `tools/WP8_S4_prep.py` (S3-style stage stream; counts equal results/WP4/s3_prep.json; train+val copy at ../data_extra/cache_v3/WP8/S4/). Side effect restored: results/WP4/s1_clean_D10.json.
- Facts seen before any score: D10 timestamps are whole minutes in Tue-Fri files, second resolution in the Monday benign file; the v3 layers key on the integer minute, S4 keeps tick = 60 s.
- Round 1 (R5, R2, R1; results/WP8/S4/s4_val_candidates.json): none feasible (macro 50.7 / 46.5 / 47.0 vs v3 58.3). Round 2 (RC5, RC2, RC1 with a one-tick carry; F1 minute-final): RC5 and F1 feasible, rule picks RC5.
- v3 reproduction: frozen domain on rebuilt val = stored WP4 S7 val view (FA 0.0095996177, macro 0.5825676723, all families). Re-derived threshold 0.995701 vs frozen 0.996067 (tie order of Monday flows inside a minute).
- Stream checks: tools/WP8_S4_stream_check.py (RC5) and WP8_S4_final_check.py (F1): stream == batch exact on 3 x 25,000 real val flows; timings in the report.
- Bot: tools/WP8_S4_bot.py, results/WP8/S4/s4_bot.json. No candidate counts for N4.
- Tests: tests/v31/test_s4_stream.py (6) and test_s4_regression.py (2); full suite 512 passed (before the last test was added), run_all.py --check all OK.
