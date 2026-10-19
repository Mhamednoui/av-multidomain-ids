"""Dataset adapters for CAN: ROAD, Car-Hacking, can-train-and-test (D11) -> unified frame tables.

Each adapter returns DataFrames in the format of can/frames.py. Raw files are untrusted data:
they are only parsed as text, never executed.

ROAD (ORNL, D05, CC BY 4.0): parse_log / family / attack_split / label_attack are COPIED from
  ../codes_v2/can/road_external.py (frame labels from capture_metadata.json, checked against
  signal_extractions). Decoded signals: signal_extractions/*.csv (no DBC package needed).
Car-Hacking (HCRL, D02): load logic copied from ../codes_v2/can/features.py (load_file).
D11 can-train-and-test (DTU, Lampe & Meng 2023, arXiv 2308.04972, CC BY 4.0): columns
  timestamp, arbitration_id (hex), data_field (hex), attack (0/1); there is NO DLC column, dlc is
  derived as len(data_field) / 2 (after stripping whitespace; one file has a trailing tab).
  Frames are kept in the recorded order (timestamps have sub-ms inversions near injected frames).
References: Verma et al. 2020 (ROAD); Seo et al. 2018 / Song et al. 2020 (Car-Hacking).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from can.frames import BYTE_COLS, hex_to_bytes, make_frame
from common.config import DATA, DATA_EXTRA, RESULTS

ROAD = DATA_EXTRA / "road" / "road"
D11 = DATA_EXTRA / "D11_can-train-and-test" / "can-train-and-test"
ROAD_VEHICLE = "ROAD_vehicle"          # one (unnamed) car, per the ROAD readme
CARHACKING_VEHICLE = "CarHacking_vehicle"   # one car; model not stated in the files
CARHACKING_FILES = {"DoS": "DoS_dataset.csv", "Fuzzy": "Fuzzy_dataset.csv",
                    "RPM": "RPM_dataset.csv", "Gear": "gear_dataset.csv"}

# ---------------------------------------------------------------- ROAD
ROAD_FAMILIES = ("correlated_signal", "max_speedometer", "max_engine_coolant_temp",
                 "reverse_light_off", "reverse_light_on", "fuzzing", "accelerator")
ROAD_AMB_TEST = ["ambient_dyno_drive_extended_short", "ambient_dyno_drive_benign_anomaly",
                 "ambient_highway_street_driving_diagnostics", "ambient_dyno_reverse"]
ROAD_AMB_VAL = ["ambient_dyno_drive_basic_short", "ambient_dyno_drive_winter"]


def road_family(name: str) -> str:
    for f in ROAD_FAMILIES:
        if name.startswith(f):
            return f
    raise ValueError(name)


def road_attack_split(name: str) -> str:
    """v2 rule: instance 1 -> train, 2 -> val, 3 -> test; the single coolant capture -> test."""
    if road_family(name) == "max_engine_coolant_temp":
        return "test"
    inst = [c for c in name.replace("_masquerade", "").split("_") if c.isdigit()][-1]
    return {"1": "train", "2": "val", "3": "test"}[inst]


def road_label_attack(d: pd.DataFrame, meta: dict) -> np.ndarray:
    """Injected-frame mask from capture_metadata.json (v2 logic; d needs t, id, b0..b7)."""
    a, b = meta["injection_interval"]
    m = (d["t"] >= a - 1e-6).to_numpy() & (d["t"] <= b + 1e-6).to_numpy()
    if meta["injection_id"] != "XXX":
        m &= (d["id"] == int(meta["injection_id"], 16)).to_numpy()
    pat = meta["injection_data_str"]
    for i in range(8):
        h = pat[2 * i:2 * i + 2]
        if h != "XX":
            m &= (d[f"b{i}"] == int(h, 16)).to_numpy()
    return m


def road_parse_log(path: Path) -> dict:
    """candump text '(time) bus ID#PAYLOAD' -> t (relative), id, dlc, B."""
    raw = pd.read_csv(path, sep=" ", header=None, names=["t", "bus", "frame"], dtype=str)
    t = raw["t"].str.strip("()").astype(float).to_numpy()
    idp = raw["frame"].str.split("#", n=1, expand=True)
    ids = idp[0].map(lambda s: int(s, 16)).to_numpy()
    dlc, B = hex_to_bytes(idp[1].fillna(""))
    return {"t": t - t[0], "id": ids, "dlc": dlc, "B": B}


def road_captures() -> pd.DataFrame:
    """Table of ROAD captures: name, family, kind (ambient / attack / masquerade), part, usable,
    path, meta. accelerator captures have no injected frames (usable=False, v2 skipped them)."""
    rows = []
    amb = json.load(open(ROAD / "ambient" / "capture_metadata.json"))
    for name in amb:
        part = "test" if name in ROAD_AMB_TEST else "val" if name in ROAD_AMB_VAL else "train"
        rows.append((name, "ambient", "ambient", part, True, ROAD / "ambient" / f"{name}.log", None))
    att = json.load(open(ROAD / "attacks" / "capture_metadata.json"))
    for name, meta in att.items():
        fam = road_family(name)
        if fam == "accelerator":
            rows.append((name, fam, "attack", "unused", False, ROAD / "attacks" / f"{name}.log", meta))
            continue
        kind = "masquerade" if name.endswith("_masquerade") else "attack"
        rows.append((name, fam, kind, road_attack_split(name), True, ROAD / "attacks" / f"{name}.log", meta))
    return pd.DataFrame(rows, columns=["name", "family", "kind", "part", "usable", "path", "meta"])


def load_road(name: str, caps: pd.DataFrame = None) -> pd.DataFrame:
    """One ROAD capture as a unified frame table."""
    caps = road_captures() if caps is None else caps
    r = caps[caps["name"] == name].iloc[0]
    p = road_parse_log(r["path"])
    d = pd.DataFrame({"t": p["t"], "id": p["id"]})
    for i in range(8):
        d[f"b{i}"] = p["B"][:, i]
    lab = np.zeros(len(d), dtype=bool)
    if r["meta"] is not None and r["usable"]:
        lab = road_label_attack(d, r["meta"])
    attack = np.where(lab, r["family"] + ("_masquerade" if r["kind"] == "masquerade" else ""), "normal")
    return make_frame(p["t"], p["id"], p["dlc"], p["B"], lab, attack, name, ROAD_VEHICLE)


def road_signals_path(name: str) -> Path:
    for sub in ("attacks", "ambient"):
        f = ROAD / "signal_extractions" / sub / f"{name}.csv"
        if f.exists():
            return f
    raise FileNotFoundError(name)


def load_road_signals(name: str) -> pd.DataFrame:
    """Decoded signals of a capture (signal_extractions CSV): Label, Time, ID, Signal_1..22_of_ID.
    Signal meaning: anonymized.dbc (signal_extractions/DBC). Label is ROAD's own (masquerade
    captures only carry attack labels)."""
    return pd.read_csv(road_signals_path(name))


def road_label_check(name: str, d: pd.DataFrame) -> dict:
    """Our injected count vs ROAD's own label sum in signal_extractions (masquerade only)."""
    f = ROAD / "signal_extractions" / "attacks" / f"{name}.csv"
    if not f.exists():
        return None
    lab = pd.read_csv(f, usecols=["Label"])["Label"]
    return {"ours": int(d["label"].sum()), "road_signal_labels": int(lab.sum())}


