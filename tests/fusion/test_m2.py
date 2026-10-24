"""Tests for WP6 S5 tools/WP6_S5_lib.py: group folds (disjoint, every fold has clean material, one KITTI val drive per fold) and the frozen M2 system file."""
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def test_folds_are_group_disjoint_and_have_clean_groups():
    import WP6_S5_lib as L
    if not (L.CACHE / "s5_v2x.pkl").exists():
        print("skip: no S5 cache")
        return
    u = L.load_unique("val")
    folds = L.make_folds(u)
    assert len(set(folds["gps"].values())) == 3 and len(folds["gps"]) == 3
    for k in ("can", "network", "v2x", "cross_comma"):
        groups = {s["group"] for s in u[k]["series"]}
        assert set(folds[k]) == groups
        for f in range(L.N_FOLDS):
            assert any(s["kind"] == "clean" and folds[k][s["group"]] == f for s in u[k]["series"]), (k, f)
    g = L.groups_of(folds, {0}, "K")
    assert g["gps"] == g["cross"] == g["lidar"]


def test_frozen_m2_system_loads():
    p = ROOT / "results" / "WP6" / "m2_system.pkl"
    if not p.exists():
        print("skip: M2 not frozen yet")
        return
    m = pickle.load(open(p, "rb"))
    assert set(m) == {"K", "C"}
    assert m["K"].entries == ["gps", "lidar", "can", "network", "v2x", "cross"] and m["C"].entries == ["can", "network", "v2x", "cross"]
    for s in m.values():
        assert s.fusion.method in ("max", "noisy_or") and s.fusion.threshold is not None and s.fusion.model is None
