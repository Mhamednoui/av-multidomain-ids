"""WP6 S5b coupling test, stage 1 (TEST drives; no choice depends on it): LiDAR L2c / L2d statistics when the ego pose follows a spoofed GNSS.

Why: the frozen LiDAR domain moves the previous scan into the current frame with the OXTS ego pose (lidar.background.moved). OXTS is a GNSS / INS solution,
so a GPS attack can bend the pose and make L2c (missing returns) / L2d (surfaces in free space) fire on a clean point cloud -> induced LiDAR alarms, wrong blame.
Attack model (worst case, stated): the INS position follows the spoofed GNSS position 1:1 (offset added to x, y of the pose of every scan, linear interpolation of
the 1 Hz offset at the scan time), the yaw is unchanged (IMU). Offsets = the exact WP1 KITTI runs: gps.stream.build_kitti is re-run with the same generator
(identical draws, asserted against the WP1 stream) while recording the receiver noise of every run, offset = reported - true - receiver noise (drift, accel_drift,
doppler_spoof, meaconing); gps_can (WP6 S2 coordinated runs) offset = run minus its clean r0 run of the same drive and phase.
Only scans whose pose offset changes against the previous scan are recomputed; the others keep the stored clean raw scores (WP3 S9 final frames). A zero-offset
recompute of the first scans of every drive is asserted equal to the stored raw L2c / L2d.
Usage: python -u -W ignore tools/WP6_S5b_coupling.py      Output: ../data_extra/cache_v3/WP6/s5b_coupling/<drive>.pkl (+ offsets.pkl)
"""
import pickle
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED  # noqa: E402
import WP6_S5b_lidar as LB  # noqa: E402

OUT = LB.CACHE / "s5b_coupling"
GPS_FAMS = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
N_CHECK = 8


def log(*a):
    print(*a, flush=True)


def offsets():
    """run name -> dict(family, t (1 Hz), off (n, 2) attack offset east / north m, severity, onset_t) for the test GPS attack runs and gps_can runs."""
    from gps import stream as GS
    import WP6_S1_kitti as S1
    noise = []
    orig = GS.receiver_noise

    def rec(n, rng, *a, **k):
        e = orig(n, rng, *a, **k)
        noise.append(e.copy())
        return e
    GS.receiver_noise = rec
    try:
        df = GS.build_kitti(np.random.default_rng(SEED), new_attacks=GS.ATTACKS_NEW)
    finally:
        GS.receiver_noise = orig
    runs = list(pd.unique(df["run"]))
    assert len(runs) == len(noise), (len(runs), len(noise))
    ref = S1.kitti_stream()
    out = {}
    clean_xy = {}
    for r, e in zip(runs, noise):
        g = df[df["run"] == r]
        if g["part"].iloc[0] != "test":
            continue
        a = str(g["attack"].iloc[0])
        q = ref[ref["run"] == r]
        assert len(q) == len(g) and np.allclose(q["x"].to_numpy(), g["x"].to_numpy()) and np.allclose(q["y"].to_numpy(), g["y"].to_numpy()), r
        if a == "none":
            clean_xy[r] = g[["x", "y"]].to_numpy(float)
        if a not in GPS_FAMS:
            continue
        off = g[["x", "y"]].to_numpy(float) - g[["x_true", "y_true"]].to_numpy(float) - e
        k0 = int(g["onset"].iloc[0])
        assert np.abs(off[:k0]).max() < 1e-6, r
        out[r] = {"family": a, "drive": g["drive"].iloc[0], "t": g["t"].to_numpy(float), "off": off, "severity": float(g["severity"].iloc[0]), "onset_t": float(g["onset_t"].iloc[0])}
    co = pickle.load(open(LB.CACHE / "s2_kitti.pkl", "rb"))["gps_can_runs"]
    co = co[co["part"] == "test"]
    for r, g in co.groupby("run", sort=True):
        d, ph, _ = r.split("/")
        base = clean_xy[f"{d}/{ph}/r0"]
        off = g[["x", "y"]].to_numpy(float) - base
        k0 = int(g["onset"].iloc[0])
        assert np.abs(off[:k0]).max() < 1e-6, r
        out[r] = {"family": "gps_can", "drive": d, "t": g["t"].to_numpy(float), "off": off, "severity": float(g["severity"].iloc[0]), "onset_t": float(g["onset_t"].iloc[0])}
    return out


