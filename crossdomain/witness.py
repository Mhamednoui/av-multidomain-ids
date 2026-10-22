"""WP6 S1: motion-witness layer core: MotionEstimate streams -> common 1 Hz grid -> per-pair normalised residuals.

Purpose: several domains observe the same ego motion (GPS claim, IMU gyro, LiDAR odometry, CAN wheel speed, V2X
self-report). This module puts their MotionEstimate streams on one time grid, estimates the latency between two
streams, and turns every pair into residuals normalised by the published sigmas (z ~ N(0, 1) when both are honest
and clean). S2 ("which domain lies") consumes the z tables; S1 gives no attack verdict.
Inputs: lists of common.motion.MotionEstimate (one source each), or native-rate (t, value) arrays for latency.
Outputs: pandas DataFrames (frame / grid / pair tables), lag estimates, SigmaModel, honesty statistics.

Alignment (documented choice, notes/WP6_crossdomain.md):
  - every quantity is compared as its MEAN over the second (t - 1, t] on an integer-second grid;
  - "mean" sources (displacement over the last second: gps, lidar) already are; their rows are matched to the grid
    point within 0.05 s;
  - "inst" sources (instantaneous samples: can held wheel speed, imu gyro, gnss Doppler velocity, v2x) are
    integrated piecewise-linearly (cumulative trapezoid) and the integral over (t - 1, t] is taken: at 1 Hz this is the
    trapezoid of the samples at t - 1 and t, exact for a constant acceleration; no extrapolation, gaps > max_gap s
    inside the second drop the grid point;
  - a latency L (stream b lags stream a: b(t) = a(t - L)) is removed by shifting b's timestamps by -L before gridding.
Latency: argmax over lags of the pooled cross-covariance of the first differences (accelerations / yaw accelerations)
  on a uniform dt grid, groups pooled by summing their covariances; parabolic refinement; CI by bootstrap over groups.
References: Bar-Shalom, Li & Kirubarajan 2001 (normalised innovation consistency, NEES/NIS); Knapp & Carter 1976
  (generalised cross-correlation for time-delay estimation); Furgale et al. 2013 (temporal calibration of sensors).
"""
import numpy as np
import pandas as pd

COLS = ["t", "source", "speed", "yaw_rate", "dx", "dy", "sigma"]
SOURCE_KIND = {"gps": "mean", "lidar": "mean", "can": "inst", "imu": "inst", "gnss": "inst", "wheel": "inst", "v2x": "inst"}

# 1-sigma models of the quantities the contract publishes no sigma for (WP6-derived from the producers' documented
# noise models; rad/s and m). See notes/WP6_crossdomain.md, S1.
COMPASS_SIGMA_RAD = np.radians(2.0)                    # gps/stream.py: compass heading noise per fix
YAW_SIGMA = {
    "gps": float(np.sqrt(2.0) * COMPASS_SIGMA_RAD),    # heading difference of two independent compass fixes over 1 s
    "imu": 0.005 / np.sqrt(2.0),                       # gyro N(0, 0.005) per sample, trapezoid of two samples
    "lidar": 0.0015,                                   # S5_odometry.json: median 1 s yaw error 0.0567 deg -> sigma = median / 0.6745
}
LIDAR_YAW_SIGMA = YAW_SIGMA["lidar"]


def to_frame(estimates, source=None):
    """MotionEstimate list -> DataFrame(COLS) sorted by t (displacement split into dx, dy; None -> NaN)."""
    rows = []
    for e in estimates:
        d = e.displacement if e.displacement is not None else (np.nan, np.nan)
        rows.append((e.t, source or e.source, np.nan if e.speed is None else e.speed,
                     np.nan if e.yaw_rate is None else e.yaw_rate, d[0], d[1], e.sigma))
    f = pd.DataFrame(rows, columns=COLS)
    return f.sort_values("t", kind="stable").reset_index(drop=True)


