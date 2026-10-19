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

## 2026-10-19 S2 (L1 receiver sanity rules)
Acceptance rule (written before any S2 result was computed; I had only looked at column names / value ranges
of the UAV and AV-GPS receiver fields and at the AV-GPS step sizes, no rule has been scored yet):
Coverage (stated before results, from the data layer): KITTI has no receiver fields (fix_type / hdop are constants
written by the simulator, numsats is the real OXTS count but the attack simulator never touches it, clock_offset is
produced by our own meaconing generator) -> on KITTI ONLY the kinematic rules and the receiver self-consistency rule
(Doppler vs position) are evaluated. Fix-type, satellite, DOP, noise/jamming-indicator, clock rules are not evaluated
on KITTI (no invented fields). AV-GPS (1 Hz confirmed: median step / odometry speed ~ 1): kinematic rules from
position only (no Doppler, no IMU accel); hdop = 100 and numsats = 0 mark the no-fix placeholder of the spoofed
sessions (artefact), so receiver-field rules there are reported as artefact only, never as detection. UAV: fix type,
satellites, HDOP, noise_per_ms, jamming_indicator (the PX4 stand-in for AGC; AGC itself is absent), Doppler vs position.
Clock rule: time_utc_usec is 0 in the spoofing and jamming flights, so the clock rule is implemented and unit-tested but
evaluated nowhere.
A1 unit tests tests/gps/test_l1.py pass; whole suite passes.
A2 Physical limits (max speed, longitudinal / lateral acceleration, jerk, minimum turn radius, min satellites, HDOP,
clock rate) are constants in gps/l1.py with a written source each, fixed before any run and not changed afterwards.
A3 At the physical operating point (alarm iff the quantity exceeds its limit; no fitted threshold) the UNION of the
kinematic rules has false alarms <= 1.0% on KITTI clean test runs, and each rule alone <= 1.0%. Detection is NOT a pass
criterion: a rule that detects little and never false-alarms is kept.
A4 Data-driven thresholds (Doppler-vs-position consistency; satellite / HDOP / noise / jamming-indicator jumps) are set
on validation normal rows only (KITTI val drives; UAV: the benign flight, see decision below), 1% budget, tie-safe,
test scored once.
A5 AV-GPS: false alarms of the kinematic physical union <= 1.0% of test normal rows (report what fires, incl. glitches).
A6 UAV spoofing flight: at least one L1 rule alarms within 2 s of the first spoofed fix (118.0 s); L1 union false alarms
<= 2% on the spoofing flight before 117 s (out-of-sample), benign flight false alarms reported (in-sample for the
calibrated rules).
A7 Harness ablation on KITTI at the 1% budget: B2 alone vs L1 alone vs B2+L1 vs all-but-one. "L1 adds" is judged
only as: the B2+L1 combination does not lose more than 1 point of AUC against B2 alone and the test false alarms stay <= 1.5%;
which attacks it adds detection for is reported, including "nothing".
Decision (documented, flagged to the supervisor): all UAV flights are test in splits.json (case study). The receiver-jump
rules need normal data from that receiver and no other data exists, so the BENIGN flight is used as their calibration
set and is excluded from their out-of-sample claims; their false alarms are then measured on the pre-onset part of the
spoofing flight (117 fixes). The jamming flight has no onset label and stays unlabeled (alarm timeline only).
Done (S2): gps/l1.py, tests/gps/test_l1.py (12 tests, suite 41 pass), tools/WP1_S2_l1.py, tools/WP1_S2_tables.py, results/WP1/S2_*.{json,md}, reports/WP1_S2.md.
- KITTI physical kinematic rules: 0.00% FA on clean test runs (each and union); detect jump 86% of runs, freeze 14%, everything else 0% (they never fire on drift, Doppler spoof, meaconing). Margins: yaw 0.77-0.87 of limit, others < 0.33.
- Doppler-vs-position (val 1% budget): FA 1.26% clean test runs; run-level drift 70%, accel_drift 56%, freeze 84%, jump 100%, Doppler spoof 16%, meaconing 17%.
- Harness: B2 alone AUC 0.847 FA 0.70%; B2+all L1 AUC 0.860 FA 1.39%; B2+kinematic 0.855 / 0.99%; without B2 0.709.
- AV-GPS kinematic union FA 0.61%, detection 13.7% (placeholder coordinates); sat/HDOP rules = artefact.
- UAV spoofing: sat_jump, hdop_jump, noise_jump, vel_pos fire at 118.0 s; union FA before 117 s 2.54% (3/118) -> A6 FA part NOT MET (not retuned); benign flight used as calibration set (decision flagged).
Acceptance: A1-A5, A7 MET; A6 detection MET, A6 FA NOT MET. S2 -> REVIEW.
