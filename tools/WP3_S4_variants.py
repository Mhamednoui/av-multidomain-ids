"""WP3 S4 choice 1 (validation only): segmentation variants against near-phantom merging.
Variants (see notes/WP3_lidar.md S4 acceptance rule): S3, B (link 0.25 m below 20 m), C (0.15 m), D (B + points above 2.2 m ignored).
Validation drives, every 12th scan, calibrated single-return phantoms (replace, budget) near/far. Per variant: share of phantoms that appear as ONE object
(S3 definition: object with >= 60 % of phantom points, centre within 2 m of the phantom centre), purity, plus car-like objects per scan and oversize share
on the clean scans. Writes results/WP3/S4/variants.json."""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import geometry as G
from lidar import phantom as P
from lidar import segment as S
from lidar.data import VAL, load, scan_files
from lidar.raycast import eval_params
from WP3_S3_build import params

RES = RESULTS / "WP3" / "S4"
S2 = RESULTS / "WP3" / "S2"
TABLE = G.RingTable.load(S2 / "ring_table.json")
STRIDE = 12
VARIANTS = {"S3": {}, "B": {"e_near": 0.25, "r_near": 20.0}, "C": {"e_near": 0.15, "r_near": 20.0},
            "D": {"e_near": 0.25, "r_near": 20.0, "h_max": 2.2}}


def one(args):
    d, i = args
    calib = C.load_calib(S2 / "calibration_beta.npz")
    rng = np.random.default_rng([71, int(d), i])
    pts = load(scan_files(d)[i])
    rays = P.prepare(pts, TABLE)
    cases = []
    for band in ("near", "far"):
        p = eval_params(rng, band)
        for mode in ("replace", "budget"):
            att, n, q, idx = P.phantom(pts, rays, p, rng, mode, calib)
            cases.append((mode, band, att, idx, P.box_pose(pts, q)[0]))
    rows, clean = [], []
    for v, extra in VARIANTS.items():
        prm = dict(params(), **extra)
        t = S.segment(pts, TABLE, prm)
        clean.append(dict(variant=v, d=d, i=i, n_obj=len(t), carlike=int(t.carlike.sum()), n_over=int((t.length > 8).sum())))
        for mode, band, att, idx, c in cases:
            if len(idx) == 0:
                continue
            tab, lab, _ = S.segment(att, TABLE, prm, return_labels=True)
            pl = lab[idx]
            inn = pl[pl >= 0]
            r = dict(variant=v, mode=mode, band=band, n_ph=len(idx), one=False, pure=False)
            if len(inn):
                main = np.bincount(inn).argmax()
                o = tab.iloc[main]
                share = float((pl == main).mean())
                r["one"] = bool(share >= 0.6 and np.hypot(o.cx - c[0], o.cy - c[1]) <= 2.0)
                r["pure"] = bool(r["one"] and (pl == main).sum() / o.n_points >= 0.8)
            rows.append(r)
    return rows, clean


def main():
    RES.mkdir(parents=True, exist_ok=True)
    jobs = [(d, i) for d in VAL for i in range(1, len(scan_files(d)), STRIDE)]
    with Pool(4) as pool:
        out = list(pool.imap_unordered(one, jobs))
    ph = pd.DataFrame([r for o in out for r in o[0]])
    cl = pd.DataFrame([r for o in out for r in o[1]])
    res = {}
    for v in VARIANTS:
        a, c = ph[ph.variant == v], cl[cl.variant == v]
        res[v] = {"n_scans": int(len(c)), "carlike_per_scan": float(c.carlike.mean()), "objects_per_scan": float(c.n_obj.mean()),
                  "oversize_share": float(c.n_over.sum() / c.n_obj.sum())}
        for band in ("near", "far"):
            b = a[a.band == band]
            res[v][f"one_{band}"] = float(b.one.mean())
            res[v][f"pure_{band}"] = float(b.pure.mean())
            res[v][f"n_{band}"] = int(len(b))
    (RES / "variants.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
