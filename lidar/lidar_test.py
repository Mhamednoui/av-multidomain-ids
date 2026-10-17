"""
LiDAR IDS — Full-dataset test.

Evaluates on all 405 scans (both KITTI sequences), applies all 3 attack types
to every scan, then reports aggregate metrics and saves lidar_evaluation.png.

Run with:
    python lidar/lidar_test.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import (classification_report, confusion_matrix,
                             f1_score, precision_recall_fscore_support)

from lidar.lidar_runner import LiDARDetector, _extract_features

DATA_ROOT = HERE.parent / "data" / "Depth"
SEQ_DIRS = [
    DATA_ROOT / "2011_09_26_drive_0001_sync" / "2011_09_26" /
    "2011_09_26_drive_0001_sync" / "velodyne_points" / "data",
    DATA_ROOT / "2011_09_26_drive_0015_sync" / "2011_09_26" /
    "2011_09_26_drive_0015_sync" / "velodyne_points" / "data",
]

LABEL_NAMES = ["Normal", "PointDrop", "IntensitySpoof", "GhostCluster"]
RNG = np.random.default_rng(0)  # different seed from training


# ── Same attack functions (mirrored from train) ──────────────────────────────

def synth_point_drop(pts):
    keep = RNG.random(len(pts)) > RNG.uniform(0.40, 0.70)
    return pts[keep] if keep.sum() > 100 else pts[:100]


def synth_intensity_spoof(pts):
    out = pts.copy()
    out[:, 3] = RNG.uniform(0.88, 1.0, size=len(pts)).astype(np.float32)
    return out


def synth_ghost_cluster(pts):
    out = pts.copy()
    n_ghost = RNG.integers(2000, 6000)
    gx = RNG.uniform(8.0, 20.0, n_ghost).astype(np.float32)
    gy = RNG.uniform(-1.5, 1.5, n_ghost).astype(np.float32)
    gz = RNG.uniform(-1.5, 1.5, n_ghost).astype(np.float32)
    gi = RNG.uniform(0.1, 0.6, n_ghost).astype(np.float32)
    ghost = np.stack([gx, gy, gz, gi], axis=1)
    return np.concatenate([out, ghost], axis=0)


ATTACK_FNS = {
    "PointDrop": (1, synth_point_drop),
    "IntensitySpoof": (2, synth_intensity_spoof),
    "GhostCluster": (3, synth_ghost_cluster),
}


def save_evaluation_png(y_true, y_pred, classes, out_path: Path):
    cm = confusion_matrix(y_true, y_pred, labels=list(range(len(classes))))
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=list(range(len(classes))), zero_division=0
    )

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Blues",
        xticklabels=classes, yticklabels=classes, ax=axes[0]
    )
    axes[0].set_title("Confusion Matrix — Full Dataset")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("True")

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
    print(f"Saved: {out_path}")


def main():
    print("=== LiDAR IDS — Full Dataset Evaluation ===")
    det = LiDARDetector()

    bins = []
    for d in SEQ_DIRS:
        bins += sorted(d.glob("*.bin"))
    print(f"Total scans: {len(bins)}")

    y_true, y_pred = [], []
    n = len(bins)

    for idx, fp in enumerate(bins):
        if idx % 100 == 0:
            print(f"  [{idx}/{n}] …")

        pts = np.fromfile(fp, dtype=np.float32).reshape(-1, 4)

        # Normal
        r = det.predict_one(pts)
        y_true.append(0)
        y_pred.append(r["label_id"])

        # All 3 attack types for every scan
        for name, (label_id, fn) in ATTACK_FNS.items():
            attack_pts = fn(pts)
            r = det.predict_one(attack_pts)
            y_true.append(label_id)
            y_pred.append(r["label_id"])

    y_true = np.array(y_true)
    y_pred = np.array(y_pred)

    total = len(y_true)
    correct = (y_true == y_pred).sum()
    acc = correct / total
    f1 = f1_score(y_true, y_pred, average="weighted")

    print(f"\nTotal samples : {total}")
    print(f"Accuracy      : {acc:.4%}")
    print(f"F1 (weighted) : {f1:.4%}")
    print()
    print(classification_report(y_true, y_pred, target_names=LABEL_NAMES))

    # Per-class breakdown
    for label_id, name in enumerate(LABEL_NAMES):
        mask = y_true == label_id
        cls_acc = (y_pred[mask] == label_id).mean()
        print(f"  {name:<16s} : {cls_acc:.2%} ({mask.sum()} samples)")

    save_evaluation_png(y_true, y_pred, LABEL_NAMES, HERE / "lidar_evaluation.png")


if __name__ == "__main__":
    main()
