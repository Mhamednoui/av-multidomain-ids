"""Tests of the WP9 B1 CAN benchmark library (tools/WP9_B1_lib.py): window features, labels, threshold tie handling, bootstrap."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import WP9_B1_lib as L
from common.metrics import budget_threshold


def _seg(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    t = np.cumsum(rng.uniform(0.0008, 0.0012, n))
    ids = rng.choice([0x10, 0x20, 0x30], size=n).astype(np.int32)
    B = rng.integers(0, 256, size=(n, 8)).astype(np.int16)
    d = {"t": t, "id": ids, "dlc": np.full(n, 8, np.int8), "B": B}
    cls = np.zeros(n, np.int8)
    cls[(t > 1.2) & (t < 1.5)] = 2
    S = L.build_segment(d, cls)
    return S


def test_window_labels_and_validity():
    S = _seg()
    w = L.segment_windows(S, np.array([16, 32, 48]), np.array([0.003] * 3), [16, 32, 48], 3)
    assert w["W"].shape[0] == len(w["y"]) == int(S["t"][-1] - S["t"][0]) + 1
    assert w["y"][1] == 2 and w["y"][0] == 0
    assert not w["valid"][-1]                       # last (partial) window dropped
    assert w["W"].shape[1] == len(w["names"])


def test_window_max_score():
    wid = np.array([0, 0, 0, 1, 1, 2])
    s = np.array([0.1, 0.9, 0.3, 0.2, 0.2, 0.5], np.float32)
    c = np.array([1, 2, 1, 1, 2, 3], np.int16)
    sw, cw = L.window_scores_from_frames(wid, 3, s, c)
    assert np.allclose(sw, [0.9, 0.2, 0.5]) and cw[0] == 2 and cw[2] == 3


def test_threshold_ties_never_exceed_budget_in_float32():
    rng = np.random.default_rng(1)
    s = np.round(rng.random(2000), 1).astype(np.float32)       # many ties
    y = np.zeros(2000, int)
    thr = budget_threshold(s, 0.01)
    pred = L.decide(s, np.ones(2000, np.int16), thr)
    assert (pred != 0).mean() <= 0.01 + 1e-12


def test_summarize_perfect_and_bootstrap():
    rng = np.random.default_rng(2)
    y = np.r_[np.zeros(200, int), np.ones(50, int), np.full(50, 2)]
    s = np.r_[rng.random(200) * 0.1, 0.9 + rng.random(100) * 0.1]
    c = np.r_[np.ones(200, int), np.ones(50, int), np.full(50, 2)].astype(np.int16)
    g = np.arange(300) % 10
    r = L.summarize(y, s, c, 0.5, groups=g, n_boot=50)
    assert r["macro_f1"] == 1.0 and r["fpr"] == 0.0 and r["recall_any"] == 1.0
    assert r["ci95"]["macro_f1"][0] <= r["ci95"]["macro_f1"][1] and r["n_groups"] == 10


def test_dedup_drops_exact_rows_only():
    d = {"t": np.array([0., 0., 1.]), "id": np.array([1, 1, 1], np.int32), "dlc": np.array([1, 1, 1], np.int8),
         "B": np.array([[1] + [-1] * 7, [1] + [-1] * 7, [2] + [-1] * 7], np.int16), "lab": np.array([0, 0, 1], np.int8)}
    d2, rep = L.dedup(d)
    assert rep["exact_duplicates"] == 1 and len(d2["t"]) == 2
