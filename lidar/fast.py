"""WP8 S3 (v3.1) fast per-scan statistics of the LiDAR domain: the same numbers as the v3 code, computed with one ring assignment per scan.

Purpose: the v3 domain took 1.2-1.8 s per scan: lidar.geometry.RingTable.assign ran three times (segmentation, tiles, L1 statistics),
every iteration over all points x 64 lasers, and the segmenter built a full object table (PCA of ~300 clusters) that the domain never reads
(only the cluster labels feed the L2a tiles). Here: (1) assign_fast = the same algorithm restricted to the points the common mode reads
(15-70 m) in its iterations, float64 and the same final argmin, so (k, res, margin) are bit-identical; (2) cluster_labels = lidar.segment.segment
without object_row; (3) ScanStats computes L1 statistics, tile table and the L2c / L2d pair statistics with ONE assignment, reusing the images
of the previous scan in streaming (prev_img). v3 code (lidar/segment.py, geometry.py, domain.py) is untouched; tests/v31/test_fast.py checks equality.
Inputs: float32 N x 4 scan, ring table, previous scan + planar poses. Outputs: dict of statistics (see ScanStats.compute).
Reference: reports/WP3_S9.md (cost 1.84 s per scan), notes/WP8_v31.md rule L1."""
import numpy as np
from scipy.ndimage import minimum_filter
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from lidar import background as B
from lidar import density as D
from lidar import geometry as G
from lidar import objects as O
from lidar import segment as S
from lidar import track as T
from lidar.s4_build import tiles as make_tiles


def common_mode_fast(res, rho, ab, lo=15.0, hi=70.0, gate=0.06, min_n=8):
    """lidar.geometry.common_mode with the per-bin medians taken from one lexsort (same values: the median of an even count is the mean of the
    two middle values, as numpy does)."""
    sel = (rho >= lo) & (rho <= hi) & (np.abs(res) < gate)
    b, r = ab[sel], res[sel]
    o = np.lexsort((r, b))
    b, r = b[o], r[o]
    cnt = np.bincount(b, minlength=G.NBIN)
    st = np.cumsum(cnt) - cnt
    valid = cnt >= min_n
    c = np.zeros(G.NBIN)
    if valid.any():
        half = cnt // 2
        hi_i = np.where(valid, st + half, 0)
        lo_i = np.where(valid, st + half - 1 + (cnt % 2), 0)       # odd count: both middle indices coincide
        c[valid] = (0.5 * (r[lo_i] + r[hi_i]))[valid]
    return G._smooth_circ(c, valid)


R_MARGIN = 8.0         # m: below it a point cannot be an "unambiguous laser" (max gap between ring lines 0.081 m + tau 0.06 < MARGIN 0.15) and
                       # is outside the 8-80 m ring test: its (k, res, margin) only matter for clustered points (tile ring group)


def assign_fast(table, pts, iters=3, keep=None):
    """Same output as RingTable.assign (k, res, cm, rho, ab, margin) with the common-mode iterations on the far points only.
    keep (bool mask, optional): points whose final (k, res, margin) are needed; the others get k = -1, res = margin = 0 (L1 statistics and
    tiles need only points at >= R_MARGIN m and clustered points, so with keep = (rho >= R_MARGIN) | clustered the results are identical)."""
    rho = np.linalg.norm(pts[:, :3], axis=1)
    ab = G.az_bin(pts)
    far = np.flatnonzero((rho >= 15.0) & (rho <= 70.0))           # the only points common_mode() reads (lo=15, hi=70)
    pf, rf, af = pts[far], rho[far], ab[far]
    cm = np.zeros(G.NBIN)
    kf = None                                                     # the assignment of the previous iteration is the estimate of the next
    for _ in range(iters):
        kf, res, _ = nearest_windowed(table, pf, cm, rf, af, margin=False, k_prev=kf)
        cm = cm + common_mode_fast(res, rf, af)
    if keep is None:
        k, res, mar = nearest_windowed(table, pts, cm, rho, ab)
    else:
        i = np.flatnonzero(keep)
        k, res, mar = np.full(len(pts), -1), np.zeros(len(pts)), np.zeros(len(pts))
        k[i], res[i], mar[i] = nearest_windowed(table, pts[i], cm, rho[i], ab[i])
    return {"k": k, "res": res, "cm": cm, "rho": rho, "ab": ab, "margin": mar}


FULL_BELOW = 4.0       # m: closer than this all 64 lasers are searched
W_NEAR, W_FAR, RHO_FAR = 3, 2, 14.0       # lasers each side of the two-stage slope estimate (see _estimate)


