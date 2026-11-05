"""Tests of the WP9 B4 libraries (tools/WP9_B4_gps_lib.py, WP9_B4_lidar_lib.py): F1, derived GPS features, cluster bootstrap, tie-safe thresholds, drive bootstrap, AV-GPS lock."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import WP9_B4_gps_lib as G
import WP9_B4_lidar_lib as D


def test_f1_at():
    m = G.f1_at([1, 1, 0, 0, 0], [1, 0, 1, 0, 0])
    assert m["tp"] == 1 and m["fp"] == 1 and m["fn"] == 1 and m["tn"] == 2
    assert abs(m["f1"] - 0.5) < 1e-9 and abs(m["fpr"] - 1 / 3) < 1e-9


def test_derived_step_and_speed_gap():
    lat = 32.0 + np.arange(6) * (3.0 / G.M_PER_DEG)          # 3 m north per row
    g = pd.DataFrame({"GPS Latitude": lat, "GPS Longitude": np.full(6, -110.0), "Velocity (m/s)": np.full(6, 3.0), "Heading (deg)": np.zeros(6)})
    d = G.derived(g)
    assert np.isnan(d.pos_step_m.iloc[0]) and np.allclose(d.pos_step_m.iloc[1:], 3.0, atol=1e-6)
    assert np.allclose(d.speed_gap.iloc[1:], 0.0, atol=1e-6) and np.allclose(d.heading_gap.iloc[1:], 0.0, atol=1e-6)


def test_cluster_boot_and_threshold_tie_safe():
    rng = np.random.default_rng(0)
    y = np.r_[np.zeros(300), np.ones(100)]
    s = np.where(y == 1, rng.beta(5, 2, 400), rng.beta(2, 5, 400))
    sess = np.repeat(np.arange(8), 50)
    ci = G.cluster_boot(y, s, s > 0.5, sess, n=200)
    assert ci["auc"][0] <= ci["auc"][1] and 0.5 < ci["auc"][1] <= 1.0
    thr = D.thr_at(np.r_[np.ones(50), np.zeros(950)], 0.05)
    assert (np.r_[np.ones(50), np.zeros(950)] >= thr).mean() <= 0.05


def test_drive_boot_and_class_map():
    ci = D.drive_boot({"a": (5, 10), "b": (9, 10), "c": (1, 10)}, n=300)
    assert 0 <= ci[0] <= ci[1] <= 1
    assert D.cls_of("clean") == 0 and D.cls_of("PointDrop") == 1 and D.cls_of("IntensitySpoof") == 2 and D.cls_of("cmp_boxcloud") == 3 and D.cls_of("ph_replace_near") == 3


def test_locks_disjoint_and_no_h31():
    a = json.loads((ROOT / "locks" / "WP9_avgps.json").read_text())
    for c in ("case_I", "case_II"):
        tr, te = set(a[c]["train"] + a[c]["val"]), set(a[c]["test"] + a[c]["test_normal_only_extra"])
        assert not tr & te
    k = json.loads((ROOT / "locks" / "WP9_kitti.json").read_text())
    ds = {p: set(v["drives"]) for p, v in k["parts"].items()}
    assert not (ds["train"] & ds["val"] or ds["train"] & ds["test"] or ds["val"] & ds["test"])
    h31 = {x["drive"] for x in json.loads((ROOT / "locks" / "H31.json").read_text())["domains"]["kitti_vehicle_block"]["drives"]}
    assert not (set().union(*ds.values()) & {d.split("_")[-1] for d in h31})
