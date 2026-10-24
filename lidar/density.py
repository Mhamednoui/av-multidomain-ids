"""WP3 S4 L2a: density and intensity versus range per object (domain "lidar", layer "L2a", kind "physics").

Purpose: a real object returns a predictable number of points for its angular size and range, with a typical intensity;
a crude spoof (a dense cloud far away, a sparse blob near, a removed sector, a bright sector) does not.
Inputs: object table of a scan (lidar.segment.COLUMNS), S2 calibration (return probability p(range)).
Outputs: per-object improbability scores dens_hi / dens_lo / int_hi / int_lo (-log10 of the one-sided tail of the clean
distribution), per-scan maxima (the Layer samples), Layers.
Model.
  slots = (rings spanned) x (azimuth steps spanned): the sensor grid cells inside the object's angular footprint. HDL-64E manual:
    64 lasers (~0.4 deg apart vertically), 0.1728 deg azimuth step at 10 Hz (0.08-0.35 deg over 5-20 Hz).
  E = slots x p(range), p = calibrated return probability of real car-like objects (S2).  u = log((n + 1) / (E + 1)).
  The clean distribution of u and of the mean intensity is the empirical conditional CDF of clean TRAIN objects per cell
  (range bin x slots bin; intensity: range bin), objects with n >= nmin at 4-60 m. Scan score = max over objects.
Limit stated plainly: a phantom made with the calibrated generator matches the real density at equal angular size by construction,
so this layer sees only uncalibrated / crude spoofs, removed sectors and wrong intensities; it cannot see a density-matched phantom.
References: Velodyne HDL-64E S2 manual; Cao et al. CCS 2019 (spoofed point counts); Sun et al. USENIX Sec 2020 (CARLO).
"""
import numpy as np
import pandas as pd

from common.layer import Layer
from lidar.geometry import SPEC

R_EDGES = np.array([4.0, 6.0, 8.0, 10.0, 13.0, 16.0, 20.0, 25.0, 30.0, 40.0, 60.01])
S_EDGES = np.array([0.0, 12.0, 30.0, 80.0, 250.0, 1e12])
N_EDGES = np.array([0.0, 12.0, 20.0, 32.0, 50.0, 80.0, 1e12])      # point-count bins of the intensity cells (a mean over more points is tighter)
MIN_CELL = 200
STATS = ["dens_hi", "dens_lo", "int_hi", "int_lo"]
CNT = ["cnt_" + s for s in STATS]       # number of units with improbability >= CNT_LEVEL (a sector attack moves many units a little)
ALL_STATS = STATS + CNT
CNT_LEVEL = 2.0


def slots_of(objs):
    return (objs["ring_max"].to_numpy() - objs["ring_min"].to_numpy() + 1.0) * (objs["az_span"].to_numpy() / SPEC["az_step"] + 1.0)


def residual(objs, calib):
    """log((n + 1) / (E + 1)) with E = slots x calibrated return probability at the object's range."""
    e = slots_of(objs) * calib.mean_p(objs["range"].to_numpy())
    return np.log((objs["n_points"].to_numpy() + 1.0) / (e + 1.0))


def _cdf(sorted_ref, x):
    lo = np.searchsorted(sorted_ref, x, side="left")
    hi = np.searchsorted(sorted_ref, x, side="right")
    n = len(sorted_ref)
    return np.clip(0.5 * (lo + hi) / n, 0.5 / n, 1.0 - 0.5 / n)


def tail_scores(ref, x):
    """(too high, too low) improbability -log10 of the one-sided empirical tails of `ref` at x. Beyond the reference extremes the
    score keeps growing (excess in units of the reference inter-quartile range) so that extreme values do not tie at the cap."""
    F = _cdf(ref, x)
    hi, lo = -np.log10(1 - F), -np.log10(F)
    q1, q3 = np.quantile(ref, [0.25, 0.75])
    iqr = max(q3 - q1, 1e-6)
    hi = hi + np.maximum(x - ref[-1], 0.0) / iqr
    lo = lo + np.maximum(ref[0] - x, 0.0) / iqr
    return hi, lo


