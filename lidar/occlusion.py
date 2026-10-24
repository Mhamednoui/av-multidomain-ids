"""WP3 S5 L2b free space / occlusion per object (domain "lidar", layer "L2b", kind "physics").

Purpose: a solid object hides what is behind it. If a laser returns from FAR behind a place that lies between two returns of
the same object (same laser, neighbouring azimuths; or same azimuth, neighbouring lasers), the beam passed through the
object's silhouette: the object is not solid there (CARLO, Sun et al., USENIX Security 2020, "free space" / occlusion check;
the same idea as the frustum check: an object point must not sit in space that a ray to a farther point proves empty).
Inputs: scan (N x 4), cluster labels of lidar.segment (-1 = none), ring table (laser index k), optionally the injected-return
mask. Outputs: a tile table (one row per cluster x 2 deg x 8 lasers x 2 m cell with >= TILE_MIN returns) with the number of
"see-through" returns counted for a small grid of margins / gaps, scan statistics, and Layers.
Definitions (see sandwich()):
  row sandwich: points of the same laser sorted by azimuth; a point j is see-through if the nearest object points before and after
    it in the row belong to the SAME cluster, are at most `gap` degrees apart and at similar range (same surface), and j is
    farther than both by more than `margin` metres (and is not itself part of that cluster).
  column sandwich: the same in a column (azimuth bin of 0.2 deg, lasers sorted by elevation), neighbours at most COL_SPAN lasers apart.
Physics point stated plainly: with single-return physics an exact ray-cast phantom REPLACES the real returns behind it, so behind
a complete phantom nothing is visible; the check can only fire where the injected silhouette has holes (rays that pass through the
silhouette without an injected return keep their real, farther return) or where the budget cut leaves the real scene visible
inside the object's angular extent. A real object with a missing return (dark paint) gives NO return, not a far one.
Limits: windows, thin structures (fences, foliage) show far returns through gaps in clean scans; the thresholds come from clean
train + validation drives (leave-one-drive-out).
"""
import numpy as np
import pandas as pd

from common.layer import Layer
from lidar import phantom as P

MARGINS = (0.5, 1.0, 2.0)          # m: a see-through return is farther than the object points around it by more than this
GAPS = (0.4, 0.8)                  # deg: maximum azimuth distance of the two object points of a row sandwich
COL_AZ = 0.2                       # deg: azimuth bin of the column sandwich
COL_SPAN = 2                       # lasers
DR0, DR1 = 0.6, 0.03               # same-surface tolerance |r_P - r_N| <= DR0 + DR1 * r
AZ_TILE, RING_GROUP, R_CELL, TILE_MIN = 2.0, 8, 2.0, 8
DS0, DS1 = 0.25, 0.01              # "strict" same-surface tolerance (flat face): |r_P - r_N| <= DS0 + DS1 * r
SR = [f"sr_{i}_{j}_{s}" for i in range(len(MARGINS)) for j in range(len(GAPS)) for s in range(2)]
SC = [f"sc_{i}_{s}" for i in range(len(MARGINS)) for s in range(2)]
STATS = ["tot", "maxf", "cnt", "maxn"]
CNT_F = 0.10


def sandwich(group, order, lab, rho, span_max, span_of):
    """Generic sandwich search. Points are sorted by (group, order); for every point j the nearest object point before (P) and after (N)
    in the same group are found. Returns (index of P in the input, excess = r_j - max(r_P, r_N), span between P and N, strict same-surface flag) for the
    points j that are strictly between two points of one cluster, in the same group, at similar range, with span <= span_max and
    j not in that cluster and farther than both."""
    n = len(group)
    if n < 3:
        return np.zeros(0, int), np.zeros(0), np.zeros(0), np.zeros(0, bool)
    o = np.lexsort((order, group))
    g, od, L, r = group[o], order[o], lab[o], rho[o]
    pos = np.arange(n)
    isobj = L >= 0
    last = np.maximum.accumulate(np.where(isobj, pos, -1))
    nxt = np.minimum.accumulate(np.where(isobj, pos, n)[::-1])[::-1]
    pj = np.r_[-1, last[:-1]]                  # nearest object point strictly before j
    nj = np.r_[nxt[1:], n]                     # nearest object point strictly after j
    ok = (pj >= 0) & (nj < n)
    pj_c, nj_c = np.clip(pj, 0, n - 1), np.clip(nj, 0, n - 1)
    ok &= (g[pj_c] == g) & (g[nj_c] == g) & (L[pj_c] == L[nj_c]) & (L[pj_c] >= 0) & (L != L[pj_c])
    span = span_of(od[nj_c], od[pj_c])
    rp, rn = r[pj_c], r[nj_c]
    ok &= (span > 0) & (span <= span_max) & (np.abs(rp - rn) <= DR0 + DR1 * np.maximum(rp, rn))
    ex = r - np.maximum(rp, rn)
    ok &= ex > MARGINS[0]
    j = np.flatnonzero(ok)
    strict = np.abs(rp - rn) <= DS0 + DS1 * np.maximum(rp, rn)
    return o[pj_c[j]], ex[j], span[j], strict[j]


