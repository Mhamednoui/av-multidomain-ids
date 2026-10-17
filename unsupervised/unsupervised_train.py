"""
Unsupervised / Zero-Day Threat Detector — Training script.

Approach: One-Class SVM trained exclusively on the 19-dimensional probability
vectors produced by all 4 supervised domain runners when they see BENIGN/Normal
traffic. At inference time any input that falls outside the learned "normal"
distribution is flagged as an unknown/zero-day threat.

Feature vector (19 dims):
    [network_probs(7)] + [can_probs(6)] + [gps_probs(2)] + [lidar_probs(4)]

Why this works:
    - When all 4 models see normal traffic they confidently output near-[1,0,0,…]
      probability vectors. Attacks shift one or more vectors toward non-benign
      classes, creating a pattern the One-Class SVM has never seen.
    - Catches zero-day attacks that fool individual supervised models but still
      create an unusual joint probability signature.

Data sources (benign samples):
    - Network : CICIDS2017_sample.csv           → BENIGN rows (22,731)
    - CAN     : decimal_benign.csv              → all rows  (~230k, sampled)
    - GPS     : AV-GPS-Dataset-0/1/2/3.csv      → Normal rows
    - LiDAR   : KITTI .bin scans, seq 0001+0015 → real scans (405)

Run with:
    python unsupervised/unsupervised_train.py
"""
import json
import sys
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

HERE = Path(__file__).parent
CODES = HERE.parent
sys.path.insert(0, str(CODES))

from network.network_runner import NetworkDetector
from can.can_runner import CANDetector
from gps.gps_runner import GPSDetector
from lidar.lidar_runner import LiDARDetector, _extract_features

DATA = CODES / "data"

# ── Constants ────────────────────────────────────────────────────────────────

N_NETWORK = 7
N_CAN = 6
N_GPS = 2
N_LIDAR = 4
FEAT_DIM = N_NETWORK + N_CAN + N_GPS + N_LIDAR  # 19

NETWORK_CLASSES = ["BENIGN", "Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"]
CAN_CLASSES = ["BENIGN", "DoS", "GAS", "RPM", "SPEED", "STEERING_WHEEL"]
GPS_CLASSES = ["Normal", "Spoofing"]
LIDAR_CLASSES = ["Normal", "PointDrop", "IntensitySpoof", "GhostCluster"]

# Maximum benign samples per domain (keep training fast)
MAX_NETWORK = 5_000
MAX_CAN = 5_000
MAX_GPS = 5_000
MAX_LIDAR = 405  # use all — only 405 scans available


# ── Helpers ──────────────────────────────────────────────────────────────────

def probs_to_vec(result: dict, class_list: list) -> np.ndarray:
    """Extract ordered probability vector from a runner result dict."""
    # GPS runner uses prob_normal/prob_spoof instead of a probabilities dict
    if "probabilities" in result:
        p = result["probabilities"]
        return np.array([p[c] for c in class_list], dtype=np.float32)
    else:
        # GPS-style: prob_normal, prob_spoof
        return np.array([result.get("prob_normal", 0.0),
                         result.get("prob_spoof", 0.0)], dtype=np.float32)


# ── Benign sample collection ─────────────────────────────────────────────────

def collect_network(det: NetworkDetector) -> np.ndarray:
    print("  [Network] Loading BENIGN rows …")
    df = pd.read_csv(DATA / "CICIDS2017_sample.csv")
    feats = json.load(open(CODES / "network" / "network_features.json"))
    benign = df[df["Label"] == "BENIGN"][feats].head(MAX_NETWORK)
    benign = benign.replace([np.inf, -np.inf], 0).fillna(0)
    records = benign.to_dict(orient="records")
    results = det.predict(records)
    vecs = np.array([probs_to_vec(r, NETWORK_CLASSES) for r in results])
    print(f"    {len(vecs)} samples")
    return vecs


