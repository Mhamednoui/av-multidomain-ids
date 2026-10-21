"""Unit tests of the V2X L3 Kalman tracker (v2x/l3.py) on synthetic message tables."""
import numpy as np
import pandas as pd

from v2x import l3


def simulate(n_tracks=60, n=80, dt=1.0, sp=0.5, sv=0.1, sa=1.0, seed=0, prefix="s"):
    """Tracks from the filter's own model: s' = F s + w, w ~ N(0, Q); z = s + N(0, R)."""
    rng = np.random.RandomState(seed)
    Q = l3._Q(np.array([dt]), sa)[0]
    L = np.linalg.cholesky(Q + 1e-12 * np.eye(4))
    F = np.eye(4)
    F[0, 2] = F[1, 3] = dt
    rows = []
    for k in range(n_tracks):
        s = np.array([rng.uniform(0, 1000), rng.uniform(0, 1000), rng.uniform(-15, 15), rng.uniform(-15, 15)])
        for i in range(n):
            z = s + rng.randn(4) * np.array([sp, sp, sv, sv])
            rows.append((f"{prefix}{k}", f"{prefix}{k}", i * dt, z[0], z[1], z[2], z[3]))
            s = F @ s + L @ rng.randn(4)
    d = pd.DataFrame(rows, columns=["track", "sender", "t", "x", "y", "vx", "vy"])
    d["speed"] = np.hypot(d["vx"], d["vy"])
    d["heading"] = np.arctan2(d["vy"], d["vx"])
    return d


def straight(name="a", n=10, v=10.0, dt=1.0, x0=0.0, t0=0.0):
    t = t0 + np.arange(n) * dt
    d = pd.DataFrame({"track": name, "sender": name, "t": t, "x": x0 + v * (t - t0), "y": 0.0, "vx": v, "vy": 0.0})
    d["speed"], d["heading"] = v, 0.0
    return d


def tracker(sp=0.5, sv=0.1, sa=1.0):
    return l3.Tracker(l3.KalmanParams(sp, sv, sa))


def test_first_message_not_scored_and_consistent_track_has_tiny_nis():
    tr = tracker()
    r = tr.run(straight())
    assert not r["scored"][0] and r["nis"][0] == 0
    assert r["scored"][1:].all() and r["nis"][1:].max() < 1e-6


def test_nis_is_chi_square_4_on_data_from_the_model():
    d = simulate()
    r = tracker().run(d)
    c = l3.consistency(r["nis"], r["scored"])
    assert 3.6 < c["nis_mean"] < 4.4, c
    assert 0.03 < c["frac_above_chi2_95"] < 0.07, c
    assert 0.03 < c["frac_below_chi2_05"] < 0.07, c


def test_jump_gives_large_nis_and_cusum_hi_grows_then_decays():
    d = straight(n=12)
    d.loc[6:, "x"] += 300.0                     # constant offset appearing mid-track: one jump, then consistent again
    r = tracker().run(d)
    assert r["nis"][6] > 1000
    assert r["nis"][11] < r["nis"][6] / 10             # the filter follows the new level, innovations shrink
    assert r["chi"][6] > 1000


def test_persistent_inconsistency_accumulates_cusum_hi():
    d = straight(n=20)
    d["vx"] = 10.0
    d["x"] = 100.0                              # ConstPos: claims 10 m/s but never moves
    r = tracker().run(d)
    assert np.all(np.diff(r["chi"][1:]) > 0)


def test_cusum_lo_fires_on_frozen_stream_not_on_noisy_one():
    noisy = simulate(n_tracks=20, n=60, seed=3)
    r = tracker().run(noisy)
    assert np.quantile(r["clo"], 0.99) < 6.0
    frozen = straight(n=30)
    frozen["x"], frozen["vx"], frozen["speed"] = 50.0, 0.0, 0.0
    frozen["y"] = 20.0
    r = tracker().run(frozen)
    assert r["clo"][-1] > 40.0                  # about 29 x K_LO
    assert r["chi"].max() == 0.0


