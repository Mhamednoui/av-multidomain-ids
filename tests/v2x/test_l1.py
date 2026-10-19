"""Unit tests of the V2X L1 message checks (v2x/l1.py) on synthetic message tables."""
import numpy as np
import pandas as pd

from v2x import l1


def table(tracks):
    """tracks: dict name -> dict(t=array, x=, y=, speed=, acl=, yaw=, age=); returns a message table."""
    rows = []
    for name, d in tracks.items():
        t = np.asarray(d["t"], float)
        n = len(t)
        rows.append(pd.DataFrame({
            "track": name, "t": t,
            "x": d.get("x", np.zeros(n)), "y": d.get("y", np.zeros(n)),
            "speed": d.get("speed", np.full(n, 10.0)), "acl": d.get("acl", np.zeros(n)),
            "yaw_rate": d.get("yaw", np.zeros(n)), "rx_x": np.nan, "rx_y": np.nan,
            "sample_id": [f"{name}:{i}" for i in range(n)]}))
    return pd.concat(rows, ignore_index=True)


def test_rate_proportional_and_first_message_zero():
    df = table({"a": dict(t=np.arange(10) * 1.0), "b": dict(t=np.arange(20) * 0.5 + 100)})
    r = l1.BeaconRate().raw_scores(df)
    a, b = r[:10], r[10:]
    assert a[0] == 0 and b[0] == 0
    assert np.allclose(a[1:], 1.0 / l1.LIMITS["RATE_MAX_HZ"])
    assert np.allclose(b[1:], 2.0 / l1.LIMITS["RATE_MAX_HZ"])


def test_rate_is_causal_and_order_independent():
    t = np.cumsum(np.r_[0.0, np.random.RandomState(0).uniform(0.05, 1.2, 40)])
    df = table({"a": dict(t=t), "b": dict(t=t + 3.1)})
    full = l1.BeaconRate().raw_scores(df)
    prefix = df[df.t <= t[20] + 0.0].copy()
    part = l1.BeaconRate().raw_scores(prefix)
    assert np.allclose(full[prefix.index], part)                   # later messages do not change earlier scores
    shuf = df.sample(frac=1.0, random_state=1)
    assert np.allclose(l1.BeaconRate().raw_scores(shuf), full[shuf.index])   # row order irrelevant for rate


def test_rate_alarm_after_calibration_on_genuine_only():
    gen = table({f"g{i}": dict(t=np.arange(100) * 1.0 + i * 0.37) for i in range(30)})
    lay = l1.BeaconRate().calibrate(gen, budget=0.01)
    dos = table({"d": dict(t=np.arange(100) * 0.5)})
    fa = np.mean([e.alarm for e in lay.score(gen)])
    det = np.mean([e.alarm for e in lay.score(dos)][1:])
    assert fa <= 0.01 and det == 1.0
    ev = lay.score(dos)[5]
    assert ev.domain == "v2x" and ev.layer == "L1" and ev.name == "v2x.beacon_rate" and ev.reason and 0 <= ev.score <= 1


def test_rate_physical_alarm_standard_limit():
    df = table({"a": dict(t=np.arange(30) * 0.1), "b": dict(t=np.arange(30) * 0.04)})
    al = l1.BeaconRate().physical_alarm(df)
    assert not al[:30].any() and al[31:].all()      # 10 Hz ok, 25 Hz above the J2945/1 maximum


def test_freshness_age_future_and_ordering():
    n = 6
    age = np.array([-0.5, -0.2, 0.3, 45.0, -3.0, 0.1])
    df = table({"a": dict(t=np.arange(n) * 1.0, age=age)})
    df["age_s"] = age
    lay = l1.Freshness()
    r = lay.raw_scores(df)
    assert r[3] == 45.0 and np.isclose(r[4], 2.0) and r[0] == 0 and r[1] == 0 and r[2] == 0.3
    assert lay.evaluable(df)
    no_age = df.drop(columns="age_s")
    assert not lay.evaluable(no_age)
    back = table({"a": dict(t=[10.0, 11.0, 12.0, 9.0, 13.0, 13.0])})      # arrival order = row order
    rb = lay.raw_scores(back)
    assert np.isclose(rb[3], 3.0) and rb[4] == 0 and rb[5] == l1.LIMITS["TIME_RES_S"] and rb[:3].sum() == 0


