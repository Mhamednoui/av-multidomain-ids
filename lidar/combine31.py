"""WP8 S3 (v3.1) LiDAR combiner with per-layer budgets: the union of layer alarms, each layer at its own tie-safe threshold of its ECDF rank.

Why: the v3 combiner (lidar.combine.Stack("max")) puts ONE threshold on the max of the layers' ranks, so every layer spends about B / k of the
1 % scan budget and a strong layer loses most of its detection (PointDrop 87 % alone, 27.6 % in the stack). Here layer i alarms when its rank
r_i >= tau_i, tau_i = tie-safe b_i quantile of the OOF clean reference ranks, sum b_i = B (union bound: scan false-alarm rate <= B). The
statistic published = max_i (r_i - tau_i) (alarm: >= 0), the score its ECDF on the reference.
Budgets: alpha_budgets (share alpha to one layer, rest equal) or waterfill (label-free: tie-limited layers keep only what they can spend).
Inputs: dict layer -> raw score arrays. Outputs: stat / score / alarm arrays. Reference: notes/WP8_v31.md S3 pre-registration."""
import numpy as np

from common.calibration import ECDFCalibrator
from common.metrics import budget_threshold

LAYERS = ["L1", "L2a", "L2c", "L2d"]


def ecdf_rank(ref_sorted, x):
    return np.searchsorted(ref_sorted, np.asarray(x, float), side="left") / len(ref_sorted)


class Union:
    """method "union": per-layer budgets; method "max": the v3 rule (one threshold on the max rank, budgets = total budget B)."""

    def __init__(self, budgets=None, method="union"):
        self.budgets, self.method = budgets, method

    def fit(self, ref_raw):
        self.ref = {l: np.sort(np.asarray(ref_raw[l], float)) for l in LAYERS}
        R = np.column_stack([ecdf_rank(self.ref[l], ref_raw[l]) for l in LAYERS])
        if self.method == "max":
            self.tau = np.full(len(LAYERS), np.nan)
            self.thr = budget_threshold(R.max(axis=1), self.budgets)
            s = R.max(axis=1) - self.thr
        else:
            self.tau = np.array([budget_threshold(R[:, j], b) if b > 0 else np.inf for j, b in enumerate(self.budgets)])
            s = (R - self.tau[None, :]).max(axis=1)
        self.cal = ECDFCalibrator().fit(s)
        self.R_ref = R
        return self

    def ranks(self, raw):
        return np.column_stack([ecdf_rank(self.ref[l], raw[l]) for l in LAYERS])

    def stat(self, raw):
        R = self.ranks(raw)
        return R.max(axis=1) - self.thr if self.method == "max" else (R - self.tau[None, :]).max(axis=1)

    def alarm(self, raw):
        return self.stat(raw) >= 0.0

    def score(self, raw):
        return self.cal.transform(self.stat(raw))

    def layer_alarm(self, raw):
        """(n, 4) bool: which layers are over their own threshold (method union only)."""
        return self.ranks(raw) >= self.tau[None, :]


def natural_fa(R_col, b):
    t = budget_threshold(R_col, b)
    return float((R_col >= t).mean())


def waterfill(R, B, tol=0.9, iters=10):
    """Equal shares; a layer whose tie-limited FA is below tol * its share keeps only that FA, the rest goes to the others equally."""
    k = R.shape[1]
    b = np.full(k, B / k)
    for _ in range(iters):
        fa = np.array([natural_fa(R[:, j], b[j]) for j in range(k)])
        under = fa < tol * b
        if not under.any() or under.all():
            break
        spare = (b[under] - fa[under]).sum()
        nb = b.copy()
        nb[under] = fa[under]
        nb[~under] = b[~under] + spare / (~under).sum()
        if np.allclose(nb, b):
            break
        b = nb
    return b


def alpha_budgets(alpha, B=0.01, special=2):
    """Budget vector over LAYERS: share alpha of B to layer index `special` (default L2c), the others (1 - alpha) / 3 each."""
    b = np.full(len(LAYERS), (1 - alpha) / 3)
    b[special] = alpha
    return b * B
