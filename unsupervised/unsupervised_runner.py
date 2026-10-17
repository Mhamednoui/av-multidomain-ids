"""
Unsupervised Zero-Day Detector — Inference runner.

Takes the raw inputs for ALL 4 domains simultaneously, runs each supervised
runner, concatenates the 19-dim probability vector, then applies One-Class SVM.

Interface:
    det = ZeroDayDetector()
    result = det.predict_one(network=net_dict, can=can_dict,
                             gps=gps_dict, lidar=lidar_source)
    result = det.predict(list_of_quad_dicts)
"""
import json
import sys
from pathlib import Path
from typing import Union

import joblib
import numpy as np

HERE = Path(__file__).parent
CODES = HERE.parent
sys.path.insert(0, str(CODES))

from network.network_runner import NetworkDetector
from can.can_runner import CANDetector
from gps.gps_runner import GPSDetector
from lidar.lidar_runner import LiDARDetector

NETWORK_CLASSES = ["BENIGN", "Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"]
CAN_CLASSES = ["BENIGN", "DoS", "GAS", "RPM", "SPEED", "STEERING_WHEEL"]
GPS_CLASSES = ["Normal", "Spoofing"]
LIDAR_CLASSES = ["Normal", "PointDrop", "IntensitySpoof", "GhostCluster"]


def _probs_vec(result: dict, class_list: list) -> np.ndarray:
    if "probabilities" in result:
        p = result["probabilities"]
        return np.array([p[c] for c in class_list], dtype=np.float32)
    # GPS-style output
    return np.array([result.get("prob_normal", 0.0),
                     result.get("prob_spoof", 0.0)], dtype=np.float32)


class ZeroDayDetector:
    """
    Unsupervised zero-day threat detector.

    Wraps all 4 supervised runners + One-Class SVM.
    Detects anomalous joint probability patterns that indicate unknown attacks.
    """

    def __init__(
        self,
        model_path: str = None,
        scaler_path: str = None,
        meta_path: str = None,
        network_det: NetworkDetector = None,
        can_det: CANDetector = None,
        gps_det: GPSDetector = None,
        lidar_det: LiDARDetector = None,
    ):
        model_path = Path(model_path or HERE / "unsupervised_model.pkl")
        scaler_path = Path(scaler_path or HERE / "unsupervised_scaler.pkl")
        meta_path = Path(meta_path or HERE / "unsupervised_meta.json")

        self.ocsvm = joblib.load(str(model_path))
        self.scaler = joblib.load(str(scaler_path))
        self.meta = json.loads(meta_path.read_text())

        # Reuse passed runners or instantiate new ones
        self.net_det = network_det or NetworkDetector()
        self.can_det = can_det or CANDetector()
        self.gps_det = gps_det or GPSDetector()
        self.lid_det = lidar_det or LiDARDetector()

    def _build_vector(
        self,
        network_input: dict,
        can_input: dict,
        gps_input: dict,
        lidar_input: Union[str, Path, np.ndarray],
    ) -> tuple[np.ndarray, dict]:
        """Returns (19-dim prob vector, per-domain results dict)."""
        net_r = self.net_det.predict([network_input])[0]
        can_r = self.can_det.predict([can_input])[0]
        gps_r = self.gps_det.predict([gps_input])[0]
        lid_r = self.lid_det.predict_one(lidar_input)

        vec = np.concatenate([
            _probs_vec(net_r, NETWORK_CLASSES),
            _probs_vec(can_r, CAN_CLASSES),
            _probs_vec(gps_r, GPS_CLASSES),
            _probs_vec(lid_r, LIDAR_CLASSES),
        ])
        domain_results = {
            "network": net_r,
            "can": can_r,
            "gps": gps_r,
            "lidar": lid_r,
        }
        return vec, domain_results

    def predict_one(
        self,
        network: dict,
        can: dict,
        gps: dict,
        lidar: Union[str, Path, np.ndarray],
    ) -> dict:
        """
        Predict a single time-step across all 4 domains.

        Parameters
        ----------
        network : dict — raw network flow record (43 features)
        can     : dict — raw CAN packet (ID + DATA_0..7)
        gps     : dict — raw GPS/IMU frame (34 features)
        lidar   : str | Path | np.ndarray — .bin path or N×4 array

        Returns
        -------
        dict with keys:
            is_zero_day     : bool   — True = unknown/zero-day threat detected
            anomaly_score   : float  — decision function value (>0 = normal)
            supervised_flags: dict   — per-domain is_attack flags + label
            domain_results  : dict   — full per-domain runner outputs
        """
        vec, domain_results = self._build_vector(network, can, gps, lidar)
        X = self.scaler.transform(vec.reshape(1, -1))
        pred = int(self.ocsvm.predict(X)[0])          # +1 = normal, -1 = anomaly
        score = float(self.ocsvm.decision_function(X)[0])

        supervised_flags = {}
        for name, res in domain_results.items():
            if "is_attack" in res:
                is_atk = res["is_attack"]
            elif "label_int" in res:       # GPS runner
                is_atk = res["label_int"] != 0
            else:
                is_atk = res.get("label_id", 0) != 0
            label = res.get("label_name") or res.get("label", "unknown")
            supervised_flags[name] = {
                "is_attack": is_atk,
                "label": label,
                "confidence": res["confidence"],
            }

        return {
            "is_zero_day": pred == -1,
            "anomaly_score": score,
            "supervised_flags": supervised_flags,
            "domain_results": domain_results,
        }

    def predict(self, samples: list[dict]) -> list[dict]:
        """
        Predict a list of samples.

        Each sample is a dict with keys: 'network', 'can', 'gps', 'lidar'.
        """
        return [
            self.predict_one(
                s["network"], s["can"], s["gps"], s["lidar"]
            )
            for s in samples
        ]