def _estimate(table, z, r_):
    """Laser index estimate in two stages: slope with the mean vertical offset, then with the offset of the first estimate (the offsets
    v_k differ by up to 0.09 m between lasers and shift a one-stage estimate by several lasers at short range)."""
    k0 = np.clip(np.searchsorted(-table.s, -(z - table.v.mean()) / r_), 0, 63)       # table.s decreases with k
    return np.clip(np.searchsorted(-table.s, -(z - table.v[k0]) / r_), 0, 63)


def _best(table, z, r_, k1, W):
    st = np.clip(k1 - W, 0, 64 - (2 * W + 1))
    kc = st[:, None] + np.arange(2 * W + 1)[None, :]
    r = z[:, None] - (table.v[kc] + table.s[kc] * r_[:, None])
    a = np.abs(r)
    j = np.argmin(a, axis=1)
    rows = np.arange(len(z))
    return kc[rows, j], r[rows, j], a, j, rows


def nearest_windowed(table, pts, cm, rho, ab, margin=True, k_prev=None):
    """RingTable.nearest(..., margin) searching only the lasers around an estimate (two-stage slope estimate, or k_prev when the caller
    already has the assignment of a previous iteration). Points nearer than FULL_BELOW m: all 64 lasers. Exact for the fitted ring table
    (tests/v31/test_fast.py compares with the full search on real scans)."""
    n = len(pts)
    k, res, mar = np.zeros(n, int), np.zeros(n), np.zeros(n)
    z = pts[:, 2].astype(np.float64) - cm[ab]
    ok = rho >= FULL_BELOW
    for sel, W in ((ok & (rho < RHO_FAR), W_NEAR), (rho >= RHO_FAR, W_FAR)):
        i = np.flatnonzero(sel)
        if len(i) == 0:
            continue
        k1 = k_prev[i] if k_prev is not None else _estimate(table, z[i], rho[i])
        kk, rr, a, jj, rows = _best(table, z[i], rho[i], k1, W)
        k[i], res[i] = kk, rr
        if margin:
            a[rows, jj] = np.inf
            mar[i] = a.min(axis=1)
    i = np.flatnonzero(~ok)
    if len(i):
        if margin:
            k[i], res[i], mar[i] = table.nearest(pts[i], cm, rho[i], margin=True)
        else:
            k[i], res[i] = table.nearest(pts[i], cm, rho[i])
    return (k, res, mar) if margin else (k, res, None)


def ground_height_fast(pts, extent=60.0):
    """lidar.objects.ground_height with the cell minima from a radix sort instead of np.minimum.at (identical values)."""
    n = int(2 * extent / O.CELL)
    ix = np.clip(((pts[:, 0] + extent) / O.CELL).astype(int), 0, n - 1)
    iy = np.clip(((pts[:, 1] + extent) / O.CELL).astype(int), 0, n - 1)
    flat = ix * n + iy
    o = np.argsort(flat.astype(np.uint16), kind="stable")          # n * n = 3600
    fs, zs = flat[o], pts[o, 2]
    st = np.r_[0, np.flatnonzero(np.diff(fs)) + 1]
    grid = np.full(n * n, np.inf)
    grid[fs[st]] = np.minimum.reduceat(zs, st)
    grid = grid.reshape(n, n)
    fill = np.nanmedian(grid[np.isfinite(grid)]) if np.isfinite(grid).any() else -1.7
    grid[~np.isfinite(grid)] = fill + 5.0
    return minimum_filter(grid, size=5, mode="nearest")[ix, iy]


VOX = 0.1              # m: voxel of the reduced clustering (v3.1; 0 = the exact v3 clustering on all points)


def _cluster_vox(xyz, e0, min_pts, vox):
    """Euclidean clusters of the voxel centroids (link radius e0), mapped back to the points; clusters with < min_pts POINTS dropped."""
    q = np.floor(xyz / vox).astype(np.int64)
    key = (q[:, 0] + 4096) * 16777216 + (q[:, 1] + 4096) * 4096 + (q[:, 2] + 64)
    _, inv = np.unique(key, return_inverse=True)
    cnt = np.bincount(inv).astype(float)
    cen = np.column_stack([np.bincount(inv, weights=xyz[:, j]) / cnt for j in range(3)])
    n = len(cen)
    pr = cKDTree(cen, balanced_tree=False, compact_nodes=False).query_pairs(e0, output_type="ndarray")
    _, lab = connected_components(coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n)), directed=False)
    lp = lab[inv]
    size = np.bincount(lp)
    return np.where(size[lp] >= min_pts, lp, -1)


