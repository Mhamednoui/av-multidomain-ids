"""Tests for system/v2x_runner.py (WP7 S1): the streaming runner (bounded context per message) equals the batch physics-only domain on the whole table; truncation;
reset; equal-timestamp counter; save / load. Synthetic highway traffic (one lane, 1 Hz beacons, GPS noise), one attacker with a position jump, one with a speed lie,
and a sybil burst of fresh identities; no data files."""
import tempfile

import numpy as np
import pandas as pd

from system.runner import compare_sequences
from system.v2x_runner import LAYER_NAMES, V2XPhysicsDomain, V2XRunner
from v2x import l3
from v2x.schema import COLUMNS


def _traffic(seed, n_veh=10, T=45, attack=False):
    rng = np.random.default_rng(seed)
    rows = []
    mid = 0
    for v in range(n_veh):
        t0 = 3.0 * v + rng.uniform(0, 0.9)
        x0, y0, sp = 40.0 * v, 3.5 * (v % 3), 12.0 + rng.uniform(0, 4)
        for k in range(T):
            t = t0 + k + rng.normal(0, 0.003)
            x = x0 + sp * k + rng.normal(0, 0.6)
            y = y0 + rng.normal(0, 0.6)
            lab = 0
            if attack and v == n_veh - 1 and k >= T // 2:
                x += 400.0
                lab = 3
            spd = sp + rng.normal(0, 0.05) + (25.0 if (attack and v == n_veh - 2 and k >= T // 2) else 0.0)
            lab = 7 if (attack and v == n_veh - 2 and k >= T // 2) else lab
            rows.append((f"m{mid}", f"s{v}", f"s{v}/0", t, x, y, spd, lab))
            mid += 1
    if attack:                                              # sybil burst: a fresh identity per message near the road
        for j in range(15):
            t = 20.0 + 0.31 * j + 0.0007 * j
            rows.append((f"m{mid}", f"g{j}", f"g{j}/0", t, 150.0 + 3 * j + rng.normal(0, 1), 8.0, 13.0, 18))
            mid += 1
    d = pd.DataFrame(rows, columns=["msg_id", "sender", "track", "t", "x", "y", "speed", "label"])
    d["pseudo"] = "0"
    d["source"] = "synthetic"
    d["vx"], d["vy"], d["heading"] = d["speed"], 0.0, 0.0
    d["acl"], d["yaw_rate"] = 0.0, np.nan
    d["rx_id"] = None
    for c in COLUMNS:
        if c not in d.columns:
            d[c] = np.nan
    return d.sort_values("t", kind="stable").reset_index(drop=True)


def _domain():
    val = _traffic(1)
    return V2XPhysicsDomain(l3.Tracker(l3.KalmanParams())).fit(val)


def _recs(df):
    return df.to_dict("records")


def test_stream_equals_batch_on_whole_table_with_attacks():
    dom = _domain()
    assert set(dom.thr) == set(LAYER_NAMES) and 0 < dom.comb_thr <= 1
    df = _traffic(2, attack=True)
    batch = dom.score_table(df, per_layer=True)
    run = V2XRunner(dom, per_layer=True)
    out = run.run(_recs(df), key="blk")
    assert len(out) == 13 * len(df)
    c = compare_sequences(out, batch, tol=1e-12)
    assert c["identical"], c
    comb = [e for e in out if e.layer == "combined"]
    assert any(e.alarm for e in comb) and not all(e.alarm for e in comb)
    assert all((e.reason != "") == e.alarm for e in comb)
    assert run.tie_events == 0 and run.out_of_order == 0
    lab = df["label"].to_numpy()
    assert np.mean([e.alarm for e, l in zip(comb, lab) if l > 0]) > np.mean([e.alarm for e, l in zip(comb, lab) if l == 0])


def test_truncation_and_reset():
    dom = _domain()
    df = _traffic(3, attack=True)
    full = V2XRunner(dom).run(_recs(df), key="a")
    for k in (30, 150, 300):
        part = V2XRunner(dom).run(_recs(df.iloc[:k]), key="a")
        assert compare_sequences(part, full[:k], tol=0.0)["identical"]
        assert compare_sequences(dom.score_table(df.iloc[:k].reset_index(drop=True)), full[:k], tol=1e-12)["identical"]   # frozen batch code is causal
    r = V2XRunner(dom)
    r.run(_recs(_traffic(4, attack=True)), key="other")
    again = r.run(_recs(df), key="a")
    assert compare_sequences(again, full, tol=0.0)["identical"]


def test_equal_timestamps_counted_and_context_is_bounded():
    dom = _domain()
    df = _traffic(5)
    r = V2XRunner(dom)
    recs = _recs(df)[:80]
    recs[10]["t"] = recs[9]["t"]
    r.run(recs, key="t")
    assert r.tie_events >= 1
    r.reset("c")
    r.run(_recs(df), key="c")
    assert max(r.n_ctx_rows) < len(df) and np.median(r.n_ctx_rows) < 100


def test_domain_save_load_round_trip():
    dom = _domain()
    df = _traffic(6, attack=True).iloc[:120].reset_index(drop=True)
    with tempfile.TemporaryDirectory() as tmp:
        dom.save(tmp)
        d2 = V2XPhysicsDomain.load(tmp)
    a, b = dom.score_table(df), d2.score_table(df)
    assert compare_sequences(a, b, tol=1e-12)["identical"]
    assert d2.thr == dom.thr and d2.comb_thr == dom.comb_thr
