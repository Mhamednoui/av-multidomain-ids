"""Tests for can/frames.py, can/adapters.py, can/splits.py (WP2 S1). Synthetic files + one real ROAD capture."""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from can import adapters, splits
from can.frames import BYTE_COLS, bytes_to_hex, dt_clipped, hex_to_bytes, make_frame, validate_frame


class Skip(Exception):
    pass


def _raises(f, exc=ValueError):
    try:
        f()
    except exc:
        return True
    return False


def test_hex_roundtrip_and_edge_cases():
    src = ["", "00", "DEADBEEF", "0123456789ABCDEF", "FFFFFFFFFFFFFFFF", "AB\t", "1A2b"]
    dlc, B = hex_to_bytes(src)
    assert dlc.tolist() == [0, 1, 4, 8, 8, 1, 2]
    assert (B[0] == -1).all() and B[1].tolist() == [0] + [-1] * 7
    assert B[5, 0] == 0xAB and B[5, 1] == -1
    back = bytes_to_hex(dlc, B)
    assert back.tolist() == ["", "00", "DEADBEEF", "0123456789ABCDEF", "FFFFFFFFFFFFFFFF", "AB", "1A2B"]


def test_hex_rejects_bad_input():
    assert _raises(lambda: hex_to_bytes(["ABC"]))
    assert _raises(lambda: hex_to_bytes(["00" * 9]))
    assert _raises(lambda: hex_to_bytes(["0G"]))
    assert _raises(lambda: hex_to_bytes(["AB CD"]))


def _frame(n=5):
    dlc, B = hex_to_bytes(["0102"] * n)
    return make_frame(np.arange(n) * 0.01, [0x10] * n, dlc, B, [0, 0, 1, 0, 0],
                      ["normal", "normal", "x", "normal", "normal"], "c", "v")


def test_validate_frame_contract():
    d = _frame()
    assert validate_frame(d)["injected"] == 1
    bad = d.copy()
    bad.loc[0, "b5"] = 7                                   # byte beyond DLC
    assert _raises(lambda: validate_frame(bad))
    bad = d.copy()
    bad["label"] = 0                                       # attack name without label
    assert _raises(lambda: validate_frame(bad))
    assert _raises(lambda: validate_frame(d.iloc[:0]))
    assert list(d.columns)[-3:] == ["attack", "capture", "vehicle"]


def test_dt_clipped_keeps_order():
    t = np.array([0.0, 1.0, 0.9999, 2.0])
    d = dt_clipped(t)
    assert np.isnan(d[0]) and d[1] == 1.0 and d[2] == 0.0 and abs(d[3] - 1.0001) < 1e-9


def test_road_parse_and_label():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "c.log"
        p.write_text("(10.000000) can0 100#0102030405060708\n(10.010000) can0 200#FF\n"
                     "(10.020000) can0 100#FFFFFFFFFFFFFFFF\n(10.030000) can0 300#\n")
        r = adapters.road_parse_log(p)
        assert r["t"].tolist() == [0.0, 0.01, 0.02, 0.03] or np.allclose(r["t"], [0, 0.01, 0.02, 0.03])
        assert r["id"].tolist() == [0x100, 0x200, 0x100, 0x300]
        assert r["dlc"].tolist() == [8, 1, 8, 0]
        assert r["B"][1].tolist() == [255] + [-1] * 7
        d = pd.DataFrame({"t": r["t"], "id": r["id"]})
        for i in range(8):
            d[f"b{i}"] = r["B"][:, i]
        meta = {"injection_interval": [0.015, 0.05], "injection_id": "XXX", "injection_data_str": "FFFFFFFFFFFFFFFF"}
        assert adapters.road_label_attack(d, meta).tolist() == [False, False, True, False]
        meta = {"injection_interval": [0.0, 0.05], "injection_id": "100", "injection_data_str": "01XX0304XXXXXXXX"}
        assert adapters.road_label_attack(d, meta).tolist() == [True, False, False, False]


