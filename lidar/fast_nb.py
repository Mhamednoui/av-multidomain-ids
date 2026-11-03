"""WP8 S3b (v3.1) numba kernels for the three hot spots of lidar.fast: ring assignment, voxel clustering, range images.

Purpose: S3 brought the LiDAR domain to 0.14-0.18 s per scan (rule L1: median <= 0.10 s). The remaining time is in numpy passes over ~120k points.
Each kernel here is an operation-for-operation mirror of the numpy function it replaces (same float64 arithmetic in the same order, same
tie-breaking, same label order), so the outputs are identical (tests/v31/test_fast_nb.py, tools/WP8_S3b_equal.py), and each has a pure-numpy
fallback: lidar.fast dispatches here only when fast.USE_NUMBA is True (fast.set_numba(True); env AV_LIDAR_NUMBA=1) and numba imports.
Kernels: (1) assign_nb = assign_fast (windowed ring search + per-bin median common mode); (2) cluster_vox_nb = _cluster_vox (voxel centroids,
grid neighbour search at radius e0, union-find, labels in order of the first node as scipy's connected_components); (3) img_nb = ImgFast
(count / nearest return / nearest non-ground return per ring x azimuth degree); (4) ground_min_nb = cell minima of ground_height_fast.
Inputs: float32 N x 4 scans and the arrays lidar.fast already computes (rho, azimuth bin). Outputs: the arrays of the numpy versions.
Reference: reports/WP8_S3b.md, notes/WP8_v31.md (Orchestrator decisions on S3, item 2). Compilation is cached on disk (cache=True): the first
call of a fresh process pays a one-off load (reported separately as warm-up)."""
import numpy as np

try:
    from numba import njit
    AVAILABLE = True
except Exception:                                   # numba missing: callers keep the numpy path
    AVAILABLE = False

    def njit(*a, **k):
        return (lambda f: f) if not (len(a) == 1 and callable(a[0])) else a[0]

NBIN = 180


# ---------------------------------------------------------------- ring assignment
@njit(cache=True)
def _row(z, r_, v, s, k1, W, margin):
    """Window search around k1 (half-width W): (k, residual, margin) with the first minimal |residual|, as numpy argmin."""
    st = min(max(k1 - W, 0), 64 - (2 * W + 1))
    best, kb, rb = np.inf, st, 0.0
    for k in range(st, st + 2 * W + 1):
        r = z - (v[k] + s[k] * r_)
        a = abs(r)
        if a < best:
            best, kb, rb = a, k, r
    m = np.inf
    if margin:
        for k in range(st, st + 2 * W + 1):
            if k != kb:
                a = abs(z - (v[k] + s[k] * r_))
                if a < m:
                    m = a
    return kb, rb, m


@njit(cache=True)
def _full(z, r_, v, s, margin):
    best, kb, rb = np.inf, 0, 0.0
    for k in range(64):
        r = z - (v[k] + s[k] * r_)
        a = abs(r)
        if a < best:
            best, kb, rb = a, k, r
    m = np.inf
    if margin:
        for k in range(64):
            if k != kb:
                a = abs(z - (v[k] + s[k] * r_))
                if a < m:
                    m = a
    return kb, rb, m


@njit(cache=True)
def _search(z, r_, v, s, vmean, ns, kprev, use_prev, margin, w_near, w_far, w_iter, full_below, rho_far):
    """One point of fast.nearest_windowed."""
    if r_ < full_below:
        return _full(z, r_, v, s, margin)
    if use_prev:
        k1 = kprev
    else:
        k0 = min(max(np.searchsorted(ns, -(z - vmean) / r_), 0), 63)
        k1 = min(max(np.searchsorted(ns, -(z - v[k0]) / r_), 0), 63)
    if r_ < rho_far:
        W = w_near
    else:
        W = w_iter if use_prev else w_far
    return _row(z, r_, v, s, k1, W, margin)


@njit(cache=True)
def _nearest_far(zraw, rho, ab, cm, v, s, vmean, ns, kprev, use_prev, w_near, w_far, w_iter, full_below, rho_far):
    n = len(zraw)
    k, res = np.zeros(n, np.int64), np.zeros(n)
    for i in range(n):
        kk, rr, _ = _search(zraw[i] - cm[ab[i]], rho[i], v, s, vmean, ns, kprev[i] if use_prev else 0, use_prev, False,
                            w_near, w_far, w_iter, full_below, rho_far)
        k[i], res[i] = kk, rr
    return k, res


