"""Empirical-CDF score calibration: raw statistic -> 0..1 = fraction of validation normal scores
strictly below it. Makes layers comparable inside a combiner.

Above the largest validation normal score the ECDF would saturate at 1.0 (ties inside a combiner);
there a strictly increasing tail 1 - exp(-(x - max)/scale)/n is used: it starts at 1 - 1/n (never
below the ECDF at max), stays < 1, and keeps ranking very large raw scores. scale = max(q99 - q90,
IQR, tiny) of the validation normals (robust spread).

Inputs: raw validation-normal scores (fit), raw scores (transform). Outputs: scores in [0, 1],
monotone non-decreasing in the raw score. Reference: ARCHITECTURE.md section 4.
"""
import numpy as np


class ECDFCalibrator:
    def __init__(self):
        self.sorted_ = None
        self.scale_ = None

    def fit(self, normal_scores):
        s = np.asarray(normal_scores, dtype=float)
        if len(s) == 0:
            raise ValueError("no normal scores")
        self.sorted_ = np.sort(s)
        q = np.quantile(s, [0.25, 0.75, 0.90, 0.99])
        self.scale_ = float(max(q[3] - q[2], q[1] - q[0], 1e-9 * (1.0 + abs(s.max()))))
        return self

    def transform(self, x):
        x = np.asarray(x, dtype=float)
        shape, x = x.shape, np.atleast_1d(x)
        n, top = len(self.sorted_), self.sorted_[-1]
        out = np.searchsorted(self.sorted_, x, side="left") / n
        above = x > top
        if above.any():
            z = np.minimum((x[above] - top) / self.scale_, 30.0)
            out[above] = np.minimum(1.0 - np.exp(-z) / n, np.nextafter(1.0, 0.0))
        return out.reshape(shape)

    def to_dict(self) -> dict:
        return {"sorted": self.sorted_.tolist(), "scale": self.scale_}

    @classmethod
    def from_dict(cls, d):
        c = cls(); c.sorted_ = np.asarray(d["sorted"], dtype=float); c.scale_ = float(d["scale"]); return c