def test_road_family_and_split_rules():
    assert adapters.road_family("reverse_light_off_attack_2_masquerade") == "reverse_light_off"
    assert adapters.road_family("reverse_light_on_attack_1") == "reverse_light_on"
    assert adapters.road_attack_split("max_speedometer_attack_2_masquerade") == "val"
    assert adapters.road_attack_split("fuzzing_attack_3") == "test"
    assert adapters.road_attack_split("max_engine_coolant_temp_attack") == "test"


def test_road_split_masquerade_with_original():
    caps = pd.DataFrame({"name": ["a_attack_1", "a_attack_1_masquerade", "b_attack_2"],
                         "usable": True, "part": ["train", "train", "val"]})
    sp = splits.road_split(caps)
    assert sp["train"] == ["a_attack_1", "a_attack_1_masquerade"] and sp["test"] == []
    caps.loc[1, "part"] = "test"
    assert _raises(lambda: splits.road_split(caps))


def test_road_real_capture_counts():
    if not (adapters.ROAD / "ambient" / "ambient_dyno_drive_winter.log").exists():
        raise Skip("ROAD not available")
    caps = adapters.road_captures()
    assert len(caps) == 45 and caps["usable"].sum() == 41
    d = adapters.load_road("ambient_dyno_drive_winter", caps)
    assert validate_frame(d)["frames"] == 114148 and d["label"].sum() == 0
    sp = splits.road_split(caps)
    assert {k: len(v) for k, v in sp.items()} == {"train": 15, "val": 11, "test": 15}


def test_block_split_deterministic_and_interleaved():
    lab = np.r_[np.ones(300, dtype=int), np.zeros(100, dtype=int)]
    lab = np.repeat(lab, 25)
    a = splits.block_split(lab, np.random.default_rng(1))
    b = splits.block_split(lab, np.random.default_rng(1))
    assert (a == b).all()
    assert set(a) == {"train", "val", "test"}
    blocks = splits.block_assign(lab, np.random.default_rng(1))
    assert len(blocks) == 100
    # attack blocks (first 75) appear in every part
    assert set(blocks[:75]) == {"train", "val", "test"}


def test_d11_adapter_order_dlc_tab_empty():
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "DoS-3.csv"
        p.write_text("timestamp,arbitration_id,data_field,attack\n"
                     "1672531200.0,0C7,02BD91A3,0\n"
                     "1672531200.0010,000,FFFF,1\n"
                     "1672531200.0009,0F9,012640127A97D512,0\n"      # inversion
                     "1672531200.0020,1ED,614008F208E870DE\t,1\n"    # trailing tab
                     "1672531200.0030,257,,1\n")                     # empty payload, attack
        d = adapters.load_d11(p, "set_x/train_01/DoS-3", "Impala")
        assert validate_frame(d) == {"frames": 5, "injected": 3, "negative_dt": 1}
        assert d["dlc"].tolist() == [4, 2, 8, 8, 0]
        assert d["id"].tolist() == [0xC7, 0, 0xF9, 0x1ED, 0x257]
        assert d["attack"].astype(str).tolist() == ["normal", "DoS", "normal", "DoS", "DoS"]
        assert d["t"].iloc[0] == 0.0 and d["t"].iloc[1] > d["t"].iloc[2]    # recorded order kept
        assert str(d["vehicle"].iloc[0]) == "Impala"
        assert bytes_to_hex(d["dlc"].to_numpy(), d[BYTE_COLS].to_numpy()).tolist() == [
            "02BD91A3", "FFFF", "012640127A97D512", "614008F208E870DE", ""]


def test_d11_file_table_rules():
    assert adapters.d11_attack_of("rpm-accessory-3.csv") == "rpm-accessory"
    assert adapters.d11_attack_of("DoS-3.csv") == "DoS"
    assert adapters.d11_vehicle_by_readme("set_03", "test_02_unknown_vehicle_known_attack") == "Subaru"
    assert adapters.d11_vehicle_by_readme("set_03", "train_01") == "Silverado"
    assert adapters.d11_vehicle_by_readme("set_04", "test_03_known_vehicle_unknown_attack") == "Subaru"


