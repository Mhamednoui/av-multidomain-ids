"""WP6 S2 KITTI: witness residuals of every clean / attacked run of the VAL and TEST drives (design R, S1 kitti_R models).

Stage build (python -u -W ignore tools/WP6_S2_kitti.py build):
  per drive (val + test, WP1 split) and phase (10): the WP1 clean run r0 and the WP1 GPS attack runs (drift, accel_drift,
  doppler_spoof, meaconing: the exact runs the frozen GPS domain was scored on), plus attacks injected on the clean run:
  lidar_scale / lidar_bias / lidar_yaw (LiDAR odometry grid), can_scale / can_offset / can_freeze (decoded CAN speed),
  and the coordinated gps_can (along-track Doppler-consistent GPS spoof + same offset on CAN and on the wheel odometry column).
  Witnesses: gps (claim), compass + gyro (imu), lidar (ICP odometry, WP1 cache), can (SIMULATED 0x6e0 decoded by the frozen
  CanDomain, design R2 scale). Output: ../data_extra/cache_v3/WP6/s2_kitti.pkl = {"rows": DataFrame (one row per run second:
  meta + r_<edge>, v_<edge>), "gps_can_runs": DataFrame of the modified coordinated GPS runs (stream columns, for the GPS domain)}.
Seeds: common.config.SEED; per run generator [SEED, 6, 20, drive, phase, attack index].
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED  # noqa: E402
from crossdomain import attacks as A  # noqa: E402
from crossdomain import can_sim  # noqa: E402
from crossdomain import kitti as K  # noqa: E402
from crossdomain import witness as W  # noqa: E402
from gps import stream as GS  # noqa: E402
from gps.domain import gps_motion_estimates  # noqa: E402
import WP6_S1_kitti as S1  # noqa: E402

CACHE = S1.CACHE
GPS_ATTACKS = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
LIDAR_ATTACKS = ["lidar_scale", "lidar_bias", "lidar_yaw"]
CAN_ATTACKS = ["can_scale", "can_offset", "can_freeze"]
INJECTED = LIDAR_ATTACKS + CAN_ATTACKS + ["gps_can"]
DOMAIN_OF = {"gps": "gps", "lidar": "lidar", "can": "can", "gyro": "imu", "compass": "imu"}
TARGET = {**{a: "gps" for a in GPS_ATTACKS}, **{a: "lidar" for a in LIDAR_ATTACKS}, **{a: "can" for a in CAN_ATTACKS}, "gps_can": "gps+can"}
# edge name -> (node a, node b, quantity, S1 kitti_R model key)
EDGES = [("gps", "lidar", "speed", "gps-lidar speed"), ("gps", "can", "speed", "gps-can speed"), ("lidar", "can", "speed", "lidar-can speed"),
         ("gps", "lidar", "lateral", "gps-lidar lateral"), ("compass", "lidar", "yaw", "gps-lidar yaw_rate"),
         ("compass", "gyro", "yaw", "gps-imu yaw_rate"), ("gyro", "lidar", "yaw", "imu-lidar yaw_rate")]


def edge_name(e):
    return f"{e[0]}-{e[1]} {e[2]}"


def residuals(G):
    """G: grids of gps, lidar (both R4 forward speed), can, imu -> dict edge name -> (r, v)."""
    sp = lambda s: G[s]["speed"].to_numpy(float)
    yw = lambda s: G[s]["yaw_rate"].to_numpy(float)
    mean2 = lambda a, b: np.nanmean(np.c_[a, b], axis=1)
    out = {}
    out["gps-lidar speed"] = (sp("gps") - sp("lidar"), mean2(sp("gps"), sp("lidar")))
    out["gps-can speed"] = (sp("gps") - sp("can"), mean2(sp("gps"), sp("can")))
    out["lidar-can speed"] = (sp("lidar") - sp("can"), mean2(sp("lidar"), sp("can")))
    out["gps-lidar lateral"] = (G["gps"]["dy"].to_numpy(float) - G["lidar"]["dy"].to_numpy(float), sp("lidar"))
    out["compass-lidar yaw"] = (yw("gps") - yw("lidar"), mean2(sp("gps"), sp("lidar")))
    out["compass-gyro yaw"] = (yw("gps") - yw("imu"), sp("gps"))
    out["gyro-lidar yaw"] = (yw("imu") - yw("lidar"), sp("lidar"))
    return out


def gps_grid(run, grid):
    return K.forward_speed(W.to_grid(W.to_frame(gps_motion_estimates(run)), grid))


def rows_of(meta, grid, G):
    res = residuals(G)
    d = {"t": grid}
    for k, (r, v) in res.items():
        d[f"r_{k}"], d[f"v_{k}"] = r, v
    f = pd.DataFrame(d)
    for k, v in meta.items():
        f[k] = v
    return f


def coordinated(run, ox, k0, rng):
    """gps_can on a clean run: along-track Doppler-consistent offset w(t) on the GPS position / Doppler and the wheel odometry."""
    t = run["t"].to_numpy(float)
    t_on = t[k0]
    w_max = A.sign(rng) * rng.uniform(*A.COORD_SEV)
    ve, vn = np.interp(t, ox["t"], ox["ve"]), np.interp(t, ox["t"], ox["vn"])
    dE, dN, dve, dvn, w = A.along_track(t, ve, vn, t_on, w_max)
    r = run.copy()
    r["x"], r["y"] = r["x"] + dE, r["y"] + dN
    lat0 = float(r["lat"].iloc[0])
    r["lat"] = r["lat"] + dN / GS.M_PER_DEG
    r["lon"] = r["lon"] + dE / (GS.M_PER_DEG * np.cos(np.radians(lat0)))
    r["vel_e"], r["vel_n"] = r["vel_e"] + dve, r["vel_n"] + dvn
    r["speed_gps"] = np.hypot(r["vel_e"], r["vel_n"])
    r["course"] = GS._course(r[["x", "y"]].to_numpy(float), r["heading"].to_numpy(float))
    r["odo_speed"] = np.clip(r["odo_speed"] + w, 0, None)
    r["attack"], r["severity"], r["onset"], r["onset_t"] = "gps_can", w_max, k0, t_on
    r["label"] = (np.arange(len(r)) >= k0).astype(int)
    return r, (t, w), w_max


def build():
    from can.domain import CanDomain
    dom = CanDomain.load(Path(__file__).resolve().parent.parent / "results" / "WP2" / "s7_domain")
    kx = S1.kitti_stream()
    print("attacks in WP1 stream:", sorted(kx["attack"].unique()), flush=True)
    T0 = time.time()
    rows, coord_runs = [], []
    drives = sorted(d for d in GS.SCENE if GS.part_of(d) in ("val", "test"))
    for d in drives:
        ox = GS.load_oxts(d)
        part = GS.part_of(d)
        frames = can_sim.simulate_frames(ox, np.random.default_rng([SEED, 6, 2, int(d)]),
                                         scale=S1.VEHICLE_SCALE + np.random.default_rng([SEED, 6, 4, int(d)]).normal(0, S1.R2_DRIVE_SIGMA))
        can_f = W.to_frame(can_sim.can_motion_estimates(dom, frames))
        kd = kx[kx["drive"] == d]
        for ph in range(GS.PHASES):
            pr = kd[kd["run"].str.startswith(f"{d}/p{ph}/")]
            if not len(pr):
                continue
            clean = pr[pr["run"] == f"{d}/p{ph}/r0"].sort_values("t").reset_index(drop=True)
            grid = clean["t"].to_numpy(float)
            n = len(grid)
            lid = K.forward_speed(W.to_grid(W.to_frame(K.lidar_estimates(clean, d)), grid))
            can_g = W.to_grid(can_f, grid)
            imu_c = W.to_grid(W.to_frame(K.imu_motion_estimates(clean)), grid)
            gps_c = gps_grid(clean, grid)
            base = {"drive": d, "part": part, "phase": ph}
            rows.append(rows_of({**base, "run": f"{d}/p{ph}/r0", "attack": "none", "target": "none", "onset_t": np.nan, "severity": np.nan},
                                grid, {"gps": gps_c, "lidar": lid, "can": can_g, "imu": imu_c}))
            for a in GPS_ATTACKS:
                for rid, ar in pr[pr["attack"] == a].groupby("run"):
                    ar = ar.sort_values("t").reset_index(drop=True)
                    G = {"gps": gps_grid(ar, grid), "lidar": lid, "can": can_g, "imu": W.to_grid(W.to_frame(K.imu_motion_estimates(ar)), grid)}
                    rows.append(rows_of({**base, "run": rid, "attack": a, "target": "gps", "onset_t": float(ar["onset_t"].iloc[0]),
                                         "severity": float(ar["severity"].iloc[0])}, grid, G))
            for ia, a in enumerate(INJECTED):
                rng = np.random.default_rng([SEED, 6, 20, int(d), ph, ia])
                k0 = int(rng.integers(3, max(4, n - 2)))
                t_on = float(grid[min(k0, n - 1)])
                G = {"gps": gps_c, "lidar": lid, "can": can_g, "imu": imu_c}
                if a in LIDAR_ATTACKS:
                    G["lidar"], sev = A.lidar_attack(a, lid, t_on, rng)
                elif a in CAN_ATTACKS:
                    cf = can_f.copy()
                    cf["speed"], sev = A.can_attack(a, cf["t"].to_numpy(float), cf["speed"].to_numpy(float), t_on, rng)
                    G["can"] = W.to_grid(cf, grid)
                else:
                    r2, (tw, w), sev = coordinated(clean, ox, k0, rng)
                    cf = can_f.copy()
                    wc = np.interp(cf["t"].to_numpy(float), tw, w, left=0.0)
                    cf["speed"] = np.clip(cf["speed"].to_numpy(float) + wc, 0, None)
                    G["can"] = W.to_grid(cf, grid)
                    G["gps"] = gps_grid(r2, grid)
                    r2["run"] = f"{d}/p{ph}/gps_can"
                    coord_runs.append(r2)
                rows.append(rows_of({**base, "run": f"{d}/p{ph}/{a}", "attack": a, "target": TARGET[a], "onset_t": t_on, "severity": float(sev)},
                                    grid, G))
        print(f"[{time.time() - T0:5.0f}s] drive {d} {part}", flush=True)
    out = {"rows": pd.concat(rows, ignore_index=True), "gps_can_runs": pd.concat(coord_runs, ignore_index=True)}
    pickle.dump(out, open(CACHE / "s2_kitti.pkl", "wb"))
    print(out["rows"].groupby(["part", "attack"])["run"].nunique(), flush=True)


if __name__ == "__main__":
    {"build": build}[sys.argv[1]]()
