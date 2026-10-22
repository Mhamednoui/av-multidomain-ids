"""WP6 S2: single-domain and coordinated attacks on motion-witness streams (time-based, native rate or 1 Hz grid).

Purpose: inject what an attacker of ONE domain can change, leaving the other witnesses untouched.
- GNSS (comma2k19, native rate): drift, accel_drift, doppler_spoof, meaconing: the equations and severity ranges of the WP1
  generator (gps/stream.py: attack_offset, doppler_pull, meacon_delay, SEV, DOPPLER_ACCEL, TAU_RATE), written on a time axis
  instead of the 1 Hz fix index. KITTI GPS attacks are the WP1 runs themselves (not regenerated here).
  A spoofer controls the receiver's position, Doppler velocity and bearing; it cannot touch wheel speed, gyro or LiDAR.
- LiDAR odometry (1 Hz grid of the "lidar" witness): what an attacker of the point cloud (injected / removed returns)
  can do to ICP: a scale error (dx, dy x (1 + s)), a forward speed bias ramped in at 0.4 m/s^2, a yaw-rate bias.
  It cannot touch GPS, CAN or the IMU.
- CAN wheel speed (decoded native speed of one message): masquerade of the speed signal: scale, offset ramped in at
  0.4 m/s^2 (clipped >= 0, a speed is unsigned), frozen at the onset value (ROAD masquerade rewrites one ID in place).
- Coordinated (two domains agree on the lie): along-track Doppler-consistent GPS spoof + the same speed offset on CAN.
Inputs: numpy arrays (times, values), onset time, numpy Generator. Outputs: modified copies + severity.
Limits: non-adaptive attackers (they do not know the thresholds or the other witnesses' noise).
"""
import numpy as np

from gps.stream import DOPPLER_ACCEL, SEV, TAU_RATE

LIDAR_SEV = {"lidar_scale": (0.02, 0.2), "lidar_bias": (0.2, 2.0), "lidar_yaw": (0.005, 0.05)}
CAN_SEV = {"can_scale": (0.02, 0.2), "can_offset": (0.2, 2.0), "can_freeze": (0.0, 0.0), "can_bus": (0.02, 0.2)}
COORD_SEV = (0.2, 3.0)
RAMP = DOPPLER_ACCEL          # m/s^2


def _tr(t, t_on):
    return np.clip(np.asarray(t, float) - t_on, 0, None)


def ramp(t, t_on, w_max, accel=RAMP):
    """Offset that grows at `accel` from 0 at onset to w_max (signed), then stays: w(t) = w_max min(tr / T, 1), T = |w_max| / accel."""
    T = max(abs(w_max) / accel, 1e-9)
    return w_max * np.minimum(_tr(t, t_on) / T, 1.0)


def ramp_integral(t, t_on, w_max, accel=RAMP):
    """Integral of ramp() from onset: 0.5 a tr^2 (signed) for tr <= T, then 0.5 a T^2 + w_max (tr - T)."""
    tr = _tr(t, t_on)
    T = max(abs(w_max) / accel, 1e-9)
    s = np.sign(w_max)
    return np.where(tr <= T, s * 0.5 * accel * tr ** 2, s * 0.5 * accel * T ** 2 + w_max * (tr - T))


def sign(rng):
    return 1.0 if rng.uniform() < 0.5 else -1.0