def cluster_labels(pts, prm, vox=None):
    """Cluster labels of lidar.segment.segment(pts, table, prm, return_labels=True) without building the object table. vox = 0 or None with
    prm["vox"] unset: the exact v3 clustering (identical labels); vox > 0: clustering of voxel centroids (v3.1, about 3x faster, >= 99 % of the
    tiles identical)."""
    prm = dict(S.PARAMS, **(prm or {}))
    vox = prm.get("vox", 0.0) if vox is None else vox
    h = pts[:, 2] - ground_height_fast(pts) if prm["ground"] == "grid" else S.height_above_ground(pts, prm["ground"])[0]
    rho_xy = np.hypot(pts[:, 0], pts[:, 1])
    sel = np.flatnonzero((h > prm["h0"]) & (h < prm["h_max"]) & (rho_xy < prm["r_max"]))
    labels = np.full(len(pts), -1)
    if len(sel) < prm["min_pts"]:
        return labels
    if vox and vox > 0:
        lab = _cluster_vox(pts[sel, :3].astype(np.float64), prm["e0"], prm["min_pts"], vox)
    else:
        lab = S.cluster(pts[sel, :3].astype(np.float64), rho_xy[sel], prm["e0"], prm["e1"], prm["min_pts"],
                        e_near=prm.get("e_near", 0.0), r_near=prm.get("r_near", 20.0))
    keep = lab >= 0
    sel, lab = sel[keep], lab[keep]
    _, inv = np.unique(lab, return_inverse=True)                   # consecutive ids in order of the first label (as the v3 loop)
    labels[sel] = inv
    return labels


class ImgFast(B.Img):
    """lidar.background.Img with the nearest-return images from one 16-bit radix sort instead of two float argsorts (identical arrays)."""

    def __init__(self, pts, edges):
        x, y, z = pts[:, 0].astype(np.float64), pts[:, 1].astype(np.float64), pts[:, 2].astype(np.float64)
        rho = np.hypot(x, y)
        keep = (rho >= B.R_LO) & (rho <= B.R_HI)
        x, y, z, rho = x[keep], y[keep], z[keep], rho[keep]
        k = np.searchsorted(edges, np.degrees(np.arctan2(z, rho)))
        a = np.clip(((np.degrees(np.arctan2(y, x)) + 180.0) % 360.0).astype(np.int64), 0, B.NAZ - 1)
        flat = k * B.NAZ + a
        self.cnt = np.bincount(flat, minlength=B.NK * B.NAZ).reshape(B.NK, B.NAZ).astype(np.float64)
        o = np.argsort(flat.astype(np.uint16), kind="stable")      # NK * NAZ = 23040 < 65536: radix sort
        fs, rs, ng = flat[o], rho[o], (z > B.GROUND_Z)[o]
        self.amin = _cell_min(fs, rs)
        self.nmin = _cell_min(fs[ng], rs[ng])


def _cell_min(fs, rs):
    img = np.full(B.NK * B.NAZ, B.BIG)
    if len(fs):
        st = np.r_[0, np.flatnonzero(np.diff(fs)) + 1]
        img[fs[st]] = np.minimum.reduceat(rs, st)
    return img.reshape(B.NK, B.NAZ)


class IntensityScorer:
    """Per-scan L2a intensity statistics (int_hi, int_lo, cnt_int_hi, cnt_int_lo) of a tile table with the cells of an IntensityModel
    precomputed (IQR per cell); same numbers as ObjectModel.scores + density.scan_scores, without pandas."""

    def __init__(self, model):
        self.nmin = model.nmin
        self.cells = {key: (ref, *np.quantile(ref, [0.25, 0.75])) for key, ref in model.i.items()}

    def tail(self, key, x):
        ref, q1, q3 = self.cells[key] if key in self.cells else self.cells[(key[0], -1)]
        n = len(ref)
        lo, hi = np.searchsorted(ref, x, side="left"), np.searchsorted(ref, x, side="right")
        F = np.clip(0.5 * (lo + hi) / n, 0.5 / n, 1.0 - 0.5 / n)
        iqr = max(q3 - q1, 1e-6)
        return -np.log10(1 - F) + np.maximum(x - ref[-1], 0.0) / iqr, -np.log10(F) + np.maximum(ref[0] - x, 0.0) / iqr

    def n_valid(self, rng, n):
        """Number of tiles the intensity model scores (the denominator of the scale-free count statistics)."""
        return int(((n >= self.nmin) & (rng >= D.R_EDGES[0]) & (rng <= D.R_EDGES[-1])).sum())

    def scan_stats(self, rng, n, im):
        """(int_hi, int_lo, cnt_int_hi, cnt_int_lo) of one scan from its tile arrays (range, n_points, mean intensity)."""
        m = (n >= self.nmin) & (rng >= D.R_EDGES[0]) & (rng <= D.R_EDGES[-1])
        if not m.any():
            return np.zeros(4)
        r_, n_, i_ = rng[m], n[m], im[m]
        rb = np.clip(np.searchsorted(D.R_EDGES, r_, side="right") - 1, 0, len(D.R_EDGES) - 2)
        nb = np.clip(np.searchsorted(D.N_EDGES, n_, side="right") - 1, 0, len(D.N_EDGES) - 2)
        hi, lo = np.zeros(len(r_)), np.zeros(len(r_))
        for r in np.unique(rb):
            mr = rb == r
            for q in np.unique(nb[mr]):
                mq = mr & (nb == q)
                hi[mq], lo[mq] = self.tail((int(r), int(q)), i_[mq])
        return np.array([hi.max(), lo.max(), float((hi >= D.CNT_LEVEL).sum()), float((lo >= D.CNT_LEVEL).sum())])


