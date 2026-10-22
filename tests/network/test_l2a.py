"""Tests for network/l2a.py (WP4 S3): sliding-window counts against a brute-force reference, TRW, scan, brute force, DoS rate, slow,
topology-free property (renaming addresses changes nothing)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from network import l2a


def _ref_trailing(kid, minute, W, iid=None):
    out = []
    for k, m in zip(kid, minute):
        sel = (kid == k) & (minute <= m) & (minute > m - W)
        out.append(len(set(iid[sel])) if iid is not None else int(sel.sum()))
    return np.array(out)


def test_trailing_matches_reference():
    rng = np.random.RandomState(0)
    n = 400
    kid, minute, iid = rng.randint(0, 5, n), rng.randint(100, 140, n), rng.randint(0, 6, n)
    for W in (1, 3, 5, 11):
        assert (l2a.trailing(kid, minute, W) == _ref_trailing(kid, minute, W)).all()
        assert (l2a.trailing(kid, minute, W, iid) == _ref_trailing(kid, minute, W, iid)).all()
    w = rng.randint(0, 2, n).astype(float)
    ref = np.array([w[(kid == k) & (minute <= m) & (minute > m - 4)].sum() for k, m in zip(kid, minute)])
    assert np.allclose(l2a.trailing(kid, minute, 4, w=w), ref)


def _flows(n, src, dst, port, minute, fwd=3, bwd=3, dur=2e6, proto=6, plen=100.0):
    return pd.DataFrame({"src_id": src, "dst_id": dst, "dst_port": port, "protocol": proto, "minute": minute,
                         "Tot Fwd Pkts": float(fwd), "Tot Bwd Pkts": float(bwd), "TotLen Fwd Pkts": plen, "TotLen Bwd Pkts": plen,
                         "Flow Duration": dur, "row": 0}, index=range(n))


def _benign(seed=0):
    rng = np.random.RandomState(seed)
    parts = []
    for m in range(200, 400):
        for s in range(30):
            k = rng.randint(1, 4)
            parts.append(_flows(k, s, rng.randint(100, 104, k), rng.choice([80, 443], k), m))
    d = pd.concat(parts, ignore_index=True)
    d["row"] = np.arange(len(d))
    return d


def _scan_attack(m=500):
    d = _flows(300, 999, 100, np.arange(300) + 1, m, fwd=1, bwd=1, plen=0.0)
    d["row"] = np.arange(len(d)) + 10**6
    return d


def test_scan_and_trw_see_a_port_scan():
    ben = _benign()
    atk = _scan_attack()
    for L in (l2a.Scan(W=1), l2a.Trw(W=1)):
        L.fit(ben)
        s_b, s_a = L.stream_scores(ben), L.stream_scores(pd.concat([ben, atk], ignore_index=True))[len(ben):]
        assert s_a.min() > np.quantile(s_b, 0.999), L.name


def test_trw_failures_up_successes_down():
    ok = _flows(10, 1, np.arange(10), 80, 5)
    ok["row"] = np.arange(10)
    bad = ok.copy(); bad["Tot Bwd Pkts"] = 0.0
    L = l2a.Trw(W=1)
    assert L.stream_scores(ok)[0] == 0.0
    assert abs(L.stream_scores(bad)[0] - 10 * l2a.TRW_STEP) < 1e-9
    # a repeated contact to the same (dst, port) counts once
    rep = _flows(10, 1, 7, 80, 5, bwd=0)
    rep["row"] = np.arange(10)
    assert abs(L.stream_scores(rep)[0] - l2a.TRW_STEP) < 1e-9


def test_bruteforce_counts_sessions_per_service():
    ben = _benign()
    ben = pd.concat([ben] + [_flows(1, s, 100, 22, 300 + s) for s in range(150)], ignore_index=True)
    L = l2a.BruteForce(W=1).fit(ben)
    atk = _flows(100, 999, 100, 22, 500)
    s = L.stream_scores(pd.concat([ben, atk], ignore_index=True))
    assert s[len(ben):].min() > np.quantile(s[:len(ben)], 0.999)


def test_dos_rate_uses_the_destinations_own_baseline():
    rng = np.random.RandomState(1)
    parts = []
    for m in range(300):                                     # dst 1: ~2 flows / min, dst 2: ~40 flows / min (busy but normal)
        parts.append(_flows(2, rng.randint(0, 50, 2), 1, 80, m))
        parts.append(_flows(40, rng.randint(0, 50, 40), 2, 80, m))
    ben = pd.concat(parts, ignore_index=True)
    L = l2a.DosRate(W=1).fit(ben)
    test = pd.concat([_flows(40, 5, 1, 80, 1000), _flows(40, 5, 2, 80, 1000)], ignore_index=True)
    s = L.stream_scores(test)
    assert s[0] > s[-1] + 2.0                                # 40 flows / min is a flood for dst 1, normal for dst 2
    assert L.stream_scores(test, same_network=False)[0] == L.stream_scores(test, same_network=False)[-1]   # no lookup on another network


def test_slow_counts_halfopen_and_stalled():
    ben = _benign()
    L = l2a.Slow(W=1).fit(ben)
    slow = _flows(50, np.arange(50), 100, 80, 600, fwd=3, bwd=1, dur=60e6)
    half = _flows(50, np.arange(50), 101, 80, 600, fwd=1, bwd=0, dur=1e6)
    s = L.stream_scores(pd.concat([ben, slow, half], ignore_index=True))
    base = np.quantile(s[:len(ben)], 0.999)
    assert s[len(ben):len(ben) + 50].min() > base and s[len(ben) + 50:].min() > base


def test_topology_free_renaming_addresses():
    ben, atk = _benign(), _scan_attack()
    full = pd.concat([ben, atk], ignore_index=True)
    perm = np.random.RandomState(3).permutation(2000)
    ren = full.copy()
    ren["src_id"], ren["dst_id"] = perm[full["src_id"].to_numpy()], perm[full["dst_id"].to_numpy() + 1000]
    for cls in (l2a.Scan, l2a.Trw, l2a.BruteForce, l2a.Slow):
        a = cls(W=5).fit(full).stream_scores(full)
        b = cls(W=5).fit(ren).stream_scores(ren)
        assert np.allclose(a, b), cls.name
