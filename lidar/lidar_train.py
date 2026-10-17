"""
LiDAR IDS — Training script.

Strategy: supervised XGBoost (GPU) trained on real KITTI scans (Normal) +
synthetically perturbed scans (3 attack types). This gives labelled data and
clean class probabilities for the fusion layer — identical interface to all
other domain detectors.

Attack synthesis (no labelled attack dataset available):
  1. PointDrop     — randomly zero out 40-70% of points (blind-spot spoofing)
  2. IntensitySpoof — clamp all intensities to [0.9, 1.0] (reflective spoofing)
  3. GhostCluster  — inject a dense rectangular cluster at a fixed position

Run with:
    python lidar/lidar_train.py
"""
import argparse
import json
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from imblearn.over_sampling import SMOTE
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
import xgboost as xgb

HERE = Path(__file__).parent
DATA_ROOT = HERE.parent / "data" / "Depth"

SEQ_DIRS = [
    DATA_ROOT / "2011_09_26_drive_0001_sync" / "2011_09_26" /
    "2011_09_26_drive_0001_sync" / "velodyne_points" / "data",
    DATA_ROOT / "2011_09_26_drive_0015_sync" / "2011_09_26" /
    "2011_09_26_drive_0015_sync" / "velodyne_points" / "data",
]

N_RINGS = 64          # elevation histogram bins
N_DIST_RINGS = 8      # range-ring occupancy bins
LABEL_NAMES = ["Normal", "PointDrop", "IntensitySpoof", "GhostCluster"]
RNG = np.random.default_rng(42)


# ── Feature extraction ──────────────────────────────────────────────────────

def extract_features(pts: np.ndarray) -> np.ndarray:
    """Extract a fixed-length feature vector from an N×4 point cloud."""
    if len(pts) == 0:
        return np.zeros(N_RINGS + N_DIST_RINGS + 14, dtype=np.float32)

    x, y, z, intensity = pts[:, 0], pts[:, 1], pts[:, 2], pts[:, 3]
    r = np.sqrt(x**2 + y**2)
    elev = np.degrees(np.arctan2(z, r))

    # Global stats
    n_pts = len(pts)
    z_mean, z_std = z.mean(), z.std()
    i_mean, i_std = intensity.mean(), intensity.std()
    r_mean, r_max = r.mean(), r.max()

    # Ground plane: points below -0.4 m assumed ground
    ground_mask = z < -0.4
    n_ground = ground_mask.sum()
    ground_z_mean = z[ground_mask].mean() if n_ground > 0 else 0.0
    ground_residual = float(z_mean - ground_z_mean)

    # Elevation ring density (64 bins)
    elev_hist, _ = np.histogram(elev, bins=N_RINGS, range=(-25.0, 15.0), density=True)

    # Radial ring occupancy (8 rings, 0–80 m)
    dist_hist, _ = np.histogram(r, bins=N_DIST_RINGS, range=(0.0, 80.0), density=True)

    # Bounding-box volume of foreground cluster (non-ground)
    fg = pts[~ground_mask]
    if len(fg) > 10:
        bb_vol = float(
            (fg[:, 0].max() - fg[:, 0].min()) *
            (fg[:, 1].max() - fg[:, 1].min()) *
            (fg[:, 2].max() - fg[:, 2].min())
        )
    else:
        bb_vol = 0.0

    # Intensity distribution shape
    i_p10, i_p90 = np.percentile(intensity, 10), np.percentile(intensity, 90)
    i_iqr = float(i_p90 - i_p10)
    # fraction of very-high-intensity points (reflective spoof signature)
    i_high_frac = float((intensity > 0.85).mean())

    global_feats = np.array([
        n_pts, z_mean, z_std, i_mean, i_std,
        r_mean, r_max, n_ground / (n_pts + 1e-6),
        ground_residual, bb_vol,
        i_iqr, i_high_frac,
        elev.min(), elev.max(),
    ], dtype=np.float32)

    return np.concatenate([global_feats, elev_hist.astype(np.float32),
                           dist_hist.astype(np.float32)])


def feature_names() -> list[str]:
    names = [
        "n_pts", "z_mean", "z_std", "intensity_mean", "intensity_std",
        "r_mean", "r_max", "ground_frac", "ground_residual", "bb_vol",
        "intensity_iqr", "intensity_high_frac",
        "elev_min", "elev_max",
    ]
    names += [f"ring_{i:02d}" for i in range(N_RINGS)]
    names += [f"dist_ring_{i}" for i in range(N_DIST_RINGS)]
    return names


# ── Attack synthesis ─────────────────────────────────────────────────────────

def synth_point_drop(pts: np.ndarray) -> np.ndarray:
    """Drop 40–70% of points randomly."""
    keep = RNG.random(len(pts)) > RNG.uniform(0.40, 0.70)
    return pts[keep] if keep.sum() > 100 else pts[:100]


def synth_intensity_spoof(pts: np.ndarray) -> np.ndarray:
    """Clamp intensities to near-max (reflective tape / retroreflector attack)."""
    out = pts.copy()
    out[:, 3] = RNG.uniform(0.88, 1.0, size=len(pts)).astype(np.float32)
    return out


