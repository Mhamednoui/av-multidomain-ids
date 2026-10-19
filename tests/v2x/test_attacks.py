"""Physical-consistency tests of the VeReMi-taxonomy injection (v2x/attacks.py) on synthetic BSMs."""
import numpy as np
import pandas as pd

from v2x import attacks as A
from v2x.schema import COLUMNS, validate

SENDERS = list("ABCDEFGH")


def make_traffic(n=200, dt=0.1):
    rows = []
    for i, s in enumerate(SENDERS):
        t = np.arange(n) * dt + 100.0 + i * 0.013
        v = 10.0 + 2 * i
        h = 0.3 * i
        x = 50.0 * i + np.cumsum(np.full(n, v * dt * np.cos(h)))
        y = 20.0 * i + np.cumsum(np.full(n, v * dt * np.sin(h)))
        d = pd.DataFrame({"msg_id": [f"m:{s}:{k}" for k in range(n)], "source": "tampa",
                          "sender": s, "pseudo": s, "track": s + "/0", "t": t, "x": x, "y": y,
                          "speed": v, "vx": v * np.cos(h), "vy": v * np.sin(h), "heading": h,
                          "acl": 0.1 * np.sin(np.arange(n) / 7.0), "yaw_rate": 0.0})
        rows.append(d)
    df = pd.concat(rows, ignore_index=True)
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = np.nan if c not in ("rx_id",) else None
    df["label"] = 0
    df["attack"] = "Genuine"
    df["injected"] = False
    return df[COLUMNS]


def scen(aid, seed=7, frac=0.25):
    df = make_traffic()
    sc, att = A.build_scenario(df, SENDERS, aid, seed=seed, frac=frac)
    validate(sc)
    return df, sc, att


def att_rows(sc, att):
    return sc[sc["sender"].isin(att)]


