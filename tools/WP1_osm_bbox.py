"""WP1 S0: bbox of all KITTI 2011_09_26 OXTS drives (lat, lon = first two OXTS fields).
Output: results/WP1/osm_bbox.json. Run with python -I."""
import json, glob, os
import numpy as np
ROOTS = [r"C:\Users\nouir\PFE\codes\data\Depth", r"C:\Users\nouir\PFE\data_extra\kitti_raw"]
out = {}
for r in ROOTS:
    for d in sorted(glob.glob(os.path.join(r, "2011_09_26_drive_*_sync"))):
        fs = sorted(glob.glob(os.path.join(d, "2011_09_26", os.path.basename(d), "oxts", "data", "*.txt")))
        if not fs:
            continue
        a = np.array([np.loadtxt(f)[:2] for f in fs])
        out[os.path.basename(d)[-9:-5]] = [float(a[:, 0].min()), float(a[:, 0].max()), float(a[:, 1].min()), float(a[:, 1].max()), len(a)]
la0 = min(v[0] for v in out.values()); la1 = max(v[1] for v in out.values())
lo0 = min(v[2] for v in out.values()); lo1 = max(v[3] for v in out.values())
m = 1000.0; dla = m / 111320.0; dlo = m / (111320.0 * np.cos(np.radians((la0 + la1) / 2)))
res = {"drives": out, "bbox": [la0, la1, lo0, lo1], "bbox_margin_1km": [la0 - dla, la1 + dla, lo0 - dlo, lo1 + dlo]}
json.dump(res, open(r"C:\Users\nouir\PFE\codes_v3\results\WP1\osm_bbox.json", "w"), indent=1)
print(len(out), "drives", res["bbox"], res["bbox_margin_1km"])
