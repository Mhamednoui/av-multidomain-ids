"""Unit tests of the V2X L4 supervised model (v2x/l4.py) on synthetic message tables."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from v2x import l3, l4
from test_l3 import simulate, straight


def tracker(sp=0.5, sv=0.1, sa=1.0):
    return l3.Tracker(l3.KalmanParams(sp, sv, sa))


def test_features_exclude_raw_position_speed_id_and_time():
    assert not set(l4.FEATURES) & l4.FORBIDDEN
    fs = l4.feature_sets()
    assert set(fs["A1_no_time_track"]) == set(l4.FEATURES) - set(l4.T_FEATURES)
    assert not set(fs["A2_residuals_only"]) & set(l4.RATE_BIRTH_FEATURES + l4.T_FEATURES)
    assert not set(fs["no_memory"]) & set(l4.MEMORY_FEATURES)
    assert "kf_cusum_lo" not in " ".join(l4.FEATURES) and "cusum_lo" not in l4.FEATURES


def test_feature_table_columns_and_finite():
    d = simulate(n_tracks=6, n=30, seed=1)
    f = l4.feature_table(d, tracker())
    assert list(f.columns[:len(l4.FEATURES)]) == l4.FEATURES or set(l4.FEATURES) <= set(f.columns)
    assert np.isfinite(f.to_numpy()).all() and len(f) == len(d)


def test_window_aggregates():
    v = np.array([1.0, 5.0, 2.0, 0.0, 9.0, 3.0])
    pos = np.array([0, 1, 2, 0, 1, 2])                  # two tracks of three
    assert np.array_equal(l4._window_agg(v, pos, 2, "max"), [1, 5, 5, 0, 9, 9])
    assert np.allclose(l4._window_agg(v, pos, 2, "mean"), [1, 3, 3.5, 0, 4.5, 6])
    assert np.array_equal(l4._window_agg((v > 1.5).astype(float), pos, 3, "count"), [0, 1, 2, 0, 1, 2])


def test_features_are_causal_and_row_order_free():
    d = simulate(n_tracks=8, n=40, seed=2)
    f = l4.feature_table(d, tracker())
    keep = (d["t"] < 25).to_numpy()
    short = d[keep].reset_index(drop=True)
    g = l4.feature_table(short, tracker())
    cols = l4.FEATURES
    assert np.allclose(f.loc[keep, cols].to_numpy(), g[cols].to_numpy(), atol=1e-4)
    perm = np.random.RandomState(0).permutation(len(d))
    h = l4.feature_table(d.iloc[perm].reset_index(drop=True), tracker())
    assert np.allclose(f[cols].to_numpy()[perm], h[cols].to_numpy(), atol=1e-4)


def test_track_birth_density_is_carried_along_the_track():
    rows = []
    for i in range(5):
        for k in range(4):
            rows.append((f"b{i}", 100.0 + i + k, 500.0 + 10 * i + 10 * k, 0.0))
    d = pd.DataFrame(rows, columns=["track", "t", "x", "y"])
    d["sender"], d["speed"], d["heading"], d["vx"], d["vy"] = d["track"], 10.0, 0.0, 10.0, 0.0
    f = l4.feature_table(d, tracker())
    last = d["track"].eq("b4").to_numpy()
    assert (f.loc[last, "track_birth_density"] == 4).all()
    assert f.loc[last, "is_first"].sum() == 1


def test_rate_feature_is_beacon_rate_and_window_sees_a_burst():
    a = straight("n", n=10, dt=1.0)
    b = straight("dos", n=10, dt=0.25)
    d = pd.concat([a, b], ignore_index=True)
    f = l4.feature_table(d, tracker())
    assert f.loc[d["track"] == "n", "w_rate_max"].max() < 0.11
    assert f.loc[d["track"] == "dos", "w_rate_max"].max() > 0.35


def test_gbmodel_learns_generalises_and_shuffled_labels_collapse():
    rng = np.random.RandomState(0)
    n = 6000
    X = pd.DataFrame({"a": rng.randn(n), "b": rng.randn(n), "c": rng.randn(n)})
    y = (X["a"] + 0.3 * X["b"] > 0.5).astype(int)
    Xt = pd.DataFrame({"a": rng.randn(n), "b": rng.randn(n), "c": rng.randn(n)})
    yt = (Xt["a"] + 0.3 * Xt["b"] > 0.5).astype(int)
    m = l4.GBModel(["a", "b", "c"], {"max_depth": 3}, n_estimators=60).fit(X, y)
    from common.metrics import auc
    assert auc(yt, m.predict(Xt)) > 0.95
    imp = m.importance()
    assert list(imp)[0] == "a" and abs(sum(imp.values()) - 1) < 1e-6
    ms = l4.GBModel(["a", "b", "c"], {"max_depth": 3}, n_estimators=60).fit(X, rng.permutation(y))
    assert 0.4 < auc(yt, ms.predict(Xt)) < 0.6
    sub = l4.GBModel(["b", "c"], {"max_depth": 3}, n_estimators=60).fit(X, y)
    assert sub.features == ["b", "c"] and auc(yt, sub.predict(Xt)) < auc(yt, m.predict(Xt))


def _jump_tracks(offset, seed, prefix):
    d = simulate(n_tracks=40, n=50, seed=seed, prefix=prefix)
    att = d["track"].str[len(prefix):].astype(int) % 2 == 1
    late = (d["t"] >= 25).to_numpy() & att.to_numpy()
    d.loc[late, "x"] += offset
    d["label"] = late.astype(int)
    return d


def test_l4_layer_detects_an_unseen_jump_size_from_plausibility_features():
    tr = tracker()
    train = _jump_tracks(200.0, 11, "a")
    test = _jump_tracks(900.0, 12, "b")                  # a jump size never seen in training
    ftr, fte = l4.feature_table(train, tr), l4.feature_table(test, tr)
    m = l4.GBModel(l4.FEATURES, {"max_depth": 4}, n_estimators=40).fit(ftr, train["label"])
    layer = l4.L4(m, tr)
    layer.calibrate(test[test["label"] == 0], budget=0.01)
    ev = layer.score(test)
    al = np.array([e.alarm for e in ev])
    y = test["label"].to_numpy().astype(bool)
    assert al[y].mean() > 0.8 and al[~y].mean() <= 0.02
