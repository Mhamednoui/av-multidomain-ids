"""Paths, seed and false-alarm budgets shared by every v3 module.

Inputs: environment variables AVIDS_DATA, AVIDS_DATA_EXTRA (optional).
Outputs: constants only. Reference: ARCHITECTURE.md section 4.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("AVIDS_DATA", ROOT.parent / "codes" / "data"))
DATA_EXTRA = Path(os.environ.get("AVIDS_DATA_EXTRA", ROOT.parent / "data_extra"))
RESULTS = ROOT / "results"
SEED = 42

BUDGET_DOMAIN = 0.01   # false alarms allowed on normal validation samples, per domain / layer
BUDGET_SYSTEM = 0.02   # same, at system level

# per-dataset locations (DATASETS.md); datasets live in two places (S1 report, item 7)
DATASET_PATHS = {
    "D01_cicids2017_sample": DATA / "CICIDS2017_sample.csv",
    "D02_car_hacking": DATA,
    "D03_av_gps": DATA / "AV-GPS-Dataset",
    "D04_kitti_raw_a": DATA / "Depth",            # drives 0001, 0015
    "D04_kitti_raw_b": DATA_EXTRA / "kitti_raw",  # the 21 other drives
    "D05_road": DATA_EXTRA / "road" / "road",
    "D06_gps_uav": DATA_EXTRA / "gps_uav",
}


def results_dir(wp: str) -> Path:
    d = RESULTS / wp
    d.mkdir(parents=True, exist_ok=True)
    return d
