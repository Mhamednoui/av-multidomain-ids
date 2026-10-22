"""WP2 S7: shared definitions of the ROAD units, folds and loaders (cache ../data_extra/WP2_S7_cache).

Units: 6 dyno captures + 4 time blocks of the real-road highway_long drive (LOCO folds), exercise_all_bits (fit only).
Blocks: 4 equal parts of the highway drive, 30 s cut at each interior boundary (belongs to neither fit nor scoring).
Attack captures (train / val / test), the two sets of ambient test captures and the 4 accelerator captures are loaded as whole captures.
Inputs: ../data_extra/WP2_S2_cache/road (t, id, dlc, label), ../data_extra/WP2_S4_cache/road (payload bytes), ROAD logs (accelerator).
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import adapters as A
from can.stack_core import UnitData, slice_unit
from common.config import DATA_EXTRA, RESULTS

CACHE = DATA_EXTRA / "WP2_S7_cache"
S2 = DATA_EXTRA / "WP2_S2_cache" / "road"
S4 = DATA_EXTRA / "WP2_S4_cache"
S5 = DATA_EXTRA / "WP2_S5_cache"
OUT = RESULTS / "WP2"
HW = "ambient_highway_street_driving_long"
DYNO = ["ambient_dyno_drive_basic_long", "ambient_dyno_drive_extended_long", "ambient_dyno_drive_radio_infotainment",
        "ambient_dyno_idle_radio_infotainment", "ambient_dyno_drive_basic_short", "ambient_dyno_drive_winter"]
EXERCISE = "ambient_dyno_exercise_all_bits"
BLOCKS = [f"hw_block{k}" for k in range(4)]
FOLDS = DYNO + BLOCKS
AMB_UNITS = FOLDS + [EXERCISE]
BLOCK_GAP = 30.0
FAMS = ["correlated_signal", "max_speedometer", "reverse_light_off", "reverse_light_on", "fuzzing"]
ACCEL = ["accelerator_attack_drive_1", "accelerator_attack_drive_2", "accelerator_attack_reverse_1", "accelerator_attack_reverse_2"]


def attack_names(inst):
    out = []
    for f in FAMS:
        out.append(f"{f}_attack_{inst}")
        if f != "fuzzing":
            out.append(f"{f}_attack_{inst}_masquerade")
    return out


VAL_ATTACK = attack_names(1) + attack_names(2)
TEST_ATTACK = [f"{f}_attack_3" for f in FAMS] + [f"{f}_attack_3_masquerade" for f in FAMS if f != "fuzzing"] + \
              ["max_engine_coolant_temp_attack", "max_engine_coolant_temp_attack_masquerade"]
TEST_AMB = ["ambient_dyno_drive_benign_anomaly", "ambient_dyno_drive_extended_short", "ambient_dyno_reverse",
            "ambient_highway_street_driving_diagnostics"]
TEST = TEST_ATTACK + TEST_AMB
MASQ_TEST = [n for n in TEST_ATTACK if n.endswith("_masquerade")]


def twin(name):
    """Capture that shares the lead (original <-> masquerade copy)."""
    return name[:-len("_masquerade")] if name.endswith("_masquerade") else name + "_masquerade"


def base_of(name):
    return name[:-len("_masquerade")] if name.endswith("_masquerade") else name


def load_capture(name) -> UnitData:
    if name in ACCEL:
        p = A.road_parse_log(A.ROAD / "attacks" / f"{name}.log")
        return UnitData(name, p["t"], p["id"].astype(np.int32), p["dlc"].astype(np.int8), np.maximum(p["B"], 0).astype(np.uint8),
                        np.zeros(len(p["t"]), np.int8))
    z = np.load(S2 / (name + ".npz"))
    B = np.load(S4 / "road" / (name + ".npy"))
    return UnitData(name, z["t"], z["id"], z["dlc"], B, z["label"])


def block_ranges(tm):
    """Frame index ranges [i0, i1) of the four highway blocks."""
    T = tm[-1]
    w = T / 4.0
    out = []
    for k in range(4):
        a = k * w + (BLOCK_GAP / 2 if k > 0 else 0.0)
        b = (k + 1) * w - (BLOCK_GAP / 2 if k < 3 else 0.0)
        out.append((int(np.searchsorted(tm, a, "left")), int(np.searchsorted(tm, b, "left")) if k < 3 else len(tm)))
    return out


_HW = {}


def load_unit(name) -> UnitData:
    if name in BLOCKS:
        if "u" not in _HW:
            _HW["u"] = load_capture(HW)
        U = _HW["u"]
        i0, i1 = block_ranges(U.tm)[BLOCKS.index(name)]
        return slice_unit(U, i0, i1, name)
    return load_capture(name)


def regime_of(name):
    return "road" if name in BLOCKS else "dyno"


def dump_json(obj, path):
    import json

    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, default=conv))
