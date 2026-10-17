"""
network_train.py
================
Training pipeline for CICIDS2017 external network IDS.

The preprocessing (k-means cluster sampling, information-gain feature selection)
and the tuned XGBoost hyperparameters are adapted from MTH-IDS by Li Yang,
Abdallah Moubayed and Abdallah Shami (MIT licence), see THIRD_PARTY_NOTICES.md.

Outputs (saved next to this script in network/):
  network_model.json
  network_scaler.pkl
  network_label_encoder.pkl
  network_features.json
  network_evaluation.png

Usage:
  python network/network_train.py
  python network/network_train.py --data ../data/CICIDS2017_sample.csv
"""

import argparse
import json
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import xgboost as xgb
from imblearn.over_sampling import SMOTE
from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_selection import mutual_info_classif
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

HERE = Path(__file__).parent

IG_THRESHOLD   = 0.9
KMEANS_K       = 1000
SAMPLE_FRAC    = 0.008
TEST_SIZE      = 0.2
RANDOM_STATE   = 0

XGB_PARAMS = dict(
    learning_rate    = 0.17630368113106493,
    n_estimators     = 240,
    max_depth        = 3,
    subsample        = 0.9169895211023081,
    colsample_bytree = 0.9980218077025694,
    use_label_encoder= False,
    eval_metric      = "mlogloss",
)


def load_and_clean(csv_path: Path) -> pd.DataFrame:
    print("[1/7] Loading data ...")
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.fillna(0, inplace=True)
    print(f"      Shape: {df.shape}")
    print(f"      Label distribution:\n{df['Label'].value_counts()}")
    return df


def normalize_full(df: pd.DataFrame) -> pd.DataFrame:
    print("[2/7] Normalising full feature set ...")
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if "Label" in num_cols:
        num_cols.remove("Label")
    df[num_cols] = df[num_cols].apply(lambda x: (x - x.mean()) / x.std())
    df.fillna(0, inplace=True)
    return df


def encode_labels(df: pd.DataFrame, out_dir: Path):
    print("[3/7] Encoding labels ...")
    le = LabelEncoder()
    df["Label"] = le.fit_transform(df["Label"])
    joblib.dump(le, out_dir / "network_label_encoder.pkl")
    print(f"      Classes: {list(zip(le.classes_, le.transform(le.classes_)))}")
    return df, le


def kmeans_sample(df: pd.DataFrame) -> pd.DataFrame:
    print("[4/7] K-means cluster sampling ...")
    minority_mask = df["Label"].isin([1, 4, 6])
    df_minor = df[minority_mask]
    df_major = df[~minority_mask].copy()
    X_major = df_major.drop(["Label"], axis=1)
    km = MiniBatchKMeans(n_clusters=KMEANS_K, random_state=RANDOM_STATE)
    df_major["_klabel"] = km.fit_predict(X_major)
    df_sampled = df_major.groupby("_klabel", group_keys=False).apply(
        lambda g: g.sample(frac=SAMPLE_FRAC, random_state=RANDOM_STATE)
    )
    if "_klabel" in df_sampled.columns:
        df_sampled = df_sampled.drop(columns=["_klabel"])
    df_out = pd.concat([df_sampled, df_minor], ignore_index=True)
    print(f"      Sampled shape: {df_out.shape}")
    return df_out


def select_features(df: pd.DataFrame):
    print("[5/7] Feature selection by Information Gain ...")
    features = df.drop(["Label"], axis=1).columns
    X = df.drop(["Label"], axis=1).values
    y = df["Label"].values
    importances = mutual_info_classif(X, y, random_state=RANDOM_STATE)
    total = importances.sum()
    f_list = sorted(zip(importances / total, features), reverse=True)
    cum, fs = 0.0, []
    for score, feat in f_list:
        cum += score
        fs.append(feat)
        if cum >= IG_THRESHOLD:
            break
    print(f"      Selected {len(fs)} / {len(features)} features covering {IG_THRESHOLD*100:.0f}% of importance")
    return fs


def scale_and_save(df: pd.DataFrame, fs: list, out_dir: Path):
    print("[6/7] Scaling selected features ...")
    df_fs = df[fs].copy()
    df_fs.replace([np.inf, -np.inf], np.nan, inplace=True)
    df_fs.fillna(0, inplace=True)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_fs)
    joblib.dump(scaler, out_dir / "network_scaler.pkl")
    with open(out_dir / "network_features.json", "w") as f:
        json.dump(list(fs), f, indent=2)
    print(f"      Scaler + features saved -> {out_dir}")
    return X_scaled, scaler


def train_and_evaluate(X: np.ndarray, y: np.ndarray, fs: list,
                       le: LabelEncoder, out_dir: Path):
    print("[7/7] Training XGBoost ...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
    smote = SMOTE(random_state=RANDOM_STATE)
    X_train, y_train = smote.fit_resample(X_train, y_train)
    print(f"      After SMOTE: {X_train.shape}")

    model = xgb.XGBClassifier(**XGB_PARAMS)
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=50)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average="weighted")

    print("\n" + "=" * 60)
    print("  EVALUATION RESULTS")
    print("=" * 60)
    print(f"  Accuracy  : {acc*100:.2f}%")
    print(f"  Precision : {precision*100:.2f}%")
    print(f"  Recall    : {recall*100:.2f}%")
    print(f"  F1-Score  : {f1*100:.2f}%")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    cm = confusion_matrix(y_test, y_pred)
    fig, axes = plt.subplots(1, 2, figsize=(18, 6))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=le.classes_, yticklabels=le.classes_, ax=axes[0])
    axes[0].set_title("Confusion Matrix")
    axes[0].set_xlabel("Predicted")
    axes[0].set_ylabel("Actual")
    axes[0].tick_params(axis="x", rotation=45)

    imp = model.feature_importances_
    top_idx = np.argsort(imp)[-20:][::-1]
    top_names = [fs[i] for i in top_idx]
    axes[1].barh(top_names[::-1], imp[top_idx][::-1], color="steelblue")
    axes[1].set_title("Top 20 Feature Importances")
    axes[1].set_xlabel("Importance")

    plt.tight_layout()
    plot_path = out_dir / "network_evaluation.png"
    plt.savefig(plot_path, dpi=150)
    print(f"  Plot saved -> {plot_path}")

    model_path = out_dir / "network_model.json"
    model.save_model(model_path)
    print(f"  Model saved -> {model_path}")
    print("=" * 60)
    return model


def main():
    parser = argparse.ArgumentParser(description="Train CICIDS2017 IDS model")
    parser.add_argument(
        "--data",
        default=str(HERE.parent / "data" / "CICIDS2017_sample.csv"),
        help="Path to raw CICIDS2017 CSV",
    )
    args = parser.parse_args()
    out_dir  = HERE
    csv_path = Path(args.data)

    df          = load_and_clean(csv_path)
    df          = normalize_full(df)
    df, le      = encode_labels(df, out_dir)
    df          = kmeans_sample(df)
    fs          = select_features(df)
    y           = df["Label"].values
    X_scaled, _ = scale_and_save(df, fs, out_dir)
    train_and_evaluate(X_scaled, y, fs, le, out_dir)

    print("`n[OK] All artifacts saved:")
    for name in ("network_model.json", "network_scaler.pkl",
                 "network_label_encoder.pkl", "network_features.json",
                 "network_evaluation.png"):
        print(f"     {out_dir / name}")


if __name__ == "__main__":
    main()
