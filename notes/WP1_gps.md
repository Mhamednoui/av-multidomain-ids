# WP1 GPS notes

## 2026-10-19 S0 (download D15 OSM)
Acceptance rule (written before any result):
- Extract covers the lat/lon bbox of all 23 KITTI 2011_09_26 drives (OXTS) + ~1 km margin:
  100% of OXTS fixes of every drive fall inside the extract bbox (and inside bbox minus 500 m).
- File loads with python -I; contains > 0 highway ways and their nodes; every drive has road
  ways within 50 m of >= 95% of its fixes (sanity: map is the right place).
- Size < 100 MB; >= 15 GB disk free after download; licence ODbL recorded with attribution.
Done (tools/WP1_osm_bbox.py -> results/WP1/osm_bbox.json; tools/WP1_osm_verify.py -> results/WP1/osm_verify.json):
- 23 KITTI drives, OXTS bbox lat 48.94231..49.06758, lon 8.33725..8.47829; +1 km margin
  lat 48.93333..49.07656, lon 8.32356..8.49199.
- Overpass query (all highway=* ways + nodes) -> ../data_extra/D15_osm/karlsruhe_highways.json,
  36,924,973 bytes (35.2 MB), 57,018 ways, 193,170 nodes, OSM timestamp 2026-10-19T21:54:50Z.
  Contains footways/paths/service etc. (map matching in S6 should filter to drivable classes).
- All 23 drives: 100% of fixes inside bbox+margin; 100% of fixes (min over drives) within 50 m of a road.
- Disk free after: 52 GB. Licence ODbL 1.0, attribution (c) OpenStreetMap contributors.
- Untrusted data read with python -I, JSON only; nothing executed.
Acceptance: MET (all criteria above).

## 2026-10-19 S1 (data layer: unified stream + attack generator)
Acceptance rule (written before any result):
1. Unit tests in tests/gps/ pass, and `python tests/run_tests.py` passes (whole suite).
2. B2 (dead-reckoning rule) run on the NEW stream (v2 attacks only, same rng order, same split)
   reproduces the WP0 S3 numbers exactly: rows test/train/val 7910/23859/2850, runs 350/1080/150;
   false alarms on clean test runs 0.015803; row and run-level detection per attack identical to
   1e-4; tp/fp/fn/tn 1770/67/1151/4922; raw-equivalent threshold 6.658872 (WP0 v3 definition).
   (v2's interpolated 6.657975 differs by 0.0009 m with no decision changed, see WP0_S3.md.)
3. Extended stream (v2 attacks unchanged + two new attacks per run structure) keeps the v2 runs
   bit-identical (same lat/lon/odo speed as the v2-only build).
4. Doppler-consistent spoof: exact discrete identity (offset step/dt = mean of the velocity
   offset of the two fixes) and, on the built KITTI stream, the median |reported velocity -
   central difference of reported track| on spoofed rows <= 1.5 x the same median on clean
   rows (naive drift of v2 must be clearly larger: >= 2 x).
5. Meaconing: reported track equals the true track at t - tau(t) (exact on synthetic truth),
   reported velocity = V(t - tau)(1 - dtau/dt) = derivative of the reported track (synthetic
   circular truth, error < 1% of speed), reported acceleration never exceeds the clean maximum
   by more than the ramp's contribution (tau' <= 0.25), clock offset column = -tau.
6. Severity ranges explicit in module constants and in the report.
7. Splits by group (drive / session / flight), stored in results/WP1/splits.json; no group in two parts.
Amendment (still before any result): meaconing delay growth tau' rises linearly 0 -> 0.2 s/s over 2 s
(smooth onset, no acceleration impulse); criterion 5 becomes: reported speed change per second on attacked
rows <= max(99.9th percentile on clean test rows, 3 m/s^2); velocity = derivative of reported track on
synthetic circular truth within 2% of speed.
Amendment 2 (before any result; unit tests only so far): the delay profile is a smoothstep tau = tau_max(3u^2 - 2u^3),
u = min(tr/T,1), T = 1.5 tau_max / 0.2 (tau' zero at both ends, peak 0.2 s/s) because the capped linear ramp
left a step in the apparent speed when the cap was reached (caught by the unit test). Criteria 5 unchanged otherwise.
Done (S1): gps/stream.py, tools/WP1_S1_b2.py, tests/gps/test_stream.py (10 tests; suite 29 pass), results/WP1/S1_*.json, splits.json, reports/WP1_S1.md.
- B2 from the new stream = WP0 S3 exactly (every comparison OK, threshold 6.658872); extended stream keeps v2 runs identical.
- Extended test (B2 calibrated train+val): run-level detected doppler_spoof 0.414, meaconing 0.471; val-only calibration: AUC 0.847, FA 0.70%.
- Physics: median |v_rep - track derivative| ratio to clean: doppler 1.03, meaconing 1.03, drift 2.53, accel_drift 3.95, freeze 19.4.
- Pitfalls: capped linear delay ramp left a speed step (test caught it); AV-GPS time = row counter; UAV onset 117 s approximate.
Acceptance: MET. S1 -> REVIEW.
