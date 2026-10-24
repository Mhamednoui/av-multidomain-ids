"""Tests of lidar.combine (WP3 S9): label-free combiners, budget control, split union bound, drive bootstrap."""
import numpy as np
import pandas as pd

from lidar import combine as K


def _ref(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({"raw_A": rng.normal(size=n), "raw_B": rng.exponential(size=n), "raw_C": rng.uniform(size=n),
                         "drive": np.repeat(["d1", "d2", "d3", "d4"], n // 4)})


def test_fa_within_budget_on_reference():
    ref = _ref()
    for m in K.METHODS:
        s = K.Stack(["raw_A", "raw_B", "raw_C"], m, 0.01).fit(ref)
        assert s.alarm(ref).mean() <= 0.01 + 1e-12, m


def test_split_is_union_of_layer_alarms():
    ref = _ref(seed=1)
    cols = ["raw_A", "raw_B", "raw_C"]
    s = K.Stack(cols, "split", 0.01).fit(ref)
    R = s.ranks(ref)
    union = (R >= s.tau[None, :]).any(axis=1)
    assert (union == s.alarm(ref)).all()
    assert union.mean() <= 0.01


def test_split_catches_single_layer_extreme_only_at_its_share():
    ref = _ref(seed=2)
    s = K.Stack(["raw_A", "raw_B"], "split", 0.01).fit(ref)
    test = pd.DataFrame({"raw_A": [10.0, 0.0], "raw_B": [0.0, 0.0]})
    assert list(s.alarm(test)) == [True, False]
    assert s.dominant(test)[0] == 0


def test_noisy_or_ranking_equals_product_form():
    ref = _ref(seed=3)
    s = K.Stack(["raw_A", "raw_C"], "noisy_or", 0.01).fit(ref)
    x = _ref(500, seed=4)
    R = np.clip(s.ranks(x), 0, K.CLIP)
    prod = 1 - np.prod(1 - R, axis=1)
    assert np.array_equal(np.argsort(s.stat(x), kind="stable"), np.argsort(prod, kind="stable")) or abs(np.corrcoef(s.stat(x), prod)[0, 1]) > 0.9
    a, b = s.stat(x), prod
    order = np.argsort(a)
    assert (np.diff(b[order]) >= -1e-12).all()


def test_max_dilutes_a_strong_layer_compared_with_its_own_threshold():
    ref = _ref(seed=5)
    cols = ["raw_A", "raw_B", "raw_C"]
    alone = K.Stack(["raw_A"], "max", 0.01).fit(ref)
    stack = K.Stack(cols, "max", 0.01).fit(ref)
    x = pd.DataFrame({"raw_A": np.linspace(2.0, 3.0, 200), "raw_B": 0.0, "raw_C": 0.0})
    assert alone.alarm(x).mean() >= stack.alarm(x).mean()


def test_lodo_fa_and_summary():
    ref = _ref(seed=6)
    fa = K.lodo_fa(ref, ["raw_A", "raw_B"], "max", 0.01)
    assert set(fa) == {"d1", "d2", "d3", "d4"}
    mean, worst, who = K.lodo_summary(fa, {d: 1000 for d in fa})
    assert 0 <= mean <= worst <= 0.1 and who in fa


def test_drive_bootstrap_interval_contains_point():
    rng = np.random.default_rng(0)
    dr = np.repeat(list("abcdefg"), 50)
    a = (rng.uniform(size=len(dr)) < 0.3).astype(float)
    p, lo, hi = K.drive_bootstrap(a, dr, n=300)
    assert lo <= p <= hi