@njit(cache=True)
def _final(zraw, rho, ab, keep, cm, v, s, vmean, ns, w_near, w_far, w_iter, full_below, rho_far):
    n = len(zraw)
    k, res, mar = np.full(n, -1, np.int64), np.zeros(n), np.zeros(n)
    for i in range(n):
        if keep[i]:
            kk, rr, mm = _search(zraw[i] - cm[ab[i]], rho[i], v, s, vmean, ns, 0, False, True, w_near, w_far, w_iter, full_below, rho_far)
            k[i], res[i], mar[i] = kk, rr, mm
    return k, res, mar


@njit(cache=True)
def _bin_median(res, rho, ab, lo, hi, gate, min_n, nbin):
    """Per-bin median of the residuals with rho in [lo, hi] and |res| < gate; (c, valid): bins with < min_n values are invalid."""
    cnt = np.zeros(nbin, np.int64)
    for i in range(len(res)):
        if rho[i] >= lo and rho[i] <= hi and abs(res[i]) < gate:
            cnt[ab[i]] += 1
    st = np.zeros(nbin + 1, np.int64)
    for b in range(nbin):
        st[b + 1] = st[b] + cnt[b]
    buf = np.empty(st[nbin])
    fill = st[:nbin].copy()
    for i in range(len(res)):
        if rho[i] >= lo and rho[i] <= hi and abs(res[i]) < gate:
            buf[fill[ab[i]]] = res[i]
            fill[ab[i]] += 1
    c, valid = np.zeros(nbin), np.zeros(nbin, np.bool_)
    for b in range(nbin):
        if cnt[b] >= min_n:
            a = np.sort(buf[st[b]:st[b + 1]])
            h = cnt[b] // 2
            c[b] = 0.5 * (a[h - 1 + (cnt[b] % 2)] + a[h])
            valid[b] = True
    return c, valid


def assign_nb(table, pts, ab, rho, keep, smooth, iters=3, w_near=3, w_far=2, w_iter=1, full_below=4.0, rho_far=14.0):
    """lidar.fast.assign_fast core: returns (k, res, cm, margin). `smooth` = geometry._smooth_circ; ab, rho as computed by the numpy path."""
    v, s = np.ascontiguousarray(table.v, np.float64), np.ascontiguousarray(table.s, np.float64)
    ns, vmean = -s, float(table.v.mean())
    rho64 = np.ascontiguousarray(rho, np.float64)
    zraw = np.ascontiguousarray(pts[:, 2], np.float64)
    far = np.flatnonzero((rho >= 15.0) & (rho <= 70.0))
    zf, rf, af = zraw[far], rho64[far], np.ascontiguousarray(ab[far], np.int64)
    cm, kf, use = np.zeros(NBIN), np.zeros(len(far), np.int64), False
    for _ in range(iters):
        kf, res = _nearest_far(zf, rf, af, cm, v, s, vmean, ns, kf, use, w_near, w_far, w_iter, full_below, rho_far)
        use = True
        c, valid = _bin_median(res, rf, af, 15.0, 70.0, 0.06, 8, NBIN)
        cm = cm + smooth(c, valid)
    if keep is None:
        keep = np.ones(len(pts), bool)
    k, res, mar = _final(zraw, rho64, np.ascontiguousarray(ab, np.int64), np.ascontiguousarray(keep), cm, v, s, vmean, ns, w_near, w_far, w_iter,
                         full_below, rho_far)
    return k, res, cm, mar


# ---------------------------------------------------------------- voxel clustering
@njit(cache=True)
def _find(p, i):
    while p[i] != i:
        p[i] = p[p[i]]
        i = p[i]
    return i