def test_all_attacks_valid_and_labelled():
    for aid in A.ATTACK_IDS:
        df, sc, att = scen(aid)
        assert len(att) == 2
        a = att_rows(sc, att)
        assert (a["label"] == aid).any() and set(a["label"]) <= {0, aid}
        assert (sc[~sc["sender"].isin(att)]["label"] == 0).all()
        # genuine vehicles are untouched
        g0 = df[~df["sender"].isin(att)].sort_values(["track", "t"]).reset_index(drop=True)
        g1 = sc[~sc["sender"].isin(att)].sort_values(["track", "t"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(g0.drop(columns=[]), g1)


def test_deterministic():
    _, a, _ = scen(3)
    _, b, _ = scen(3)
    pd.testing.assert_frame_equal(a, b)


def test_const_pos():
    df, sc, att = scen(1)
    for s in att:
        a = sc[sc["sender"] == s]
        assert a["x"].nunique() == 1 and a["y"].nunique() == 1
        o = df[df["sender"] == s]
        np.testing.assert_allclose(a["speed"].to_numpy(), o["speed"].to_numpy())  # speed stays true


def test_const_pos_offset():
    df, sc, att = scen(2)
    for s in att:
        a, o = sc[sc["sender"] == s], df[df["sender"] == s]
        dx, dy = a["x"].to_numpy() - o["x"].to_numpy(), a["y"].to_numpy() - o["y"].to_numpy()
        assert np.ptp(dx) < 1e-9 and np.ptp(dy) < 1e-9
        assert 100 <= np.hypot(dx[0], dy[0]) <= 300


def test_random_pos_in_box_and_jumps():
    df, sc, att = scen(3)
    for s in att:
        a = sc[sc["sender"] == s]
        assert a["x"].between(df["x"].min(), df["x"].max()).all()
        assert np.hypot(a["x"].diff(), a["y"].diff()).median() > 50      # not drivable at 10 Hz


def test_random_pos_offset_range():
    df, sc, att = scen(4)
    for s in att:
        a, o = sc[sc["sender"] == s], df[df["sender"] == s]
        r = np.hypot(a["x"].to_numpy() - o["x"].to_numpy(), a["y"].to_numpy() - o["y"].to_numpy())
        assert r.min() >= 50 - 1e-9 and r.max() <= 300 + 1e-9


def test_speed_attacks_keep_velocity_consistent():
    for aid in (5, 6, 7, 8):
        df, sc, att = scen(aid)
        for s in att:
            a, o = sc[sc["sender"] == s], df[df["sender"] == s]
            np.testing.assert_allclose(np.hypot(a["vx"], a["vy"]), a["speed"], atol=1e-9)
            np.testing.assert_allclose(np.arctan2(a["vy"], a["vx"]), a["heading"], atol=1e-9)
            np.testing.assert_allclose(a["x"].to_numpy(), o["x"].to_numpy())  # position stays true
            d = a["speed"].to_numpy() - o["speed"].to_numpy()
            if aid == 5:
                assert a["speed"].nunique() == 1 and 15 <= a["speed"].iloc[0] <= 35
            if aid == 6:
                assert np.ptp(d) < 1e-9 and 5 <= d[0] <= 15
            if aid == 7:
                assert a["speed"].between(0, 35).all() and a["speed"].nunique() > 100
            if aid == 8:
                assert (d >= 0).all() and (d <= 10).all()


def test_eventual_stop():
    df, sc, att = scen(9)
    for s in att:
        a = sc[sc["sender"] == s].sort_values("t")
        o = df[df["sender"] == s].sort_values("t")
        k = int((a["label"] == 0).sum())
        assert 0.3 * len(a) - 1 <= k <= 0.6 * len(a) + 1
        assert (a["label"].iloc[:k] == 0).all() and (a["label"].iloc[k:] == 9).all()
        np.testing.assert_allclose(a["x"].iloc[:k], o["x"].iloc[:k])                  # genuine before
        assert a["x"].iloc[k:].nunique() == 1 and (a["speed"].iloc[k:] == 0).all()
        assert (a["t"].diff().dropna() > 0).all()


def test_disruptive_uses_real_messages():
    for aid in (10, 15, 19):
        df, sc, att = scen(aid)
        genuine = df[~df["sender"].isin(att)]
        keyset = set(map(tuple, genuine[["x", "y", "speed"]].round(9).to_numpy()))
        a = att_rows(sc, att)
        got = list(map(tuple, a[["x", "y", "speed"]].round(9).to_numpy()))
        assert all(g in keyset for g in got)


def test_data_replay_exact_sequence():
    df, sc, att = scen(11)
    for s in att:
        a = sc[sc["sender"] == s].sort_values("t")
        found = False
        for v in set(SENDERS) - set(att):
            o = df[df["sender"] == v].sort_values("t")
            if len(o) >= len(a) and np.allclose(a["x"].to_numpy(), o["x"].to_numpy()[:len(a)]) \
                    and np.allclose(a["speed"].to_numpy(), o["speed"].to_numpy()[:len(a)]):
                found = True
        assert found
        assert np.allclose(np.diff(a["t"]), 0.1)        # attacker's own clock, not the victim's


def test_delayed_messages_lag():
    df, sc, att = scen(12)
    for s in att:
        a = sc[sc["sender"] == s].sort_values("t")
        o = df[df["sender"] == s].sort_values("t")
        assert len(a) == len(o) - 30 or len(a) == len(o) - 29       # 3 s of 10 Hz not sendable
        # claimed position = true position 3 s (30 messages) ago -> lag behind truth = v * 3 s
        lag = np.hypot(a["x"].to_numpy() - o["x"].to_numpy()[-len(a):],
                       a["y"].to_numpy() - o["y"].to_numpy()[-len(a):])
        np.testing.assert_allclose(lag, o["speed"].iloc[0] * 3.0, rtol=0.05)


def test_dos_rates_and_extrapolation():
    base = make_traffic()
    for aid, k in ((13, 2), (14, 4), (15, 4), (18, 2), (19, 2)):
        df, sc, att = scen(aid)
        n_att = len(att_rows(sc, att))
        n_orig = int(base[base["sender"].isin(att)].shape[0])
        assert n_att == k * n_orig
    df, sc, att = scen(13)
    a = sc[sc["sender"] == att[0]].sort_values("t")
    v = np.hypot(a["x"].diff(), a["y"].diff()) / a["t"].diff()
    np.testing.assert_allclose(v.dropna().to_numpy(), a["speed"].iloc[1:].to_numpy(), rtol=0.02)


def test_grid_sybil_platoon():
    df, sc, att = scen(16)
    a = sc[sc["sender"] == att[0]]
    assert a["pseudo"].nunique() == 6                                 # attacker + 5 ghosts
    base = a[a["pseudo"] == att[0]].set_index("t")
    for p in set(a["pseudo"]) - {att[0]}:
        g = a[a["pseudo"] == p].set_index("t")
        d = np.hypot(g["x"] - base["x"], g["y"] - base["y"])
        assert np.ptp(d.to_numpy()) < 1e-6 and 3.4 <= d.iloc[0] <= 22        # fixed grid slot
        np.testing.assert_allclose(g["speed"], base["speed"])         # no relative motion
    assert len(a) == 6 * 200


def test_data_replay_sybil_pseudonyms():
    df, sc, att = scen(17)
    a = sc[sc["sender"] == att[0]]
    assert a["pseudo"].nunique() == 4 and len(a) == 200
    for p, g in a.groupby("pseudo"):
        assert len(g) <= A.REPLAY_BLOCK
        assert (g["t"].diff().dropna() > 0).all()


def test_sybil_pseudonym_pool():
    for aid in (18, 19):
        df, sc, att = scen(aid)
        a = sc[sc["sender"] == att[0]]
        assert 20 < a["pseudo"].nunique() <= A.N_PSEUDO
        assert (a["track"] == a["sender"] + "/" + a["pseudo"]).all()


def test_timestamps_never_before_genuine_start():
    for aid in A.ATTACK_IDS:
        df, sc, att = scen(aid)
        for s in att:
            assert sc[sc["sender"] == s]["t"].min() >= df[df["sender"] == s]["t"].min() - 1e-9


def test_other_split_vehicles_not_used():
    df = make_traffic()
    sc, att = A.build_scenario(df, list("ABCD"), 10, seed=1, frac=0.5)
    assert set(sc["sender"]) <= set("ABCD") and set(att) <= set("ABCD")
