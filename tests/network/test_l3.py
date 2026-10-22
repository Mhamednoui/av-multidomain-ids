"""Tests for network/l3.py (WP4 S5): feature hygiene, preprocessing, service grouping, service-conditional scoring, per-service normalisation,
Layer contract (calibration budget), determinism, topology-free property (no address column needed, row order irrelevant), attributions."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from common.config import BUDGET_DOMAIN
from network import l3
from network.flows import FEATURES


def _flows(n, rng, port=80, scale=1.0, odd=None):
    d = {f: np.abs(rng.lognormal(3.0, 1.0, n)) * scale for f in FEATURES}
    d["Tot Fwd Pkts"] = rng.randint(1, 20, n).astype(float) * scale
    d["Fwd Byts/b Avg"] = np.zeros(n)                         # constant column
    df = pd.DataFrame(d)
    if odd:
        for k, v in odd.items():
            df[k] = v
    df["dst_port"] = port
    df["protocol"] = 6
    return df


def _two_services(n=6000, seed=0):
    rng = np.random.RandomState(seed)
    a = _flows(n, rng, port=80, scale=1.0)
    b = _flows(n, rng, port=22, scale=8.0)
    return pd.concat([a, b], ignore_index=True)


def test_feature_sets_hygiene():
    allf, clean = l3.feature_set("all"), l3.feature_set("clean")
    assert allf == list(FEATURES) and len(allf) == 76
    assert set(clean) < set(allf)
    for bad in l3.HOST_STACK + l3.TOOL_FLAGS + l3.DUPLICATES:
        assert bad not in clean
    for idf in ("src_ip", "dst_ip", "Flow ID", "src_port", "dst_port", "protocol", "ts"):
        assert idf not in allf and idf not in clean


def test_prep_finite_and_constant_dropped():
    rng = np.random.RandomState(1)
    df = _flows(2000, rng)
    df.loc[:50, "Flow Duration"] = np.nan
    df.loc[51:60, "Flow Duration"] = -5.0
    p = l3.Prep(l3.feature_set("clean")).fit(df)
    Z = p.transform(df)
    assert np.isfinite(Z).all() and Z.shape[1] == len(p.names)
    assert "Fwd Byts/b Avg" not in p.names
    assert np.abs(Z).max() <= l3.CLIP + 1e-6


def test_groups_bucket_and_fallback():
    rng = np.random.RandomState(2)
    big = _flows(l3.MIN_SVC + 10, rng, port=80)
    rare = _flows(300, rng, port=5555)                       # below MIN_SVC, registered-port bucket
    g = l3.Groups().fit(pd.concat([big, rare], ignore_index=True))
    q = pd.DataFrame({"dst_port": [80, 5555, 6000, 9, 80], "protocol": [6, 6, 6, 6, 99]})
    a = g.assign(q)
    assert a[0] == 6 * 100000 + 80
    assert a[1] == l3.bucket_key(np.array([6 * 100000 + 5555]))[0] == a[2]     # same registered-port bucket
    assert a[3] == -1 and a[4] == -1                         # port class without enough train flows / unseen protocol -> global


def test_service_profile_is_service_conditional():
    tr = _two_services()
    L = l3.ServiceProfile(mode="maha").fit(tr)
    rng = np.random.RandomState(5)
    a_norm = _flows(500, rng, port=80, scale=1.0)
    a_in_b = _flows(500, rng, port=80, scale=50.0)            # a flow shape that is normal for another service but anomalous here
    s_norm, s_odd = L.raw_scores(a_norm), L.raw_scores(a_in_b)
    assert np.median(s_odd) > 3 * np.median(s_norm)


def test_modes_rank_an_outlier_first():
    tr = _two_services()
    rng = np.random.RandomState(6)
    test = _flows(200, rng, port=80)
    test.loc[0, "Pkt Len Max"] = 1e7
    test.loc[0, "Flow Duration"] = 1e9
    for mode in ("rz_mean", "rz_top3", "maha", "hbos"):
        L = l3.ServiceProfile(mode=mode).fit(tr)
        s = L.raw_scores(test)
        assert np.isfinite(s).all()
        if mode != "hbos":          # a histogram score gives the open tail bin the mass of one quantile bin: not a distance (negative result of S5)
            assert s.argmax() == 0, mode


def test_layer_contract_budget_and_evidence():
    tr = _two_services(5000, 3)
    val = _two_services(5000, 4)
    L = l3.ServiceProfile(mode="maha").fit(tr)
    L.calibrate(val, BUDGET_DOMAIN)
    ev = L.score(val.iloc[:200])
    assert len(ev) == 200 and all(e.domain == "network" and e.layer == "L3" and e.name == "net.l3_service" for e in ev)
    fa = np.mean([e.alarm for e in L.score(val)])
    assert fa <= BUDGET_DOMAIN + 1e-9


def test_per_service_normalisation_shares_the_budget():
    rng = np.random.RandomState(7)
    busy = _flows(8000, rng, port=80)
    busy["Pkt Len Max"] *= rng.pareto(1.0, len(busy)) + 1.0           # heavy-tailed busy service
    calm = _flows(8000, rng, port=22)
    tr = pd.concat([busy, calm], ignore_index=True)
    L = l3.ServiceProfile(mode="maha", svc_norm=True).fit(tr)
    val = pd.concat([_flows(4000, rng, port=80), _flows(4000, rng, port=22)], ignore_index=True)
    val.loc[:3999, "Pkt Len Max"] *= rng.pareto(1.0, 4000) + 1.0
    s = L.raw_scores(val)
    thr = np.quantile(s, 0.99)
    fa_busy, fa_calm = (s[:4000] >= thr).mean(), (s[4000:] >= thr).mean()
    assert fa_calm > 0.003 and abs(fa_busy - fa_calm) < 0.02        # without the normalisation the busy service holds nearly all alarms


def test_isoforest_and_autoencoder_deterministic_and_rank():
    tr = _two_services(3000, 8)
    rng = np.random.RandomState(9)
    test = _flows(100, rng, port=80)
    test.loc[0, FEATURES[:30]] = 1e12                         # extreme in half of the columns
    for L1, L2 in ((l3.IsoForest(n_estimators=30, n_fit=4000), l3.IsoForest(n_estimators=30, n_fit=4000)),
                   (l3.AutoEncoder(hidden=(8, 4, 8), epochs=4, n_fit=4000), l3.AutoEncoder(hidden=(8, 4, 8), epochs=4, n_fit=4000))):
        s1 = L1.fit(tr).raw_scores(test)
        assert np.isfinite(s1).all() and s1.argmax() == 0
        if isinstance(L1, l3.IsoForest):
            assert np.allclose(s1, L2.fit(tr).raw_scores(test))


def test_scores_need_no_address_and_ignore_row_order():
    tr = _two_services(3000, 10)
    L = l3.ServiceProfile(mode="maha").fit(tr)
    rng = np.random.RandomState(11)
    t = _flows(300, rng, port=80)
    assert not any(c in t.columns for c in ("src_ip", "dst_ip", "src_port", "Flow ID", "ts"))
    s = L.raw_scores(t)
    perm = rng.permutation(len(t))
    assert np.allclose(L.raw_scores(t.iloc[perm]), s[perm])
    t2 = t.copy()
    t2["src_ip"], t2["dst_ip"], t2["src_port"] = "10.0.0.1", "10.0.0.2", 12345
    assert np.allclose(L.raw_scores(t2), s)                   # address / source-port columns are ignored


def test_contributions_explain_the_outlier():
    tr = _two_services(4000, 12)
    rng = np.random.RandomState(13)
    t = _flows(5, rng, port=80)
    t.loc[0, "Bwd Pkt Len Max"] = 1e8
    for mode in ("rz_mean", "maha"):
        L = l3.ServiceProfile(mode=mode).fit(tr)
        C, names = L.contributions(t)
        assert C.shape == (5, len(names))
        assert names[int(np.argmax(C[0]))] in ("Bwd Pkt Len Max", "Pkt Len Max", "Pkt Len Std", "Pkt Len Var", "Bwd Pkt Len Mean", "Bwd Pkt Len Std",
                                               "Pkt Len Mean", "Pkt Size Avg", "TotLen Bwd Pkts", "Flow Byts/s"), (mode, names[int(np.argmax(C[0]))])
    Lm = l3.ServiceProfile(mode="maha").fit(tr)
    C, _ = Lm.contributions(t)
    d2 = (Lm.raw_scores(t) ** 2) * C.shape[1]
    assert np.allclose(C.sum(1), d2, rtol=1e-3, atol=1e-3)         # attribution sums to the squared Mahalanobis distance
