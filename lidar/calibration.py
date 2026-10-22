"""WP3 S2 calibration of the phantom generator to real objects: statistics, fit, save / load, two-sample tests.

Purpose: make a phantom of a given range and angular size have the point count and intensity distribution of a real
car-like object (lidar.objects). Inputs: scans, ring table. Outputs: Calib (lidar.phantom) + statistics tables.
Statistic: occupancy q = points / sensor-grid cells covered by the object (lasers spanned x azimuth steps spanned);
q is the share of the sensor's own sampling grid that returns, so it removes the dependence on size and range that the
raw point count has (a 4 m car at 30 m covers ~15 lasers x 25 steps). The same statistic is measured on real
clusters and on phantom points.
References: Cao et al., CCS 2019 (spoofed returns lie on the laser's rays); Geiger et al., KITTI 2013.
"""
import numpy as np
from scipy.stats import ks_2samp

from lidar import geometry as G
from lidar import objects as O
from lidar import phantom as P
from lidar.features import raycast_ghost

EDGES = np.array([6.0, 12.0, 16.0, 20.0, 25.0, 30.0, 35.0, 45.0])
N_MIN = 15


def phantom_params(rng, lo=8.0, hi=45.0):
    return {"range": float(rng.uniform(lo, hi)), "az": float(rng.uniform(-180, 180)), "rot": float(rng.uniform(0, np.pi)),
            "budget": 10 ** 6}


def stat_of(new, k):
    """(centroid range, n, cells, q) of an injected / real point set with laser indices k."""
    az = np.degrees(np.arctan2(new[:, 1], new[:, 0]))
    cells = G.ideal_cells(k, az)
    return float(np.hypot(new[:, 0].mean(), new[:, 1].mean())), len(new), cells, len(new) / max(cells, 1.0)


def scan_records(pts, table, rng, n_ph=3, calib=None):
    """Real car-like clusters and phantoms (uncalibrated exact-ray 'add', S1 origin-ray 'add', and calibrated if given)
    of one scan. Rows: dict(kind, range, n, cells, q, int)."""
    rays = P.prepare(pts, table)
    out = []
    for c in O.clusters(pts, table, rays["asg"]):
        out.append({"kind": "real", "range": c["range"], "n": c["n"], "cells": c["cells"], "q": c["q"],
                    "int": c["int"], "length": c["length"]})
    for _ in range(n_ph):
        p = phantom_params(rng)
        variants = [("exact", None)] + ([("calibrated", calib)] if calib is not None else [])
        for kind, cb in variants:
            att, n, q, idx = P.phantom(pts, rays, p, rng, "add", cb)
            if n >= N_MIN:
                new = att[len(pts):]
                r, n_, cells, qq = stat_of(new, rays["k"][idx])
                out.append({"kind": kind, "range": r, "n": n_, "cells": cells, "q": qq, "int": new[:, 3].copy()})
        old, n_old = raycast_ghost(pts, p, rng, "add", retry=True)
        new = old[len(pts):]
        if n_old >= N_MIN:
            k, _ = table.nearest(new, rays["asg"]["cm"])
            r, n_, cells, qq = stat_of(new, k)
            out.append({"kind": "s1", "range": r, "n": n_, "cells": cells, "q": qq, "int": new[:, 3].copy()})
    return out


def fit_calibration(real, ref, kappa=None, rng_seed=0):
    """Fit p(range) per bin and kappa from real cluster rows and exact-ray phantom rows (lists of dict).
    kappa=None: moment estimate; kappa=np.inf: no between-object variance (pure Bernoulli thinning)."""
    nb = len(EDGES) - 1
    rb = lambda rows: np.clip(np.searchsorted(EDGES, [r["range"] for r in rows]) - 1, 0, nb - 1)
    br, bp = rb(real), rb(ref)
    qr = np.array([r["q"] for r in real])
    qp = np.array([r["q"] for r in ref])
    p, kap = np.ones(nb), []
    for b in range(nb):
        a, c = qr[br == b], qp[bp == b]
        if len(a) < 10 or len(c) < 10:
            continue
        p[b] = min(1.0, a.mean() / c.mean())
        e2 = (a.var() + a.mean() ** 2) / (c ** 2).mean()          # E[pi^2] if q_real = q_ph * pi, independent
        extra = e2 - p[b] ** 2
        if extra > 1e-6 and 0 < p[b] < 1:
            kap.append(p[b] * (1 - p[b]) / extra - 1.0)
    k_hat = float(np.median(kap)) if kap else np.inf
    kappa = k_hat if kappa is None else kappa
    lib = []
    rng = np.random.default_rng(rng_seed)
    for b in range(nb):
        items = [r["int"] for r, bb in zip(real, br) if bb == b]
        if len(items) > 400:
            items = [items[i] for i in rng.choice(len(items), 400, replace=False)]
        lib.append(items)
    return P.Calib(EDGES, p, max(kappa, 2.0) if np.isfinite(kappa) else np.inf, lib), k_hat


