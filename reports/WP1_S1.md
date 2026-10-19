# WP1 S1: Data layer, unified GPS stream and attack generator

Date: 2026-10-19    Worker: sonnet (WP1)

## Goal of the step
One table format (`gps/stream.py`) for KITTI OXTS, AV-GPS and UAV data; attack generator with the four v2 attacks plus a Doppler-consistent trajectory spoof and a meaconing delay; v2 split; B2 reproduced from the new stream.

## Acceptance rule (notes/WP1_gps.md, "2026-10-19 S1", written before any result; two amendments to the meaconing profile are logged there, made after unit tests and before the data run)
1 tests pass; 2 B2 on the new stream (v2 attacks) equals WP0 S3 exactly (rows 7910/23859/2850, runs 350/1080/150, FA 0.015803, detection per attack, tp/fp/fn/tn, threshold 6.658872); 3 the extended stream keeps the v2 runs bit-identical; 4 Doppler spoof: median |reported velocity - central difference of reported track| on attacked rows <= 1.5 x clean rows, naive drift >= 2 x; 5 meaconing: track = truth at t - tau, velocity = derivative of the track, speed change per second <= max(clean 99.9th pct, 3 m/s^2), clock offset = -tau; 6 severity ranges explicit; 7 splits by group.

## What was done
- `gps/stream.py`: loaders (KITTI OXTS, AV-GPS, UAV PX4), 1 Hz resampling on real timestamps, receiver noise, the six attacks, split constants, `splits_dict`. Copied from v2 `gps/kitti_external.py`, `gps/features.py`, `gps/uav_case_study.py`; nothing imported.
- `tools/WP1_S1_b2.py`: builds the streams, B2 layer (copy of WP0), reproduction check, attack checks, summaries.
- `tests/gps/test_stream.py` (10 tests); full suite 29 passed.
- Outputs in `results/WP1/`: `S1_b2_reproduction.json`, `S1_attack_checks.json`, `S1_stream_summary.json`, `S1_b2_extended_val_only.{json,md}`, `S1_b2_extended_table.md`, `splits.json`, `logs/S1_b2.log`.

### Stream columns (one row per fix, 1 Hz)
`t, lat, lon, x, y` (reported, local ENU m), `x_true, y_true` (KITTI only), `vel_n, vel_e, speed_gps, course` (receiver Doppler velocity and course), `odo_speed, heading, yaw_rate, acc_n, acc_e` (vehicle sensors, never attacked), `numsats, hdop, fix_type, clock_offset` (receiver fields; `clock_offset` = reported GPS time - true time, s), `label, attack, onset, onset_t, severity, k, run, drive, part`. NaN when a source lacks a field.

### Sources
- KITTI (D04): 23 drives, 10 phases, runs `[clean] + 4 v2 attacks (x2 in train) [+ 2 new attacks]`. Split TEST 0001 0005 0095 0039 0079 0028 0052, VAL 0011 0035 0027, TRAIN the other 13 (by drive). Simulation parameters from v2, kept: receiver noise AR(1) phi 0.9 sigma 1 m per axis (OXTS is RTK, otherwise every detector looks perfect), odometry = OXTS forward speed x (1 + N(0, 2%)) per run + N(0, 0.05 m/s) per fix, IMU heading = yaw + N(0, 2 deg). Added (per-run seeded generator, so v2 draws are untouched): Doppler velocity noise N(0, 0.05 m/s) per axis, IMU acceleration (nav frame) N(0, 0.05 m/s^2), gyro N(0, 0.005 rad/s). The Doppler velocity of v2 runs is the true velocity plus that noise.
- AV-GPS (D03): 15 sessions (contiguous blocks of one label; v2 definition), time = row counter (Clock Time not parseable on every row). Test = files 2 and 3 (6 sessions), val = 3 file-1 sessions, train = 6 sessions. No Doppler velocity, no IMU acceleration (NaN). Known artefact kept in the docstring: numsats separates the classes, do not use it as a detector.
- UAV (D06): 3 live flights (benign 248 fixes, jamming 224, spoofing 138), IMU specific force rotated to NED, gravity added back, averaged over the second before each fix; no odometry. Labels: spoofing flight t >= 117 s (v2 case study, approximate, 20 fixes). All three flights are test (case study).

