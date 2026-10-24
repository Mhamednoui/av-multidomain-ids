"""WP3 S6 L2c background model: expected returns per laser ring x azimuth, ego-motion compensated with OXTS (removal attacks).

Purpose: a static world seen from the moving car returns about the same number of points per (ring, azimuth) sector in
consecutive scans. The previous scan is moved into the current frame (planar OXTS pose, lidar.ego.between; height unchanged), binned
by elevation ring (64 bins) x 1 degree azimuth, and compared with the current scan: a sector that has far fewer returns than the
static background predicts is suspicious (PointDrop; the real returns that a removal attack deletes).
Why the count and not the tile validity of L2a (S4): removal makes tiles vanish below the validity threshold; the missing returns are
scored directly here, against the prediction.
Inputs: previous and current scan (N x 4), poses (x, y, yaw) of both (lidar.ego.poses), the ring table (results/WP3/S2).
Outputs: Img (count / nearest-return images 64 x 360) and the L2c statistics `miss_*` (dict); `StatUnion` Layer (domain "lidar").
Statistic: miss = 1 - min(window ratio) / median(window ratio), ratio = observed / expected returns in an azimuth window (10 or 20
degrees) over all rings or per group of 8 rings, expected >= EMIN. Dividing by the median removes global effects (speed, weather).
References: static-background / free-space ideas of Sun et al. (CARLO, USENIX Sec 2020); Cao et al. (CCS 2019) for the attacks.
"""
import numpy as np
from scipy.ndimage import minimum_filter

from common.layer import Layer
from lidar import ego

NAZ = 360
NK = 64
R_LO, R_HI = 3.0, 50.0          # m, horizontal range window of the comparison
GROUND_Z = -1.3                 # m (velodyne frame, sensor 1.73 m above ground): returns above are "non-ground"
EMIN_ALL, EMIN_G = 40.0, 20.0   # minimum expected returns of a window
BIG = 1e3


def ring_edges(table):
    """Elevation edges (deg) between the 64 laser rings, from the S2 ring table."""
    e = np.sort(np.asarray(table.elevation_deg(), float))
    return 0.5 * (e[1:] + e[:-1])


class Img:
    """Binned scan: count of returns and nearest return (all / non-ground) per (ring, azimuth degree), horizontal range in [R_LO, R_HI]."""

    def __init__(self, pts, edges):
        x, y, z = pts[:, 0].astype(np.float64), pts[:, 1].astype(np.float64), pts[:, 2].astype(np.float64)
        rho = np.hypot(x, y)
        keep = (rho >= R_LO) & (rho <= R_HI)
        x, y, z, rho = x[keep], y[keep], z[keep], rho[keep]
        k = np.searchsorted(edges, np.degrees(np.arctan2(z, rho)))
        a = np.clip(((np.degrees(np.arctan2(y, x)) + 180.0) % 360.0).astype(np.int64), 0, NAZ - 1)
        flat = k * NAZ + a
        self.cnt = np.bincount(flat, minlength=NK * NAZ).reshape(NK, NAZ).astype(np.float64)
        self.amin = _nearest(flat, rho, NK * NAZ)
        ng = z > GROUND_Z
        self.nmin = _nearest(flat[ng], rho[ng], NK * NAZ)


def _nearest(flat, rho, n):
    img = np.full(n, BIG)
    if len(flat):
        o = np.argsort(-rho, kind="stable")
        img[flat[o]] = rho[o]
    return img.reshape(NK, NAZ)


def moved(prev_pts, pose_prev, pose_cur):
    """Previous scan expressed in the current sensor frame (static world, planar motion)."""
    out = prev_pts.copy()
    out[:, :2] = ego.between(prev_pts[:, :2].astype(np.float64), pose_prev, pose_cur)
    return out


def window_sums(c, w):
    """Circular sums over w consecutive azimuth bins (axis -1), result length NAZ (window starting at each bin)."""
    cc = np.concatenate([c, c[..., :w - 1]], axis=-1)
    cs = np.cumsum(np.concatenate([np.zeros(c.shape[:-1] + (1,)), cc], axis=-1), axis=-1)
    return cs[..., w:w + NAZ] - cs[..., :NAZ]


def _miss(obs, exp, emin):
    """1 - min ratio / median ratio over the windows with exp >= emin (0 when no window qualifies)."""
    ok = exp >= emin
    if ok.sum() < 3:
        return 0.0
    r = obs[ok] / exp[ok]
    med = np.median(r)
    return float(max(0.0, 1.0 - r.min() / max(med, 1e-6)))


def _zmiss(obs, exp, emin):
    """Largest Poisson shortfall (expected - observed) / sqrt(expected) after scaling the expectation by the median ratio."""
    ok = exp >= emin
    if ok.sum() < 3:
        return 0.0
    med = np.median(obs[ok] / exp[ok])
    e = exp[ok] * med
    return float(max(0.0, ((e - obs[ok]) / np.sqrt(np.maximum(e, 1.0))).max()))


def miss_stats(cur, pred):
    """L2c statistics from the current Img and the predicted Img: miss_w10, miss_w20 (all rings), miss_g10, miss_g20 (groups of 8 rings),
    miss_z20 (Poisson shortfall, 20 degree windows), miss_tot (global ratio, informative)."""
    out = {}
    co, ce = cur.cnt, pred.cnt
    for w in (10, 20):
        o, e = window_sums(co.sum(0), w), window_sums(ce.sum(0), w)
        out[f"miss_w{w}"] = _miss(o, e, EMIN_ALL)
        og = window_sums(co.reshape(8, 8, NAZ).sum(1), w)
        eg = window_sums(ce.reshape(8, 8, NAZ).sum(1), w)
        out[f"miss_g{w}"] = _miss(og, eg, EMIN_G)
        if w == 20:
            out["miss_z20"] = _zmiss(o, e, EMIN_ALL)
    out["miss_tot"] = float(max(0.0, 1.0 - co.sum() / max(ce.sum(), 1.0)))
    return out


def dilate(img, rings=1, az=1):
    """Minimum over the (2 rings+1) x (2 az+1) neighbourhood, circular in azimuth."""
    return minimum_filter(img, size=(2 * rings + 1, 2 * az + 1), mode=("nearest", "wrap"))


class StatUnion(Layer):
    """Union of scan statistics: score = max over statistics of the rank of the value in the clean reference (as lidar.density.L2aUnion).
    Reference = pooled clean scans of the train + validation drives (the statistics have no learned parameters, so pooling is out of
    fold by construction); threshold = tie-safe 1 % quantile."""
    domain, kind = "lidar", "physics"

    def __init__(self, layer_id, stats, name="union"):
        super().__init__()
        self.layer_id, self.name, self.stats, self.ref = layer_id, name, list(stats), None

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
        return [f"{self.layer_id}: {self.stats[int(np.argmax(P[i]))]} outside the clean-scan range" for i in range(len(raw))]
