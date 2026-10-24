"""WP3 S9 label-free combiners of the LiDAR layers: max, log-form noisy-or and equal budget split of the ECDF ranks of the layers' raw scores.

Purpose: turn the raw per-scan scores of the headline layers (L1, L2a, L2c, L2d, optional L2b / L4) into ONE stack score and ONE alarm at a
total scan budget (default 1 %), without any attack label (a learned combiner makes detection depend on which families validation contained,
see ORCHESTRATOR 2026-10-22). Ranks: r_i = fraction of the clean reference scores of layer i strictly below the value (reference = the
out-of-fold clean scores of the 16 train+val drives = leave-one-drive-out calibration).
  max        stat = max_i r_i;  alarm = stat >= tie-safe `budget` quantile of the reference stats.
  noisy_or   stat = sum_i -log(1 - min(r_i, 1 - 1e-3)) (rank-equivalent to 1 - prod(1 - r_i), no float saturation); same threshold rule.
  split      each of the k layers has its own tie-safe threshold tau_i at budget / k on the reference; stat = max_i (r_i - tau_i);
             alarm = stat >= 0 (union of k layer alarms, false-alarm rate <= budget by the union bound, no label used).
Score published = ECDF (common.calibration) of the stat on the reference stats (monotone in the stat), alarm = stat >= threshold.
Inputs: DataFrames with one column per layer ("raw_L1", ...). Outputs: stat / score / alarm arrays, the layer that dominates an alarm."""
import numpy as np
import pandas as pd

from common.calibration import ECDFCalibrator
from common.metrics import budget_threshold

METHODS = ("max", "split", "noisy_or")        # simplest first (tie-break order of the validation rule)
CLIP = 1.0 - 1e-3


def ecdf_rank(ref_sorted, x):
    return np.searchsorted(ref_sorted, np.asarray(x, float), side="left") / len(ref_sorted)


class Stack:
    def __init__(self, cols, method="max", budget=0.01):
        if method not in METHODS:
            raise ValueError(method)
        self.cols, self.method, self.budget = list(cols), method, budget
        self.ref, self.tau, self.threshold, self.cal = None, None, None, None

    # ---- fit (clean reference only) -------------------------------------------------------------
    def fit(self, ref):
        self.ref = {c: np.sort(np.asarray(ref[c], float)) for c in self.cols}
        R = self.ranks(ref)
        if self.method == "split":
            self.tau = np.array([budget_threshold(R[:, j], self.budget / len(self.cols)) for j in range(len(self.cols))])
        s = self._stat(R)
        self.threshold = 0.0 if self.method == "split" else float(budget_threshold(s, self.budget))
        self.cal = ECDFCalibrator().fit(s)
        return self

    # ---- scoring ----------------------------------------------------------------------------------
    def ranks(self, df):
        return np.column_stack([ecdf_rank(self.ref[c], df[c].to_numpy(float)) for c in self.cols])

    def _stat(self, R):
        if self.method == "max":
            return R.max(axis=1)
        if self.method == "noisy_or":
            return (-np.log1p(-np.clip(R, 0.0, CLIP))).sum(axis=1)
        return (R - self.tau[None, :]).max(axis=1)

    def stat(self, df):
        return self._stat(self.ranks(df))

    def score(self, df):
        return self.cal.transform(self.stat(df))

    def alarm(self, df):
        return self.stat(df) >= self.threshold

    def dominant(self, df):
        """Index of the layer that carries the stat (largest rank, or largest margin over its tau for split)."""
        R = self.ranks(df)
        return (R - self.tau[None, :] if self.method == "split" else R).argmax(axis=1)


def lodo_fa(ref, cols, method, budget=0.01):
    """Per-drive false-alarm rate when the whole stack (ranks, tau, threshold) is fitted on the other drives' out-of-fold clean scores."""
    out = {}
    dr = ref["drive"].to_numpy()
    for d in sorted(set(dr)):
        s = Stack(cols, method, budget).fit(ref[dr != d])
        out[d] = float(s.alarm(ref[dr == d]).mean())
    return out


def lodo_summary(fa_by_drive, sizes):
    """(scan-weighted mean FA, worst drive FA, worst drive id)."""
    d = sorted(fa_by_drive)
    w = np.array([sizes[x] for x in d], float)
    v = np.array([fa_by_drive[x] for x in d])
    return float((v * w).sum() / w.sum()), float(v.max()), d[int(v.argmax())]


def detection(stack, att):
    """Detection rate per attack name."""
    a = stack.alarm(att)
    return pd.Series(a.astype(float)).groupby(att["attack"].to_numpy()).mean().to_dict()


def drive_bootstrap(alarm, drives, n=2000, seed=11):
    """Cluster bootstrap over drives of the pooled detection rate: (point, lo, hi). alarm: 0/1 vector, drives: drive id per scan."""
    a, dr = np.asarray(alarm, float), np.asarray(drives)
    ids = sorted(set(dr))
    num = np.array([a[dr == d].sum() for d in ids])
    den = np.array([(dr == d).sum() for d in ids], float)
    rng = np.random.default_rng(seed)
    m = np.empty(n)
    for b in range(n):
        k = rng.integers(0, len(ids), len(ids))
        m[b] = num[k].sum() / max(den[k].sum(), 1.0)
    return float(a.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))
