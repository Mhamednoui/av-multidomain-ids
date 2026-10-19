"""Unit tests of the V2X L2 plausibility checks (v2x/l2.py) on synthetic message tables."""
import json

import numpy as np
import pandas as pd

from v2x import l2
from v2x.l1 import LIMITS


def track(name, t, x, y, speed, heading=0.0, acl=0.0, yaw=0.0):
    t = np.asarray(t, float)
    n = len(t)
    b = lambda v: np.broadcast_to(np.asarray(v, float), n).copy()
    h = b(heading)
    sp = b(speed)
    return pd.DataFrame({"track": name, "t": t, "x": b(x), "y": b(y), "speed": sp, "heading": h,
                         "vx": sp * np.cos(h), "vy": sp * np.sin(h), "acl": b(acl), "yaw_rate": b(yaw),
                         "sample_id": [f"{name}:{i}" for i in range(n)]})


def straight(name="a", n=10, v=10.0, dt=1.0, t0=0.0, x0=0.0, y0=0.0, h=0.0):
    t = t0 + np.arange(n) * dt
    return track(name, t, x0 + v * np.cos(h) * (t - t0), y0 + v * np.sin(h) * (t - t0), v, h)


def test_pos_speed_consistent_zero_and_constpos_residual():
    ok = straight()
    r = l2.PosSpeed().raw_scores(ok)
    assert r[0] == 0 and np.allclose(r, 0)
    stuck = track("s", np.arange(10) * 1.0, 100.0, 0.0, 10.0)           # claims 10 m/s but never moves
    r = l2.PosSpeed().raw_scores(stuck)
    assert r[0] == 0 and np.allclose(r[1:], 10.0)


def test_pos_speed_gap_longer_than_dt_max_not_evaluated():
    d = straight(n=3)
    d.loc[2, "t"] = 50.0
    assert l2.PosSpeed().raw_scores(d)[2] == 0.0


def test_pos_heading_gate_and_angle():
    ok = straight()
    assert np.allclose(l2.PosHeading().raw_scores(ok), 0)
    side = track("s", np.arange(6) * 1.0, 0.0, np.arange(6) * 10.0, 10.0, heading=0.0)   # moves north, claims east
    r = l2.PosHeading().raw_scores(side)
    assert np.allclose(r[1:], (np.pi / 2) * 10 / 12)
    slow = track("l", np.arange(6) * 1.0, 0.0, np.arange(6) * 1.0, 1.0, heading=0.0)      # below 3 m/s: heading undefined
    assert np.allclose(l2.PosHeading().raw_scores(slow), 0)


def test_speed_change_physical():
    v = np.array([10, 10, 10, 40, 40, 10.0])
    d = track("a", np.arange(6) * 1.0, np.cumsum(v), 0.0, v)
    lay = l2.SpeedChange()
    al = lay.physical_alarm(d)
    assert list(al) == [False, False, False, True, False, True]
    assert np.isclose(lay.raw_scores(d)[3], 30.0 / (1.0 * LIMITS["A_MAX"]))


def test_implied_speed_physical():
    x = np.array([0, 10, 20, 150, 160.0])
    d = track("a", np.arange(5) * 1.0, x, 0.0, 10.0)
    al = l2.ImpliedSpeed().physical_alarm(d)
    assert list(al) == [False, False, False, True, False]
    assert np.isclose(l2.ImpliedSpeed().raw_scores(d)[3], 130.0 / LIMITS["V_MAX"])


def test_heading_rate_physical_and_standing_gate():
    h = np.array([0, 0.05, 0.1, 1.9, 1.95])
    d = track("a", np.arange(5) * 1.0, 0.0, 0.0, 10.0, heading=h)      # 10 m/s -> limit 2 rad/s; 1.8 rad in 1 s is fine, 0.9 ok
    assert not l2.HeadingRate().physical_alarm(d).any()
    h2 = np.array([0, 0.05, 3.0, 3.05, 3.1])
    d2 = track("a", np.arange(5) * 1.0, 0.0, 0.0, 10.0, heading=h2)    # 2.95 rad/s > 2 rad/s
    assert list(l2.HeadingRate().physical_alarm(d2)) == [False, False, True, False, False]
    d3 = track("a", np.arange(5) * 1.0, 0.0, 0.0, 0.5, heading=h2)     # nearly standing: undefined heading, no alarm
    assert not l2.HeadingRate().physical_alarm(d3).any()


def test_accel_and_yaw_consistency():
    v = np.arange(6) * 2.0 + 5.0                                       # +2 m/s per s
    d = track("a", np.arange(6) * 1.0, np.cumsum(v), 0.0, v, acl=2.0)
    assert np.allclose(l2.AccelConsistency().raw_scores(d), 0)
    d["acl"] = -3.0
    assert np.allclose(l2.AccelConsistency().raw_scores(d)[1:], 5.0)
    h = np.arange(6) * 0.2                                             # 0.2 rad/s
    dy = track("a", np.arange(6) * 1.0, 0.0, 0.0, 10.0, heading=h, yaw=0.2)
    assert np.allclose(l2.YawConsistency().raw_scores(dy), 0)
    dy["yaw_rate"] = 0.0
    assert np.allclose(l2.YawConsistency().raw_scores(dy)[1:], 0.2)
    dn = dy.assign(yaw_rate=np.nan)
    assert not l2.YawConsistency().evaluable(dn) and l2.YawConsistency().evaluable(dy)


