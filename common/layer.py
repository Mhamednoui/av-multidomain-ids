"""Layer: base class of every detection layer (rule, physics, normal-behaviour model, supervised).

A subclass implements `raw_scores(samples) -> np.ndarray` (higher = more attack-like, causal only,
uses self state for streams) and optionally `fit`, `reset`, `reasons`. The base class turns raw
scores into calibrated Evidence: calibrate() fits the empirical-CDF map and the tie-safe budget
threshold on validation normal samples; score() returns list[Evidence].

Samples: a pandas DataFrame (one row per sample; optional columns "t", "sample_id"), or any
sequence with len(); times / ids default to the position index.
Stateful layers: the caller (harness: evaluate.score_groups) calls reset() before each new group.
Reference: ARCHITECTURE.md sections 3-4.
"""
import json
from pathlib import Path

import numpy as np

from common.calibration import ECDFCalibrator
from common.config import BUDGET_DOMAIN
from common.evidence import Evidence
from common.metrics import budget_threshold


class Layer:
    domain = "unknown"
    name = "unknown"
    kind = "rule"                 # "rule" | "physics" | "normal_model" | "supervised"
    needs_attack_data = False
    layer_id = "L1"               # Evidence.layer value

    def __init__(self):
        self.calibrator = None
        self.threshold = None
        self.budget = None

    # --- to override -------------------------------------------------------------------
    def fit(self, train, val=None):
        """Rules may only calibrate on normal data. Default: nothing to learn."""
        return self

    def reset(self):
        """Clear stream state (new drive / capture)."""

    def raw_scores(self, samples) -> np.ndarray:
        raise NotImplementedError

    def reasons(self, samples, raw, alarm) -> list:
        """One sentence per sample (only used where alarm is True)."""
        return [f"{self.name} raw score {r:.4g} above its threshold" for r in raw]

    # --- contract ----------------------------------------------------------------------
    def calibrate(self, val_normal, budget=BUDGET_DOMAIN):
        """Set the 0..1 calibration and self.threshold (tie-safe) from validation NORMAL samples."""
        raw = np.asarray(self.raw_scores(val_normal), dtype=float)
        self.calibrator = ECDFCalibrator().fit(raw)
        self.budget = budget
        self.threshold = budget_threshold(self.calibrator.transform(raw), budget)
        return self

    def score(self, samples) -> list:
        if self.calibrator is None:
            raise RuntimeError("calibrate() first")
        raw = np.asarray(self.raw_scores(samples), dtype=float)
        cal = self.calibrator.transform(raw)
        alarm = cal >= self.threshold
        why = self.reasons(samples, raw, alarm)
        t, ids = _times(samples), _ids(samples)
        return [Evidence(domain=self.domain, layer=self.layer_id, name=self.name, t=float(t[i]),
                         score=float(cal[i]), alarm=bool(alarm[i]), reason=why[i] if alarm[i] else "",
                         details={"raw": float(raw[i])}, sample_id=str(ids[i]))
                for i in range(len(raw))]

    def save(self, folder):
        folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{self.name}.json").write_text(json.dumps(
            {"threshold": self.threshold, "budget": self.budget,
             "calibrator": self.calibrator.to_dict() if self.calibrator else None}))

    def load(self, folder):
        d = json.loads((Path(folder) / f"{self.name}.json").read_text())
        self.threshold, self.budget = d["threshold"], d["budget"]
        self.calibrator = ECDFCalibrator.from_dict(d["calibrator"]) if d["calibrator"] else None
        return self


def _col(samples, name):
    try:
        if name in samples.columns:
            return samples[name].to_numpy()
    except AttributeError:
        pass
    return None


def _times(samples):
    c = _col(samples, "t")
    return c if c is not None else np.arange(len(samples), dtype=float)


def _ids(samples):
    c = _col(samples, "sample_id")
    return c if c is not None else np.arange(len(samples))
