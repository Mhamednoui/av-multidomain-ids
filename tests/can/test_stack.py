"""Tests of the S7 CAN stack pieces: profile merge, L3c series equivalence, threshold-LOCO, intervals, units, motion estimate."""
import numpy as np

from can import l1 as L
from can import l3_predictors as P
from can import signals as S
from can.domain import WHEEL_UNIT_MPS, WHEELS, CanDomain
from can.stack_core import UnitData, lead_clean, l3c_series, merge_builders, slice_unit
from can.stack_eval import (block_bootstrap_rate, clopper_pearson, cluster_bootstrap_rate, noisy_or_log, threshold_loco)
from common.combiner import noisy_or_stat


def _frames(seed, n=4000):
    rng = np.random.default_rng(seed)
    ids = rng.choice([0x100, 0x200, 0x300], size=n)
    t = np.cumsum(rng.uniform(0.001, 0.003, n))
    dlc = np.full(n, 8)
    return t, ids, dlc


def test_merge_builders_equals_joint_builder():
    t1, i1, d1 = _frames(1)
    t2, i2, d2 = _frames(2)
    b = []
    for t, i, d in ((t1, i1, d1), (t2, i2, d2)):
        F = L.make_features(t, i, d, windows=False)
        b.append(L.ProfileBuilder().add(F["id"], F["dlc"], F["dt_id"]))
    m = merge_builders(b).finish()
    assert list(m.ids) == [0x100, 0x200, 0x300]
    assert m.n.sum() == len(t1) + len(t2)
    assert m.periodic.dtype == bool and (m.p > 0).all()
    # merging in another order gives the same profile
    m2 = merge_builders(b[::-1]).finish()
    assert np.allclose(m.p, m2.p) and (m.dlc_mask == m2.dlc_mask).all()


def test_l3c_series_equals_grid_scores():
    rng = np.random.default_rng(0)
    p = 6
    M = P.L3cModel()
    M.mu, M.sd, M.own = np.zeros(p), np.ones(p), True
    M.W = rng.normal(0, 0.1, (p * (1 + len(P.LAGS)), p))
    M.b0, M.sigma = rng.normal(0, 0.1, p), np.full(p, 0.05)
    M.r2 = np.array([0.99, 0.95, 0.5, 0.92, 0.1, 0.0])
    G = np.cumsum(rng.normal(0, 1, (400, p)), axis=0).astype(np.float32)
    ser = l3c_series(M, G, (0.0, 0.9))
    for rm in (0.0, 0.9):
        assert np.allclose(ser[rm], P.grid_scores(M, G, rm, "cusum"), rtol=1e-5, atol=1e-4)
    assert (ser[0.9] <= ser[0.0] + 1e-6).all()


def test_threshold_loco_uses_only_other_units():
    sc = {"a": np.zeros(200), "b": np.zeros(200), "c": np.r_[np.zeros(190), np.full(10, 5.0)]}
    out = threshold_loco(sc, ["a", "b", "c"], 0.01)
    # unit c: threshold from a and b (all zeros) -> tie-safe threshold just above 0, so c's ten 5.0 scores all alarm (5%)
    assert abs(out["c"][1] - 0.05) < 1e-9
    # unit a: pool b + c has 10/400 = 2.5% of 5.0 values > 1%: threshold above 5.0 -> a never alarms
    assert out["a"][1] == 0.0
    # a unit outside the pool uses all pool units
    out2 = threshold_loco(sc, ["a", "b"], 0.01)
    assert out2["c"][0] == out["c"][0]


def test_intervals():
    lo, hi = clopper_pearson(5, 5)
    assert abs(lo - 0.025 ** 0.2) < 1e-9 and hi == 1.0
    lo, hi = clopper_pearson(0, 5)
    assert lo == 0.0 and abs(hi - (1 - 0.025 ** 0.2)) < 1e-9
    rng = np.random.default_rng(3)
    caps = [rng.random(300) < 0.02 for _ in range(8)]
    rate, (a, b) = cluster_bootstrap_rate(caps, n_boot=500)
    assert a <= rate <= b
    r1, (a1, b1) = block_bootstrap_rate(caps[0], block=10, n_boot=500)
    assert a1 <= r1 <= b1 + 1e-12
    z, (az, bz) = block_bootstrap_rate(np.zeros(100, bool))
    assert z == 0.0 and az == 0.0 and bz > 0.0


def test_noisy_or_log_matches_combiner():
    X = np.random.default_rng(1).random((50, 4)) * 0.99
    assert np.allclose(noisy_or_log(X), noisy_or_stat(X))


def test_lead_clean_and_slice():
    n = 100
    t = np.linspace(0, 10, n)
    lab = np.zeros(n, np.int8)
    lab[60:] = 1
    U = UnitData("x", t, np.full(n, 5), np.full(n, 8), np.zeros((n, 8), np.uint8), lab)
    c = lead_clean(U)
    assert c[:50].all() and not c[51:].any()          # frames within 1 s of the first injected frame are not clean
    V = slice_unit(U, 20, 70, "y")
    assert V.t[0] == 0.0 and len(V) == 50 and V.label[-1] == 1


def test_motion_estimate_from_wheel_speeds():
    n = 400
    rng = np.random.default_rng(5)
    t = np.arange(n) * 0.01
    ids = np.full(n, 0x6E0)
    B = rng.integers(0, 256, (n, 8)).astype(np.uint8)
    dom = CanDomain.__new__(CanDomain)
    est = dom.motion_estimates(t, ids, np.full(n, 8), B)
    assert est and all(e.source == "can" and e.speed >= 0 and e.sigma >= 0.3 for e in est)
    dec = S.decode_all(ids, B, {0x6E0: S.parse_dbc()[0x6E0]})
    rows, V = dec[0x6E0]
    # the estimate at second 2 is the mean of the four wheel signals of the last frame at t <= 2.0
    k = np.searchsorted(t, 2.0, side="right") - 1
    want = np.mean([V[k, c] for _, c in WHEELS]) * WHEEL_UNIT_MPS
    e2 = [e for e in est if abs(e.t - 2.0) < 1e-9][0]
    assert abs(e2.speed - want) < 1e-9
    assert dom.motion_estimates(t, np.full(n, 0x123), np.full(n, 8), B) == []
