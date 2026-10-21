"""WP2 S5: L3 per-signal predictors for CAN (ROAD), trained on attack-free decoded signals only.

Purpose: catch masquerade that keeps a signal plausible and self-consistent in time but inconsistent with the signals physically tied to it
(wheel speeds vs speedometer vs other speed copies, a temperature byte vs the other thermal signals). Two sub-detectors:
  L3c  one ridge predictor per continuous signal (138 signals of the S4 catalog) on the 0.05 s sample-and-hold grid. Features: all OTHER continuous signals at the
       same grid step ("cross") and, optionally, the signal's own value 0.05 / 0.25 / 1.0 s earlier ("cross+own"); causal (nothing after t is used).
       Residual standardised by sigma_j = the LARGEST per-capture RMS of out-of-fold (inner leave-one-capture-out) residuals (conservative across
       sessions): z_j = min(|r_j| / sigma_j, 1000). Signals whose out-of-fold R2 is below r_min are not used. Score of a grid step = max_j z_j ("max")
       or max_j of the windowed CUSUM_j = sum over the last 1 s of max(z - 3, 0) ("cusum"; bounded, so a persistent session offset cannot accumulate).
  L3d  lag-aware state predictor for the reverse-light bit: gear code -> expected flag from three redundant gear copies; a grid step contradicts when >= 2 of the 3
       copies contradict the held flag; score = seconds of contradiction within the last 1 s. A lag of a few frames between lever and light scores ~0; a masquerade
       that holds the flag against the gear for seconds scores ~1.
Everything is computed from summable sufficient statistics (Gram matrices per capture), so leave-one-capture-out and nested hyper-parameter selection are cheap.
Inputs: grids (tools/WP2_S5_grids.py), timestamps. Outputs: grid-level scores, mapped to frames / 1 s windows.
References: Verma et al. 2022 (ROAD); Kang et al. 2018 and Wasicek et al. 2017 (signal prediction for in-vehicle intrusion detection); Page 1954 (CUSUM).
"""
import numpy as np
from scipy.linalg import cho_factor, cho_solve

from can.l1 import CanRule

LAGS = (1, 5, 20)                      # grid steps (0.05, 0.25, 1.0 s)
LAMBDAS = (1e-4, 1e-3, 1e-2, 1e-1)
ZMAX = 1000.0
CUSUM_K = 3.0
L3D_WIN = 20                           # grid steps = 1 s
GRID_DT = 0.05
PURITY = 0.99                          # gear code -> flag rule only when >= 99% of the clean samples agree


# ------------------------------------------------------------------ design matrix
def standardise(G, mu, sd):
    """Raw grid (n x p, NaN before an ID's first frame) -> z-scored, NaN imputed by the mean (0)."""
    Z = (np.asarray(G, np.float64) - mu) / sd
    Z[~np.isfinite(Z)] = 0.0
    return Z


def lag_stack(Z, lags=LAGS):
    """[Z, Z(t-l1), Z(t-l2), ...] n x (p*(1+len(lags))); lags clamp to the first row (causal)."""
    n = len(Z)
    out = [Z]
    for l in lags:
        idx = np.maximum(np.arange(n) - l, 0)
        out.append(Z[idx])
    return np.concatenate(out, axis=1)


def scale_constants(grids):
    """Per-signal mean / sd over the clean fit captures (NaN aware). Constants of the feature scaling only."""
    n = sum((~np.isnan(g)).sum(0) for g in grids)
    s = sum(np.nansum(g.astype(np.float64), 0) for g in grids)
    mu = s / np.maximum(n, 1)
    s2 = sum(np.nansum((g.astype(np.float64) - mu) ** 2, 0) for g in grids)
    sd = np.sqrt(s2 / np.maximum(n, 1))
    return mu, np.maximum(sd, 1e-6)


class Gram:
    """Sufficient statistics of one capture: n, sum, X'X for X = [signals at t, lags...] (standardised, imputed)."""

    def __init__(self, G, mu, sd, chunk=8000):
        X = lag_stack(standardise(G, mu, sd))
        d = X.shape[1]
        self.n, self.s, self.A = len(X), X.sum(0), np.zeros((d, d))
        for a in range(0, len(X), chunk):
            c = X[a:a + chunk]
            self.A += c.T @ c


