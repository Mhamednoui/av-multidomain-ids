"""WP3 S2 sensor geometry of the Velodyne HDL-64E as seen in KITTI scans (ring table + L1 measurements).

Purpose: describe what a single-return spinning LiDAR can physically output, and measure how far a point cloud
departs from it. Inputs: N x 4 float32 scans (x y z intensity in [0, 1], KITTI sensor frame). Outputs: ring table
(fitted on TRAIN scans), per-point nearest ring and residual, five L1 scan statistics.

Model. Laser k fires along a ray from (0, 0, h_k) with fixed elevation: its returns lie on z = v_k + s_k * rho
(rho = distance from the sensor origin, v_k ~0.1-0.25 m vertical laser offset, s_k = sin of the laser elevation).
KITTI scans are written ring by ring (65 azimuth-wrap runs: runs 0-63 are the 64 lasers); the ring table is fitted on
train scans using that order (estimation only: the detector never uses the point order). The vehicle pitches / heaves
during the 0.1 s sweep, which shifts all lasers by a common ~0.03 m that depends on the azimuth (time in the sweep):
it is removed per scan as a median over the points of each 2 deg azimuth bin (robust to a minority of injected points).
Single-return physics: one laser gives one return per firing (azimuth step 0.1728 deg at 10 Hz; KITTI neighbours of one
laser are 0.18 deg apart, or 0.09 deg for ~7 % of pairs, and only 0.03 % of the 359k train pairs are closer than 0.02 deg);
two returns of the same laser at the same azimuth (< 0.02 deg) and different ranges cannot come from one single-return
sensor. The test is applied only to points whose laser is unambiguous (runner-up ring farther than 7.5 cm), because at
short range neighbouring lasers are closer than the residual noise.

Spec values (Velodyne HDL-64E S2 manual / data sheet): 64 lasers, vertical FOV +2.0 to -24.8 deg, range accuracy
< 2 cm, range up to 120 m, horizontal resolution 0.1728 deg at 10 Hz (0.08-0.35 deg over 5-20 Hz), intensity 0-255
(KITTI rescales to [0, 1]). References: Velodyne HDL-64E S2 User Manual; Geiger et al., KITTI, IJRR 2013.
"""
import json
from pathlib import Path

import numpy as np

SPEC = {"n_rings": 64, "elev_max": 2.0, "elev_min": -24.8, "range_max": 120.0, "range_acc": 0.02,
        "az_step": 0.1728, "intensity": (0.0, 1.0)}
TAU_Z = 3 * SPEC["range_acc"]          # ring tolerance (m): 3 x range accuracy
NBIN = 180                             # 2 deg azimuth bins for the common mode
RHO_TEST = (8.0, 80.0)                 # ring test range (m): below 8 m the ring spacing is below the tolerance
DUP_DAZ = 0.02                         # deg: below it only 0.03 % of true same-laser neighbours (train, 359k pairs)
MARGIN = 2.5 * TAU_Z                   # runner-up ring at least this far (m): the laser identity is unambiguous
DUP_DRHO = 0.3                         # m: different range at the same direction


def runs_of(pts):
    """Laser index of each point from the azimuth-wrap runs of the file order (estimation only).
    Returns None when the scan does not have the usual 65 runs."""
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    w = np.flatnonzero(np.abs(np.diff(az)) > 100)
    ids = np.r_[0, w + 1, len(pts)]
    if len(ids) - 1 != 65:
        return None
    ring = np.zeros(len(pts), int)
    for k in range(65):
        ring[ids[k]:ids[k + 1]] = k
    return ring


