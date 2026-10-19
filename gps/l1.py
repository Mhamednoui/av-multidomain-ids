"""WP1 S2: L1 receiver sanity rules for GPS, as v3 Layers (domain "gps", layer "L1", kind "rule").

Purpose: cheap checks that need no model and no attack data. Two families.
 (a) Physical-limit rules: a quantity measured from the reported fixes (speed, longitudinal / lateral
     acceleration, jerk, yaw rate vs minimum turn radius) or from receiver fields (fix type, satellites, HDOP,
     clock rate) divided by a PHYSICAL limit (LIMITS below, each with a source). raw >= 1 means the limit is
     violated. At the "physical operating point" the alarm is raw >= 1: no fitted threshold. The harness also
     uses the calibrated 0..1 score (ECDF of validation normal raw values) for AUC / budget operating points.
 (b) Data-driven rules: Doppler-vs-position consistency and one-step jumps of satellites / HDOP / noise level /
     jamming indicator. Their threshold is set on validation normal samples only (Layer.calibrate, tie-safe).

Inputs: a GPS stream table (gps/stream.py columns; UAV additionally `noise_per_ms`, `jamming_indicator` via
attach_uav_extras). `l1_features(df)` computes the per-fix quantities group by group (column `run`), strictly causal
(row k uses rows <= k), so the same table can be sliced by the harness. Outputs: Evidence list per rule.
Missing fields are NaN and give raw 0 ("not evaluable" is decided per dataset by COVERAGE, not per row).

Physical limits (a passenger car on a public road; chosen before any S2 result, never fitted):
  V_MAX   70 m/s   (252 km/h): the 250 km/h electronic limit of the German premium manufacturers (VDA voluntary
                   commitment); faster than any road AV drives.
  A_LONG  1.3 g    longitudinal acceleration / braking: tyre-road friction mu <= ~1.0-1.2 braking (Wong, Theory of
                   Ground Vehicles, 4th ed., ch. 3; Rajamani, Vehicle Dynamics and Control), 1.3 g allows the
                   quickest production car launches (0-60 mph in ~2.1 s = 1.3 g, manufacturer data).
  A_LAT   1.2 g    lateral acceleration: road-legal sport tyres on a skidpad reach 1.0-1.2 g (same sources).
  J_MAX   50 m/s^3 jerk: engineering estimate, not a literature value: full braking force (1.3 g) cannot build up in
                   less than ~0.25 s (hydraulic actuator rise time, Rajamani ch. 11 order of magnitude). Comfort
                   limits (~2 m/s^3, ISO 2631 based) are NOT used: they would flag normal hard driving.
  R_MIN   5 m      minimum turning radius of a passenger car (Ackermann geometry; curb-to-curb circle 10-12 m).
                   yaw rate <= v / R_MIN. Only evaluated when both speeds >= YAW_MIN_SPEED (course is noise at low speed).
  SAT_MIN 4        a 3D fix has four unknowns (x, y, z, receiver clock) -> at least four satellites.
  HDOP    5        HDOP above 5 is "moderate / poor" geometry (Langley, "Dilution of precision", GPS World 10(5), 1999).
  FIX_MIN 3        fix_type 3 = 3D fix (u-blox UBX-NAV-PVT / PX4 vehicle_gps_position convention).
  CLOCK   1e-3 s/s receiver clock offset changes by more than 1 ms per second: a TCXO drifts by a few us/s
                   (ppm level), only a 1 ms receiver clock reset or a spoofer / repeater time shift does more.
Limitations: the limits are bounds, not typical values, so at 1 Hz sampling they only fire on gross inconsistency
(jumps, impossible dynamics, glitches). Slow drifts and Doppler-consistent spoofs stay inside them (that is expected;
the rule is useful because it does not false-alarm, not because it detects those).

Reference: ARCHITECTURE.md sections 2-4; RULES.md section 5; S1 report for the stream definition.
"""
import numpy as np
import pandas as pd

from common.layer import Layer
from gps import stream as S

G = S.G
LIMITS = {
    "V_MAX": 70.0,
    "A_LONG": 1.3 * G,
    "A_LAT": 1.2 * G,
    "J_MAX": 50.0,
    "R_MIN": 5.0,
    "YAW_MIN_SPEED": 3.0,
    "DIR_MIN_SPEED": 0.5,
    "SAT_MIN": 4.0,
    "HDOP_MAX": 5.0,
    "FIX_MIN": 3.0,
    "CLOCK_RATE": 1e-3,
}

