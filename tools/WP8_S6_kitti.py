"""WP8 S6 KITTI builder: per drive and phase the cross-domain residual tables, the GPS-domain tick series and the simulated accelerometer integral of every
vehicle-block run of the S6 evaluation (notes/WP8_v31.md "S6 round 1").

Material: the 13 v3 TRAIN drives (fits only, clean runs) and the 10 V31_val drives (locks/V31_val.json); never an H31 drive (G1 guard on the OXTS folders).
Runs: tools/WP7_S2_veh.vehicle_inputs (seeds [42, 77, ...], onset tick 3): clean, drift, accel_drift, doppler_spoof, meaconing, lidar_scale / bias / yaw,
can_scale / offset / freeze, gps_can. Per (drive, phase, family): the 7 frozen cross-edge residuals r and speeds v (system/cross_runner.py residuals on the
1 Hz grid), the three speed-source series (gps, lidar, can forward speed) for the inertial edges, the GPS-domain tick score and own alarm of the (attacked) GPS run.
Accelerometer: OXTS af (10 Hz) + simulated white noise N(0, 0.05) + per-run constant bias N(0, 0.01) (seeds [42, 31, 1, drive, phase]); A_k = integral over (t_k - 1, t_k].
Output (resumable, one pickle per drive, written to a temp name then renamed): ../data_extra/cache_v3/WP8/S6/kitti_<drive>.pkl
Run from codes_v3/: python -I -u -W ignore tools/WP8_S6_kitti.py [drive ...]   (default: all 23)
"""
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

import WP7_S2_veh as V
import WP8_lib as L8
from can.domain import CanDomain
from common.config import DATA_EXTRA, SEED
from crossdomain import witness as W
from crossdomain.kitti import forward_speed
from gps import stream as GS
from gps.domain import GPSDomain, prepare
from system.cross_runner import residuals

CACHE = DATA_EXTRA / "cache_v3" / "WP8" / "S6"
SOURCES = ("gps", "lidar", "can", "imu")
ACC_NOISE, ACC_BIAS = 0.05, 0.01
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def lock_drives():
    v = json.loads((ROOT / "locks" / "V31_val.json").read_text())["domains"]["kitti_vehicle_block"]
    return list(v["train"]), list(v["val"])


def accel_increments(ox, grid, rng):
    """Simulated accelerometer: OXTS af + bias + white noise, integrated over (t_k - 1, t_k] on the 1 Hz grid -> A (n,), A_0 = 0."""
    t, af = np.asarray(ox["t"], float), np.asarray(ox["af"], float)
    a = af + rng.normal(0, ACC_BIAS) + rng.normal(0, ACC_NOISE, len(af))
    I = np.r_[0.0, np.cumsum(0.5 * (a[1:] + a[:-1]) * np.diff(t))]
    Ig = np.interp(grid, t, I)
    return np.r_[0.0, np.diff(Ig)]


def grids(mes, grid):
    G = {s: W.to_grid(W.to_frame(mes[s]), grid) for s in SOURCES}
    G["gps"], G["lidar"] = forward_speed(G["gps"]), forward_speed(G["lidar"])
    return G


def build_drive(d, dom_can, gdom, keep_attacks):
    L8.assert_not_h31([str(GS.oxts_dir(d))])
    wm, ox = V.wheel_motion(d, dom_can)
    recs, frames = [], []
    for ph in range(GS.PHASES):
        vi = V.vehicle_inputs(d, ph, ox, wm)
        if vi is None:
            continue
        grid = vi["grid"]
        A = accel_increments(ox, grid, np.random.default_rng([SEED, 31, 1, int(d), ph]))
        for fam, df in vi["runs"].items():
            if fam != "none" and not keep_attacks:
                continue
            df = df.copy()
            df["run"] = f"{d}/p{ph}/{fam}"
            frames.append(df)
        for fam, mes in vi["fams"].items():
            if fam != "none" and not keep_attacks:
                continue
            G = grids(mes, grid)
            res = residuals(G)
            names = list(res)
            R = np.column_stack([res[k][0] for k in names])
            Vv = np.column_stack([res[k][1] for k in names])
            spd = np.column_stack([G[s]["speed"].to_numpy(float) for s in ("gps", "lidar", "can")])
            recs.append({"drive": d, "phase": ph, "family": fam, "t": grid, "R": R, "V": Vv, "speed": spd, "A": A, "edge_names": names,
                         "onset_t": float(vi["onset"][fam]), "gps_run": f"{d}/p{ph}/{fam if fam in vi['runs'] else 'none'}"})
    if not frames:
        return recs
    # GPS domain batch scoring of all runs of the drive (the stage_gps recipe)
    g = pd.concat(frames, ignore_index=True).sort_values(["run", "t"], kind="stable").reset_index(drop=True)
    g = prepare(g)
    _, sc, al = gdom.score_arrays(g)
    gps = {}
    for run, idx in g.groupby("run", sort=False).indices.items():
        gps[run] = {"score": sc[idx].astype(np.float32), "alarm": al[idx], "t": g["t"].to_numpy(float)[idx]}
    for r in recs:
        s = gps[r["gps_run"]]
        assert len(s["t"]) == len(r["t"]) and np.allclose(s["t"], r["t"], atol=1e-6), (r["gps_run"], len(s["t"]), len(r["t"]))
        r["gps_score"], r["gps_alarm"] = s["score"], s["alarm"]
    return recs


def main(argv):
    CACHE.mkdir(parents=True, exist_ok=True)
    train, val = lock_drives()
    todo = [(d, False) for d in train] + [(d, True) for d in val]
    if argv:
        todo = [x for x in todo if x[0] in argv]
    dom_can = CanDomain.load(ROOT / "results" / "WP2" / "s7_domain")
    gdom = GPSDomain.load(ROOT / "results" / "WP1" / "frozen_gps")
    for d, keep in todo:
        f = CACHE / f"kitti_{d}.pkl"
        if f.exists():
            log("skip", d)
            continue
        recs = build_drive(d, dom_can, gdom, keep)
        tmp = f.with_suffix(".tmp")
        pickle.dump({"drive": d, "split": "val" if keep else "train", "records": recs}, open(tmp, "wb"), protocol=4)
        tmp.replace(f)
        log("done", d, "val" if keep else "train", len(recs), "records")


if __name__ == "__main__":
    main(sys.argv[1:])