def _interval_mean(t, v, grid, w=1.0, max_gap=1.5):
    """Mean of the piecewise-linear signal (t, v) over (g - w, g] for every grid point g; NaN without support."""
    ok = np.isfinite(v)
    t, v = t[ok], v[ok]
    out = np.full(len(grid), np.nan)
    if len(t) < 2:
        return out
    I = np.r_[0.0, np.cumsum(0.5 * (v[1:] + v[:-1]) * np.diff(t))]
    a, b = grid - w, grid
    inside = (a >= t[0] - 1e-9) & (b <= t[-1] + 1e-9)
    Ia, Ib = np.interp(a, t, I), np.interp(b, t, I)
    gaps = np.r_[0.0, np.diff(t)]
    # largest gap touching (a, b]: samples with index in [ia, ib] (ia = first sample > a, ib = first sample >= b)
    ia = np.searchsorted(t, a, side="right")
    ib = np.minimum(np.searchsorted(t, b, side="left"), len(t) - 1)
    big = np.flatnonzero(gaps > max_gap)
    bad = np.zeros(len(grid), bool)
    if len(big):
        # a gap ending at sample j covers (t[j-1], t[j]); it intersects (a, b] when ia <= j <= ib
        pos = np.searchsorted(big, ia, side="left")
        nxt = np.where(pos < len(big), big[np.minimum(pos, len(big) - 1)], len(t) + 1)
        bad = nxt <= ib
    out[inside & ~bad] = ((Ib - Ia) / w)[inside & ~bad]
    return out


def to_grid(frame, grid, kind=None, lag=0.0, tol=0.05, max_gap=1.5):
    """One source frame -> values on the integer-second grid (index = grid time): speed, yaw_rate, dx, dy, sigma.
    kind "mean" (default for gps / lidar): rows matched within tol; "inst": interval mean over (g - 1, g]."""
    src = frame["source"].iloc[0] if len(frame) else "?"
    kind = kind or SOURCE_KIND.get(src, "inst")
    grid = np.asarray(grid, float)
    t = frame["t"].to_numpy(float) - lag
    cols = ["speed", "yaw_rate", "dx", "dy", "sigma"]
    out = pd.DataFrame(np.nan, index=pd.Index(grid, name="t"), columns=cols)
    if not len(frame):
        return out
    if kind == "mean":
        j = np.clip(np.searchsorted(t, grid), 0, len(t) - 1)
        jm = np.clip(j - 1, 0, len(t) - 1)
        j = np.where(np.abs(t[jm] - grid) < np.abs(t[j] - grid), jm, j)
        hit = np.abs(t[j] - grid) <= tol
        for c in cols:
            v = frame[c].to_numpy(float)[j]
            out[c] = np.where(hit, v, np.nan)
    else:
        for c in cols:
            out[c] = _interval_mean(t, frame[c].to_numpy(float), grid, max_gap=max_gap)
    return out


def yaw_sigma(source, n=1):
    return np.full(n, YAW_SIGMA.get(source, np.nan))


def pair_table(ga, gb, a, b, quantity="speed", sa=None, sb=None):
    """Residual table of one pair on a common grid: r = q_a - q_b, s = sqrt(sa^2 + sb^2), z = r / s, v = mean speed.
    sa / sb: arrays of 1-sigma (default: the published speed sigma for speed, YAW_SIGMA for yaw_rate)."""
    j = ga.join(gb, how="inner", lsuffix="_a", rsuffix="_b")
    qa, qb = j[f"{quantity}_a"].to_numpy(float), j[f"{quantity}_b"].to_numpy(float)
    if sa is None:
        sa = j["sigma_a"].to_numpy(float) if quantity == "speed" else yaw_sigma(a, len(j))
    if sb is None:
        sb = j["sigma_b"].to_numpy(float) if quantity == "speed" else yaw_sigma(b, len(j))
    v = np.nanmean(np.c_[j["speed_a"].to_numpy(float), j["speed_b"].to_numpy(float)], axis=1) if len(j) else np.zeros(0)
    r = qa - qb
    s = np.hypot(sa, sb)
    f = pd.DataFrame({"t": j.index.to_numpy(float), "pair": f"{a}-{b}", "quantity": quantity, "a": qa, "b": qb, "r": r, "s": s,
                      "z": r / s, "v": v})
    return f[np.isfinite(f["r"]) & np.isfinite(f["s"])].reset_index(drop=True)


