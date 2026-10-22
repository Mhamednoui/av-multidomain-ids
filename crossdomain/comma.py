"""WP6 S1: comma2k19 (D22, MIT) motion-witness streams: real CAN speed / wheel speeds, u-blox GNSS, IMU gyro, same car.

Purpose: the only data set in reach with a real CAN bus and a GNSS receiver on the same vehicle. Used to (1) validate the
CAN-vs-GNSS speed relation (scale, latency, residual distribution), (2) show how a CAN wheel-speed unit is calibrated
against GNSS (the raw Toyota-style 0xAA wheel-speed counts vs GNSS speed), (3) give real (not simulated) residual
statistics for the witness layer.
Data: Chunk_1 of comma2k19 (Schafer et al. 2018, arXiv:1812.05752), 20 routes of one car (dongle b0c9d2329ad1606b), 1 min
segments, processed_log numpy arrays only (fetched by tools/WP6_S1_comma_fetch.py, read with np.load(allow_pickle=False),
never executed). Time base: the device boot clock (s), shared by all processed_log arrays of a route.
Fields used (comma2k19 README): CAN/speed (m/s, decoded by comma), CAN/wheel_speed (4 x m/s), CAN/raw_can (address, 8-byte
data, t), GNSS/live_gnss_ublox value = [lat, lon, speed m/s, utc ms, altitude m, bearing deg], IMU/gyro (3 axes, rad/s,
device frame).
Outputs: per route dict of source frames (crossdomain.witness.COLS) and native-rate signals.
Sources: "can" (decoded vehicle speed), "wheel" (mean of the 4 decoded wheel speeds), "gnss" (u-blox Doppler speed and
bearing-rate yaw; a GPS CLAIM), "imu" (gyro yaw axis; axis and sign chosen on TRAIN routes, tools/WP6_S1_comma.py).
Published sigmas: "can"/"wheel" take the frozen CAN formula max(0.3, 3% v) (can/domain.py); "gnss" takes the WP1 GPS claim
sigma 0.45 m/s (gps/domain.py); comma publishes none: honesty is judged after the train recalibration (SigmaModel).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import DATA_EXTRA

ROOT = DATA_EXTRA / "D22_comma2k19" / "Chunk_1"
CAN_SIGMA_MIN, CAN_SIGMA_REL = 0.3, 0.03
GNSS_SPEED_SIGMA = 0.45
MIN_BEARING_SPEED = 3.0          # m/s: below this the GNSS bearing is noise
WHEEL_ADDR = 0xAA                # Toyota-style WHEEL_SPEEDS (4 x 16 bit big-endian, 0.01 km/h, offset -67.67 km/h; opendbc)


def routes(root=ROOT):
    return sorted(p for p in Path(root).iterdir() if p.is_dir())


def split_routes(rs):
    """BY ROUTE, sorted by start time (route name = date): first 60% train, next 20% val, last 20% test (rounded)."""
    rs = sorted(rs, key=lambda p: p.name.split("_", 1)[1])
    n = len(rs)
    ntr = int(round(0.6 * n))
    nva = max(1, int(round(0.2 * n)))
    return {"train": rs[:ntr], "val": rs[ntr:ntr + nva], "test": rs[ntr + nva:]}


def _load(seg, rel):
    return np.load(Path(seg) / rel, allow_pickle=False)


def _cat(segs, rel):
    t = np.concatenate([_load(s, rel + "/t") for s in segs])
    v = np.concatenate([_load(s, rel + "/value") for s in segs])
    o = np.argsort(t, kind="stable")
    return t[o], v[o]


def load_route(route):
    """Native-rate arrays of a route (segments concatenated in time order)."""
    segs = sorted((s for s in Path(route).iterdir() if s.is_dir()), key=lambda p: int(p.name))
    out = {"segments": [int(s.name) for s in segs]}
    out["can_t"], v = _cat(segs, "processed_log/CAN/speed")
    out["can_v"] = v.reshape(len(v), -1)[:, 0]
    out["wheel_t"], w = _cat(segs, "processed_log/CAN/wheel_speed")
    out["wheel_v"] = w.mean(1)
    out["gnss_t"], g = _cat(segs, "processed_log/GNSS/live_gnss_ublox")
    out["gnss_lat"], out["gnss_lon"], out["gnss_v"], out["gnss_bearing"] = g[:, 0], g[:, 1], g[:, 2], g[:, 5]
    out["gyro_t"], out["gyro"] = _cat(segs, "processed_log/IMU/gyro")
    ts, adr, dat = [], [], []
    for s in segs:
        a = _load(s, "processed_log/CAN/raw_can/address")
        m = a == WHEEL_ADDR
        ts.append(_load(s, "processed_log/CAN/raw_can/t")[m])
        dat.append(_load(s, "processed_log/CAN/raw_can/data")[m])
    t = np.concatenate(ts)
    d = np.concatenate(dat)
    B = np.frombuffer(b"".join(x.ljust(8, b"\0")[:8] for x in d), np.uint8).reshape(-1, 8) if len(d) else np.zeros((0, 8), np.uint8)
    o = np.argsort(t, kind="stable")
    out["raw_wheel_t"], out["raw_wheel_B"] = t[o], B[o]
    return out


def raw_wheel_counts(B):
    """4 x 16-bit big-endian raw counts of the 0xAA payload (n x 4)."""
    B = np.asarray(B, np.int64)
    return np.c_[B[:, 0] * 256 + B[:, 1], B[:, 2] * 256 + B[:, 3], B[:, 4] * 256 + B[:, 5], B[:, 6] * 256 + B[:, 7]]


def gnss_yaw_rate(t, bearing, v, min_speed=MIN_BEARING_SPEED):
    """Instantaneous yaw rate (rad/s, positive left) from consecutive u-blox bearings (compass deg, clockwise), at the middle
    of each sample pair; NaN where either speed is below min_speed."""
    b = np.unwrap(np.radians(bearing))
    dt = np.diff(t)
    w = -np.diff(b) / np.where(dt > 0, dt, np.nan)
    ok = (v[1:] >= min_speed) & (v[:-1] >= min_speed) & (dt > 0)
    return 0.5 * (t[1:] + t[:-1]), np.where(ok, w, np.nan)


def frames(r, gyro_axis=2, gyro_sign=1.0):
    """Source frames (witness.COLS, instantaneous samples) of a loaded route."""
    def fr(src, t, speed=None, yaw=None, sigma=None):
        n = len(t)
        return pd.DataFrame({"t": t, "source": src, "speed": np.full(n, np.nan) if speed is None else speed,
                             "yaw_rate": np.full(n, np.nan) if yaw is None else yaw, "dx": np.nan, "dy": np.nan,
                             "sigma": np.full(n, np.nan) if sigma is None else sigma})
    cs = lambda v: np.maximum(CAN_SIGMA_MIN, CAN_SIGMA_REL * np.abs(v))
    ty, wy = gnss_yaw_rate(r["gnss_t"], r["gnss_bearing"], r["gnss_v"])
    g = fr("gnss", r["gnss_t"], r["gnss_v"], None, np.full(len(r["gnss_t"]), GNSS_SPEED_SIGMA))
    gy = fr("gnss", ty, None, wy)
    return {"can": fr("can", r["can_t"], r["can_v"], None, cs(r["can_v"])),
            "wheel": fr("wheel", r["wheel_t"], r["wheel_v"], None, cs(r["wheel_v"])),
            "gnss": g, "gnss_yaw": gy,
            "imu": fr("imu", r["gyro_t"], None, gyro_sign * r["gyro"][:, gyro_axis])}
