"""WP8 S7 LiDAR: per-scan scores of the FROZEN v3 LidarDomain stack and the FROZEN v3.1 Domain31 (frozen_lidar31) on the 13 H31 drives: clean scans, the S3/S4 attack set
(seeds [83, drive, i], stride 3, attacked scan vs the CLEAN previous scan, 9 kinds) and persistent PointDrop episodes (3 per drive, 30 scans, seeds [101, drive]; later steps vs the attacked previous scan).
One pass per scan: lidar.fast ScanStats (numba kernels, voxel-0.1 clustering) -> (a) Domain31.raw_from_records / evidence = v3.1; (b) the frozen v3 layer objects (results/WP3/S9/frozen_lidar:
L1 / L2a / L2c / L2d raw scores, stack.stat, stack.threshold, stack.cal) on the same statistics = v3. The fast statistics equal the v3 statistics (S3 equivalence: L1/L2c/L2d bit-identical, L2a within the voxel
clustering difference, 0 alarm differences on 150 scans); WP8_S7_lidar_check.py repeats that check on a seeded sample of H31 scans with the literal frozen v3 LidarDomain (labelled sample check).
Output (resumable, temp name then rename): results/WP8/S7/parts/lidar_<kind>_<drive>.pkl (DataFrame, one row per scan), assembled by --assemble into ../data_extra/cache_v3/WP8/S7/lidar.pkl.
Run: python -u -W ignore tools/WP8_S7_lidar.py [--procs 3] [--assemble]"""
import argparse
import pickle
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np
import pandas as pd

LAYERS = ("L1", "L2a", "L2c", "L2d")
_G = {}


def objs():
    if not _G:
        S7.patch_h31_paths()
        import WP8_S3_lib as L
        from lidar import fast
        from lidar.domain import COLS, LidarDomain
        from lidar.domain31 import Domain31
        from lidar.fast import ScanStats
        fast.set_numba(True)
        _G.update(L=L, COLS=COLS, d31=Domain31.load(S7.ROOT / "results" / "WP8" / "S3" / "frozen_lidar31"),
                  v3=LidarDomain.load(S7.ROOT / "results" / "WP3" / "S9" / "frozen_lidar"), ss=ScanStats(L.table(), L.PRM), table=L.table(), calib=L.calib())
    return _G


def score_scan(pts, pose, prev, t, sid):
    """-> dict of the v3.1 and v3 scores of one scan from one set of statistics, and the current range image for the next scan."""
    from lidar import s4_eval as E4
    g = objs()
    d31, v3, L = g["d31"], g["v3"], g["L"]
    l1, tl, pair, cur = g["ss"].compute(pts, pose, prev)
    a = d31.scorer.scan_stats(tl["range"].to_numpy(), tl["n_points"].to_numpy(), tl["int_mean"].to_numpy())
    raw = d31.raw_from_records(l1, a, pair, d31.scorer.n_valid(tl["range"].to_numpy(), tl["n_points"].to_numpy()))
    comb, per = d31.evidence(raw, t, sid, first=prev is None)
    row = {"v31_score": float(comb.score), "v31_alarm": bool(comb.alarm), "v31_stat": float(comb.details["stat"])}
    for lay in LAYERS:
        row[f"v31_raw_{lay}"] = float(raw[lay])
        row[f"v31_rank_{lay}"] = float(per[lay].score)
        row[f"v31_fire_{lay}"] = bool(per[lay].alarm)
    tl2 = tl.copy()
    tl2.insert(0, "scan", "s")
    tl2["ring_min"], tl2["ring_max"], tl2["az_span"] = 0.0, 7.0, 2.0 - 0.1728
    a2 = E4.scan_frame(v3.model, tl2, pd.DataFrame({"scan": ["s"]}))
    r3 = {"L1": float(v3.layers["L1"].raw_scores(pd.DataFrame([dict(zip(L.L1_KEYS, l1))]))[0]), "L2a": float(v3.layers["L2a"].raw_scores(a2)[0])}
    if pair is None:
        r3["L2c"] = r3["L2d"] = 0.0
    else:
        s6 = pd.DataFrame([pair])
        r3["L2c"], r3["L2d"] = float(v3.layers["L2c"].raw_scores(s6)[0]), float(v3.layers["L2d"].raw_scores(s6)[0])
    stat3 = float(v3.stack.stat(pd.DataFrame([{c: r3[c[4:]] for c in g["COLS"]}]))[0])
    row.update({"v3_stat": stat3, "v3_alarm": bool(stat3 >= v3.stack.threshold), "v3_score": float(v3.stack.cal.transform(np.array([stat3]))[0])})
    row.update({f"v3_raw_{lay}": r3[lay] for lay in LAYERS})
    row["n_pts"] = int(len(pts))
    return row, cur


