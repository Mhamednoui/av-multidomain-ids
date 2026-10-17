"""
Temporal Alert Correlator Demo — AV-IDS
=========================================
Simulates a 30-step alert stream with a burst attack in the middle.
Shows how the TemporalCorrelator escalates threat level during the burst
and returns to NORMAL once the attack stops.

Uses the windowing + full pipeline from window_demo.py.

Run with:
    python temporal/temporal_demo.py
"""
import json
import sys
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
from temporal.temporal_correlator     import TemporalCorrelator

DATA = CODES / "data"
RNG  = np.random.default_rng(777)

CAN_WINDOW = 50
GPS_WINDOW = 10
N_STEPS    = 30   # total fusion decisions

# attack burst: steps 10-19
ATTACK_START = 10
ATTACK_END   = 19


def can_packets(attack: bool, n: int):
    fname = "decimal_DoS.csv" if attack else "decimal_benign.csv"
    df = pd.read_csv(DATA / "CICIoV2024" / "decimal" / fname,
                     encoding="latin-1", nrows=n * 3)
    cols = ["ID","DATA_0","DATA_1","DATA_2","DATA_3",
            "DATA_4","DATA_5","DATA_6","DATA_7"]
    return df[cols].sample(n, random_state=int(attack)).to_dict(orient="records")


def gps_frames(attack: bool, n: int):
    drop = ["Clock Time","GPS MGRS","Hobbs","Data Type","Hobbs Time",
            "Arming State","Flight Mode"]
    src  = 1 if attack else 0
    df   = pd.read_csv(DATA / "AV-GPS-Dataset" / f"AV-GPS-Dataset-{src}.csv")
    d    = df.drop(columns=[c for c in drop if c in df.columns], errors="ignore")
    dtype = 1 if attack else 0
    return d[df["Data Type"] == dtype].head(n).to_dict(orient="records")


def net_flow():
    feats = json.load(open(CODES / "network" / "network_features.json"))
    df = pd.read_csv(DATA / "CICIDS2017_sample_km_test.csv")
    df = df.replace([np.inf, -np.inf], 0).fillna(0)
    return df[df["Label"] == "BENIGN"][feats].sample(1, random_state=5).iloc[0].to_dict()


def lidar_scan():
    d = (DATA / "Depth" / "2011_09_26_drive_0001_sync" / "2011_09_26"
         / "2011_09_26_drive_0001_sync" / "velodyne_points" / "data")
    return str(sorted(d.glob("*.bin"))[0])


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


def main():
    print("=" * 72)
    print("  AV-IDS Temporal Alert Correlator Demo")
    print(f"  {N_STEPS} steps | attack burst: steps {ATTACK_START}-{ATTACK_END}")
    print(f"  Correlator: window=10, threshold=60%")
    print("=" * 72)

    print("\n[1/3] Loading runners ...")
    can_det = CANDetector()
    gps_det = GPSDetector()
    net_det = NetworkDetector()
    lid_det = LiDARDetector()
    zd_det  = ZeroDayDetector(network_det=net_det, can_det=can_det,
                               gps_det=gps_det, lidar_det=lid_det)
    engine  = FusionEngine(strategy="meta")
    tc      = TemporalCorrelator(window=10, threshold=0.6)
    mdw     = MultiDomainWindow(can_size=CAN_WINDOW, gps_size=GPS_WINDOW)

    # pre-load data pools
    can_b = can_packets(False, N_STEPS * CAN_WINDOW)
    can_a = can_packets(True,  N_STEPS * CAN_WINDOW)
    gps_b = gps_frames(False,  N_STEPS * GPS_WINDOW)
    gps_a = gps_frames(True,   N_STEPS * GPS_WINDOW)
    net_f = net_flow()
    lid_s = lidar_scan()
    print("  Ready.")

    print("\n[2/3] Simulating stream ...")
    print(f"\n  {'Step':>4}  {'Scenario':<10}  {'Fusion':>10}  {'Correlated':>10}  "
          f"{'Escalated':>9}  {'Win Rate':>9}  {'Persistent'}")
    print(f"  {'-'*72}")

    escalation_steps = []

    for step in range(N_STEPS):
        is_attack = ATTACK_START <= step <= ATTACK_END
        scenario  = "ATTACK" if is_attack else "BENIGN"

        # push window packets
        for i in range(CAN_WINDOW):
            src = can_a if is_attack else can_b
            mdw.push_can(src[(step * CAN_WINDOW + i) % len(src)])
        for i in range(GPS_WINDOW):
            src = gps_a if is_attack else gps_b
            mdw.push_gps(src[(step * GPS_WINDOW + i) % len(src)])
        mdw.push_network(net_f)
        mdw.push_lidar(lid_s)

        inputs = mdw.flush_all()

        # run runners
        can_r = can_det.predict(inputs["can"])[-1]
        gps_r = gps_det.predict(inputs["gps"])[-1]
        net_r = net_det.predict(inputs["network"])[0]
        lid_r = lid_det.predict_one(inputs["lidar"])
        zd_r  = compute_zd(zd_det, net_r, can_r, gps_r, lid_r)
        alert = engine.predict(net_r, can_r, gps_r, lid_r, zd_r)

        # correlate
        corr  = tc.correlate(alert)

        esc_str  = "YES" if corr.escalated else "-"
        rate_str = f"{corr.window_attack_rate:.0%}"

        print(f"  {step:>4}  {scenario:<10}  {alert.threat_label:>10}  "
              f"{corr.threat_label:>10}  {esc_str:>9}  {rate_str:>9}  "
              f"{corr.persistent_domain}")

        if corr.escalated:
            escalation_steps.append(step)

    print(f"\n[3/3] Summary")
    print("=" * 72)
    print(f"  Attack burst   : steps {ATTACK_START}-{ATTACK_END} "
          f"({ATTACK_END - ATTACK_START + 1} steps)")
    print(f"  Escalated at   : steps {escalation_steps}")
    print(f"  Correlator window=10 means escalation starts at step "
          f"{ATTACK_START + 5} (when 60% of window is attacks)")
    print()
    print(f"  Without correlator: every CRITICAL is independent, no burst context")
    print(f"  With correlator   : LOW alerts during burst get escalated to MEDIUM/HIGH,")
    print(f"                      giving operator a clear persistent-attack signal")
    print("=" * 72)


if __name__ == "__main__":
    main()
