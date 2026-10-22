"""Tests for network/l2b.py (WP4 S4): window matrices, gap statistics on known series, minimum-connection rule, continuous activity is not a beacon,
benign-learned tail scoring, topology-free property (renaming addresses changes nothing)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from network import l2b


def _stream(minutes, src=1, dst=2, port=8080):
    m = np.asarray(minutes, dtype="int64")
    return pd.DataFrame({"src_id": src, "dst_id": dst, "dst_port": port, "protocol": 6, "minute": m, "row": np.arange(len(m))})


def _stats(df, n_min=6):
    c = l2b.build_cells(df)
    return c, l2b.cell_stats(c, l2b.WIN, n_min)


def test_window_matrix_matches_reference():
    mins = [100, 103, 104, 110, 130, 131, 170]
    c = l2b.build_cells(_stream(mins))
    X, C = l2b._window_matrix(c, 0, len(c["comb"]))
    for i, m in enumerate(sorted(set(mins))):
        ref = np.array([(m - j) in mins for j in range(l2b.WIN)])
        assert (X[i] == ref).all()


def test_perfect_period_has_zero_gap_cv():
    df = _stream(np.arange(0, 120, 5))
    _, s = _stats(df)
    last = s["cv"][-1]
    assert abs(last) < 1e-9 and s["tol"][-1] == 1.0 and s["_med"][-1] == 5.0
    assert s["acf"][-1] > 0.8


def test_min_connections_before_scoring():
    df = _stream(np.arange(0, 20, 5))      # 4 active minutes
    _, s = _stats(df, n_min=6)
    assert np.isnan(s["cv"]).all() and np.isnan(s["tol"]).all()
    _, s2 = _stats(df, n_min=4)
    assert not np.isnan(s2["cv"][-1])


def test_continuous_activity_is_not_a_beacon():
    df = _stream(np.arange(0, 40))          # every minute: median gap 1
    _, s = _stats(df)
    assert np.isnan(s["cv"]).all() and np.isnan(s["acf"]).all()


def test_jitter_lowers_regularity():
    rng = np.random.RandomState(0)
    reg = np.cumsum(np.full(40, 4))
    jit = np.cumsum(rng.randint(1, 12, 40))
    _, a = _stats(_stream(reg))
    _, b = _stats(_stream(jit))
    assert a["cv"][-1] > b["cv"][-1] and a["mad"][-1] >= b["mad"][-1]


def test_rate_statistic_for_metronome_below_one_minute():
    mins = np.repeat(np.arange(30), 6)      # 6 flows every minute (10 s period)
    _, s = _stats(_stream(mins))
    assert np.isnan(s["cv"][-1]) and abs(s["rate"][-1]) < 1e-9


def test_reply_flows_are_ignored():
    df = _stream(np.arange(0, 120, 5), port=50000)
    c = l2b.build_cells(df)
    assert len(c["comb"]) == 0 or (c["fcell"] == -1).all()


def _benign(seed=0, groups=300):
    rng = np.random.RandomState(seed)
    parts = []
    for g in range(groups):
        n = rng.randint(8, 40)
        parts.append(_stream(np.sort(rng.randint(0, 400, n)), src=g, dst=1000 + g % 7, port=int(rng.choice([80, 443, 53]))))
    return pd.concat(parts, ignore_index=True).sort_values(["minute", "row"], kind="stable").reset_index(drop=True)


def test_periodic_group_scores_above_benign_and_ids_do_not_matter():
    ben = _benign()
    L = l2b.Beacon().fit(ben)
    test = pd.concat([ben.head(2000), _stream(np.arange(0, 300, 7), src=9999, dst=9998, port=8080)], ignore_index=True)
    test = test.sort_values(["minute", "row"], kind="stable").reset_index(drop=True)
    sc = L.stream_scores(test)
    per = (test["src_id"] == 9999).to_numpy()
    assert sc[per].max() > np.quantile(sc[~per], 0.99)
    # renaming addresses changes nothing
    ren = test.copy()
    ren["src_id"], ren["dst_id"] = ren["src_id"] * 7 + 3, ren["dst_id"] * 5 + 1
    assert np.allclose(L.stream_scores(ren), sc)
    # flows of groups below the minimum score 0
    assert sc[(test["src_id"] == 9999).to_numpy()][:3].max() == 0.0
