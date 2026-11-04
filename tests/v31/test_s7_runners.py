"""WP8 S7 step 0 tests: the v3.1 runner wrappers (system/runners31.py) equal the batch code. Synthetic inputs and V31_val material only (never H31):
CAN (frame by frame vs CanDomain.score_capture), V2X (EgoStream wrapper vs V2XPhysicsDomain batch Evidence), network F1 (push/flush vs score_table) and RC5 (push vs score_table),
blame A1 (Blame31Stream vs blame_run), fusion (Fusion31Runner replay vs SystemV31.run on synthetic composites with the frozen system), LiDAR (wrapper vs Domain31 stream on V31_val drive 0011)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "network"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from can.domain import CanDomain
from crossdomain import blame31 as B31
from fusion.system31 import load_system31
from network import l2a  # noqa: E402,F401
from network.stream31 import Stream31, Stream31Final
from system.runners31 import Blame31Stream, CanRunner31, Fusion31Runner, NetRunner31, V2XRunner31
from system.v2x_runner import LAYER_NAMES, V2XPhysicsDomain
from test_domain import _fitted, _flows  # noqa: E402
from test_s5_incremental import FROZEN, _can_frames, _traffic
from v2x import l3


def test_can_runner_equals_batch():
    dom = CanDomain.load(FROZEN)
    t, ids, dlc, B = _can_frames(seed=11, secs=8)
    comb, per = dom.score_capture(t, ids, dlc, B, name="c", explain=True)
    r = CanRunner31(dom)
    r.reset("c")
    out = []
    for k in range(len(t)):
        out.extend(r.push((t[k], ids[k], dlc[k], B[k])))
    out.extend(r.flush())
    combs = [e for e in out if e.layer == "combined"]
    assert len(combs) == len(comb) > 0
    for a, b in zip(combs, comb):
        assert a.sample_id == b.sample_id and a.score == b.score and a.alarm == b.alarm and a.reason == b.reason
    assert len(out) == len(comb) * (1 + len(dom.layers))
    assert len(r.latency.ns) == len(t)


def test_v2x_runner_equals_batch():
    d = _traffic(seed=3, clock_offsets=False).sort_values("t", kind="stable").reset_index(drop=True)
    dom = V2XPhysicsDomain(l3.Tracker())
    dom.fit(d.assign(label=0))
    ref = dom.score_table(d, per_layer=False)
    r = V2XRunner31(dom)
    r.reset("ego")
    got = []
    for s in d.to_dict("records"):
        got.extend(r.push(s))
    assert len(got) == len(ref)
    for a, b in zip(got, ref):
        assert a.sample_id == b.sample_id and a.score == b.score and a.alarm == b.alarm and a.reason == b.reason


def test_net_runner_f1_and_rc5_equal_batch():
    D, rng = _fitted(7)
    va = D.prepare(_flows(rng, range(1700, 1740)))
    st = D.prepare(_flows(rng, range(1800, 1830), scan=True))
    st["t"] = st["t"].astype(float)
    cols = ["ts", "src_ip", "dst_ip", "dst_port", "protocol"] + [c for c in st.columns if c.startswith(("Tot", "Flow", "FIN", "SYN", "RST", "PSH", "ACK", "URG", "ECE"))]
    recs = st[cols].to_dict("records")
    F = Stream31Final.from_frozen(D)
    F.calibrate(va)
    s_b, a_b, _, _ = F.score_table(st)
    r = NetRunner31(F, variant="F1")
    r.reset("n")
    got = {}
    for x in recs:
        for e in r.push(x):
            got[int(e.sample_id)] = e
    for e in r.flush():
        got[int(e.sample_id)] = e
    assert sorted(got) == list(range(len(recs)))
    assert max(abs(got[i].score - s_b[i]) for i in range(len(recs))) <= 1e-12 and all(got[i].alarm == bool(a_b[i]) for i in range(len(recs)))
    R = Stream31.from_frozen(D, carry=True)
    R.calibrate(va)
    s_r, a_r, _, _ = R.score_table(st)
    rr = NetRunner31(R, variant="RC5")
    rr.reset("n")
    ev = []
    for x in recs:
        ev.extend(rr.push(x))
    assert len(ev) == len(recs) and max(abs(e.score - s) for e, s in zip(ev, s_r)) <= 1e-12 and [e.alarm for e in ev] == list(a_r)


def test_blame_stream_equals_blame_run():
    for graph, E in (("K", len(B31.K_EDGES)), ("C", len(B31.C_EDGES))):
        _blame_case(graph, E)


def _blame_case(graph, E):
    blamer = B31.selected_blamers()[graph]
    rng = np.random.default_rng(5)
    n = 300
    al = rng.random((n, E)) < 0.08
    al[100:140, 1] = True
    al[100:140, 0] = True
    ob = rng.random((n, E)) < 0.9
    al &= ob
    ca = al.any(axis=1)
    ref = B31.blame_run(blamer, al, ob, ca)
    s = Blame31Stream(blamer)
    got = [s.push(al[i], ob[i], ca[i]) for i in range(n)]
    assert [None if x is None else str(x) for x in got] == [None if x is None else str(x) for x in ref]


def _synthetic_parts(entries, seed, n):
    rng = np.random.default_rng(seed)
    parts = {}
    for e in entries:
        sc = rng.random(n) ** 3
        sc[150:180] = 0.9995 if e == entries[seed % len(entries)] else sc[150:180]
        p = {"score": sc, "count": rng.integers(1, 5, n).astype(float), "dom_alarm": sc > 0.97, "layers": np.zeros((n, 1)), "layer_alarm": np.zeros((n, 1), bool)}
        if e == "cross":
            p["blame"] = np.where(sc > 0.97, rng.choice(["gps", "can", "undecided"], n), None).astype(object)
        parts[e] = p
    return parts


def test_fusion_runner_equals_system_run():
    for fam in ("K", "C"):
        _fusion_case(fam)


def _fusion_case(fam):
    sysm = load_system31()[fam]
    n = 400
    for seed in range(3):
        parts = _synthetic_parts(sysm.entries, seed, n)
        ref = sysm.run(parts)
        runner = Fusion31Runner(sysm, track_events=True)
        runner.reset(n)
        delay = {d: (60 if d == "network" else 0) for d in sysm.entries}
        buckets = {}
        for d in sysm.entries:
            for k in range(n):
                buckets.setdefault(k + 1 + delay[d], []).append((d, k))
        for T in range(1, max(buckets) + 1):
            for d, k in buckets.get(T, ()):
                p = parts[d]
                runner.T = T
                runner.submit(d, k, p["score"][k], p["count"][k], np.zeros(1), p["dom_alarm"][k], None, None if p.get("blame") is None else p["blame"][k])
            runner.step(T)
        out = runner.final()
        assert len(out["score"]) == n
        assert np.array_equal(out["alarm"], ref["alarm"]) and np.allclose(out["score"], ref["score"], atol=1e-12)
        assert [(e.start, e.end, e.response, e.blamed) for e in out["events"]] == [(e.start, e.end, e.response, e.blamed) for e in ref["events"]]


def test_lidar_runner_equals_domain_stream():
    from lidar import data as lid
    f = ROOT / "results" / "WP8" / "S3" / "frozen_lidar31" / "domain31.pkl"
    if not f.exists():
        return
    sys.path.insert(0, str(ROOT / "tools"))
    import WP8_lib as L8
    from lidar import ego
    from lidar.domain31 import Domain31
    from system.runners31 import LidarRunner31
    L8.assert_not_h31(["0011"])
    files = lid.scan_files("0011")[:4]
    pose = ego.poses("0011")[:4]
    dom = Domain31.load(f.parent)
    r = LidarRunner31(dom)
    r.reset("0011")
    st = dom.stream()
    for i, fp in enumerate(files):
        pts = lid.load(fp)
        got = r.push({"points": pts, "pose": pose[i], "t": 0.1 * i, "sample_id": i})
        comb, per = st.push(pts, pose[i], 0.1 * i, i)
        assert got[0].score == comb.score and got[0].alarm == comb.alarm and got[0].details["layer_raw"] == comb.details["layer_raw"]
        assert [e.score for e in got[1:]] == [per[l].score for l in ("L1", "L2a", "L2c", "L2d")]
