"""WP1 S0: verify D15 OSM extract loads and covers every KITTI drive. Run with python -I.
Output: results/WP1/osm_verify.json."""
import json, glob, os, collections
import numpy as np
from scipy.spatial import cKDTree
P = r"C:\Users\nouir\PFE\data_extra\D15_osm\karlsruhe_highways.json"
d = json.load(open(P, encoding="utf-8"))
els = d["elements"]
nodes = {e["id"]: (e["lat"], e["lon"]) for e in els if e["type"] == "node"}
ways = [e for e in els if e["type"] == "way"]
hw = collections.Counter(w["tags"]["highway"] for w in ways)
bb = json.load(open(r"C:\Users\nouir\PFE\codes_v3\results\WP1\osm_bbox.json"))
la0, la1, lo0, lo1 = bb["bbox"]; m0 = bb["bbox_margin_1km"]
pts = np.array(list(nodes.values())); lat0 = np.radians((la0 + la1) / 2)
def xy(a): return np.c_[(a[:, 0]) * 111320.0, a[:, 1] * 111320.0 * np.cos(lat0)]
# densify way segments every ~5 m so distance-to-node approximates distance-to-road
dense = []
for w in ways:
    q = np.array([nodes[n] for n in w["nodes"] if n in nodes])
    for a, b in zip(q[:-1], q[1:]):
        k = max(1, int(np.hypot(*(xy(b[None]) - xy(a[None]))[0]) // 5))
        dense.append(a + (b - a) * (np.arange(k) / k)[:, None])
    if len(q): dense.append(q[-1:])
tree = cKDTree(xy(np.vstack(dense)))
res = {}
for r in [r"C:\Users\nouir\PFE\codes\data\Depth", r"C:\Users\nouir\PFE\data_extra\kitti_raw"]:
    for dr in sorted(glob.glob(os.path.join(r, "2011_09_26_drive_*_sync"))):
        fs = sorted(glob.glob(os.path.join(dr, "2011_09_26", os.path.basename(dr), "oxts", "data", "*.txt")))
        if not fs: continue
        a = np.array([np.loadtxt(f)[:2] for f in fs])
        inside = bool(((a[:, 0] >= m0[0]) & (a[:, 0] <= m0[1]) & (a[:, 1] >= m0[2]) & (a[:, 1] <= m0[3])).all())
        dist = tree.query(xy(a))[0]
        res[os.path.basename(dr)[-9:-5]] = {"n": len(a), "inside_bbox_margin": inside,
            "frac_within_50m_of_road": float((dist <= 50).mean()), "median_dist_m": float(np.median(dist)), "max_dist_m": float(dist.max())}
out = {"file_bytes": os.path.getsize(P), "osm_timestamp": d["osm3s"]["timestamp_osm_base"], "n_nodes": len(nodes),
       "n_ways": len(ways), "highway_types_top": hw.most_common(8), "node_bbox": [float(pts[:, 0].min()), float(pts[:, 0].max()), float(pts[:, 1].min()), float(pts[:, 1].max())],
       "all_drives_inside": all(v["inside_bbox_margin"] for v in res.values()),
       "min_frac_within_50m": min(v["frac_within_50m_of_road"] for v in res.values()), "drives": res}
json.dump(out, open(r"C:\Users\nouir\PFE\codes_v3\results\WP1\osm_verify.json", "w"), indent=1)
print({k: v for k, v in out.items() if k != "drives"}); print(len(res), "drives")
