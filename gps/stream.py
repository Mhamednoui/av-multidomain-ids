"""GPS unified stream (WP1 S1): one table format for every GPS data source + the attack generator.

Purpose: every WP1 layer (rules, EKF, CUSUM, LiDAR odometry, map matching, learned models) reads the
same DataFrame, whatever the source (KITTI OXTS tracks, AV-GPS sessions, UAV PX4 flights).
Inputs: KITTI raw OXTS (D04), AV-GPS-Dataset (D03), UAV live flights (D06).
Outputs: DataFrames with the columns of COLUMNS (NaN when a source lacks the field), one row per
GPS fix (1 Hz), grouped by `run` (= group id: KITTI run, AV-GPS session, UAV flight).

Copied from ../codes_v2 (nothing imported): gps/kitti_external.py (load_oxts, resample_1hz,
receiver_noise, attack_offset, track), gps/features.py (AV-GPS sessions), gps/uav_case_study.py
(UAV topics, quaternion rotation). The KITTI generation keeps the v2 random draws in the v2 order,
so the four v2 attacks are bit-identical to v2 / WP0 S3 (tested via tools/WP1_S1_b2.py).

Documented simulation parameters (from v2, kept):
- KITTI OXTS is RTK (cm level): receiver noise AR(1) phi 0.9, sigma 1 m per axis is added to the
  reported position (a civil receiver's multipath / atmosphere wander, correlated over ~10 s).
- Wheel odometry: per-run scale error N(0, 2%) and per-fix noise N(0, 0.05 m/s) on the OXTS forward speed.
- IMU heading: OXTS yaw + N(0, 2 deg) per fix (compass-like).
Added in S1 (not used by B2): Doppler velocity noise N(0, 0.05 m/s) per axis, IMU acceleration noise
N(0, 0.05 m/s^2) per axis, gyro noise N(0, 0.005 rad/s) (per-run generator, so they never change the
v2 draws).

ATTACKS (reported = what the receiver outputs; the odometry, IMU and heading are never attacked,
a GPS spoofer cannot touch the vehicle's own sensors). Equations in reports/WP1_S1.md.
v2 (position-only, naive): drift, accel_drift, jump, freeze. The Doppler velocity stays TRUE, which is
exactly what a naive spoofer leaves inconsistent.
New: doppler_spoof (position AND Doppler velocity follow the fake track) and meaconing (the receiver
reports the solution of an earlier time: record-and-rebroadcast with a growing latency).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import DATA, DATA_EXTRA, SEED

M_PER_DEG = 111_320.0
G = 9.80665

COLUMNS = [
    "t", "lat", "lon", "x", "y", "x_true", "y_true",       # time (s), reported position, local ENU metres
    "vel_n", "vel_e", "speed_gps", "course",               # receiver velocity (Doppler), course (deg)
    "odo_speed", "heading", "yaw_rate", "acc_n", "acc_e",  # odometry m/s, IMU compass deg, gyro rad/s, accel m/s^2 (nav frame)
    "numsats", "hdop", "fix_type", "clock_offset",         # receiver fields; clock_offset = reported GPS time - true time (s)
    "label", "attack", "onset", "onset_t", "severity",     # label 1 from onset index on
    "k", "run", "drive", "part",                           # fix index in run, group id, source group, split part
]

# ----- KITTI (D04) ---------------------------------------------------------------------------
SCENE = {"0001": "city", "0002": "city", "0005": "city", "0011": "city", "0013": "city", "0017": "city",
         "0048": "city", "0060": "city", "0095": "city", "0106": "city", "0113": "city",
         "0019": "residential", "0020": "residential", "0035": "residential", "0039": "residential",
         "0046": "residential", "0079": "residential",
         "0015": "road", "0027": "road", "0028": "road", "0029": "road", "0052": "road", "0070": "road"}
TEST = ["0001", "0005", "0095", "0039", "0079", "0028", "0052"]
VAL = ["0011", "0035", "0027"]
PHASES = 10
ATTACKS_V2 = ["drift", "accel_drift", "jump", "freeze"]
ATTACKS_NEW = ["doppler_spoof", "meaconing"]

# Attack severity ranges (explicit; see report). Units: m/s, m/s^2, m, s.
SEV = {
    "drift": (0.2, 2.0),            # constant pull-off speed (m/s), v2
    "accel_drift": (0.05, 0.5),     # pull-off acceleration (m/s^2), v2
    "jump": (5.0, 50.0),            # step offset (m), v2
    "freeze": (0.0, 0.0),           # position held at the onset fix, v2
    "doppler_spoof": (0.2, 3.0),    # final velocity offset w_max (m/s)
    "meaconing": (0.5, 3.0),        # final delay tau_max (s)
}
DOPPLER_ACCEL = 0.4                 # m/s^2: pull-off acceleration of the velocity offset (<< 1 g, plausible)
TAU_RATE = 0.2                      # s/s: peak growth of the delay (reported speed >= (1 - 0.2) v)

VEL_SIGMA, ACC_SIGMA, GYRO_SIGMA = 0.05, 0.05, 0.005


def part_of(d):
    return "test" if d in TEST else "val" if d in VAL else "train"


def oxts_dir(d):
    name = f"2011_09_26_drive_{d}_sync"
    root = DATA / "Depth" if d in ("0001", "0015") else DATA_EXTRA / "kitti_raw"
    return root / name / "2011_09_26" / name / "oxts" / "data"


def load_oxts(d):
    a = np.array([np.loadtxt(f) for f in sorted(oxts_dir(d).glob("*.txt"))])
    ts = pd.to_datetime(pd.read_csv(oxts_dir(d).parent / "timestamps.txt", header=None)[0])
    t = (ts - ts.iloc[0]).dt.total_seconds().to_numpy()
    return {"t": t, "lat": a[:, 0], "lon": a[:, 1], "yaw": a[:, 5], "vn": a[:, 6], "ve": a[:, 7],
            "vf": a[:, 8], "af": a[:, 14], "al": a[:, 15], "wz": a[:, 19], "numsats": a[:, 26]}


def resample_1hz(ox, offset):
    """1 Hz grid on the real timestamps (KITTI frames are ~0.1032 s apart, not 0.1 s)."""
    tg = np.arange(offset, ox["t"][-1] + 1e-9, 1.0)
    g = {"t": tg, "yaw": np.interp(tg, ox["t"], np.unwrap(ox["yaw"]))}
    for k in ("lat", "lon", "vf", "vn", "ve", "af", "al", "wz"):
        g[k] = np.interp(tg, ox["t"], ox[k])
    g["numsats"] = ox["numsats"][np.searchsorted(ox["t"], tg).clip(0, len(ox["t"]) - 1)]
    return g


def receiver_noise(n, rng, phi=0.9, sigma=1.0):
    e = np.zeros((n, 2))
    e[0] = rng.normal(0, sigma, 2)
    for k in range(1, n):
        e[k] = phi * e[k - 1] + np.sqrt(1 - phi ** 2) * sigma * rng.normal(0, 1, 2)
    return e


# ----- attacks ----------------------------------------------------------------------------------
def attack_offset(name, east, north, k0, rng):
    """v2 position-only attacks. Returns (offset (n, 2) metres, severity). Same draws as v2."""
    n = len(east)
    t = np.clip(np.arange(n) - k0, 0, None).astype(float)
    th = rng.uniform(0, 2 * np.pi)
    u = np.array([np.cos(th), np.sin(th)])
    if name == "drift":
        sev = rng.uniform(*SEV["drift"])
        return np.outer(sev * t, u), sev
    if name == "accel_drift":
        sev = rng.uniform(*SEV["accel_drift"])
        return np.outer(0.5 * sev * t ** 2, u), sev
    if name == "jump":
        sev = rng.uniform(*SEV["jump"])
        return np.outer((t > 0) | (np.arange(n) == k0), u) * sev, sev
    off = np.zeros((n, 2))
    off[k0:, 0] = east[k0] - east[k0:]
    off[k0:, 1] = north[k0] - north[k0:]
    return off, 0.0


def doppler_pull(n, k0, w_max, theta, dt=1.0, accel=DOPPLER_ACCEL):
    """Doppler-consistent pull-off. Velocity offset w(t) = w_max min(tr / T, 1) u, tr = (k - k0) dt,
    T = w_max / accel (the spoofer accelerates the fake track away at `accel`); position offset
    o_k = o_{k-1} + (w_k + w_{k-1}) dt / 2 (trapezoid), so the offset track's discrete derivative is
    exactly the mean of the velocity offsets. Returns (o (n, 2) m, w (n, 2) m/s)."""
    u = np.array([np.cos(theta), np.sin(theta)])
    tr = np.clip(np.arange(n) - k0, 0, None) * dt
    w = w_max * np.minimum(tr / (w_max / accel), 1.0)
    o = np.r_[0.0, np.cumsum((w[1:] + w[:-1]) * dt / 2)]
    return np.outer(o, u), np.outer(w, u)


def meacon_delay(n, k0, tau_max, dt=1.0, rate=TAU_RATE):
    """Delay profile of the meaconing attack: smoothstep from 0 to tau_max,
      tau(tr) = tau_max (3u^2 - 2u^3),  u = min(tr / T, 1),  T = 1.5 tau_max / rate,  tr = (k - k0) dt,
    so the delay growth tau' = 6 tau_max u (1 - u) / T is 0 at both ends (no step in the apparent speed),
    peaks at `rate` s/s, and the receiver's apparent speed is (1 - tau') v >= (1 - rate) v.
    Returns (tau (n,) s, dtau/dt (n,))."""
    T = 1.5 * tau_max / rate
    u = np.minimum(np.clip(np.arange(n) - k0, 0, None) * dt / T, 1.0)
    return tau_max * (3 * u ** 2 - 2 * u ** 3), 6 * tau_max * u * (1 - u) / T


def _course(rep, heading):
    """v2 course: bearing of the reported position step, held when the step is < 0.3 m."""
    n = len(rep)
    step = np.r_[0, np.hypot(np.diff(rep[:, 0]), np.diff(rep[:, 1]))]
    course = np.degrees(np.arctan2(np.r_[0, np.diff(rep[:, 0])], np.r_[0, np.diff(rep[:, 1])])) % 360
    course[0] = heading[0]
    for k in range(1, n):
        if step[k] < 0.3:
            course[k] = course[k - 1]
    return course % 360


def _truth_at(ox, ts, lat0, lon0):
    """True local position (east, north) and velocity (east, north) at times ts, full-rate OXTS."""
    lat, lon = np.interp(ts, ox["t"], ox["lat"]), np.interp(ts, ox["t"], ox["lon"])
    north = (lat - lat0) * M_PER_DEG
    east = (lon - lon0) * M_PER_DEG * np.cos(np.radians(lat0))
    return np.c_[east, north], np.c_[np.interp(ts, ox["t"], ox["ve"]), np.interp(ts, ox["t"], ox["vn"])]


def make_run(ox, g, rng, attack=None, aux=None):
    """One 1 Hz KITTI run -> DataFrame(COLUMNS minus run/drive/part). For the four v2 attacks the draws
    on `rng` are exactly those of v2 track() (receiver noise, onset, attack, heading noise, scale, odo noise).
    `aux` (per-run generator) draws the added fields: Doppler / IMU / gyro noise."""
    idx = np.arange(len(g["t"]))
    n = len(idx)
    lat0, lon0 = g["lat"][0], g["lon"][0]
    north = (g["lat"] - lat0) * M_PER_DEG
    east = (g["lon"] - lon0) * M_PER_DEG * np.cos(np.radians(lat0))
    true_xy = np.c_[east, north]
    vel_true = np.c_[g["ve"], g["vn"]]
    rep = true_xy + receiver_noise(n, rng)
    label, sev, k0 = np.zeros(n, int), np.nan, -1
    dvel, clock = np.zeros((n, 2)), np.zeros(n)
    if attack == "meaconing":
        k0 = int(rng.integers(3, max(4, n - 2)))
        th_unused = rng.uniform(0, 2 * np.pi)          # keeps the draw pattern "theta then severity" of every attack
        sev = rng.uniform(*SEV["meaconing"])
        tau, dtau = meacon_delay(n, k0, sev)
        pos_d, vel_d = _truth_at(ox, np.clip(g["t"] - tau, ox["t"][0], None), lat0, lon0)
        rep = pos_d + (rep - true_xy)                  # fresh receiver noise on the delayed solution
        vel_true = vel_d * (1 - dtau)[:, None]         # chain rule: d/dt X(t - tau(t)) = V(t - tau)(1 - tau')
        clock = -tau
        label[k0:] = 1
    elif attack == "doppler_spoof":
        k0 = int(rng.integers(3, max(4, n - 2)))
        theta = rng.uniform(0, 2 * np.pi)
        sev = rng.uniform(*SEV["doppler_spoof"])
        off, dvel = doppler_pull(n, k0, sev, theta)
        rep = rep + off
        label[k0:] = 1
    elif attack:
        k0 = int(rng.integers(3, max(4, n - 2)))
        off, sev = attack_offset(attack, rep[:, 0], rep[:, 1], k0, rng)
        rep = rep + off
        label[k0:] = 1
    lat = lat0 + rep[:, 1] / M_PER_DEG
    lon = lon0 + rep[:, 0] / (M_PER_DEG * np.cos(np.radians(lat0)))
    heading = (90 - np.degrees(g["yaw"])) % 360 + rng.normal(0, 2, n)
    course = _course(rep, heading)
    odo = np.clip(g["vf"] * (1 + rng.normal(0, 0.02)) + rng.normal(0, 0.05, n), 0, None)
    aux = aux if aux is not None else np.random.default_rng(SEED)
    vel = vel_true + dvel + aux.normal(0, VEL_SIGMA, (n, 2))      # reported (Doppler) velocity, east / north
    cy, sy = np.cos(g["yaw"]), np.sin(g["yaw"])
    acc_e = g["af"] * cy - g["al"] * sy + aux.normal(0, ACC_SIGMA, n)
    acc_n = g["af"] * sy + g["al"] * cy + aux.normal(0, ACC_SIGMA, n)
    return pd.DataFrame({
        "t": g["t"], "lat": lat, "lon": lon, "x": rep[:, 0], "y": rep[:, 1],
        "x_true": east, "y_true": north,
        "vel_n": vel[:, 1], "vel_e": vel[:, 0], "speed_gps": np.hypot(vel[:, 0], vel[:, 1]), "course": course,
        "odo_speed": odo, "heading": heading, "yaw_rate": g["wz"] + aux.normal(0, GYRO_SIGMA, n),
        "acc_n": acc_n, "acc_e": acc_e,
        "numsats": g["numsats"], "hdop": 1.0, "fix_type": 3.0, "clock_offset": clock,
        "label": label, "attack": attack or "none", "onset": k0, "onset_t": g["t"][k0] if k0 >= 0 else np.nan,
        "severity": sev, "k": idx})


def build_kitti(rng, attacks=ATTACKS_V2, new_attacks=(), drives=None):
    """All KITTI runs. `rng` is the single v2 generator (default_rng(42)), consumed in sorted(SCENE) order,
    runs [clean] + v2 attacks (x2 for train) exactly as v2. New attacks follow in each phase, each run with
    its own generator seeded from (SEED, drive, phase, run index), so they never disturb the v2 draws."""
    parts = []
    for d in sorted(SCENE):
        if drives is not None and d not in drives:
            continue
        ox = load_oxts(d)
        part = part_of(d)
        reps = 2 if part == "train" else 1
        for ph in range(PHASES):
            g = resample_1hz(ox, ph / PHASES)
            if len(g["t"]) < 6:
                continue
            runs = [None] + [a for a in attacks for _ in range(reps)]
            runs_new = [a for a in new_attacks for _ in range(reps)]
            for r, a in enumerate(runs + runs_new):
                new = r >= len(runs)
                run_rng = np.random.default_rng([SEED, 3, int(d), ph, r]) if new else rng
                aux = np.random.default_rng([SEED, 2, int(d), ph, r])
                f = make_run(ox, g, run_rng, a, aux)
                f["drive"], f["part"], f["run"] = d, part, f"{d}/p{ph}/r{r}"
                parts.append(f)
    df = pd.concat(parts, ignore_index=True)
    return df[COLUMNS]


# ----- AV-GPS (D03) -----------------------------------------------------------------------------
AVGPS_VAL = {"f1:28562-29152", "f1:44251-44332", "f1:54195-62042"}


def load_avgps():
    """AV-GPS files 1-3 -> stream. Sessions = contiguous blocks with one label (v2). One row per second
    (row counter as time: the Clock Time field is not parseable on every row). Split as v2: test = files
    2 and 3, val = three file-1 sessions, train = the other file-1 sessions. Fields the dataset lacks are NaN
    (no Doppler velocity, no IMU acceleration; the receiver `numsats` has the known artefact: spoofed
    sessions show 0-1 satellites, so numsats must not be used as a detector on this data)."""
    out = []
    for i in (1, 2, 3):
        d = pd.read_csv(DATA / "AV-GPS-Dataset" / f"AV-GPS-Dataset-{i}.csv")
        y = d["Data Type"].to_numpy()
        b = np.r_[0, np.flatnonzero(np.diff(y)) + 1, len(y)]
        for s, e in zip(b[:-1], b[1:]):
            seg = d.iloc[s:e]
            sid = f"f{i}:{s}-{e}"
            lat, lon = seg["GPS Latitude"].to_numpy(float), seg["GPS Longitude"].to_numpy(float)
            x = (lon - lon[0]) * M_PER_DEG * np.cos(np.radians(lat[0]))
            yy = (lat - lat[0]) * M_PER_DEG
            n = len(seg)
            nan = np.full(n, np.nan)
            part = "test" if i in (2, 3) else "val" if sid in AVGPS_VAL else "train"
            out.append(pd.DataFrame({
                "t": np.arange(n, dtype=float), "lat": lat, "lon": lon, "x": x, "y": yy, "x_true": nan, "y_true": nan,
                "vel_n": nan, "vel_e": nan, "speed_gps": nan, "course": seg["GPS Course"].to_numpy(float),
                "odo_speed": seg["Velocity (m/s)"].to_numpy(float), "heading": seg["Heading (deg)"].to_numpy(float),
                "yaw_rate": np.radians(seg["Yaw Rate (deg/s)"].to_numpy(float)), "acc_n": nan, "acc_e": nan,
                "numsats": seg["Satellite Count"].to_numpy(float), "hdop": seg["GPS HDOP"].to_numpy(float),
                "fix_type": nan, "clock_offset": nan,
                "label": seg["Data Type"].to_numpy(int), "attack": np.where(seg["Data Type"] == 1, "avgps_spoof", "none"),
                "onset": 0 if y[s] == 1 else -1, "onset_t": 0.0 if y[s] == 1 else np.nan, "severity": np.nan,
                "k": np.arange(n), "run": sid, "drive": f"file{i}", "part": part}))
    return pd.concat(out, ignore_index=True)[COLUMNS]


# ----- UAV (D06) --------------------------------------------------------------------------------
UAV_LIVE = DATA_EXTRA / "gps_uav" / "extracted" / "Live GPS Spoofing and Jamming"
UAV_FLIGHTS = {"benign": "Benign Flight", "jamming": "GPS Jamming", "spoofing": "GPS Spoofing"}
UAV_SPOOF_ONSET_S = 117.0      # v2 case study: first spoofed fix at 118.0 s; no per-fix labels exist in the dataset


def _uav_topic(folder, name):
    return pd.read_csv(next((UAV_LIVE / folder).glob(f"*_{name}_0.csv")))


def _quat_rot(q, v):
    w, x, y, z = q.T
    R = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                  [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                  [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])
    return np.einsum("ijn,nj->ni", R, v)


def load_uav_flight(name):
    """One PX4 live flight -> stream at the GPS rate (1 Hz). Acceleration = IMU specific force rotated to NED
    with the attitude quaternion, gravity added back, averaged over the second before each fix. There is no
    wheel odometry on a drone (NaN). Labels: spoofing flight rows with t >= UAV_SPOOF_ONSET_S are 1 (approximate
    onset from the v2 case study; jamming flight is label 0 here: it is a jamming, not a spoofing, case)."""
    folder = UAV_FLIGHTS[name]
    gps, imu, att = _uav_topic(folder, "vehicle_gps_position"), _uav_topic(folder, "sensor_combined"), _uav_topic(folder, "vehicle_attitude")
    t0 = gps["timestamp"].iloc[0]
    tg, ti, ta = [(x["timestamp"].to_numpy() - t0) / 1e6 for x in (gps, imu, att)]
    q = np.c_[[np.interp(ti, ta, att[f"q[{k}]"]) for k in range(4)]].T
    q /= np.linalg.norm(q, axis=1, keepdims=True)
    a_ned = _quat_rot(q, imu[[f"accelerometer_m_s2[{k}]" for k in range(3)]].to_numpy()) + np.array([0, 0, G])
    gz = imu["gyro_rad[2]"].to_numpy()
    yaw = np.arctan2(2 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]), 1 - 2 * (q[:, 2] ** 2 + q[:, 3] ** 2))

    def window_mean(sig, w=1.0):
        c = np.r_[0, np.cumsum(sig)]
        hi = np.searchsorted(ti, tg, side="right")
        lo = np.searchsorted(ti, tg - w, side="right")
        return (c[hi] - c[lo]) / np.maximum(hi - lo, 1)

    lat, lon = gps["lat"].to_numpy() * 1e-7, gps["lon"].to_numpy() * 1e-7
    n = len(gps)
    nan = np.full(n, np.nan)
    label = (tg >= UAV_SPOOF_ONSET_S).astype(int) if name == "spoofing" else np.zeros(n, int)
    return pd.DataFrame({
        "t": tg, "lat": lat, "lon": lon,
        "x": (lon - lon[0]) * M_PER_DEG * np.cos(np.radians(lat[0])), "y": (lat - lat[0]) * M_PER_DEG,
        "x_true": nan, "y_true": nan,
        "vel_n": gps["vel_n_m_s"].to_numpy(), "vel_e": gps["vel_e_m_s"].to_numpy(), "speed_gps": gps["vel_m_s"].to_numpy(),
        "course": np.degrees(gps["cog_rad"].to_numpy()) % 360,
        "odo_speed": nan, "heading": np.degrees(np.interp(tg, ti, np.unwrap(yaw))) % 360,
        "yaw_rate": -window_mean(gz), "acc_n": window_mean(a_ned[:, 0]), "acc_e": window_mean(a_ned[:, 1]),
        "numsats": gps["satellites_used"].to_numpy(float), "hdop": gps["hdop"].to_numpy(float),
        "fix_type": gps["fix_type"].to_numpy(float), "clock_offset": nan,
        "label": label, "attack": np.where(label == 1, "uav_live_spoof", "none"),
        "onset": int(np.argmax(label)) if label.any() else -1,
        "onset_t": float(tg[np.argmax(label)]) if label.any() else np.nan, "severity": np.nan,
        "k": np.arange(n), "run": f"uav/{name}", "drive": f"uav/{name}", "part": "test"})[COLUMNS]


def load_uav():
    return pd.concat([load_uav_flight(k) for k in UAV_FLIGHTS], ignore_index=True)


# ----- splits -----------------------------------------------------------------------------------
def splits_dict(kitti, avgps, uav):
    """Group ids per part, for results/WP1/splits.json. KITTI by drive, AV-GPS by session, UAV by flight
    (all flights are test: they are a case study, nothing is trained or calibrated on them)."""
    return {
        "kitti_drives": {"train": sorted(set(SCENE) - set(TEST) - set(VAL)), "val": sorted(VAL), "test": sorted(TEST)},
        "kitti_runs": {p: sorted(kitti.loc[kitti["part"] == p, "run"].unique()) for p in ("train", "val", "test")},
        "avgps_sessions": {p: sorted(avgps.loc[avgps["part"] == p, "run"].unique()) for p in ("train", "val", "test")},
        "uav_flights": {"test": sorted(uav["run"].unique())},
    }


def write_splits(kitti, avgps, uav, path):
    Path(path).write_text(json.dumps(splits_dict(kitti, avgps, uav), indent=1))
