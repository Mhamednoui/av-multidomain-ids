"""Tests for network/domain.py (WP4 S7): the frozen network domain (stack H) on synthetic flows, Evidence fields, save / load round trip,
window finality (flows flagged final do not change when later flows are appended), equality with DomainCombiner, and the S7 vectorised combiner helper."""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.combiner import DomainCombiner
from common.evidence import Evidence
from network.domain import NetworkDomain


def _flows(rng, minutes, n_src=30, scan=False):
    rows = []
    for m in minutes:
        for s in range(n_src):
            for _ in range(rng.randint(1, 4)):
                rows.append((m * 60.0 + rng.rand() * 59, f"10.0.0.{s}", f"10.1.0.{rng.randint(1, 4)}", int(rng.choice([80, 443])), 6, 3, 3, 100.0, 100.0, 2e6))
        if scan and m % 10 == 5:
            for p in range(1, 301):
                rows.append((m * 60.0 + 30.0, "10.9.9.9", "10.1.0.2", p, 6, 1, 0, 0.0, 0.0, 1e4))
    d = pd.DataFrame(rows, columns=["ts", "src_ip", "dst_ip", "dst_port", "protocol", "Tot Fwd Pkts", "Tot Bwd Pkts", "TotLen Fwd Pkts", "TotLen Bwd Pkts", "Flow Duration"])
    for f in ("FIN", "SYN", "RST", "PSH", "ACK", "URG", "ECE"):
        d[f + " Flag Cnt"] = 0.0
    d["SYN Flag Cnt"], d["ACK Flag Cnt"], d["FIN Flag Cnt"] = 1.0, 1.0, 1.0
    scan_rows = d["Tot Bwd Pkts"] == 0
    d.loc[scan_rows, ["ACK Flag Cnt", "FIN Flag Cnt"]] = 0.0
    return d


def _fitted(seed=0):
    rng = np.random.RandomState(seed)
    D = NetworkDomain("H", method="max")
    tr = D.prepare(_flows(rng, range(1000, 1060)))
    va = D.prepare(_flows(rng, range(1100, 1160)))
    return D.fit(tr, va), rng


def test_fit_and_alarm_on_scan():
    D, rng = _fitted()
    fl = _flows(rng, range(1200, 1240), scan=True)
    comb, per = D.score_stream(fl)
    assert len(comb) == len(fl) and set(per) == {"net.tcp_flags", "net.scan", "net.trw", "net.bruteforce"}
    assert all(isinstance(e, Evidence) and e.domain == "network" and e.layer == "combined" and e.name == "network.combined" for e in comb)
    assert all(0.0 <= e.score <= 1.0 for e in comb)
    st = D.prepare(fl)
    isscan = (st["src_ip"] == "10.9.9.9").to_numpy()
    al = np.array([e.alarm for e in comb])
    assert al[isscan].mean() > 0.95, al[isscan].mean()
    assert al[~isscan].mean() < 0.05, al[~isscan].mean()
    ex = next(e for e, s in zip(comb, isscan) if s and e.alarm)
    assert ex.reason.startswith("Network alarm") and "net." in ex.reason and set(ex.details) == {"method", "layer_scores", "final"}
    assert all(e.reason == "" for e, a in zip(comb, al) if not a)


def test_combined_equals_domaincombiner():
    D, rng = _fitted(1)
    fl = _flows(rng, range(1200, 1215), scan=True)
    comb, per = D.score_stream(fl)
    C = DomainCombiner(method=D.comb.method)
    C.layer_names, C.model, C.threshold = D.comb.layer_names, D.comb.model, D.comb.threshold
    ref = C.combine(per)
    assert np.allclose([e.score for e in comb], [e.score for e in ref])
    assert [e.alarm for e in comb] == [e.alarm for e in ref]


def test_save_load_roundtrip():
    D, rng = _fitted(2)
    fl = _flows(rng, range(1200, 1215), scan=True)
    a, _ = D.score_stream(fl)
    with tempfile.TemporaryDirectory() as tmp:
        D.save(tmp)
        D2 = NetworkDomain.load(tmp)
        assert (Path(tmp) / "domain.json").exists()
    b, _ = D2.score_stream(fl)
    assert np.array_equal([e.score for e in a], [e.score for e in b]) and [e.alarm for e in a] == [e.alarm for e in b]


