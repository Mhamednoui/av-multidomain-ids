"""Tests for v2x/schema.py, adapters.py, splitting.py (synthetic CSVs; real files if present)."""
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import RESULTS
from v2x import adapters, schema, splitting


def _veremi_csv(path, n=30):
    r = []
    for s, cls in ((11, 0), (22, 1)):
        for k in range(n):
            r.append(dict(type=4, sendTime=100.0 + k + s, sender=s, senderPseudo=s * 10 + 7,
                          messageID=s * 1000 + k, **{"class": cls}, posx=10.0 + k, posy=5.0, posz=0.0,
                          posx_n=3.0, posy_n=3.0, posz_n=0.0, spdx=1.0, spdy=0.0, spdz=0.0,
                          spdx_n=0.0, spdy_n=0.0, spdz_n=0.0, aclx=0.5, acly=0.0, aclz=0.0,
                          aclx_n=0.0, acly_n=0.0, aclz_n=0.0, hedx=1.0, hedy=0.0, hedz=0.0,
                          hedx_n=1.0, hedy_n=1.0, hedz_n=0.0))
    pd.DataFrame(r).to_csv(path, index=False)


def test_veremi_adapter_synthetic():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "v.csv"
        _veremi_csv(p)
        df = adapters.load_veremi(p)
    schema.validate(df)
    assert list(df.columns) == schema.COLUMNS and len(df) == 60
    assert set(df["attack"]) == {"Genuine", "ConstPos"}
    assert abs(df["heading"].iloc[0]) < 1e-12 and abs(df["acl"].iloc[0] - 0.5) < 1e-12
    assert df["track"].nunique() == 2


def test_tampa_adapter_synthetic_units():
    base = dict(metadata_RSUID="thea1", coreData_id=777, coreData_lat=279500000, coreData_long=-824500000,
                coreData_accelset_yaw=100, coreData_accelset_long=50, coreData_speed=500,
                coreData_heading=7200)    # 10 m/s, 90 deg compass = East
    rows = []
    for i in range(5):
        r = dict(base, metadata_recordGeneratedAt="03/19/2021 05:14:5%d AM" % i,
                 coreData_secMark=51000 + 100 * i, coreData_msgCnt=i)
        rows.append(r)
    rows.append(dict(rows[0]))                         # duplicate heard by a second RSU
    rows.append(dict(base, metadata_recordGeneratedAt="03/19/2021 05:20:00 AM", coreData_secMark=5000,
                     coreData_msgCnt=9, coreData_speed=8191))             # unavailable speed -> dropped
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.csv"
        pd.DataFrame(rows).to_csv(p, index=False)
        df = adapters.load_tampa(p)
    schema.validate(df)
    assert len(df) == 5
    assert abs(df["speed"].iloc[0] - 10.0) < 1e-9
    assert abs(df["heading"].iloc[0]) < 1e-9 and abs(df["vx"].iloc[0] - 10.0) < 1e-9   # East
    assert abs(df["acl"].iloc[0] - 0.5) < 1e-12 and df["yaw_rate"].iloc[0] < 0          # clockwise
    assert abs(df["t"].iloc[1] - df["t"].iloc[0] - 0.1) < 1e-9


def test_tampa_real_file_if_present():
    if not adapters.TAMPA_CSV.exists():
        return
    df = adapters.load_tampa()
    schema.validate(df)
    assert 30 <= df["sender"].nunique() <= 60 and len(df) < 20000 and df["speed"].max() < 60      # passages, deduplicated
    old = adapters.load_tampa_v1()
    schema.validate(old)
    assert old["sender"].nunique() > 200 and len(old) > 30000                                  # legacy: ids per RSU


def test_v2aix_missing_data_raises():
    """The real V2AIX adapter (WP5 S0c, v2x/v2aix.py) raises when nothing is extracted (tested on an empty folder)."""
    with tempfile.TemporaryDirectory() as d:
        try:
            adapters.load_v2aix(Path(d))
        except schema.DataNotAvailableError as e:
            assert "not extracted" in str(e)
        else:
            raise AssertionError("must raise")


def test_validate_rejects_bad_tables():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "v.csv"
        _veremi_csv(p)
        df = adapters.load_veremi(p)
    bad = df.copy()
    bad.loc[0, "x"] = np.nan
    for b in (bad, df.assign(speed=-1.0), df.drop(columns=["acl"]), df.assign(msg_id="a")):
        try:
            schema.validate(b)
        except ValueError:
            continue
        raise AssertionError("should fail")


def _fake_veremi(n_blocks=10, per_block=40):
    rows = []
    for b in range(n_blocks):
        for k in range(per_block):
            t0 = b * 1800 + 10 + k * 40
            rows += [dict(sender=str(b * 1000 + k), t=t0), dict(sender=str(b * 1000 + k), t=t0 + 60)]
    # one sender crossing a block boundary
    rows += [dict(sender="cross", t=1790.0), dict(sender="cross", t=1810.0)]
    return pd.DataFrame(rows)


def test_time_block_split_disjoint_and_guarded():
    df = _fake_veremi()
    split, info = splitting.veremi_time_block_split(df)
    allids = [s for v in split.values() for s in v]
    assert len(allids) == len(set(allids))
    assert "cross" not in allids and "cross" in info["dropped_senders"]
    # no sender of one part is on air in a time block of another part
    part_of = {s: p for p, v in split.items() for s in v}
    blk = {s: int(g["t"].min() // 1800) for s, g in df.groupby("sender") if s in part_of}
    for p, q in (("train", "val"), ("train", "test"), ("val", "test")):
        assert not ({blk[s] for s in split[p]} & {blk[s] for s in split[q]})


def test_tampa_vehicle_split_disjoint():
    df = pd.DataFrame({"sender": [str(i // 3) for i in range(60)]})
    sp = splitting.tampa_vehicle_split(df)
    ids = [s for v in sp.values() for s in v]
    assert len(ids) == len(set(ids)) == 20


def test_saved_splits_if_present():
    for name in ("splits_veremi.json", "splits_tampa.json"):
        p = RESULTS / "WP5" / name
        if not p.exists():
            continue
        sp = json.loads(p.read_text())
        ids = [s for k in ("train", "val", "test") for s in sp[k]]
        assert len(ids) == len(set(ids)) and all(len(sp[k]) > 0 for k in ("train", "val", "test"))