@njit(cache=True)
def cluster_vox_nb(xyz, e0, min_pts, vox):
    """fast._cluster_vox: labels (-1 = dropped) of the points, clusters of voxel centroids linked within e0, < min_pts points dropped."""
    n = len(xyz)
    key = np.empty(n, np.int64)
    for i in range(n):
        key[i] = ((np.int64(np.floor(xyz[i, 0] / vox)) + 4096) * 16777216 + (np.int64(np.floor(xyz[i, 1] / vox)) + 4096) * 4096
                  + (np.int64(np.floor(xyz[i, 2] / vox)) + 64))
    o = np.argsort(key, kind="mergesort")
    inv = np.empty(n, np.int64)
    m = 0
    for j in range(n):
        if j > 0 and key[o[j]] != key[o[j - 1]]:
            m += 1
        inv[o[j]] = m
    m += 1
    cnt, cen = np.zeros(m), np.zeros((m, 3))
    for i in range(n):                                                # sums in point order, as np.bincount
        cnt[inv[i]] += 1.0
        cen[inv[i], 0] += xyz[i, 0]
        cen[inv[i], 1] += xyz[i, 1]
        cen[inv[i], 2] += xyz[i, 2]
    for g in range(m):
        cen[g, 0] /= cnt[g]
        cen[g, 1] /= cnt[g]
        cen[g, 2] /= cnt[g]
    # grid of cell e0 over the centroids: sort by cell key, look at the 27 neighbouring cells
    cx = np.empty(m, np.int64)
    cy = np.empty(m, np.int64)
    cz = np.empty(m, np.int64)
    ck = np.empty(m, np.int64)
    for g in range(m):
        cx[g], cy[g], cz[g] = np.int64(np.floor(cen[g, 0] / e0)), np.int64(np.floor(cen[g, 1] / e0)), np.int64(np.floor(cen[g, 2] / e0))
        ck[g] = ((cx[g] + 512) * 4096 + (cy[g] + 512)) * 1024 + (cz[g] + 512)
    og = np.argsort(ck, kind="mergesort")
    cks = ck[og]
    cs = np.zeros(m + 1, np.int64)                                     # runs of equal cell key in the sorted order
    nc = 0
    for j in range(m):
        if j == 0 or cks[j] != cks[j - 1]:
            cs[nc] = j
            nc += 1
    cs[nc] = m
    ukey = cks[cs[:nc]]
    par = np.arange(m)
    r2 = e0 * e0
    for c in range(nc):                                                # each cell against itself and its 13 forward neighbour cells
        g0 = og[cs[c]]
        for dx in range(0, 2):
            for dy in range(-1, 2):
                for dz in range(-1, 2):
                    if dx == 0 and (dy < 0 or (dy == 0 and dz < 0)):
                        continue
                    kk = ukey[c] + (dx * 4096 + dy) * 1024 + dz
                    if dx == 0 and dy == 0 and dz == 0:
                        c2 = c
                    else:
                        c2 = np.searchsorted(ukey, kk)
                        if c2 >= nc or ukey[c2] != kk:
                            continue
                    for ia in range(cs[c], cs[c + 1]):
                        g = og[ia]
                        for ib in range(cs[c2], cs[c2 + 1]):
                            h = og[ib]
                            if c2 == c and ib <= ia:
                                continue
                            ddx, ddy, ddz = cen[g, 0] - cen[h, 0], cen[g, 1] - cen[h, 1], cen[g, 2] - cen[h, 2]
                            if ddx * ddx + ddy * ddy + ddz * ddz <= r2:
                                ra, rb = _find(par, g), _find(par, h)
                                if ra != rb:
                                    par[max(ra, rb)] = min(ra, rb)
    lab = np.full(m, -1, np.int64)                                     # component ids in order of the lowest node, as scipy
    nl = 0
    for g in range(m):
        r = _find(par, g)
        if lab[r] < 0:
            lab[r] = nl
            nl += 1
        lab[g] = lab[r]
    size = np.zeros(nl, np.int64)
    for i in range(n):
        size[lab[inv[i]]] += 1
    out = np.empty(n, np.int64)
    for i in range(n):
        l = lab[inv[i]]
        out[i] = l if size[l] >= min_pts else -1
    return out


# ---------------------------------------------------------------- range image and ground cells
@njit(cache=True)
def img_nb(pts, edges, r_lo, r_hi, naz, nk, big, ground_z):
    """fast.ImgFast arrays (cnt, amin, nmin), flattened NK * NAZ, from the float32 scan."""
    cnt, amin, nmin = np.zeros(nk * naz), np.full(nk * naz, big), np.full(nk * naz, big)
    d = 180.0 / np.pi
    for i in range(len(pts)):
        x, y, z = np.float64(pts[i, 0]), np.float64(pts[i, 1]), np.float64(pts[i, 2])
        rho = np.hypot(x, y)
        if rho >= r_lo and rho <= r_hi:
            k = np.searchsorted(edges, np.arctan2(z, rho) * d)
            a = min(max(np.int64(((np.arctan2(y, x) * d + 180.0) % 360.0)), 0), naz - 1)
            f = k * naz + a
            cnt[f] += 1.0
            if rho < amin[f]:
                amin[f] = rho
            if z > ground_z and rho < nmin[f]:
                nmin[f] = rho
    return cnt, amin, nmin


@njit(cache=True)
def ground_min_nb(pts, extent, cell, n):
    """fast.ground_height_fast grid before the filter: per-cell minimum z (inf where empty) and the cell index of each point."""
    grid = np.full(n * n, np.inf)
    flat = np.empty(len(pts), np.int64)
    for i in range(len(pts)):
        ix = min(max(np.int64((np.float32(pts[i, 0]) + np.float32(extent)) / np.float32(cell)), 0), n - 1)      # float32 arithmetic as numpy
        iy = min(max(np.int64((np.float32(pts[i, 1]) + np.float32(extent)) / np.float32(cell)), 0), n - 1)
        flat[i] = ix * n + iy
        if pts[i, 2] < grid[flat[i]]:
            grid[flat[i]] = pts[i, 2]
    return grid, flat