def job(task):
    kind, d = task
    f = S7.PARTS / f"lidar_{kind}_{d}.pkl"
    if f.exists():
        return kind, d, "skip"
    t0 = time.time()
    try:
        from lidar import ego
        from lidar.data import load, scan_files
        from lidar.fast import PrevScan
        from lidar.features import apply_attack, attack_params
        from lidar.s4_build import attack_cases
        g = objs()
        files, pose = scan_files(d), ego.poses(d)
        rows = []
        if kind == "clean":
            prev = None
            for i, fp in enumerate(files):
                pts = load(fp)
                r, cur = score_scan(pts, pose[i], prev, 0.0, i)
                rows.append(dict(kind="clean", drive=d, i=i, attack="", ep=-1, step=-1, **r))
                prev = PrevScan(pts, pose[i], img=cur)
        elif kind == "att":
            for i in range(1, len(files), 3):
                pts = load(files[i])
                rng = np.random.default_rng([83, int(d), i])
                prev = PrevScan(load(files[i - 1]), pose[i - 1])
                for name, att, idx in attack_cases(pts, rng, g["table"], g["calib"]):
                    r, _ = score_scan(att, pose[i], prev, 0.0, i)
                    rows.append(dict(kind="att", drive=d, i=i, attack=name, ep=-1, step=-1, n_inj=0 if idx is None else int(len(idx)), **r))
        else:
            rng = np.random.default_rng([101, int(d)])
            for j in range(g["L"].PD_EP_PER_DRIVE):
                p = attack_params("PointDrop", rng)
                s0 = int(rng.integers(1, max(2, len(files) - g["L"].EP_LEN)))
                prev = PrevScan(load(files[s0 - 1]), pose[s0 - 1])
                for k in range(s0, min(len(files), s0 + g["L"].EP_LEN)):
                    att = apply_attack("PointDrop", load(files[k]), p, rng)
                    r, cur = score_scan(att, pose[k], prev, 0.0, k)
                    rows.append(dict(kind="pdep", drive=d, i=k, attack="ep_PointDrop", ep=j, step=k - s0 + 1, **r))
                    prev = PrevScan(att, pose[k], img=cur)
        S7.PARTS.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".tmp")
        pd.to_pickle(pd.DataFrame(rows), tmp)
        tmp.replace(f)
        return kind, d, f"{time.time() - t0:.0f}s {len(rows)} scans"
    except Exception:
        import traceback
        return kind, d, "FAILED " + traceback.format_exc()


def assemble():
    from gps import stream as GS
    S7.patch_h31_paths()
    kinds = ["IntensitySpoof", "PointDrop", "ph_budget_far", "ph_budget_near", "ph_replace_far", "ph_replace_near"]
    out = {"drives": {}, "kinds": kinds}
    for d in sorted(S7.kitti_drives()):
        df = pd.concat([pd.read_pickle(S7.PARTS / f"lidar_{k}_{d}.pkl") for k in ("clean", "att", "pdep")], ignore_index=True)
        df = df[(df["kind"] != "clean") | (df["i"] >= 1)].reset_index(drop=True)
        tox = np.asarray(GS.load_oxts(d)["t"], float)
        t = tox[np.clip(df["i"].to_numpy(int), 0, len(tox) - 1)]
        rec = {"t_oxts": tox, "stratum": S7.kitti_drives()[d][1], "frame": df}
        for tag, pre in (("L100", "v31"), ("V3", "v3")):
            lay = np.column_stack([df[f"{pre}_raw_{l}"].to_numpy(float) for l in LAYERS]).astype(np.float32)
            rec[tag] = {"kind": df["kind"].astype(str).to_numpy(), "attack": df["attack"].astype(str).to_numpy(), "i": df["i"].to_numpy(int), "ep": df["ep"].to_numpy(int),
                        "step": df["step"].to_numpy(int), "t": t, "score": df[f"{pre}_score"].to_numpy(np.float32), "alarm": df[f"{pre}_alarm"].to_numpy(bool), "layers": lay,
                        "stat": df[f"{pre}_stat"].to_numpy(np.float64)}
        out["drives"][d] = rec
    S7.CACHE.mkdir(parents=True, exist_ok=True)
    tmp = S7.CACHE / "lidar.tmp"
    pickle.dump(out, open(tmp, "wb"), protocol=4)
    tmp.replace(S7.CACHE / "lidar.pkl")
    print("assembled", {d: len(r["frame"]) for d, r in out["drives"].items()}, flush=True)


def _init():
    S7.open_guard()
    S7.patch_h31_paths()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("--assemble", action="store_true")
    a = ap.parse_args()
    if a.assemble:
        assemble()
        sys.exit(0)
    _init()
    from lidar.data import scan_files
    ids = sorted(S7.kitti_drives())
    size = {d: len(scan_files(d)) for d in ids}
    tasks = [("att", d) for d in ids] + [("pdep", d) for d in ids] + [("clean", d) for d in ids]
    tasks.sort(key=lambda t: -size[t[1]] * (3.5 if t[0] == "att" else 1.0 if t[0] == "clean" else 0.6))
    print(time.strftime("%H:%M:%S"), len(tasks), "tasks", flush=True)
    with Pool(a.procs, initializer=_init) as pool:
        for kind, d, msg in pool.imap_unordered(job, tasks):
            print(time.strftime("%H:%M:%S"), kind, d, msg, flush=True)
    print("done", flush=True)
