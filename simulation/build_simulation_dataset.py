"""
Build Simulation Dataset — AV-IDS
===================================
Creates a single wide CSV that represents a realistic AV sensor timeline.
Each row = one "cycle" (one window worth of data across all 4 domains).

Scenario sequence (600 rows each):
  Block 1  : ALL NORMAL          (baseline)
  Block 2  : GPS SPOOFING        (GPS attack only)
  Block 3  : ALL NORMAL          (recovery)
  Block 4  : CAN DoS             (CAN attack only)
  Block 5  : ALL NORMAL          (recovery)
  Block 6  : NETWORK DoS         (Network attack only)
  Block 7  : ALL NORMAL          (recovery)
  Block 8  : MULTI-DOMAIN        (CAN + GPS simultaneous)
  Block 9  : ALL NORMAL          (final baseline)

Total: 5,400 rows

Columns:
  scenario        : block label (e.g. "NORMAL", "GPS_SPOOFING", ...)
  true_attack     : bool — any domain is under attack
  lidar_bin       : path to .bin file for this cycle
  + all CAN raw columns (ID, DATA_0..DATA_7)
  + all GPS raw columns (40 cols)
  + all NET raw columns (43 cols)

Run with:
    python simulation/build_simulation_dataset.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE  = Path(__file__).parent
CODES = HERE.parent
DATA  = CODES / "data"
OUT   = HERE / "simulation_dataset.csv"

RNG = np.random.default_rng(42)

# ── column definitions ────────────────────────────────────────────────────────
CAN_RAW  = ["ID","DATA_0","DATA_1","DATA_2","DATA_3","DATA_4","DATA_5","DATA_6","DATA_7"]
GPS_DROP = ["Clock Time","GPS MGRS","Hobbs","Data Type","Hobbs Time","Arming State","Flight Mode"]
GPS_COLS = ['Roll (deg)','Pitch (deg)','Heading (deg)','Yaw (deg)','Yaw Rate (deg/s)',
            'Velocity (m/s)','Steering Angle (deg)','Relative Altitude (m)','Altitude AMSL (m)',
            'Altitude Tuning','Altitude Tuning Setpoint','X-Track Error (m)',
            'Travelled Distance (m)','Run Time','Distance To Home (m)','Mission Index',
            'Heading To Next WP (deg)','Heading To Home (deg)','Distance To GCS (m)',
            'Throttle (%)','Clock Date','GPS Latitude','GPS Longitude','GPS HDOP','GPS VDOP',
            'GPS Course','Satellite Locks','Satellite Count','Longitudinal Position (m)',
            'Lateral Position (m)','Vertical Position (m)','Longitudinal Velocity (m/s)',
            'Absolute Longitudinal Velocity (m/s)','Lateral Velocity (m/s)',
            'Absolute Lateral Velocity (m/s)','Vertical Velocity (m/s)','Temperature (F)',
            'Longitudinal Vibration','Lateral Vibration','Vertical Vibration']

NET_FEATS = json.load(open(CODES / "network" / "network_features.json"))

BLOCK_SIZE = 600          # 9 blocks x 600 = 5,400 rows

SCENARIOS = [
    ("NORMAL",       False, False, False),   # block 1
    ("GPS_SPOOFING", False, True,  False),   # block 2  — GPS attack
    ("NORMAL",       False, False, False),   # block 3
    ("CAN_DOS",      True,  False, False),   # block 4  — CAN attack
    ("NORMAL",       False, False, False),   # block 5
    ("NET_DOS",      False, False, True),    # block 6  — Network attack
    ("NORMAL",       False, False, False),   # block 7
    ("MULTI_ATTACK", True,  True,  False),   # block 8  — CAN + GPS
    ("NORMAL",       False, False, False),   # block 9
]
# columns: scenario_name, can_attack, gps_attack, net_attack


# =============================================================================
#  DATA LOADERS
# =============================================================================

def load_can(attack: bool, n: int) -> pd.DataFrame:
    fname = "decimal_DoS.csv" if attack else "decimal_benign.csv"
    df = pd.read_csv(DATA / "CICIoV2024" / "decimal" / fname,
                     encoding="latin-1", nrows=n * 3)[CAN_RAW]
    return df.sample(n, random_state=int(attack)*7+1).reset_index(drop=True)


def load_gps(attack: bool, n: int) -> pd.DataFrame:
    src = 1 if attack else 0
    df  = pd.read_csv(DATA / "AV-GPS-Dataset" / f"AV-GPS-Dataset-{src}.csv")
    d   = df.drop(columns=[c for c in GPS_DROP if c in df.columns], errors="ignore")
    dtype = 1 if attack else 0
    rows = d[df["Data Type"] == dtype]
    if len(rows) < n:
        rows = pd.concat([rows] * (n // len(rows) + 1)).head(n)
    return rows.sample(n, random_state=int(attack)*13+2).reset_index(drop=True)


def load_net(attack: bool, n: int) -> pd.DataFrame:
    df = pd.read_csv(DATA / "CICIDS2017_sample_km_test.csv")
    df = df.replace([np.inf, -np.inf], 0).fillna(0)
    if attack:
        rows = df[df["Label"] != "BENIGN"]
        if len(rows) < n:
            rows = pd.concat([rows] * (n // len(rows) + 1)).head(n)
        return rows[NET_FEATS].sample(n, random_state=17+3).reset_index(drop=True)
    else:
        # Benign rows are sampled as they come.
        #
        # An earlier version of this builder kept only the benign rows that the
        # network detector already classified correctly, which removed that
        # detector's own false positives from the NORMAL blocks and pushed
        # simulation precision to 100%. Screening out precisely the inputs the
        # weakest detector struggles with flatters the result and hides a real
        # deployment cost, so the filter was removed. See thesis Section 5.7.1.
        rows = df[df["Label"] == "BENIGN"][NET_FEATS]
        if len(rows) < n:
            rows = pd.concat([rows] * (n // len(rows) + 1)).head(n)
        return rows.sample(n, random_state=3).reset_index(drop=True)


def load_lidar_bins(n: int) -> list:
    seq_dirs = [
        DATA/"Depth"/"2011_09_26_drive_0001_sync"/"2011_09_26"
             /"2011_09_26_drive_0001_sync"/"velodyne_points"/"data",
        DATA/"Depth"/"2011_09_26_drive_0015_sync"/"2011_09_26"
             /"2011_09_26_drive_0015_sync"/"velodyne_points"/"data",
    ]
    bins = []
    for d in seq_dirs:
        bins += sorted(d.glob("*.bin"))
    idx = [i % len(bins) for i in range(n)]
    return [str(bins[i]) for i in idx]


# =============================================================================
#  MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  AV-IDS Simulation Dataset Builder")
    print("=" * 60)

    HERE.mkdir(exist_ok=True)
    all_rows = []
    total = len(SCENARIOS) * BLOCK_SIZE

    for block_idx, (scenario, can_atk, gps_atk, net_atk) in enumerate(SCENARIOS):
        n = BLOCK_SIZE
        print(f"\n  Block {block_idx+1:>2}/9  {scenario:<16}  "
              f"CAN={'ATK' if can_atk else 'ok '}  "
              f"GPS={'ATK' if gps_atk else 'ok '}  "
              f"NET={'ATK' if net_atk else 'ok '}  "
              f"({n} rows)")

        can_df   = load_can(can_atk,   n)
        gps_df   = load_gps(gps_atk,   n)
        net_df   = load_net(net_atk,   n)
        lidar_bins = load_lidar_bins(n)

        for i in range(n):
            row = {"scenario": scenario,
                   "true_attack": can_atk or gps_atk or net_atk,
                   "can_attack":  can_atk,
                   "gps_attack":  gps_atk,
                   "net_attack":  net_atk,
                   "lidar_bin":   lidar_bins[i]}

            for col in CAN_RAW:
                row[f"can_{col}"] = can_df.iloc[i][col]

            for col in GPS_COLS:
                row[f"gps_{col}"] = gps_df.iloc[i][col] if col in gps_df.columns else 0.0

            for col in NET_FEATS:
                row[f"net_{col}"] = net_df.iloc[i][col]

            all_rows.append(row)

    df_out = pd.DataFrame(all_rows)
    df_out.to_csv(OUT, index=False)

    print(f"\n  Done. {len(df_out)} rows saved to:")
    print(f"  {OUT}")
    print(f"\n  Scenario breakdown:")
    for s, cnt in df_out["scenario"].value_counts().sort_index().items():
        atk = df_out[df_out["scenario"] == s]["true_attack"].iloc[0]
        tag = "[ATTACK]" if atk else "[normal]"
        print(f"    {s:<20} {cnt:>4} rows  {tag}")
    print("=" * 60)


if __name__ == "__main__":
    main()
