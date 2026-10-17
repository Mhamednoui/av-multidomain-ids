"""
Windowed Aggregation Demo — AV-IDS
====================================
Simulates a real-time sensor stream:
  - CAN packets arrive one by one at 5000 pkt/s
  - GPS frames arrive one by one at 10 Hz
  - Network flows arrive one per flow
  - LiDAR scans arrive one per frame

The WindowEngine buffers them and only calls the domain runners when a
full window is ready. This is how the IDS would work in production.

Timeline simulated:
  t=0.000 – 0.500s : BENIGN traffic on all domains (5 CAN windows)
  t=0.500 – 1.000s : CAN DoS ATTACK injected (5 CAN windows)
  t=1.000 – 1.500s : back to BENIGN

Each CAN window = 50 packets (~10ms at 5000 pkt/s)
Each GPS window = 10 frames (1s at 10 Hz)

Run with:
    python windowing/window_demo.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE  = Path(__file__).parent
CODES = HERE.parent
sys.path.insert(0, str(CODES))

from can.can_runner                   import CANDetector
from gps.gps_runner                   import GPSDetector
from network.network_runner           import NetworkDetector
from lidar.lidar_runner               import LiDARDetector
from unsupervised.unsupervised_runner import ZeroDayDetector, _probs_vec
from fusion.fusion_engine             import FusionEngine
from windowing.window_engine          import MultiDomainWindow

DATA = CODES / "data"
RNG  = np.random.default_rng(2025)

CAN_WINDOW  = 50   # packets per window
GPS_WINDOW  = 10   # frames per window
N_WINDOWS   = 15   # total fusion decisions to make


# =============================================================================
#  STREAM GENERATORS
# =============================================================================

def can_stream_benign(n: int):
    """Load n real BENIGN CAN packets from the dataset."""
    df = pd.read_csv(DATA / "CICIoV2024" / "decimal" / "decimal_benign.csv",
                     encoding="latin-1", nrows=n * 2)
    cols = ["ID","DATA_0","DATA_1","DATA_2","DATA_3",
            "DATA_4","DATA_5","DATA_6","DATA_7"]
    return df[cols].sample(n, random_state=1).to_dict(orient="records")


def can_stream_attack(n: int):
    """Load n real DoS CAN packets from the dataset."""
    df = pd.read_csv(DATA / "CICIoV2024" / "decimal" / "decimal_DoS.csv",
                     encoding="latin-1", nrows=n * 2)
    cols = ["ID","DATA_0","DATA_1","DATA_2","DATA_3",
            "DATA_4","DATA_5","DATA_6","DATA_7"]
    return df[cols].sample(n, random_state=2).to_dict(orient="records")


def gps_stream_benign(n: int):
    """Load n real Normal GPS frames."""
    drop = ["Clock Time","GPS MGRS","Hobbs","Data Type","Hobbs Time",
            "Arming State","Flight Mode"]
    df = pd.read_csv(DATA / "AV-GPS-Dataset" / "AV-GPS-Dataset-0.csv")
    d  = df.drop(columns=[c for c in drop if c in df.columns], errors="ignore")
    return d[df["Data Type"] == 0].head(n).to_dict(orient="records")


def gps_stream_attack(n: int):
    """Load n real Spoofing GPS frames."""
    drop = ["Clock Time","GPS MGRS","Hobbs","Data Type","Hobbs Time",
            "Arming State","Flight Mode"]
    df = pd.read_csv(DATA / "AV-GPS-Dataset" / "AV-GPS-Dataset-1.csv")
    d  = df.drop(columns=[c for c in drop if c in df.columns], errors="ignore")
    return d[df["Data Type"] == 1].head(n).to_dict(orient="records")


def net_flow_benign():
    """Return one BENIGN network flow feature dict."""
    feats = json.load(open(CODES / "network" / "network_features.json"))
    df = pd.read_csv(DATA / "CICIDS2017_sample_km_test.csv")
    df = df.replace([np.inf, -np.inf], 0).fillna(0)
    row = df[df["Label"] == "BENIGN"][feats].sample(1, random_state=3).iloc[0]
    return row.to_dict()


def lidar_scan_normal():
    """Return path to one normal LiDAR scan."""
    scan_dir = (DATA / "Depth" / "2011_09_26_drive_0001_sync" / "2011_09_26"
                / "2011_09_26_drive_0001_sync" / "velodyne_points" / "data")
    bins = sorted(scan_dir.glob("*.bin"))
    return str(bins[0])


def compute_zd(zd_det, net_r, can_r, gps_r, lid_r):
    NET_C = ["BENIGN","Bot","BruteForce","DoS","Infiltration","PortScan","WebAttack"]
    CAN_C = ["BENIGN","DoS","GAS","RPM","SPEED","STEERING_WHEEL"]
    GPS_C = ["Normal","Spoofing"]
    LID_C = ["Normal","PointDrop","IntensitySpoof","GhostCluster"]
    vec   = np.concatenate([_probs_vec(net_r, NET_C), _probs_vec(can_r, CAN_C),
                             _probs_vec(gps_r, GPS_C), _probs_vec(lid_r, LID_C)])
    sc    = zd_det.scaler.transform(vec.reshape(1,-1))
    return {
        "anomaly_score": float(zd_det.ocsvm.decision_function(sc)[0]),
        "is_zero_day":   bool(zd_det.ocsvm.predict(sc)[0] == -1),
    }


# =============================================================================
#  MAIN
# =============================================================================

def main():
    print("=" * 65)
    print("  AV-IDS Windowed Aggregation Demo")
    print(f"  CAN window={CAN_WINDOW} pkts  |  GPS window={GPS_WINDOW} frames")
    print(f"  Simulating {N_WINDOWS} fusion decisions")
    print("=" * 65)

    # ── load runners ──────────────────────────────────────────────────────────
    print("\n[1/4] Loading runners ...")
    can_det = CANDetector()
    gps_det = GPSDetector()
    net_det = NetworkDetector()
    lid_det = LiDARDetector()
    zd_det  = ZeroDayDetector(network_det=net_det, can_det=can_det,
                               gps_det=gps_det,    lidar_det=lid_det)
    engine  = FusionEngine(strategy="meta")
    print("  Ready.")

    # ── pre-load streams ──────────────────────────────────────────────────────
    print("\n[2/4] Loading sensor streams ...")
    total_can = N_WINDOWS * CAN_WINDOW
    total_gps = N_WINDOWS * GPS_WINDOW

    # scenario: windows 0-4 benign, 5-9 CAN+GPS attack, 10-14 benign
    can_b = can_stream_benign(total_can)
    can_a = can_stream_attack(total_can)
    gps_b = gps_stream_benign(total_gps)
    gps_a = gps_stream_attack(total_gps)
    net_f = net_flow_benign()
    lid_s = lidar_scan_normal()

    def get_can(window_idx: int, offset: int) -> dict:
        stream = can_a if 5 <= window_idx <= 9 else can_b
        return stream[offset % len(stream)]

    def get_gps(window_idx: int, frame_idx: int) -> dict:
        stream = gps_a if 5 <= window_idx <= 9 else gps_b
        return stream[frame_idx % len(stream)]

    print(f"  CAN: {len(can_b)} benign + {len(can_a)} attack packets loaded")
    print(f"  GPS: {len(gps_b)} benign + {len(gps_a)} attack frames loaded")

    # ── streaming simulation ──────────────────────────────────────────────────
    print("\n[3/4] Simulating stream ...")
    print(f"\n  {'Win':>3}  {'Scenario':<12}  {'CAN Window':>12}  "
          f"{'GPS Window':>12}  {'Fusion':>10}  {'Score':>6}  {'Triggered by'}")
    print(f"  {'-'*75}")

    mdw = MultiDomainWindow(can_size=CAN_WINDOW, gps_size=GPS_WINDOW)

    for w in range(N_WINDOWS):
        scenario = "ATTACK" if 5 <= w <= 9 else "BENIGN"
        sim_time = w * (CAN_WINDOW / 5000.0)   # simulated seconds at 5000 pkt/s

        # -- push CAN packets one by one (simulating 5000 pkt/s stream)
        for i in range(CAN_WINDOW):
            mdw.push_can(get_can(w, w * CAN_WINDOW + i))

        # -- push GPS frames one by one (simulating 10 Hz stream)
        for i in range(GPS_WINDOW):
            mdw.push_gps(get_gps(w, w * GPS_WINDOW + i))

        # -- network flow and LiDAR scan (pass-through, one per window)
        mdw.push_network(net_f)
        mdw.push_lidar(lid_s)

        # -- all domains ready -> flush and run
        if not mdw.all_ready():
            print(f"  {w:>3}  {scenario:<12}  [window not full yet]")
            continue

        inputs = mdw.flush_all()

        # run domain runners on the window
        can_r = can_det.predict(inputs["can"])[-1]   # use last packet prediction
        gps_r = gps_det.predict(inputs["gps"])[-1]
        net_r = net_det.predict(inputs["network"])[0]
        lid_r = lid_det.predict_one(inputs["lidar"])
        zd_r  = compute_zd(zd_det, net_r, can_r, gps_r, lid_r)
        alert = engine.predict(net_r, can_r, gps_r, lid_r, zd_r)

        triggered = "|".join(alert.triggered_by) if alert.triggered_by else "-"
        can_lbl  = can_r["label_name"]
        gps_lbl  = gps_r.get("label") or gps_r.get("label_name", "?")

        print(f"  {w:>3}  {scenario:<12}  {can_lbl:>12}  {gps_lbl:>12}  "
              f"{alert.threat_label:>10}  {alert.attack_score:>6.3f}  {triggered}")

    # ── summary ───────────────────────────────────────────────────────────────
    print(f"\n[4/4] Interpretation")
    print("=" * 65)
    print(f"  Windows 0-4   : BENIGN traffic  -> expect NORMAL")
    print(f"  Windows 5-9   : CAN DoS + GPS Spoofing attack  -> expect CRITICAL")
    print(f"  Windows 10-14 : BENIGN traffic  -> expect NORMAL (attack cleared)")
    print()
    print(f"  Each CAN window = {CAN_WINDOW} packets buffered before one model call")
    print(f"    -> at 5000 pkt/s this represents {CAN_WINDOW/5000*1000:.1f}ms of traffic")
    print(f"  Each GPS window = {GPS_WINDOW} frames buffered before one model call")
    print(f"    -> at 10 Hz this represents {GPS_WINDOW/10:.1f}s of GPS data")
    print()
    print(f"  Without windowing: {N_WINDOWS * CAN_WINDOW} model calls for CAN alone")
    print(f"  With windowing   : {N_WINDOWS} model calls -- {CAN_WINDOW}x fewer")
    print("=" * 65)


if __name__ == "__main__":
    main()