def sum_grams(gs):
    n = sum(g.n for g in gs)
    return n, sum(g.s for g in gs), sum(g.A for g in gs)


def ridge_fit(n, s, A, F, j, lam):
    """Ridge of column j on columns F (centred, standardised-by-construction features), from sufficient statistics. Returns (b, b0)."""
    mu = s / n
    C = A[np.ix_(F, F)] / n - np.outer(mu[F], mu[F])
    c = A[F, j] / n - mu[F] * mu[j]
    sdF = np.sqrt(np.maximum(np.diag(C), 1e-12))
    Cn = C / np.outer(sdF, sdF) + lam * np.eye(len(F))      # correlation matrix + ridge
    b = cho_solve(cho_factor(Cn), c / sdF) / sdF
    return b, float(mu[j] - mu[F] @ b)


def sse(g: Gram, F, j, b, b0):
    """Sum of squared residuals of y_j = b0 + X_F b on the capture of Gram g."""
    return float(g.A[j, j] - 2 * b @ g.A[F, j] + b @ g.A[np.ix_(F, F)] @ b - 2 * b0 * (g.s[j] - b @ g.s[F]) + g.n * b0 * b0)


def feature_sets(p, own: bool):
    """Column indices (in the lag_stack layout) used for each target signal j."""
    out = []
    for j in range(p):
        F = [c for c in range(p) if c != j]
        if own:
            F += [p * (m + 1) + j for m in range(len(LAGS))]
        out.append(np.array(F))
    return out


class L3cModel:
    """Fitted per-signal ridge predictors for one feature set (cross or cross+own)."""


def fit_l3c(grams: dict, fit_names, inner_names, mu, sd, own: bool) -> L3cModel:
    """Fit on the captures `fit_names`; the ridge lambda, sigma and R2 of every signal come from inner leave-one-capture-out
    over `inner_names` (subset of fit_names: the captures allowed to be held out). Nested: nothing of any outer held-out capture is used."""
    p = len(mu)
    sets = feature_sets(p, own)
    G_fit = [grams[n] for n in fit_names]
    n_all, s_all, A_all = sum_grams(G_fit)
    M = L3cModel()
    M.own, M.mu, M.sd = own, mu, sd
    M.W = np.zeros((p * (1 + len(LAGS)), p))
    M.b0, M.sigma, M.r2, M.lam = np.zeros(p), np.ones(p), np.zeros(p), np.zeros(p)
    M.sigma_rms = np.ones(p)
    inner = [grams[n] for n in inner_names]
    tot_n = sum(g.n for g in inner)
    for j in range(p):
        F = sets[j]
        best = None
        for lam in LAMBDAS:
            parts = []
            for g in inner:
                b, b0 = ridge_fit(n_all - g.n, s_all - g.s, A_all - g.A, F, j, lam)
                parts.append(sse(g, F, j, b, b0))
            tot = sum(parts)
            if best is None or tot < best[0]:
                best = (tot, lam, parts)
        tot, lam, parts = best
        var = sum(g.A[j, j] for g in inner) / tot_n - (sum(g.s[j] for g in inner) / tot_n) ** 2
        M.sigma_rms[j] = np.sqrt(tot / tot_n)
        M.sigma[j] = max(max(np.sqrt(max(sp, 0.0) / g.n) for sp, g in zip(parts, inner)), 1e-6)
        M.r2[j] = 1.0 - (tot / tot_n) / max(var, 1e-12)
        M.lam[j] = lam
        b, b0 = ridge_fit(n_all, s_all, A_all, F, j, lam)
        M.W[F, j], M.b0[j] = b, b0
    return M


def z_matrix(M: L3cModel, G):
    """Standardised residuals |r| / sigma (n x p float32, winsorised); 0 where the target signal has no value yet."""
    X = lag_stack(standardise(G, M.mu, M.sd))
    r = X[:, :len(M.mu)] - (X @ M.W + M.b0)
    z = np.minimum(np.abs(r) / M.sigma, ZMAX)
    z[~np.isfinite(np.asarray(G, np.float64))] = 0.0
    return z.astype(np.float32)


