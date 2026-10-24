"""Unit tests for tools/WP6_S4_lib.py (WP6 S4 zero-day v3): held-out categories, variants, novelty columns, vectorised bootstrap."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
import WP6_S3_lib as L3  # noqa: E402
import WP6_S4_lib as L  # noqa: E402
from fusion import streams as ST  # noqa: E402


def test_categories_follow_the_pre_registered_held_out_lists():
    assert L.category("doppler_spoof", "gps") == "heldout" and L.category("drift", "gps") == "seen"
    assert L.category("max_speedometer_masquerade", "can") == "heldout" and L.category("max_speedometer", "can") == "seen"
    assert L.category("PortScan", "network") == "heldout" and L.category("DoS-Hulk", "network") == "seen"
    assert L.category("17_DataReplaySybil", "v2x") == "heldout" and L.category("01_ConstPos", "v2x") == "seen"
    assert L.category("PointDrop", "lidar") == "lidar_labelfree" and L.category("can_scale", "cross") == "choice_seen"
    assert L.category("gps_can", "gps+can") == "choice_seen" and L.category("none", None) is None
    assert L.domain_category_fn("cross")("meaconing") == "heldout" and L.domain_category_fn("gps")("gps_can") == "choice_seen"


def test_variants_have_the_expected_entries_and_no_lidar_novelty():
    v = L.variant("K", "noisy_or", "H+L3", "mcd")
    names = [e[0] for e in v["entries"]]
    assert names[:6] == ["gps", "lidar", "can", "network", "v2x", "cross"] and "lidar.nov" not in names and "gps.nov" in names
    assert dict((e[0], e[2]) for e in v["entries"])["network"] == L.NET_ZD and dict((e[0], e[2]) for e in v["entries"])["lidar"] == ["lidar.l1_union"]
    assert [e[0] for e in L.variant("C", "max", "H", None)["entries"]] == ["can", "network", "v2x", "cross"]
    assert [e[0] for e in L.variant("K", "max", "H", None, groups="l3")["entries"]] == ["gps", "can", "network", "v2x"]


def _pack(rng, key, m=4, n_series=4, n=40):
    ser = []
    for i in range(n_series):
        lay = np.clip(rng.random((n, m)) * 0.9, 0, 0.99)
        ser.append(ST.series(f"g{i}", f"s{i}", "clean", "none", lay.max(axis=1), lay, np.zeros(n, bool)))
    return {"domain": key, "layer_names": [f"{key}.l{j}" for j in range(m)], "layer_thr": np.full(m, 0.99), "dom_thr": 0.99, "series": ser}


def test_attach_novelty_appends_two_columns_without_touching_the_input():
    rng = np.random.default_rng(0)
    u = {"gps": _pack(rng, "gps"), "can": _pack(rng, "can", 3), "network": _pack(rng, "network", 7), "v2x": _pack(rng, "v2x", 5),
         "cross_kitti": _pack(rng, "cross", 3), "cross_comma": _pack(rng, "cross", 3), "lidar": _pack(rng, "lidar", 2)}
    u["network"]["layer_names"] = L.NET_H + ["net.dos_rate"] + L.NET_L3
    gA = {k: {"g0", "g1", "g2"} for k in u}
    dets, oof = L.fit_novelty(u, gA)
    out = L.attach_novelty(u, dets, oof)
    assert out["lidar"] is u["lidar"]
    for k in ("gps", "can", "network", "v2x", "cross_kitti", "cross_comma"):
        assert out[k]["series"][0]["layers"].shape[1] == u[k]["series"][0]["layers"].shape[1] + 2
        assert u[k]["series"][0]["layers"].shape[1] == len(u[k]["layer_names"])
        assert out[k]["layer_names"][-2:] == ["nov.mcd", "nov.iforest"] and len(out[k]["layer_thr"]) == len(out[k]["layer_names"])
    assert dets[("network", "mcd")][1] == [u["network"]["layer_names"].index(n) for n in L.NET_ZD]     # dos_rate is not a novelty feature


def test_fast_ci_matches_the_s3_bootstrap_scale():
    rng = np.random.default_rng(1)
    outs = []
    for v in range(6):
        for _ in range(30):
            outs.append({"family": "none", "vehicle": f"v{v}", "n": 20, "alarm_ticks": int(rng.integers(0, 2)), "detected": False})
        for _ in range(30):
            outs.append({"family": "f1", "vehicle": f"v{v}", "n": 20, "alarm_ticks": 0, "detected": bool(rng.random() < 0.5)})
    a, b = L.fast_ci(outs, ["f1"]), L3.cluster_ci(outs, ["f1"], n_boot=500)
    for k in ("fa_tick", "mean_detection"):
        assert abs(a[k][0] - b[k][0]) < 0.06 and abs(a[k][1] - b[k][1]) < 0.06
