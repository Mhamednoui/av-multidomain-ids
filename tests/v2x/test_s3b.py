"""Tests for WP5 S3b: receiver-position layers (v2x/l_rx.py), V2AIX injection (v2x/v2aix_inject.py), evaluation helpers (v2x/v2aix_eval.py). Synthetic data only."""
import numpy as np
import pandas as pd

from v2x import l_rx, v2aix_eval as ev, v2aix_inject as inj
from v2x.schema import COLUMNS


def _table(n_senders=6, n=40, dt=0.3, rec="Stationary/V2X-only/Site/2024", rx=(0.0, 0.0), start_far=True, seed=0):
    rng = np.random.RandomState(seed)
    rows = []
    for s in range(n_senders):
        t0 = 100.0 + s * 3.0
        x0 = -800.0 + 150.0 * s if start_far else 20.0 * s
        for k in range(n):
            t = t0 + k * dt
            rows.append({"msg_id": f"m{s}_{k}", "source": "v2aix", "sender": f"{rec}#{s}", "pseudo": str(s), "track": f"{rec}#{s}/0", "t": t, "x": x0 + 15.0 * k * dt + rng.randn() * 0.5,
                         "y": 3.0 * s + rng.randn() * 0.5, "speed": 15.0, "vx": 15.0, "vy": 0.0, "heading": 0.0, "acl": 0.0, "yaw_rate": 0.0, "pos_sigma": 2.0, "spd_sigma": 0.1,
                         "acl_sigma": np.nan, "rx_id": rec, "rx_x": rx[0], "rx_y": rx[1], "lat": 50.8, "lon": 6.1, "label": 0, "attack": "Genuine", "injected": False,
                         "age_s": 0.02 * rng.rand(), "recording": rec, "station_id": str(s), "station_type": 5.0, "rx_src": "cohda_static", "recv_s": t + 7.0 + 0.02 * rng.rand()})
    df = pd.DataFrame(rows)
    df["track"] = df["sender"] + "/0"
    return df.sort_values(["track", "t"], kind="stable").reset_index(drop=True)


def test_distance_and_nan():
    df = _table()
    d = l_rx.distance_to_receiver(df)
    assert np.allclose(d, np.hypot(df["x"], df["y"]))
    df2 = df.copy()
    df2["rx_x"] = np.nan
    lay = l_rx.AcceptanceRange()
    assert not lay.evaluable(df2)
    assert np.all(lay.raw_scores(df2) == 0)


def test_acceptance_range_threshold_tie_safe():
    df = _table(n_senders=10)
    g = np.ones(len(df), bool)
    lay = l_rx.AcceptanceRange().calibrate_fit(df, g, budget=0.01)
    assert lay.alarms(df).mean() <= 0.01 + 1e-9                      # tie-safe: never above the budget on the calibration data
    far = df.copy()
    far["x"] = far["x"] + 50000.0
    assert lay.alarms(far).mean() > 0.99                             # 50 km away is farther than any validation sender
    nan = df.copy()
    nan["rx_x"] = np.nan
    assert not lay.alarms(nan).any()                                 # not evaluable, never alarms


def test_first_flags_grace_and_rx():
    df = _table(n_senders=4)
    first, ev_ = l_rx.first_flags(df, grace_s=5.0)
    assert first.sum() == 4                                           # one first message per track
    assert ev_.sum() == 2                                             # senders 0 and 1 start within 5 s of the recording start (grace period)
    nan = df.copy()
    nan["rx_x"] = np.nan
    assert l_rx.first_flags(nan)[1].sum() == 0


def test_appearance_close_first_message_alarms():
    df = _table(n_senders=12, start_far=True)
    lay = l_rx.AppearanceData().calibrate_fit(df, np.ones(len(df), bool), budget=0.1)
    ghost = df[df["sender"].str.endswith("#9")].copy()
    ghost["sender"] = ghost["sender"] + "g"
    ghost["track"] = ghost["sender"] + "/0"
    ghost["x"] = ghost["x"] - ghost["x"].iloc[0] + 30.0                 # first heard 30 m from the receiver
    ghost["y"] = ghost["y"] - ghost["y"].iloc[0]
    ghost["msg_id"] = ghost["msg_id"] + "g"
    both = pd.concat([df, ghost], ignore_index=True)
    a = lay.alarms(both)
    first, evf = l_rx.first_flags(both)
    gi = both["sender"].str.endswith("g").to_numpy()
    assert a[gi & first].all() and not a[gi & ~first].any()           # only the first message of the ghost track
    assert l_rx.appearance_physical_alarm(both)[gi & first].all()


