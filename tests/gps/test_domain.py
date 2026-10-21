"""Tests for gps/domain.py and gps/b2.py (WP1 S8): save / load round trip, Evidence contract, B2 identical to the S1 tool version,
GPS MotionEstimate geometry. Uses KITTI drive 0001 OXTS (as tests/gps/test_stream.py), lidar=False (no ICP needed)."""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from common.evidence import Evidence
from common.motion import MotionEstimate
from gps import b2, domain, stack
from gps import stream as S

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))


def _runs(attacks=(None, None, "doppler_spoof", "jump")):
    ox = S.load_oxts("0001")
    g = S.resample_1hz(ox, 0.0)
    rng = np.random.default_rng(3)
    parts = []
    for i, a in enumerate(attacks):
        f = S.make_run(ox, g, rng, a, np.random.default_rng(10 + i))
        f["drive"], f["part"], f["run"] = "0001", "train", f"r{i}"
        parts.append(f)
    return pd.concat(parts, ignore_index=True)[S.COLUMNS]


def _config():
    import json
    tune = json.loads((Path(__file__).resolve().parent.parent.parent / "results" / "WP1" / "S3_tuning.json").read_text())
    return domain.default_config(tune, {"stat": "axis", "kappa": 1.5}, {"stat": "nis", "kappa": 2.0})


def test_b2_matches_tool_version():
    import WP1_S1_b2 as T
    df = _runs()
    a, b = b2.b2_features(df), T.b2_features(df)
    assert np.allclose(a.to_numpy(), b.to_numpy())
    d2 = df.join(a)
    assert np.allclose(b2.B2Layer().raw_scores(d2), T.B2Layer().raw_scores(d2))


def test_domain_round_trip_and_evidence_contract():
    df = domain.prepare(_runs(), lidar=False)
    cal, att = df[df["run"].isin(["r0", "r1"])], df[df["run"].isin(["r2", "r3"])]
    d = domain.GPSDomain(_config(), lidar=False).fit(cal)
    assert d.names == sorted(l.name for l in d.layers) and len(d.names) == 10
    S1, sc1, al1 = d.score_arrays(att)
    assert ((sc1 >= 0) & (sc1 <= 1)).all() and (al1 == (sc1 >= d.comb_threshold)).all()
    with tempfile.TemporaryDirectory() as tmp:
        d.save(tmp)
        d2 = domain.GPSDomain.load(tmp)
    S2, sc2, al2 = d2.score_arrays(att)
    assert np.allclose(S1, S2, atol=1e-12) and np.allclose(sc1, sc2, atol=1e-12) and (al1 == al2).all()
    ev = d2.score(att)
    assert len(ev) == len(att) and all(isinstance(e, Evidence) and e.domain == "gps" and e.layer == "combined" and e.name == "gps.combined" for e in ev)
    assert all((e.reason != "") == e.alarm for e in ev)
    assert np.allclose([e.score for e in ev], sc2, atol=1e-12)
    assert set(ev[0].details["layer_scores"]) == set(d2.names)
    # the attacked runs raise the statistic: a jump of >= 5 m is seen
    jump = att["run"].to_numpy() == "r3"
    assert al1[jump & (att["label"].to_numpy() == 1)].any()


def test_gps_motion_estimate_geometry():
    n = 20
    t = np.arange(n, dtype=float)
    hd = 90.0                                      # heading east (compass bearing), x east
    df = pd.DataFrame({"t": t, "x": 10.0 * t, "y": 2.0 * t * 0, "heading": hd})
    me = domain.gps_motion_estimates(df)
    assert len(me) == n - 1 and all(isinstance(m, MotionEstimate) and m.source == "gps" for m in me)
    assert abs(me[5].displacement[0] - 10.0) < 1e-9 and abs(me[5].displacement[1]) < 1e-9 and abs(me[5].speed - 10.0) < 1e-9
    df2 = df.assign(x=0.0, y=3.0 * t)               # moving north while the compass says east: the car's left is north
    me2 = domain.gps_motion_estimates(df2)
    assert abs(me2[0].displacement[0]) < 1e-9 and abs(me2[0].displacement[1] - 3.0) < 1e-9


def test_noisy_or_log_ranks_like_noisy_or_and_does_not_saturate():
    rng = np.random.default_rng(0)
    X = rng.random((200, 5)) * 0.9
    a, b = 1 - np.prod(1 - X, axis=1), stack.noisy_or_log(X)
    assert (np.argsort(a, kind="stable") == np.argsort(b, kind="stable")).all()
    big = np.full((3, 16), 1.0 - 1e-6)
    assert (1 - np.prod(1 - big, axis=1) == 1.0).all()          # the common.combiner formula ties at exactly 1.0 ...
    assert stack.noisy_or_log(big)[0] > stack.noisy_or_log(big[:, :8])[0]   # ... the log form still adds up