def test_gap_longer_than_dt_max_restarts_the_filter():
    d = straight(n=6)
    d.loc[3:, "t"] += 30.0
    d.loc[3:, "x"] += 5000.0
    r = tracker().run(d)
    assert not r["scored"][3] and r["nis"][3] == 0
    assert r["scored"][4]


def test_causal_scores_do_not_depend_on_later_messages():
    d = simulate(n_tracks=5, n=40, seed=5)
    a = tracker().run(d)
    d2 = d.copy()
    late = d2["t"] > 30
    d2.loc[late, "x"] += 500.0
    b = tracker().run(d2)
    early = (d["t"] <= 30).to_numpy()
    assert np.allclose(a["nis"][early], b["nis"][early]) and np.allclose(a["chi"][early], b["chi"][early])


def test_rows_in_arbitrary_order_give_the_same_scores():
    d = simulate(n_tracks=4, n=30, seed=6)
    a = tracker().run(d)["nis"]
    perm = np.random.RandomState(1).permutation(len(d))
    dp = d.iloc[perm].reset_index(drop=True)
    b = tracker().run(dp)["nis"]
    assert np.allclose(a[perm], b)


def test_fit_noise_recovers_parameters_and_uses_only_given_rows():
    d = simulate(n_tracks=50, n=40, sp=0.6, sv=0.15, sa=1.2, seed=7)
    p, info = l3.fit_noise(d, max_tracks=50, max_msgs=40)
    assert 0.4 < p.sp < 0.9 and 0.9 < p.sa < 1.6, p      # sv is not identifiable when sa^2 dt >> sv^2: only bounded below by the floor
    assert p.sv >= l3.SV_MIN
    assert set(info["senders_used"]) <= set(d["sender"])
    half = d[d["sender"].isin(sorted(set(d["sender"]))[:30])]
    _, info2 = l3.fit_noise(half, max_tracks=20, max_msgs=20)
    assert set(info2["senders_used"]) <= set(half["sender"])


def test_birth_density_counts_recent_nearby_births_only_and_is_causal():
    rows = []
    for i in range(6):                                   # six new identities within 5 s and 100 m
        rows.append((f"b{i}", 100.0 + i, 500.0 + 10 * i, 0.0))
    rows.append(("far", 102.0, 5000.0, 0.0))             # far away
    rows.append(("old", 50.0, 500.0, 0.0))               # same place, long ago
    d = pd.DataFrame(rows, columns=["track", "t", "x", "y"])
    d2 = pd.concat([d, pd.DataFrame({"track": ["b0"] * 3, "t": [101.0, 102.0, 103.0], "x": 500.0, "y": 0.0})], ignore_index=True)
    r = l3.birth_density(d2)
    byt = dict(zip(d2["track"][:9], r[:9]))
    assert byt["b0"] == 0 and byt["b5"] == 5             # b5 sees the five earlier ones
    assert byt["far"] == 0 and byt["old"] == 0
    assert (r[9:] == 0).all()                            # continuing messages of an existing track are not births
    keep = (d2["t"] <= 102.0).to_numpy()
    r_short = l3.birth_density(d2[keep].reset_index(drop=True))
    assert np.array_equal(r_short, r[keep])              # dropping later births does not change an earlier score


def test_layers_calibrate_to_the_budget_and_flag_an_attack():
    d = simulate(n_tracks=200, n=50, seed=8)
    tr = tracker()
    layers = l3.make_layers(tr)
    mask = np.ones(len(d), bool)
    for l in layers[:3]:
        l.calibrate_masked(d, mask, 0.01)
        ev = l.score(d)
        fa = np.mean([e.alarm for e in ev])
        assert fa <= 0.0101, (l.name, fa)
    bad = straight(n=20)
    bad["x"] = 100.0
    ev = layers[1].score(bad)
    assert ev[-1].alarm and ev[-1].reason