# raw feature column -> (layer name, kind of threshold, one-sentence reason)
RULES = {
    "r_speed": ("gps.max_speed", "physical", "Reported speed exceeds what a road vehicle can do ({raw:.2f} x the limit)."),
    "r_long": ("gps.long_accel", "physical", "Longitudinal acceleration of the reported track exceeds tyre-friction limits ({raw:.2f} x the limit)."),
    "r_lat": ("gps.lat_accel", "physical", "Lateral acceleration of the reported track exceeds tyre-friction limits ({raw:.2f} x the limit)."),
    "r_jerk": ("gps.jerk", "physical", "Jerk of the reported track exceeds what brakes and engine can produce ({raw:.2f} x the limit)."),
    "r_yaw": ("gps.yaw_rate", "physical", "Course changes faster than the minimum turn radius allows ({raw:.2f} x the limit)."),
    "r_fix": ("gps.fix_invalid", "physical", "Receiver reports no 3D fix."),
    "r_sat_low": ("gps.sat_low", "physical", "Fewer than four satellites in use."),
    "r_dop": ("gps.hdop_high", "physical", "HDOP above 5 (poor geometry)."),
    "r_clock": ("gps.clock_jump", "physical", "Receiver clock offset changed faster than any oscillator drifts ({raw:.2f} x the limit)."),
    "e_velpos": ("gps.vel_pos_consistency", "data", "Reported Doppler velocity and the reported position steps disagree by {raw:.2f} m/s."),
    "d_sat": ("gps.sat_jump", "data", "Number of satellites in use changed by {raw:.0f} in one second."),
    "d_hdop": ("gps.hdop_jump", "data", "HDOP changed by {raw:.2f} in one second."),
    "d_noise": ("gps.noise_jump", "data", "Receiver noise level changed by {raw:.0f} in one second."),
    "d_jam": ("gps.jam_ind_jump", "data", "Jamming indicator changed by {raw:.0f} in one second."),
}
KINEMATIC = ["r_speed", "r_long", "r_lat", "r_jerk", "r_yaw"]
RECEIVER_PHYS = ["r_fix", "r_sat_low", "r_dop", "r_clock"]
RECEIVER_JUMP = ["d_sat", "d_hdop", "d_noise", "d_jam"]

# Which rules can be evaluated on which dataset, and why not otherwise (stated before the results).
COVERAGE = {
    "kitti": {
        "evaluated": KINEMATIC + ["e_velpos"],
        "not_evaluated": {
            "r_fix": "fix_type is a constant written by the stream simulator (OXTS is RTK, no fix field)",
            "r_sat_low": "numsats is the real OXTS count but the attack simulator never changes it",
            "r_dop": "hdop is a constant written by the stream simulator",
            "r_clock": "clock_offset exists only because our meaconing generator writes it (circular)",
            "d_sat": "see numsats", "d_hdop": "see hdop",
            "d_noise": "no noise / AGC field in OXTS", "d_jam": "no jamming indicator in OXTS"},
    },
    "avgps": {
        "evaluated": list(KINEMATIC),
        "artefact_only": ["r_sat_low", "r_dop", "d_sat", "d_hdop"],
        "not_evaluated": {
            "e_velpos": "no Doppler velocity in AV-GPS",
            "r_fix": "no fix type field", "r_clock": "Clock Time not parseable on every row",
            "d_noise": "no noise / AGC field", "d_jam": "no jamming indicator"},
    },
    "uav": {
        "evaluated": ["r_fix", "r_sat_low", "r_dop", "d_sat", "d_hdop", "d_noise", "d_jam", "e_velpos"],
        "not_evaluated": {
            "r_clock": "time_utc_usec is 0 in the spoofing and jamming flights",
            "kinematic": "car limits do not describe a multirotor; no platform limits are cited, so not applied"},
    },
}


def attach_uav_extras(uav):
    """Add `noise_per_ms` and `jamming_indicator` (PX4 vehicle_gps_position; u-blox noisePerMS / jamInd, the AGC
    stand-ins: the AGC counter itself is not in the log) to the UAV stream. Rows align with the GPS topic rows."""
    out = []
    for name, folder in S.UAV_FLIGHTS.items():
        g = S._uav_topic(folder, "vehicle_gps_position")
        f = uav[uav["run"] == f"uav/{name}"].copy()
        assert len(f) == len(g)
        f["noise_per_ms"] = g["noise_per_ms"].to_numpy(float)
        f["jamming_indicator"] = g["jamming_indicator"].to_numpy(float)
        out.append(f)
    return pd.concat(out)


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def _nan0(a):
    return np.nan_to_num(np.asarray(a, dtype=float), nan=0.0, posinf=1e12)


