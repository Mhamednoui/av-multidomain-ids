# WP6 cross-domain brief (state at end of S1, 2026-10-22: S1 in REVIEW)

## Current state
- S1 motion witnesses done, report reports/WP6_S1.md, verdicts results/WP6/s1_acceptance.json:
  A1 streams MET, A2 latency MET, A3 sigma honesty on val NOT MET, A4 tests MET (315 pass), A5 API MET,
  A6 ROAD unit 0.01 km/h PLAUSIBLE (not confirmable), comma CAN = 0.990 x GNSS (stable per route).
- Pairs: KITTI gps-lidar (speed, yaw, lateral), gps-can, lidar-can (speed; CAN SIMULATED), gps-imu, imu-lidar
  (yaw); comma2k19 gnss-can, gnss-wheel (speed), gnss-imu (yaw). V2X: other vehicles only (no ego self-report).
- Latency: comma GNSS lags CAN 0.22 s; KITTI LiDAR yaw leads OXTS 0.05 s; others ~0.
- Honest on KITTI val: every gps-lidar pair and gps-imu. Not honest: CAN pairs (scale model), imu-lidar
  (heavy tails), comma (published sigmas 10x too wide; train-fitted conservative 30%).
- Revised design R (R1 linear bias, R2 one-vehicle CAN scale, R4 forward-displacement speed) recommended for S2.

## Binding decisions / conventions
- Grid 1 Hz, quantity = mean over (t-1, t]; inst sources via cumulative trapezoid; gap > 1.5 s drops the point.
- Splits: KITTI = WP1 drive split; comma = by route sorted by date, 13 / 4 / 4.
- Acceptance rules written in notes/WP6_crossdomain.md before results; test once per step.

## Pitfalls
- KITTI val = 3 drives, ~55 grid points per pair: mean-z bounds are noisy.
- WP1 odometry scale model (independent 2% per drive) is unrealistic for one car (real 0.15%).
- comma: "|" in route names -> "_"; read arrays with np.load(allow_pickle=False), python -I for the fetcher.
- comma sensor regimes (gyro 10 vs 100 Hz) change the residual variance 2-4x.

## File map
- crossdomain/: witness.py (core), kitti.py, can_sim.py, comma.py, v2x_self.py, __init__.py (API).
- tools/WP6_S1_*.py: comma_fetch, road_wheel, kitti (build/dev/test), comma (build/dev/test), diag, tables.
- results/WP6/: s1_*.json, s1_tables.md, s1_sigma_models.json (kitti, kitti_R, comma, comma_R), logs/.
- Data: ../data_extra/D22_comma2k19/Chunk_1 (1.31 GB); cache ../data_extra/cache_v3/WP6 (79 MB; rebuild:
  WP6_S1_kitti.py build, WP6_S1_comma.py build).
