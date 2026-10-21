"""Tests for gps/stack.py (WP1 S8): matrix combiner == DomainCombiner, fast run-level detection == brute force, combiner round trip."""
import numpy as np
import pandas as pd

from common.combiner import DomainCombiner
from common.evidence import Evidence
from gps import stack as ST


def _data(n=600, k=4, seed=0):
    rng = np.random.default_rng(seed)
    groups = np.repeat(np.arange(8), n // 8).astype(str)
    y = (rng.random(n) < 0.3).astype(int)
    X = np.clip(rng.random((n, k)) * 0.9 + 0.35 * y[:, None] * rng.random((n, k)), 0, 0.999)
    return X, y, groups


def _evidence(X, names):
    return {nm: [Evidence("gps", "L1", nm, float(i), float(X[i, j]), False) for i in range(len(X))] for j, nm in enumerate(names)}


def test_matrix_combiner_equals_domain_combiner():
    X, y, g = _data()
    names = ["a", "b", "c", "d"]
    for method in ("noisy_or", "max", "logistic", "auto"):
        ref = DomainCombiner(method=method).fit(_evidence(X, names), y, g)
        mc = ST.MatrixCombiner(method=method).fit_matrix(names, X, y, g)
        assert ref.method == mc.method
        assert abs(ref.threshold - mc.threshold) < 1e-12
        s_ref = np.array([e.score for e in ref.combine(_evidence(X, names))])
        assert np.allclose(s_ref, mc.score_matrix(X), atol=1e-12)


def test_combiner_dict_round_trip():
    X, y, g = _data(seed=3)
    names = ["a", "b", "c", "d"]
    for method in ("noisy_or", "logistic"):
        mc = ST.MatrixCombiner(method=method).fit_matrix(names, X, y, g)
        d = ST.combiner_to_dict(mc)
        mc2 = ST.combiner_from_dict(__import__("json").loads(__import__("json").dumps(d)))
        assert np.allclose(mc.score_matrix(X), mc2.score_matrix(X), atol=1e-12)
        assert mc2.threshold == mc.threshold


def test_fit_mask_leaves_rows_out_of_the_fit():
    X, y, g = _data(seed=5)
    names = ["a", "b", "c", "d"]
    keep = np.arange(len(y)) % 2 == 0
    a = ST.MatrixCombiner(method="logistic").fit_matrix(names, X, y, g, fit_mask=keep)
    b = ST.MatrixCombiner(method="logistic").fit_matrix(names, X[keep], y[keep], g[keep])
    assert np.allclose(a.model.coef_, b.model.coef_) and a.threshold == b.threshold


def _runs():
    rows = []
    for drive, attack, sev, onset, n in (("d1", "none", np.nan, -1, 8), ("d1", "drift", 0.3, 3, 40), ("d1", "jump", 10.0, 4, 8),
                                         ("d2", "drift", 0.4, 2, 12), ("d2", "none", np.nan, -1, 8), ("d2", "freeze", 0.0, 5, 9)):
        for k in range(n):
            rows.append({"run": f"{drive}/{attack}/{len(rows)}", "drive": drive, "attack": attack, "severity": sev, "onset": onset, "k": k,
                         "label": int(onset >= 0 and k >= onset)})
    df = pd.DataFrame(rows)
    df["run"] = df.groupby(["drive", "attack"], sort=False).ngroup()
    return df


def test_run_index_matches_brute_force():
    df = _runs()
    ri = ST.RunIndex(df)
    rng = np.random.default_rng(2)
    flag = rng.random(len(df)) < 0.08
    det = ri.detected(flag)
    for i, (_, g) in enumerate(df.groupby("run", sort=False)):
        ok = flag[g.index.to_numpy()][g["label"].to_numpy() == 1].any()
        assert det[i] == ok
    slow = ri.slow_detected(flag)
    for i, (_, g) in enumerate(df.groupby("run", sort=False)):
        if g["attack"].iloc[0] == "drift" and g["severity"].iloc[0] < 0.5:
            w = (g["k"] >= g["onset"].iloc[0]) & (g["k"] < g["onset"].iloc[0] + 30)
            assert slow[i] == flag[g.index.to_numpy()][w.to_numpy()].any()
    # J: mean of the 6 attack detections (attacks without a run count 0 only if present; here missing attacks would be nan -> guarded by test data)
    assert ri.clean_fa(flag) == flag[(df["attack"] == "none").to_numpy()].mean()


def test_raw_threshold_is_tie_safe():
    raw = np.array([1.0] * 50 + [0.0] * 50)
    thr = ST.raw_threshold(raw, np.ones(100, bool), 0.01)
    assert (raw >= thr).mean() <= 0.01