# ---------------------------------------------------------------- Car-Hacking
def load_carhacking(name: str, nrows=None) -> pd.DataFrame:
    """One Car-Hacking file (Timestamp, ID hex, DLC, DLC data bytes, flag R/T) -> unified frame.
    Recorded order kept. Attack name = file key ('DoS', 'Fuzzy', 'RPM', 'Gear')."""
    raw = pd.read_csv(DATA / CARHACKING_FILES[name], header=None, names=list(range(12)), dtype=str,
                      nrows=nrows)
    dlc = raw[2].astype(int).to_numpy()
    vals = raw.iloc[:, 3:12].to_numpy()
    flag = vals[np.arange(len(raw)), dlc]                # flag sits right after the last data byte
    B = np.full((len(raw), 8), -1, dtype=np.int16)
    for i in range(8):
        col = pd.Series(vals[:, i]).where(i < dlc)
        B[:, i] = col.map(lambda s: int(s, 16) if isinstance(s, str) else -1).to_numpy()
    t = raw[0].astype(float).to_numpy()
    ids = raw[1].map(lambda s: int(s, 16)).to_numpy()
    lab = flag == "T"
    return make_frame(t - t[0], ids, dlc, B, lab, np.where(lab, name, "normal"), name, CARHACKING_VEHICLE)


