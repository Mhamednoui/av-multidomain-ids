"""
Response Module Demo
====================
Runs 60 samples through the full pipeline and shows the response module in action.
Demonstrates the complete loop: data → runners → fusion → response.

Run with:
    python response/response_demo.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE  = Path(__file__).parent
CODES = HERE.parent
sys.path.insert(0, str(CODES))

from network.network_runner           import NetworkDetector
from can.can_runner                   import CANDetector
from gps.gps_runner                   import GPSDetector
from lidar.lidar_runner               import LiDARDetector
from unsupervised.unsupervised_runner import ZeroDayDetector, _probs_vec
from fusion.fusion_engine             import FusionEngine
from response.response_module         import ResponseModule

DATA = CODES / "data"
RNG  = np.random.default_rng(99)
N    = 60   # 30 normal + 30 attack


def load_samples():
    # network
    net_feats = json.load(open(CODES / "network" / "network_features.json"))
    df_net = pd.read_csv(DATA / "CICIDS2017_sample_km_test.csv")
    df_net = df_net.replace([np.inf, -np.inf], 0).fillna(0)
    ben = df_net[df_net["Label"] == "BENIGN"][net_feats].sample(N//2, random_state=7)
    atk = df_net[df_net["Label"] != "BENIGN"][net_feats].sample(N//2, random_state=7)
    net_rows = ([("BENIGN", r.to_dict()) for _, r in ben.iterrows()] +
                [("ATTACK", r.to_dict()) for _, r in atk.iterrows()])

    # CAN
    raw_cols = ["ID","DATA_0","DATA_1","DATA_2","DATA_3",
                "DATA_4","DATA_5","DATA_6","DATA_7"]
    can_dir  = DATA / "CICIoV2024" / "decimal"
    cb = pd.read_csv(can_dir/"decimal_benign.csv", encoding="latin-1",
                     nrows=N*3)[raw_cols].sample(N//2, random_state=7)
    ca = pd.read_csv(can_dir/"decimal_DoS.csv",    encoding="latin-1",
                     nrows=N*3)[raw_cols].sample(N//2, random_state=7)
    can_rows = ([("BENIGN", r.to_dict()) for _, r in cb.iterrows()] +
                [("ATTACK", r.to_dict()) for _, r in ca.iterrows()])

    # GPS
    drop_cols = ["Clock Time","GPS MGRS","Hobbs","Data Type",
                 "Hobbs Time","Arming State","Flight Mode"]
    gps_n, gps_s = [], []
    for i in range(4):
        df_g = pd.read_csv(DATA / "AV-GPS-Dataset" / f"AV-GPS-Dataset-{i}.csv")
        d    = df_g.drop(columns=[c for c in drop_cols if c in df_g.columns], errors="ignore")
        gps_n.extend(d[df_g["Data Type"] == 0].to_dict(orient="records"))
        gps_s.extend(d[df_g["Data Type"] == 1].to_dict(orient="records"))
    ni = RNG.choice(len(gps_n), N//2, replace=False)
    si = RNG.choice(len(gps_s), N//2, replace=False)
    gps_rows = ([("Normal",   gps_n[i]) for i in ni] +
                [("Spoofing", gps_s[i]) for i in si])

    # LiDAR
    seq_dirs = [
        DATA/"Depth"/"2011_09_26_drive_0001_sync"/"2011_09_26"
             /"2011_09_26_drive_0001_sync"/"velodyne_points"/"data",
        DATA/"Depth"/"2011_09_26_drive_0015_sync"/"2011_09_26"
             /"2011_09_26_drive_0015_sync"/"velodyne_points"/"data",
    ]
    bins = []
    for d in seq_dirs:
        bins += sorted(d.glob("*.bin"))

    def ghost(pts):
        ng = int(RNG.integers(2000, 6000))
        g  = np.stack([RNG.uniform(8,20,ng).astype(np.float32),
                       RNG.uniform(-1.5,1.5,ng).astype(np.float32),
                       RNG.uniform(-1.5,1.5,ng).astype(np.float32),
                       RNG.uniform(0.1,0.6,ng).astype(np.float32)], axis=1)
        return np.concatenate([pts, g])

    idx_n = RNG.choice(len(bins), N//2, replace=True)
    idx_a = RNG.choice(len(bins), N//2, replace=True)
    lid_rows = (
        [("Normal",       str(bins[i])) for i in idx_n] +
        [("GhostCluster", ghost(np.fromfile(bins[i], dtype=np.float32).reshape(-1,4)))
         for i in idx_a]
    )

    rows = list(zip(net_rows, can_rows, gps_rows, lid_rows))
    RNG.shuffle(rows)
    return rows


def compute_zd(zd_det, net_r, can_r, gps_r, lid_r):
    NET_C = ["BENIGN","Bot","BruteForce","DoS","Infiltration","PortScan","WebAttack"]
    CAN_C = ["BENIGN","DoS","GAS","RPM","SPEED","STEERING_WHEEL"]
    GPS_C = ["Normal","Spoofing"]
    LID_C = ["Normal","PointDrop","IntensitySpoof","GhostCluster"]
    vec   = np.concatenate([_probs_vec(net_r, NET_C), _probs_vec(can_r, CAN_C),
                             _probs_vec(gps_r, GPS_C), _probs_vec(lid_r, LID_C)])
    sc    = zd_det.scaler.transform(vec.reshape(1,-1))
    score = float(zd_det.ocsvm.decision_function(sc)[0])
    flag  = bool(zd_det.ocsvm.predict(sc)[0] == -1)
    return {"anomaly_score": score, "is_zero_day": flag}


def main():
    print("=" * 65)
    print("  AV-IDS Response Module Demo")
    print(f"  {N} samples  (normal + attack mixed)")
    print("=" * 65)

    print("\n[1/3] Loading runners ...")
    net_det = NetworkDetector()
    can_det = CANDetector()
    gps_det = GPSDetector()
    lid_det = LiDARDetector()
    zd_det  = ZeroDayDetector(network_det=net_det, can_det=can_det,
                               gps_det=gps_det,    lidar_det=lid_det)
    engine  = FusionEngine(strategy="meta")
    rm      = ResponseModule()
    print("  Ready.")

    print(f"\n[2/3] Running pipeline on {N} samples ...")
    samples = load_samples()

    print(f"\n  {'#':>3}  {'True':>10}  {'Fusion':>10}  {'Score':>6}  {'Actions'}")
    print(f"  {'-'*60}")

    for i, ((net_lbl, net_f), (can_lbl, can_f),
             (gps_lbl, gps_f), (lid_lbl, lid_s)) in enumerate(samples):

        net_r = net_det.predict([net_f])[0]
        can_r = can_det.predict([can_f])[0]
        gps_r = gps_det.predict([gps_f])[0]
        lid_r = lid_det.predict_one(lid_s)
        zd_r  = compute_zd(zd_det, net_r, can_r, gps_r, lid_r)
        alert = engine.predict(net_r, can_r, gps_r, lid_r, zd_r)

        true_any = (net_lbl != "BENIGN" or can_lbl != "BENIGN" or
                    gps_lbl == "Spoofing" or lid_lbl != "Normal")
        true_str = "ATTACK" if true_any else "NORMAL"

        action = rm.handle(alert)
        acts   = ", ".join(action["actions_taken"]) if action["actions_taken"] else "-"

        print(f"  {i+1:>3}  {true_str:>10}  {alert.threat_label:>10}"
              f"  {alert.attack_score:>6.3f}  {acts}")

    print(f"\n[3/3] Summary")
    print("=" * 65)
    s = rm.summary()
    print(f"  Total handled  : {s['total_handled']}")
    print(f"  HIGH alerts    : {s['HIGH']}  (JSON saved to response/alerts/)")
    print(f"  CRITICAL alerts: {s['CRITICAL']}  (JSON + ISOLATE flag written)")
    isolate = rm.isolate_path
    if isolate.exists():
        print(f"\n  ISOLATE flag is ACTIVE: {isolate}")
        data = json.loads(isolate.read_text())
        print(f"    Triggered by : {data['triggered_by']}")
        print(f"    Attack score : {data['attack_score']:.3f}")
        print(f"\n  (call rm.clear_isolate() to resolve)")
    else:
        print(f"\n  No active ISOLATE flag.")
    print(f"\n  Log file : {rm.LOG_FILE if hasattr(rm,'LOG_FILE') else 'response/ids_alerts.log'}")
    print(f"  Alerts   : response/alerts/")
    print("=" * 65)


if __name__ == "__main__":
    main()