# ------------------------------------------------------------------------------------------------------------------
# latency
# ------------------------------------------------------------------------------------------------------------------
def _uniform(t, v, dt, t0, t1, max_gap=0.5):
    g = np.arange(t0, t1, dt)
    x = np.interp(g, t, v)
    k = np.clip(np.searchsorted(t, g), 1, len(t) - 1)
    bad = (t[k] - t[k - 1]) > max_gap
    x[bad] = np.nan
    return g, x


def lag_covariance(ta, a, tb, b, max_lag=2.0, dt=0.02, diff=0.2, max_gap=0.5):
    """Cross-covariance of the first differences (over `diff` s) of a(t) and b(t + lag) for lags in [-max_lag, max_lag]
    (step dt) for ONE group. Returns (lags, num, Sa, Sb, n): sums to be pooled over groups."""
    ta, a, tb, b = map(lambda x: np.asarray(x, float), (ta, a, tb, b))
    oka, okb = np.isfinite(a), np.isfinite(b)
    ta, a, tb, b = ta[oka], a[oka], tb[okb], b[okb]
    K = int(round(max_lag / dt))
    lags = np.arange(-K, K + 1) * dt
    if len(ta) < 3 or len(tb) < 3:
        return lags, np.zeros(len(lags)), 0.0, 0.0, 0
    t0, t1 = max(ta[0], tb[0]), min(ta[-1], tb[-1])
    if t1 - t0 < 4 * max_lag:
        return lags, np.zeros(len(lags)), 0.0, 0.0, 0
    _, xa = _uniform(ta, a, dt, t0, t1, max_gap)
    _, xb = _uniform(tb, b, dt, t0, t1, max_gap)
    m = int(round(diff / dt))
    da = xa[m:] - xa[:-m]
    db = xb[m:] - xb[:-m]
    da = np.where(np.isfinite(da), da - np.nanmean(da), 0.0)
    db = np.where(np.isfinite(db), db - np.nanmean(db), 0.0)
    n = len(da)
    num = np.zeros(len(lags))
    for i, k in enumerate(range(-K, K + 1)):
        if k >= 0:
            num[i] = da[: n - k] @ db[k:]
        else:
            num[i] = da[-k:] @ db[: n + k]
    return lags, num, float(da @ da), float(db @ db), n


def _peak(lags, c):
    i = int(np.argmax(c))
    if 0 < i < len(c) - 1:
        y0, y1, y2 = c[i - 1], c[i], c[i + 1]
        den = y0 - 2 * y1 + y2
        off = 0.5 * (y0 - y2) / den if den != 0 else 0.0
        return float(lags[i] + off * (lags[1] - lags[0]))
    return float(lags[i])


