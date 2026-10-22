"""WP3 S2 exploration (train scans only): ring structure and azimuth sampling of KITTI HDL-64E scans."""
import numpy as np
from lidar.data import drives_of, scan_files, load

d = drives_of("train")[0]
fs = scan_files(d)
p = load(fs[10])
x, y, z, it = p.T
r = np.hypot(x, y); rr = np.linalg.norm(p[:, :3], axis=1)
el = np.degrees(np.arctan2(z, r)); az = np.degrees(np.arctan2(y, x))
print(len(p), "pts; elev", el.min(), el.max(), "range", rr.min(), rr.max(), "int", it.min(), it.max())
for lo, hi in ((0, 5), (5, 10), (10, 20), (20, 40), (40, 80)):
    m = (rr >= lo) & (rr < hi)
    h, e = np.histogram(el[m], bins=np.arange(-25, 3, 0.05))
    pk = (h > 0.25 * h.max()) & (h >= np.r_[0, h[:-1]]) & (h >= np.r_[h[1:], 0])
    print(lo, hi, m.sum(), "peaks", pk.sum())
h, e = np.histogram(el, bins=np.arange(-25, 3, 0.02))
c = 0.5 * (e[1:] + e[:-1])
pk = np.flatnonzero((h > 150) & (h >= np.r_[0, h[:-1]]) & (h > np.r_[h[1:], 0]))
print(len(pk), np.round(c[pk], 2))
# azimuth step on a single ring (pick the strongest peak)
k = pk[np.argmax(h[pk])]
m = np.abs(el - c[k]) < 0.1
a = np.sort(az[m]); da = np.diff(a)
print("ring el", c[k], "n", m.sum(), "az step quantiles", np.round(np.quantile(da, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]), 4))
# z/range: do far points follow ring angle?
