"""Tests for can/l2a_skew.py (WP2 S3): clock-skew filter, causality, calibration on clean data only, dt inversions."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from can import l1 as L
from can import l2a_skew as K


def _stream(n=6000, skew=0.0, seed=0, jitter=2e-5, period=0.01, t0=0.0):
    rng = np.random.default_rng(seed)
    return t0 + np.arange(n) * period * (1 + skew) + rng.normal(0, jitter, n)


def _F(t, ids=None):
    ids = np.full(len(t), 0x100) if ids is None else ids
    return L.make_features(t, ids, np.full(len(t), 8), windows=False)


def _calibrated(variant, seeds=(1, 2, 3), skews=(2e-5, -1e-5, 4e-5)):
    Fs = [_F(_stream(skew=s, seed=sd)) for sd, s in zip(seeds, skews)]
    P = L.ProfileBuilder()
    for F in Fs:
        P.add(F["id"], F["dlc"], F["dt_id"])
    l1p = P.finish()
    b = K.SkewBuilder(l1p)
    ones = np.ones(len(Fs[0]["id"]), bool)
    for F in Fs:
        b.add_periods(F, ones)
    S = b.prof(variant)
    for F in Fs:
        b.add_errors(S, F, ones)
    b.finish(S)
    for F in Fs:
        b.add_stats(S, F, ones)
    return b.finish_scale(S)


def test_clean_low_and_skew_change_detected():
    for v in (0, 2, 4, 8, 12):
        S = _calibrated(v)
        assert S.scored.all()
        clean = K.run_pass(_F(_stream(skew=1e-5, seed=9)), S)[0]
        t = np.r_[_stream(3000, 1e-5, 9), _stream(3000, 1e-5 + 3e-4, 10, t0=30.0)]  # skew jump at frame 3000
        sc = K.run_pass(_F(t), S)[0]
        f = 1.5 if v >= 8 else 3.0               # the local baseline adapts to the new skew within ~50 batches
        assert sc[3500:].max() > f * max(clean.max(), 0.5), (v, clean.max(), sc[3500:].max())
        assert sc[:3000].max() < sc[3500:].max()


def test_causal_prefix():
    S = _calibrated(0)
    t = _stream(skew=1e-5, seed=11)
    full = K.run_pass(_F(t), S)[0]
    pre = K.run_pass(_F(t[:3000]), S)[0]
    assert np.allclose(full[:3000], pre)


def test_negative_dt_never_used():
    S = _calibrated(0)
    t = _stream(skew=1e-5, seed=12)
    t2 = t.copy()
    t2[100:110] = t2[100:110] - 0.004                       # local inversions
    sc = K.run_pass(_F(t2), S)[0]
    assert np.isfinite(sc).all() and (sc >= 0).all()
    F = _F(t2)
    assert np.nanmin(F["dt_id"]) >= 0


def test_unknown_and_event_ids_score_zero():
    S = _calibrated(0)
    t = _stream(skew=1e-5, seed=13)
    ids = np.full(len(t), 0x7FF)
    assert K.run_pass(_F(t, ids), S)[0].max() == 0.0


def test_calibration_uses_masked_frames_only():
    Fs = [_F(_stream(skew=s, seed=sd)) for sd, s in ((1, 2e-5), (2, 1e-5))]
    l1b = L.ProfileBuilder()
    for F in Fs:
        l1b.add(F["id"], F["dlc"], F["dt_id"])
    b = K.SkewBuilder(l1b.finish())
    S = b.prof(0)
    none = np.zeros(len(Fs[0]["id"]), bool)
    for F in Fs:
        b.add_errors(S, F, none)
    S = b.finish(S)
    assert not S.scored.any()


def test_layer_window_score_is_max_of_frames():
    S = _calibrated(0)
    t = _stream(skew=1e-5, seed=14)
    F = L.make_features(t, np.full(len(t), 0x100), np.full(len(t), 8))
    fr = K.SkewLayer(S, "frame").frame_raw(F)
    w = K.SkewLayer(S, "window").raw_scores(F)
    assert np.isclose(w.max(), fr.max()) and len(w) == len(F["wkeys"])