class ObjectModel:
    """Conditional empirical CDFs of clean objects."""

    def __init__(self, calib, nmin=20):
        self.calib, self.nmin = calib, nmin
        self.u, self.i, self.nref = {}, {}, {}

    def keys(self, objs):
        rb = np.clip(np.searchsorted(R_EDGES, objs["range"].to_numpy(), side="right") - 1, 0, len(R_EDGES) - 2)
        sb = np.clip(np.searchsorted(S_EDGES, slots_of(objs), side="right") - 1, 0, len(S_EDGES) - 2)
        return rb, sb

    def valid(self, objs):
        r = objs["range"].to_numpy()
        return (objs["n_points"].to_numpy() >= self.nmin) & (r >= R_EDGES[0]) & (r <= R_EDGES[-1])

    def fit(self, objs):
        m = self.valid(objs)
        o = objs[m]
        u = residual(o, self.calib)
        im = o["int_mean"].to_numpy()
        rb, sb = self.keys(o)
        nb = np.clip(np.searchsorted(N_EDGES, o["n_points"].to_numpy(), side="right") - 1, 0, len(N_EDGES) - 2)
        self.u, self.i, self.nref = {}, {}, {}
        for r in range(len(R_EDGES) - 1):
            mr = rb == r
            self.i[(r, -1)] = np.sort(im[mr])
            for q in range(len(N_EDGES) - 1):
                mq = mr & (nb == q)
                if mq.sum() >= MIN_CELL:
                    self.i[(r, q)] = np.sort(im[mq])
            self.u[(r, -1)] = np.sort(u[mr])
            for s in range(len(S_EDGES) - 1):
                ms = mr & (sb == s)
                if ms.sum() >= MIN_CELL:
                    self.u[(r, s)] = np.sort(u[ms])
        return self

    def scores(self, objs):
        """DataFrame (index of objs) with STATS; 0 for objects that are not scored (too few points, out of range)."""
        out = np.zeros((len(objs), 4))
        m = self.valid(objs)
        if not m.any():
            return pd.DataFrame(out, columns=STATS, index=objs.index)
        o = objs[m]
        u = residual(o, self.calib)
        im = o["int_mean"].to_numpy()
        rb, sb = self.keys(o)
        nb = np.clip(np.searchsorted(N_EDGES, o["n_points"].to_numpy(), side="right") - 1, 0, len(N_EDGES) - 2)
        res = np.zeros((m.sum(), 4))
        for r in np.unique(rb):
            mr = rb == r
            for q in np.unique(nb[mr]):
                mq = mr & (nb == q)
                res[mq, 2], res[mq, 3] = tail_scores(self.i.get((r, q), self.i[(r, -1)]), im[mq])
            for s in np.unique(sb[mr]):
                ms = mr & (sb == s)
                ref = self.u.get((r, s), self.u[(r, -1)])
                res[ms, 0], res[ms, 1] = tail_scores(ref, u[ms])
        out[m] = res
        return pd.DataFrame(out, columns=STATS, index=objs.index)


def scan_scores(objs, scores, key="scan"):
    """Per-scan maxima of the object scores. objs has the column `key`; returns DataFrame indexed by key."""
    g = objs[key].to_numpy()
    mx = scores.groupby(g).max()
    cn = (scores >= CNT_LEVEL).groupby(g).sum().astype(float)
    cn.columns = CNT
    return mx.join(cn)


class L2aStat(Layer):
    domain, layer_id, kind = "lidar", "L2a", "physics"

    def __init__(self, stat):
        super().__init__()
        self.stat, self.name = stat, stat

    def raw_scores(self, samples):
        return np.asarray(samples[self.stat], dtype=float)

    def reasons(self, samples, raw, alarm):
        what = {"dens_hi": "too many points for its range and size", "dens_lo": "too few points for its range and size",
                "int_hi": "intensity too high for its range", "int_lo": "intensity too low for its range"}[self.stat]
        return [f"object {what} (improbability 1e-{r:.1f})" for r in raw]


class L2aUnion(Layer):
    domain, layer_id, kind, name = "lidar", "L2a", "physics", "union"

    def __init__(self, stats=ALL_STATS):
        super().__init__()
        self.stats, self.ref = list(stats), None

    def calibrate(self, val_normal, budget=0.01):
        self.ref = {s: np.sort(np.asarray(val_normal[s], dtype=float)) for s in self.stats}
        return super().calibrate(val_normal, budget)

    def parts(self, samples):
        return np.column_stack([np.searchsorted(self.ref[s], np.asarray(samples[s], dtype=float), side="left") / len(self.ref[s])
                                for s in self.stats])

    def raw_scores(self, samples):
        return self.parts(samples).max(axis=1)

    def reasons(self, samples, raw, alarm):
        P = self.parts(samples)
        return [f"object density/intensity: {self.stats[int(np.argmax(P[i]))]} improbable for the clean scans" for i in range(len(raw))]
