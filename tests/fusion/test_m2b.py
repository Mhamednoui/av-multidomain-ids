"""Tests for WP6 S5b (M2 addendum, system config version 2): decided-majority event blame, SAFE_STOP corroboration, weighted budget split, per-layer LiDAR entries,
SystemV2 run on a toy drive, backward compatibility of the M2 pickle, the frozen system_v2 file and the S5b LiDAR pack."""
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from fusion.correlator import TemporalCorrelator, event_blame, respond  # noqa: E402
from fusion.system import DensityTransform, SystemFusion, SystemV2, entry_domain, entry_part, wsplit_score  # noqa: E402


def test_event_blame_rules():
    bc = {"gps": 1, "undecided": 4}
    assert event_blame(bc, 5, "plurality") == "gps"                 # M2: one decided tick decides
    assert event_blame(bc, 5, "majority_all") == "undecided"
    assert event_blame(bc, 5, "majority_decided") == "undecided"     # needs >= 2 decided ticks
    bc = {"gps": 2, "can": 1, "undecided": 3}
    assert event_blame(bc, 6, "majority_all") == "undecided" and event_blame(bc, 6, "majority_decided") == "gps"
    assert event_blame({"lidar": 4, "undecided": 1}, 5, "majority_all") == "lidar"
    assert event_blame({"undecided": 3}, 3, "majority_decided") == "undecided"


def test_safe_stop_needs_two_domains():
    bc = {"can": 40}
    assert respond(bc, "can", 40)[0] == "SAFE_STOP"                  # M2 rule (one domain, >= 30 s)
    assert respond(bc, "can", 40, n_domains=1, min_domains=2)[0] == "DEGRADE"
    assert respond(bc, "can", 40, n_domains=2, min_domains=2)[0] == "SAFE_STOP"
    assert respond({"gps": 3, "can": 3}, "gps", 5, n_domains=1, min_domains=2)[0] == "DEGRADE"


def test_correlator_defaults_reproduce_m2_and_old_pickles():
    c = TemporalCorrelator(2, 5, 15, True)
    assert c.rules() == ("plurality", 1)
    old = TemporalCorrelator(2, 5, 15, True)
    del old.blame_rule, old.safe_stop_min_domains                    # an M2-era object has no such attributes
    assert old.rules() == ("plurality", 1) and old.to_dict()["blame_rule"] == "plurality"
    a = np.zeros(60, bool)
    a[[3, 4, 5]] = True
    own = np.zeros((60, 2), bool)
    own[3:6, 0] = True
    bl = np.array(["undecided"] * 60, object)
    bl[3] = "can"
    ev = TemporalCorrelator(2, 5, 15, False, "majority_all", 2).events(a, own, ["can", "gps"], bl)
    assert len(ev) == 1 and ev[0].blamed == "undecided"
    ev = TemporalCorrelator(2, 5, 15, False).events(a, own, ["can", "gps"], bl)
    assert ev[0].blamed == "can"


def test_wsplit_equal_weights_is_max_and_shares():
    rng = np.random.default_rng(0)
    X = rng.uniform(size=(500, 3))
    assert np.allclose(wsplit_score(X, np.ones(3)), X.max(axis=1))
    s = wsplit_score(X, np.array([1.0, 0.5, 0.5]))
    t = 1 - 0.02                                                       # alarm <=> tail(1 - X_d) <= 0.02 w_d
    al = s >= t
    assert np.array_equal(al, ((1 - X[:, 0]) <= 0.02) | ((1 - X[:, 1]) <= 0.01) | ((1 - X[:, 2]) <= 0.01))