def z_stats(cur, pred):
    """Extra L2c statistics (v3.1): the Poisson-shortfall rule of background.miss_stats (miss_z20) at windows of 10, 30, 45, 60 degrees over all
    rings, and per group of 8 rings at 20 degrees. Same helper functions and thresholds as v3 (background._zmiss, EMIN_ALL, EMIN_G)."""
    co, ce = cur.cnt, pred.cnt
    out = {}
    for w in (10, 30, 45, 60):
        out[f"miss_z{w}"] = B._zmiss(B.window_sums(co.sum(0), w), B.window_sums(ce.sum(0), w), B.EMIN_ALL)
    out["miss_zg20"] = B._zmiss(B.window_sums(co.reshape(8, 8, B.NAZ).sum(1), 20), B.window_sums(ce.reshape(8, 8, B.NAZ).sum(1), 20), B.EMIN_G)
    return out


class ScanStats:
    """Statistics of one scan for the four headline layers.
    compute(pts, pose, prev) -> (l1 dict-array, tile DataFrame, pair-row dict or None); prev = PrevScan (see below) or None."""

    def __init__(self, table, prm, edges=None):
        self.table, self.prm = table, prm
        self.edges = B.ring_edges(table) if edges is None else edges

    def l1_and_tiles(self, pts, exact=False):
        """(L1 statistics, tile table) of a scan; exact=True: also the tile table of the exact v3 clustering (baseline of the v3 layers)."""
        lab = cluster_labels(pts, self.prm)
        lab3 = cluster_labels(pts, self.prm, vox=0) if exact else lab
        rho = np.linalg.norm(pts[:, :3], axis=1)
        asg = assign_fast(self.table, pts, keep=(rho >= R_MARGIN) | (lab >= 0) | (lab3 >= 0))
        l1 = G.l1_stats(pts, self.table, asg=asg)
        tl = make_tiles(pts, lab, asg["k"])
        return (l1, tl, make_tiles(pts, lab3, asg["k"])) if exact else (l1, tl)

    def pair(self, prev, pts, pose):
        """L2c / L2d statistics of `pts` given prev = PrevScan; the raw image of prev is reused when it is already built."""
        raw = prev.img(self.edges)
        pred = ImgFast(B.moved(prev.pts, prev.pose, pose), self.edges)
        cur = ImgFast(pts, self.edges)
        row = B.miss_stats(cur, pred)
        row.update(T.track_stats(cur, pred, raw))
        row.update(z_stats(cur, pred))
        row["disp"] = float(np.hypot(*(np.asarray(pose[:2], float) - prev.pose[:2])))
        return row, cur

    def compute(self, pts, pose, prev=None, exact=False):
        """(L1 statistics, tiles, [tiles of the exact v3 clustering], pair row or None, range image of this scan)."""
        out = self.l1_and_tiles(pts, exact)
        row, cur = (self.pair(prev, pts, pose) if prev is not None else (None, None))
        return (*out, row, cur)


class PrevScan:
    """The previous scan (points, planar pose) and, once built, its range image (so a stream builds each image once)."""

    def __init__(self, pts, pose, img=None):
        self.pts, self.pose, self._img = pts, np.asarray(pose, float), img

    def img(self, edges):
        if self._img is None:
            self._img = ImgFast(self.pts, edges)
        return self._img
