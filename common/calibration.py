"""Empirical-CDF score calibration: raw statistic -> 0..1 = fraction of validation normal scores
strictly below it. Makes layers comparable inside a combiner.

Inputs: raw validation-normal scores (fit), raw scores (transform). Outputs: scores in [0, 1],
monotone non-decreasing in the raw score. Reference: ARCHITECTURE.md section 4.
"""
import numpy as np


class ECDFCalibrator:
    def __init__(self):
        self.sorted_ = None

    def fit(self, normal_scores):
        s = np.asarray(normal_scores, dtype=float)
        if len(s) == 0:
            raise ValueError("no normal scores")
        self.sorted_ = np.sort(s)
        return self

    def transform(self, x):
        x = np.asarray(x, dtype=float)
        return np.searchsorted(self.sorted_, x, side="left") / len(self.sorted_)

    def to_dict(self) -> dict:
        return {"sorted": self.sorted_.tolist()}

    @classmethod
    def from_dict(cls, d):
        c = cls(); c.sorted_ = np.asarray(d["sorted"], dtype=float); return c