def az_bin(pts):
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    return np.clip(((az + 180.0) // (360.0 / NBIN)).astype(int), 0, NBIN - 1)


def _smooth_circ(c, valid):
    """Fill empty bins from neighbours (circular) and smooth over 3 bins."""
    c = c.copy()
    if valid.sum() == 0:
        return np.zeros_like(c)
    idx = np.flatnonzero(valid)
    c[~valid] = np.interp(np.flatnonzero(~valid), idx, c[idx], period=len(c)) if (~valid).any() else c[~valid]
    return (np.roll(c, 1) + c + np.roll(c, -1)) / 3.0


def common_mode(res, rho, ab, lo=15.0, hi=70.0, gate=0.06, min_n=8):
    """Per-azimuth-bin median of the ring residuals (m) of far points; empty bins are interpolated."""
    c = np.zeros(NBIN)
    valid = np.zeros(NBIN, bool)
    sel = (rho >= lo) & (rho <= hi) & (np.abs(res) < gate)
    order = np.argsort(ab[sel], kind="stable")
    b, r = ab[sel][order], res[sel][order]
    if len(b):
        edges = np.searchsorted(b, np.arange(NBIN + 1))
        for i in range(NBIN):
            seg = r[edges[i]:edges[i + 1]]
            if len(seg) >= min_n:
                c[i], valid[i] = np.median(seg), True
    return _smooth_circ(c, valid)


class RingTable:
    """z = v[k] + s[k] * rho for k = 0..63 (k = 0 the top laser), plus fitted metadata."""

    def __init__(self, v, s, sigma=None, meta=None):
        self.v, self.s = np.asarray(v, float), np.asarray(s, float)
        self.sigma = np.zeros(len(self.v)) if sigma is None else np.asarray(sigma, float)
        self.meta = meta or {}

    def to_dict(self):
        return {"v": self.v.tolist(), "s": self.s.tolist(), "sigma": self.sigma.tolist(), "meta": self.meta}

    @classmethod
    def from_dict(cls, d):
        return cls(d["v"], d["s"], d.get("sigma"), d.get("meta"))

    def save(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=1))

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text()))

    def elevation_deg(self):
        return np.degrees(np.arcsin(self.s))

    def nearest(self, pts, cm=None, rho=None, margin=False):
        """(ring index, residual in m to that ring after subtracting the common mode `cm` per azimuth bin).
        The residual is z - cm(az) - (v_k + s_k rho)."""
        rho = np.linalg.norm(pts[:, :3], axis=1) if rho is None else rho
        z = pts[:, 2].astype(np.float64)
        if cm is not None:
            z = z - cm[az_bin(pts)]
        pred = self.v[None, :] + self.s[None, :] * rho[:, None]
        r = z[:, None] - pred
        a = np.abs(r)
        k = np.argmin(a, axis=1)
        if margin:
            a[np.arange(len(k)), k] = np.inf
            return k, r[np.arange(len(k)), k], a.min(axis=1)
        return k, r[np.arange(len(k)), k]

    def assign(self, pts, iters=3):
        """Nearest ring and residual with a per-scan common mode estimated from the far points.
        Returns dict(k, res, cm, rho): res is the residual AFTER the common mode, raw = res + cm[az]."""
        rho = np.linalg.norm(pts[:, :3], axis=1)
        ab = az_bin(pts)
        cm = np.zeros(NBIN)
        for _ in range(iters):
            k, res = self.nearest(pts, cm, rho)
            cm = cm + common_mode(res, rho, ab)
        k, res, mar = self.nearest(pts, cm, rho, margin=True)
        return {"k": k, "res": res, "cm": cm, "rho": rho, "ab": ab, "margin": mar}


