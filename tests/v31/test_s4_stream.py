"""WP8 S4 tests for network/stream31.py: E1 RunningState == independent quadratic reference (several windows / bins), E2 last running value of a cell == the v3 cell value (scan, bruteforce, trw),
stream (one flow at a time, Evidence) == batch table path, causality (appending later flows never changes earlier Evidence), v3 frozen domain untouched by building a Stream31."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "network"))
from network import l2a
from network.domain import NetworkDomain
from network.stream31 import LAYERS, RunningState, Stream31, Stream31Final, reference_running
from test_domain import _flows, _fitted  # noqa: E402


def _rows(seed, n=500, ticks=14, tick_s=60.0):
    rng = np.random.RandomState(seed)
    t = np.sort(rng.randint(0, ticks, n) * tick_s + rng.randint(0, int(tick_s), n))
    rows = []
    for i in range(n):
        port = int(rng.choice([22, 80, 443, 8080, 40000, 50000, 21, 23]))
        proto = int(rng.choice([6, 6, 6, 17]))
        rows.append((float(t[i]), int(rng.randint(0, 4)), int(rng.randint(0, 5)), port, proto, int(rng.randint(1, 3)), int(rng.randint(0, 3)), float(rng.choice([0, 4, 100])), float(rng.choice([0, 6, 90]))))
    return rows


def test_running_equals_reference():
    for seed, (w_scan, w_brute, trw_bin) in enumerate([(1, 1, 5), (3, 2, 1), (2, 4, 3), (1, 1, 1)]):
        rows = _rows(seed)
        ref = reference_running(rows, 60.0, w_scan, w_brute, trw_bin)
        st = RunningState(60.0, w_scan, w_brute, trw_bin, sweep_every=37)         # frequent sweeps: eviction must not change values
        got = [st.push(int(r[0] // 60), *r[1:]) for r in rows]
        assert [tuple(g) for g in got] == [tuple(r) for r in ref], (seed, w_scan, w_brute, trw_bin)


def test_running_carry_equals_reference():
    for seed, (w_scan, w_brute, trw_bin) in enumerate([(1, 1, 5), (1, 1, 1), (2, 3, 2)]):
        rows = _rows(20 + seed, n=400, ticks=12)
        ref = reference_running(rows, 60.0, w_scan, w_brute, trw_bin, carry=True)
        st = RunningState(60.0, w_scan, w_brute, trw_bin, sweep_every=29, carry=True)
        got = [st.push(int(r[0] // 60), *r[1:]) for r in rows]
        assert [tuple(g) for g in got] == [tuple(r) for r in ref], (seed, w_scan, w_brute, trw_bin)
        base = reference_running(rows, 60.0, w_scan, w_brute, trw_bin)
        assert all(a[j] >= b[j] for a, b in zip(got, base) for j in range(4))        # carry never lowers a statistic


def _table(rows, W=1):
    d = pd.DataFrame(rows, columns=["t", "src_id", "dst_id", "dst_port", "protocol", "Tot Fwd Pkts", "Tot Bwd Pkts", "TotLen Fwd Pkts", "TotLen Bwd Pkts"])
    d["minute"] = (d["t"] // 60).astype("int64")
    d["row"] = np.arange(len(d))
    return d


def test_last_of_cell_equals_v3_cell_value():
    rows = _rows(5, n=800)
    d = _table(rows)
    st = RunningState(60.0, 1, 1, 5)
    run = np.array([st.push(int(r[0] // 60), *r[1:]) for r in rows])
    sc, br, tr = l2a.Scan(W=1), l2a.BruteForce(W=1), l2a.Trw(W=5)
    f_sc, f_br, f_tr = sc.feats(d), br.feats(d), tr.feats(d)
    # cells: scan ports (src, dst, minute), hosts (src, minute), brute (src, dst, port, proto, minute), trw (src, bin)
    def last_of(keys):
        k = pd.concat([x.astype(str) for x in keys], axis=1).agg("|".join, axis=1)
        return pd.Series(np.arange(len(d))).groupby(k.to_numpy()).transform("max").to_numpy()
    li = last_of([d["src_id"], d["dst_id"], d["minute"]])
    assert (run[li, 0] == f_sc["ports"]).all()
    li = last_of([d["src_id"], d["minute"]])
    assert (run[li, 1] == f_sc["hosts"]).all()
    li = last_of([d["src_id"], d["dst_id"], d["dst_port"], d["protocol"], d["minute"]])
    assert (run[li, 2] == f_br["n"]).all()
    li = last_of([d["src_id"], d["minute"] // 5])
    assert np.allclose(run[li, 3], f_tr["peak"])


def _stream31(seed=0):
    D, rng = _fitted(seed)
    S = Stream31.from_frozen(D)
    va = D.prepare(_flows(rng, range(1300, 1340)))
    S.calibrate(va)
    return D, S, rng


def test_stream_equals_batch_and_causal():
    D, S, rng = _stream31(2)
    fl = _flows(rng, range(1400, 1420), scan=True)
    st = D.prepare(fl)
    st["t"] = st["t"].astype(float)
    s, alarm, X, raw = S.score_table(st)
    S.reset()
    recs = st[["ts", "src_ip", "dst_ip", "dst_port", "protocol"] + [c for c in st.columns if c.startswith(("Tot", "Flow", "FIN", "SYN", "RST", "PSH", "ACK", "URG", "ECE"))]].to_dict("records")
    ev = [S.push(r) for r in recs]
    assert max(abs(e.score - x) for e, x in zip(ev, s)) <= 1e-12
    assert [e.alarm for e in ev] == list(alarm)
    assert alarm[(st["src_ip"] == "10.9.9.9").to_numpy()].mean() > 0.9      # the scanner is still detected, causally
    # causality: the first k Evidence of a longer stream equal those of the prefix
    S.reset()
    k = len(recs) // 2
    pre = [S.push(r) for r in recs[:k]]
    assert [e.score for e in pre] == [e.score for e in ev[:k]]
    # delay is zero by construction: Evidence timestamp == flow timestamp
    assert all(e.t == r["ts"] for e, r in zip(ev, recs))


def test_frozen_v3_domain_unchanged_by_stream31():
    D, S, rng = _stream31(3)
    fl = _flows(rng, range(1500, 1520), scan=True)
    c1, _ = D.score_stream(fl)
    S2 = Stream31.from_frozen(D)
    S2.calibrate(D.prepare(_flows(rng, range(1600, 1620))))
    c2, _ = D.score_stream(fl)
    assert [e.score for e in c1] == [e.score for e in c2]
    assert S2.scan is not [L for L in D.layers if L.name == "net.scan"][0]


def test_final_emission_equals_v3_cell_statistics_and_batch():
    D, rng = _fitted(4)
    F = Stream31Final.from_frozen(D)
    F.calibrate(D.prepare(_flows(rng, range(1700, 1740))))
    st = D.prepare(_flows(rng, range(1800, 1830), scan=True))
    st["t"] = st["t"].astype(float)
    s_b, a_b, X_b, raw_b = F.score_table(st)
    # final statistics of the batch path equal the v3 cell values (trw bin = 1 tick)
    sc, br, tr = F.scan, F.brute, l2a.Trw(W=1)
    st2 = st.assign(minute=(st["t"] // 60).astype("int64"))
    assert np.allclose(raw_b["net.scan"], sc.stream_scores(st2)) and np.allclose(raw_b["net.bruteforce"], br.stream_scores(st2)) and np.allclose(raw_b["net.trw"], tr.stream_scores(st2))
    # stream: Evidence arrives only when the next tick starts; same scores / alarms as the batch path
    F.reset()
    recs = st[["ts", "src_ip", "dst_ip", "dst_port", "protocol"] + [c for c in st.columns if c.startswith(("Tot", "Flow", "FIN", "SYN", "RST", "PSH", "ACK", "URG", "ECE"))]].to_dict("records")
    got, emitted_at = {}, {}
    for i, r in enumerate(recs):
        for e in F.push(r):
            got[int(e.sample_id)] = e
            emitted_at[int(e.sample_id)] = r["ts"]
    for e in F.flush():
        got[int(e.sample_id)] = e
        emitted_at[int(e.sample_id)] = recs[-1]["ts"]
    assert sorted(got) == list(range(len(recs)))
    assert max(abs(got[i].score - s_b[i]) for i in range(len(recs))) <= 1e-12 and all(got[i].alarm == bool(a_b[i]) for i in range(len(recs)))
    assert all(emitted_at[i] - recs[i]["ts"] >= 0 and emitted_at[i] // 60 <= recs[i]["ts"] // 60 + 60 for i in range(len(recs)))
