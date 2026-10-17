"""
gps_runner.py
=============
Inference API for GPS spoofing detection.
Loads gps_model.json + gps_scaler.pkl (produced by gps_train.py).

Usage:
    from gps.gps_runner import GPSDetector

    detector = GPSDetector()
    result = detector.predict_one({ "GPS Latitude": 32.23, "GPS Longitude": -110.94, ... })
    # -> { "label": "Normal", "label_int": 0, "confidence": 0.999, "prob_normal": 0.999, "prob_spoof": 0.001 }
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any, Dict, List, Union

import joblib
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

HERE = Path(__file__).parent

# 13 column names added by feature engineering (never supplied by caller)
_ENGINEERED = {
    "lat_delta", "lon_delta", "alt_delta", "vel_delta",
    "position_jump", "velocity_ratio", "heading_diff",
    "sat_drop", "low_sat", "poor_hdop", "poor_vdop",
    "alt_discrepancy", "total_vibration",
}


def _engineer(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    df = df.copy().reset_index(drop=True)

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
    df["low_sat"]   = (df["Satellite Count"] < cfg["low_sat_threshold"]).astype(int)
    df["poor_hdop"] = (df["GPS HDOP"] > cfg["poor_hdop_threshold"]).astype(int)
    df["poor_vdop"] = (df["GPS VDOP"] > cfg["poor_vdop_threshold"]).astype(int)

    df["alt_discrepancy"] = abs(
        df["Relative Altitude (m)"] - df["Vertical Position (m)"]
    )

    df["total_vibration"] = (
        df["Longitudinal Vibration"]
        + df["Lateral Vibration"]
        + df["Vertical Vibration"]
    )

    return df


class GPSDetector:
    def __init__(
        self,
        model_path:           str   = None,
        scaler_path:          str   = None,
        features_path:        str   = None,
        low_sat_threshold:    int   = 5,
        poor_hdop_threshold:  float = 2.0,
        poor_vdop_threshold:  float = 3.0,
    ):
        model_path    = Path(model_path)    if model_path    else HERE / "gps_model.json"
        scaler_path   = Path(scaler_path)   if scaler_path   else HERE / "gps_scaler.pkl"
        features_path = Path(features_path) if features_path else HERE / "gps_features.json"

        for p in (model_path, scaler_path, features_path):
            if not p.exists():
                raise FileNotFoundError(f"Missing artifact: {p}")

        import xgboost as xgb
        self._model  = xgb.XGBClassifier()
        self._model.load_model(model_path)
        self._scaler = joblib.load(scaler_path)

        with open(features_path) as f:
            self._all_features = json.load(f)     # all 47 in training order

        # Raw columns the caller must supply (everything except the 13 engineered ones)
        self.required_raw_columns = [c for c in self._all_features if c not in _ENGINEERED]

        self._cfg = {
            "low_sat_threshold":  low_sat_threshold,
            "poor_hdop_threshold": poor_hdop_threshold,
            "poor_vdop_threshold": poor_vdop_threshold,
        }
        self._labels = {0: "Normal", 1: "Spoofing"}

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
            return pd.DataFrame(data)
        raise TypeError(f"Unsupported input type: {type(data)}")

    # ── preprocessing ────────────────────────────────────────────────────────

    def _preprocess(self, df: pd.DataFrame) -> np.ndarray:
        missing = [c for c in self.required_raw_columns if c not in df.columns]
        if missing:
            raise ValueError(f"Input is missing required columns:\n  {missing}")

        df_eng = _engineer(df[self.required_raw_columns], self._cfg)
        df_eng = df_eng[self._all_features]          # enforce exact column order
        return self._scaler.transform(df_eng)

    # ── public API ───────────────────────────────────────────────────────────

    def predict(self, data: Union[Dict, List[Dict], pd.Series, pd.DataFrame]) -> List[Dict[str, Any]]:
        df    = self._to_dataframe(data)
        X     = self._preprocess(df)
        preds = self._model.predict(X)
        probas = self._model.predict_proba(X)

        results = []
        for pred, proba in zip(preds, probas):
            lid = int(pred)
            results.append({
                "label":       self._labels[lid],
                "label_int":   lid,
                "confidence":  round(float(proba[lid]), 4),
                "prob_normal": round(float(proba[0]), 4),
                "prob_spoof":  round(float(proba[1]), 4),
            })
        return results

    def predict_one(self, row: Union[Dict, pd.Series]) -> Dict[str, Any]:
        return self.predict(row)[0]
