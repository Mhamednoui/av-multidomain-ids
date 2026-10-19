"""WP1 S5: assemble reports/WP1_S5.md = narrative (numbers read from the JSON files) + generated tables (results/WP1/S5_tables.md).
Run after tools/WP1_S5_tables.py. From codes_v3/: python tools/WP1_S5_report.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results" / "WP1"
J = lambda n: json.loads((R / n).read_text())
odo, dev, kit, acc, sev = J("S5_odometry.json"), J("S5_dev.json"), J("S5_kitti.json"), J("S5_acceptance.json"), J("S5_severity.json")
P = lambda x, d=1: "n/a" if x is None else f"{100 * x:.{d}f}%"
blocks, cur = {}, None
for b in (R / "S5_tables.md").read_text().split("\n\n"):
    if b.startswith("**"):
        cur = b.split("**")[1]
        blocks[cur] = [b]
    elif cur:
        blocks[cur].append(b)


def get(prefix):
    for k, v in blocks.items():
        if k.startswith(prefix):
            return "\n\n".join(v)
    raise KeyError(prefix)


prim = kit["dev_selection"]["primary_layer_name"]
pl = kit["calibration"]["lodo"]["per_layer"]
vl = kit["calibration"]["valonly"]["per_layer"]
c6rows = ["| harness | calibration | AUC base -> with | detection base -> with | combined FA | best row-level gain (points) | adds? |", "|---|---|---|---|---|---|---|"]
for sch in ("lodo", "valonly"):
    for key, lab in (("primary", f"+ {prim}"), ("seq", "+ gps.cusum_lidar"), ("all_L2d", "+ all 7 L2d layers")):
        a = acc[f"C6_{sch}_{key}"]
        g = a["row_level_gain_points"]
        best = max(g, key=g.get)
        c6rows.append(f"| S4 stack {lab} | {sch} | {a['auc_base']:.3f} -> {a['auc_with']:.3f} | {P(a['det_base'])} -> {P(a['det_with'])} | {P(a['fa_with'], 2)} | {g[best]:+.1f} ({best}) | {'yes' if a['adds'] else 'no'} |")
sevl = ["| attack | severity range | test runs | run-level detected | median attacked fixes |", "|---|---|---|---|---|"]
for a, bl in sev["bins"].items():
    for b in bl:
        sevl.append(f"| {a} | {b['severity_range'][0]} - {b['severity_range'][1]} | {b['runs']} | {P(b['detected'], 0)} | {b['median_attacked_fixes']} |")
rows_acc = [
    ("C1 tests", "133 pass (8 new in tests/gps/test_lidar_odom.py)", "MET"),
    ("C2a odometry translation error <= 2.0% (dev)", f"{acc['C2']['translation_dev_pct']:.2f}% (test {odo['test']['translation_error_pct']:.2f}%)", "MET"),
    ("C2b rotation <= 0.02 deg/m (dev)", f"{acc['C2']['rotation_dev_deg_per_m']:.4f} (test {odo['test']['rotation_error_deg_per_m']:.4f})", "MET"),
    ("C2c median 1 s displacement error <= 0.10 m (dev)", f"{acc['C2']['median_1s_disp_err_dev_m']:.3f} m (test {odo['test']['median_1s_disp_err_m_moving']:.3f})", "NOT MET"),
    ("C3 sigma coverage (2 sigma) >= 90% on test", f"{P(acc['C3']['coverage_test'])} (dev {P(acc['C3']['coverage_dev'])})", "NOT MET (narrow)"),
    ("C4 clean-run FA on test <= 1.5% (LODO) and nested held-out FA <= 1.5%", f"{P(acc['C4']['fa_clean_runs_test_lodo'], 2)} (val-only {P(acc['C4']['fa_clean_runs_test_valonly'], 2)}); nested dev {P(acc['C4']['nested_heldout_fa_dev'], 2)}", "NOT MET (test FA 1.64%)"),
    ("C5 Doppler spoof and meaconing run-level >= 75% (LODO)", f"{P(acc['C5']['doppler_spoof_run_lodo'], 0)} / {P(acc['C5']['meaconing_run_lodo'], 0)} (cusum_dr {P(acc['C5']['reference_cusum_dr']['doppler_spoof'], 0)} / {P(acc['C5']['reference_cusum_dr']['meaconing'], 0)})", "NOT MET"),
    ("C6 L2d adds on top of B2 + L1 + L2a + L2b", f"primary: AUC {acc['C6_lodo_primary']['auc_gain']:+.4f}, FA {P(acc['C6_lodo_primary']['fa_with'], 2)}: no. All 7 L2d layers: AUC {acc['C6_lodo_all_L2d']['auc_gain']:+.4f}, drift +{acc['C6_lodo_all_L2d']['row_level_gain_points']['drift']:.1f} points: yes (LODO); val-only: no", "primary NOT adding; whole L2d family adds under LODO only"),
    ("C7 slow drift", "untestable on KITTI test (no run has 30 s after onset)", "reported only"),
    ("C8 MotionEstimate published, documented, tested", "gps/lidar_odom.motion_estimates, results/WP1/S5_motion_estimates.json", "MET"),
]
acc_tab = "| criterion | value | verdict |\n|---|---|---|\n" + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in rows_acc)

TEXT = f"""# WP1 S5: L2d LiDAR odometry (point-to-plane ICP) as an independent motion witness, MotionEstimate

