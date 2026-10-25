"""WP7 S2: FusionRunner (system/fusion_runner.py) over the frozen system v2: the streaming state equals SystemV2.run on the same per-domain tick arrays, with and without a late
domain (network Evidence arriving minutes after its tick), a late domain can only raise alarms late (never retract), and the timeline records when events and responses became visible."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from fusion.system import load_system
from system.fusion_runner import FusionRunner, replay

SYS = Path(__file__).resolve().parent.parent.parent / "results" / "WP6" / "system_v2.pkl"


class Skip(Exception):
    pass


_SYSTEMS = {}


def systems():
    if not SYS.exists():
        raise Skip("frozen system v2 pickle (git-ignored) not present")
    if not _SYSTEMS:
        _SYSTEMS.update(load_system(2))
    return _SYSTEMS


WIDTH = {"gps": 16, "lidar": 4, "can": 3, "network": 5, "v2x": 12, "cross": 7}


def composite(sysm, n, rng, spike_at=()):
    parts, avail = {}, {}
    for d in sysm.domains:
        w = WIDTH[d]
        sc = rng.beta(1, 8, n).astype(np.float32)
        lay = rng.random((n, w)).astype(np.float32) * 0.5
        p = {"score": sc, "count": np.ones(n, np.float32), "layers": lay, "dom_alarm": sc > 0.95, "layer_alarm": lay > 0.45, "present": np.ones(n, bool),
             "blame": np.full(n, None, object)}
        if d == "cross":
            p["blame"][sc > 0.9] = "gps"
        for k in (spike_at if d in ("gps", "cross", "can") else ()):
            p["score"][k] = 1.0
            p["dom_alarm"][k] = True
        parts[d] = p
        avail[d] = np.arange(n) + 1.0
    return parts, avail


def run_batch(sysm, parts):
    return sysm.run({d: {k: v for k, v in p.items() if k != "present"} for d, p in parts.items()}, explain=True)


def same_events(a, b):
    return len(a) == len(b) and all((x.start, x.first_alarm, x.end, x.blamed, x.response, x.domains, x.explanation) == (y.start, y.first_alarm, y.end, y.blamed, y.response, y.domains, y.explanation)
                                     for x, y in zip(a, b))


def test_stream_equals_batch():
    S = systems()
    for fam in ("K", "C"):
        sysm = S[fam]
        rng = np.random.default_rng(1)
        parts, avail = composite(sysm, 90, rng, spike_at=(10, 11, 12, 40, 41))
        fr = replay(sysm, parts, avail, 90)
        ref = run_batch(sysm, parts)
        fin = fr.final()
        assert (fin["alarm"] == ref["alarm"]).all() and np.allclose(fin["score"], ref["score"])
        assert same_events(fin["events"], ref["events"])


def test_late_domain_raises_alarms_late_and_matches_batch():
    S = systems()
    sysm = S["K"]
    n = 120
    rng = np.random.default_rng(2)
    parts, avail = composite(sysm, n, rng)
    # network evidence of ticks 20..79 only arrives at second 100; a strong network value makes those ticks alarm
    parts["network"]["score"][20:80] = 1.0
    parts["network"]["dom_alarm"][20:80] = True
    for d in ("gps", "cross"):
        parts[d]["score"][20:80] = 1.0
    avail["network"] = np.where((np.arange(n) >= 20) & (np.arange(n) < 80), 100.0, np.arange(n) + 1.0)
    fr = replay(sysm, parts, avail, n)
    ref = run_batch(sysm, parts)
    assert (fr.final()["alarm"] == ref["alarm"]).all()
    early = replay(sysm, {**parts, "network": {**parts["network"], "present": np.arange(n) >= 80}}, avail, n)
    late_alarm = np.flatnonzero(fr.alarm[20:80]) + 20
    assert len(late_alarm) > 40
    assert (fr.first_known[late_alarm] >= 100).sum() >= len(late_alarm) - early.alarm[20:80].sum()
    assert np.all(fr.alarm[early.alarm])                                # a late domain never retracts an alarm


def test_timeline_and_visible_time():
    S = systems()
    sysm = S["K"]
    n = 60
    rng = np.random.default_rng(3)
    parts, avail = composite(sysm, n, rng)
    for k in (30, 31, 32, 33):
        for d in ("gps", "cross", "can"):
            parts[d]["score"][k] = 1.0
            parts[d]["dom_alarm"][k] = True
    parts["gps"]["layer_alarm"][30:34] = True
    fr = replay(sysm, parts, avail, n)
    ev = fr.final()["events"]
    assert ev, "an event must exist"
    e = ev[0]
    t = fr.visible_time(e.start, e.end, "WARN")
    assert t is not None and t >= e.start + 1
    assert fr.first_known[30] == 31.0
    assert fr.visible_time(e.start, e.end, "SAFE_STOP") is None or fr.visible_time(e.start, e.end, "SAFE_STOP") >= t


def test_no_tracking_gives_same_final_state():
    S = systems()
    sysm = S["C"]
    rng = np.random.default_rng(4)
    parts, avail = composite(sysm, 70, rng, spike_at=(5, 6, 7))
    a = replay(sysm, parts, avail, 70, track_events=True).final()
    b = replay(sysm, parts, avail, 70, track_events=False).final()
    assert (a["alarm"] == b["alarm"]).all() and same_events(a["events"], b["events"])
