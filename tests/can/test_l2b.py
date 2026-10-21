"""Tests for can/signals.py and can/l2b_signals.py (WP2 S4): decoding, learned envelope, causality, clean-only fit."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from can import l2b_signals as Z
from can import signals as S


def _dbc():
    return {1: [S.Sig("a", 0, 16, True, False, 1, 0), S.Sig("b", 16, 16, True, False, 1, 0)],
            2: [S.Sig("c", 7, 8, False, False, 1, 0)]}


def _cat():
    c = Z.Catalog.__new__(Z.Catalog)
    c.dbc = _dbc()
    c.keys = [(1, 0), (1, 1), (2, 0)]
    c.j = {k: n for n, k in enumerate(c.keys)}
    c.cont = [(1, 0), (1, 1)]
    c.disc = []
    c.cont_ix = {k: n for n, k in enumerate(c.cont)}
    c.disc_ix = {}
    c.ids = [1, 2]
    return c


def _capture(n=4000, seed=0, speed_break_at=None):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * 0.01
    ids = np.where(np.arange(n) % 2 == 0, 1, 2)
    v = 1000 + 400 * np.sin(np.arange(n) / 300.0) + rng.normal(0, 2, n)          # smooth "speed"
    B = np.zeros((n, 8), np.uint8)
    a = np.round(v).astype(np.int64)
    b = 2 * a                                                                    # b = 2 a (linear relation)
    if speed_break_at is not None:
        a = a.copy()
        a[speed_break_at:] = 1700                                                # attacker overwrites a
    B[:, 0], B[:, 1] = a & 255, a >> 8
    B[:, 2], B[:, 3] = b & 255, b >> 8
    B[:, 0][ids == 2] = 0
    B[ids == 2, 0] = np.clip(np.round(v[ids == 2] / 8), 0, 255).astype(np.uint8)
    return t, ids, B


def test_decode_intel_and_motorola():
    B = np.array([[0x34, 0x12, 0, 0, 0, 0, 0, 0]], np.uint8)
    assert S.Sig("x", 0, 16, True, False, 1, 0).decode(B)[0] == 0x1234
    B = np.array([[0xAB, 0xCD, 0, 0, 0, 0, 0, 0]], np.uint8)
    assert S.Sig("m", 7, 8, False, False, 1, 0).decode(B)[0] == 0xAB            # Motorola start bit 7 = MSB of byte 0
    assert S.Sig("m", 7, 16, False, False, 1, 0).decode(B)[0] == 0xABCD
    B = np.array([[0xFF, 0, 0, 0, 0, 0, 0, 0]], np.uint8)
    assert S.Sig("s", 7, 8, False, True, 1, 0).decode(B)[0] == -1


def _fit(cat):
    t, ids, B = _capture()
    dec = S.decode_all(ids, B, cat.dbc)
    st = Z.capture_stats("clean", t, dec, cat)
    M = Z.fit_model([st], [np.zeros((len(st.Gd), 0), np.int8)], cat, [], 0.98, 1)
    return M


def test_clean_scores_zero_and_linear_break_detected():
    cat = _cat()
    M = _fit(cat)
    assert len(M.lin) == 1
    t, ids, B = _capture(seed=1)
    dec = S.decode_all(ids, B, cat.dbc)
    assert Z.score_frames(M, t, dec, len(t))["linear"].max() == 0.0
    t, ids, B = _capture(seed=1, speed_break_at=2000)       # a overwritten, b still follows the real speed
    dec = S.decode_all(ids, B, cat.dbc)
    r = Z.score_frames(M, t, dec, len(t))
    assert r["linear"][2000:].max() > 0.5 and r["linear"][:1900].max() == 0.0


def test_range_violation_and_causality():
    cat = _cat()
    M = _fit(cat)
    t, ids, B = _capture(seed=2, speed_break_at=3000)
    dec = S.decode_all(ids, B, cat.dbc)
    full = Z.score_frames(M, t, dec, len(t))
    m = 3500
    decp = S.decode_all(ids[:m], B[:m], cat.dbc)
    pre = Z.score_frames(M, t[:m], decp, m)
    for k in Z.TYPES:
        assert np.array_equal(full[k][:m], pre[k]), k                       # score of a frame never depends on later frames


def test_fit_uses_only_given_captures():
    cat = _cat()
    M = _fit(cat)
    assert M.hi[cat.j[(1, 0)]] < 1500                                       # envelope from the clean capture only


def test_windows():
    tm = np.array([0.1, 0.5, 1.2, 1.9, 2.5])
    st = Z.window_starts(tm)
    assert st.tolist() == [0, 2, 4]
    assert Z.window_max(np.array([1, 3, 2, 5, 4.0]), st).tolist() == [3, 5, 4]