Date: 2026-10-20    Worker: sonnet (WP1)

## Goal of the step
Build LiDAR odometry from consecutive KITTI velodyne scans (numpy + scipy cKDTree), validate it against the OXTS ground truth, use the 1 s LiDAR displacement (and heading change) as a GPS consistency check that does not depend on the GPS receiver, calibrate it with LODO over the 16 train+val drives at a 1% budget (tie-safe), publish a MotionEstimate per second for WP6, and report the harness ablation on top of B2 + L1 + L2a + L2b.

## Acceptance rule (notes/WP1_gps.md, "2026-10-20 S5", written before any detection result; amendments listed under Deviations)
{acc_tab}

## Data availability
Velodyne scans exist for ALL 23 drives (21 in `../data_extra/kitti_raw`, drives 0001 and 0015 in `../codes/data/Depth`, which the assignment did not count). No drive is without LiDAR; nothing had to be marked "layer not available". Drive 0048 lasts 2.3 s (22 scans): it is in the odometry validation but yields no 1 Hz stream run, so the LODO detection folds are 15 (as in S4, where the "16 drives" were also 15 with runs). Two drives (0017, 0060) are stationary (0.1 m of path), 0052 nearly (8 m): they contribute clean-run false-alarm exposure but almost no odometry segments.

## What was done
- `gps/lidar_odom.py`: voxel grid (0.5 m, range 2.5-60 m), normals by PCA of 8 neighbours, 6-DOF point-to-plane Gauss-Newton (gates 2.0 -> 0.5 m, 20% trimming, constant-velocity start, multi-start for the first pair), pose chaining, 1 s windows, stream features, `motion_estimates()`, `LidarLayer` (v3 Layer, domain gps, layer id L2d). All parameters fixed before any result.
- `gps/lidar_dr.py`: the S4 dead-reckoning branch with LiDAR displacement as odometry (no scale state) + CUSUM, `LidarCusumLayer` (sequential variant).
- `tests/gps/test_lidar_odom.py` (8 tests; suite 133 pass). Tools: `WP1_S5_odom_run.py` (ICP over all drives, Pool(4), cache), `WP1_S5_odometry.py` (validation, sigma fit), `WP1_S5_dev.py` (16 drives only: LODO, nested selection), `WP1_S5_test.py` (the single test pass; dry run on val rows first), `WP1_S5_tables.py`, `WP1_S5_severity.py` (post-hoc diagnostic), `WP1_S5_report.py`.
- Results: `results/WP1/S5_odometry.json`, `S5_dev.json`, `S5_kitti.json`, `S5_acceptance.json`, `S5_severity.json`, `S5_motion_estimates.json`, `S5_tables.md`, harness files `S5_*_{{lodo,valonly}}.json|md`. Odometry cache (gitignored): `results/WP1/cache/lidar_odom_<drive>.npz` (23 files). Logs in `results/WP1/logs/`.
- Cost: about 0.12 s per scan pair (4673 scans in total); all 23 drives in about 7 min with 4 workers; the features and layers then cost seconds, so later steps read the cache.

### The scores (all from the stream columns of `lidar_odom.stream_features`)
- `gps.lidar_resid_W`: |GPS displacement over the last W fixes - LiDAR displacement over the same interval| in metres (W = 1, 3, 10). The LiDAR displacement is rotated to east-north with the compass offset averaged over the window (compass minus LiDAR yaw): the compass is the vehicle's own sensor, so nothing in the check comes from the receiver.
- `gps.lidar_z_W`: the same residual divided by its modelled standard deviation (receiver AR(1) difference with the S3 values, LiDAR relative error 1.9% x path, compass 2 deg/sqrt(n) x path, floor 0.05 m; constants frozen before detection results).
- `gps.lidar_course`: lateral-metre equivalent of |change of GPS course - change of LiDAR direction of travel| (compass-free; 0 below 2 m/s).
- `gps.cusum_lidar`: sequential variant (LiDAR dead-reckoning branch, frozen when suspicious, CUSUM on its innovations).
- Primary L2d = `{prim}`: selected by J (mean of 6 run-level detections + slow drift) nested in LODO: chosen in {dev['nested']['choice_counts'].get('lid_z_1', 0)} of {dev['n_drives']} folds (LODO folds), nested held-out FA {P(dev['nested']['heldout_fa_pooled'], 2)}.