def toy_parts(n=40, seed=1):
    rng = np.random.default_rng(seed)
    p = {}
    for d in ("gps", "lidar", "can", "network", "v2x", "cross"):
        m = 4 if d == "lidar" else 2
        p[d] = {"score": rng.uniform(size=n).astype(np.float32), "count": np.ones(n, np.float32), "layers": rng.uniform(size=(n, m)).astype(np.float32),
                "dom_alarm": np.zeros(n, bool), "layer_alarm": np.zeros((n, m), bool), "blame": None}
    p["cross"]["blame"] = np.full(n, None, object)
    p["lidar"]["layer_alarm"][10:13, 2] = True
    p["lidar"]["layers"][10:13, 2] = 1.0
    return p


def test_entry_part_and_domain():
    p = toy_parts()
    v = entry_part(p, "lidar.L2c")
    assert np.array_equal(v["score"], p["lidar"]["layers"][:, 2]) and v["dom_alarm"][10:13].all() and entry_domain("lidar.L2c") == "lidar"
    assert entry_part(p, "gps") is p["gps"]


def _toy_system(entries, method="noisy_or"):
    rng = np.random.default_rng(3)
    fus = SystemFusion(entries, method)
    fus.fit_calibration({e: rng.uniform(size=500) for e in entries})
    fus.threshold = 0.9
    fus.weights = np.ones(len(entries)) if method == "wsplit" else None
    return SystemV2(entries, {e: DensityTransform(0.0) for e in entries}, fus, TemporalCorrelator(2, 5, 15, False, "majority_decided", 2))


def test_system_v2_runs_and_counts_lidar_layers_as_one_domain():
    ents = ["gps", "lidar.L1", "lidar.L2a", "lidar.L2c", "lidar.L2d", "can", "network", "v2x", "cross"]
    sysm = _toy_system(ents, "wsplit")
    assert sysm.domains == ["gps", "lidar", "can", "network", "v2x", "cross"] and sysm.config_version == 2
    p = toy_parts()
    p["lidar"]["layer_alarm"][10:13, 1] = True                         # two LiDAR layers alarm together: still ONE domain
    own, own_e = sysm.own_by_domain(p)
    assert own.shape == (40, 6) and own[10:13, 1].all() and own_e[10:13, [2, 3]].all() and own.sum() == 3
    o = sysm.run(p)
    assert o["alarm"].shape == (40,) and all(e.response != "SAFE_STOP" for e in o["events"])
    assert all(set(e.domains) <= set(sysm.domains) for e in o["events"])


def test_frozen_system_v2_file():
    p = ROOT / "results" / "WP6" / "system_v2.pkl"
    if not p.exists():
        print("skip: system v2 not frozen yet")
        return
    from fusion.system import load_system
    m = load_system(2)
    assert set(m) == {"K", "C"}
    for fam, s in m.items():
        assert s.config_version == 2 and s.correlator.rules()[1] == 2 and s.correlator.rules()[0] in ("majority_all", "majority_decided")
        assert s.fusion.threshold is not None and s.fusion.method in ("noisy_or", "max", "wsplit")
    assert "lidar" in m["K"].domains and m["C"].entries == ["can", "network", "v2x", "cross"]
    m1 = load_system(1)
    assert m1["K"].correlator.rules() == ("plurality", 1)               # the M2 system is unchanged


def test_s5b_lidar_pack():
    import WP6_S5b_lidar as LB
    f = LB.CACHE / "s5b_lidar.pkl"
    if not f.exists():
        print("skip: no S5b LiDAR pack")
        return
    P = pickle.load(open(f, "rb"))
    v = P["val"]
    assert {s["group"] for s in v["series"]} == set(LB.VAL) and {s["group"] for s in P["test"]["series"]} == set(LB.TEST)
    assert all(s["kind"] == "clean" for s in v["calib_series"]) and not ({s["group"] for s in v["calib_series"]} & (set(LB.VAL) | set(LB.TEST)))
    for s in v["series"][:20]:
        n = len(s["score"])
        assert s["layers"].shape == (n, 4) and s["layer_alarm"].shape == (n, 4) and len(s["dom_alarm"]) == n
        assert np.all(s["score"] >= 0) and np.all(s["score"] <= 1)