def _group_features(g):
    n = len(g)
    t = g["t"].to_numpy(float)
    dt = np.r_[np.nan, np.diff(t)]
    dt = np.where(dt > 1e-6, dt, np.nan)
    xy = g[["x", "y"]].to_numpy(float)
    vp = np.full((n, 2), np.nan)
    vp[1:] = np.diff(xy, axis=0) / dt[1:, None]
    vd = g[["vel_e", "vel_n"]].to_numpy(float)
    L = LIMITS
    out = {}
    sp = [np.hypot(*s.T) for s in (vp, vd)]
    out["r_speed"] = _nan0(np.fmax(sp[0], sp[1]) / L["V_MAX"])
    rl, rt, rj, ry = [], [], [], []
    for s in (vp, vd):
        a = np.full((n, 2), np.nan)
        a[1:] = (s[1:] - s[:-1]) / dt[1:, None]
        mean = np.full((n, 2), np.nan)
        mean[1:] = (s[1:] + s[:-1]) / 2
        mn = np.hypot(*mean.T)
        u = mean / np.where(mn > L["DIR_MIN_SPEED"], mn, np.nan)[:, None]
        am = np.hypot(*a.T)
        along = np.where(np.isnan(u[:, 0]), am, np.abs((a * u).sum(1)))        # direction unknown -> all counted as longitudinal
        lat = np.where(np.isnan(u[:, 0]), 0.0, np.abs(a[:, 0] * u[:, 1] - a[:, 1] * u[:, 0]))
        rl.append(along / L["A_LONG"]); rt.append(lat / L["A_LAT"])
        j = np.full(n, np.nan)
        j[2:] = np.hypot(*((a[2:] - a[1:-1]) / dt[2:, None]).T)
        rj.append(j / L["J_MAX"])
        sm = np.hypot(*s.T)
        course = np.arctan2(s[:, 0], s[:, 1])
        dc = np.r_[np.nan, np.abs(_wrap(np.diff(course)))]
        vm = np.r_[np.nan, (sm[1:] + sm[:-1]) / 2]
        ok = np.r_[False, (sm[1:] >= L["YAW_MIN_SPEED"]) & (sm[:-1] >= L["YAW_MIN_SPEED"])]
        w_max = vm / L["R_MIN"]
        ry.append(np.where(ok, (dc / dt) / np.where(w_max > 0, w_max, np.nan), 0.0))
    for key, lst in (("r_long", rl), ("r_lat", rt), ("r_jerk", rj), ("r_yaw", ry)):
        out[key] = _nan0(np.fmax(lst[0], lst[1]))
    vmid = np.full((n, 2), np.nan)
    vmid[1:] = (vd[1:] + vd[:-1]) / 2
    out["e_velpos"] = _nan0(np.hypot(*(vp - vmid).T))
    fix = g["fix_type"].to_numpy(float)
    out["r_fix"] = np.where(np.isnan(fix), 0.0, (fix < L["FIX_MIN"]).astype(float))
    ns = g["numsats"].to_numpy(float)
    out["r_sat_low"] = _nan0(np.maximum(0.0, L["SAT_MIN"] - ns))
    out["r_dop"] = _nan0(g["hdop"].to_numpy(float) / L["HDOP_MAX"])
    ck = g["clock_offset"].to_numpy(float)
    out["r_clock"] = _nan0(np.r_[np.nan, np.abs(np.diff(ck))] / dt / L["CLOCK_RATE"])
    for col, src in (("d_sat", "numsats"), ("d_hdop", "hdop"), ("d_noise", "noise_per_ms"), ("d_jam", "jamming_indicator")):
        v = g[src].to_numpy(float) if src in g.columns else np.full(n, np.nan)
        out[col] = _nan0(np.r_[np.nan, np.abs(np.diff(v))])
    return pd.DataFrame(out, index=g.index)


def l1_features(df):
    """Per-fix L1 quantities for every run of `df` (rows of one run must be in time order). Causal."""
    parts = [_group_features(g) for _, g in df.groupby("run", sort=False)]
    return pd.concat(parts).loc[df.index]


class L1Rule(Layer):
    """One L1 rule over a feature column from l1_features. Physical rules alarm at raw >= 1 (the written limit);
    their calibrated score (ECDF of validation normal raw values) serves AUC / budget operating points."""
    domain = "gps"
    kind = "rule"
    layer_id = "L1"

    def __init__(self, column):
        super().__init__()
        self.column = column
        self.name, self.mode, self._why = RULES[column]
        self.physical = self.mode == "physical"

    def raw_scores(self, samples):
        return _nan0(samples[self.column].to_numpy())

    def reasons(self, samples, raw, alarm):
        return [self._why.format(raw=r) for r in raw]

    def score(self, samples):
        ev = super().score(samples)
        if self.physical:
            for e in ev:
                e.alarm = e.details["raw"] >= 1.0
                e.reason = self._why.format(raw=e.details["raw"]) if e.alarm else ""
        return ev


def make_rules(columns):
    return [L1Rule(c) for c in columns]