def grid_scores(M: L3cModel, G, r_min: float, agg: str, return_argmax=False):
    """Grid-level L3c score (n,) for min R2 r_min and aggregator 'max' | 'cusum'."""
    z = z_matrix(M, G)
    use = M.r2 >= r_min
    z = z[:, use]
    if agg == "cusum":
        cs = np.cumsum(np.vstack([np.zeros((1, z.shape[1])), np.maximum(z - CUSUM_K, 0.0)]), axis=0, dtype=np.float64)
        idx = np.arange(1, len(z) + 1)
        z = (cs[idx] - cs[np.maximum(idx - L3D_WIN, 0)]).astype(np.float32)
    sc = z.max(1)
    if return_argmax:
        return sc, np.flatnonzero(use)[z.argmax(1)]
    return sc


# ------------------------------------------------------------------ L3d
class L3dModel:
    """Gear code -> expected reverse flag, per gear copy, from clean captures."""


def fit_l3d(Gds) -> L3dModel:
    """Gds: list of clean grids (n x 4: reverse bit, 3 gear copies)."""
    D = np.concatenate([g[np.isfinite(g).all(1)] for g in Gds])
    M = L3dModel()
    M.maps = []
    for k in range(1, D.shape[1]):
        m = {}
        for code in np.unique(D[:, k]):
            f = D[D[:, k] == code, 0]
            p1 = float((f == 1).mean())
            if max(p1, 1 - p1) >= PURITY:
                m[float(code)] = float(p1 >= 0.5)
        M.maps.append(m)
    return M


def l3d_scores(M: L3dModel, Gd) -> np.ndarray:
    """Seconds of contradiction (>= 2 of 3 gear copies against the held flag) within the last 1 s, per grid step."""
    n = len(Gd)
    votes = np.zeros(n, np.int8)
    for k, m in enumerate(M.maps, start=1):
        for code, exp in m.items():
            votes += ((Gd[:, k] == code) & (Gd[:, 0] != exp) & np.isfinite(Gd[:, 0])).astype(np.int8)
    c = (votes >= 2).astype(np.float64)
    cs = np.cumsum(np.r_[0.0, c])
    idx = np.arange(1, n + 1)
    return ((cs[idx] - cs[np.maximum(idx - L3D_WIN, 0)]) * GRID_DT).astype(np.float32)


# ------------------------------------------------------------------ grid -> frames / windows
def grid_index(tm, t0, n):
    """Grid step of each frame (-1 before the grid starts: those frames are not scored)."""
    gi = np.floor((tm - t0) / GRID_DT).astype(np.int64)
    gi = np.where(gi < 0, -1, np.minimum(gi, n - 1))
    return gi


def frame_scores(gs, tm, t0):
    """Frame score = score of the grid step containing the frame; 0 before the grid starts."""
    gi = grid_index(tm, t0, len(gs))
    return np.where(gi >= 0, gs[np.maximum(gi, 0)], 0.0).astype(np.float32)


def window_scores(gs, tm, t0, starts):
    """1 s window score (windows from can.l1_signals-style running-max time, `starts` = first frame of each window) = max of the grid steps
    inside the same integer second; 0 for a window without grid step."""
    g = t0 + GRID_DT * np.arange(len(gs))
    gsec = np.floor(g).astype(np.int64)
    ub, first = np.unique(gsec, return_index=True)
    mx = np.maximum.reduceat(gs, first)
    wsec = np.floor(tm[starts]).astype(np.int64)
    pos = np.minimum(np.searchsorted(ub, wsec), len(ub) - 1)
    ok = ub[pos] == wsec
    return np.where(ok, mx[pos], 0.0).astype(np.float32), ok


class L3Layer(CanRule):
    """L3 sub-detector as a Layer. samples = dict with F['l3_raw'] (frame or window scores, already computed); calibrate_from_raw gives the
    LOCO tie-safe 1% threshold."""
    name = "can.l3_predictors"
    layer_id = "L3"
    kind = "normal_model"
    why = "decoded signals disagree with the signals that physically predict them (prediction residual / lagged state contradiction)"

    def __init__(self, unit="frame", part="c"):
        super().__init__(None, unit)
        self.part = part
        self.name = f"can.l3{part}_predictors"

    def frame_raw(self, F):
        return F["l3_raw"]

    def clone(self, unit):
        return L3Layer(unit, self.part)
