"""
LiDAR IDS — Inference runner.

Interface identical to other domain runners:
    det = LiDARDetector()
    result = det.predict_one("/path/to/scan.bin")
    result = det.predict_one(numpy_Nx4_array)
    results = det.predict([path1, path2, ...])
"""
import json
from pathlib import Path
from typing import Union

import joblib
import numpy as np
import xgboost as xgb

HERE = Path(__file__).parent


def _extract_features(pts: np.ndarray) -> np.ndarray:
    """Same extraction as lidar_train.py — must stay in sync."""
    N_RINGS = 64
    N_DIST_RINGS = 8

    if len(pts) == 0:
        return np.zeros(N_RINGS + N_DIST_RINGS + 14, dtype=np.float32)

    x, y, z, intensity = pts[:, 0], pts[:, 1], pts[:, 2], pts[:, 3]
    r = np.sqrt(x**2 + y**2)
    elev = np.degrees(np.arctan2(z, r))

    n_pts = len(pts)
    z_mean, z_std = z.mean(), z.std()
    i_mean, i_std = intensity.mean(), intensity.std()
    r_mean, r_max = r.mean(), r.max()

    ground_mask = z < -0.4
    n_ground = ground_mask.sum()
    ground_z_mean = z[ground_mask].mean() if n_ground > 0 else 0.0
    ground_residual = float(z_mean - ground_z_mean)

    elev_hist, _ = np.histogram(elev, bins=N_RINGS, range=(-25.0, 15.0), density=True)
    dist_hist, _ = np.histogram(r, bins=N_DIST_RINGS, range=(0.0, 80.0), density=True)

    fg = pts[~ground_mask]
    if len(fg) > 10:
        bb_vol = float(
            (fg[:, 0].max() - fg[:, 0].min()) *
            (fg[:, 1].max() - fg[:, 1].min()) *
            (fg[:, 2].max() - fg[:, 2].min())
        )
    else:
        bb_vol = 0.0

    i_p10, i_p90 = np.percentile(intensity, 10), np.percentile(intensity, 90)
    i_iqr = float(i_p90 - i_p10)
    i_high_frac = float((intensity > 0.85).mean())

    global_feats = np.array([
        n_pts, z_mean, z_std, i_mean, i_std,
        r_mean, r_max, n_ground / (n_pts + 1e-6),
        ground_residual, bb_vol,
        i_iqr, i_high_frac,
        elev.min(), elev.max(),
    ], dtype=np.float32)

    return np.concatenate([global_feats, elev_hist.astype(np.float32),
                           dist_hist.astype(np.float32)])


class LiDARDetector:
    """
    Detects LiDAR anomalies / attacks.

    Parameters
    ----------
    model_path, scaler_path, features_path, label_map_path :
        Paths to artifacts. Default: same directory as this file.
    """

    def __init__(
        self,
        model_path: str = None,
        scaler_path: str = None,
        features_path: str = None,
        label_map_path: str = None,
    ):
        model_path = Path(model_path or HERE / "lidar_model.json")
        scaler_path = Path(scaler_path or HERE / "lidar_scaler.pkl")
        features_path = Path(features_path or HERE / "lidar_features.json")
        label_map_path = Path(label_map_path or HERE / "lidar_label_map.json")

        self.model = xgb.XGBClassifier()
        self.model.load_model(str(model_path))
        self.scaler = joblib.load(str(scaler_path))
        self.features = json.loads(features_path.read_text())
        raw_map = json.loads(label_map_path.read_text())
        self.label_map = {int(k): v for k, v in raw_map.items()}
        self.classes = [self.label_map[i] for i in range(len(self.label_map))]

    def _load_pts(self, source: Union[str, Path, np.ndarray]) -> np.ndarray:
        if isinstance(source, np.ndarray):
            return source.astype(np.float32)
        return np.fromfile(str(source), dtype=np.float32).reshape(-1, 4)

    def _predict_features(self, feats: np.ndarray) -> dict:
        X = self.scaler.transform(feats.reshape(1, -1))
        pred_id = int(self.model.predict(X)[0])
        probs = self.model.predict_proba(X)[0]
        return {
            "label_id": pred_id,
            "label_name": self.label_map[pred_id],
            "confidence": float(probs[pred_id]),
            "probabilities": {cls: float(p) for cls, p in zip(self.classes, probs)},
            "is_attack": pred_id != 0,
        }

    def predict_one(self, source: Union[str, Path, np.ndarray]) -> dict:
        """Predict a single scan. source = .bin path or N×4 numpy array."""
        pts = self._load_pts(source)
        feats = _extract_features(pts)
        return self._predict_features(feats)

    def predict(self, sources: list) -> list[dict]:
        """Predict a list of .bin paths or N×4 arrays."""
        results = []
        for src in sources:
            results.append(self.predict_one(src))
        return results

    def predict_batch_features(self, X: np.ndarray) -> list[dict]:
        """Predict from a pre-computed N×D feature matrix (already extracted)."""
        X_sc = self.scaler.transform(X)
        pred_ids = self.model.predict(X_sc)
        probs_all = self.model.predict_proba(X_sc)
        results = []
        for pid, probs in zip(pred_ids, probs_all):
            pid = int(pid)
            results.append({
                "label_id": pid,
                "label_name": self.label_map[pid],
                "confidence": float(probs[pid]),
                "probabilities": {cls: float(p) for cls, p in zip(self.classes, probs)},
                "is_attack": pid != 0,
            })
        return results
