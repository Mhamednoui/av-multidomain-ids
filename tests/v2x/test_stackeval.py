"""Unit tests of the V2X stack evaluation helpers (v2x/stackeval.py)."""
import numpy as np
import pandas as pd

from v2x import stackeval


def toy():
    rows = []
    for b in range(6):                                    # 6 time blocks
        for s in range(4):                                # 2 genuine, 1 attacker class A, 1 attacker class B per block
            name = f"s{b}_{s}"
            atype = ["normal", "normal", "A", "B"][s]
            for i in range(10):
                rows.append((name, 100.0 * b + i, atype != "normal", atype, str(b)))
    return pd.DataFrame(rows, columns=["sender", "t", "y", "atype", "group"])


def test_block_bootstrap_matches_plain_rates_and_ci_contains_them():
    m = toy()
    al = ((m["atype"] == "A") & (m["t"] % 100 >= 5)).to_numpy()          # A: 50% of messages, from message 5 on
    r = stackeval.evaluate_alarms(m, al, ["A", "B"], k=3, B=200)
    assert abs(r["msg_all"]["A"]["p"] - 0.5) < 1e-9 and r["msg_all"]["B"]["p"] == 0.0
    assert r["fa_msg"]["p"] == 0.0 and r["fa_sender"]["p"] == 0.0
    lo, hi = r["msg_all"]["A"]["ci"]
    assert lo <= 0.5 <= hi and abs(lo - 0.5) < 1e-9          # identical blocks -> degenerate CI
    assert r["sender"]["A"]["p"] == 1.0 and r["sender"]["B"]["p"] == 0.0


def test_ci_widens_when_blocks_differ():
    m = toy()
    al = ((m["atype"] == "A") & (m["group"].astype(int) < 3)).to_numpy()   # A detected only in blocks 0-2
    r = stackeval.evaluate_alarms(m, al, ["A"], k=3, B=500)
    lo, hi = r["msg_all"]["A"]["ci"]
    assert abs(r["msg_all"]["A"]["p"] - 0.5) < 1e-9 and lo < 0.4 and hi > 0.6


def test_scored_rows_and_delay():
    m = toy()
    kinds = np.where(m["t"] % 100 == 0, 1, 0)                  # first message of each sender is unscored
    al = ((m["atype"] == "A") & (m["t"] % 100 >= 4)).to_numpy()
    r = stackeval.evaluate_alarms(m, al, ["A", "B"], kinds=kinds, seen=["A", "B"], k=3, B=50)
    assert abs(r["msg_scored"]["A"]["p"] - 6 / 9) < 1e-9 and r["msg_scored"]["A"]["n"] == 54
    assert r["scored_share"]["A"] == 0.9
    d = r["sender"]["A"]
    assert d["delay_first_alarm_s_q25_med_q75"][1] == 4.0 and d["delay_kth_alarm_s_q25_med_q75"][1] == 6.0
    assert "claimed" in r["msg_scored"]["A"]
    assert abs(r["mean_msg_scored"]["seen"]["p"] - 1 / 3) < 1e-9 or r["mean_msg_scored"]["seen"]["p"] < 0.5


def test_sender_level_false_alarm_needs_k_alarms():
    m = toy()
    g = (m["sender"] == "s0_0").to_numpy()
    al = g & (m["t"] < 2).to_numpy()                            # 2 alarms on one genuine sender
    assert stackeval.evaluate_alarms(m, al, ["A", "B"], k=3, B=20)["fa_sender"]["p"] == 0.0
    al = g & (m["t"] < 3).to_numpy()
    assert abs(stackeval.evaluate_alarms(m, al, ["A", "B"], k=3, B=20)["fa_sender"]["p"] - 1 / 12) < 1e-9


def test_same_vehicle_id_in_two_scenarios_is_two_senders():
    m = toy()
    extra = m[m["sender"] == "s0_2"].copy()                      # the attacker id of class A re-used as a class-B attacker
    extra["atype"] = "B"
    m2 = pd.concat([m, extra], ignore_index=True)
    al = np.zeros(len(m2), bool)
    st = stackeval.sender_table(m2, al, 3)
    assert len(st[st["sender"] == "s0_2"]) == 2 and set(st[st["sender"] == "s0_2"]["atype"]) == {"A", "B"}
    r = stackeval.evaluate_alarms(m2, al, ["A", "B"], k=3, B=10)
    assert r["sender"]["A"]["n_senders"] == 6 and r["sender"]["B"]["n_senders"] == 7
