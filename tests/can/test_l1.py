"""Tests for can/l1.py (WP2 S2): profile, five rules, causality, calibration on clean data only."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from can import l1 as L


def _traffic(n=3000, seed=0, inject_at=None):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * 0.01 + rng.normal(0, 1e-4, n)         # ID 0x100 every 10 ms
    ids = np.full(n, 0x100)
    dlc = np.full(n, 8)
    lab = np.zeros(n, np.int8)
    if inject_at is not None:                                  # extra frames of the same ID between regular ones
        extra = t[inject_at:inject_at + 100] + 0.003
        t = np.r_[t, extra]
        ids = np.r_[ids, np.full(100, 0x100)]
        dlc = np.r_[dlc, np.full(100, 8)]
        lab = np.r_[lab, np.ones(100, np.int8)]
        o = np.argsort(t, kind="stable")
        t, ids, dlc, lab = t[o], ids[o], dlc[o], lab[o]
    return t, ids, dlc, lab


def _profile(t, ids, dlc):
    F = L.make_features(t, ids, dlc, windows=False)
    return L.ProfileBuilder().add(F["id"], F["dlc"], F["dt_id"]).finish()


def test_profile_periodic_and_allowlist():
    P = _profile(*_traffic()[:3])
    assert list(P.ids) == [0x100] and bool(P.periodic[0])
    assert abs(P.p[0] - 0.01) < 1e-3


def test_rules_flag_unknown_id_dlc_and_injection():
    t, ids, dlc, _ = _traffic()
    P = _profile(t, ids, dlc)
    t2, i2, d2, lab = _traffic(seed=1, inject_at=1000)
    i2 = i2.copy(); d2 = d2.copy()
    i2[5], d2[7] = 0x7FF, 3
    F = L.make_features(t2, i2, d2, lab, windows=False)
    assert L.IdAllowList(P).frame_raw(F)[5] >= 1
    assert L.DlcPerId(P).frame_raw(F)[7] >= 1
    r = L.PeriodPerId(P).frame_raw(F)
    assert (r[lab == 1] >= 1).mean() > 0.9 and (r[lab == 0] >= 1).mean() < 0.05


def test_calibration_on_clean_gives_budget_and_noisy_or_bounds():
    t, ids, dlc, _ = _traffic(seed=2)
    P = _profile(t, ids, dlc)
    F = L.make_features(t, ids, dlc, windows=False)
    rules = L.build_rules(P, "frame")
    for r in rules.values():
        r.calibrate_from_raw(r.frame_raw(F), 0.01)
        assert (r.alarms(r.frame_raw(F))).mean() <= 0.01 + 1e-9
    c = L.noisy_or([r.calibrated(r.frame_raw(F)) for r in rules.values()])
    assert (c >= 0).all() and (c <= 1).all()


def test_causal_prefix_scores_unchanged():
    t, ids, dlc, lab = _traffic(inject_at=1000)
    P = _profile(*_traffic()[:3])
    full = L.make_features(t, ids, dlc, lab, windows=False)
    cut = L.make_features(t[:2000], ids[:2000], dlc[:2000], lab[:2000], windows=False)
    for c in L.RULE_CLASSES:
        a, b = c(P).frame_raw(full)[:2000], c(P).frame_raw(cut)
        assert np.allclose(a, b)