def save_calib(c, path):
    flat = [np.concatenate(([len(x)], x)) for b in c.library for x in b]
    sizes = [len(b) for b in c.library]
    np.savez_compressed(path, edges=c.edges, p=c.p, kappa=c.kappa, sizes=sizes,
                        data=np.concatenate(flat).astype(np.float32) if flat else np.zeros(0, np.float32))


def load_calib(path):
    z = np.load(path)
    data, lib, i = z["data"], [], 0
    for s in z["sizes"]:
        items = []
        for _ in range(int(s)):
            n = int(data[i]); items.append(data[i + 1:i + 1 + n].copy()); i += 1 + n
        lib.append(items)
    return P.Calib(z["edges"], z["p"], float(z["kappa"]), lib)


def compare(real, other, edges=EDGES, min_real=30):
    """Per range bin: n, KS D (p-value) of q and of pooled intensities, median-count ratio other / real."""
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        a = [r for r in real if lo <= r["range"] < hi]
        b = [r for r in other if lo <= r["range"] < hi]
        row = {"bin": f"{lo:g}-{hi:g}", "n_real": len(a), "n_other": len(b)}
        if len(a) >= 5 and len(b) >= 5:
            ks = ks_2samp([r["q"] for r in a], [r["q"] for r in b])
            ia = np.concatenate([r["int"] for r in a]); ib = np.concatenate([r["int"] for r in b])
            ki = ks_2samp(ia, ib)
            row.update(D_q=float(ks.statistic), p_q=float(ks.pvalue), D_int=float(ki.statistic), p_int=float(ki.pvalue),
                       med_n_real=float(np.median([r["n"] for r in a])), med_n_other=float(np.median([r["n"] for r in b])),
                       med_q_real=float(np.median([r["q"] for r in a])), med_q_other=float(np.median([r["q"] for r in b])),
                       ratio_n=float(np.median([r["n"] for r in b]) / np.median([r["n"] for r in a])),
                       testable=bool(len(a) >= min_real))
        out.append(row)
    return out


def compare_by_size(real, other, edges=EDGES, n_strata=3):
    """Count comparison at equal angular size: per range bin, strata = terciles of the real clusters' `cells`;
    median point count real vs other inside each stratum, and the ratio."""
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        a = [r for r in real if lo <= r["range"] < hi]
        b = [r for r in other if lo <= r["range"] < hi]
        if len(a) < 30 or len(b) < 10:
            continue
        cuts = np.quantile([r["cells"] for r in a], np.linspace(0, 1, n_strata + 1))
        cuts[0], cuts[-1] = 0.0, np.inf
        for s in range(n_strata):
            aa = [r for r in a if cuts[s] <= r["cells"] < cuts[s + 1]]
            bb = [r for r in b if cuts[s] <= r["cells"] < cuts[s + 1]]
            if len(aa) >= 10 and len(bb) >= 5:
                out.append({"bin": f"{lo:g}-{hi:g}", "stratum": s, "cells_lo": float(cuts[s]), "n_real": len(aa), "n_other": len(bb),
                            "med_n_real": float(np.median([r["n"] for r in aa])), "med_n_other": float(np.median([r["n"] for r in bb])),
                            "ratio": float(np.median([r["n"] for r in bb]) / np.median([r["n"] for r in aa]))})
    return out
