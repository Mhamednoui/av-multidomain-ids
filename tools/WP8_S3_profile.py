"""WP8 S3 profile of the v3 LiDAR domain per scan (where do the 1.8 s go). Read-only diagnostic on one V31_val drive."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from lidar import ego
from lidar.data import load, scan_files
from lidar.domain import LidarDomain
from lidar import segment as S, geometry as G, background as B
from lidar.s4_build import tiles
from lidar.background_build import pair_row

d = LidarDomain.load("results/WP3/S9/frozen_lidar")
files = scan_files("0011"); pose = ego.poses("0011")
tm = {}
def T(k, f):
    t = time.perf_counter(); r = f(); tm.setdefault(k, []).append(time.perf_counter() - t); return r
for i in range(20, 30):
    pts, prev = load(files[i]), load(files[i - 1])
    T("load", lambda: load(files[i]))
    tab, lab, h = T("segment", lambda: S.segment(pts, d.table, d.prm, return_labels=True))
    T("ground", lambda: S.height_above_ground(pts, d.prm["ground"]))
    T("assign", lambda: d.table.assign(pts))
    T("l1_stats", lambda: G.l1_stats(pts, d.table))
    T("pair_row", lambda: pair_row(prev, pose[i-1], pts, pose[i], d.edges))
    T("total", lambda: d.score_scan(pts, pose[i], (prev, pose[i-1])))
for k, v in tm.items():
    print(k, round(float(np.median(v)), 4))
print("params", d.prm)
