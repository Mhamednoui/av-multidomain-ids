import numpy as np
from lidar.data import drives_of, scan_files, load
np.set_printoptions(linewidth=200, suppress=True)
p = load(scan_files("0002")[10])
az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
w = np.flatnonzero(np.abs(np.diff(az)) > 100); ids = np.r_[0, w + 1, len(p)]
rr = np.linalg.norm(p[:, :3], axis=1)
for k in range(0, 65, 1):
    s = slice(ids[k], ids[k+1]); z = p[s, 2]; r = rr[s]; a = az[s]
    el = np.degrees(np.arcsin(z / r))
    print(k, ids[k+1]-ids[k], "az %.0f..%.0f" % (a[0], a[-1]), "el med %.3f  q10 %.3f q90 %.3f" % (np.median(el), *np.quantile(el, [0.1, 0.9])))
