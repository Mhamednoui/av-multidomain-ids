# WP7 System brief (state at end of S1, 2026-10-22)

## State
- S1 streaming runtime: REVIEW. Acceptance A1-A6 all MET on validation data (results/WP7/S1_acceptance.json); report reports/WP7_S1.md; tables results/WP7/S1_tables.md; log notes/WP7_system.md.
- S2 simulation v3, S3 run_all / make_report / README, S4 publication: not started (S2 needs the NET and LiDAR domains frozen to be more than a plumbing test).

## What exists (system/)
- bus.py EvidenceBus (publish / subscribe / merged by stream time / wall + ingest time per record), runner.py (Runner base: reset, push, flush, LatencyLog, status labels; compare_sequences / same_evidence helpers).
- gps_runner.py GPSRunner(folder frozen_gps): per fix; row dict = gps/stream.py columns + the 6 lid_* columns (LiDAR odometry computed upstream). Prefix re-score of the frozen GPSDomain.
- can_runner.py CANRunner(folder s7_domain): per frame (t, id, dlc, payload8); emits combined + per-layer Evidence per completed 1 s window; pop_motion() gives the wheel-speed MotionEstimates; flush() = last partial window.
- v2x_runner.py V2XPhysicsDomain (WP7 re-creation of the WP5 S6 physics-only recipe; fit / save / load JSON) + V2XRunner (per message, bounded context table; counts tie_events / out_of_order).
- cross_runner.py CrossObject (SigmaModels + WhichDomainLies, JSON) + CrossRunner: push(MotionEstimate of gps / lidar / can / imu) or push({"t","r","v"}) at residual level; keeps whole source history (bit-exact).
- placeholder_runners.py LidarInterimRunner (WP3 S1 retrained v2 baseline, status "interim") + LidarInterimModel; NetworkRunner (status "placeholder"; optional adapter to NetworkDomain.score_stream).

## Key numbers (validation, this loaded machine; details in S1_tables.md)
- Exactness: 0 mismatches, max score diff 0.0 in all domains (GPS 210 runs, CAN 6 captures, V2X 4 blocks / 12 classes, cross 360 + 9 runs, LiDAR 34 scans).
- Latency median / p99 ms: GPS fix 31.6 / 89.2; CAN frame 0.0032 / 0.0084 (amortised 0.044), CAN window 96 / 212; V2X message 20.7 / 59.8; cross step 6.3 / 15.9; LiDAR interim 32.1 / 59.6; bus publish 7 us.

## Binding decisions / conventions
- Runners wrap FROZEN code only; no file of another WP was changed. Exactness is tested against the frozen batch code, never assumed.
- Objects created by WP7 (not frozen files of their owners): results/WP7/frozen_v2x (32 MB, NOT in git: regenerate with tools/WP7_S1_v2x_fit.py), frozen_cross (in-sample runtime object, NOT the WP6 verdict model), frozen_lidar_interim.
- Interim / placeholder labels travel in Evidence.details["status"] and BusRecord.status.

## Pitfalls
- Latency of GPS / CAN / V2X grows with the stream so far (prefix re-score): upper bound only. Quote it with the growth tables.
- ECDF scores are step functions: a 1e-13 difference in z can move a score by 1/n. Keep the full source history in the cross aligner for bit-exactness.
- v2x.l3.birth_density counts equal-timestamp births that arrive later (non-causal at ties); VeReMi val has none. Check ties on new data (runner.tie_events).
- Machine is shared: repeat latency runs, report the spread; run the five tools one after the other (tools/WP7_S1_run_all.sh).
- Files with long docstrings: write with the editor tool, not bash heredocs.

## File map
- system/*.py, tests/system/test_{bus_runner,cross_runner,v2x_runner,placeholder_runners,gps_can_runners}.py (21 tests).
- tools/WP7_S1_{gps,can,v2x,cross,lidar}.py (stream vs batch + latency), WP7_S1_{v2x,lidar,cross}_fit.py, WP7_S1_bus.py, WP7_S1_report.py, WP7_S1_lib.py, WP7_S1_run_all.sh.
- results/WP7/S1_*.json, S1_tables.md, frozen_*/, logs/. reports/WP7_S1.md, reports/REQUEST_WP7_incremental_entry_points.md.
