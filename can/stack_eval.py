"""WP2 S7: small evaluation helpers for the CAN stack (threshold-LOCO, ECDF layer scores, noisy-or statistic, intervals).

threshold_loco: for each held-out unit, the alarm threshold comes from the held-out scores of the OTHER units of the pool (tie-safe budget quantile),
  i.e. a simulation of "a new session arrives": the false-alarm rate of a pooled leave-one-capture-out calibration is otherwise optimistic.
Intervals: Clopper-Pearson (exact binomial) for counts of captures, cluster bootstrap over captures for pooled rates, moving-block bootstrap
  (blocks of consecutive windows) for the rate of ONE capture.
Inputs: dict unit -> array of scores. Outputs: floats / dicts. References: Efron & Tibshirani 1993 (bootstrap); Clopper & Pearson 1934.
"""
import numpy as np
from scipy.stats import beta

from common.metrics import budget_threshold


def threshold_loco(scores: dict, pool: list, budget: float = 0.01) -> dict:
    """unit -> (threshold from the other `pool` units, false-alarm rate of the unit at it). `pool` lists the units whose scores may set thresholds;
    a unit outside the pool (e.g. a road block when the pool is dyno-only) uses all pool units."""
    out = {}
    for u, s in scores.items():
        others = [v for k, v in scores.items() if k in pool and k != u]
        thr = budget_threshold(np.concatenate(others), budget)
        out[u] = (thr, float((s >= thr).mean()) if len(s) else float("nan"))
    return out


def clopper_pearson(k: int, n: int, alpha: float = 0.05):
    lo = 0.0 if k == 0 else float(beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


def cluster_bootstrap_rate(alarms: list, n_boot: int = 2000, seed: int = 42):
    """alarms: list of boolean arrays, one per capture (cluster). Pooled rate and its 95% percentile interval over resampled captures."""
    rng = np.random.default_rng(seed)
    k = np.array([a.sum() for a in alarms], float)
    n = np.array([len(a) for a in alarms], float)
    pooled = k.sum() / max(n.sum(), 1)
    if len(alarms) < 2:
        return float(pooled), (float("nan"), float("nan"))
    idx = rng.integers(0, len(alarms), size=(n_boot, len(alarms)))
    r = k[idx].sum(1) / np.maximum(n[idx].sum(1), 1)
    return float(pooled), (float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975)))


def block_bootstrap_rate(alarm: np.ndarray, block: int = 10, n_boot: int = 2000, seed: int = 42):
    """Rate of one capture with a moving-block bootstrap (consecutive windows are correlated)."""
    a = np.asarray(alarm, float)
    n = len(a)
    if n == 0:
        return float("nan"), (float("nan"), float("nan"))
    if a.sum() == 0 and n >= block:
        # no alarm: rule-of-three style exact bound from the effective number of independent blocks
        nb = max(n // block, 1)
        return 0.0, (0.0, float(1 - 0.025 ** (1.0 / nb)))
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / block))
    starts = rng.integers(0, max(n - block, 0) + 1, size=(n_boot, nb))
    cs = np.r_[0.0, np.cumsum(a)]
    k = (cs[np.minimum(starts + block, n)] - cs[starts]).sum(1)
    r = k / (nb * block)
    return float(a.mean()), (float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975)))


def noisy_or_log(cal: np.ndarray) -> np.ndarray:
    """-sum log(1 - s_i) over the columns (ECDF-calibrated layer scores)."""
    return -np.log1p(-np.clip(np.asarray(cal, float), 0.0, 1.0 - 1e-16)).sum(axis=1)