## Attack models (what a real attacker could and could not do)
The attacker controls the GNSS signal only. It cannot change wheel odometry, IMU, gyro or heading. Reported position p_rep, velocity v_rep, course and clock are what the receiver outputs. Onset index k0 uniform in [3, n-3]. n_k is the AR(1) receiver noise (v2). u = (cos th, sin th), th uniform.
- v2 drift: p_rep = p + n + s (t - t0) u, s in [0.2, 2.0] m/s. accel_drift: s (t - t0)^2 / 2 u, s in [0.05, 0.5] m/s^2. jump: s u from k0, s in [5, 50] m. freeze: p_rep(k) = p_rep(k0) for k >= k0. These change position only; the Doppler velocity stays true (a naive spoofer).
- doppler_spoof (new): velocity offset w(t) = w_max min((t - t0)/T, 1) u, T = w_max / a, a = 0.4 m/s^2 (the fake track is pulled away at a plausible 0.4 m/s^2), w_max in [0.2, 3.0] m/s. Position offset o_k = o_{k-1} + (w_k + w_{k-1}) dt / 2. Reported: p_rep = p + n + o, v_rep = v + n_v + w. So the offset track's derivative equals the velocity offset exactly (tested), and v_rep is consistent with the reported track up to receiver noise. Course comes from the reported position step (v2 rule). The attacker is assumed to know the vehicle's real position and velocity (a tracking receiver); it cannot know the odometry, so the offset still shows against odometry and IMU.
- meaconing (new): the receiver reports the solution of an earlier time (a record-and-rebroadcast chain whose latency grows): p_rep(t) = P(t - tau(t)) + n, v_rep(t) = V(t - tau(t)) (1 - tau'(t)) + n_v, clock_offset = -tau(t). tau(tr) = tau_max (3u^2 - 2u^3), u = min(tr/T, 1), T = 1.5 tau_max / 0.2, so tau' = 6 tau_max u (1-u)/T is 0 at both ends and peaks at 0.2 s/s: the apparent speed is at least 0.8 v, with no step. tau_max in [0.5, 3.0] s. The track is the vehicle's own past track, so it stays kinematically smooth and v_rep is its exact derivative (chain rule, tested on circular truth). The position error at the plateau is v tau_max (about 30 m at 10 m/s and 3 s): short delays at low speed are below the 1 m receiver noise and cannot be detected by position consistency. Limit: a real repeater adds a geometry-dependent offset, not a clean time shift; this is a stale-solution model, stated as such.

## Results (copied from results/WP1/S1_b2_reproduction.json and S1_attack_checks.json)
B2 on the new stream, v2 attacks, calibrated on train+val normal rows as in WP0 S3 (single test pass):

| quantity | WP0 S3 | new stream |
|---|---|---|
| rows test/train/val; runs | 7910/23859/2850; 350/1080/150 | identical |
| false alarms, clean test runs | 0.015803 | 0.015803 |
| row detection drift / accel / jump / freeze | 0.3364 / 0.4582 / 0.7194 / 0.8658 | identical (`matches_wp0_s3: true`, every comparison OK) |
| run detected | 0.3857 / 0.4286 / 1.0 / 0.8857 | identical |
| tp / fp / fn / tn | 1770 / 67 / 1151 / 4922 | identical |
| threshold (raw equivalent) | 6.658872 | 6.658872 (v2 interpolated 6.657975, 0.0009 m, no decision changes) |

`matches_v2_json: true`; `extended_keeps_v2_runs_identical: true`.

Attack physics on the extended stream (median over attacked rows of |v_rep - central difference of reported track|, m/s; clean rows 0.384):

| attack | median | ratio to clean |
|---|---|---|
| doppler_spoof | 0.394 | 1.03 |
| meaconing | 0.394 | 1.03 |
| jump | 0.428 | 1.11 |
| drift | 0.972 | 2.53 |
| accel_drift | 1.516 | 3.95 |
| freeze | 7.44 | 19.4 |

Meaconing max speed change per second on attacked rows 2.59 m/s^2 (clean test 99.9th pct 1.88; bound max(1.88, 3.0) = 3.0).
Acceptance: MET (criteria 1-7).

## Ablation row (baseline: B2 alone on the extended stream; this step adds no layer)
B2 calibrated on the VAL drives only (v3 protocol, threshold 7.49 m), test once: AUC 0.847, false alarms on test normal 0.70%; row detection drift 29.8, accel_drift 43.7, jump 70.8, freeze 86.2, doppler_spoof 44.3, meaconing 28.7 %. With the v2 calibration (train+val rows): run-level detected doppler_spoof 0.414 (median delay 6 s), meaconing 0.471 (median 5 s). The new attacks are about as hard for B2 as the slow drifts; these are baselines for S3-S5 to beat.

## Problems, surprises, open questions
- First delay profile (linear ramp then cap) left a step in apparent speed at the cap; found by a unit test, replaced by the smoothstep before any data run (logged in the notes).
- AV-GPS has no Doppler or IMU acceleration, UAV has no odometry; layers needing them apply to KITTI only (or the sources that have them). The attack generator is KITTI-only (needs the true track).
- UAV label onset is the v2 estimate (117 s), not a dataset label.
- No blocking question. Suggest S2 does not use `numsats` on AV-GPS.

## Proposed next step
S2 L1 receiver sanity rules on this stream.
