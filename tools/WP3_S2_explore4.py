import numpy as np
from lidar import geometry as G
from lidar.data import drives_of, scan_files, load
from common.config import RESULTS
T = G.RingTable.load(RESULTS / "WP3/S2/ring_table.json")
res = {}
for d in drives_of("val") + drives_of("train")[:3]:
    for f in scan_files(d)[10::40]:
        p = load(f); a = T.assign(p)
        az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
        for daz in (0.005, 0.01, 0.02, 0.04):
            for lo in (0, 15):
                m = a["rho"] >= lo
                res.setdefault((daz, lo), []).append(G.count_duplicates(az[m], a["rho"][m], a["k"][m], daz=daz))
for k, v in res.items(): print(k, "mean", np.mean(v), "max", np.max(v), "frac>0", np.mean(np.array(v) > 0))
