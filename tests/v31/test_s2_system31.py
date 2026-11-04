"""WP8 S2: unit tests of fusion/system31.py (tick_blame31, Correlator31, SystemV31) and the equivalence with the frozen v3 system on the S6 fixture."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import numpy as np  # noqa: E402

from fusion import correlator as CR  # noqa: E402
from fusion.system31 import Correlator31, SystemV31, tick_blame31  # noqa: E402


def test_tick_blame31_no_unrelated_fallback():
    names = ["gps", "v2x", "cross"]
    X = np.array([[0.9, 0.95, 0.99], [0.9, 0.95, 0.99], [0.2, 0.3, 0.1], [0.5, 0.97, 0.2]])
    own = np.array([[False, True, True], [False, True, True], [False, False, False], [False, True, False]])
    cb = np.array(["gps", "undecided", None, None], object)
    ca = np.array([True, True, False, False])
    b = tick_blame31(names, X, own, cb, ca)
    assert list(b) == ["gps", "undecided", "undecided", "v2x"]
    v3 = CR.tick_blame(names, X, own, cb, ca)
    assert list(v3) == ["gps", "v2x", "v2x", "v2x"]          # v3 falls back onto the unrelated V2X alarm and onto the strongest non-alarming entry


def test_correlator31_default_equals_v3_correlator():
    rng = np.random.default_rng(3)
    names = ["gps", "can", "cross"]
    for _ in range(30):
        n = 200
        alarm = rng.random(n) < 0.08
        own = rng.random((n, 3)) < 0.05
        blame = rng.choice(np.array(["gps", "can", "undecided"], object), n)
        v3 = CR.TemporalCorrelator(m=2, w=5, gap=15, blame_rule="majority_decided", safe_stop_min_domains=2).events(alarm, own, names, blame)
        v31 = Correlator31().events(alarm, own, names, blame)
        assert [(e.start, e.end, e.blamed, e.response, e.domains) for e in v3] == [(e.start, e.end, e.blamed, e.response, e.domains) for e in v31]


def test_dedup_and_k_lower_safe_stop():
    names = ["gps", "can", "cross"]
    n = 60
    alarm = np.zeros(n, bool)
    alarm[5:45] = True
    own = np.zeros((n, 3), bool)
    own[5:45, 0] = True          # gps
    own[5:45, 2] = True          # cross (same evidence as the gps alarm)
    own[20, 1] = True            # one coincidental CAN tick
    blame = np.full(n, "gps", object)
    lv = lambda c: c.events(alarm, own, names, blame)[0].response
    assert lv(Correlator31()) == "SAFE_STOP"                          # v3 rule: 3 domains with own alarms
    assert lv(Correlator31(dedup=True)) == "SAFE_STOP"                # gps + can still 2 domains
    assert lv(Correlator31(dedup=True, k_corr=3)) == "DEGRADE"        # the single CAN tick does not corroborate, cross = gps


def test_systemv31_reproduces_systemv2_on_fixture():
    import WP8_S6_fixture as F
    from fusion.system import load_system
    sysd = load_system(2)
    for fam in ("K", "C"):
        s2 = sysd[fam]
        parts = F.synthetic_parts(s2.entries, seed=7 if fam == "K" else 8)
        ref = s2.run(parts, explain=True)
        s31 = SystemV31(s2.entries, method=s2.fusion.method, blame="v3", correlator=Correlator31(m=2, w=5, gap=15))
        s31.cal = {e: s2.fusion.cal[e] for e in s2.entries}
        s31.density = s2.density
        s31.threshold = s2.fusion.threshold
        out = s31.run(parts)
        assert np.array_equal(out["alarm"], ref["alarm"]) and np.abs(out["score"] - ref["score"]).max() <= 1e-12
        assert list(out["blame"]) == list(ref["blame"])
        assert [(e.start, e.end, e.blamed, e.response) for e in out["events"]] == [(e.start, e.end, e.blamed, e.response) for e in ref["events"]]


def test_wsplit_equal_weights_is_max():
    X = np.random.default_rng(1).random((50, 4))
    s = SystemV31(["a", "b", "c", "d"], method="wsplit", weights={k: 1.0 for k in "abcd"}).combine(X)
    assert np.allclose(s, X.max(axis=1))
