"""WP7 S2 LiDAR pass: the FROZEN LiDAR domain (system/lidar_runner.py, results/WP3/S9/frozen_lidar) streamed scan by scan over the 7 KITTI TEST drives.
Jobs (resumable, one pickle each in ../data_extra/cache_v3/WP7/S2_lidar/):
  clean <drive>             all scans of the drive, no attack (the clean LiDAR stream of the K vehicle blocks and of the clean timelines)
  scan <drive> <kind>       persistent per-scan attack: scans 29..W1-1 streamed (29 = clean previous scan), scans i >= 31 with i % 3 == 1 attacked with the WP3 S4 generator
                            (seed [83, drive, i], lidar.s4_build.attack_cases, single-return), W1 = min(n_scans, 180); kinds: ph_replace_near ph_budget_near ph_replace_far
                            ph_budget_far PointDrop IntensitySpoof
  ep <drive> sensor|world   ALL persistent 30-scan phantom episodes of the drive (WP3 S4 / S9 generators and seeds [89, drive] / [97, drive], 3 per kind, 4 kinds): per episode
                            scans s0-1 (clean previous) .. s0+39 streamed, scans s0..s0+29 attacked
Per scan: OXTS time, combined score / alarm, 4 layer scores / alarms, compute time (ns, from the runner's LatencyLog). No threshold, ECDF or layer is touched.
Usage: python -u -W ignore tools/WP7_S2_lidar.py [--procs 4] [--smoke] [clean scan ep]       Output: ../data_extra/cache_v3/WP7/S2_lidar/*.pkl, results/WP7/logs/S2_lidar.log
--smoke: validation drive 0011, 6 scans, to test the plumbing without reading test scans.
"""
import pickle
import sys
import time
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np

from common.config import DATA_EXTRA
from lidar import ego
from lidar import phantom as P
from lidar.background_build import world_params
from lidar.data import TEST, load, scan_files
from lidar.domain import LAYERS
from lidar.raycast import eval_params
from lidar.s4_build import EP_KINDS, EP_LEN, attack_cases
from gps.stream import load_oxts
from system.lidar_runner import LidarRunner

FROZEN = ROOT / "results" / "WP3" / "S9" / "frozen_lidar"
OUT = DATA_EXTRA / "cache_v3" / "WP7" / "S2_lidar"
KINDS = ["ph_replace_near", "ph_budget_near", "ph_replace_far", "ph_budget_far", "PointDrop", "IntensitySpoof"]
START, STRIDE, MAX_WINDOW, POST = 30, 3, 150, 10
_R = None


def runner():
    global _R
    if _R is None:
        _R = LidarRunner(FROZEN)
    return _R


class Rec:
    """Collects per-scan results of one stream."""

    def __init__(self, key, t):
        self.key, self.t, self.rows = key, t, []
        runner().reset(key)

    def push(self, idx, pts, pose, attacked=False, tag=""):
        r = runner()
        n0 = len(r.latency.ns)
        ev = r.push({"points": pts, "pose": pose, "t": float(self.t[idx]), "sample_id": f"{self.key}/{idx}"})
        comb, lay = ev[0], ev[1:]
        self.rows.append({"idx": int(idx), "t": float(self.t[idx]), "score": float(comb.score), "alarm": bool(comb.alarm), "layers": [float(e.score) for e in lay],
                          "layer_alarm": [bool(e.alarm) for e in lay], "ns": int(r.latency.ns[n0]), "attacked": bool(attacked), "tag": tag, "n_points": int(len(pts)),
                          "reason": comb.reason if comb.alarm else ""})

    def result(self, **kw):
        return {"key": self.key, "rows": self.rows, **kw}


def job_clean(d, n_max=None):
    files, pose, t = scan_files(d), ego.poses(d), np.asarray(load_oxts(d)["t"], float)
    rec = Rec(f"{d}/clean", t)
    for i in range(len(files) if n_max is None else min(n_max, len(files))):
        rec.push(i, load(files[i]), pose[i])
    return rec.result(drive=d, kind="clean")


