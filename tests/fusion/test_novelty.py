"""Unit tests for fusion/novelty.py (WP6 S4 evidence-novelty layer)."""
import numpy as np

from common.metrics import auc
from fusion import novelty as NV


def _clean(rng, n=3000, m=5):
    base = rng.random((n, 1))                                  # one shared factor: layers co-fire in the clean data
    return np.clip(0.6 * base + 0.4 * rng.random((n, m)), 0, 0.98)


def test_both_kinds_separate_a_new_joint_pattern_and_are_deterministic():
    rng = np.random.default_rng(0)
    X = _clean(rng)
    A = X[:300].copy()
    A[:, 0], A[:, 1] = 0.97, 0.05                              # layer 0 high without its partner: no clean tick looks like it
    for kind in NV.KINDS:
        d = NV.EvidenceNovelty(kind).fit(X)
        sc, sa = d.score(X[1000:1300]), d.score(A)
        assert auc(np.r_[np.zeros(300), np.ones(300)], np.r_[sc, sa]) > 0.9
        assert np.allclose(sa, NV.EvidenceNovelty(kind).fit(X).score(A))


def test_zero_evidence_ticks_have_zero_novelty_and_are_not_fitted():
    rng = np.random.default_rng(1)
    X = np.vstack([_clean(rng, 500), np.zeros((500, 5))])
    for kind in NV.KINDS:
        d = NV.EvidenceNovelty(kind).fit(X)
        assert (d.score(np.zeros((10, 5))) == 0).all()
        assert (d.score(X[:50]) > 0).all()


def test_constant_columns_and_tiny_fit_sets_do_not_crash():
    X = np.zeros((40, 3))
    X[:, 1] = np.linspace(0.1, 0.9, 40)
    for kind in NV.KINDS:
        s = NV.EvidenceNovelty(kind).fit(X).score(X)
        assert s.shape == (40,) and np.isfinite(s).all()
        assert (NV.EvidenceNovelty(kind).fit(np.zeros((3, 3))).score(X) == 0).all()


def test_oof_scores_come_from_detectors_that_did_not_see_the_rows():
    rng = np.random.default_rng(2)
    X = _clean(rng, 1000, 4)
    blocks = np.arange(1000) // 20
    o = NV.fit_oof("mcd", X, blocks, k=5)
    i = NV.EvidenceNovelty("mcd").fit(X).score(X)
    assert o.shape == (1000,) and np.mean(o) >= np.mean(i) * 0.9      # out-of-fold is not smaller on average than in-sample
    assert (o > 0).mean() > 0.9


def test_explain_names_the_deviating_layer():
    rng = np.random.default_rng(3)
    X = _clean(rng, 2000, 4)
    d = NV.EvidenceNovelty("mcd", layer_names=["a", "b", "c", "d"]).fit(X)
    x = X[0].copy()
    x[2] = 0.999
    assert d.explain(x)[0][0] == "c"
