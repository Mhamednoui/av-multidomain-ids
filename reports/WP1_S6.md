# WP1 S6: L2e map matching on the D15 OSM extract (drivable roads only)

Date: 2026-10-21    Worker: sonnet (WP1, medium)

## Summary (details: results/WP1/S6_tables.md, S6_acceptance.json, notes/WP1_gps.md "2026-10-21 S6")
- Built `gps/map_match.py`: D15 filtered to DRIVABLE classes (fixed before any result: motorway, trunk, primary, secondary, tertiary, unclassified, residential, service, living_street, and *_link of the first five; footway, path, cycleway, steps, pedestrian, track excluded), 97,614 segments, one-way handling (oneway=yes/1/true/-1, roundabouts), scipy cKDTree on points densified every 3 m + exact point-to-segment distance. Scores: map_dist (m), map_heading (deg vs road direction, 0 below 3 m/s), map_comb (max of both, scaled by dev 95th percentiles).
- Calibration: LODO over the 16 train+val drives (1% budget, tie-safe), val-only side by side; no fitted parameter. Primary chosen by nested J: map_dist (14/15 folds). One test pass.
- Acceptance (rule written before results):
  - D1 tests: MET (154 pass, 6 new).
  - D2 map sanity: MET (100% of clean dev fixes within 10 m of a drivable road; median 1.71 m, p99 5.62 m; median heading deviation 1.5 deg).
  - D3 clean-run FA on test <= 1.5% (LODO) and nested held-out <= 1.5%: NOT MET. map_dist test FA 4.11% LODO (0.57% val-only); nested dev held-out FA 2.63%. Cause (post-hoc, S6_diag.json): a systematic 4-5 m centreline offset on a few drives (test 0028 25.7%, 0001 7.3%; dev 0027 21.7%, 0017 3.0% FA at the pooled threshold), i.e. a per-road bias (lane offset, OSM geometry), not receiver noise. The global threshold is 5.62 m. Not retuned.
  - D4 "L2e adds" on top of the S5 stack (AUC 0.922, FA 1.15%): NO. AUC -0.0024, FA 1.27%; row-level gains <= +1.9 points (drift, Doppler, meaconing), below the +5 rule. Same for base, base + all L2d, all three map layers; val-only also no.
  - D5 physics expectation: confirmed (below). Slow drift untestable (S4/S5 decision).
- Run-level detection on test, LODO (map_dist; row-level in brackets): drift 33% (23), accel_drift 39% (39), jump 87% (60), freeze 9% (18), doppler_spoof 40% (41), meaconing 11% (8). Median delay 5-7 fixes for drift/accel/Doppler, 0 for jump. Reference cusum_dr: 70/61/100/84/70/61.
- Alone it is weak: AUC 0.652 (map_heading 0.586, map_comb 0.667); B2 + map AUC 0.824 vs B2 alone 0.847 (LODO).
- What it can and cannot see (measured on-road fraction = share of attacked test rows whose fix lies within 5.62 m of a drivable road, so no threshold can flag them): meaconing 92% (replays the true track, stays on the road), freeze 82%, drift 77%, accel_drift 61%, Doppler spoof 59%, jump 40%. It only sees spoofs that push the fix off the network: mainly jump, and the late phase of large drifts. Anything that follows or drifts along a road, or freezes on it, is invisible by construction; a route-aware (road-following) spoofer defeats it entirely.
- Verdict: L2e is a weak, map-dependent layer; it does not improve the S5 stack and its false alarms transfer badly across drives because OSM geometry has per-road offsets. Recommend: keep it out of the default GPS stack; optional low-weight evidence for WP5 (road plausibility) / WP6.
- Heading layer: course vs road direction is nearly useless (AUC 0.586): attack courses follow the road and the clean p99 deviation is 30 deg at junctions.

## Acceptance table
| criterion | value | verdict |
|---|---|---|
| D1 tests | 154 pass | MET |
| D2 map sanity | 100% within 10 m; median 1.71 m; heading median 1.5 deg | MET |
| D3 clean-run FA test (LODO) / nested dev | 4.11% (val-only 0.57%) / 2.63% | NOT MET |
| D4 adds on S5 stack | AUC -0.0024, FA 1.27%, max row-level gain +1.9 pts | NO |
| D5 physics expectation | on-road fractions 40-92% | confirmed |

## What was done
- Files: `gps/map_match.py`, `tests/gps/test_map_match.py`, `tools/WP1_S6_dev.py` (16 drives only), `tools/WP1_S6_test.py` (one pass; dry run on val first), `tools/WP1_S6_tables.py`, `tools/WP1_S6_diag.py` (post-hoc), `results/WP1/S6_*.json|md`, `notes/WP1_gps.md`, `notes/WP1_brief.md`.
- Data: D15 (ODbL), KITTI streams as in S4/S5; test drives scored once.
- Map variants (dev only, diagnostic, not selectable): without service ways J 0.301 vs 0.299 (no difference, 53,330 segments); with ALL highway classes (footways, paths, tracks) J 0.255: the drivable filter matters (+0.044).

## Results (full tables incl. harness ablations, delays and FA transfer: results/WP1/S6_tables.md)
Test, LODO calibration (clean-run FA; run-level detection):
| layer | FA | drift | accel | jump | freeze | Doppler | meaconing | AUC |
|---|---|---|---|---|---|---|---|---|
| gps.map_dist | 4.11% | 33% | 39% | 87% | 9% | 40% | 11% | 0.652 |
| gps.map_heading | 0.63% | 16% | 21% | 46% | 0% | 17% | 4% | 0.586 |
| gps.map_comb | 0.63% | 20% | 29% | 57% | 0% | 23% | 4% | 0.667 |
| gps.cusum_dr (S4) | 1.64% | 70% | 61% | 100% | 84% | 70% | 61% | 0.846 |

Val-only calibration: map_dist FA 0.57%, detection 26/31/76/1/31/1%; the FA depends on which drives are in the calibration set.

## Problems, surprises, open questions
- map_dist false alarms concentrate on a few drives with a 4-5 m systematic offset to the OSM centreline; more dev drives would not fix a per-road bias.
- Open question: keep L2e out of the default stack (recommended), or give it a role in WP5/WP6?

## Proposed next step
S7 (L3 normal-only model of residuals; L4 retrain C2 inside the harness) without L2e in the default stack; L2e enters the S8 ablation as an optional row.