def test_injection_ghost_and_far_offset_geometry():
    df = _table(n_senders=6, n=60)
    sc, att = inj.build_scenario(df, "20", frac=0.5, min_msgs=20)
    gh = sc[sc["attack"] == "GhostNearReceiver"]
    assert len(gh) > 0
    first = gh.sort_values("recv_s").groupby("track").first()
    d0 = np.hypot(first["x"] - first["rx_x"], first["y"] - first["rx_y"])
    assert ((d0 >= 19.9) & (d0 <= 150.1)).all()                       # first message 20-150 m from the receiver
    assert (gh["recv_s"] >= df["recv_s"].min() + inj.GHOST_MIN_START_S - 1e-9).all()
    sc2, _ = inj.build_scenario(df, "21", frac=0.5, min_msgs=20)
    fo = sc2[sc2["injected"]]
    g0 = df.set_index("msg_id").loc[fo["msg_id"]]
    shift = np.hypot(fo["x"].to_numpy() - g0["x"].to_numpy(), fo["y"].to_numpy() - g0["y"].to_numpy())
    assert ((shift >= 5000) & (shift <= 20000)).all()
    assert (pd.Series(shift).groupby(fo["sender"].to_numpy()).apply(np.ptp) < 1e-6).all()    # rigid shift: one offset per attacker


def test_injection_recv_time_consistent_and_split_pool():
    df = _table(n_senders=8, n=60)
    for code in ("3", "11", "13", "16", "12", "12b"):
        sc, att = inj.build_scenario(df, code, frac=0.5, min_msgs=20)
        assert np.all(np.isfinite(sc[["t", "x", "y", "recv_s"]].to_numpy()))
        base = df.assign(lat_s=df["recv_s"] - df["t"])
        lat = (sc["recv_s"] - sc["t"]).to_numpy()
        step = 3.0 if code == "12b" else 0.0
        assert lat.min() >= (base["lat_s"].min() - 1e-9) and lat.max() <= base["lat_s"].max() + step + 1e-9
        assert set(sc.loc[sc["injected"], "sender"]) <= set(att)
        assert set(sc["sender"]) <= set(df["sender"])                  # nothing from outside the given table (split purity)
    sc, att = inj.build_scenario(df, "12b", frac=0.5, min_msgs=20)
    stepped = sc[sc["injected"]]
    assert (stepped["age_s"] > 2.9).all() and sc[~sc["injected"]]["age_s"].max() < 1.0


def test_injection_dos_rate_and_determinism():
    df = _table(n_senders=6, n=60)
    a, att1 = inj.build_scenario(df, "13", seed=42)
    b, att2 = inj.build_scenario(df, "13", seed=42)
    assert att1 == att2 and a["msg_id"].tolist() == b["msg_id"].tolist()
    n_att = int(df["sender"].isin(att1).sum())
    assert int(a["injected"].sum()) == 2 * n_att                       # DoS x2


def test_eval_helpers():
    df = _table(n_senders=5, n=20, dt=0.5)
    assert abs(ev.recording_hours(df) - (df["recv_s"].max() - df["recv_s"].min()) / 3600.0) < 1e-12
    alarm = np.zeros(len(df), bool)
    alarm[:5] = True
    c = ev.sender_counts(df, alarm)
    assert c["n_alarm"].sum() == 5
    assert ev.k_for_budget(pd.Series([0] * 98 + [1, 5]), 0.01) == 2    # at most 1 sender of 100 may have >= k alarms
    assert ev.alarm_events(df, alarm) == 1
    p, lo, hi, n = ev.boot_rate(df, alarm, B=50)
    assert n == len(df) and lo <= p <= hi


def test_columns_after_injection():
    df = _table()
    sc, _ = inj.build_scenario(df, "3")
    assert all(c in sc.columns for c in COLUMNS)


def test_injection_finite_with_missing_heading():
    df = _table(n_senders=6, n=60)
    df.loc[df.index[::7], ["heading", "vx", "vy"]] = np.nan           # 14% unavailable headings (real CAMs: 0.3%)
    for code in ("16", "13", "18"):
        sc, _ = inj.build_scenario(df, code, frac=0.5, min_msgs=20)
        assert np.isfinite(sc.loc[sc["injected"], ["x", "y", "t"]].to_numpy()).all()
