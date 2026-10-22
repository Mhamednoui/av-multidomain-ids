"""WP3 S1 data layer. COPIED from ../codes_v2/lidar/features.py (unchanged logic; v3 never imports v2).

LiDAR detector v2: localized synthetic attacks on KITTI scans and a sector-aware descriptor.

Attacks (each with random severity, so some are subtle):
  PointDrop       points removed inside one azimuth sector (10-60 deg wide, 50-100% removed),
                  i.e. a blind spot rather than a uniform thinning of the whole scan
  IntensitySpoof  intensity raised to 0.8-1.0 inside one sector (5-30 deg), i.e. a
                  retro-reflective or laser-saturated region, not the whole scan
  GhostCluster    one car-sized phantom (4 x 1.8 x 1.5 m on the ground, 5-40 m, any azimuth /
                  heading) of 150-1,500 points placed uniformly inside the box and ADDED to the
                  scan: a proxy for a large point injection. Not physically exact (a spoofer
                  can only create returns along the sensor's rays); physically consistent
                  ray-cast phantoms are tested in lidar/raycast_test.py. Two training attempts
                  with ray-cast phantoms limited to a realistic 50-400 points (replacing, then
                  added) were not separable from normal scans with this scan-level descriptor
                  (validation Normal recall 0.02 and 0.28, detection = false-alarm rate) and
                  were reverted: small realistic phantoms need a local, per-object check.

Temporal (scan-to-scan) features: the descriptor of the current scan minus the descriptor of
the previous scan (0.1 s earlier), plus a few summaries of where the change is largest. A
blind spot or phantom that appears suddenly changes one sector much more than the ego motion
does. When the attack is sustained (same sector / same phantom in both scans) the difference
carries little information and the single-scan features have to do the work.
"""
import numpy as np
from scipy.ndimage import uniform_filter

N_RINGS, N_DIST, N_SECT = 64, 8, 36
CLASSES = ["Normal", "PointDrop", "IntensitySpoof", "GhostCluster"]


def attack_params(name, rng):
    """Random parameters of one attack instance. Drawn once and reused on consecutive scans
    for a sustained attack (same blind sector / same phantom position relative to the car)."""
    if name == "PointDrop":
        return {"c": rng.uniform(-180, 180), "w": rng.uniform(10, 60), "frac": rng.uniform(0.5, 1.0)}
    if name == "IntensitySpoof":
        return {"c": rng.uniform(-180, 180), "w": rng.uniform(5, 30)}
    return {"n": int(rng.integers(150, 1500)), "range": rng.uniform(5, 40), "az": rng.uniform(-180, 180),
            "rot": rng.uniform(0, np.pi)}


BOX_HALF = np.array([2.0, 0.9, 0.75])
MIN_RAYS = 30


def box_hits(pts, p):
    """Rays (sensor origin -> real return) that cross the phantom box before their real return.
    Returns (hit mask, distance to the box along each ray, unit ray directions)."""
    ground = np.percentile(pts[:, 2], 5)
    az = np.radians(p["az"])
    c = np.array([p["range"] * np.cos(az), p["range"] * np.sin(az), ground + BOX_HALF[2]])
    cr, sr = np.cos(p["rot"]), np.sin(p["rot"])
    R = np.array([[cr, sr, 0], [-sr, cr, 0], [0, 0, 1]])           # world -> box frame
    xyz = pts[:, :3].astype(np.float64)
    r = np.linalg.norm(xyz, axis=1)
    d = xyz / np.maximum(r, 1e-6)[:, None]
    o = R @ (-c)
    db = d @ R.T
    with np.errstate(divide="ignore", invalid="ignore"):
        t1, t2 = (-BOX_HALF - o) / db, (BOX_HALF - o) / db
    tmin = np.nanmax(np.minimum(t1, t2), axis=1)
    tmax = np.nanmin(np.maximum(t1, t2), axis=1)
    return (tmin <= tmax) & (tmin > 0.5) & (tmin < r - 0.05), tmin, d


def raycast_ghost(pts, p, rng, mode="budget", retry=False):
    """Ray-cast phantom (test variants, lidar/raycast_test.py). mode: 'budget_add' (added
    returns on at most p['budget'] contiguous rays), 'budget' (same, replacing the real
    returns), 'replace' (every hitting ray replaced), 'add' (every hitting ray gets an added
    return).
    retry=True shifts the azimuth in 25 deg steps until >= MIN_RAYS rays hit the box.
    Returns (attacked scan, number of spoofed returns)."""
    q = dict(p)
    hit, tmin, d = box_hits(pts, q)
    if retry:
        for _ in range(14):
            if hit.sum() >= MIN_RAYS:
                break
            q["az"] = (q["az"] + 25.0 + 180.0) % 360.0 - 180.0
            hit, tmin, d = box_hits(pts, q)
    if mode in ("budget", "budget_add") and hit.sum() > q["budget"]:
        idx = np.flatnonzero(hit)
        ray_az = np.degrees(np.arctan2(d[idx, 1], d[idx, 0]))
        off = np.abs((ray_az - q["az"] + 180) % 360 - 180)
        hit = np.zeros(len(pts), bool)
        hit[idx[np.argsort(off, kind="stable")[:q["budget"]]]] = True
    new = np.c_[d[hit] * tmin[hit, None], rng.choice(pts[:, 3], hit.sum())].astype(np.float32)
    if mode in ("add", "budget_add"):
        return np.vstack([pts, new]), int(hit.sum())
    out = pts.copy()
    out[hit] = new
    return out, int(hit.sum())


