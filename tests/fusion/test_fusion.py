"""Unit tests for fusion/streams.py, fusion/system.py and fusion/composite.py (WP6 S3 system fusion)."""
import numpy as np

from fusion import composite as CP
from fusion import streams as ST
from fusion.system import SystemFusion, alarm_events


def test_tick_helpers():
    k = np.array([0, 0, 2, 5, 9])
    v = np.array([[0.1, 0.9], [0.5, 0.2], [0.3, 0.3], [0.7, 0.0], [1.0, 1.0]])
    out = ST.tick_max(k, v, 3)
    assert out.shape == (3, 2) and np.allclose(out[0], [0.5, 0.9]) and np.allclose(out[1], 0) and np.allclose(out[2], 0.3)
    assert ST.tick_any(k, [False, True, False, True, True], 6).tolist() == [True, False, False, False, False, True]
    f = ST.tick_family(np.array([1, 1, 1, 3]), np.array(["a", "b", "b", ""], object), 4)
    assert f.tolist() == ["", "b", "", ""]


def test_hold_minutes_shows_a_closed_minute_one_minute_later():
    V, L, F = ST.hold_minutes(np.array([10, 11]), np.array([[0.2], [0.9]]), np.array([False, True]), np.array(["", "x"], object), 10, 12)
    assert V.shape == (180, 1)
    assert np.allclose(V[:60], 0) and np.allclose(V[60:120], 0.2) and np.allclose(V[120:], 0.9)
    assert not L[:120].any() and L[120:].all() and F[150] == "x"


def test_threshold_is_tie_safe_and_within_budget():
    rng = np.random.default_rng(0)
    clean = {"a": rng.random(5000), "b": np.r_[np.zeros(4000), rng.random(1000)]}
    for m in ("max", "noisy_or"):
        f = SystemFusion(["a", "b"], m).fit_calibration(clean)
        X = f.matrix(clean)
        s = f.scores(X)
        f.fit_threshold(s)
        assert (s >= f.threshold).mean() <= 0.02
        ties = SystemFusion(["a"], m).fit_calibration({"a": np.zeros(100)})
        ties.fit_threshold(ties.scores(ties.matrix({"a": np.zeros(100)})))
        assert not (ties.scores(ties.matrix({"a": np.zeros(100)})) >= ties.threshold).any()


def test_noisy_or_adds_up_weak_evidence_max_does_not():
    f = SystemFusion(["a", "b", "c"], "noisy_or")
    one = f.scores(np.array([[0.99, 0.0, 0.0]]))[0]
    three = f.scores(np.array([[0.9, 0.9, 0.9]]))[0]
    assert three > one
    g = SystemFusion(["a", "b", "c"], "max")
    assert g.scores(np.array([[0.9, 0.9, 0.9]]))[0] < g.scores(np.array([[0.99, 0.0, 0.0]]))[0]


def _part(n, score, dom_alarm, blame=None, m=2):
    return {"score": np.full(n, score, np.float32), "layers": np.zeros((n, m), np.float32), "dom_alarm": np.full(n, dom_alarm),
            "layer_alarm": np.c_[np.full(n, dom_alarm), np.zeros(n, bool)], "present": np.ones(n, bool), "label": np.zeros(n, bool),
            "blame": None if blame is None else np.full(n, blame, object)}


def test_explanation_names_fired_domains_layers_and_blame():
    f = SystemFusion(["gps", "can", "cross"], "max")
    f.threshold = 0.5
    parts = {"gps": _part(3, 0.9, True), "can": _part(3, 0.1, False), "cross": _part(3, 0.8, True, blame="gps")}
    e = f.explain(1, np.array([0.95, 0.1, 0.9]), parts, {"gps": ["gps.l1", "gps.l2"], "can": ["c1", "c2"], "cross": ["e1", "e2"]}, 0.95)
    assert [d["domain"] for d in e.domains] == ["gps", "cross"]
    assert e.domains[0]["layers_fired"] == ["gps.l1"] and e.cross_blame == "gps"
    assert "gps" in e.reason and "cross-domain blame: gps" in e.reason
    parts = {"gps": _part(3, 0.5, False), "can": _part(3, 0.4, False), "cross": _part(3, 0.1, False)}
    e = f.explain(0, np.array([0.6, 0.5, 0.1]), parts, {"gps": ["a", "b"], "can": ["a", "b"], "cross": ["a", "b"]}, 0.6)
    assert [d["domain"] for d in e.domains] == ["gps"] and "no domain alarms alone" in e.reason


def test_alarm_events():
    assert alarm_events([0, 1, 1, 0, 1, 0, 0, 1]) == 3
    assert alarm_events([1, 1]) == 1 and alarm_events([]) == 0


def _series(group, name, kind, n, onset=None, family="x", m=1):
    lab = np.zeros(n, bool)
    if onset is not None:
        lab[onset:] = True
    s = ST.series(group, name, kind, family if onset is not None else "none", np.where(lab, 0.9, 0.1), np.where(lab, 0.9, 0.1)[:, None] * np.ones(m), lab)
    s["t"] = np.arange(n, dtype=float)
    return s


def test_segment_pads_and_composites_place_the_onset_in_the_first_half():
    s = _series("g", "g/a", "attack", 10, onset=6)
    pack = {"dom_thr": 0.5, "layer_thr": [0.5], "series": [s]}
    seg = CP.segment(s, pack, 5, 8)
    assert seg["present"].tolist() == [True] * 5 + [False] * 3 and seg["label"][1] and not seg["label"][0]
    assert CP.onsets(s, "x").tolist() == [6]
    n = 20
    cross = {"dom_thr": 0.5, "layer_thr": [0.5], "series": [_series(f"d{i}", f"d{i}/p0/r0", "clean", n) for i in range(2)]}
    other = {"dom_thr": 0.5, "layer_thr": [0.5], "series": [_series("c0", "c0", "clean", 50), _series("c1", "c1", "attack", 50, onset=30)]}
    packs = {"cross": cross, "can": other, "network": other, "v2x": other}
    B = CP.Builder("C", packs, None, seed=1)
    cl = B.clean_composites(5)
    assert all(not c["label"].any() and set(c["parts"]) == set(CP.C_DOMAINS) for c in cl)
    at = B.domain_attacks("can", "x", 20)
    assert len(at) == 20
    for c in at:
        assert 0 <= c["onset"] < n // 2 and c["label"][c["onset"]] and not c["label"][:c["onset"]].any() and c["attacked"] == "can"
