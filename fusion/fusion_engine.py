"""
Fusion Engine — combines outputs from all 4 supervised domain detectors
and the unsupervised zero-day detector into a single unified threat alert.

Three fusion strategies are available and can be selected at runtime:

  1. rule_based   — flag if any domain is_attack=True above a confidence
                    threshold OR if zero-day score is below its threshold
  2. weighted     — weighted average of per-domain attack probability,
                    weights derived from validation accuracy
  3. meta         — a trained XGBoost meta-classifier on the full 20-dim
                    feature vector (19 probs + 1 zero-day score)

Usage:
    engine = FusionEngine(strategy="weighted")   # or "rule_based" / "meta"
    alert  = engine.predict(
        network_result  = nd.predict([net_row])[0],
        can_result      = cd.predict([can_row])[0],
        gps_result      = gd.predict([gps_row])[0],
        lidar_result    = ld.predict_one(bin_path),
        zeroday_result  = zd.predict_one(...),   # optional
    )
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import joblib
import numpy as np

HERE = Path(__file__).parent

# ── Domain weights (validation accuracy) ─────────────────────────────────────
DOMAIN_WEIGHTS = {
    "network": 0.9104,
    "can":     1.0000,
    "gps":     0.9998,
    "lidar":   0.9963,
}
WEIGHT_SUM = sum(DOMAIN_WEIGHTS.values())

# ── Benign class name per domain ──────────────────────────────────────────────
BENIGN_CLASS = {
    "network": "BENIGN",
    "can":     "BENIGN",
    "gps":     "Normal",
    "lidar":   "Normal",
}

# ── Threat levels ─────────────────────────────────────────────────────────────
THREAT_LEVELS = {
    0: "NORMAL",
    1: "LOW",
    2: "MEDIUM",
    3: "HIGH",
    4: "CRITICAL",
}


@dataclass
class FusionAlert:
    """Unified threat alert produced by the fusion engine."""
    threat_level:    int           # 0–4
    threat_label:    str           # NORMAL / LOW / MEDIUM / HIGH / CRITICAL
    attack_score:    float         # 0.0–1.0  (higher = more likely attack)
    is_attack:       bool          # True if threat_level >= 2
    strategy:        str           # which fusion strategy was used
    triggered_by:    list          # domains that flagged an attack
    domain_results:  dict          # raw per-domain runner outputs
    zero_day_result: Optional[dict] = None
    meta: dict = field(default_factory=dict)  # extra strategy-specific info


def _attack_prob(result: dict, domain: str) -> float:
    """Return probability of the ATTACK hypothesis for a domain result."""
    benign = BENIGN_CLASS[domain]
    if "probabilities" in result:
        p = result["probabilities"]
        return 1.0 - p.get(benign, 0.0)
    # GPS-style
    return float(result.get("prob_spoof", 0.0))


def _is_attack_flag(result: dict, domain: str) -> bool:
    if "is_attack" in result:
        return bool(result["is_attack"])
    if "label_int" in result:        # GPS
        return result["label_int"] != 0
    return result.get("label_id", 0) != 0


def _label(result: dict) -> str:
    return result.get("label_name") or result.get("label", "unknown")


def _confidence(result: dict) -> float:
    return float(result.get("confidence", 0.0))


# ── Threat level mapping from attack score ────────────────────────────────────

def _score_to_threat(score: float, zero_day: bool = False) -> int:
    """Map a continuous attack score [0,1] to a discrete threat level 0–4.

    Thresholds are tuned for the weighted strategy where a single high-confidence
    domain (weight ~1.0, prob_attack ~0.9) produces score ~0.23 — enough for MEDIUM.
    Two domains produce ~0.46 → HIGH. All four → CRITICAL.
    """
    if zero_day and score >= 0.2:
        base = _score_to_threat(score, False)
        return min(base + 1, 4)
    if score < 0.08:  return 0   # NORMAL  — no domain flagging
    if score < 0.18:  return 1   # LOW     — one domain, low confidence
    if score < 0.32:  return 2   # MEDIUM  — one domain, high confidence
    if score < 0.50:  return 3   # HIGH    — two domains flagging
    return 4                      # CRITICAL — three+ domains or all flagging


# ── Strategy 1: Rule-Based ────────────────────────────────────────────────────

def _fuse_rule_based(
    results: dict,
    zero_day: Optional[dict],
    conf_threshold: float = 0.5,
    zd_score_threshold: float = -0.5,
) -> FusionAlert:
    """
    Flag if:
      - Any domain predicts attack with confidence >= conf_threshold
      - OR zero-day anomaly_score < zd_score_threshold
    Threat level scales with number of domains triggered.
    """
    triggered = []
    for domain, result in results.items():
        if _is_attack_flag(result, domain) and _confidence(result) >= conf_threshold:
            triggered.append(domain)

    zd_triggered = False
    if zero_day and zero_day.get("is_zero_day") and \
            zero_day.get("anomaly_score", 0) < zd_score_threshold:
        zd_triggered = True
        triggered.append("zero_day")

    n = len([t for t in triggered if t != "zero_day"])
    # score: fraction of domains triggered, boosted by zero-day
    score = n / len(results)
    if zd_triggered:
        score = min(score + 0.25, 1.0)

    threat = _score_to_threat(score, zd_triggered)

    return FusionAlert(
        threat_level=threat,
        threat_label=THREAT_LEVELS[threat],
        attack_score=round(score, 4),
        is_attack=threat >= 2,
        strategy="rule_based",
        triggered_by=triggered,
        domain_results=results,
        zero_day_result=zero_day,
        meta={"conf_threshold": conf_threshold,
              "zd_score_threshold": zd_score_threshold},
    )


# ── Strategy 2: Weighted Voting ───────────────────────────────────────────────

def _fuse_weighted(
    results: dict,
    zero_day: Optional[dict],
    zd_weight: float = 0.15,
) -> FusionAlert:
    """
    Weighted average of per-domain attack probabilities.
    Weights = validation accuracy (CAN > GPS > LiDAR > Network).
    Zero-day anomaly score is incorporated as an additional signal.
    """
    weighted_score = 0.0
    total_weight = 0.0
    triggered = []

    for domain, result in results.items():
        w = DOMAIN_WEIGHTS[domain]
        p_attack = _attack_prob(result, domain)
        weighted_score += w * p_attack
        total_weight += w
        if p_attack > 0.5:
            triggered.append(domain)

    score = weighted_score / total_weight   # [0, 1]

    # Blend in zero-day signal
    if zero_day is not None:
        # OC-SVM score: negative = anomaly. Normalise to [0,1].
        raw = zero_day.get("anomaly_score", 0.0)
        zd_prob = float(np.clip(1.0 / (1.0 + np.exp(raw * 2)), 0, 1))
        score = (1 - zd_weight) * score + zd_weight * zd_prob
        if zero_day.get("is_zero_day"):
            triggered.append("zero_day")

    score = float(np.clip(score, 0.0, 1.0))
    threat = _score_to_threat(score, zero_day.get("is_zero_day", False) if zero_day else False)

    return FusionAlert(
        threat_level=threat,
        threat_label=THREAT_LEVELS[threat],
        attack_score=round(score, 4),
        is_attack=threat >= 2,
        strategy="weighted",
        triggered_by=triggered,
        domain_results=results,
        zero_day_result=zero_day,
        meta={"weights": DOMAIN_WEIGHTS, "zd_weight": zd_weight},
    )


# ── Strategy 3: Meta-Classifier ───────────────────────────────────────────────

def _build_meta_feature_vector(results: dict, zero_day: Optional[dict]) -> np.ndarray:
    """Build the 20-dim feature vector for the meta-classifier."""
    NETWORK_CLASSES = ["BENIGN","Bot","BruteForce","DoS","Infiltration","PortScan","WebAttack"]
    CAN_CLASSES     = ["BENIGN","DoS","GAS","RPM","SPEED","STEERING_WHEEL"]
    GPS_CLASSES     = ["Normal","Spoofing"]
    LIDAR_CLASSES   = ["Normal","PointDrop","IntensitySpoof","GhostCluster"]

    def _probs(res, classes):
        if "probabilities" in res:
            p = res["probabilities"]
            return [p.get(c, 0.0) for c in classes]
        return [res.get("prob_normal", 0.0), res.get("prob_spoof", 0.0)]

    net_v  = _probs(results["network"], NETWORK_CLASSES)
    can_v  = _probs(results["can"],     CAN_CLASSES)
    gps_v  = _probs(results["gps"],     GPS_CLASSES)
    lid_v  = _probs(results["lidar"],   LIDAR_CLASSES)
    zd_s   = [float(zero_day.get("anomaly_score", 0.0))] if zero_day else [0.0]

    return np.array(net_v + can_v + gps_v + lid_v + zd_s, dtype=np.float32)


def _fuse_meta(
    results: dict,
    zero_day: Optional[dict],
    model_path: Path,
    scaler_path: Path,
) -> FusionAlert:
    """Meta-classifier: XGBoost trained on 20-dim feature vector."""
    import xgboost as xgb

    model  = xgb.XGBClassifier()
    model.load_model(str(model_path))
    scaler = joblib.load(str(scaler_path))

    vec = _build_meta_feature_vector(results, zero_day)
    X   = scaler.transform(vec.reshape(1, -1))

    pred_id = int(model.predict(X)[0])
    probs   = model.predict_proba(X)[0]

    # meta model outputs: 0=NORMAL, 1=ATTACK
    score   = float(probs[1]) if len(probs) > 1 else float(pred_id)
    threat  = _score_to_threat(score, zero_day.get("is_zero_day", False) if zero_day else False)

    triggered = [d for d, r in results.items() if _is_attack_flag(r, d)]
    if zero_day and zero_day.get("is_zero_day"):
        triggered.append("zero_day")

    return FusionAlert(
        threat_level=threat,
        threat_label=THREAT_LEVELS[threat],
        attack_score=round(score, 4),
        is_attack=threat >= 2,
        strategy="meta",
        triggered_by=triggered,
        domain_results=results,
        zero_day_result=zero_day,
        meta={"meta_pred_id": pred_id, "meta_probs": probs.tolist()},
    )


# ── Public API ────────────────────────────────────────────────────────────────

class FusionEngine:
    """
    Unified threat decision engine.

    Parameters
    ----------
    strategy : "rule_based" | "weighted" | "meta"
        Fusion strategy. Default: "weighted".
    conf_threshold : float
        For rule_based only — minimum domain confidence to trigger a flag.
    zd_weight : float
        For weighted only — weight of the zero-day signal (0–1).
    meta_model_path, meta_scaler_path : Path
        For meta only — paths to trained XGBoost meta-classifier artifacts.
    """

    def __init__(
        self,
        strategy: Literal["rule_based", "weighted", "meta"] = "weighted",
        conf_threshold: float = 0.5,
        zd_weight: float = 0.15,
        meta_model_path: str = None,
        meta_scaler_path: str = None,
    ):
        self.strategy       = strategy
        self.conf_threshold = conf_threshold
        self.zd_weight      = zd_weight
        self.meta_model_path  = Path(meta_model_path or HERE / "fusion_meta_model.json")
        self.meta_scaler_path = Path(meta_scaler_path or HERE / "fusion_meta_scaler.pkl")

    def predict(
        self,
        network_result: dict,
        can_result:     dict,
        gps_result:     dict,
        lidar_result:   dict,
        zeroday_result: Optional[dict] = None,
    ) -> FusionAlert:
        """
        Produce a unified threat alert from all domain results.

        Parameters
        ----------
        network_result  : output of NetworkDetector.predict()[0]
        can_result      : output of CANDetector.predict()[0]
        gps_result      : output of GPSDetector.predict()[0]
        lidar_result    : output of LiDARDetector.predict_one()
        zeroday_result  : output of ZeroDayDetector.predict_one()  (optional)

        Returns
        -------
        FusionAlert dataclass
        """
        results = {
            "network": network_result,
            "can":     can_result,
            "gps":     gps_result,
            "lidar":   lidar_result,
        }

        if self.strategy == "rule_based":
            return _fuse_rule_based(results, zeroday_result, self.conf_threshold)
        elif self.strategy == "weighted":
            return _fuse_weighted(results, zeroday_result, self.zd_weight)
        elif self.strategy == "meta":
            return _fuse_meta(results, zeroday_result,
                              self.meta_model_path, self.meta_scaler_path)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy!r}")

    def predict_batch(self, samples: list[dict]) -> list[FusionAlert]:
        """
        Predict a list of samples.
        Each sample is a dict with keys:
            network_result, can_result, gps_result, lidar_result,
            zeroday_result (optional).
        """
        return [self.predict(**s) for s in samples]

    def alert_to_dict(self, alert: FusionAlert) -> dict:
        """Serialize a FusionAlert to a plain dict (JSON-safe)."""
        return {
            "threat_level":  alert.threat_level,
            "threat_label":  alert.threat_label,
            "attack_score":  alert.attack_score,
            "is_attack":     alert.is_attack,
            "strategy":      alert.strategy,
            "triggered_by":  alert.triggered_by,
            "meta":          alert.meta,
            "domains": {
                domain: {
                    "label":      _label(r),
                    "confidence": _confidence(r),
                    "is_attack":  _is_attack_flag(r, domain),
                    "attack_prob": round(_attack_prob(r, domain), 4),
                }
                for domain, r in alert.domain_results.items()
            },
            "zero_day": {
                "is_zero_day":   alert.zero_day_result.get("is_zero_day"),
                "anomaly_score": alert.zero_day_result.get("anomaly_score"),
            } if alert.zero_day_result else None,
        }
