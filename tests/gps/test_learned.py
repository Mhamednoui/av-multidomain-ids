"""Tests for gps/learned.py (WP1 S7): C2 features, residual normal models, XGBoost search, score-column layer."""
import numpy as np
import pandas as pd

from gps import learned
from gps import stream as S


def _run_df(n=40, run="r0", speed=10.0):
    t = np.arange(n, dtype=float)
    heading = np.full(n, 90.0)                       # east
    x = speed * t + np.random.default_rng(1).normal(0, 0.3, n)
    y = np.zeros(n)
    lat = y / S.M_PER_DEG
    lon = x / (S.M_PER_DEG * np.cos(np.radians(0.0)))
    return pd.DataFrame({"run": run, "t": t, "x": x, "y": y, "lat": lat, "lon": lon, "odo_speed": speed, "heading": heading, "course": 90.0})


def test_c2_features_match_hand_computation():
    df = _run_df()
    f = learned.c2_features(df)
    assert list(f.columns) == learned.C2_ALL
    step = np.hypot(np.diff(df["x"]), np.diff(df["y"]))
    assert np.allclose(f["pos_step_m"].iloc[1:], step, atol=1e-6)
    assert np.isnan(f["pos_step_m"].iloc[0])
    assert np.allclose(f["speed_gap"].iloc[1:], np.abs(step - 10.0), atol=1e-6)
    assert (f["heading_gap"] == 0).all()
    # dead reckoning: heading east at 10 m/s vs the reported track: residual of window 10 = |dx_rep - 10 * 10| (first fixes: shorter window)
    k = 25
    assert abs(f["dr_resid_10"].iloc[k] - abs((df["x"].iloc[k] - df["x"].iloc[k - 10]) - 100.0)) < 1e-6
    assert abs(f["dr_resid_5"].iloc[k] - abs((df["x"].iloc[k] - df["x"].iloc[k - 5]) - 50.0)) < 1e-6


def test_c2_features_are_causal_and_per_run():
    a, b = _run_df(30, "a"), _run_df(30, "b", speed=3.0)
    both = pd.concat([a, b], ignore_index=True)
    f = learned.c2_features(both)
    fa = learned.c2_features(a)
    assert np.allclose(f.iloc[:30].fillna(-1).to_numpy(), fa.fillna(-1).to_numpy())
    cut = both.iloc[:20]                                         # truncating the future must not change the past
    assert np.allclose(learned.c2_features(cut).fillna(-1).to_numpy(), f.iloc[:20].fillna(-1).to_numpy())


def _gauss(n, seed=0, p=7):
    r = np.random.default_rng(seed)
    X = np.abs(r.normal(0, 1, (n, p)))
    return pd.DataFrame(X, columns=learned.RES_A)


def test_residual_models_rank_outliers_higher():
    train, test = _gauss(3000, 0), _gauss(500, 1)
    out = test.copy()
    out[learned.RES_A] = out[learned.RES_A] + 6.0               # every residual large: a spoof-like vector
    for kind in ("lw", "mcd", "if256", "if1024"):
        m = learned.ResidualNormalModel(kind, learned.RES_A).fit(train)
        s_n, s_o = m.score(test), m.score(out)
        assert np.median(s_o) > np.percentile(s_n, 99), kind


def test_residual_model_is_deterministic():
    train = _gauss(2000, 3)
    a = learned.ResidualNormalModel("mcd", learned.RES_A).fit(train).score(train.iloc[:50])
    b = learned.ResidualNormalModel("mcd", learned.RES_A).fit(train).score(train.iloc[:50])
    assert np.array_equal(a, b)


def test_xgb_search_learns_separable_toy_and_collapses_on_shuffled_labels():
    r = np.random.default_rng(0)
    X = r.normal(0, 1, (1500, 4))
    y = (X[:, 0] + 0.5 * X[:, 1] > 0.3).astype(int)
    tr, va = slice(0, 1000), slice(1000, 1500)
    m, info = learned.xgb_search(X[tr].astype(np.float32), y[tr], X[va].astype(np.float32), y[va], n_iter=2)
    p = m.predict_proba(X[va].astype(np.float32))[:, 1]
    from common.metrics import auc
    assert auc(y[va], p) > 0.95
    ys = np.random.default_rng(1).permutation(y)
    m2, _ = learned.xgb_search(X[tr].astype(np.float32), ys[tr], X[va].astype(np.float32), ys[va], n_iter=2)
    assert auc(y[va], m2.predict_proba(X[va].astype(np.float32))[:, 1]) < 0.6


def test_score_column_layer_calibrates_and_alarms():
    r = np.random.default_rng(0)
    df = pd.DataFrame({"s": r.normal(0, 1, 2000)})
    lay = learned.ScoreColumnLayer("s", "gps.test", "L3", "normal_model", why="x").calibrate(df, budget=0.01)
    ev = lay.score(df)
    fa = np.mean([e.alarm for e in ev])
    assert fa <= 0.0125
    hi = lay.score(pd.DataFrame({"s": [10.0]}))
    assert hi[0].alarm and hi[0].layer == "L3" and hi[0].domain == "gps"
