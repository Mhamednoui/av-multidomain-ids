"""Tests for network/l4.py (WP4 S6): class weights, matrix hygiene (inf -> NaN, no port / address column used), learning of a toy signal,
Layer contract (calibration budget), shuffled-label null (no signal), determinism, importance."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.config import BUDGET_DOMAIN
from common.metrics import auc
from network import l4
from network.flows import FEATURES

P = {"max_depth": 3, "learning_rate": 0.2, "subsample": 1.0, "colsample_bytree": 1.0, "min_child_weight": 1, "reg_lambda": 1.0}


def _flows(n, rng, shift=0.0):
    df = pd.DataFrame({f: rng.lognormal(3.0, 1.0, n) for f in FEATURES})
    df["Flow Duration"] = df["Flow Duration"] * np.exp(shift)
    df["dst_port"] = 80
    df["protocol"] = 6
    return df


def _toy(n=1500, seed=0):
    rng = np.random.RandomState(seed)
    b, a = _flows(n, rng), _flows(n // 5, rng, shift=4.0)
    df = pd.concat([b, a], ignore_index=True)
    y = np.r_[np.zeros(n), np.ones(n // 5)].astype(int)
    return df, y


def test_class_weights_mean_one_and_rare_up():
    g = np.array(["a"] * 90 + ["b"] * 10)
    w = l4.class_weights(g, 0.5)
    assert abs(w.mean() - 1.0) < 1e-9
    assert w[g == "b"][0] > w[g == "a"][0]
    assert np.allclose(l4.class_weights(g, 0.0), 1.0)


def test_matrix_inf_to_nan_and_uses_only_clean_columns():
    df, _ = _toy(50)
    df.loc[0, "Flow Duration"] = np.inf
    L = l4.XGBNet(params=P, n_trees=5)
    X = l4.matrix(df, L.cols)
    assert X.shape == (len(df), 60)
    assert np.isnan(X[0, L.cols.index("Flow Duration")]) and not np.isinf(X).any()
    for bad in ("dst_port", "protocol", "Init Fwd Win Byts", "RST Flag Cnt"):
        assert bad not in L.cols


def test_learns_toy_signal_and_contract():
    df, y = _toy()
    L = l4.XGBNet(params=P, n_trees=30).fit(df, y, np.where(y == 1, "A", "BENIGN"))
    te, yt = _toy(seed=1)
    raw = L.raw_scores(te)
    assert auc(yt, raw) > 0.95
    L.calibrate(te[yt == 0], BUDGET_DOMAIN)
    ev = L.score(te)
    assert len(ev) == len(te) and ev[0].layer == "L4"
    fa = np.mean(L.calibrator.transform(raw[yt == 0]) >= L.threshold)
    assert fa <= BUDGET_DOMAIN + 1e-9
    assert L.kind == "supervised" and L.needs_attack_data


def test_shuffled_labels_give_no_signal_and_port_irrelevant():
    df, y = _toy()
    rng = np.random.RandomState(3)
    L = l4.XGBNet(params=P, n_trees=30).fit(df, rng.permutation(y), np.where(y == 1, "A", "BENIGN"))
    te, yt = _toy(seed=1)
    real = l4.XGBNet(params=P, n_trees=30).fit(df, y, np.where(y == 1, "A", "BENIGN"))
    # a shuffled-label model keeps a weak residual (attack rows sit in the extreme feature range: WP5 out-of-range leaves) but is far below the real model
    assert auc(yt, L.raw_scores(te)) < auc(yt, real.raw_scores(te)) - 0.25
    te2 = te.copy()
    te2["dst_port"] = 9999
    assert np.array_equal(L.raw_scores(te), L.raw_scores(te2))


def test_deterministic_and_early_stopping_and_importance():
    df, y = _toy()
    g = np.where(y == 1, "A", "BENIGN")
    va, yv = _toy(seed=2)
    a = l4.XGBNet(params=P, max_trees=60).fit(df, y, g, val=va, y_val=yv)
    b = l4.XGBNet(params=P, max_trees=60).fit(df, y, g, val=va, y_val=yv)
    assert a.best_n_trees == b.best_n_trees and 1 <= a.best_n_trees <= 60
    assert np.array_equal(a.raw_scores(va), b.raw_scores(va))
    imp = a.importance()
    assert abs(sum(imp.values()) - 1.0) < 1e-6
    assert next(iter(imp)) == "Flow Duration"
