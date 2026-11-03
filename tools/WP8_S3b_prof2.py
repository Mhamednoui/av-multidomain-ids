"""WP8 S3b profile of the pieces around the compiled kernels (diagnostic)."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from lidar import fast as F, fast_nb as N, geometry as G, segment as S
from lidar.data import load, scan_files
from lidar.domain31 import Domain31
dom = Domain31.load("results/WP8/S3/frozen_lidar31"); st = dom.stats; F.set_numba(True)
files = scan_files("0011"); tm = {}
def T(k, f):
    t = time.perf_counter(); r = f(); tm.setdefault(k, []).append(time.perf_counter() - t); return r
for i in range(20, 40):
    pts = load(files[i]); prm = dict(S.PARAMS, **st.prm)
    T("rho", lambda: np.linalg.norm(pts[:, :3], axis=1)); T("azbin", lambda: G.az_bin(pts))
    gh = T("ground", lambda: F.ground_height_fast(pts))
    h = pts[:, 2] - gh; rxy = T("hypot", lambda: np.hypot(pts[:, 0], pts[:, 1]))
    sel = T("sel", lambda: np.flatnonzero((h > prm["h0"]) & (h < prm["h_max"]) & (rxy < prm["r_max"])))
    xyz = pts[sel, :3].astype(np.float64)
    T("kern_cluster", lambda: N.cluster_vox_nb(xyz, 0.6, 5, 0.1))
    T("cluster_all", lambda: F.cluster_labels(pts, st.prm))
    T("img", lambda: F.ImgFast(pts, st.edges))
print(len(sel))
for k, v in tm.items(): print(k, round(1000*float(np.median(v)), 1))
