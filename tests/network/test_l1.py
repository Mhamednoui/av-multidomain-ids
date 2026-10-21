"""Tests for network/l1.py (WP4 S2): allow-list novelty, hard limits, flag rarity, rate, calibration on benign only."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from network import l1


def _frame(n, src="192.168.10.5", dst="192.168.10.50", port=80, proto=6, flags=(0, 0, 0, 1, 1, 0, 0), seed=0):
    rng = np.random.RandomState(seed)
    pk = rng.randint(4, 30, n)
    d = pd.DataFrame({"src_ip": src, "dst_ip": dst, "src_port": 40000, "dst_port": port, "protocol": proto,
                      "Tot Fwd Pkts": pk.astype(float), "Tot Bwd Pkts": pk.astype(float),
                      "TotLen Fwd Pkts": pk * 100.0, "TotLen Bwd Pkts": pk * 500.0,
                      "Fwd Pkt Len Max": 500.0, "Fwd Pkt Len Min": 10.0, "Pkt Len Max": 1000.0,
                      "Fwd Header Len": pk * 32.0, "Bwd Header Len": pk * 32.0,
                      "Flow Duration": rng.randint(100000, 5000000, n).astype(float), "t": np.arange(n, dtype=float)})
    for f, v in zip(l1.FLAGS, flags):
        d[f] = float(v)
    return d


def _train():
    a = _frame(4000, port=80, seed=1)
    b = _frame(4000, src="192.168.10.9", dst="8.8.8.8", port=53, proto=17, flags=(0,) * 7, seed=2)
    b["Fwd Header Len"] = b["Tot Fwd Pkts"] * 8.0
    b["Bwd Header Len"] = b["Tot Bwd Pkts"] * 8.0
    return pd.concat([a, b], ignore_index=True)


def test_allow_list_flags_new_pair_and_port():
    tr = _train()
    for cls in (l1.AllowPair, l1.AllowService):
        L = cls(rare_port=10)
        L.min_support = 100
        L.fit(tr)
        seen = L.raw_scores(_frame(50, seed=3))
        newport = L.raw_scores(_frame(50, port=31337, seed=3))
        assert newport.min() > seen.max()
    P = l1.AllowPair(rare_port=10); P.min_support = 100; P.fit(tr)
    newpair = P.raw_scores(_frame(50, src="192.168.10.9", dst="192.168.10.50", port=80, seed=3))   # both hosts known, pair never seen
    assert newpair.min() > P.raw_scores(_frame(50, seed=3)).max()
    S = l1.AllowService(rare_port=10); S.min_support = 100; S.fit(tr)
    assert np.allclose(S.raw_scores(_frame(5, src="1.2.3.4")), S.raw_scores(_frame(5, src="192.168.10.5")))   # no source identity


def test_allow_list_needs_ips():
    d = _frame(10); d["src_ip"] = np.nan
    try:
        l1.AllowPair().fit(d)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_hard_violations():
    d = _frame(1)
    assert l1.hard_violations(d)[0] == 0
    x = d.copy(); x["dst_port"] = 0
    assert l1.hard_violations(x)[0] >= 1                                   # RFC 6335 port 0
    x = d.copy(); x["Fwd Header Len"] = x["Tot Fwd Pkts"] * 10.0
    assert l1.hard_violations(x)[0] >= 1                                   # TCP header < 20 B
    x = d.copy(); x["Pkt Len Max"] = 70000.0
    assert l1.hard_violations(x)[0] >= 1                                   # > 65535 B
    x = d.copy(); x["protocol"] = 99
    assert l1.hard_violations(x)[0] >= 1


def test_proto_port_unseen_protocol_for_port():
    tr = _train()
    L = l1.ProtoPort().fit(tr)
    ok = L.raw_scores(_frame(20, port=53, proto=17, flags=(0,) * 7).assign(**{"Fwd Header Len": 8.0 * np.arange(1, 21), "Tot Fwd Pkts": np.arange(1, 21.0), "Tot Bwd Pkts": 0.0}))
    bad = L.raw_scores(_frame(20, port=53, proto=6))
    assert bad.mean() > ok.mean()


def test_tcp_flags_rare_combination_and_single_packet_rule():
    tr = _train()
    L = l1.TcpFlags().fit(tr)
    base = L.raw_scores(_frame(20))
    xmas = L.raw_scores(_frame(20, flags=(0, 1, 0, 0, 1, 1, 0)))           # FIN PSH URG never seen
    null = L.raw_scores(_frame(20, flags=(0,) * 7))                         # null scan: TCP without any flag
    assert xmas.min() > base.max() and null.min() > base.max()
    one = _frame(1, flags=(1, 1, 0, 0, 0, 0, 0)); one["Tot Fwd Pkts"] = 1.0; one["Tot Bwd Pkts"] = 0.0
    two = one.copy(); two["Tot Fwd Pkts"] = 2.0
    assert L.raw_scores(one)[0] >= L.raw_scores(two)[0] + 4.9               # SYN+FIN in one packet
    udp = L.raw_scores(_frame(5, proto=17))
    assert (udp == 0).all()                                                  # not TCP -> 0


def test_flow_rate_zero_duration_many_packets():
    L = l1.FlowRate()
    n = _frame(3)
    z = n.copy(); z["Flow Duration"] = 0.0; z["Tot Fwd Pkts"] = 1000.0
    assert L.raw_scores(z).min() > L.raw_scores(n).max()
    one = n.copy(); one["Tot Fwd Pkts"] = 1.0; one["Tot Bwd Pkts"] = 0.0; one["Flow Duration"] = 0.0
    assert (L.raw_scores(one) == 0).all()


def test_calibration_budget_on_benign_val_and_evidence():
    tr = _train()
    val = pd.concat([_frame(2000, seed=7), _frame(2000, src="192.168.10.9", dst="8.8.8.8", port=53, proto=17, flags=(0,) * 7, seed=8)],
                    ignore_index=True)
    val["Fwd Header Len"] = np.where(val.protocol == 17, val["Tot Fwd Pkts"] * 8.0, val["Fwd Header Len"])
    val["Bwd Header Len"] = np.where(val.protocol == 17, val["Tot Bwd Pkts"] * 8.0, val["Bwd Header Len"])
    for L in l1.all_layers():
        L.fit(tr).calibrate(val, 0.01)
        ev = L.score(val)
        assert np.mean([e.alarm for e in ev]) <= 0.01 + 1e-9
        assert all(0 <= e.score <= 1 for e in ev)
        assert ev[0].domain == "network" and ev[0].layer == "L1" and ev[0].name == L.name
