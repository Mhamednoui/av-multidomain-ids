"""WP6 S2 comma2k19: witness residuals of clean routes (all parts, for the per-setup sigma fit / honesty) and of clean / attacked
120 s episodes of the VAL and TEST routes.

Stage build (python -u -W ignore tools/WP6_S2_comma.py build); input: the S1 route cache (../data_extra/cache_v3/WP6/s1_comma_routes.pkl).
Witnesses: gnss (u-blox: Doppler speed, position, bearing; CLAIM), can (vehicle-speed message), wheel (0xAA wheel-speed message, same
bus), imu (gyro yaw, axis / sign from S1). Lags from S1 (train). Edges: gnss-can speed, gnss-wheel speed, can-wheel speed,
gnss-can pspeed, gnss-wheel pspeed (pspeed = |GNSS position change over (t-1, t]|), gnss-imu yaw.
Setup of a route (sample rates only): gyro_hz, gnss_hz.
Attacks (crossdomain/attacks.py): gnss drift / accel_drift / doppler_spoof / meaconing, can_scale / can_offset / can_freeze on the
vehicle-speed message, coordinated gnss_can, can_bus (both CAN speed messages scaled together).
Episodes: consecutive 120 s blocks of the route grid; onset 30-90 s into the block; 2 draws per block and attack.
Output: ../data_extra/cache_v3/WP6/s2_comma.pkl = {"routes": DataFrame (clean full routes), "episodes": DataFrame, "setup": {route: ...}}.
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DATA_EXTRA, SEED, results_dir  # noqa: E402
from crossdomain import attacks as A  # noqa: E402
from crossdomain import comma as C  # noqa: E402
from crossdomain import witness as W  # noqa: E402
from gps.stream import M_PER_DEG  # noqa: E402

CACHE = DATA_EXTRA / "cache_v3" / "WP6"
OUT = results_dir("WP6")
GNSS_ATTACKS = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
CAN_ATTACKS = ["can_scale", "can_offset", "can_freeze"]
ATTACKS = GNSS_ATTACKS + CAN_ATTACKS + ["gnss_can", "can_bus"]
TARGET = {**{a: "gnss" for a in GNSS_ATTACKS}, **{a: "can" for a in CAN_ATTACKS}, "gnss_can": "gnss+can", "can_bus": "can+wheel"}
DOMAIN_OF = {"gnss": "gps", "can": "can", "wheel": "can", "imu": "imu"}
EDGE_NAMES = ["gnss-can speed", "gnss-wheel speed", "can-wheel speed", "gnss-can pspeed", "gnss-wheel pspeed", "gnss-imu yaw"]
WIN, REPS, ON_LO, ON_HI = 120, 2, 30.0, 90.0
POS_GAP = 0.6


def enu(r):
    lat0, lon0 = r["gnss_lat"][0], r["gnss_lon"][0]
    return (r["gnss_lon"] - lon0) * M_PER_DEG * np.cos(np.radians(lat0)), (r["gnss_lat"] - lat0) * M_PER_DEG


def pspeed(t, E, N, grid):
    """|position change over (g-1, g]| / 1 s from linearly interpolated GNSS positions; NaN if no sample within POS_GAP."""
    out = np.full(len(grid), np.nan)
    if len(t) < 2:
        return out
    def near(x):
        j = np.clip(np.searchsorted(t, x), 1, len(t) - 1)
        return np.minimum(np.abs(t[j] - x), np.abs(t[j - 1] - x)) <= POS_GAP
    ok = near(grid) & near(grid - 1) & (grid - 1 >= t[0]) & (grid <= t[-1])
    dE = np.interp(grid, t, E) - np.interp(grid - 1, t, E)
    dN = np.interp(grid, t, N) - np.interp(grid - 1, t, N)
    out[ok] = np.hypot(dE, dN)[ok]
    return out


def residuals(sig, grid, lags, gyro):
    """sig: dict of native arrays (gnss_t, gnss_v, gnss_bearing, E, N, can_t, can_v, wheel_t, wheel_v, gyro_t, gyro) -> {edge: (r, v)}."""
    fr = lambda src, t, speed=None, yaw=None: pd.DataFrame({"t": t, "source": src, "speed": np.nan if speed is None else speed,
                                                            "yaw_rate": np.nan if yaw is None else yaw, "dx": np.nan, "dy": np.nan, "sigma": 1.0})
    g = W.to_grid(fr("gnss", sig["gnss_t"], sig["gnss_v"]), grid, kind="inst")["speed"].to_numpy()
    c = W.to_grid(fr("can", sig["can_t"], sig["can_v"]), grid, kind="inst", lag=lags["gnss-can speed"])["speed"].to_numpy()
    w = W.to_grid(fr("wheel", sig["wheel_t"], sig["wheel_v"]), grid, kind="inst", lag=lags["gnss-wheel speed"])["speed"].to_numpy()
    p = pspeed(sig["gnss_t"], sig["E"], sig["N"], grid)
    ty, wy = C.gnss_yaw_rate(sig["gnss_t"], sig["gnss_bearing"], sig["gnss_v"])
    gy = W.to_grid(fr("gnss", ty, None, wy), grid, kind="inst")["yaw_rate"].to_numpy()
    iy = W.to_grid(fr("imu", sig["gyro_t"], None, gyro[1] * sig["gyro"][:, gyro[0]]), grid, kind="inst", lag=lags["gnss-imu yaw_rate"])["yaw_rate"].to_numpy()
    m2 = lambda a, b: np.nanmean(np.c_[a, b], axis=1)
    return {"gnss-can speed": (g - c, m2(g, c)), "gnss-wheel speed": (g - w, m2(g, w)), "can-wheel speed": (c - w, m2(c, w)),
            "gnss-can pspeed": (p - c, m2(p, c)), "gnss-wheel pspeed": (p - w, m2(p, w)), "gnss-imu yaw": (gy - iy, g)}


def frame_rows(meta, grid, res):
    d = {"t": grid}
    for k, (r, v) in res.items():
        d[f"r_{k}"], d[f"v_{k}"] = r, v
    f = pd.DataFrame(d)
    for k, v in meta.items():
        f[k] = v
    return f


def native(r):
    E, N = enu(r)
    return {"gnss_t": r["gnss_t"], "gnss_v": r["gnss_v"], "gnss_bearing": r["gnss_bearing"], "E": E, "N": N, "can_t": r["can_t"], "can_v": r["can_v"],
            "wheel_t": r["wheel_t"], "wheel_v": r["wheel_v"], "gyro_t": r["gyro_t"], "gyro": r["gyro"]}


def cut(sig, t0, t1):
    out = {}
    for src, keys in (("gnss_t", ("gnss_v", "gnss_bearing", "E", "N")), ("can_t", ("can_v",)), ("wheel_t", ("wheel_v",)), ("gyro_t", ("gyro",))):
        m = (sig[src] >= t0) & (sig[src] <= t1)
        out[src] = sig[src][m]
        for k in keys:
            out[k] = sig[k][m]
    return out


def attack(sig, a, t_on, rng):
    s = {k: np.array(v, copy=True) for k, v in sig.items()}
    b = np.radians(s["gnss_bearing"])
    ve, vn = s["gnss_v"] * np.sin(b), s["gnss_v"] * np.cos(b)
    def set_gnss(E, N, ve2, vn2):
        s["E"], s["N"] = E, N
        s["gnss_v"] = np.hypot(ve2, vn2)
        s["gnss_bearing"] = np.degrees(np.arctan2(ve2, vn2)) % 360
    if a in GNSS_ATTACKS:
        E, N, ve2, vn2, sev = A.gnss_attack(a, s["gnss_t"], s["E"], s["N"], ve, vn, t_on, rng)
        set_gnss(E, N, ve2, vn2)
    elif a in CAN_ATTACKS:
        s["can_v"], sev = A.can_attack(a, s["can_t"], s["can_v"], t_on, rng)
    elif a == "can_bus":
        s["can_v"], sev = A.can_attack("can_bus", s["can_t"], s["can_v"], t_on, rng)
        s["wheel_v"] = np.where(s["wheel_t"] >= t_on, s["wheel_v"] * (1 + sev), s["wheel_v"])
    elif a == "gnss_can":
        sev = A.sign(rng) * rng.uniform(*A.COORD_SEV)
        dE, dN, dve, dvn, w = A.along_track(s["gnss_t"], ve, vn, t_on, sev)
        set_gnss(s["E"] + dE, s["N"] + dN, ve + dve, vn + dvn)
        s["can_v"] = np.clip(s["can_v"] + np.interp(s["can_t"], s["gnss_t"], w), 0, None)
    else:
        raise ValueError(a)
    return s, float(sev)


def rate(t):
    return float(len(np.unique(t)) / max(t[-1] - t[0], 1e-9))      # unique: old routes duplicate every gyro timestamp


def build_all():
    sm = json.loads((OUT / "s1_sigma_models.json").read_text())["comma_R"]
    lags, gyro = sm["lags"], (sm["gyro"]["axis"], sm["gyro"]["sign"])
    c = pickle.load(open(CACHE / "s1_comma_routes.pkl", "rb"))
    data, part = c["data"], c["part"]
    T0 = time.time()
    routes, eps, setup = [], [], {}
    for ri, n in enumerate(sorted(data)):
        r = data[n]
        setup[n] = {"part": part[n], "gyro_hz": rate(r["gyro_t"]), "gnss_hz": rate(r["gnss_t"])}
        t0 = max(r["can_t"][0], r["gnss_t"][0], r["gyro_t"][0])
        t1 = min(r["can_t"][-1], r["gnss_t"][-1], r["gyro_t"][-1])
        grid = np.arange(np.ceil(t0) + 1.0, np.floor(t1) - 1.0, 1.0)
        sig = native(r)
        routes.append(frame_rows({"route": n, "part": part[n]}, grid, residuals(sig, grid, lags, gyro)))
        if part[n] == "train":
            continue
        for wi in range(len(grid) // WIN):
            g = grid[wi * WIN:(wi + 1) * WIN]
            sw = cut(sig, g[0] - 4.0, g[-1] + 2.0)
            base = {"route": n, "part": part[n], "window": wi}
            eps.append(frame_rows({**base, "run": f"{n}/w{wi}/clean", "attack": "none", "target": "none", "onset_t": np.nan, "severity": np.nan},
                                  g, residuals(sw, g, lags, gyro)))
            for ai, a in enumerate(ATTACKS):
                for rep in range(REPS):
                    rng = np.random.default_rng([SEED, 6, 30, ri, wi, ai, rep])
                    t_on = float(g[0] + rng.uniform(ON_LO, ON_HI))
                    s2, sev = attack(sw, a, t_on, rng)
                    eps.append(frame_rows({**base, "run": f"{n}/w{wi}/{a}/{rep}", "attack": a, "target": TARGET[a], "onset_t": t_on, "severity": sev},
                                          g, residuals(s2, g, lags, gyro)))
        print(f"[{time.time() - T0:5.0f}s] {n} {part[n]} gyro {setup[n]['gyro_hz']:.0f} Hz gnss {setup[n]['gnss_hz']:.1f} Hz", flush=True)
    out = {"routes": pd.concat(routes, ignore_index=True), "episodes": pd.concat(eps, ignore_index=True), "setup": setup}
    pickle.dump(out, open(CACHE / "s2_comma.pkl", "wb"))
    print(out["episodes"].groupby(["part", "attack"])["run"].nunique(), flush=True)


if __name__ == "__main__":
    {"build": build_all}[sys.argv[1]]()
