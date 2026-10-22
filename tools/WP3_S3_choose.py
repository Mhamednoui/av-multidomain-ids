"""WP3 S3: choose ground-removal and clustering parameters on the VALIDATION drives (rule in notes/WP3_lidar.md, S3).
Stage 1 ground variants (grid h0 .15/.20/.30, ransac h0 .15/.20/.30) with the default clustering; stage 2 clustering grid
(e0 x e1) with the chosen ground. Writes results/WP3/S3/choice.json and choice_tables.md. Foreground, resumable by stage."""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import assoc, ego
from lidar import geometry as G
from lidar import objects as O
from lidar import segment as S
from lidar.data import VAL, load, scan_files

RES = RESULTS / "WP3" / "S3"
STRIDE = 8
TABLE = G.RingTable.load(RESULTS / "WP3" / "S2" / "ring_table.json")
POSES = {}


def poses(d):
    if d not in POSES:
        POSES[d] = ego.poses(d)
    return POSES[d]


def ground_job(a):
    d, i, kind, h0 = a
    pts = load(scan_files(d)[i])
    h, _ = S.height_above_ground(pts, kind)
    near = np.hypot(pts[:, 0], pts[:, 1]) < 40.0
    gfrac = float((h[near] <= h0).mean())
    tab = S.segment(pts, TABLE, {"ground": kind, "h0": h0})
    ncar = int(tab["carlike"].sum())
    leak = int(((tab["height"] < 0.5) & (tab["length"] > 4.0)).sum())
    ref = len(O.clusters(pts, TABLE))
    return dict(drive=d, i=i, kind=kind, h0=h0, gfrac=gfrac, ncar=ncar, nobj=len(tab), leak=leak, ref=ref)


def cluster_job(a):
    d, i, e0, e1, prm = a
    f = scan_files(d)
    P = poses(d)
    prm = dict(prm, e0=e0, e1=e1)
    ta = S.segment(load(f[i]), TABLE, prm)
    tb = S.segment(load(f[i + 1]), TABLE, prm)
    out = []
    for lo, hi in ((10, 20), (20, 30), (30, 40), (10, 40)):
        cand, jj, dist, ratio = assoc.match(ta, P[i], tb, P[i + 1], 1.0, lo, hi)
        out.append(dict(drive=d, i=i, e0=e0, e1=e1, band=f"{lo}-{hi}", n=len(cand), matched=int((jj >= 0).sum()),
                        dist=dist[jj >= 0].tolist(), ratio=ratio[jj >= 0].tolist()))
    long_ = ta["length"].to_numpy() > 8.0
    out.append(dict(drive=d, i=i, e0=e0, e1=e1, band="all", n=len(ta), matched=int(long_.sum()), dist=[], ratio=[]))
    return out


def main():
    RES.mkdir(parents=True, exist_ok=True)
    choice_f = RES / "choice.json"
    choice = json.loads(choice_f.read_text()) if choice_f.exists() else {}
    scans = [(d, i) for d in VAL for i in range(0, len(scan_files(d)) - 1, STRIDE)]
    t0 = time.time()
    with Pool(4) as pool:
        if "ground" not in choice:
            jobs = [(d, i, k, h0) for (d, i) in scans for k in ("grid", "ransac") for h0 in (0.15, 0.20, 0.30)]
            df = pd.DataFrame(pool.map(ground_job, jobs, chunksize=4))
            g = df.groupby(["kind", "h0"]).agg(gfrac=("gfrac", "mean"), ncar=("ncar", "median"), nobj=("nobj", "median"),
                                              leak=("leak", "sum"), tot=("nobj", "sum"), ref=("ref", "median")).reset_index()
            g["leak_rate"] = g["leak"] / g["tot"]
            ok = g[(g.gfrac.between(0.35, 0.65)) & (g.leak_rate <= 0.02)]
            best = (ok if len(ok) else g).sort_values(["ncar", "h0"], ascending=[False, True]).iloc[0]
            choice["ground"] = {"kind": best.kind, "h0": float(best.h0), "table": g.to_dict("records"), "constraint_met": bool(len(ok))}
            choice_f.write_text(json.dumps(choice, indent=1))
            print(g.to_string(), "\n->", best.kind, best.h0, f"{time.time() - t0:.0f}s", flush=True)
        gk = choice["ground"]
        prm = {"ground": gk["kind"], "h0": gk["h0"]}
        if "cluster" not in choice:
            jobs = [(d, i, e0, e1, prm) for (d, i) in scans for e0 in (0.4, 0.6, 0.8) for e1 in (0.0, 0.01, 0.02)]
            rows = [r for out in pool.imap_unordered(cluster_job, jobs, chunksize=2) for r in out]
            res = []
            for (e0, e1), g in pd.DataFrame(rows).groupby(["e0", "e1"]):
                b = g[g.band == "10-40"]
                allr = g[g.band == "all"]
                dist = np.concatenate([np.array(x) for x in b.dist]) if len(b) else np.zeros(0)
                res.append(dict(e0=e0, e1=e1, match=float(b.matched.sum() / max(b.n.sum(), 1)),
                                oversize=float(allr.matched.sum() / max(allr.n.sum(), 1)), n_obj=float(allr.n.mean()),
                                dist_med=float(np.median(dist)) if len(dist) else np.nan,
                                **{f"match_{bd}": float(g[g.band == bd].matched.sum() / max(g[g.band == bd].n.sum(), 1))
                                   for bd in ("10-20", "20-30", "30-40")}))
            r = pd.DataFrame(res)
            ok = r[r.oversize <= 0.05]
            best = (ok if len(ok) else r).sort_values("match", ascending=False).iloc[0]
            choice["cluster"] = {"e0": float(best.e0), "e1": float(best.e1), "table": r.to_dict("records"),
                                 "constraint_met": bool(len(ok))}
            choice_f.write_text(json.dumps(choice, indent=1))
            print(r.to_string(), "\n->", best.e0, best.e1, f"{time.time() - t0:.0f}s", flush=True)
    print("done", json.dumps({k: {x: v for x, v in c.items() if x != "table"} for k, c in choice.items()}))


if __name__ == "__main__":
    main()