## MotionEstimate published by this step (for WP6)
`gps.lidar_odom.motion_estimates(t_fix, P, tp, quality_ok)` returns one `common.motion.MotionEstimate` per second (`t_fix` = stream times; P, tp = poses and times of the cached odometry; `load_odometry(drive)` gives them). Fields: `t` = end of the second (stream clock = first OXTS timestamp); `source = "lidar"`; `displacement = (dx, dy)` in metres over the last second in the vehicle BODY frame at the start of that second (dx forward, dy left; the contract left the frame open, this choice needs no compass and no GPS; to compare with a GPS or CAN displacement WP6 compares norms, or rotates with a heading it trusts); `speed = |displacement| / 1 s` (m/s); `yaw_rate` = heading change over the second (rad/s, positive left); `sigma` = 1-sigma uncertainty of the speed (m/s) = sqrt(0.0821^2 + (0.0046 x speed)^2), multiplied by 3 when the second contains an ICP fallback (fitted on the 16 dev drives; coverage of 2 sigma: dev {P(odo['dev']['sigma_coverage_2sigma'])}, test {P(odo['test']['sigma_coverage_2sigma'])}, just below the 90% rule on test). Seconds without a full window behind them (t < 1 s) are not published. A ready sample for all 23 drives (phase 0 of the 1 Hz grid) is in `results/WP1/S5_motion_estimates.json`. The LiDAR motion does not depend on the GPS attack, so one MotionEstimate stream serves every attacked variant of a drive.

## Results

{get('LiDAR odometry vs OXTS')}

{get('LiDAR odometry, pooled')}

Reading: the 1.7% translation / 0.008 deg/m is a plain point-to-plane ICP without loop closure or deskewing. The 1 s displacement error median of 0.13 m is larger than the speed error alone (0.065 m/s) would give, so part is cross-track; probable causes (not verified): an uncalibrated yaw offset between the velodyne and the OXTS frame and uncorrected motion distortion inside a scan. Drives 0005, 0020, 0113 (short, slow) and 0035, 0046 are the weak ones; low ICP inlier fractions (0027, 0028: 0.36-0.38, open roads) do not hurt the 1 s displacement much.

### Detection

{get('Development drives (16 train+val), candidates')}

{get('Nested selection')}

{get('KITTI test, LODO')}

{get('KITTI test, val-only')}

{get('FA transfer on test')}

{get('Beat-or-not')}

{get('Detection delay distribution, lodo')}

### Harness ablation (S4 stack = L1 + B2 + L2a EKF NIS + L2b cusum_ekf + cusum_dr; combiner refitted on the calibration drives each time)

{chr(10).join(c6rows)}

Full tables, including every `all-but-one` row and the L2d-alone runs: `results/WP1/S5_tables.md`.

### Why Doppler spoof and meaconing stay near 60% (post-hoc diagnostic, `S5_severity.json`, nothing chosen from it)

{chr(10).join(sevl)}

The LiDAR side is accurate (0.13 m per second) and cannot be dragged: the check never absorbs the attack. What limits detection is the receiver side: differencing a receiver whose error is AR(1) with 1 m sigma leaves 0.45 m per axis of noise on a 1 s displacement, so a velocity offset becomes visible only above about 1.3 m/s. A Doppler-consistent spoof ramps its velocity offset at 0.4 m/s^2 (reaches 1.3 m/s after about 3 s) and many test runs have only 6-7 attacked fixes; spoofs whose final offset is below 1 m/s are seen in {P(sev['bins']['doppler_spoof'][0]['detected'], 0)} of runs, those above 1 m/s in about 70%. Longer windows (W = 3, lid_z_3: Doppler {P(pl['gps.lidar_z_3']['run_detected']['doppler_spoof'], 0)}, meaconing {P(pl['gps.lidar_z_3']['run_detected']['meaconing'], 0)}) average more noise but the AR(1) noise also grows with the window, so there is a plateau. The sequential variant should have gained from accumulation but has a heavy false-alarm tail (below).