def job_scan(d, kind, w1_max=None):
    files, pose, t = scan_files(d), ego.poses(d), np.asarray(load_oxts(d)["t"], float)
    dom = runner().dom
    w1 = min(len(files), START + MAX_WINDOW) if w1_max is None else w1_max
    rec = Rec(f"{d}/{kind}", t)
    for i in range(START - 1, w1):
        pts = load(files[i])
        att = i >= START + 1 and i % STRIDE == 1
        if att:
            rng = np.random.default_rng([83, int(d), i])
            for name, a, _ in attack_cases(pts, rng, dom.table, dom.calib):
                if name == kind:
                    pts = a
                    break
            else:
                raise ValueError(kind)
        rec.push(i, pts, pose[i], attacked=att, tag=kind if att else "")
    return rec.result(drive=d, kind=kind, start=START, window_end=w1)


def job_ep(d, world, max_ep=None):
    """All episodes of drive d (rng draws identical to lidar.s4_build.drive_episodes / lidar.s9_build.drive_episodes_world)."""
    files, pose, t = scan_files(d), ego.poses(d), np.asarray(load_oxts(d)["t"], float)
    dom = runner().dom
    rng = np.random.default_rng([97 if world else 89, int(d)])
    eps = []
    for mode, band in EP_KINDS:
        for j in range(3):
            p = eval_params(rng, band)
            s0 = int(rng.integers(1, max(2, len(files) - EP_LEN)))
            kind = f"ep{'W' if world else ''}_{mode}_{band}"
            if max_ep is not None and len(eps) >= max_ep:
                return {"drive": d, "world": world, "episodes": eps}
            rec = Rec(f"{d}/{kind}/{j}", t)
            rec.push(s0 - 1, load(files[s0 - 1]), pose[s0 - 1])
            q = None
            for k in range(s0, min(len(files), s0 + EP_LEN)):
                pts = load(files[k])
                rays = P.prepare(pts, dom.table)
                pk = p if (not world or q is None) else world_params(q, pose[s0], pose[k])
                att, n, qk, idx = P.phantom(pts, rays, pk, rng, mode, dom.calib)
                if q is None:
                    q = qk
                rec.push(k, att, pose[k], attacked=True, tag=kind)
            for k in range(s0 + EP_LEN, min(len(files), s0 + EP_LEN + POST)):
                rec.push(k, load(files[k]), pose[k])
            eps.append(rec.result(drive=d, kind=kind, ep=j, s0=s0, world=world, n_scans=len(files)))
    return {"drive": d, "world": world, "episodes": eps}


def run_job(args):
    kind, d, extra, smoke = args
    name = f"{kind}_{d}" + (f"_{extra}" if extra else "") + ("_smoke" if smoke else "")
    f = OUT / f"{name}.pkl"
    if f.exists():
        return name, -1.0
    t0 = time.time()
    if kind == "clean":
        res = job_clean(d, 6 if smoke else None)
    elif kind == "scan":
        res = job_scan(d, extra, START + 8 if smoke else None)
    else:
        res = job_ep(d, extra == "world", 1 if smoke else None)
    pickle.dump(res, open(f.with_suffix(".tmp"), "wb"))
    f.with_suffix(".tmp").replace(f)
    return name, time.time() - t0


def jobs(which, drives, smoke):
    js = []
    for d in drives:
        n = len(scan_files(d))
        if "clean" in which:
            js.append((n, ("clean", d, "", smoke)))
        if "scan" in which:
            js += [(min(n - START, MAX_WINDOW), ("scan", d, k, smoke)) for k in KINDS]
        if "ep" in which:
            js += [(12 * (EP_LEN + POST + 1), ("ep", d, w, smoke)) for w in ("sensor", "world")]
    js.sort(key=lambda x: -x[0])
    return [j for _, j in js]


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    smoke = "--smoke" in sys.argv
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 4
    which = [a for a in sys.argv[1:] if a in ("clean", "scan", "ep")] or ["clean", "scan", "ep"]
    drives = ["0011"] if smoke else TEST
    todo = jobs(which, drives, smoke)
    if smoke:
        todo = todo[:3]
    print(f"{len(todo)} jobs, {procs} procs, smoke={smoke}", flush=True)
    t0 = time.time()
    with Pool(procs) as pool:
        for name, sec in pool.imap_unordered(run_job, todo):
            print(f"[{time.time() - t0:7.0f}s] {name} {'skipped' if sec < 0 else f'{sec:.0f}s'}", flush=True)
    print("done", flush=True)
