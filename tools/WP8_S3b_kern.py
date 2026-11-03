"""WP8 S3b kernel-level equality (numba vs numpy) on scans of V31_val drives; prints mismatches and warm-up/steady timing per kernel.
Run: python -u -W ignore tools/WP8_S3b_kern.py [--every 20]"""
import argparse, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import WP8_S3_lib as L
from lidar import fast as F, background as B
from lidar.data import load, scan_files
from lidar.domain31 import Domain31

ap = argparse.ArgumentParser(); ap.add_argument("--every", type=int, default=20); a = ap.parse_args()
dom = Domain31.load(L.ROOT / "results/WP8/S3/frozen_lidar31"); st = dom.stats
bad = {"assign": 0, "cluster": 0, "img": 0, "ground": 0}; n = 0; tm = {"np": {}, "nb": {}}
def run(flag, key, f):
    F.set_numba(flag); t = time.perf_counter(); r = f(); tm["nb" if flag else "np"].setdefault(key, []).append(time.perf_counter() - t); return r
t0 = time.perf_counter(); F.set_numba(True)
p0 = load(scan_files(L.VAL[0])[0]); F.cluster_labels(p0, st.prm); F.assign_fast(st.table, p0); F.ImgFast(p0, st.edges)
print("warm-up (compile or cache load) s:", round(time.perf_counter() - t0, 2))
for d in L.VAL:
    for f in scan_files(d)[::a.every]:
        pts = load(f); rho = np.linalg.norm(pts[:, :3], axis=1); n += 1
        lab = {fl: run(fl, "cluster", lambda: F.cluster_labels(pts, st.prm)) for fl in (False, True)}
        bad["cluster"] += int(not np.array_equal(lab[False], lab[True]))
        keep = (rho >= F.R_MARGIN) | (lab[False] >= 0)
        g = {fl: run(fl, "ground", lambda: F.ground_height_fast(pts)) for fl in (False, True)}
        bad["ground"] += int(not np.array_equal(g[False], g[True]))
        A = {fl: run(fl, "assign", lambda: F.assign_fast(st.table, pts, keep=keep, rho=rho)) for fl in (False, True)}
        bad["assign"] += int(any(not np.array_equal(A[False][k], A[True][k]) for k in ("k", "res", "cm", "margin")))
        I = {fl: run(fl, "img", lambda: F.ImgFast(pts, st.edges)) for fl in (False, True)}
        bad["img"] += int(any(not np.array_equal(getattr(I[False], k), getattr(I[True], k)) for k in ("cnt", "amin", "nmin")))
print("scans", n, "mismatching scans per kernel", bad)
for fl in ("np", "nb"): print(fl, {k: round(1000 * float(np.median(v)), 1) for k, v in tm[fl].items()}, "ms median")
