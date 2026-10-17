"""
gps_test.py
===========
Full-dataset evaluation of gps_runner.py on all 4 AV-GPS-Dataset files.

Loads Dataset-0 through Dataset-3 (~115,000 rows total) and evaluates.
Produces gps_evaluation.png in codes/gps/.

Run from codes/:
  python gps/gps_test.py
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
DATA  = CODES / "data" / "AV-GPS-Dataset"

sys.path.insert(0, str(CODES))
from gps.gps_runner import GPSDetector

CLASSES   = ["Normal", "Spoofing"]
LABEL_MAP = {0: "Normal", 1: "Spoofing"}
DROP_COLS = [
    "Clock Time", "Clock Date", "GPS MGRS", "Hobbs", "Run Time",
    "Heading To Next WP (deg)", "Distance To GCS (m)",
    "Heading To Home (deg)", "Mission Index",
]
CHUNK = 5_000


def header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.drop(columns=[c for c in DROP_COLS if c in df.columns], inplace=True)
    df.drop_duplicates(inplace=True)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def save_evaluation_png(y_true, y_pred, out_path: Path):
    cm = confusion_matrix(y_true, y_pred, labels=CLASSES)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=CLASSES, yticklabels=CLASSES, ax=axes[0])
    axes[0].set_title("Confusion Matrix — AV-GPS Full Dataset", fontsize=13)
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")

    pr, rc, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=CLASSES, zero_division=0
    )
    x  = np.arange(len(CLASSES))
    w  = 0.28
    axes[1].bar(x - w, pr,  w, label="Precision", color="steelblue")
    axes[1].bar(x,     rc,  w, label="Recall",    color="darkorange")
    axes[1].bar(x + w, f1,  w, label="F1-Score",  color="seagreen")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(CLASSES)
    axes[1].set_ylim(0, 1.08)
    axes[1].set_title("Per-Class Precision / Recall / F1", fontsize=13)
    axes[1].set_ylabel("Score")
    axes[1].legend()
    for i, f in enumerate(f1):
        axes[1].text(i + w, f + 0.01, f"{f:.3f}", ha="center", fontsize=9)

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"  Plot saved -> {out_path}")


def predict_df(det: GPSDetector, df: pd.DataFrame) -> list:
    """Predict in chunks, keeping temporal order within each dataset."""
    preds = []
    rows_all = df.drop(columns=["Data Type"]).to_dict(orient="records")
    for start in range(0, len(rows_all), CHUNK):
        chunk = rows_all[start:start + CHUNK]
        res   = det.predict(chunk)
        preds.extend(r["label_int"] for r in res)
    return preds


def main():
    print("Loading GPSDetector ...")
    det = GPSDetector()
    print(f"  Raw columns expected : {len(det.required_raw_columns)}")
    print(f"  Total features       : {len(det._all_features)}")

    header("Full dataset evaluation  (AV-GPS-Dataset-0 to -3)")

    all_true = []
    all_pred = []

    for i in range(4):
        csv_path = DATA / f"AV-GPS-Dataset-{i}.csv"
        df = load_dataset(csv_path)
        y_true = df["Data Type"].tolist()
        n_normal  = y_true.count(0)
        n_spoof   = y_true.count(1)
        print(f"\n  Dataset-{i}: {len(df):>6,} rows  (Normal={n_normal:,}  Spoofing={n_spoof:,})")

        y_pred = predict_df(det, df)

        acc_i = accuracy_score(y_true, y_pred)
        print(f"           acc={acc_i*100:.2f}%")

        all_true.extend([LABEL_MAP[v] for v in y_true])
        all_pred.extend([LABEL_MAP[v] for v in y_pred])

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

    save_evaluation_png(all_true, all_pred, HERE / "gps_evaluation.png")

    header("SUMMARY")
    ok = acc >= 0.90
    print(f"  Dataset : AV-GPS-Dataset-0 to -3 (4 files)")
    print(f"  Rows    : {len(all_true):,}")
    print(f"  Accuracy: {acc*100:.2f}%  {'[PASS]' if ok else '[FAIL]'}")
    print(f"  PNG     : {HERE / 'gps_evaluation.png'}")


if __name__ == "__main__":
    main()