def _fake_table():
    rows = []
    for sub, fam, num in [("train_01", "DoS", 1), ("train_01", "DoS", 2), ("train_01", "attack-free", 1),
                          ("test_01_known_vehicle_known_attack", "DoS", 3),
                          ("test_02_unknown_vehicle_known_attack", "DoS", 3),
                          ("test_03_known_vehicle_unknown_attack", "speed", 3)]:
        rows.append((f"s/{sub}/{fam}-{num}", "s", sub, "train" if sub == "train_01" else "test", fam, num))
    return pd.DataFrame(rows, columns=["capture", "set", "subset", "role", "attack_family", "number"])


def test_d11_split_holdout_and_dedup():
    t = _fake_table()
    h = {c: c for c in t["capture"]}
    h["s/test_02_unknown_vehicle_known_attack/DoS-3"] = "s/test_01_known_vehicle_known_attack/DoS-3"   # copy
    h["s/test_03_known_vehicle_unknown_attack/speed-3"] = "s/train_01/DoS-1"                           # copy of train
    sp = splits.d11_split(t, h)["s"]
    assert sp["val"] == ["s/train_01/DoS-2"] and sp["train"] == ["s/train_01/DoS-1", "s/train_01/attack-free-1"]
    assert sp["test_01"] == ["s/test_01_known_vehicle_known_attack/DoS-3"] and sp["test_02"] == []
    assert sp["test_03"] == [] and len(sp["excluded_duplicates"]) == 2
    splits.check_d11_split({"s": sp}, h)
    leaky = {"s": {"train": ["s/train_01/DoS-1"], "test_01": ["s/test_03_known_vehicle_unknown_attack/speed-3"]}}
    assert _raises(lambda: splits.check_d11_split(leaky, h))


def test_d11_real_table_and_saved_splits():
    from common.config import RESULTS
    import json
    if not adapters.D11.exists() or not (RESULTS / "WP2" / "splits_d11.json").exists():
        raise Skip("D11 or splits not available")
    ft = adapters.d11_file_table()
    assert len(ft) == 236 and ft["capture"].is_unique
    sp = json.load(open(RESULTS / "WP2" / "splits_d11.json"))["splits"]
    scan = json.load(open(RESULTS / "WP2" / "s1_d11_scan.json"))
    hashes = {s["capture"]: s["sha256"] for s in scan}
    assert len(set(hashes.values())) == 174
    splits.check_d11_split(sp, hashes)
    for s, parts in sp.items():
        tr = {hashes[c] for c in parts["train"] + parts["val"]}
        te = {hashes[c] for k, v in parts.items() if k.startswith("test_") for c in v}
        assert not (tr & te), s
        assert not ({hashes[c] for c in parts["train"]} & {hashes[c] for c in parts["val"]})
    # smallest file: rows and labels equal the S0 inventory
    inv = {f["path"][:-4]: f for f in json.load(open(RESULTS / "WP2" / "s0_inventory.json"))["files"]}
    cap = min(inv, key=lambda c: inv[c]["rows"])
    r = ft[ft["capture"] == cap].iloc[0]
    d = adapters.load_d11(r["path"], cap, r["vehicle"])
    assert len(d) == inv[cap]["rows"] and int(d["label"].sum()) == inv[cap]["labels"].get("1", 0)
    validate_frame(d)


def test_road_split_saved_masquerade_pairs():
    from common.config import RESULTS
    import json
    f = RESULTS / "WP2" / "splits_road.json"
    if not f.exists():
        raise Skip("splits_road.json missing")
    sp = json.load(open(f))["splits"]
    side = {n: p for p, ns in sp.items() for n in ns}
    pairs = [n for n in side if n.endswith("_masquerade")]
    assert len(pairs) == 13 and all(side[n] == side[n[:-11]] for n in pairs)