def estimate_lag(parts, n_boot=500, seed=42):
    """Pooled latency over groups. parts: list of lag_covariance() outputs (one per group).
    Returns dict(lag, ci95, corr_peak, groups, boot) ; lag > 0: b lags a."""
    parts = [p for p in parts if p[4] > 0]
    if not parts:
        return {"lag": None, "ci95": None, "corr_peak": None, "groups": 0}
    lags = parts[0][0]
    N = np.array([p[1] for p in parts])
    Sa = np.array([p[2] for p in parts])
    Sb = np.array([p[3] for p in parts])
    c = N.sum(0) / np.sqrt(Sa.sum() * Sb.sum())
    lag = _peak(lags, c)
    rng = np.random.default_rng(seed)
    boot = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(parts), len(parts))
        boot.append(_peak(lags, N[idx].sum(0) / np.sqrt(Sa[idx].sum() * Sb[idx].sum() + 1e-300)))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"lag": lag, "ci95": [float(lo), float(hi)], "corr_peak": float(c.max()), "corr_at_0": float(c[len(c) // 2]),
            "groups": len(parts)}


# ------------------------------------------------------------------------------------------------------------------
# sigma honesty and recalibration
# ------------------------------------------------------------------------------------------------------------------
HONEST = {"mean_abs_max": 0.25, "std_min": 0.8, "std_max": 1.25, "p99_abs_max": 4.0}


def honesty(z):
    z = np.asarray(z, float)
    z = z[np.isfinite(z)]
    if not len(z):
        return {"n": 0, "honest": None}
    m, s, p = float(z.mean()), float(z.std()), float(np.percentile(np.abs(z), 99))
    return {"n": int(len(z)), "mean": m, "std": s, "p99_abs": p, "p01": float(np.percentile(z, 1)), "p99": float(np.percentile(z, 99)),
            "honest": bool(abs(m) <= HONEST["mean_abs_max"] and HONEST["std_min"] <= s <= HONEST["std_max"] and p <= HONEST["p99_abs_max"])}


class SigmaModel:
    """Per-pair recalibrated residual model, fitted on TRAIN residuals only: r ~ bias(v) + N(0, a^2 + (b v)^2), v = mean
    speed of the pair. bias "const" (pre-registered): bias = median(r); bias "linear" (revised design R1, S1): bias = c0 + c1 v
    by least squares (a relative scale error, e.g. tyre radius, gives a bias proportional to speed). a^2, b^2 = non-negative
    least squares of the mean squared de-biased residual in speed-quantile bins on [1, v^2]."""

    def __init__(self, bins=10, bias="const"):
        self.bins, self.mode, self.c0, self.c1, self.a2, self.b2 = bins, bias, 0.0, 0.0, 1.0, 0.0

    @property
    def bias(self):
        return self.c0

    def bias_at(self, v):
        return self.c0 + self.c1 * np.asarray(v, float)

    def fit(self, r, v):
        r, v = np.asarray(r, float), np.abs(np.asarray(v, float))
        ok = np.isfinite(r) & np.isfinite(v)
        r, v = r[ok], v[ok]
        if self.mode == "linear":
            self.c1, self.c0 = (float(x) for x in np.polyfit(v, r, 1))
        else:
            self.c0, self.c1 = float(np.median(r)), 0.0
        rc2 = (r - self.bias_at(v)) ** 2
        q = np.unique(np.quantile(v, np.linspace(0, 1, self.bins + 1)))
        if len(q) < 3:
            self.a2, self.b2 = float(rc2.mean()), 0.0
            return self
        k = np.clip(np.searchsorted(q, v, side="right") - 1, 0, len(q) - 2)
        X, y, w = [], [], []
        for i in range(len(q) - 1):
            m = k == i
            if m.sum() < 5:
                continue
            X.append([1.0, float(np.mean(v[m] ** 2))])
            y.append(float(rc2[m].mean()))
            w.append(float(m.sum()))
        from scipy.optimize import nnls
        X, y, w = np.array(X), np.array(y), np.sqrt(np.array(w))
        sol, _ = nnls(X * w[:, None], y * w)
        self.a2, self.b2 = float(sol[0]), float(sol[1])
        if self.a2 + self.b2 == 0:
            self.a2 = float(rc2.mean())
        return self

    def sigma(self, v):
        return np.sqrt(self.a2 + self.b2 * np.asarray(v, float) ** 2)

    def z(self, r, v):
        v = np.abs(np.asarray(v, float))
        return (np.asarray(r, float) - self.bias_at(v)) / np.maximum(self.sigma(v), 1e-9)

    def to_dict(self):
        return {"bias_mode": self.mode, "bias": self.c0, "bias_per_mps": self.c1, "a": float(np.sqrt(self.a2)), "b": float(np.sqrt(self.b2)),
                "bins": self.bins}

    @classmethod
    def from_dict(cls, d):
        m = cls(d.get("bins", 10), d.get("bias_mode", "const"))
        m.c0, m.c1, m.a2, m.b2 = d["bias"], d.get("bias_per_mps", 0.0), d["a"] ** 2, d["b"] ** 2
        return m
