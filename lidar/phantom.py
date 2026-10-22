"""WP3 S2 calibrated ray-cast phantom generator (replaces the S1 generator for the evaluation attacks).

What a physical spoofer can do (Cao et al., CCS 2019; Sun et al., CARLO, USENIX Sec 2020): fire pulses so that the
victim laser k, at azimuth phi, receives a return at a chosen range along ITS OWN ray. So a phantom return lies on the
ray from the laser origin (0, 0, h_k) along (phi, elevation_k), i.e. on the laser's ring line z = v_k + s_k * rho, and
it occludes whatever is behind it on that ray. This generator takes the rays of the REAL scan (laser k and azimuth of
every real return, from lidar.geometry), intersects them with a car-sized box (4 x 1.8 x 1.5 m on the ground, as in
S1) and places the phantom return on the first box surface along the ray, keeping the real return's own residual to
its ring (pitch / noise), so a phantom point is indistinguishable from a real one by ring geometry.
Difference to S1 (lidar.raycast / v2 raycast_ghost): S1 shortened the ray from the sensor ORIGIN, which moves the
point up to ~0.1 m off its ring; and S1's phantom was denser than a real object (ideal surface, every ray returns).
Calibration (lidar.calibration, fitted on TRAIN scans): a phantom has a return probability pi ~ Beta(mean p(range),
kappa) (beam dropout / dark surfaces; per-ray p(rho) / p(range centre)), and its intensities are drawn from a real
object of the same range band (library of car-like clusters). Order: ray hits -> dropout -> budget (the attacker's
50-400 point capacity applies to the injected returns) -> mode (add keeps the real return = multi-return assumption;
replace overwrites it = single-return sensor, the physics bound; since S2b `add` also overwrites it, see phantom()).
"""
import numpy as np

from lidar.features import BOX_HALF, MIN_RAYS

MODES = ("add", "replace", "budget_add", "budget")


def prepare(pts, table):
    """Rays of a real scan: laser index, origin O_i = (0, 0, h_k + residual), unit direction and real distance."""
    asg = table.assign(pts)
    k = asg["k"]
    s, v = table.s[k], table.v[k]
    raw_res = asg["res"] + asg["cm"][asg["ab"]]
    O = np.zeros((len(pts), 3))
    O[:, 2] = v / (1.0 - s * s) + raw_res
    d = pts[:, :3].astype(np.float64) - O
    t = np.linalg.norm(d, axis=1)
    return {"k": k, "O": O, "u": d / np.maximum(t, 1e-6)[:, None], "t": t, "asg": asg}


def box_pose(pts, p):
    ground = np.percentile(pts[:, 2], 5)
    az = np.radians(p["az"])
    c = np.array([p["range"] * np.cos(az), p["range"] * np.sin(az), ground + BOX_HALF[2]])
    cr, sr = np.cos(p["rot"]), np.sin(p["rot"])
    return c, np.array([[cr, sr, 0], [-sr, cr, 0], [0, 0, 1]])


def box_hits_rays(pts, rays, p):
    """Rays crossing the box before their real return: (mask, distance to the first surface)."""
    c, R = box_pose(pts, p)
    o = (rays["O"] - c) @ R.T
    db = rays["u"] @ R.T
    with np.errstate(divide="ignore", invalid="ignore"):
        t1, t2 = (-BOX_HALF - o) / db, (BOX_HALF - o) / db
    tmin = np.nanmax(np.minimum(t1, t2), axis=1)
    tmax = np.nanmin(np.maximum(t1, t2), axis=1)
    return (tmin <= tmax) & (tmin > 0.5) & (tmin < rays["t"] - 0.05), tmin


def place(pts, rays, p):
    """Azimuth shift (25 deg steps) until >= MIN_RAYS rays hit, as in S1 / v2."""
    q = dict(p)
    for _ in range(14):
        if box_hits_rays(pts, rays, q)[0].sum() >= MIN_RAYS:
            break
        q["az"] = (q["az"] + 25.0 + 180.0) % 360.0 - 180.0
    return q


class Calib:
    """Return-probability and intensity model of real car-like objects (fitted on train)."""

    def __init__(self, edges, p, kappa, library):
        self.edges, self.p, self.kappa = np.asarray(edges, float), np.asarray(p, float), float(kappa)
        self.library = library          # list (per range bin) of lists of intensity arrays

    def centres(self):
        return 0.5 * (self.edges[1:] + self.edges[:-1])

    def mean_p(self, rho):
        return np.clip(np.interp(rho, self.centres(), self.p), 0.02, 1.0)

    def bin_of(self, rho):
        return int(np.clip(np.searchsorted(self.edges, rho) - 1, 0, len(self.p) - 1))

    def draw_pi(self, rho, rng):
        m = self.mean_p(rho)
        if not np.isfinite(self.kappa):
            return float(m)
        return float(rng.beta(max(m * self.kappa, 1e-3), max((1 - m) * self.kappa, 1e-3)))

    def draw_intensity(self, rho, n, rng):
        b = self.bin_of(rho)
        for off in (0, 1, -1, 2, -2, 3, -3):
            j = b + off
            if 0 <= j < len(self.library) and len(self.library[j]):
                lib = self.library[j]
                return rng.choice(lib[rng.integers(len(lib))], n).astype(np.float32)
        raise ValueError("empty intensity library")


def phantom(pts, rays, p, rng, mode, calib=None, single_return=True):
    """Attacked scan, number of injected returns, parameters used, indices of the real rays used.
    calib=None: no dropout and intensity from random real points (S1 behaviour on exact rays).
    single_return=True (default since S2b): KITTI's HDL-64E reports one return per beam, so an injected return REPLACES the
    real return behind it on the same ray: add == replace and budget_add == budget. single_return=False keeps the real
    return (multi-return sensor assumption of S1 / S2, only used to reproduce the old numbers)."""
    if mode not in MODES:
        raise ValueError(mode)
    q = place(pts, rays, p)
    hit, tmin = box_hits_rays(pts, rays, q)
    idx = np.flatnonzero(hit)
    if calib is not None and len(idx):
        pi = calib.draw_pi(q["range"], rng)
        rho_hit = np.linalg.norm(rays["O"][idx] + rays["u"][idx] * tmin[idx, None], axis=1)
        pr = np.minimum(1.0, pi * calib.mean_p(rho_hit) / calib.mean_p(q["range"]))
        idx = idx[rng.random(len(idx)) < pr]
    if mode in ("budget", "budget_add") and len(idx) > q["budget"]:
        ray_az = np.degrees(np.arctan2(rays["u"][idx, 1], rays["u"][idx, 0]))
        off = np.abs((ray_az - q["az"] + 180) % 360 - 180)
        idx = idx[np.argsort(off, kind="stable")[:q["budget"]]]
    xyz = rays["O"][idx] + rays["u"][idx] * tmin[idx, None]
    inten = (calib.draw_intensity(q["range"], len(idx), rng) if calib is not None
             else rng.choice(pts[:, 3], len(idx)).astype(np.float32))
    new = np.c_[xyz, inten].astype(np.float32)
    if mode in ("add", "budget_add") and not single_return:
        return np.vstack([pts, new]), int(len(idx)), q, idx
    out = pts.copy()
    out[idx] = new
    return out, int(len(idx)), q, idx