def fit_ring_table(scans, iters=4, rho_range=(4.0, 60.0), gate=0.1):
    """Fit the 64 lines on a list of scans (arrays) with 65 runs; alternate line fits and per-scan common modes."""
    pool = []
    for p in scans:
        ring = runs_of(p)
        if ring is not None:
            pool.append((p, ring, az_bin(p), np.linalg.norm(p[:, :3], axis=1)))
    cm = [np.zeros(NBIN) for _ in pool]
    v, s, sig = np.zeros(64), np.zeros(64), np.zeros(64)
    for _ in range(iters):
        for k in range(64):
            z = np.concatenate([p[ring == k, 2] - cm[j][ab[ring == k]] for j, (p, ring, ab, rr) in enumerate(pool)])
            r = np.concatenate([rr[ring == k] for (p, ring, ab, rr) in pool])
            m = (r > rho_range[0]) & (r < rho_range[1])
            keep = m.copy()
            for _ in range(5):
                c = np.polyfit(r[keep], z[keep], 1)
                e = z - np.polyval(c, r)
                keep = m & (np.abs(e) < gate)
            s[k], v[k] = c
            sig[k] = 1.4826 * np.median(np.abs(e[keep]))
        for j, (p, ring, ab, rr) in enumerate(pool):
            pred = v[ring.clip(0, 63)] + s[ring.clip(0, 63)] * rr
            e = p[:, 2] - pred
            cm[j] = common_mode(e, rr, ab, lo=8.0, hi=50.0, gate=0.15)
    return RingTable(v, s, sig, {"n_scans": len(pool), "az_step_deg": az_step(pool)})


def az_step(pool):
    """Median azimuth step within a ring (deg), from the first usable scans."""
    gaps = []
    for p, ring, ab, rr in pool[:10]:
        az = np.degrees(np.arctan2(p[:, 1], p[:, 0]))
        for k in (20, 30, 40):
            a = az[ring == k]
            d = np.diff(a)
            gaps.append(d[(d > 0) & (d < 1.0)])
    return float(np.median(np.concatenate(gaps)))


def l1_stats(pts, table, r_min=1.0, tau=TAU_Z, asg=None):
    """Five L1 scan statistics (counts):
    n_off_ring       points at 8-80 m whose ring residual exceeds tau (3 x 2 cm)
    sector_off_ring  largest count of such points in one 10 deg sector (a localized injection)
    n_range          points beyond the spec range (120 m) or nearer than r_min
    n_intensity      points with intensity outside [0, 1]
    n_dup            returns of the same (unambiguous) laser within 0.02 deg at a different range (> 0.3 m)"""
    asg = table.assign(pts) if asg is None else asg
    rho, res, k = asg["rho"], asg["res"], asg["k"]
    off = (rho >= RHO_TEST[0]) & (rho <= RHO_TEST[1]) & (np.abs(res) > tau)
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    sect = np.clip(((az + 180.0) // 10).astype(int), 0, 35)
    n_sect = np.bincount(sect[off], minlength=36).max() if off.any() else 0
    n_range = int(((rho > SPEC["range_max"]) | (rho < r_min)).sum())
    it = pts[:, 3]
    n_int = int(((it < SPEC["intensity"][0]) | (it > SPEC["intensity"][1])).sum())
    rel = (np.abs(res) <= tau) & (asg["margin"] >= MARGIN)
    return np.array([off.sum(), n_sect, n_range, n_int, count_duplicates(az[rel], rho[rel], k[rel])], dtype=np.float64)


STAT_NAMES = ["n_off_ring", "sector_off_ring", "n_range", "n_intensity", "n_dup"]


def count_duplicates(az, rho, k, daz=DUP_DAZ, drho=DUP_DRHO):
    """Adjacent (in azimuth, per laser) pairs closer than `daz` degrees whose ranges differ by more than `drho`."""
    order = np.lexsort((az, k))
    ks, a, r = k[order], az[order], rho[order]
    same = ks[1:] == ks[:-1]
    da = np.diff(a)
    close = same & (np.abs(da) < daz) & (np.abs(np.diff(r)) > drho)
    return int(close.sum())


def ideal_cells(asg_k, az, step=SPEC["az_step"]):
    """Sensor-grid cells (lasers spanned x azimuth steps spanned) covered by a set of points of one object."""
    if len(asg_k) == 0:
        return 0.0
    a = az - az[0]
    a = (a + 180.0) % 360.0 - 180.0
    return float((asg_k.max() - asg_k.min() + 1) * (np.ptp(a) / step + 1.0))