# ---------------------------------------------------------------- D11
D11_VEHICLES = {"set_01": ("Impala", "Silverado"), "set_02": ("Traverse", "Subaru"),
                "set_03": ("Silverado", "Subaru"), "set_04": ("Subaru", "Traverse")}   # (known, unknown)
D11_SUBSETS = ["train_01", "test_01_known_vehicle_known_attack", "test_02_unknown_vehicle_known_attack",
               "test_03_known_vehicle_unknown_attack", "test_04_unknown_vehicle_unknown_attack"]
D11_EPOCH = 1672531200.0


def d11_vehicle_by_readme(set_name: str, subset: str) -> str:
    """README mapping: train_01 and test_01 / test_03 = known vehicle, test_02 / test_04 = unknown.
    Set-level information only; see notes/WP2_can.md for the contradictions it contains."""
    known, unknown = D11_VEHICLES[set_name]
    return unknown if subset.startswith(("test_02", "test_04")) else known


def d11_attack_of(fname: str) -> str:
    """Attack name from the file name 'DoS-3.csv' -> 'DoS'. accessory / attack-free / *-accessory
    files have no injected frames."""
    return fname.rsplit(".", 1)[0].rsplit("-", 1)[0]


def d11_file_table(root: Path = D11) -> pd.DataFrame:
    rows = []
    for p in sorted(root.glob("set_*/*/*.csv")):
        s, sub = p.parent.parent.name, p.parent.name
        stem = p.stem
        fam, num = stem.rsplit("-", 1)
        rows.append((f"{s}/{sub}/{stem}", s, sub, "train" if sub == "train_01" else "test", fam, int(num),
                     fam in ("accessory", "attack-free", "rpm-accessory", "speed-accessory"),
                     d11_vehicle_by_readme(s, sub), p))
    ft = pd.DataFrame(rows, columns=["capture", "set", "subset", "role", "attack_family", "number",
                                     "no_attack_family", "vehicle_readme", "path"])
    # checked vehicle (tools/WP2_S1_d11_splits.py): ID-set fingerprints; README mapping where unchecked
    vf = RESULTS / "WP2" / "s1_d11_vehicles.json"
    if vf.exists():
        vt = json.load(open(vf))
        ft["vehicle"] = [vt[c]["vehicle"] for c in ft["capture"]]
        ft["vehicle_source"] = [vt[c]["source"] for c in ft["capture"]]
    else:
        ft["vehicle"], ft["vehicle_source"] = ft["vehicle_readme"], "README set-level only"
    return ft


def load_d11(path: Path, capture: str, vehicle: str) -> pd.DataFrame:
    """One D11 CSV as a unified frame table, in recorded order (no sorting). t = timestamp - epoch.
    dlc = len(data_field) / 2 after stripping whitespace."""
    raw = pd.read_csv(path, dtype={"timestamp": np.float64, "arbitration_id": str, "data_field": str,
                                   "attack": np.int8}, keep_default_na=False)
    uniq = raw["arbitration_id"].str.strip().unique()
    ids = raw["arbitration_id"].str.strip().map({u: int(u, 16) for u in uniq}).to_numpy()
    dlc, B = hex_to_bytes(raw["data_field"])
    lab = raw["attack"].to_numpy()
    fam = d11_attack_of(path.name)
    attack = np.where(lab == 1, fam, "normal")
    return make_frame(raw["timestamp"].to_numpy() - D11_EPOCH, ids, dlc, B, lab, attack, capture, vehicle)


def d11_raw_hex(path: Path) -> pd.Series:
    """data_field exactly as in the file (for the round-trip test)."""
    return pd.read_csv(path, usecols=["data_field"], dtype=str, keep_default_na=False)["data_field"]
