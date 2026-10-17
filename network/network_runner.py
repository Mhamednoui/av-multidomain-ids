"""
network_runner.py
=================
Inference API for external network intrusion detection (CICIDS2017).
Loads artifacts produced by network_train.py.

Quick start:
    from network.network_runner import NetworkDetector
    det = NetworkDetector()
    result = det.predict_one({ "Flow Duration": 4, "Total Fwd Packets": 2, ... })
    # -> { "label_id": 0, "label_name": "BENIGN", "confidence": 0.99, "probabilities": {...} }
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


class NetworkDetector:
    """
    External network intrusion detector.

    Input:  raw network flow dict/DataFrame — must contain the 43 selected features.
    Output: { label_id, label_name, confidence, probabilities }

    Classes: BENIGN, Bot, BruteForce, DoS, Infiltration, PortScan, WebAttack
    """

    def __init__(
        self,
        model_path:    str = None,
        scaler_path:   str = None,
        encoder_path:  str = None,
        features_path: str = None,
    ):
        model_path    = Path(model_path)    if model_path    else HERE / "network_model.json"
        scaler_path   = Path(scaler_path)   if scaler_path   else HERE / "network_scaler.pkl"
        encoder_path  = Path(encoder_path)  if encoder_path  else HERE / "network_label_encoder.pkl"
        features_path = Path(features_path) if features_path else HERE / "network_features.json"

        for p in (model_path, scaler_path, encoder_path, features_path):
            if not p.exists():
                raise FileNotFoundError(f"Missing artifact: {p}")

        self._model = xgb.XGBClassifier()
        self._model.load_model(model_path)
        self._scaler  = joblib.load(scaler_path)
        self._encoder = joblib.load(encoder_path)

        with open(features_path) as f:
            self._features = json.load(f)

        self._label_map = {i: cls for i, cls in enumerate(self._encoder.classes_)}

    # ── input normalisation ──────────────────────────────────────────────────

    def _to_dataframe(self, data: Union[Dict, List[Dict], pd.Series, pd.DataFrame]) -> pd.DataFrame:
        if isinstance(data, pd.DataFrame):
            return data.copy()
        if isinstance(data, pd.Series):
            return data.to_frame().T.reset_index(drop=True)
        if isinstance(data, dict):
            return pd.DataFrame([data])
        if isinstance(data, list):
            if not data:
                raise ValueError("Input list is empty.")
            if isinstance(data[0], dict):
                return pd.DataFrame(data)
            arr = np.array(data)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            if arr.shape[1] != len(self._features):
                raise ValueError(
                    f"Expected {len(self._features)} features, got {arr.shape[1]}. "
                    "Use a dict or DataFrame with named columns."
                )
            return pd.DataFrame(arr, columns=self._features)
        raise TypeError(f"Unsupported input type: {type(data)}")

    # ── preprocessing ────────────────────────────────────────────────────────

    def _preprocess(self, df: pd.DataFrame) -> np.ndarray:
        missing = [f for f in self._features if f not in df.columns]
        if missing:
            raise ValueError(f"Input is missing required features:\n  {missing}")
        df = df[self._features].replace([np.inf, -np.inf], np.nan).fillna(0)
        return self._scaler.transform(df)

    # ── public API ───────────────────────────────────────────────────────────

    def predict(self, data: Union[Dict, List[Dict], pd.Series, pd.DataFrame]) -> List[Dict[str, Any]]:
        """
        Predict on one or more network flow records.

        Parameters
        ----------
        data : dict | list[dict] | pd.Series | pd.DataFrame
            Must contain at minimum the 43 required feature columns.

        Returns
        -------
        list of dicts, each with:
            label_id      int   — numeric class index
            label_name    str   — class name (BENIGN, Bot, DoS, ...)
            confidence    float — probability of predicted class
            probabilities dict  — {class_name: probability} for all 7 classes
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
            })
        return results

    def predict_one(self, data: Union[Dict, pd.Series]) -> Dict[str, Any]:
        """Convenience wrapper — returns a single result dict instead of a list."""
        return self.predict(data)[0]

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Predict on a full DataFrame and return results as a DataFrame.

        Returns columns: label_id, label_name, confidence, + one column per class.
        """
        results = self.predict(df)
        rows = []
        for r in results:
            row = {"label_id": r["label_id"], "label_name": r["label_name"],
                   "confidence": r["confidence"]}
            row.update(r["probabilities"])
            rows.append(row)
        return pd.DataFrame(rows)
