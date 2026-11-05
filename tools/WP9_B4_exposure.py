"""WP9 B4: write results/WP9/B4_exposure.json (how often each test set was scored, by what). Run after the tests: python -I -u tools/WP9_B4_exposure.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
exp = {
    "_note": "test material of WP9 B4 and how many times it was scored (rule: each test scored once per model in this step)",
    "avgps_case_I_test": {"sessions": "file-2 sessions (5) + file-3 normal sessions (2) of locks/WP9_avgps.json", "b4_scorings": {"supervised F_full/F_nosat/F_kin/F_kin_noVS/F_pos (one pass)": 1, "v3 GPS layers (one pass)": 1},
                          "earlier": "WP1 S8 external (old split, files 2-3 as test, v3 layers; file 3 contains copies of file 2): exposure of the data n+1 for the v3 layers"},
    "avgps_case_II_test": {"sessions": "all 25 file-1 sessions (+ file-3 normals)", "b4_scorings": {"supervised (one pass)": 1}, "earlier": "file 1 train/val sessions of WP1 (train data, not test)"},
    "kitti_lidar_test_drives": {"drives": ["0001", "0005", "0028", "0039", "0052", "0079", "0095"], "b4_scorings": {"supervised": 1, "supervised_phys_only": 1, "v3.1 LODO scores (WP8 S3 frame, re-used)": 1},
                                 "earlier": "v3 frozen layers scored them in WP3 S4-S9 (one pass per step); v3.1 (WP8 S2-S6) used them as V31_val (tuning material): NOT a fresh test for v3 / v3.1; first scoring for the B4 supervised models"},
    "h31_overlap": 0,
}
(ROOT / "results" / "WP9" / "B4_exposure.json").write_text(json.dumps(exp, indent=1))
print("written")
