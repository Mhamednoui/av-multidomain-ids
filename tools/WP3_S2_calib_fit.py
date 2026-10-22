"""WP3 S2 Part A, stage 2-3: fit the calibration on TRAIN, choose the variant on VAL, report real vs old vs calibrated.
Needs tools/WP3_S2_calib_collect.py. Stage 3 generates calibrated phantoms on VAL scans (every 3rd scan, 3 per scan).
Outputs: results/WP3/S2/calibration.npz (model), results/WP3/S2/calib_report.json."""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import geometry as G
from lidar import phantom as P
from lidar.data import CACHE, drives_of, load, scan_files

OUT = RESULTS / "WP3" / "S2"
STRIDE = 3


def rows_of(part):
    rows = []
    for d in drives_of(part):
        rows += pd.read_pickle(CACHE / "S2" / f"collect_{d}.pkl")
    return rows


def val_job(args):
    d, name = args
    calib = C.load_calib(OUT / f"calibration_{name}.npz")
    table = G.RingTable.load(OUT / "ring_table.json")
    rng = np.random.default_rng([37, int(d)])
    rows = []
    for i, fp in enumerate(scan_files(d)):
        if i % STRIDE:
            continue
        pts = load(fp)
        rays = P.prepare(pts, table)
        for _ in range(3):
            p = C.phantom_params(rng)
            att, n, q, idx = P.phantom(pts, rays, p, rng, "add", calib)
            if n >= C.N_MIN:
                new = att[len(pts):]
                r, n_, cells, qq = C.stat_of(new, rays["k"][idx])
                rows.append({"kind": "calibrated", "range": r, "n": n_, "cells": cells, "q": qq, "int": new[:, 3].copy(), "drive": d})
    return rows


def summarize(tab):
    return [{k: v for k, v in r.items()} for r in tab]


if __name__ == "__main__":
    t0 = time.time()
    tr, va = rows_of("train"), rows_of("val")
    kinds = lambda rows, k: [r for r in rows if r["kind"] == k]
    real_tr, ref_tr = kinds(tr, "real"), kinds(tr, "exact")
    real_va = kinds(va, "real")
    rep = {"n_real_train": len(real_tr), "n_real_val": len(real_va), "n_exact_train": len(ref_tr),
           "real_train_by_bin": C.compare(real_tr, real_tr)[:], }
    variants = {}
    for name, kappa in (("bernoulli", np.inf), ("beta", None)):
        calib, k_hat = C.fit_calibration(real_tr, ref_tr, kappa=kappa)
        C.save_calib(calib, OUT / f"calibration_{name}.npz")
        variants[name] = {"p": calib.p.tolist(), "kappa": calib.kappa, "kappa_moment_estimate": k_hat}
    rep["variants"] = variants
    with Pool(4) as pool:
        for name in variants:
            rows = sum(pool.map(val_job, [(d, name) for d in drives_of("val")]), [])
            cmp_ = C.compare(real_va, rows)
            pd.to_pickle(rows, CACHE / "S2" / f"val_cal_{name}.pkl")
            variants[name]["val_by_size"] = C.compare_by_size(real_va, rows)
            variants[name]["val_compare"] = cmp_
            ok = [r for r in cmp_ if r.get("testable")]
            variants[name]["val_max_D_q"] = max(r["D_q"] for r in ok)
            variants[name]["val_max_D_int"] = max(r["D_int"] for r in ok)
            variants[name]["val_ratio_range"] = [min(r["ratio_n"] for r in ok), max(r["ratio_n"] for r in ok)]
            print(name, "max D_q %.3f  max D_int %.3f ratio %s" % (variants[name]["val_max_D_q"], variants[name]["val_max_D_int"],
                  variants[name]["val_ratio_range"]), flush=True)
    rep["val_exact_by_size"] = C.compare_by_size(real_va, kinds(va, "exact"))
    rep["val_s1_by_size"] = C.compare_by_size(real_va, kinds(va, "s1"))
    rep["val_exact_vs_real"] = C.compare(real_va, kinds(va, "exact"))
    rep["val_s1_vs_real"] = C.compare(real_va, kinds(va, "s1"))
    rep["train_exact_vs_real"] = C.compare(real_tr, ref_tr)
    rep["train_s1_vs_real"] = C.compare(real_tr, kinds(tr, "s1"))
    (OUT / "calib_report.json").write_text(json.dumps(rep, indent=1, default=float))
    print("done", time.time() - t0)