def elevation_rank(table):
    """Rank of each laser by elevation (ascending)."""
    e = table.elevation_deg()
    return np.argsort(np.argsort(e)).astype(np.int64)


def see_through(pts, lab, k, table_rank):
    """(rows, cols): each a tuple (P index, excess, span) of the row and column sandwiches of one scan."""
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0])) % 360.0
    rho = np.hypot(pts[:, 0], pts[:, 1])
    row = sandwich(k.astype(np.int64), az, lab, rho, GAPS[-1], lambda a, b: a - b)
    cb = np.floor(az / COL_AZ).astype(np.int64)
    col = sandwich(cb, table_rank[k], lab, rho, COL_SPAN, lambda a, b: (a - b).astype(float))
    return row, col


def tile_table(pts, lab, k, rank, inj=None):
    """Tile table with the see-through counts. Columns: oid, range, n_points, ph_n, sr_i_j (row, margin i, gap j), sc_i (column, margin i)."""
    cols = ["oid", "range", "n_points", "ph_n"] + SR + SC
    sel = np.flatnonzero(lab >= 0)
    if len(sel) == 0:
        return pd.DataFrame(columns=cols, dtype=np.float32)
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    rho = np.hypot(pts[:, 0], pts[:, 1])
    key_all = np.full(len(pts), -1, np.int64)
    key_all[sel] = ((lab[sel].astype(np.int64) * 180 + np.clip(((az[sel] + 180.0) // AZ_TILE).astype(np.int64), 0, 179)) * 8
                    + k[sel] // RING_GROUP) * 64 + np.clip((rho[sel] // R_CELL).astype(np.int64), 0, 63)
    uk, inv = np.unique(key_all[sel], return_inverse=True)
    nu = len(uk)
    n = np.bincount(inv, minlength=nu).astype(float)
    ph = np.bincount(inv, weights=inj[sel].astype(float), minlength=nu) if inj is not None else np.zeros(nu)
    data = {"oid": uk // (180 * 8 * 64), "range": np.bincount(inv, weights=rho[sel], minlength=nu) / n, "n_points": n, "ph_n": ph}
    (pr, er, sr_, st_r), (pc, ec, _, st_c) = see_through(pts, lab, k, rank)
    tid_of = np.full(len(pts), -1, np.int64)
    tid_of[sel] = inv
    for i, m in enumerate(MARGINS):
        for j, g in enumerate(GAPS):
            for s_ in range(2):
                mk = (er > m) & (sr_ <= g) & (st_r | (s_ == 0))
                data[f"sr_{i}_{j}_{s_}"] = np.bincount(tid_of[pr[mk]], minlength=nu).astype(float) if mk.any() else np.zeros(nu)
        for s_ in range(2):
            mk = (ec > m) & (st_c | (s_ == 0))
            data[f"sc_{i}_{s_}"] = np.bincount(tid_of[pc[mk]], minlength=nu).astype(float) if mk.any() else np.zeros(nu)
    t = pd.DataFrame(data)
    return t[t.n_points >= TILE_MIN].astype(np.float32).reset_index(drop=True)


def variant_cols(v):
    """v = (margin index, gap index, strict 0/1) -> (row column, column column)."""
    return f"sr_{v[0]}_{v[1]}_{v[2]}", f"sc_{v[0]}_{v[2]}"


def tile_fraction(tiles, v):
    r, c = variant_cols(v)
    return (tiles[r].to_numpy() + tiles[c].to_numpy()) / tiles["n_points"].to_numpy()


def scan_stats(tiles, v, scans):
    """One row per scan (index = scan ids of `scans`): tot, maxf, cnt (tiles with fraction >= CNT_F), maxn. Scans without tiles: 0."""
    r, c = variant_cols(v)
    t = tiles[["scan"]].copy()
    t["s"] = tiles[r].to_numpy() + tiles[c].to_numpy()
    t["f"] = t["s"] / tiles["n_points"].to_numpy()
    t["h"] = (t["f"] >= CNT_F).astype(float)
    g = t.groupby("scan")
    out = pd.DataFrame({"tot": g["s"].sum(), "maxf": g["f"].max(), "cnt": g["h"].sum(), "maxn": g["s"].max()})
    out = out.reindex(scans).fillna(0.0)
    return out


class L2bUnion(Layer):
    """Max over the clean-ECDF ranks of the scan statistics (same construction as L1Union / L2aUnion)."""
    domain, layer_id, kind, name = "lidar", "L2b", "physics", "union"

    def __init__(self, stats=STATS):
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
        pa = self.parts(samples)
        return [f"free space: {self.stats[int(np.argmax(pa[i]))]} of far returns seen through the object's silhouette is unusual" for i in range(len(raw))]


class FullCalib(P.Calib):
    """Best-case attacker: injects a return on EVERY ray through the silhouette (no dropout); intensities as the calibrated generator."""

    @classmethod
    def of(cls, c):
        return cls(c.edges, c.p, c.kappa, c.library)

    def draw_pi(self, rho, rng):
        return 1.0

    def mean_p(self, rho):
        return np.ones_like(np.asarray(rho, dtype=float))