def collect_can(det: CANDetector) -> np.ndarray:
    print("  [CAN] Loading BENIGN rows …")
    df = pd.read_csv(DATA / "CICIoV2024" / "decimal" / "decimal_benign.csv",
                     encoding="latin-1", nrows=MAX_CAN)
    raw_cols = ["ID", "DATA_0", "DATA_1", "DATA_2", "DATA_3",
                "DATA_4", "DATA_5", "DATA_6", "DATA_7"]
    records = df[raw_cols].to_dict(orient="records")
    results = det.predict(records)
    vecs = np.array([probs_to_vec(r, CAN_CLASSES) for r in results])
    print(f"    {len(vecs)} samples")
    return vecs


def collect_gps(det: GPSDetector) -> np.ndarray:
    print("  [GPS] Loading Normal rows …")
    gps_dir = DATA / "AV-GPS-Dataset"
    drop_cols = ["Clock Time", "GPS MGRS", "Hobbs", "Data Type",
                 "Hobbs Time", "Arming State", "Flight Mode"]
    all_vecs = []
    for i in range(4):
        fp = gps_dir / f"AV-GPS-Dataset-{i}.csv"
        df = pd.read_csv(fp)
        normal = df[df["Data Type"] == 0].drop(
            columns=[c for c in drop_cols if c in df.columns], errors="ignore"
        ).head(MAX_GPS // 4)
        if len(normal) == 0:
            continue
        records = normal.to_dict(orient="records")
        results = det.predict(records)
        all_vecs.extend([probs_to_vec(r, GPS_CLASSES) for r in results])
    vecs = np.array(all_vecs)
    print(f"    {len(vecs)} samples")
    return vecs


def collect_lidar(det: LiDARDetector) -> np.ndarray:
    print("  [LiDAR] Loading real KITTI scans (Normal) …")
    seq_dirs = [
        DATA / "Depth" / "2011_09_26_drive_0001_sync" / "2011_09_26" /
        "2011_09_26_drive_0001_sync" / "velodyne_points" / "data",
        DATA / "Depth" / "2011_09_26_drive_0015_sync" / "2011_09_26" /
        "2011_09_26_drive_0015_sync" / "velodyne_points" / "data",
    ]
    bins = []
    for d in seq_dirs:
        bins += sorted(d.glob("*.bin"))
    results = det.predict(bins[:MAX_LIDAR])
    vecs = np.array([probs_to_vec(r, LIDAR_CLASSES) for r in results])
    print(f"    {len(vecs)} samples")
    return vecs


# ── Evaluation PNG ────────────────────────────────────────────────────────────

def save_evaluation_png(X_normal: np.ndarray, X_attack: np.ndarray,
                        scores_normal: np.ndarray, scores_attack: np.ndarray,
                        out_path: Path):
    """
    3-panel plot:
      1. PCA scatter: normal (blue) vs synthetic attacks (red) in 2D
      2. Score distributions: normal vs attack
      3. Per-domain probability heatmap for normal samples
    """
    fig, axes = plt.subplots(1, 3, figsize=(20, 6))

    # Panel 1: PCA 2D scatter
    pca = PCA(n_components=2)
    X_all = np.vstack([X_normal, X_attack])
    X_2d = pca.fit_transform(X_all)
    n = len(X_normal)
    axes[0].scatter(X_2d[:n, 0], X_2d[:n, 1], s=10, alpha=0.5,
                    color="#4C72B0", label=f"Normal ({n})")
    axes[0].scatter(X_2d[n:, 0], X_2d[n:, 1], s=10, alpha=0.5,
                    color="#C44E52", label=f"Attack ({len(X_attack)})")
    axes[0].set_title(f"PCA 2D (var={pca.explained_variance_ratio_.sum():.1%})")
    axes[0].set_xlabel("PC1"); axes[0].set_ylabel("PC2")
    axes[0].legend(fontsize=8)

    # Panel 2: Anomaly score distribution
    axes[1].hist(scores_normal, bins=40, alpha=0.6, color="#4C72B0",
                 label="Normal", density=True)
    axes[1].hist(scores_attack, bins=40, alpha=0.6, color="#C44E52",
                 label="Attack", density=True)
    axes[1].axvline(0, color="black", linestyle="--", linewidth=1.5,
                    label="Decision boundary")
    axes[1].set_title("Anomaly Score Distribution")
    axes[1].set_xlabel("Decision score (>0 = normal)")
    axes[1].set_ylabel("Density")
    axes[1].legend()

    # Panel 3: Mean probability vector for normal samples (heatmap)
    domain_labels = (
        [f"net:{c[:4]}" for c in NETWORK_CLASSES] +
        [f"can:{c[:4]}" for c in CAN_CLASSES] +
        [f"gps:{c[:4]}" for c in GPS_CLASSES] +
        [f"lid:{c[:4]}" for c in LIDAR_CLASSES]
    )
    mean_normal = X_normal.mean(axis=0)
    mean_attack = X_attack.mean(axis=0)
    heatmap = np.vstack([mean_normal, mean_attack])
    im = axes[2].imshow(heatmap, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    axes[2].set_yticks([0, 1])
    axes[2].set_yticklabels(["Normal", "Attack"])
    axes[2].set_xticks(range(FEAT_DIM))
    axes[2].set_xticklabels(domain_labels, rotation=90, fontsize=7)
    axes[2].set_title("Mean Probability Vector\n(Normal vs Attack)")
    plt.colorbar(im, ax=axes[2], shrink=0.8)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  Saved: {out_path}")


# ── Synthetic attack vectors (for evaluation) ─────────────────────────────────

def make_attack_vectors(n: int, rng: np.random.Generator) -> np.ndarray:
    """
    Synthesize 'attack' probability vectors by concentrating probability on
    non-benign classes — used only for evaluating the OC-SVM decision boundary,
    not for training (model never sees these).
    """
    vecs = []
    for _ in range(n):
        v = np.zeros(FEAT_DIM, dtype=np.float32)
        # Network: shift to random attack class
        nc = rng.integers(1, N_NETWORK)
        nv = rng.dirichlet(np.ones(N_NETWORK) * 0.1)
        nv[nc] += 0.7; nv /= nv.sum()
        v[:N_NETWORK] = nv
        # CAN: shift to random attack class
        cc = rng.integers(1, N_CAN)
        cv = rng.dirichlet(np.ones(N_CAN) * 0.1)
        cv[cc] += 0.7; cv /= cv.sum()
        v[N_NETWORK:N_NETWORK+N_CAN] = cv
        # GPS: spoof
        gv = np.array([0.1, 0.9], dtype=np.float32)
        v[N_NETWORK+N_CAN:N_NETWORK+N_CAN+N_GPS] = gv
        # LiDAR: random attack
        lc = rng.integers(1, N_LIDAR)
        lv = rng.dirichlet(np.ones(N_LIDAR) * 0.1)
        lv[lc] += 0.7; lv /= lv.sum()
        v[N_NETWORK+N_CAN+N_GPS:] = lv
        vecs.append(v)
    return np.array(vecs)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    t0 = time.time()
    rng = np.random.default_rng(42)

    print("=== Unsupervised Zero-Day Detector — Training ===")
    print(f"Feature vector: {FEAT_DIM} dims (network={N_NETWORK}, can={N_CAN}, gps={N_GPS}, lidar={N_LIDAR})")

    # 1. Load all 4 runners
    print("\n[1/5] Loading supervised runners …")
    net_det = NetworkDetector()
    can_det = CANDetector()
    gps_det = GPSDetector()
    lid_det = LiDARDetector()
    print("  All 4 runners loaded.")

    # 2. Collect benign probability vectors from each domain
    print("\n[2/5] Collecting benign probability vectors …")
    net_vecs = collect_network(net_det)
    can_vecs = collect_can(can_det)
    gps_vecs = collect_gps(gps_det)
    lid_vecs = collect_lidar(lid_det)

    # Align sizes: repeat smaller domains to match the largest
    n = max(len(net_vecs), len(can_vecs), len(gps_vecs), len(lid_vecs))
    def repeat_to(arr, n):
        reps = (n // len(arr)) + 1
        return np.tile(arr, (reps, 1))[:n]

    net_vecs = repeat_to(net_vecs, n)
    can_vecs = repeat_to(can_vecs, n)
    gps_vecs = repeat_to(gps_vecs, n)
    lid_vecs = repeat_to(lid_vecs, n)

    # Concatenate into 19-dim vectors
    X = np.concatenate([net_vecs, can_vecs, gps_vecs, lid_vecs], axis=1)
    print(f"\n  Combined benign dataset: {X.shape}")

    # 3. Scale
    print("\n[3/5] Scaling …")
    scaler = StandardScaler()
    X_sc = scaler.fit_transform(X)

    # 4. Train One-Class SVM
    print("[4/5] Training One-Class SVM …")
    # nu = upper bound on fraction of outliers in training data
    # rbf kernel captures non-linear boundary in 19-dim prob space
    ocsvm = OneClassSVM(kernel="rbf", nu=0.05, gamma="scale")
    ocsvm.fit(X_sc)
    train_preds = ocsvm.predict(X_sc)
    train_scores = ocsvm.decision_function(X_sc)
    train_normal_frac = (train_preds == 1).mean()
    print(f"  Training samples classified as normal: {train_normal_frac:.2%}")
    print(f"  Score range on training data: [{train_scores.min():.3f}, {train_scores.max():.3f}]")

    # 5. Evaluate with synthetic attack vectors (never seen during training)
    print("\n[5/5] Evaluating …")
    X_attack = make_attack_vectors(n, rng)
    X_attack_sc = scaler.transform(X_attack)
    attack_preds = ocsvm.predict(X_attack_sc)
    attack_scores = ocsvm.decision_function(X_attack_sc)

    tp = (attack_preds == -1).sum()   # correctly flagged attacks
    fp = (train_preds == -1).sum()    # normal samples wrongly flagged

    print(f"\n  Normal samples:  {n} total, {fp} flagged as anomaly  ({fp/n:.2%} false-positive rate)")
    print(f"  Attack vectors:  {n} total, {tp} detected ({tp/n:.2%} detection rate)")

    # Save artifacts
    out_dir = HERE
    joblib.dump(ocsvm, str(out_dir / "unsupervised_model.pkl"))
    joblib.dump(scaler, str(out_dir / "unsupervised_scaler.pkl"))

    meta = {
        "feat_dim": FEAT_DIM,
        "domain_dims": {"network": N_NETWORK, "can": N_CAN, "gps": N_GPS, "lidar": N_LIDAR},
        "domain_classes": {
            "network": NETWORK_CLASSES,
            "can": CAN_CLASSES,
            "gps": GPS_CLASSES,
            "lidar": LIDAR_CLASSES,
        },
        "kernel": "rbf",
        "nu": 0.05,
        "train_samples": int(n),
        "train_normal_frac": float(train_normal_frac),
        "false_positive_rate": float(fp / n),
        "detection_rate": float(tp / n),
    }
    (out_dir / "unsupervised_meta.json").write_text(json.dumps(meta, indent=2))

    save_evaluation_png(X, X_attack, train_scores, attack_scores,
                        out_dir / "unsupervised_evaluation.png")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s.")
    print(f"Artifacts: unsupervised_model.pkl, unsupervised_scaler.pkl,")
    print(f"           unsupervised_meta.json, unsupervised_evaluation.png")


if __name__ == "__main__":
    main()