def test_freshness_calibrated_alarm_on_stale_replay():
    rng = np.random.RandomState(0)
    gen = table({f"g{i}": dict(t=np.arange(200) * 0.1) for i in range(5)})
    gen["age_s"] = rng.uniform(-1.0, 0.0, len(gen))
    stale = table({"s": dict(t=np.arange(50) * 0.1)})
    stale["age_s"] = rng.uniform(10, 60, len(stale))
    lay = l1.Freshness().calibrate(gen, budget=0.01)
    assert np.mean([e.alarm for e in lay.score(gen)]) <= 0.01
    assert np.mean([e.alarm for e in lay.score(stale)]) == 1.0


def test_ranges_physical_limits():
    df = table({"a": dict(t=np.arange(6) * 1.0,
                          speed=np.array([20.0, 80.0, 20.0, 20.0, 1.0, 20.0]),
                          acl=np.array([0.0, 0.0, 15.0, 5.0, 0.0, 0.0]),
                          yaw=np.array([0.1, 0.0, 0.0, 0.0, 6.0, 5.0]))})
    lay = l1.FieldRanges()
    al = lay.physical_alarm(df)
    # 20 m/s: yaw limit 20/5 = 4 rad/s -> 5 rad/s violates; 1 m/s (< 3 m/s): cap 5.72 rad/s -> 6.0 violates
    assert list(al) == [False, True, True, False, True, True]
    assert np.isclose(lay.raw_scores(df)[1], 80 / 70.0)


def test_ranges_nan_fields_are_not_violations():
    df = table({"a": dict(t=np.arange(3) * 1.0)})
    df["acl"] = np.nan
    df["yaw_rate"] = np.nan
    assert not l1.FieldRanges().physical_alarm(df).any()


def test_sudden_appearance_synthetic():
    # receiver at (0, 0). track "near": first heard 50 m away; "edge": first heard 290 m; "far": 400 m.
    # "later": the same track already seen far away, then close (not its first message: no alarm).
    d = {"near": dict(t=[0, 1], x=[50, 52]), "edge": dict(t=[0, 1], x=[290, 289]),
         "far": dict(t=[0, 1], x=[400, 380]), "later": dict(t=[0, 1, 2], x=[350, 100, 60])}
    df = table(d)
    df["rx_x"], df["rx_y"] = 0.0, 0.0
    lay = l1.SuddenAppearance()
    assert lay.evaluable(df)
    r = lay.raw_scores(df)
    byk = df.assign(r=r).groupby("track")["r"].apply(list).to_dict()
    assert np.isclose(byk["near"][0], 1 - 50 / 300.0) and byk["near"][1] == 0
    assert np.isclose(byk["edge"][0], 1 - 290 / 300.0)
    assert byk["far"] == [0.0, 0.0]
    assert byk["later"] == [0.0, 0.0, 0.0]
    # calibrated on genuine vehicles that all enter at the edge (> 250 m), a close first message alarms
    gen = table({f"g{i}": dict(t=[0, 1, 2], x=[250 + i, 240, 200]) for i in range(60)})
    gen["rx_x"], gen["rx_y"] = 0.0, 0.0
    lay.calibrate(gen, budget=0.01)
    al = {e.sample_id: e.alarm for e in lay.score(df)}
    assert al["near:0"] and not al["far:0"] and not al["later:2"] and not al["near:1"]


def test_sudden_appearance_not_evaluable_without_receiver():
    df = table({"a": dict(t=[0, 1])})
    lay = l1.SuddenAppearance()
    assert not lay.evaluable(df)
    assert (lay.raw_scores(df) == 0).all()


def test_make_layers_contract():
    names = [l.name for l in l1.make_layers()]
    assert names == ["v2x.beacon_rate", "v2x.freshness", "v2x.field_ranges", "v2x.sudden_appearance"]
    for l in l1.make_layers():
        assert l.domain == "v2x" and l.layer_id == "L1" and l.kind == "rule" and not l.needs_attack_data
        l.reset()