def _sector_mask(pts, c, w, max_range=60.0):
    az = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    d = (az - c + 180) % 360 - 180
    r = np.hypot(pts[:, 0], pts[:, 1])
    return (np.abs(d) <= w / 2) & (r <= max_range)


def apply_attack(name, pts, p, rng):
    if name == "PointDrop":
        drop = _sector_mask(pts, p["c"], p["w"]) & (rng.random(len(pts)) < p["frac"])
        return pts[~drop]
    if name == "IntensitySpoof":
        out = pts.copy()
        m = _sector_mask(pts, p["c"], p["w"], max_range=40.0)
        out[m, 3] = rng.uniform(0.8, 1.0, m.sum()).astype(np.float32)
        return out
    return boxcloud_ghost(pts, p, rng)


def boxcloud_ghost(pts, p, rng):
    """GhostCluster training attack: uniform random points inside the box, added to the scan."""
    n, az = p["n"], np.radians(p["az"])
    cx, cy = p["range"] * np.cos(az), p["range"] * np.sin(az)
    ground = np.percentile(pts[:, 2], 5)
    local = np.c_[rng.uniform(-2.0, 2.0, n), rng.uniform(-0.9, 0.9, n), rng.uniform(0.0, 1.5, n)]
    xr = local[:, 0] * np.cos(p["rot"]) - local[:, 1] * np.sin(p["rot"])
    yr = local[:, 0] * np.sin(p["rot"]) + local[:, 1] * np.cos(p["rot"])
    inten = rng.choice(pts[:, 3], n)
    ghost = np.c_[cx + xr, cy + yr, ground + local[:, 2], inten].astype(np.float32)
    return np.vstack([pts, ghost])


def point_drop(pts, rng):
    return apply_attack("PointDrop", pts, attack_params("PointDrop", rng), rng)


def intensity_spoof(pts, rng):
    return apply_attack("IntensitySpoof", pts, attack_params("IntensitySpoof", rng), rng)


def ghost_cluster(pts, rng):
    return apply_attack("GhostCluster", pts, attack_params("GhostCluster", rng), rng)


ATTACKS = {"PointDrop": point_drop, "IntensitySpoof": intensity_spoof, "GhostCluster": ghost_cluster}


