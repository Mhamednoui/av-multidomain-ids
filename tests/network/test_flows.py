"""Tests for network/flows.py: column map, label cleaning, timestamps, v2 cleaning, time split."""
import os

import numpy as np
import pandas as pd

from network import flows as F

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
D23_RAW = os.path.join(ROOT, "..", "data_extra", "D23_cse-cic-ids2018", "raw")


def test_column_map_is_bijection():
    assert len(F.D10_TO_D23) == 76
    assert len(set(F.D10_TO_D23.values())) == 76
    assert F.FEATURES == list(F.D10_TO_D23.values())


def test_d23_tuesday_columns_map():
    p = os.path.join(D23_RAW, "Thuesday-20-02-2018_TrafficForML_CICFlowMeter.csv")
    q = os.path.join(D23_RAW, "Friday-02-03-2018_TrafficForML_CICFlowMeter.csv")
    if not (os.path.exists(p) and os.path.exists(q)):
        return
    tue = [F._norm(c) for c in pd.read_csv(p, nrows=1).columns]
    fri = [F._norm(c) for c in pd.read_csv(q, nrows=1).columns]
    assert len(tue) == 84 and len(fri) == 80
    assert set(tue) - set(fri) == set(F.D23_TUE_EXTRA)          # exactly the 4 id columns are extra
    assert set(F.FEATURES) <= set(tue) and set(F.FEATURES) <= set(fri)
    ren = pd.DataFrame(columns=tue).rename(columns=F.D23_ID_RENAME).columns
    assert {"src_ip", "src_port", "dst_ip", "dst_port", "protocol", "ts_raw", "label_raw"} <= set(ren)


def test_d10_header_maps_to_features():
    p = os.path.join(ROOT, "..", "data_extra", "D10_cicids2017_generated_flows", "extracted", "TrafficLabelling",
                     "Friday-WorkingHours-Morning.pcap_ISCX.csv")
    if not os.path.exists(p):
        return
    cols = [F._norm(c) for c in pd.read_csv(p, nrows=1, encoding_errors="replace").columns]
    assert len(cols) == 85
    ren = pd.DataFrame(columns=cols).rename(columns={**F.D10_ID_RENAME, **F.D10_TO_D23}).columns
    assert set(F.FEATURES) <= set(ren)


def test_clean_label_and_family():
    assert F.clean_label("Web Attack � Brute Force") == "Web Attack - Brute Force"
    assert F.clean_label(" Web Attack – XSS ") == "Web Attack - XSS"
    fam = F.map_family(["BENIGN", "Web Attack � Sql Injection", "DDoS"], "D10")
    assert list(fam) == ["BENIGN", "Web-SQLi", "DDoS-LOIC-HTTP"]
    assert list(F.map_family(["Benign", "Infilteration"], "D23")) == ["BENIGN", "Infiltration"]
    try:
        F.map_family(["nonsense"], "D10")
        assert False
    except ValueError:
        pass
    assert set(F.FAMILY_D10.values()) | set(F.FAMILY_D23.values()) <= set(F.GROUP)


def test_parse_ts_pm_fix():
    t = F.parse_ts(["3/7/2017 8:59", "3/7/2017 1:05", "3/7/2017 12:10", "07/07/2017 15:01:02", "x"], pm_fix=True)
    assert t[0].hour == 8 and t[1].hour == 13 and t[2].hour == 12 and t[3].hour == 15 and t[4] is pd.NaT
    t2 = F.parse_ts(["20/02/2018 08:34:07", "20/02/2018 01:13:00"], pm_fix=True)
    assert t2[0] == pd.Timestamp("2018-02-20 08:34:07") and t2[1] == pd.Timestamp("2018-02-20 13:13:00")
    t3 = F.parse_ts(["20/02/2018 01:13:00"], pm_fix=False)
    assert t3[0].hour == 1


def test_dedup_conflicts():
    h = np.array([1, 1, 2, 3, 3, 3, 4], dtype=np.uint64)
    lab = np.array([0, 0, 0, 0, 1, 1, 0])
    order = np.array([5, 1, 2, 3, 4, 6, 7])
    keep, n_dup, n_conf, kind = F.dedup_conflicts(h, lab, order)
    # rows 0,1 identical -> earlier (row 1, order 1) kept; hash 3 has labels {0,1}: duplicate of row 4/5 removed, then both remaining conflict rows dropped
    assert n_dup == 2 and n_conf == 2
    assert list(keep) == [False, True, True, False, False, False, True]
    assert list(kind) == [1, 0, 0, 2, 2, 1, 0]


def _toy_day():
    t0 = pd.Timestamp("2017-07-05 09:00")
    ts, fam = [], []
    for m in range(0, 300):                      # 5 h, 1 benign flow / minute
        ts.append(t0 + pd.Timedelta(minutes=m)); fam.append("BENIGN")
    for m in range(60, 100):                     # attack window minutes 60-100 (80 flows)
        for k in range(2):
            ts.append(t0 + pd.Timedelta(minutes=m, seconds=10 * k)); fam.append("DoS-Hulk")
    return np.array(ts, dtype="datetime64[ns]"), np.array(fam)


def test_time_split_order_and_gaps():
    ts, fam = _toy_day()
    split, per = F.time_split(ts, fam)
    assert set(split) == {"train", "val", "test", "gap"}
    for p in set(per):
        m = per == p
        t = ts[m]
        s = split[m]
        for a, b in [("train", "val"), ("val", "test"), ("train", "test")]:
            if (s == a).any() and (s == b).any():
                assert t[s == a].max() < t[s == b].min()          # strictly earlier, never random
    # the attack family has flows in train, val and test (cut inside its window)
    for s in ["train", "val", "test"]:
        assert ((split == s) & (fam == "DoS-Hulk")).sum() > 0
    # nothing from the test part lies within 1 minute after the val part inside the same period
    for p in set(per):
        m = per == p
        t = ts[m]; s = split[m]
        if (s == "val").any() and (s == "test").any():
            assert t[s == "test"].min() - t[s == "val"].max() >= np.timedelta64(60, "s")


def test_short_period_goes_to_train():
    t0 = pd.Timestamp("2017-07-05 09:00")
    ts = np.array([t0 + pd.Timedelta(minutes=m) for m in range(5)], dtype="datetime64[ns]")
    split, per = F.time_split(ts, np.array(["BENIGN"] * 5))
    assert set(split) == {"train"}
