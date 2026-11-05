# WP9 B5 notes (final comparison, no new scoring)

2026-11-05: Acceptance rule (written when the step started, before the master table existed; the orchestrator brief gave the wording rules):
1. Every number in the master table and in the claims is read by path from an approved result JSON (B1-B4, WP8 S7/S8) and re-read by tools/WP9_B5_check.py (equality, formatted text, cell present in reports/WP9_final.md).
2. Verdict words only from {better, equal, comparable-not-like-for-like, not comparable, below}; 'better' needs same data + same-or-stricter split + CI excludes the bar (flags in the master JSON). Binding wording from notes/WP9_brief.md ("ORCH on Bx"): equal = "matches the best published results under a stricter split"; failed controls stated in the caveat column; S8 rows labelled "H31 exposure 2, post-M4 fix, NOT fresh".
3. Figures from saved scores only; operating points recomputed from the scores at stored thresholds must equal the JSON values (results/WP9/B5/figures/ops_sanity.json).
Decisions: D11 headline = 1% budget row with S secondary (ORCH on B1); AV-GPS "equal at S, never better" (ORCH on B4); LiDAR not comparable; network "not like-for-like" / "first leak-free numbers we know of" (ORCH on B2); V2X DoS matched = equal, all-19 = not comparable (ORCH on B3).
Files: tools/WP9_B5_{lib,build,figs,check}.py, results/WP9/B5_master.json, results/WP9/B5/figures/, reports/WP9_final.md, tests/system/test_wp9_b5.py.
Observed: reports/M4.md prints the paired K events-per-hour difference as -302.52/h (x100 display error); JSON value -3.03 [-5.77, 0.46] is used.
Results: check PASS (327 fields). Verdict counts in reports/WP9_final.md summary: no row 'better'.