def describe(pts: np.ndarray) -> np.ndarray:
    """v1 86-dim descriptor + per-sector counts and intensities + sector summary statistics."""
    x, y, z, it = pts[:, 0], pts[:, 1], pts[:, 2], pts[:, 3]
    r = np.hypot(x, y)
    elev = np.degrees(np.arctan2(z, r))
    ground = z < -1.4
    fg = pts[~ground]
    bb = float(np.ptp(fg[:, 0]) * np.ptp(fg[:, 1]) * np.ptp(fg[:, 2])) if len(fg) > 10 else 0.0
    g = [len(pts), z.mean(), z.std(), it.mean(), it.std(), r.mean(), r.max(), ground.mean(),
         z.mean() - (z[ground].mean() if ground.any() else 0.0), bb,
         np.percentile(it, 90) - np.percentile(it, 10), (it > 0.85).mean(), elev.min(), elev.max()]
    eh = np.histogram(elev, bins=N_RINGS, range=(-25, 15), density=True)[0]
    dh = np.histogram(r, bins=N_DIST, range=(0, 80), density=True)[0]
    az = np.degrees(np.arctan2(y, x))
    sect = np.clip(((az + 180) // (360 / N_SECT)).astype(int), 0, N_SECT - 1)
    near = r < 40
    cnt = np.bincount(sect[near], minlength=N_SECT).astype(float)
    isum = np.bincount(sect[near], weights=it[near], minlength=N_SECT)
    imean = np.divide(isum, cnt, out=np.zeros(N_SECT), where=cnt > 0)
    hi = np.bincount(sect[near], weights=(it[near] > 0.75).astype(float), minlength=N_SECT)
    hifrac = np.divide(hi, cnt, out=np.zeros(N_SECT), where=cnt > 0)
    # density of points 0.2-2.5 m above ground at 5-40 m (where obstacles live)
    obst = near & (r > 5) & (z > np.percentile(z, 5) + 0.2) & (z < np.percentile(z, 5) + 2.5)
    ocnt = np.bincount(sect[obst], minlength=N_SECT).astype(float)
    med = np.median(cnt) + 1
    summ = [cnt.min() / med, np.sort(cnt)[1] / med, cnt.max() / med, cnt.std() / med,
            imean.max() - np.median(imean), hifrac.max(), np.sort(hifrac)[-2],
            ocnt.max() / (np.median(ocnt) + 1), (cnt < 0.3 * med).sum()]
    return np.concatenate([g, eh, dh, cnt / (cnt.sum() + 1), imean, hifrac, summ,
                           occlusion_features(r, elev, az, near)]).astype(np.float32)


def occlusion_features(r, elev, az, near):
    """Physical consistency: a spinning LiDAR gets one return per (beam, azimuth) direction.
    Injected points in front of a real surface create directions with two returns far apart
    in range (the phantom does not hide what is behind it).
    Patch features: a phantom made of added returns produces a COMPACT patch of such
    double-return directions (object-sized: 6 x 25 and 10 x 50 cells = 2.5 x 5 deg and
    4.2 x 10 deg), while vegetation and edges spread them out; max count of double-return
    directions in a sliding window, and that max relative to the scan's 99th percentile."""
    e_bin = np.floor((elev + 25.0) / 0.42).astype(np.int64)
    a_bin = np.floor((az + 180.0) / 0.2).astype(np.int64)
    cell = e_bin * 2000 + a_bin
    sel = near & (r > 3)
    c, rr = cell[sel], r[sel]
    if len(c) == 0:
        return np.zeros(8, dtype=np.float32)
    order = np.argsort(c, kind="stable")
    c, rr = c[order], rr[order]
    start = np.r_[True, c[1:] != c[:-1]]
    gid = np.cumsum(start) - 1
    rmin = np.minimum.reduceat(rr, np.flatnonzero(start))
    rmax = np.maximum.reduceat(rr, np.flatnonzero(start))
    n_in = np.bincount(gid)
    multi = n_in >= 2
    spread = rmax - rmin
    double = multi & (spread > 1.5)
    # sector with the most double-return cells (a phantom is localized)
    a_of_cell = (c[np.flatnonzero(start)] % 2000) * 0.2
    sect = np.clip((a_of_cell // 10).astype(int), 0, 35)
    dsect = np.bincount(sect[double], minlength=36)
    grid = np.zeros((96, 1800), np.float32)
    cid = c[np.flatnonzero(start)][double]
    grid[np.clip(cid // 2000, 0, 95), np.clip(cid % 2000, 0, 1799)] = 1
    patch = []
    for we, wa in ((6, 25), (10, 50)):
        win = uniform_filter(grid, size=(we, wa), mode=("nearest", "wrap")) * (we * wa)
        pos = win[win > 0.5]
        patch += [win.max(), win.max() / (np.percentile(pos, 99) + 1) if len(pos) else 0.0]
    return np.array([double.sum(), double.mean(), dsect.max(), dsect.max() / (np.median(dsect) + 1), *patch],
                    dtype=np.float32)


def feature_names():
    return (["n_pts", "z_mean", "z_std", "i_mean", "i_std", "r_mean", "r_max", "ground_frac",
             "ground_residual", "bb_vol", "i_iqr", "i_high_frac", "elev_min", "elev_max"]
            + [f"elev_{k}" for k in range(N_RINGS)] + [f"dist_{k}" for k in range(N_DIST)]
            + [f"sect_cnt_{k}" for k in range(N_SECT)] + [f"sect_imean_{k}" for k in range(N_SECT)]
            + [f"sect_hifrac_{k}" for k in range(N_SECT)]
            + ["sect_min_ratio", "sect_2nd_min_ratio", "sect_max_ratio", "sect_std_ratio",
               "sect_imean_peak", "sect_hifrac_max", "sect_hifrac_2nd", "obst_peak_ratio", "n_sparse_sect",
               "double_return_cells", "double_return_frac", "double_return_sector_max",
               "double_return_sector_ratio", "dr_patch_max_6x25", "dr_patch_ratio_6x25",
               "dr_patch_max_10x50", "dr_patch_ratio_10x50"])


N_BASE = 211
_CNT, _IMEAN, _HIFRAC = slice(86, 122), slice(122, 158), slice(158, 194)
TEMPORAL_SUMMARY = ["dt_cnt_max", "dt_cnt_min", "dt_imean_max", "dt_hifrac_max", "dt_double_cells",
                    "dt_double_sector_max", "dt_npts_rel"]


def temporal(cur: np.ndarray, prev: np.ndarray) -> np.ndarray:
    """Scan-to-scan change features (len N_BASE + 7). prev = cur gives all zeros (first scan)."""
    d = cur - prev
    summ = [d[_CNT].max(), d[_CNT].min(), d[_IMEAN].max(), d[_HIFRAC].max(), d[203], d[205],
            d[0] / (prev[0] + 1)]
    return np.concatenate([d, summ]).astype(np.float32)


def feature_names_temporal():
    base = feature_names()
    return base + [f"d_{n}" for n in base] + TEMPORAL_SUMMARY
