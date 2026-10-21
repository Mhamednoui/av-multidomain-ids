"""Tests for can/l3_predictors.py (WP2 S5): Gram ridge equals least squares, causality, clean-only fit, residual alarm, lag-aware state predictor."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from can import l3_predictors as P


def _signals(n=3000, seed=0):
    """Four continuous signals: a = latent drive, b = 2a + noise, c = -a + noise, d = independent."""
    r = np.random.default_rng(seed)
    a = np.cumsum(r.normal(size=n)) * 0.2
    return np.stack([a, 2 * a + r.normal(size=n) * 0.05, -a + r.normal(size=n) * 0.05, r.normal(size=n)], axis=1)


def test_gram_ridge_matches_least_squares():
    G = _signals()
    mu, sd = P.scale_constants([G])
    g = P.Gram(G, mu, sd)
    F = np.array([0, 2, 3])
    b, b0 = P.ridge_fit(g.n, g.s, g.A, F, 1, 1e-9)
    X = P.lag_stack(P.standardise(G, mu, sd))
    A = np.c_[X[:, F], np.ones(len(X))]
    ref = np.linalg.lstsq(A, X[:, 1], rcond=None)[0]
    assert np.allclose(b, ref[:3], atol=1e-4) and abs(b0 - ref[3]) < 1e-4
    assert abs(P.sse(g, F, 1, b, b0) - ((A @ ref - X[:, 1]) ** 2).sum()) < 1e-3


def test_residual_alarms_only_on_inconsistent_signal():
    names = ["a", "b", "c", "d"]
    mu, sd = P.scale_constants([_signals(seed=i) for i in range(3)])
    gr = {f"{i}": P.Gram(_signals(seed=i), mu, sd) for i in range(3)}
    M = P.fit_l3c(gr, list(gr), list(gr), mu, sd, own=False)
    assert M.r2[1] > 0.9 and M.r2[3] < 0.1            # b is predictable from a, c; d is not
    T = _signals(seed=9)
    clean = P.grid_scores(M, T, 0.9, "max")
    T2 = T.copy()
    T2[1000:1100, 1] += 3.0                           # masquerade: b leaves its relation to a, c while staying smooth in time
    att = P.grid_scores(M, T2, 0.9, "max")
    assert att[1000:1100].min() > 3 * np.quantile(clean, 0.999)
    assert np.allclose(att[:1000], clean[:1000])


def test_causality_future_does_not_change_past_scores():
    Gs = [_signals(seed=1), _signals(seed=3)]
    mu, sd = P.scale_constants(Gs)
    gr = {str(i): P.Gram(G, mu, sd) for i, G in enumerate(Gs)}
    M = P.fit_l3c(gr, list(gr), list(gr), mu, sd, own=True)
    T = _signals(seed=2)
    s1 = P.grid_scores(M, T, 0.0, "cusum")
    T2 = T.copy()
    T2[2000:] += 5.0
    s2 = P.grid_scores(M, T2, 0.0, "cusum")
    assert np.allclose(s1[:2000], s2[:2000])


def test_l3d_lag_vs_persistent_contradiction():
    n = 400
    gear = np.full(n, 3.0)
    gear[100:200] = 1.0                               # reverse
    flag = (gear == 1.0).astype(float)
    clean = np.stack([flag, gear, gear, gear], axis=1)
    M = P.fit_l3d([clean])
    assert M.maps[0] == {3.0: 0.0, 1.0: 1.0}
    lag = clean.copy()
    lag[100:102, 0] = 0.0                             # light follows the lever with a 0.1 s lag
    held = clean.copy()
    held[100:200, 0] = 0.0                            # reverse_light_off: flag held at 0 while in R
    s_lag, s_held = P.l3d_scores(M, lag), P.l3d_scores(M, held)
    assert abs(s_lag.max() - 0.1) < 1e-6 and s_held.max() == 1.0
    one_copy = clean.copy()
    one_copy[:, 1] = 1.0                              # a single gear copy glitching does not vote alone
    assert P.l3d_scores(M, one_copy).max() == 0.0


def test_grid_to_frames_and_windows():
    tm = np.array([1.0, 1.02, 1.07, 2.5, 2.6, 3.9])
    gs = np.arange(60, dtype=np.float32)                # grid from t0 = 1.0 step 0.05
    fs = P.frame_scores(gs, tm, 1.0)
    assert list(fs[:3]) == [0.0, 0.0, 1.0]
    st = np.array([0, 3, 5])
    ws, ok = P.window_scores(gs, tm, 1.0, st)
    assert ok.all() and ws[0] == 19 and ws[1] == 39 and ws[2] == 59
    fs0 = P.frame_scores(gs, np.array([0.5, 1.0]), 1.0)
    assert fs0[0] == 0.0
