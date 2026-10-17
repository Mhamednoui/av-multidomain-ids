"""
can_test.py
===========
Full-dataset evaluation of can_runner.py on CICIoV2024.

Loads all 6 decimal CSVs (~1.4M rows total) and evaluates the runner.
Produces can_evaluation.png in codes/can/.

Run from codes/:
  python can/can_test.py
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    precision_recall_fscore_support,
)

HERE  = Path(__file__).parent
CODES = HERE.parent
DATA  = CODES / "data" / "CICIoV2024" / "decimal"

sys.path.insert(0, str(CODES))
from can.can_runner import CANDetector

CLASSES = ["BENIGN", "DoS", "GAS", "RPM", "SPEED", "STEERING_WHEEL"]
CLASS_FILES = {
    "BENIGN":         DATA / "decimal_benign.csv",
    "DoS":            DATA / "decimal_DoS.csv",
    "GAS":            DATA / "decimal_spoofing-GAS.csv",
    "RPM":            DATA / "decimal_spoofing-RPM.csv",
    "SPEED":          DATA / "decimal_spoofing-SPEED.csv",
    "STEERING_WHEEL": DATA / "decimal_spoofing-STEERING_WHEEL.csv",
}
CHUNK = 50_000   # predict in chunks to avoid OOM on the large BENIGN file


def header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def save_evaluation_png(y_true, y_pred, classes, out_path: Path):
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=classes, yticklabels=classes, ax=axes[0])
    axes[0].set_title("Confusion Matrix — CICIoV2024 Full Dataset", fontsize=13)
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")
    axes[0].tick_params(axis="x", rotation=45)

    pr, rc, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=classes, zero_division=0
    )
    x = np.arange(len(classes))
    w = 0.28
    axes[1].bar(x - w, pr,  w, label="Precision", color="steelblue")
    axes[1].bar(x,     rc,  w, label="Recall",    color="darkorange")
    axes[1].bar(x + w, f1,  w, label="F1-Score",  color="seagreen")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(classes, rotation=45, ha="right")
    axes[1].set_ylim(0, 1.08)
    axes[1].set_title("Per-Class Precision / Recall / F1", fontsize=13)
    axes[1].set_ylabel("Score")
    axes[1].legend()
    for i, f in enumerate(f1):
        axes[1].text(i + w, f + 0.01, f"{f:.2f}", ha="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  Plot saved -> {out_path}")


def main():
    print("Loading CANDetector ...")
    det = CANDetector()
    print(f"  Features expected : {len(det._features)}")
    print(f"  Classes           : {list(det._label_map.values())}")

    header("Full dataset evaluation  (CICIoV2024 decimal/)")

    all_true = []
    all_pred = []

    for label, csv_path in CLASS_FILES.items():
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        n = len(df)
        print(f"  {label:<18}: {n:>8,} rows", end="", flush=True)

        preds = []
        for start in range(0, n, CHUNK):
            chunk = df.iloc[start:start + CHUNK]
            res   = det.predict(chunk)
            preds.extend(r["label_name"] for r in res)

        all_true.extend([label] * n)
        all_pred.extend(preds)

        cls_acc = sum(p == label for p in preds) / n
        print(f"  acc={cls_acc*100:.2f}%")

    acc = accuracy_score(all_true, all_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        all_true, all_pred, average="weighted", zero_division=0
    )

    print(f"\n  Total rows: {len(all_true):,}")
    print(f"  Accuracy  : {acc*100:.2f}%")
    print(f"  Precision : {precision*100:.2f}%")
    print(f"  Recall    : {recall*100:.2f}%")
    print(f"  F1-Score  : {f1*100:.2f}%")
    print("\n" + classification_report(all_true, all_pred, labels=CLASSES,
                                       target_names=CLASSES, zero_division=0))

    save_evaluation_png(all_true, all_pred, CLASSES, HERE / "can_evaluation.png")

    header("SUMMARY")
    ok = acc >= 0.90
    print(f"  Dataset : CICIoV2024 decimal/ (6 files)")
    print(f"  Rows    : {len(all_true):,}")
    print(f"  Accuracy: {acc*100:.2f}%  {'[PASS]' if ok else '[FAIL]'}")
    print(f"  PNG     : {HERE / 'can_evaluation.png'}")


if __name__ == "__main__":
    main()
