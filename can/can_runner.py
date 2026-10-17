"""
can_runner.py
=============
Inference API for CAN bus intrusion detection (CICIoV2024).
Loads the artifacts produced by can_train.py.

Quick start:
    from can.can_runner import CANDetector
    det = CANDetector()
    result = det.predict_one({"ID": 0x513, "DATA_0": 0, "DATA_1": 0, ..., "DATA_7": 156})
    # -> { "label_id": 0, "label_name": "BENIGN", "confidence": 0.99,
    #      "probabilities": {...}, "is_attack": False }
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Dict, List, Union

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent

_DATA_COLS = ["DATA_0", "DATA_1", "DATA_2", "DATA_3",
              "DATA_4", "DATA_5", "DATA_6", "DATA_7"]


def _engineer(df: pd.DataFrame, id_freq: dict) -> pd.DataFrame:
    """Feature engineering — exact replica of the training pipeline.

    id_freq must be the global frequency table loaded from can_id_frequency.json,
    NOT recomputed from the input batch (batch size is too small to be meaningful).
    Unknown IDs fall back to 1.
    """
    df = df.copy()

    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(np.int64)
    for col in _DATA_COLS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(np.int64)

    # Map against the GLOBAL frequency table saved at training time
    df["ID_frequency"] = df["ID"].map(id_freq).fillna(1).astype(int)

    # Byte diffs (row-to-row, first row = 0)
    for col in _DATA_COLS:
        df[f"{col}_diff"] = df[col].diff().fillna(0)

    # Per-row entropy of the 8 data bytes
    data_vals = df[_DATA_COLS].values.astype(np.float64)
    row_min   = data_vals.min(axis=1, keepdims=True)
    row_max   = data_vals.max(axis=1, keepdims=True)
    row_range = np.where(row_max - row_min == 0, 1, row_max - row_min)
    normalized = (data_vals - row_min) / row_range
    normalized = np.clip(normalized + 1e-10, 0, None)
    probs = normalized / normalized.sum(axis=1, keepdims=True)
    df["data_entropy"] = (-probs * np.log(probs + 1e-10)).sum(axis=1)

    # Statistical features
    df["data_mean"]  = df[_DATA_COLS].mean(axis=1)
    df["data_std"]   = df[_DATA_COLS].std(axis=1).fillna(0)
    df["zero_count"] = (df[_DATA_COLS] == 0).sum(axis=1)
    df["data_max"]   = df[_DATA_COLS].max(axis=1)
    df["data_min"]   = df[_DATA_COLS].min(axis=1)

    return df


class CANDetector:
    """
    CAN bus intrusion detector.

    Input:  raw CAN packet — must have keys: ID, DATA_0 … DATA_7
    Output: { label_id, label_name, confidence, probabilities, is_attack }

    Classes: BENIGN, DoS, GAS, RPM, SPEED, STEERING_WHEEL
    """

    def __init__(
        self,
        model_path:    str = None,
        scaler_path:   str = None,
        encoder_path:  str = None,
        features_path: str = None,
        id_freq_path:  str = None,
    ):
        model_path    = Path(model_path)    if model_path    else HERE / "can_model.json"
        scaler_path   = Path(scaler_path)   if scaler_path   else HERE / "can_scaler.pkl"
        encoder_path  = Path(encoder_path)  if encoder_path  else HERE / "can_label_encoder.pkl"
        features_path = Path(features_path) if features_path else HERE / "can_features.json"
        id_freq_path  = Path(id_freq_path)  if id_freq_path  else HERE / "can_id_frequency.json"

        for p in (model_path, scaler_path, encoder_path, features_path, id_freq_path):
            if not p.exists():
                raise FileNotFoundError(f"Missing artifact: {p}")

        self._model   = xgb.XGBClassifier()
        self._model.load_model(model_path)
        self._scaler  = joblib.load(scaler_path)
        self._encoder = joblib.load(encoder_path)

        with open(features_path) as f:
            self._features = json.load(f)

        # Global ID frequency table — must match training distribution
        with open(id_freq_path) as f:
            raw = json.load(f)
        self._id_freq = {int(k): int(v) for k, v in raw.items()}

        self._label_map = {i: cls for i, cls in enumerate(self._encoder.classes_)}

    # ── input normalisation ──────────────────────────────────────────────────

    def _to_dataframe(self, data: Union[Dict, List[Dict], pd.DataFrame]) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if isinstance(data, dict):
            return pd.DataFrame([data])
        if isinstance(data, list):
            if not data:
                raise ValueError("Input list is empty.")
            return pd.DataFrame(data)
        raise TypeError(f"Unsupported input type: {type(data)}")

    # ── preprocessing ────────────────────────────────────────────────────────

    def _preprocess(self, df: pd.DataFrame) -> np.ndarray:
        required = ["ID"] + _DATA_COLS
        missing  = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Input is missing required columns: {missing}")
        df = _engineer(df, self._id_freq)
        df = df[self._features].replace([np.inf, -np.inf], np.nan).fillna(0)
        return self._scaler.transform(df)

    # ── public API ───────────────────────────────────────────────────────────

    def predict(self, data: Union[Dict, List[Dict], pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Predict on one or more CAN packets.

        Parameters
        ----------
        data : dict | list[dict] | pd.DataFrame
            Each record must have: ID (int), DATA_0 … DATA_7 (int 0-255)

        Returns
        -------
        list of dicts, each with:
            label_id      int   — numeric class index
            label_name    str   — class name (BENIGN, DoS, GAS, RPM, SPEED, STEERING_WHEEL)
            confidence    float — probability of predicted class
            probabilities dict  — {class_name: probability} for all 6 classes
            is_attack     bool  — True for any non-BENIGN prediction
        """
        df     = self._to_dataframe(data)
        X      = self._preprocess(df)
        preds  = self._model.predict(X).astype(int)
        probas = self._model.predict_proba(X)

        results = []
        for lid, proba in zip(preds, probas):
            cls = self._label_map[lid]
            results.append({
                "label_id":      int(lid),
                "label_name":    cls,
                "confidence":    round(float(proba[lid]), 4),
                "probabilities": {
                    self._label_map[i]: round(float(p), 4)
                    for i, p in enumerate(proba)
                },
                "is_attack":     cls != "BENIGN",
            })
        return results

    def predict_one(self, data: Union[Dict, pd.Series]) -> Dict[str, Any]:
        """Convenience wrapper — returns a single result dict instead of a list."""
        if isinstance(data, pd.Series):
            data = data.to_dict()
        return self.predict(data)[0]

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict on a full DataFrame and return results as a DataFrame.

        Returns columns: label_id, label_name, confidence, is_attack, + one column per class.
        """
        results = self.predict(df)
        rows = []
        for r in results:
            row = {"label_id": r["label_id"], "label_name": r["label_name"],
                   "confidence": r["confidence"], "is_attack": r["is_attack"]}
            row.update(r["probabilities"])
            rows.append(row)
        return pd.DataFrame(rows)