def _pair(prev_pts, pp, raw_prev, cur, pc, edges):
    from lidar import background as B
    from lidar import track as T
    pred = B.Img(B.moved(prev_pts, pp, pc), edges)
    row = B.miss_stats(cur, pred)
    row.update(T.track_stats(cur, pred, raw_prev))
    row["disp"] = float(np.hypot(*(np.asarray(pc[:2]) - np.asarray(pp[:2]))))
    return row


def drive_job(args):
    d, runs = args
    f = OUT / f"{d}.pkl"
    if f.exists():
        return d, "cached"
    from lidar import background as B
    from lidar import ego
    from lidar.data import load, scan_files
    dom = LB.load_domain()
    fin = pickle.load(open(LB.S9C / "final_frames_s9.pkl", "rb"))["clean"]
    c = fin[fin.drive == d].set_index("idx")
    files, pose = scan_files(d), ego.poses(d)
    ts = LB.scan_times(d) - LB.scan_times(d)[0]
    edges = B.ring_edges(dom.table)
    pts = [load(x) for x in files]
    imgs = [B.Img(p, edges) for p in pts]
    # zero-offset check against the stored clean raw scores
    rows = [_pair(pts[i - 1], pose[i - 1], imgs[i - 1], imgs[i], pose[i], edges) for i in range(1, N_CHECK + 1)]
    sf = pd.DataFrame(rows)
    for x in ("L2c", "L2d"):
        mine = dom.layers[x].raw_scores(sf)
        dif = float(np.abs(mine - c.loc[list(range(1, N_CHECK + 1)), f"raw_{x}"].to_numpy(float)).max())
        assert dif < 1e-9, (d, x, dif)
    out = {"drive": d, "runs": {}, "check_max_diff": 0.0}
    idx = np.array(sorted(c.index), int)
    for name, r in runs:
        ox = np.column_stack([np.interp(ts, r["t"], r["off"][:, j], left=0.0, right=r["off"][-1, j]) for j in range(2)])
        P = pose.copy()
        P[:, :2] = P[:, :2] + ox
        ch = np.r_[False, np.abs(np.diff(ox, axis=0)).max(axis=1) > 1e-9]
        raw = {x: c.loc[idx, f"raw_{x}"].to_numpy(float).copy() for x in ("L2c", "L2d")}
        sel = [j for j, i in enumerate(idx) if ch[i]]
        if sel:
            sf = pd.DataFrame([_pair(pts[idx[j] - 1], P[idx[j] - 1], imgs[idx[j] - 1], imgs[idx[j]], P[idx[j]], edges) for j in sel])
            for x in ("L2c", "L2d"):
                raw[x][sel] = dom.layers[x].raw_scores(sf)
        step = np.hypot(*np.diff(ox, axis=0).T)
        out["runs"][name] = {"family": r["family"], "idx": idx, "raw_L2c": raw["L2c"], "raw_L2d": raw["L2d"], "n_recomputed": len(sel), "severity": r["severity"],
                             "onset_t": r["onset_t"], "max_offset_m": float(np.hypot(*ox.T).max()), "max_step_m": float(step.max()) if len(step) else 0.0}
    pickle.dump(out, open(f, "wb"))
    return d, len(runs)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fo = OUT / "offsets.pkl"
    if fo.exists():
        off = pickle.load(open(fo, "rb"))
    else:
        off = offsets()
        pickle.dump(off, open(fo, "wb"))
    log("attack runs", len(off), pd.Series([v["family"] for v in off.values()]).value_counts().to_dict())
    jobs = [(d, [(n, r) for n, r in sorted(off.items()) if r["drive"] == d]) for d in LB.TEST]
    jobs.sort(key=lambda j: -len(LB.scan_times(j[0])))
    with Pool(4) as p:
        for d, n in p.imap_unordered(drive_job, jobs):
            log("drive", d, n)
    log("done")


if __name__ == "__main__":
    main()