def test_final_flows_do_not_change_with_later_flows():
    D, rng = _fitted(3)
    fl = _flows(rng, range(1200, 1240), scan=True)
    cut = 1220 * 60.0
    early = fl[fl["ts"] < cut]
    a, _ = D.score_stream(early)
    b, _ = D.score_stream(fl)
    ia = {e.sample_id: e for e in a}
    ib = {e.sample_id: e for e in b}
    # sample_id = position inside the call: the early flows are the first rows of the same table, so ids agree
    n_final = 0
    for sid, e in ia.items():
        if e.details["final"]:
            n_final += 1
            assert abs(e.score - ib[sid].score) < 1e-12 and e.alarm == ib[sid].alarm
    assert n_final > 0.5 * len(ia)


def test_topology_free_renaming_addresses():
    D, rng = _fitted(4)
    fl = _flows(rng, range(1200, 1215), scan=True)
    a, _ = D.score_stream(fl)
    ren = fl.copy()
    ren["src_ip"] = "x" + ren["src_ip"]
    ren["dst_ip"] = "y" + ren["dst_ip"]
    b, _ = D.score_stream(ren)
    assert np.allclose([e.score for e in a], [e.score for e in b])


def test_arr_combiner_matches_domaincombiner():
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
    from tools.WP4_S7_lib import ArrCombiner
    rng = np.random.RandomState(0)
    n = 4000
    y = (rng.rand(n) < 0.2).astype(int)
    g = rng.randint(0, 20, n).astype(str)
    X = np.clip(rng.rand(n, 3) * 0.99 + y[:, None] * rng.rand(n, 3) * 0.3, 0, 0.999999)
    names = ["a", "b", "c"]
    A = ArrCombiner(method="auto").fit({k: X[:, i] for i, k in enumerate(names)}, y, g)
    ev = {k: [Evidence("network", "L2a", k, float(i), float(X[i, j]), False) for i in range(n)] for j, k in enumerate(names)}
    B = DomainCombiner(method="auto").fit(ev, y, g)
    assert A.method == B.method and abs(A.threshold - B.threshold) < 1e-12
    s_ref = np.array([e.score for e in B.combine(ev)])
    assert np.allclose(A.scores(X), s_ref)


def test_scorer_block_bootstrap_counts():
    from tools.WP4_S7_lib import Scorer
    n = 2000
    rng = np.random.RandomState(1)
    df = pd.DataFrame({"fam": np.where(rng.rand(n) < 0.3, "Bot", "BENIGN"), "audit": False, "day": "d", "t": np.arange(n) * 3.0, "period": 0})
    al = (df["fam"] == "Bot").to_numpy() & (rng.rand(n) < 0.6)
    s = Scorer(df, "fam", families=["Bot"]).summary(al)
    assert abs(s["detection"]["Bot"] - al[df["fam"] == "Bot"].mean()) < 1e-12 and s["fa"] == 0.0
    lo, hi = s["detection_ci"]["Bot"]
    assert lo < s["detection"]["Bot"] < hi and hi - lo < 0.2


def test_stack_o_roundtrip_with_autoencoder_weights():
    from network.flows import FEATURES
    rng = np.random.RandomState(5)

    def mk(minutes):
        d = _flows(rng, minutes)
        for c in FEATURES:
            if c not in d.columns:
                d[c] = rng.gamma(2.0, 50.0, len(d))
        return d

    D = NetworkDomain("O", method="noisy_or", l3_params={"service": {"mode": "maha"}, "ae": {"epochs": 3}})
    tr, va = D.prepare(mk(range(1000, 1060))), D.prepare(mk(range(1100, 1160)))
    D.fit(tr, va)
    fl = mk(range(1200, 1210))
    a, per = D.score_stream(fl)
    assert set(per) == {"net.tcp_flags", "net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.l3_service", "net.l3_ae"}
    with tempfile.TemporaryDirectory() as tmp:
        D.save(tmp)
        D2 = NetworkDomain.load(tmp)
    b, _ = D2.score_stream(fl)
    assert np.allclose([e.score for e in a], [e.score for e in b], atol=1e-6) and D.layers[-1].model is not None
