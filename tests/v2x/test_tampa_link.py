"""Tests for v2x/tampa_link.py and the Tampa v2 split (WP5 S1b): dedup of copies, id linking, passages, episode split."""
import json
import numpy as np
import pandas as pd

from common.config import results_dir
from v2x import splitting, tampa_link as tl


def _raw(rows):
    cols = ["rsu", "id", "msgCnt", "t", "lat_i", "lon_i", "spd_i", "hd_i", "acl_i", "yaw_i", "rec", "age_s"]
    d = pd.DataFrame(rows, columns=cols)
    return d


def _stream(idv, rsu, t0, n, cnt0, lon0=-824500000, speed_i=1000, dt=0.1):
    """n messages of a vehicle moving East at 20 m/s (spd_i 1000 * 0.02), 10 Hz."""
    rows = []
    for i in range(n):
        t = t0 + i * dt
        lon = lon0 + int(round(20 * (t - 100.0) / (111320 * np.cos(np.radians(27.95))) * 1e7))
        rows.append((rsu, idv, (cnt0 + i) % 128, round(t, 3), 279500000, lon, speed_i, 7200, 0, 0, t, 0.5))
    return rows


def test_dedup_merges_copies_under_different_ids_and_keeps_distinct_messages():
    a = _stream(1, "r1", 100.0, 20, 0)
    b = _stream(2, "r2", 100.5, 15, 5)           # same vehicle heard by r2: messages 5..19 identical content, other id
    raw, u = tl.dedup(_raw(a + b))
    assert len(raw) == 35 and len(u) == 20
    assert (u["n_copies"] >= 1).all() and u["n_copies"].max() == 2
    comp, nc = tl.id_components(raw)
    assert nc == 1 and comp[1] == comp[2]


def test_different_vehicles_with_same_msgcnt_are_not_merged():
    a = _stream(1, "r1", 100.0, 10, 0)
    b = _stream(2, "r1", 100.0, 10, 0, lon0=-824400000)          # same time and counter, 1 km away
    raw, u = tl.dedup(_raw(a + b))
    assert len(u) == 20
    _, nc = tl.id_components(raw)
    assert nc == 2


def test_tolerance_rule_finds_no_extra_merge_on_exact_data():
    a = _stream(1, "r1", 100.0, 10, 0)
    b = _stream(2, "r2", 100.0, 10, 0)
    raw, u = tl.dedup(_raw(a + b))
    assert tl.tolerance_extra_merges(u)["extra_merges_by_tolerance_rule"] == 0


def test_continuity_links_unique_mutual_candidate_and_leaves_ambiguity():
    a = _stream(1, "r1", 100.0, 30, 0)                    # ends at 102.9, 20 m/s East
    b = _stream(2, "r2", 103.4, 30, 35)
    raw, u = tl.dedup(_raw(a + b))
    comp, _ = tl.id_components(raw)
    u["lab"] = u["id"].map(comp).to_numpy()
    links, amb = tl.link_continuity(u)
    assert len(links) == 1 and not amb and u["lab"].nunique() == 1
    # wrong message counter -> no link
    b2 = _stream(2, "r2", 103.4, 30, 90)
    raw, u = tl.dedup(_raw(a + b2))
    comp, _ = tl.id_components(raw)
    u["lab"] = u["id"].map(comp).to_numpy()
    assert len(tl.link_continuity(u)[0]) == 0
    # b and c carry the same messages under two ids: still ONE unique candidate after tier 1
    c = _stream(3, "r3", 103.4, 30, 35)
    raw, u = tl.dedup(_raw(a + b + c))
    comp, _ = tl.id_components(raw)
    u["lab"] = u["id"].map(comp).to_numpy()
    assert u["lab"].nunique() == 2                       # b and c are copies of each other (one component), a is the other
    assert len(tl.link_continuity(u)[0]) == 1 and u["lab"].nunique() == 1


def test_passages_cut_at_silence():
    u = pd.DataFrame({"vlab": [0] * 4 + [1] * 2, "t": [0, 1, 200, 201, 5, 6.0]})
    p = tl.passages(u)
    assert p.tolist() == [0, 0, 1, 1, 0, 0]


def test_episodes_cut_only_in_silences_and_merge_same_vehicle():
    rows = []
    for s, (t0, t1) in {"a": (0, 100), "b": (120, 200), "c": (300, 400), "d": (1000, 1100), "e": (2000, 2100)}.items():
        rows += [dict(sender=s, t=t0), dict(sender=s, t=t1)]
    df = pd.DataFrame(rows)
    ep = splitting.tampa_episodes(df, guard=30.0)
    assert ep["a"] == ep["b"] and ep["b"] != ep["c"] and len({ep[k] for k in "abcde"}) == 4       # a,b: 20 s apart; b,c: 100 s
    ep2 = splitting.tampa_episodes(df, guard=30.0, vehicle_of={"a": "V1", "e": "V1"})
    assert ep2["a"] == ep2["e"] and ep2["a"] == ep2["b"]
    split, info = splitting.tampa_time_block_split(df.assign(sender=df["sender"]), seed=1)
    allids = [s for v in split.values() for s in v]
    assert sorted(allids) == list("abcde") and len(set(allids)) == 5
    gaps = splitting.min_gap_between_parts(df, split)
    assert min(gaps.values()) >= 60.0


def test_saved_tampa_v2_split_is_clean():
    out = results_dir("WP5")
    f, g = out / "splits_tampa_v2.json", out / "s1b_split_info.json"
    if not (f.exists() and g.exists()):
        return
    sp, info = json.loads(f.read_text()), json.loads(g.read_text())
    ids = [s for v in sp.values() for s in v]
    assert len(ids) == len(set(ids)) and all(len(v) > 0 for v in sp.values())
    assert min(info["gap_s_between_parts"].values()) >= info["required_min_gap_s"]
    assert info["n_residual_vehicles"] == 0 and info["all_types_present_every_part"]
    vehicle = info["vehicle_of_passage"]
    part_of = {s: p for p, v in sp.items() for s in v}
    seen = {}
    for s, p in part_of.items():
        assert seen.setdefault(vehicle[s], p) == p          # no physical vehicle in two parts
    assert info["attackers_per_type_min"]["val"] >= 2 and info["attackers_per_type_min"]["test"] >= 2