def test_overlap_same_space_adjacent_lane_and_dead_reckoning():
    a = straight("a", n=8, v=10.0)
    same = straight("b", n=8, v=10.0, t0=0.5)                           # same road, same speed, shifted 0.5 s: 5 m behind at equal time
    r = l2.overlap_depth(pd.concat([a, same], ignore_index=True))
    assert r.max() == 0                                                  # 5 m longitudinal gap > 4.5 m length
    close = straight("c", n=8, v=10.0, t0=0.0, x0=-3.0)                  # 3 m behind: overlaps in length
    r = l2.overlap_depth(pd.concat([a, close], ignore_index=True))
    assert r[len(a):].max() > 0 or r[:len(a)].max() > 0
    lane = straight("d", n=8, v=10.0, y0=3.5)                            # next lane, 3.5 m: no overlap
    assert l2.overlap_depth(pd.concat([a, lane], ignore_index=True)).max() == 0
    # dead reckoning: b's last message is 0.6 s old and 6 m behind a's current position -> reaches a at t=0.6
    a2 = track("a", [1.0], [10.0], [0.0], 10.0)
    b2 = track("b", [0.4], [0.0], [0.0], 10.0)                           # at t=1.0 it is at x=6: 4 m behind a -> overlap in length
    r = l2.overlap_depth(pd.concat([b2, a2], ignore_index=True))
    assert r[1] > 0


def test_overlap_same_track_never_overlaps_itself_and_old_messages_ignored():
    a = straight("a", n=10, v=0.0, dt=0.1)                              # parked, many messages at the same place
    assert l2.overlap_depth(a).max() == 0
    old = track("o", [0.0], [0.0], [0.0], 0.0)
    new = track("n", [5.0], [0.0], [0.0], 0.0)                          # 5 s later: the old vehicle may have left
    assert l2.overlap_depth(pd.concat([old, new], ignore_index=True)).max() == 0


def test_overlap_only_within_the_same_receiver():
    a = straight("a", n=8, v=10.0)
    b = straight("b", n=8, v=10.0)                                       # identical positions: one vehicle heard by two receivers
    both = pd.concat([a.assign(rx_id="r1"), b.assign(rx_id="r2")], ignore_index=True)
    assert l2.overlap_depth(both).max() == 0
    same = pd.concat([a.assign(rx_id="r1"), b.assign(rx_id="r1")], ignore_index=True)
    assert l2.overlap_depth(same).max() > 0.9


def test_overlap_is_causal():
    parts = [straight("a", n=20, v=10.0), straight("b", n=20, v=10.0, x0=-2.0, y0=0.5)]
    df = pd.concat(parts, ignore_index=True)
    full = l2.overlap_depth(df)
    keep = df["t"] <= 9.0
    part = l2.overlap_depth(df[keep])
    assert np.allclose(full[keep.to_numpy()], part)


def test_pair_checks_are_causal_and_row_order_independent():
    rng = np.random.RandomState(0)
    d = straight("a", n=30)
    d["x"] = d["x"] + rng.normal(0, 4, len(d))
    for lay in (l2.PosSpeed(), l2.PosHeading(), l2.SpeedChange(), l2.ImpliedSpeed(), l2.HeadingRate(), l2.AccelConsistency()):
        full = lay.raw_scores(d)
        assert np.allclose(full[:15], lay.raw_scores(d.iloc[:15]))
        shuf = d.sample(frac=1.0, random_state=3)
        assert np.allclose(lay.raw_scores(shuf), full[shuf.index])


def test_map_road_distance():
    # one way along y = 0 from x = 0 to 100 m (lat0, lon0 local origin)
    lat0, lon0 = 27.95, -82.45
    m = 111320.0
    lon1 = lon0 + 100.0 / (m * np.cos(np.radians(lat0)))
    js = {"elements": [{"type": "node", "id": 1, "lat": lat0, "lon": lon0}, {"type": "node", "id": 2, "lat": lat0, "lon": lon1},
                       {"type": "way", "id": 9, "nodes": [1, 2], "tags": {"highway": "residential"}}]}
    import tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "osm.json"
    p.write_text(json.dumps(js))
    tree = l2.build_road_tree(p, lat0, lon0)
    lay = l2.MapRoad(tree)
    d = track("a", np.arange(4) * 1.0, [10, 50, 50, 200], [0.0, 5.0, 40.0, 0.0], 10.0)
    r = lay.raw_scores(d)
    assert r[0] < 0.6 and abs(r[1] - 5.0) < 0.6 and abs(r[2] - 40.0) < 0.6 and abs(r[3] - 100.0) < 0.6
    assert lay.evaluable(d) and not l2.MapRoad().evaluable(d)
    assert (l2.MapRoad().raw_scores(d) == 0).all()


def test_calibrate_masked_uses_genuine_rows_only():
    gen = [straight(f"g{i}", n=100, t0=i * 0.37) for i in range(30)]
    rng = np.random.RandomState(1)
    for g in gen:
        g["x"] = g["x"] + rng.normal(0, 3, len(g))
    att = track("z", np.arange(100) * 1.0, 0.0, 0.0, 30.0)
    frame = pd.concat(gen + [att], ignore_index=True)
    mask = ~frame["track"].eq("z").to_numpy()
    lay = l2.PosSpeed().calibrate_masked(frame, mask, 0.01)
    al = np.array([e.alarm for e in lay.score(frame)])
    assert al[mask].mean() <= 0.01 and al[~mask][1:].mean() > 0.9
    ev = [e for e in lay.score(frame) if e.alarm][0]
    assert ev.domain == "v2x" and ev.layer == "L2" and ev.name == "v2x.pos_speed" and ev.reason


def test_make_layers_contract():
    names = [l.name for l in l2.make_layers()]
    assert names == ["v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate",
                     "v2x.accel_consistency", "v2x.yaw_consistency", "v2x.overlap", "v2x.map_road"]
    for l in l2.make_layers():
        assert l.domain == "v2x" and l.layer_id == "L2" and l.kind == "physics" and not l.needs_attack_data
        l.reset()
