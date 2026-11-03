"""WP8 S1, G1 guard: every H31 group is rejected by tools/WP8_lib.assert_not_h31; V31_val material is accepted."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import WP8_lib as L  # noqa: E402


def _rejected(item):
    try:
        L.assert_not_h31([item])
    except L.H31Leak:
        return True
    return False


def test_h31_group_counts_match_lock():
    h31 = L._load(L.H31_LOCK)
    assert len(h31["domains"]["kitti_vehicle_block"]["drives"]) == 13
    d = h31["domains"]["comma_vehicle_block"]
    assert len(d["rav4"]["routes"]) == 21 and len(d["civic"]["routes"]) == 16
    assert len(h31["domains"]["v2x"]["fresh"]["v2aix"]["recordings"]) == 674


def test_every_h31_group_is_rejected():
    h31 = L._load(L.H31_LOCK)
    v_ids, _ = L._v31_ids_and_paths(L._load(L.V31_LOCK))
    groups = L._h31_group_ids(h31) - v_ids
    assert len(groups) >= 13 + 37 + 674
    for g in sorted(groups):
        assert _rejected(g), f"H31 group not rejected: {g}"


def test_h31_group_in_folder_and_path_form_is_rejected():
    h31 = L._load(L.H31_LOCK)
    for dr in h31["domains"]["kitti_vehicle_block"]["drives"]:
        assert _rejected(f"../data_extra/D04b_kitti_raw_v31/{dr['drive']}_sync/oxts/data/0000000017.txt")
    for side in ("rav4", "civic"):
        for r in h31["domains"]["comma_vehicle_block"][side]["routes"]:
            assert _rejected(f"../data_extra/D22_comma2k19/Chunk_2/{r.replace('|', '_')}/3/processed_log/CAN/x")
    for rec in h31["domains"]["v2x"]["fresh"]["v2aix"]["recordings"]:
        assert _rejected(f"../data_extra/D13_v2aix/extracted_v31/{rec['member']}")


def test_h31_only_files_are_rejected():
    _, paths = L.h31_only()
    assert paths, "expected H31-only CAN files"
    h31 = L._load(L.H31_LOCK)
    for f in h31["domains"]["can"]["reused"]["road_test"]:
        assert _rejected(f["path"]), f["path"]
    for f in h31["domains"]["can"]["reused"]["d11_test"]:
        assert _rejected(f["path"]), f["path"]
    for f in h31["domains"]["can"]["fresh"]["road_accelerator"]["files"]:
        assert _rejected(f["path"]), f["path"]


def test_guard_accepts_v31_material():
    v31 = L._load(L.V31_LOCK)
    accepted = [
        "../codes/data/Depth/2011_09_26_drive_0001_sync",
        "b0c9d2329ad1606b_2018-08-10--22-42-26",
        "99c94dc769b5d96e|2018-05-01--08-13-53",
        "../data_extra/road/road/ambient/ambient_dyno_drive_basic_short.log",
    ]
    for f in v31["domains"]["can"]["road_val"]:
        accepted.append(f["path"])
    for it in accepted:
        L.assert_not_h31([it])


def test_guard_accepts_non_group_input():
    L.assert_not_h31(["cpu", "5 %", "../data_extra/D22_comma2k19/Chunk_1/x"])
