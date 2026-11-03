"""WP8 S3b stage profile of the numpy Domain31 path (diagnostic)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from lidar import ego, fast as F, background as B, geometry as G
from lidar.data import load, scan_files
from lidar.domain31 import Domain31
dom = Domain31.load("results/WP8/S3/frozen_lidar31")
st = dom.stats
files = scan_files("0011"); pose = ego.poses("0011")
tm = {}
def T(k, f):
    t = time.perf_counter(); r = f(); tm.setdefault(k, []).append(time.perf_counter() - t); return r
for i in range(20, 35):
    pts = load(files[i]); prev = load(files[i-1])
    lab = T("cluster", lambda: F.cluster_labels(pts, st.prm))
    rho = np.linalg.norm(pts[:, :3], axis=1)
    asg = T("assign", lambda: F.assign_fast(st.table, pts, keep=(rho >= F.R_MARGIN) | (lab >= 0), rho=rho))
    T("l1", lambda: G.l1_stats(pts, st.table, asg=asg))
    T("tiles", lambda: F.make_tiles(pts, lab, asg["k"]))
    T("img", lambda: F.ImgFast(pts, st.edges))
    T("moved", lambda: B.moved(prev, pose[i-1], pose[i]) if False else None)
    ps = F.PrevScan(prev, pose[i-1])
    T("pair", lambda: st.pair(ps, pts, pose[i]))
    T("total", lambda: st.compute(pts, pose[i], F.PrevScan(prev, pose[i-1])))
for k, v in tm.items(): print(k, round(1000*float(np.median(v)), 1), "ms")
print(len(pts))
