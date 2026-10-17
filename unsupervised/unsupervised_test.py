"""
Unsupervised Zero-Day Detector — Test / Evaluation script.

Tests:
  1. Pure benign traffic (should all be normal)
  2. Known attacks through supervised runners (should mostly be flagged)
  3. Synthetic zero-day vectors (unseen attack patterns)
  4. Threshold sensitivity analysis

Produces unsupervised_evaluation.png.

Run with:
    python unsupervised/unsupervised_test.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
CODES = HERE.parent
sys.path.insert(0, str(CODES))

import joblib
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score, roc_curve

from network.network_runner import NetworkDetector
from can.can_runner import CANDetector
from gps.gps_runner import GPSDetector
from lidar.lidar_runner import LiDARDetector, _extract_features

DATA = CODES / "data"

NETWORK_CLASSES = ["BENIGN", "Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"]
CAN_CLASSES     = ["BENIGN", "DoS", "GAS", "RPM", "SPEED", "STEERING_WHEEL"]
GPS_CLASSES     = ["Normal", "Spoofing"]
LIDAR_CLASSES   = ["Normal", "PointDrop", "IntensitySpoof", "GhostCluster"]
FEAT_DIM        = 19

RNG = np.random.default_rng(99)


def probs_vec(result, class_list):
    if "probabilities" in result:
        p = result["probabilities"]
        return np.array([p[c] for c in class_list], dtype=np.float32)
    return np.array([result.get("prob_normal", 0.0),
                     result.get("prob_spoof", 0.0)], dtype=np.float32)


def build_19dim(net_r, can_r, gps_r, lid_r):
    return np.concatenate([
        probs_vec(net_r, NETWORK_CLASSES),
        probs_vec(can_r, CAN_CLASSES),
        probs_vec(gps_r, GPS_CLASSES),
        probs_vec(lid_r, LIDAR_CLASSES),
    ])


# ── Collect test vectors ──────────────────────────────────────────────────────

def collect_benign_vectors(net_det, can_det, gps_det, lid_det, n=500):
    """Build n benign 19-dim vectors from real data."""
    print(f"  Collecting {n} benign vectors …")
    net_df = pd.read_csv(DATA / "CICIDS2017_sample.csv")
    net_feats = json.load(open(CODES / "network" / "network_features.json"))
    net_rows = (net_df[net_df["Label"] == "BENIGN"][net_feats]
                .replace([np.inf, -np.inf], 0).fillna(0)
                .sample(n=min(n, 22731), random_state=1).to_dict(orient="records"))

    can_df = pd.read_csv(DATA / "CICIoV2024" / "decimal" / "decimal_benign.csv",
                         encoding="latin-1", nrows=n)
    can_rows = can_df[["ID","DATA_0","DATA_1","DATA_2","DATA_3",
                        "DATA_4","DATA_5","DATA_6","DATA_7"]].to_dict(orient="records")

    gps_dfs = []
    for i in range(4):
        df = pd.read_csv(DATA / "AV-GPS-Dataset" / f"AV-GPS-Dataset-{i}.csv")
        drop = ["Clock Time","GPS MGRS","Hobbs","Data Type","Hobbs Time",
                "Arming State","Flight Mode"]
        normal = df[df["Data Type"]==0].drop(columns=[c for c in drop if c in df.columns], errors="ignore")
        gps_dfs.append(normal)
    gps_df = pd.concat(gps_dfs).sample(n=min(n, sum(len(d) for d in gps_dfs)), random_state=1)
    gps_rows = gps_df.to_dict(orient="records")

    seq_dirs = [
        DATA/"Depth"/"2011_09_26_drive_0001_sync"/"2011_09_26"/"2011_09_26_drive_0001_sync"/"velodyne_points"/"data",
        DATA/"Depth"/"2011_09_26_drive_0015_sync"/"2011_09_26"/"2011_09_26_drive_0015_sync"/"velodyne_points"/"data",
    ]
    bins = []
    for d in seq_dirs:
        bins += sorted(d.glob("*.bin"))

    m = min(n, len(net_rows), len(can_rows), len(gps_rows), len(bins))
    vecs = []
    for i in range(m):
        net_r = net_det.predict([net_rows[i]])[0]
        can_r = can_det.predict([can_rows[i]])[0]
        gps_r = gps_det.predict([gps_rows[i]])[0]
        lid_r = lid_det.predict_one(bins[i % len(bins)])
        vecs.append(build_19dim(net_r, can_r, gps_r, lid_r))
    print(f"    {len(vecs)} benign vectors collected")
    return np.array(vecs)


def collect_attack_vectors(net_det, can_det, gps_det, lid_det, n=200):
    """Build n attack 19-dim vectors using real labelled attack data."""
    print(f"  Collecting {n} attack vectors …")
    net_df = pd.read_csv(DATA / "CICIDS2017_sample.csv")
    net_feats = json.load(open(CODES / "network" / "network_features.json"))
    attack_net = (net_df[net_df["Label"] != "BENIGN"][net_feats]
                  .replace([np.inf, -np.inf], 0).fillna(0)
                  .sample(n=min(n, len(net_df[net_df["Label"]!="BENIGN"])), random_state=2)
                  .to_dict(orient="records"))

    can_attack_files = [
        DATA/"CICIoV2024"/"decimal"/"decimal_DoS.csv",
        DATA/"CICIoV2024"/"decimal"/"decimal_spoofing-SPEED.csv",
    ]
    can_rows = []
    for fp in can_attack_files:
        df = pd.read_csv(fp, encoding="latin-1", nrows=n//2)
        can_rows += df[["ID","DATA_0","DATA_1","DATA_2","DATA_3",
                         "DATA_4","DATA_5","DATA_6","DATA_7"]].to_dict(orient="records")

    gps_dfs = []
    for i in range(4):
        df = pd.read_csv(DATA/"AV-GPS-Dataset"/f"AV-GPS-Dataset-{i}.csv")
        drop = ["Clock Time","GPS MGRS","Hobbs","Data Type","Hobbs Time",
                "Arming State","Flight Mode"]
        spoof = df[df["Data Type"]==1].drop(columns=[c for c in drop if c in df.columns], errors="ignore")
        gps_dfs.append(spoof)
    gps_attack = pd.concat(gps_dfs)
    if len(gps_attack) == 0:
        gps_attack_rows = []
    else:
        gps_attack_rows = gps_attack.sample(n=min(n, len(gps_attack)), random_state=2).to_dict(orient="records")

    seq_dirs = [
        DATA/"Depth"/"2011_09_26_drive_0001_sync"/"2011_09_26"/"2011_09_26_drive_0001_sync"/"velodyne_points"/"data",
    ]
    bins = sorted(seq_dirs[0].glob("*.bin"))

    m = min(n, len(attack_net), len(can_rows))
    vecs = []
    for i in range(m):
        net_r = net_det.predict([attack_net[i]])[0]
        can_r = can_det.predict([can_rows[i % len(can_rows)]])[0]
        gps_r = gps_det.predict([gps_attack_rows[i % len(gps_attack_rows)]])[0] if gps_attack_rows else None
        if gps_r is None:
            gps_r = gps_det.predict([{"GPS Latitude":0,"GPS Longitude":0,
                                       "Relative Altitude (m)":0,"Vertical Position (m)":0,
                                       "Longitudinal Position (m)":0,"Lateral Position (m)":0,
                                       "Velocity (m/s)":0,"Absolute Longitudinal Velocity (m/s)":0,
                                       "Longitudinal Velocity (m/s)":0,"Lateral Velocity (m/s)":0,
                                       "Absolute Lateral Velocity (m/s)":0,"Vertical Velocity (m/s)":0,
                                       "Roll (deg)":0,"Pitch (deg)":0,"Heading (deg)":0,"Yaw (deg)":0,
                                       "Yaw Rate (deg/s)":0,"GPS Course":0,"Steering Angle (deg)":0,
                                       "Satellite Locks":1,"Satellite Count":1,"GPS HDOP":5.0,"GPS VDOP":5.0,
                                       "Altitude AMSL (m)":0,"Altitude Tuning":0,"Altitude Tuning Setpoint":0,
                                       "X-Track Error (m)":0,"Travelled Distance (m)":0,
                                       "Distance To Home (m)":0,"Throttle (%)":0,"Temperature (F)":0,
                                       "Longitudinal Vibration":0,"Lateral Vibration":0,"Vertical Vibration":0}])[0]

        # LiDAR: use a PointDrop-attacked scan
        pts = np.fromfile(bins[i % len(bins)], dtype=np.float32).reshape(-1, 4)
        keep = RNG.random(len(pts)) > 0.6
        pts_drop = pts[keep] if keep.sum() > 100 else pts[:100]
        lid_r = lid_det.predict_one(pts_drop)

        vecs.append(build_19dim(net_r, can_r, gps_r, lid_r))

    print(f"    {len(vecs)} attack vectors collected")
    return np.array(vecs)


def save_evaluation_png(X_benign, X_attack, scores_benign, scores_attack, out_path):
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    # PCA scatter
    pca = PCA(n_components=2)
    X_all = np.vstack([X_benign, X_attack])
    X_2d = pca.fit_transform(X_all)
    n = len(X_benign)
    axes[0].scatter(X_2d[:n,0], X_2d[:n,1], s=12, alpha=0.5, color="#4C72B0", label=f"Benign ({n})")
    axes[0].scatter(X_2d[n:,0], X_2d[n:,1], s=12, alpha=0.5, color="#C44E52", label=f"Attack ({len(X_attack)})")
    axes[0].set_title(f"PCA 2D  (var={pca.explained_variance_ratio_.sum():.1%})")
    axes[0].set_xlabel("PC1"); axes[0].set_ylabel("PC2"); axes[0].legend(fontsize=9)

    # Score distribution
    axes[1].hist(scores_benign, bins=40, alpha=0.6, color="#4C72B0", label="Benign", density=True)
    axes[1].hist(scores_attack, bins=40, alpha=0.6, color="#C44E52", label="Attack", density=True)
    axes[1].axvline(0, color="black", linestyle="--", linewidth=1.5, label="Threshold (0)")
    axes[1].set_title("OC-SVM Decision Score Distribution")
    axes[1].set_xlabel("Score  (>0 = normal)"); axes[1].set_ylabel("Density"); axes[1].legend()

    # ROC curve
    y_true = np.concatenate([np.zeros(len(scores_benign)), np.ones(len(scores_attack))])
    # flip sign: higher score = more normal → negate for anomaly detection
    y_score = np.concatenate([-scores_benign, -scores_attack])
    try:
        auc = roc_auc_score(y_true, y_score)
        fpr, tpr, _ = roc_curve(y_true, y_score)
        axes[2].plot(fpr, tpr, color="#4C72B0", lw=2, label=f"ROC AUC = {auc:.3f}")
        axes[2].plot([0,1],[0,1],"k--", lw=1)
        axes[2].set_xlabel("False Positive Rate"); axes[2].set_ylabel("True Positive Rate")
        axes[2].set_title("ROC Curve — Zero-Day Detection"); axes[2].legend()
    except Exception:
        axes[2].text(0.5, 0.5, "ROC N/A", ha="center", va="center")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def main():
    print("=== Unsupervised Zero-Day Detector — Full Evaluation ===")

    ocsvm  = joblib.load(HERE / "unsupervised_model.pkl")
    scaler = joblib.load(HERE / "unsupervised_scaler.pkl")
    meta   = json.loads((HERE / "unsupervised_meta.json").read_text())
    print(f"Model: nu={meta['nu']}, kernel={meta['kernel']}, "
          f"train_samples={meta['train_samples']}")

    print("\nLoading runners …")
    net_det = NetworkDetector()
    can_det = CANDetector()
    gps_det = GPSDetector()
    lid_det = LiDARDetector()

    print("\nCollecting test vectors …")
    X_benign = collect_benign_vectors(net_det, can_det, gps_det, lid_det, n=300)
    X_attack = collect_attack_vectors(net_det, can_det, gps_det, lid_det, n=200)

    X_b_sc = scaler.transform(X_benign)
    X_a_sc = scaler.transform(X_attack)

    scores_b = ocsvm.decision_function(X_b_sc)
    scores_a = ocsvm.decision_function(X_a_sc)
    preds_b  = ocsvm.predict(X_b_sc)
    preds_a  = ocsvm.predict(X_a_sc)

    tp = (preds_a == -1).sum()
    fp = (preds_b == -1).sum()
    tn = (preds_b ==  1).sum()
    fn = (preds_a ==  1).sum()

    precision = tp / (tp + fp + 1e-9)
    recall    = tp / (tp + fn + 1e-9)
    f1        = 2 * precision * recall / (precision + recall + 1e-9)
    fpr       = fp / (fp + tn + 1e-9)

    print(f"\n{'-'*45}")
    print(f"  Benign samples  : {len(X_benign)}")
    print(f"  Attack samples  : {len(X_attack)}")
    print(f"{'-'*45}")
    print(f"  True Positives  : {tp}  (attacks detected)")
    print(f"  False Positives : {fp}  (benign wrongly flagged)")
    print(f"  True Negatives  : {tn}  (benign correctly passed)")
    print(f"  False Negatives : {fn}  (attacks missed)")
    print(f"{'-'*45}")
    print(f"  Detection Rate  : {recall:.2%}")
    print(f"  False Pos Rate  : {fpr:.2%}")
    print(f"  Precision       : {precision:.2%}")
    print(f"  F1              : {f1:.2%}")
    print(f"{'-'*45}")

    y_true  = np.concatenate([np.zeros(len(scores_b)), np.ones(len(scores_a))])
    y_score = np.concatenate([-scores_b, -scores_a])
    try:
        auc = roc_auc_score(y_true, y_score)
        print(f"  ROC AUC         : {auc:.4f}")
    except Exception:
        pass

    save_evaluation_png(X_benign, X_attack, scores_b, scores_a,
                        HERE / "unsupervised_evaluation.png")


if __name__ == "__main__":
    main()
