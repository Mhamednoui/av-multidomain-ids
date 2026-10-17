"""
SHAP Explainability — Fusion Meta-Classifier
=============================================
Explains why the fusion model fires on a given sample.

Produces:
  shap_summary.png    — global feature importance across all test samples
  shap_waterfall.png  — single CRITICAL alert breakdown (which domain/feature pushed it)
  shap_bar.png        — mean |SHAP| bar chart (clean version for thesis)

Run with:
    python explainability/shap_explain.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
import joblib

HERE  = Path(__file__).parent
CODES = HERE.parent
FUSION = CODES / "fusion"

FEATURE_LABELS = {
    "net_BENIGN":         "Net: Benign",
    "net_Bot":            "Net: Bot",
    "net_BruteForce":     "Net: BruteForce",
    "net_DoS":            "Net: DoS",
    "net_Infiltration":   "Net: Infiltration",
    "net_PortScan":       "Net: PortScan",
    "net_WebAttack":      "Net: WebAttack",
    "can_BENIGN":         "CAN: Benign",
    "can_DoS":            "CAN: DoS",
    "can_GAS":            "CAN: Gas Spoof",
    "can_RPM":            "CAN: RPM Spoof",
    "can_SPEED":          "CAN: Speed Spoof",
    "can_STEERING_WHEEL": "CAN: Steering Spoof",
    "gps_Normal":         "GPS: Normal",
    "gps_Spoofing":       "GPS: Spoofing",
    "lid_Normal":         "LiDAR: Normal",
    "lid_PointDrop":      "LiDAR: PointDrop",
    "lid_IntensitySpoof": "LiDAR: IntensitySpoof",
    "lid_GhostCluster":   "LiDAR: GhostCluster",
    "zd_score":           "Zero-Day Score",
}

DARK_BG  = "#0d1117"
PANEL_BG = "#161b22"
TEXT_COL = "#f0ede6"
MUTED    = "#9c9a92"


def load_fusion_model():
    features = json.load(open(FUSION / "fusion_meta_features.json"))
    scaler   = joblib.load(FUSION / "fusion_meta_scaler.pkl")
    model    = xgb.XGBClassifier()
    model.load_model(str(FUSION / "fusion_meta_model.json"))
    return model, scaler, features


def build_test_matrix(scaler, features):
    sys.path.insert(0, str(CODES))
    from network.network_runner           import NetworkDetector
    from can.can_runner                   import CANDetector
    from gps.gps_runner                   import GPSDetector
    from lidar.lidar_runner               import LiDARDetector
    from unsupervised.unsupervised_runner import ZeroDayDetector, _probs_vec

    NET_C = ["BENIGN","Bot","BruteForce","DoS","Infiltration","PortScan","WebAttack"]
    CAN_C = ["BENIGN","DoS","GAS","RPM","SPEED","STEERING_WHEEL"]
    GPS_C = ["Normal","Spoofing"]
    LID_C = ["Normal","PointDrop","IntensitySpoof","GhostCluster"]

    print("  Loading runners ...")
    net_det = NetworkDetector()
    can_det = CANDetector()
    gps_det = GPSDetector()
    lid_det = LiDARDetector()
    zd_det  = ZeroDayDetector(network_det=net_det, can_det=can_det,
                               gps_det=gps_det, lidar_det=lid_det)

    DATA = CODES / "data"
    RNG  = np.random.default_rng(42)
    N    = 150  # 150 normal + 150 attack

    # network
    net_feats = json.load(open(CODES / "network" / "network_features.json"))
    df_net = pd.read_csv(DATA / "CICIDS2017_sample_km_test.csv")
    df_net = df_net.replace([np.inf, -np.inf], 0).fillna(0)
    ben_net = df_net[df_net["Label"] == "BENIGN"][net_feats].sample(N, random_state=42)
    atk_net = df_net[df_net["Label"] != "BENIGN"][net_feats].sample(N, random_state=42)
    net_rows = ([("BENIGN", r.to_dict()) for _, r in ben_net.iterrows()] +
                [("ATTACK", r.to_dict()) for _, r in atk_net.iterrows()])

    # CAN
    raw_cols = ["ID","DATA_0","DATA_1","DATA_2","DATA_3",
                "DATA_4","DATA_5","DATA_6","DATA_7"]
    can_dir = DATA / "CICIoV2024" / "decimal"
    df_cb = pd.read_csv(can_dir / "decimal_benign.csv",
                        encoding="latin-1", nrows=N*3)[raw_cols].sample(N, random_state=42)
    df_ca = pd.read_csv(can_dir / "decimal_DoS.csv",
                        encoding="latin-1", nrows=N*3)[raw_cols].sample(N, random_state=42)
    can_rows = ([("BENIGN", r.to_dict()) for _, r in df_cb.iterrows()] +
                [("ATTACK", r.to_dict()) for _, r in df_ca.iterrows()])

    # GPS
    drop_cols = ["Clock Time","GPS MGRS","Hobbs","Data Type",
                 "Hobbs Time","Arming State","Flight Mode"]
    gps_normal, gps_spoof = [], []
    for i in range(4):
        df_g = pd.read_csv(DATA / "AV-GPS-Dataset" / f"AV-GPS-Dataset-{i}.csv")
        d    = df_g.drop(columns=[c for c in drop_cols if c in df_g.columns], errors="ignore")
        gps_normal.extend(d[df_g["Data Type"] == 0].to_dict(orient="records"))
        gps_spoof.extend( d[df_g["Data Type"] == 1].to_dict(orient="records"))
    ni = RNG.choice(len(gps_normal), N, replace=False)
    si = RNG.choice(len(gps_spoof),  N, replace=False)
    gps_rows = ([("Normal",   gps_normal[i]) for i in ni] +
                [("Spoofing", gps_spoof[i])  for i in si])

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

    idx_n = RNG.choice(len(bins), N, replace=True)
    idx_a = RNG.choice(len(bins), N, replace=True)
    lid_rows = (
        [("Normal",       str(bins[i])) for i in idx_n] +
        [("GhostCluster", ghost(np.fromfile(bins[i], dtype=np.float32).reshape(-1,4)))
         for i in idx_a]
    )

    # build matrix
    print(f"  Building {N*2} feature vectors ...")
    X_rows, y_rows = [], []
    m = min(len(net_rows), len(can_rows), len(gps_rows), len(lid_rows))
    for i in range(m):
        net_lbl, net_f = net_rows[i]
        can_lbl, can_f = can_rows[i]
        gps_lbl, gps_f = gps_rows[i]
        lid_lbl, lid_s = lid_rows[i]

        net_r = net_det.predict([net_f])[0]
        can_r = can_det.predict([can_f])[0]
        gps_r = gps_det.predict([gps_f])[0]
        lid_r = lid_det.predict_one(lid_s)

        vec   = np.concatenate([_probs_vec(net_r, NET_C), _probs_vec(can_r, CAN_C),
                                 _probs_vec(gps_r, GPS_C), _probs_vec(lid_r, LID_C)])
        sc    = zd_det.scaler.transform(vec.reshape(1,-1))
        score = float(zd_det.ocsvm.decision_function(sc)[0])
        X_rows.append(list(vec) + [score])

        is_attack = (net_lbl != "BENIGN" or can_lbl != "BENIGN" or
                     gps_lbl == "Spoofing" or lid_lbl != "Normal")
        y_rows.append(int(is_attack))

        if (i+1) % 100 == 0:
            print(f"    [{i+1}/{m}]")

    X        = np.array(X_rows, dtype=np.float32)
    y        = np.array(y_rows, dtype=int)
    X_scaled = scaler.transform(X).astype(np.float32)
    return X_scaled, y


# =============================================================================
#  PLOT 1 — beeswarm summary
# =============================================================================

def plot_summary(shap_values, X_scaled, feature_names, out_path):
    labels = [FEATURE_LABELS.get(f, f) for f in feature_names]
    shap.summary_plot(shap_values, X_scaled, feature_names=labels, show=False)
    fig = plt.gcf()
    ax  = plt.gca()
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors=TEXT_COL, labelsize=9)
    ax.xaxis.label.set_color(TEXT_COL)
    ax.set_title("AV-IDS Fusion — Global Feature Importance (SHAP Beeswarm)",
                 color=TEXT_COL, fontsize=12, fontweight="bold", pad=12)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  Saved: {out_path}")


# =============================================================================
#  PLOT 2 — mean |SHAP| bar (thesis-friendly, coloured by domain)
# =============================================================================

def plot_bar(shap_values, feature_names, out_path):
    labels   = [FEATURE_LABELS.get(f, f) for f in feature_names]
    mean_abs = np.abs(shap_values).mean(axis=0)
    order    = np.argsort(mean_abs)

    domain_colors = {
        "Net":      "#4C72B0",
        "CAN":      "#C44E52",
        "GPS":      "#55A868",
        "LiDAR":    "#DD8452",
        "Zero-Day": "#8172B2",
    }
    def bar_color(label):
        for prefix, col in domain_colors.items():
            if label.startswith(prefix):
                return col
        return "#777"

    sorted_labels = [labels[i] for i in order]
    sorted_vals   = [mean_abs[i] for i in order]
    colors        = [bar_color(l) for l in sorted_labels]

    fig, ax = plt.subplots(figsize=(10, 7))
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(PANEL_BG)
    bars = ax.barh(range(len(sorted_labels)), sorted_vals,
                   color=colors, edgecolor="#222", height=0.7)
    ax.set_yticks(range(len(sorted_labels)))
    ax.set_yticklabels(sorted_labels, fontsize=9, color=TEXT_COL)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8)
    ax.set_xlabel("Mean |SHAP value|", color=MUTED, fontsize=9)
    ax.set_title("AV-IDS Fusion — Feature Importance by Domain",
                 color=TEXT_COL, fontsize=12, fontweight="bold", pad=12)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    for bar, val in zip(bars, sorted_vals):
        ax.text(val + 0.001, bar.get_y() + bar.get_height()/2,
                f"{val:.3f}", va="center", fontsize=7.5, color=TEXT_COL)
    patches = [plt.Rectangle((0,0),1,1, color=c, label=d)
               for d, c in domain_colors.items()]
    ax.legend(handles=patches, fontsize=8, labelcolor=TEXT_COL,
              facecolor=PANEL_BG, edgecolor="#333", loc="lower right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  Saved: {out_path}")


# =============================================================================
#  PLOT 3 — waterfall for one CRITICAL sample
# =============================================================================

def plot_waterfall(explainer, shap_values, X_scaled, y, feature_names, out_path):
    labels     = [FEATURE_LABELS.get(f, f) for f in feature_names]
    attack_idx = np.where(y == 1)[0]
    magnitudes = np.abs(shap_values[attack_idx]).sum(axis=1)
    chosen     = attack_idx[np.argmax(magnitudes)]

    sv = shap.Explanation(
        values        = shap_values[chosen],
        base_values   = explainer.expected_value,
        data          = X_scaled[chosen],
        feature_names = labels,
    )
    shap.waterfall_plot(sv, show=False, max_display=20)
    fig = plt.gcf()
    ax  = plt.gca()
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors=TEXT_COL, labelsize=8)
    ax.xaxis.label.set_color(TEXT_COL)
    ax.set_title(
        f"AV-IDS Fusion — Single CRITICAL Alert Explanation  (sample #{chosen})",
        color=TEXT_COL, fontsize=11, fontweight="bold", pad=10)
    for spine in ax.spines.values():
        spine.set_edgecolor("#333")
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close()
    print(f"  Saved: {out_path}")


# =============================================================================
#  MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("  AV-IDS SHAP Explainability")
    print("=" * 60)

    print("\n[1/4] Loading fusion model ...")
    model, scaler, features = load_fusion_model()

    print("\n[2/4] Building test matrix (300 samples) ...")
    X_scaled, y = build_test_matrix(scaler, features)
    print(f"  X: {X_scaled.shape}  attacks={y.sum()}  normals={(y==0).sum()}")

    print("\n[3/4] Computing SHAP values ...")
    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_scaled)
    if isinstance(shap_values, list):
        shap_values = shap_values[1]
    print(f"  SHAP matrix: {shap_values.shape}")

    print("\n[4/4] Saving plots ...")
    plot_summary(  shap_values, X_scaled, features, HERE / "shap_summary.png")
    plot_bar(      shap_values,           features, HERE / "shap_bar.png")
    plot_waterfall(explainer, shap_values, X_scaled, y, features, HERE / "shap_waterfall.png")

    # top-10 console summary
    mean_abs = np.abs(shap_values).mean(axis=0)
    order    = np.argsort(mean_abs)[::-1]
    print("\n  Top-10 most important features:")
    print(f"  {'Feature':<26} {'Mean |SHAP|':>12}")
    print(f"  {'-'*40}")
    for i in order[:10]:
        lbl = FEATURE_LABELS.get(features[i], features[i])
        print(f"  {lbl:<26} {mean_abs[i]:>12.4f}")

    print("\n" + "=" * 60)
    print("  Done. Output:")
    print(f"    explainability/shap_summary.png")
    print(f"    explainability/shap_bar.png")
    print(f"    explainability/shap_waterfall.png")
    print("=" * 60)


if __name__ == "__main__":
    main()
