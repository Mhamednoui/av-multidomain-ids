"""WP3 S2: fit the HDL-64E ring table on TRAIN scans and describe its residuals on clean scans.
Output: results/WP3/S2/ring_table.json, results/WP3/S2/ring_table_report.json."""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import geometry as G
from lidar.data import drives_of, load, scan_files

OUT = RESULTS / "WP3" / "S2"
OUT.mkdir(parents=True, exist_ok=True)
t0 = time.time()
train = [load(f) for d in drives_of("train") for f in scan_files(d)[5::20]]
print(len(train), "train scans", flush=True)
table = G.fit_ring_table(train)
table.save(OUT / "ring_table.json")
print("fit", time.time() - t0, "s", table.meta, flush=True)

rep = {"n_fit_scans": table.meta["n_scans"], "az_step_deg": table.meta["az_step_deg"],
       "elev_deg_top_bottom": [float(table.elevation_deg()[0]), float(table.elevation_deg()[-1])],
       "spacing_deg": [float(np.diff(table.elevation_deg())[:31].mean()), float(np.diff(table.elevation_deg())[32:].mean())]}
# residual statistics on clean scans of train (different scans than the fit) and val
res = {}
for part in ("train", "val"):
    rows = []
    for d in drives_of(part):
        for f in scan_files(d)[2::15]:
            p = load(f)
            rho = np.linalg.norm(p[:, :3], axis=1)
            k0, r0 = table.nearest(p, None, rho)
            a = table.assign(p)
            m = (rho >= 8) & (rho <= 80)
            rows.append((np.quantile(np.abs(r0[m]), 0.99), np.quantile(np.abs(a["res"][m]), 0.99),
                         np.mean(np.abs(a["res"][m]) > G.TAU_Z), rho.min(), rho.max(), p[:, 3].min(), p[:, 3].max(),
                         G.l1_stats(p, table, asg=a)))
    A = np.array([r[:7] for r in rows])
    S = np.array([r[7] for r in rows])
    res[part] = {"n_scans": len(rows), "q99_abs_res_no_cm": float(A[:, 0].mean()), "q99_abs_res_cm": float(A[:, 1].mean()),
                 "mean_frac_off_ring": float(A[:, 2].mean()), "min_range": float(A[:, 3].min()), "max_range": float(A[:, 4].max()),
                 "min_int": float(A[:, 5].min()), "max_int": float(A[:, 6].max()),
                 "stats_mean": dict(zip(G.STAT_NAMES, S.mean(0).tolist())),
                 "stats_q99": dict(zip(G.STAT_NAMES, np.quantile(S, 0.99, axis=0).tolist())),
                 "stats_max": dict(zip(G.STAT_NAMES, S.max(0).tolist()))}
    print(part, json.dumps(res[part]), flush=True)
rep["clean_scans"] = res
(OUT / "ring_table_report.json").write_text(json.dumps(rep, indent=1))
print("done", time.time() - t0)
