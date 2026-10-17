"""
network_test.py
===============
Full-dataset evaluation of network_runner.py on CICIDS2017.

Evaluates on CICIDS2017_sample_km_test.csv (56,661 rows, all 7 classes).
Produces network_evaluation.png in codes/network/.

Run from codes/:
  python network/network_test.py
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
DATA  = CODES / "data"

sys.path.insert(0, str(CODES))
from network.network_runner import NetworkDetector

CLASSES = ["BENIGN", "Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"]


def header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def save_evaluation_png(y_true, y_pred, classes, out_path: Path):
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    fig, axes = plt.subplots(1, 2, figsize=(18, 7))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=classes, yticklabels=classes, ax=axes[0])
    axes[0].set_title("Confusion Matrix — CICIDS2017 Full Dataset", fontsize=13)
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")
    axes[0].tick_params(axis="x", rotation=45)

    pr, rc, f1, sup = precision_recall_fscore_support(
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
    print("Loading NetworkDetector ...")
    det = NetworkDetector()
    print(f"  Features expected : {len(det._features)}")
    print(f"  Classes           : {list(det._label_map.values())}")

    csv_path = DATA / "CICIDS2017_sample_km_test.csv"
    header(f"Full dataset evaluation  ({csv_path.name})")

    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    df.replace([float("inf"), float("-inf")], 0, inplace=True)
    df.fillna(0, inplace=True)

    print(f"  Total rows: {len(df):,}")
    print(f"  Class distribution:\n{df['Label'].value_counts().to_string()}")

    y_true = df["Label"].tolist()
    X      = df.drop(columns=["Label"])

    print("\n  Running predictions ...")
    results = det.predict(X)
    y_pred  = [r["label_name"] for r in results]

    acc = accuracy_score(y_true, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="weighted", zero_division=0
    )

    print(f"\n  Accuracy  : {acc*100:.2f}%")
    print(f"  Precision : {precision*100:.2f}%")
    print(f"  Recall    : {recall*100:.2f}%")
    print(f"  F1-Score  : {f1*100:.2f}%")

    present = [c for c in CLASSES if c in set(y_true)]
    print("\n" + classification_report(y_true, y_pred, labels=present,
                                       target_names=present, zero_division=0))

    save_evaluation_png(y_true, y_pred, present, HERE / "network_evaluation.png")

    header("SUMMARY")
    ok = acc >= 0.90
    print(f"  Dataset : {csv_path.name}")
    print(f"  Rows    : {len(df):,}")
    print(f"  Accuracy: {acc*100:.2f}%  {'[PASS]' if ok else '[FAIL]'}")
    print(f"  PNG     : {HERE / 'network_evaluation.png'}")


if __name__ == "__main__":
    main()