# ---- GNSS (native rate; E, N metres local; ve, vn m/s) ------------------------------------------------------------
def gnss_attack(name, t, E, N, ve, vn, t_on, rng):
    """Return (E, N, ve, vn, severity) after the attack. Draw order: theta, severity (as gps/stream.py)."""
    t = np.asarray(t, float)
    th = rng.uniform(0, 2 * np.pi)
    u = np.array([np.cos(th), np.sin(th)])
    tr = _tr(t, t_on)
    E, N, ve, vn = (np.array(x, float) for x in (E, N, ve, vn))
    if name == "drift":
        sev = rng.uniform(*SEV["drift"])
        return E + sev * tr * u[0], N + sev * tr * u[1], ve, vn, sev
    if name == "accel_drift":
        sev = rng.uniform(*SEV["accel_drift"])
        return E + 0.5 * sev * tr ** 2 * u[0], N + 0.5 * sev * tr ** 2 * u[1], ve, vn, sev
    if name == "doppler_spoof":
        sev = rng.uniform(*SEV["doppler_spoof"])
        o, w = ramp_integral(t, t_on, sev), ramp(t, t_on, sev)
        return E + o * u[0], N + o * u[1], ve + w * u[0], vn + w * u[1], sev
    if name == "meaconing":
        sev = rng.uniform(*SEV["meaconing"])
        T = 1.5 * sev / TAU_RATE
        x = np.minimum(tr / T, 1.0)
        tau, dtau = sev * (3 * x ** 2 - 2 * x ** 3), 6 * sev * x * (1 - x) / T
        td = t - tau
        f = lambda v: np.interp(td, t, v)
        return f(E), f(N), f(ve) * (1 - dtau), f(vn) * (1 - dtau), sev
    raise ValueError(name)


def along_track(t, ve, vn, t_on, w_max):
    """Coordinated GPS + CAN: velocity offset w(t) along the true direction of travel; returns (dE, dN, dve, dvn, w)."""
    sp = np.hypot(ve, vn)
    ue, un = np.where(sp > 0.5, ve / np.maximum(sp, 1e-9), 0.0), np.where(sp > 0.5, vn / np.maximum(sp, 1e-9), 0.0)
    w = ramp(t, t_on, w_max)
    dve, dvn = w * ue, w * un
    dt = np.diff(np.asarray(t, float))
    dE = np.r_[0.0, np.cumsum(0.5 * (dve[1:] + dve[:-1]) * dt)]
    dN = np.r_[0.0, np.cumsum(0.5 * (dvn[1:] + dvn[:-1]) * dt)]
    return dE, dN, dve, dvn, w


# ---- CAN (decoded native speed) -----------------------------------------------------------------------------------
def can_attack(name, t, v, t_on, rng):
    """Return (v, severity) for the CAN speed signal of one message."""
    t, v = np.asarray(t, float), np.array(v, float)
    on = t >= t_on
    if name in ("can_scale", "can_bus"):
        s = sign(rng) * rng.uniform(*CAN_SEV[name])
        return np.where(on, v * (1 + s), v), s
    if name == "can_offset":
        b = sign(rng) * rng.uniform(*CAN_SEV[name])
        return np.clip(v + ramp(t, t_on, b), 0, None), b
    if name == "can_freeze":
        i = min(int(np.searchsorted(t, t_on)), len(v) - 1)
        return np.where(on, v[i], v), 0.0
    raise ValueError(name)


# ---- LiDAR odometry (1 Hz grid: columns dx, dy, speed, yaw_rate) ---------------------------------------------------
def lidar_attack(name, grid, t_on, rng):
    """grid: DataFrame indexed by grid time with dx, dy, speed (R4: = dx), yaw_rate. Returns (copy, severity)."""
    g = grid.copy()
    t = g.index.to_numpy(float)
    on = t >= t_on
    if name == "lidar_scale":
        s = sign(rng) * rng.uniform(*LIDAR_SEV[name])
        for c in ("dx", "dy", "speed"):
            g[c] = np.where(on, g[c].to_numpy(float) * (1 + s), g[c].to_numpy(float))
        return g, s
    if name == "lidar_bias":
        b = sign(rng) * rng.uniform(*LIDAR_SEV[name])
        w = ramp(t, t_on, b)
        g["dx"] = g["dx"].to_numpy(float) + w
        g["speed"] = g["speed"].to_numpy(float) + w
        return g, b
    if name == "lidar_yaw":
        w = sign(rng) * rng.uniform(*LIDAR_SEV[name])
        g["yaw_rate"] = np.where(on, g["yaw_rate"].to_numpy(float) + w, g["yaw_rate"].to_numpy(float))
        return g, w
    raise ValueError(name)
