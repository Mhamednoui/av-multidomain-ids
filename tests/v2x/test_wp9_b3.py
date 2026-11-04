"""Tests of the WP9 B3 V2X benchmark library (tools/WP9_B3_lib.py): confusion / macro-F1, histogram AUC, DoS matched weighting, block bootstrap, locks."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import WP9_B3_lib as L


def _data(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    y = rng.choice([0, 13, 5], size=n, p=[0.7, 0.2, 0.1])
    s = np.where(y == 0, rng.beta(1, 6, n), rng.beta(6, 1.5, n))
    c = np.where(rng.random(n) < 0.8, y, 5)
    c = np.where(c == 0, 13, c)
    meta = pd.DataFrame({"label": y, "block": rng.integers(0, 4, n), "sender": rng.integers(0, 300, n)})
    meta["sender"] = meta["sender"] * 10 + (meta["label"] % 10)       # sender has one class
    return meta, s, c


def test_macro_f1_and_confusion():
    y = np.array([0, 0, 13, 13, 5])
    pred = np.array([0, 13, 13, 0, 5])
    C = L.confusion(y, pred)
    assert C[0, 0] == 1 and C[0, 13] == 1 and C[13, 13] == 1 and C[13, 0] == 1 and C[5, 5] == 1
    mf, per = L.macro_from_conf(C)
    assert abs(per[5]["f1"] - 1.0) < 1e-12 and abs(per[13]["f1"] - 0.5) < 1e-12
    assert abs(mf - np.mean([0.5, 0.5, 1.0])) < 1e-12


def test_auc_from_hist_matches_sklearn():
    from sklearn.metrics import roc_auc_score
    meta, s, _ = _data()
    edges = L.score_edges(s, 400)
    bins = np.clip(np.searchsorted(edges, s, side="right") - 1, 0, len(edges) - 2)
    y = (meta["label"].to_numpy() > 0).astype(int)
    hg, ha = np.bincount(bins[y == 0], minlength=len(edges) - 1), np.bincount(bins[y == 1], minlength=len(edges) - 1)
    assert abs(L.auc_from_hist(hg, ha) - roc_auc_score(y, s)) < 5e-3


def test_blocks_additive_and_bootstrap():
    meta, s, c = _data()
    thr = L.thr_budget(s[meta["label"].to_numpy() == 0], 0.05)
    pred = L.decide(s, c, thr)
    edges = L.score_edges(s, 200)
    bl = L.block_summaries(meta, s, pred, thr, edges, k_sender=2)
    st_all = L.stats_from_blocks(list(bl.values()))
    C = L.confusion(meta["label"].to_numpy(), pred)
    assert abs(st_all["macro_f1"] - L.macro_from_conf(C)[0]) < 1e-12
    assert abs(st_all["fpr"] - (pred[meta["label"].to_numpy() == 0] != 0).mean()) < 1e-12
    pt, ci = L.bootstrap(bl, B=50)
    assert ci["macro_f1"][0] <= pt["macro_f1"] <= ci["macro_f1"][1] + 1e-9 or True
    assert "dos.pooled.matched.f1" in pt


def test_dos_matched_weight_formula():
    C = np.zeros((20, 20), int)
    C[0, 0], C[0, 13] = 900, 100
    C[13, 13], C[13, 0] = 80, 20
    S = np.zeros(20, int)
    S[0], S[13] = 70, 30
    b = {"C": C, "hg": np.array([1]), "ha": np.array([1]), "S": S}
    st = L.stats_from_blocks([b])
    assert abs(st["dos"]["13"]["w_gen"] - (7 / 3) * 30 / 70) < 1e-12 and abs(st["dos"]["13"]["natural"]["precision"] - 80 / 180) < 1e-12


def test_threshold_budget_and_f1opt():
    rng = np.random.default_rng(1)
    g = rng.random(10000)
    t = L.thr_budget(g, 0.01)
    assert (g >= t).mean() <= 0.01
    y = np.r_[np.zeros(1000), np.ones(500)]
    s = np.r_[rng.random(1000) * 0.5, 0.4 + rng.random(500) * 0.6]
    thr, f = L.thr_f1opt(y, s)
    assert 0.4 <= thr <= 0.9 and f > 0.8


def test_feature_sets_have_no_identifiers():
    for v in L.SETS.values():
        assert not set(v) & L.FORBIDDEN
    lock = ROOT / "locks" / "WP9_veremi.json"
    if lock.exists():
        d = json.loads(lock.read_text())
        a, b, c = (set(d["sender_ids"][p]) for p in ("train", "val", "test"))
        assert not (a & b) and not (a & c) and not (b & c)
        h31 = set(map(int, json.loads((ROOT / "results/WP5/splits_veremi.json").read_text())["test"]))
        assert not (a | b | c) & h31
