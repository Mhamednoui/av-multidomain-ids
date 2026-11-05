"""Reference-health gate of v3.1 + S8 (WP8 S8): a SENSOR-HEALTH signal, not an attack verdict.

Purpose: the K vehicle block (GPS domain, cross-domain checks, LiDAR layers L2c / L2d) takes its inputs from the navigation unit record (OXTS: position, velocity, heading, ego pose). When the unit
itself reports that its solution is degraded (horizontal position accuracy / velocity accuracy far outside what the detectors noise models assume) the checks that compare other sources with that
solution cannot be evaluated: they would report the unit's own error as an attack. The gate marks those ticks / scans as "reference degraded" and the dependent verdicts are withheld (and published as
`sensor_health`, with the reported accuracies as reason). It uses only fields the receiver publishes, no labels, no detector score.
Rule (pre-registered in notes/WP8_S8.md section 3, thresholds 3 x the largest value on any v3-train / V31_val drive, rounded): a frame is degraded if pos_accuracy > POS_ACC_MAX (5.0 m) or
vel_accuracy > VEL_ACC_MAX (0.5 m/s) or either field is not finite. A 1 Hz tick (window (t - 1, t]) is degraded if one frame in the window is; a LiDAR scan if its OXTS frame is.
Effects (functions below, applied to saved tick / scan sources by tools/WP8_S8_sim.py; the frozen detectors, ECDFs, thresholds, combiner and correlator are not touched):
GPS domain: score 0, alarm False. Cross domain: score 0, edges 0, alarm False, blame None, observed False. LiDAR: L2c (background) and L2d (tracking) use the OXTS pose and are masked out of the
union (stat = max over L1, L2a); L1 and L2a stay. CAN, network, V2X: untouched.
Exploit surface: the accuracy fields are receiver output; a spoofer that controls the receiver can claim poor accuracy to blind the GPS-based checks. See reports/WP8_S8.md (attack windows).
Inputs: OXTS fields 23 (pos_accuracy) and 24 (vel_accuracy) per frame (KITTI dataformat), frame times. Outputs: boolean arrays.
"""
from pathlib import Path

import numpy as np

POS_ACC_MAX = 5.0         # m
VEL_ACC_MAX = 0.5         # m/s
POSE_LAYERS = ("L2c", "L2d")
LIDAR_LAYERS = ["L1", "L2a", "L2c", "L2d"]
OXTS_POS_ACC, OXTS_VEL_ACC = 23, 24


def degraded_frames(pos_acc, vel_acc, pos_max=POS_ACC_MAX, vel_max=VEL_ACC_MAX):
    """bool per OXTS frame: the unit's own accuracy estimate is outside what the detectors can test."""
    p, v = np.asarray(pos_acc, float), np.asarray(vel_acc, float)
    return ~np.isfinite(p) | ~np.isfinite(v) | (p > pos_max) | (v > vel_max)


def tick_gate(t_frames, degraded, t_ticks, window=1.0):
    """bool per tick: at least one degraded frame with t in (t_tick - window, t_tick] (causal)."""
    t = np.asarray(t_frames, float)
    bad = np.asarray(degraded, bool)
    tb = t[bad]
    tt = np.asarray(t_ticks, float)
    if not len(tb):
        return np.zeros(len(tt), bool)
    hi = np.searchsorted(tb, tt, side="right")
    lo = np.searchsorted(tb, tt - window, side="right")
    return hi > lo


def read_oxts_health(oxts_data_dir):
    """(t, pos_accuracy, vel_accuracy) of a drive; t = seconds from the first OXTS timestamp (same clock as gps.stream.load_oxts)."""
    import pandas as pd
    d = Path(oxts_data_dir)
    a = np.array([np.loadtxt(f) for f in sorted(d.glob("*.txt"))])
    ts = pd.to_datetime(pd.read_csv(d.parent / "timestamps.txt", header=None)[0])
    t = (ts - ts.iloc[0]).dt.total_seconds().to_numpy()
    return t, a[:, OXTS_POS_ACC], a[:, OXTS_VEL_ACC]


def mask_union(union, raw, gated):
    """LiDAR union statistic with the pose layers masked at gated scans. raw: dict layer -> raw score arrays (float64), gated: bool per scan.
    Returns (stat, score, alarm); identical to union.stat / score / alarm where gated is False."""
    R = union.ranks(raw)
    S = R - union.tau[None, :]
    g = np.asarray(gated, bool)
    for j, lay in enumerate(LIDAR_LAYERS):
        if lay in POSE_LAYERS:
            S[g, j] = -np.inf
    stat = S.max(axis=1)
    return stat, union.cal.transform(stat), stat >= 0.0


def gate_series(s, g):
    """Copy of one K vehicle series dict (tools/WP8_S7_veh.py layout) with the GPS and cross verdicts withheld at gated ticks g (bool per tick)."""
    o = dict(s)
    g = np.asarray(g, bool)
    o["gps_score"] = np.where(g, 0.0, s["gps_score"]).astype(s["gps_score"].dtype)
    o["gps_alarm"] = s["gps_alarm"] & ~g
    o["cross_score"] = np.where(g, 0.0, s["cross_score"]).astype(s["cross_score"].dtype)
    o["cross_alarm"] = s["cross_alarm"] & ~g
    o["cross_layers"] = np.where(g[:, None], 0.0, s["cross_layers"]).astype(s["cross_layers"].dtype)
    o["cross_layer_alarm"] = s["cross_layer_alarm"] & ~g[:, None]
    o["cross_present"] = s["cross_present"] & ~g
    for k in ("blame_A1", "blame_A3", "blame_V3"):
        b = np.array(s[k], object)
        b[g] = None
        o[k] = b
    o["gate"] = g
    return o