### Honest reading of the results
- LiDAR odometry is a working independent witness: with only the receiver-noise limit, `lid_z_1` beats B2 on drift (+23 points), accel drift (+16), Doppler spoof (+19) and meaconing (+13) at equal false alarms, and detects jumps and freezes as well as B2, but it does NOT beat the wheel-odometry dead-reckoning branch cusum_dr (-9 points on drift, -10 on Doppler spoof, equal otherwise), and on top of the full S4 stack the primary layer adds nothing (AUC {acc['C6_lodo_primary']['auc_gain']:+.4f}). The stack already holds a second, partly independent odometry (wheel speed + compass); LiDAR duplicates it.
- Value of independence: under LODO the whole L2d family lifts the stack AUC from {acc['C6_lodo_all_L2d']['auc_base']:.3f} to {acc['C6_lodo_all_L2d']['auc_with']:.3f} and the row-level drift detection by {acc['C6_lodo_all_L2d']['row_level_gain_points']['drift']:+.1f} points at combined FA {P(acc['C6_lodo_all_L2d']['fa_with'], 2)} (rule met via the +5 points clause); with val-only calibration it does not (FA {P(acc['C6_valonly_all_L2d']['fa_with'], 2)}, driven by gps.cusum_lidar). I would not claim more than "marginal gain".
- `gps.cusum_lidar` is a failure as a calibrated layer: clean-run FA {P(pl['gps.cusum_lidar']['false_alarm_clean_runs'], 2)} on test (LODO) and {P(vl['gps.cusum_lidar']['false_alarm_clean_runs'], 2)} (val-only) against a dev held-out estimate of {P(kit['calibration']['lodo']['lodo_transfer']['gps.cusum_lidar']['lodo_heldout_fa_pooled'], 2)}: a few clean runs where the ICP is momentarily wrong latch the freeze and the CUSUM runs away (the S4 branch survived this thanks to its learned scale and 2 deg compass model; here the tighter LiDAR model is less forgiving). Not recommended; kept in the tables for completeness.
- `gps.lidar_course` (compass-free heading change) is weak (AUC 0.558): below 2 m/s it is silent and above it the GPS course noise is large.
- Slow drift (< 0.5 m/s within 30 s): untestable on KITTI test (supervisor decision S4); lid_z_1 detects {P(pl[prim]['slow_drift_lt_0.5_within_30s']['rate'], 0)} of the 14 runs inside the available window.

## Deviations from the written plan (all before any test number; details in notes/WP1_gps.md)
1. Standardised variant lid_z_W added to the candidates after the first look at clean residual quantiles (dev only); constants frozen.
2. Sequential layer (gps/lidar_dr.py) added after the first dev result showed the instantaneous residual below the C5 target; selection among all candidates nested in LODO as written.
3. Bug found on dev diagnostics: the first scan pair of each drive had no previous motion, the identity start converged to a wrong minimum at speed (first second 6 m instead of 14 m). Fixed with a multi-start for the first pair only; odometry recomputed for all 23 drives (dev and test) with the same code; the earlier numbers (translation 1.88% dev) were superseded. ALPHA_FIXES 5 -> 20 and the sigma constants updated from the corrected run (dev data only).
4. The "21 of 23 drives" premise was wrong: 23 of 23 have velodyne.

## Problems, surprises, open questions
- Question 1 (frame): `MotionEstimate.displacement` is in the body frame (forward, left) of the start of the second. The contract does not fix the frame; please confirm for WP6 or ask for east-north (then it needs a trusted heading).
- Question 2 (C5): the 75% target for Doppler spoof / meaconing is not reachable with a per-second test against a simulated receiver with 1 m AR(1) noise. Is the target to be kept for S8, or replaced by a delay-based statement?
- The receiver noise (1 m AR(1) on top of RTK) is the S1 simulation; a real civil receiver with Doppler-derived velocity would be less noisy in displacement over 1 s (velocity-based checks) than the position differencing used here. The check still uses position only.
- Odometry: no extrinsic velodyne-to-IMU calibration and no scan deskewing (both would likely reduce the 0.13 m 1 s error); both left out on purpose to stay within the step. KITTI GT is OXTS, not a separate ground truth.
- The harness combiner is refitted on the calibration drives each time; with LODO the combiner is fitted on pooled 16-drive scores, not out-of-fold (as in S4).

## Proposed next step
S6 L2e map matching on OSM drivable roads (S4 note: filter footways). Not started.
"""

(ROOT / "reports" / "WP1_S5.md").write_text(TEXT)
print("written", len(TEXT))
