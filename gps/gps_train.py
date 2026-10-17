"""
gps_train.py
============
Training pipeline for GPS spoofing detection.
Dataset: AV-GPS-Dataset (4 CSVs, 44 features, binary: Normal=0 / Spoofing=1)

Outputs (saved to same folder as this script):
  gps_model.json          XGBoost model
  gps_scaler.pkl          StandardScaler
  gps_features.json       Ordered feature list (raw + engineered, 47 total)

Usage:
  python gps_train.py
  python gps_train.py --data ../data/AV-GPS-Dataset
"""

import argparse
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    accuracy_score, average_precision_score,
    classification_report, confusion_matrix,
    precision_recall_fscore_support, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
DROP_COLS = [
    "Clock Time", "Clock Date", "GPS MGRS",
    "Hobbs", "Run Time",
    "Heading To Next WP (deg)",
    "Distance To GCS (m)",
    "Heading To Home (deg)",
    "Mission Index",
]

LOW_SAT_THRESHOLD   = 5
POOR_HDOP_THRESHOLD = 2.0
POOR_VDOP_THRESHOLD = 3.0

XGB_PARAMS = dict(
    learning_rate    = 0.05,
    n_estimators     = 500,
    max_depth        = 6,
    subsample        = 0.8,
    colsample_bytree = 0.8,
    use_label_encoder= False,
    eval_metric      = "logloss",
    random_state     = 42,
)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Load & clean
# ─────────────────────────────────────────────────────────────────────────────
def load_and_clean(data_dir: Path) -> pd.DataFrame:
    print("\n[1/5] Loading data ...")
    csvs = sorted(data_dir.glob("AV-GPS-Dataset-*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No AV-GPS-Dataset-*.csv files found in {data_dir}")

    # Use first 3 CSVs for training (matches original notebook)
    dfs = [pd.read_csv(f) for f in csvs[:3]]
    df  = pd.concat(dfs, ignore_index=True)
    print(f"      Loaded {len(csvs[:3])} files -> shape: {df.shape}")
    print(f"      Class distribution:\n{df['Data Type'].value_counts().to_string()}")

    # Drop metadata/text columns
    df.drop(columns=[c for c in DROP_COLS if c in df.columns], inplace=True)

    # Dedup + dropna
    df.drop_duplicates(inplace=True)
    df.dropna(inplace=True)
    df.reset_index(drop=True, inplace=True)
    print(f"      After dedup + dropna: {df.shape}")

    # Clip extreme outliers per column (1st–99th percentile)
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    num_cols.remove("Data Type")
    for col in num_cols:
        df[col] = df[col].clip(lower=df[col].quantile(0.01),
                               upper=df[col].quantile(0.99))

    print(f"      Final class distribution:\n{df['Data Type'].value_counts().to_string()}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Feature engineering
# ─────────────────────────────────────────────────────────────────────────────
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[2/5] Engineering features ...")
    df = df.sort_index().reset_index(drop=True)

    df["lat_delta"]     = df["GPS Latitude"].diff().fillna(0)
    df["lon_delta"]     = df["GPS Longitude"].diff().fillna(0)
    df["alt_delta"]     = df["Relative Altitude (m)"].diff().fillna(0)
    df["vel_delta"]     = df["Velocity (m/s)"].diff().fillna(0)

    df["position_jump"]  = np.sqrt(df["lat_delta"]**2 + df["lon_delta"]**2)

    df["velocity_ratio"] = df["Velocity (m/s)"] / (
        df["Absolute Longitudinal Velocity (m/s)"] + 1e-6
    )

    df["heading_diff"] = abs(df["GPS Course"] - df["Heading (deg)"])
    df["heading_diff"] = df["heading_diff"].apply(
        lambda x: x if x <= 180 else 360 - x
    )

    df["sat_drop"]  = df["Satellite Count"].diff().fillna(0)
    df["low_sat"]   = (df["Satellite Count"] < LOW_SAT_THRESHOLD).astype(int)
    df["poor_hdop"] = (df["GPS HDOP"] > POOR_HDOP_THRESHOLD).astype(int)
    df["poor_vdop"] = (df["GPS VDOP"] > POOR_VDOP_THRESHOLD).astype(int)

    df["alt_discrepancy"] = abs(
        df["Relative Altitude (m)"] - df["Vertical Position (m)"]
    )

    df["total_vibration"] = (
        df["Longitudinal Vibration"]
        + df["Lateral Vibration"]
        + df["Vertical Vibration"]
    )

    print(f"      Shape after engineering: {df.shape}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Split + scale
# ─────────────────────────────────────────────────────────────────────────────
def split_and_scale(df: pd.DataFrame, out_dir: Path):
    print("\n[3/5] Splitting and scaling ...")
    X = df.drop(columns=["Data Type"])
    y = df["Data Type"]

    print(f"      Features: {X.shape[1]}  |  Samples: {len(X)}")
    print(f"      Normal: {(y==0).sum()}  Spoofing: {(y==1).sum()}  Ratio: {(y==0).sum()/(y==1).sum():.2f}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Fit scaler on training data only (as a DataFrame to preserve feature_names_in_)
    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s  = scaler.transform(X_test)

    scaler_path = out_dir / "gps_scaler.pkl"
    joblib.dump(scaler, scaler_path)
    print(f"      Scaler saved -> {scaler_path}")

    features_path = out_dir / "gps_features.json"
    with open(features_path, "w") as f:
        json.dump(list(scaler.feature_names_in_), f, indent=2)
    print(f"      Features saved -> {features_path}  ({len(scaler.feature_names_in_)} features)")

    return X_train_s, X_test_s, y_train, y_test, X.columns.tolist()


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Train XGBoost
# ─────────────────────────────────────────────────────────────────────────────
def train(X_train, X_test, y_train, y_test, out_dir: Path):
    print("\n[4/5] Training XGBoost ...")
    model = xgb.XGBClassifier(**XGB_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=100,
    )

    model_path = out_dir / "gps_model.json"
    model.save_model(model_path)
    print(f"      Model saved -> {model_path}")
    return model


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5 — Evaluate
# ─────────────────────────────────────────────────────────────────────────────
def evaluate(model, X_test, y_test, feature_names, out_dir: Path):
    print("\n[5/5] Evaluating ...")
    y_pred  = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    acc = accuracy_score(y_test, y_pred)
    p, r, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted")

    print("\n" + "="*60)
    print("  RESULTS")
    print("="*60)
    print(f"  Accuracy  : {acc*100:.2f}%")
    print(f"  Precision : {p*100:.2f}%")
    print(f"  Recall    : {r*100:.2f}%")
    print(f"  F1-Score  : {f1*100:.2f}%")
    print(f"  ROC-AUC   : {roc_auc_score(y_test, y_proba):.4f}")
    print(f"  PR-AUC    : {average_precision_score(y_test, y_proba):.4f}")
    print("\n  Classification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=["Normal", "Spoofing"]))

    # Confusion matrix plot
    cm = confusion_matrix(y_test, y_pred)
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["Normal", "Spoofing"],
                yticklabels=["Normal", "Spoofing"], ax=axes[0])
    axes[0].set_title("Confusion Matrix")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")

    # Top-20 feature importance
    imp = model.feature_importances_
    top_idx  = np.argsort(imp)[-20:][::-1]
    top_names = [feature_names[i] for i in top_idx]
    top_vals  = imp[top_idx]
    axes[1].barh(top_names[::-1], top_vals[::-1], color="steelblue")
    axes[1].set_title("Top 20 Feature Importances")
    axes[1].set_xlabel("Importance")

    plt.tight_layout()
    plot_path = out_dir / "gps_evaluation.png"
    plt.savefig(plot_path, dpi=150)
    print(f"\n  Plot saved -> {plot_path}")
    print("="*60)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Train GPS spoofing detection model")
    parser.add_argument("--data", default=str(HERE.parent / "data" / "AV-GPS-Dataset"),
                        help="Path to AV-GPS-Dataset folder")
    args = parser.parse_args()

    data_dir = Path(args.data)
    out_dir  = HERE  # save artifacts next to this script

    df                             = load_and_clean(data_dir)
    df                             = engineer_features(df)
    X_train, X_test, y_train, y_test, feat_names = split_and_scale(df, out_dir)
    model                          = train(X_train, X_test, y_train, y_test, out_dir)
    evaluate(model, X_test, y_test, feat_names, out_dir)

    print("\n[OK] All artifacts saved:")
    print(f"     {out_dir / 'gps_model.json'}")
    print(f"     {out_dir / 'gps_scaler.pkl'}")
    print(f"     {out_dir / 'gps_features.json'}")


if __name__ == "__main__":
    main()