def synth_ghost_cluster(pts: np.ndarray) -> np.ndarray:
    """Inject a dense rectangular ghost obstacle ahead of the vehicle."""
    out = pts.copy()
    n_ghost = RNG.integers(2000, 6000)
    gx = RNG.uniform(8.0, 20.0, n_ghost).astype(np.float32)
    gy = RNG.uniform(-1.5, 1.5, n_ghost).astype(np.float32)
    gz = RNG.uniform(-1.5, 1.5, n_ghost).astype(np.float32)
    gi = RNG.uniform(0.1, 0.6, n_ghost).astype(np.float32)
    ghost = np.stack([gx, gy, gz, gi], axis=1)
    return np.concatenate([out, ghost], axis=0)


ATTACK_FNS = {
    "PointDrop": synth_point_drop,
    "IntensitySpoof": synth_intensity_spoof,
    "GhostCluster": synth_ghost_cluster,
}


# ── Data loading ─────────────────────────────────────────────────────────────

def load_all_bins() -> list[Path]:
    bins = []
    for d in SEQ_DIRS:
        bins += sorted(d.glob("*.bin"))
    return bins


def build_dataset(bin_files: list[Path], verbose: bool = True) -> tuple:
    X, y = [], []
    n = len(bin_files)
    for idx, fp in enumerate(bin_files):
        if verbose and idx % 50 == 0:
            print(f"  [{idx}/{n}] {fp.name}")
        pts = np.fromfile(fp, dtype=np.float32).reshape(-1, 4)

        # Normal
        X.append(extract_features(pts))
        y.append(0)

        # One random attack per scan (balanced by SMOTE later)
        attack_name = RNG.choice(list(ATTACK_FNS.keys()))
        attack_pts = ATTACK_FNS[attack_name](pts)
        X.append(extract_features(attack_pts))
        y.append(LABEL_NAMES.index(attack_name))

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


# ── Evaluation PNG ────────────────────────────────────────────────────────────

def save_evaluation_png(y_true, y_pred, classes, out_path: Path):
    import seaborn as sns
    from sklearn.metrics import precision_recall_fscore_support

    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(classes))))
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(classes))), zero_division=0
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Confusion matrix
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=classes, yticklabels=classes, ax=axes[0]
    )
    axes[0].set_title("Confusion Matrix (test set)")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("True")

    # Per-class metrics
    x = np.arange(len(classes))
    w = 0.25
    axes[1].bar(x - w, prec, w, label="Precision", color="#4C72B0")
    axes[1].bar(x,     rec,  w, label="Recall",    color="#55A868")
    axes[1].bar(x + w, f1,   w, label="F1",        color="#C44E52")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(classes, rotation=15)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_title("Per-class Precision / Recall / F1")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  Saved: {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    t0 = time.time()

    print("=== LiDAR IDS Training ===")
    print(f"Feature dim: {len(feature_names())}")

    # 1. Load scans + synthesize attacks
    print("\n[1/5] Loading .bin scans and synthesizing attacks …")
    bins = load_all_bins()
    print(f"  Found {len(bins)} scans across both sequences")
    X, y = build_dataset(bins)
    print(f"  Dataset shape: {X.shape}, labels: {np.bincount(y)}")

    # 2. Train/test split
    print("\n[2/5] Splitting …")
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=args.seed
    )

    # 3. Scale
    print("[3/5] Scaling …")
    scaler = StandardScaler()
    X_tr = scaler.fit_transform(X_tr)
    X_te = scaler.transform(X_te)

    # 4. SMOTE (small dataset — ensure each class has enough samples)
    print("[4/5] SMOTE …")
    k_neighbors = min(5, min(np.bincount(y_tr)) - 1)
    sm = SMOTE(random_state=args.seed, k_neighbors=max(1, k_neighbors))
    X_tr, y_tr = sm.fit_resample(X_tr, y_tr)
    print(f"  After SMOTE: {X_tr.shape}, labels: {np.bincount(y_tr)}")

    # 5. Train XGBoost (GPU)
    print("[5/5] Training XGBoost (GPU) …")
    le = LabelEncoder()
    le.fit(list(range(len(LABEL_NAMES))))  # 0,1,2,3

    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric="mlogloss",
        device="cuda",
        random_state=args.seed,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_te, y_te)], verbose=50)

    # Evaluate
    y_pred = model.predict(X_te)
    acc = (y_pred == y_te).mean()
    f1 = f1_score(y_te, y_pred, average="weighted")
    print(f"\nTest accuracy : {acc:.4%}")
    print(f"Test F1 (w)   : {f1:.4%}")
    print(classification_report(y_te, y_pred, target_names=LABEL_NAMES))

    # Save artifacts
    out_dir = HERE
    model.save_model(str(out_dir / "lidar_model.json"))
    joblib.dump(scaler, str(out_dir / "lidar_scaler.pkl"))
    feat_names = feature_names()
    (out_dir / "lidar_features.json").write_text(json.dumps(feat_names, indent=2))

    # Save label encoder mapping
    label_map = {i: name for i, name in enumerate(LABEL_NAMES)}
    (out_dir / "lidar_label_map.json").write_text(json.dumps(label_map, indent=2))

    save_evaluation_png(y_te, y_pred, LABEL_NAMES, out_dir / "lidar_evaluation.png")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s. Artifacts saved to {out_dir}")
    print(f"  lidar_model.json, lidar_scaler.pkl, lidar_features.json,")
    print(f"  lidar_label_map.json, lidar_evaluation.png")


if __name__ == "__main__":
    main()
