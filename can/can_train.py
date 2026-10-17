"""
can_train.py
============
Training pipeline for CAN bus intrusion detection (CICIoV2024).
Same pipeline as the original training notebook, plus one extra artifact:
  can_id_frequency.json  -- global ID->count map from the full dataset

Outputs (saved next to this script):
  can_model.json
  can_scaler.pkl
  can_label_encoder.pkl
  can_features.json
  can_id_frequency.json  <-- NEW: used by can_runner.py for consistent ID_frequency

Usage:
  python can/can_train.py
  python can/can_train.py --data ../data/CICIoV2024/decimal
"""

import argparse
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from imblearn.over_sampling import SMOTE
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
import xgboost as xgb

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent

DATA_COLS = ["DATA_0","DATA_1","DATA_2","DATA_3","DATA_4","DATA_5","DATA_6","DATA_7"]

CLASS_FILES = {
    "BENIGN":         "decimal_benign.csv",
    "DoS":            "decimal_DoS.csv",
    "GAS":            "decimal_spoofing-GAS.csv",
    "RPM":            "decimal_spoofing-RPM.csv",
    "SPEED":          "decimal_spoofing-SPEED.csv",
    "STEERING_WHEEL": "decimal_spoofing-STEERING_WHEEL.csv",
}


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Load
# ─────────────────────────────────────────────────────────────────────────────
def load(data_dir: Path) -> pd.DataFrame:
    print("\n[1/5] Loading data ...")
    dfs = []
    for label, fname in CLASS_FILES.items():
        path = data_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"Missing: {path}")
        df = pd.read_csv(path)
        df.columns = df.columns.str.strip()
        print(f"      {label}: {df.shape[0]:>8,} rows")
        dfs.append(df)
    df = pd.concat(dfs, ignore_index=True).sort_index().reset_index(drop=True)
    print(f"      Total: {df.shape[0]:,} rows")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Feature engineering
# ─────────────────────────────────────────────────────────────────────────────
def engineer(df: pd.DataFrame, out_dir: Path) -> tuple[pd.DataFrame, dict]:
    print("\n[2/5] Feature engineering ...")

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(np.int64)
    for col in DATA_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(np.int64)

    # ID frequency on the FULL dataset — save for inference
    id_freq = df["ID"].value_counts().to_dict()
    id_freq = {int(k): int(v) for k, v in id_freq.items()}
    freq_path = out_dir / "can_id_frequency.json"
    with open(freq_path, "w") as f:
        json.dump(id_freq, f)
    print(f"      ID frequency table saved -> {freq_path}  ({len(id_freq)} unique IDs)")

    df["ID_frequency"] = df["ID"].map(id_freq)

    for col in DATA_COLS:
        df[f"{col}_diff"] = df[col].diff().fillna(0)

    data_vals  = df[DATA_COLS].values.astype(np.float64)
    row_min    = data_vals.min(axis=1, keepdims=True)
    row_max    = data_vals.max(axis=1, keepdims=True)
    row_range  = np.where(row_max - row_min == 0, 1, row_max - row_min)
    normalized = (data_vals - row_min) / row_range
    normalized = np.clip(normalized + 1e-10, 0, None)
    probs      = normalized / normalized.sum(axis=1, keepdims=True)
    df["data_entropy"] = (-probs * np.log(probs + 1e-10)).sum(axis=1)

    df["data_mean"]  = df[DATA_COLS].mean(axis=1)
    df["data_std"]   = df[DATA_COLS].std(axis=1).fillna(0)
    df["zero_count"] = (df[DATA_COLS] == 0).sum(axis=1)
    df["data_max"]   = df[DATA_COLS].max(axis=1)
    df["data_min"]   = df[DATA_COLS].min(axis=1)

    print(f"      Shape after engineering: {df.shape}")
    return df, id_freq


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Scale + encode + split
# ─────────────────────────────────────────────────────────────────────────────
def scale_encode_split(df: pd.DataFrame, out_dir: Path):
    print("\n[3/5] Scaling, encoding, splitting ...")

    feature_cols = [c for c in df.columns
                    if c not in ("label", "category", "specific_class", "label_encoded")]
    feature_cols = [c for c in feature_cols
                    if df[c].dtype != object]

    scaler = StandardScaler()
    df[feature_cols] = scaler.fit_transform(df[feature_cols])
    df = df.fillna(0)

    le = LabelEncoder()
    df["label_encoded"] = le.fit_transform(df["specific_class"])

    joblib.dump(scaler, out_dir / "can_scaler.pkl")
    joblib.dump(le,     out_dir / "can_label_encoder.pkl")
    with open(out_dir / "can_features.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    print(f"      Features: {len(feature_cols)}")
    print(f"      Classes:  {list(zip(le.classes_, le.transform(le.classes_)))}")

    X = df[feature_cols].values
    y = df["label_encoded"].values
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=0, stratify=y
    )

    print(f"      Train: {X_train.shape}  Test: {X_test.shape}")
    return X_train, X_test, y_train, y_test, le, feature_cols


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — SMOTE + train
# ─────────────────────────────────────────────────────────────────────────────
def smote_and_train(X_train, X_test, y_train, y_test, out_dir: Path):
    print("\n[4/5] SMOTE + training ...")

    smote = SMOTE(random_state=42)
    X_train, y_train = smote.fit_resample(X_train, y_train)
    print(f"      After SMOTE: {X_train.shape}")

    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    model_path = out_dir / "can_model.json"
    model.save_model(model_path)
    print(f"      Model saved -> {model_path}")
    return model


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Evaluate
# ─────────────────────────────────────────────────────────────────────────────
def evaluate(model, X_test, y_test, le, feature_cols, out_dir: Path):
    print("\n[5/5] Evaluating ...")
    y_pred = model.predict(X_test)
    acc    = accuracy_score(y_test, y_pred)

    print(f"\n{'='*60}")
    print(f"  Accuracy: {acc*100:.2f}%")
    print(f"\n  Classification Report:")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    cm = confusion_matrix(y_test, y_pred)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=le.classes_, yticklabels=le.classes_, ax=axes[0])
    axes[0].set_title("Confusion Matrix")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")
    axes[0].tick_params(axis="x", rotation=45)

    imp      = model.feature_importances_
    top_idx  = np.argsort(imp)[-15:][::-1]
    top_names = [feature_cols[i] for i in top_idx]
    axes[1].barh(top_names[::-1], imp[top_idx][::-1], color="steelblue")
    axes[1].set_title("Top 15 Feature Importances")
    axes[1].set_xlabel("Importance")

    plt.tight_layout()
    plot_path = out_dir / "can_evaluation.png"
    plt.savefig(plot_path, dpi=150)
    print(f"  Plot saved -> {plot_path}")
    print(f"{'='*60}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train CAN bus IDS model")
    parser.add_argument("--data", default=str(HERE.parent / "data" / "CICIoV2024" / "decimal"),
                        help="Path to CICIoV2024/decimal folder")
    args     = parser.parse_args()
    data_dir = Path(args.data)
    out_dir  = HERE

    df                                        = load(data_dir)
    df, _                                     = engineer(df, out_dir)
    X_train, X_test, y_train, y_test, le, fc = scale_encode_split(df, out_dir)
    model                                     = smote_and_train(X_train, X_test, y_train, y_test, out_dir)
    evaluate(model, X_test, y_test, le, fc, out_dir)

    print("\n[OK] All artifacts saved:")
    for name in ("can_model.json","can_scaler.pkl","can_label_encoder.pkl",
                 "can_features.json","can_id_frequency.json"):
        print(f"     {out_dir / name}")


if __name__ == "__main__":
    main()
