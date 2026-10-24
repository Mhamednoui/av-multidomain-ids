"""WP6 S4: evidence-novelty layer. A novelty detector on the vector of per-layer calibrated scores of ONE domain.

Idea: the layers of a domain are individually calibrated (ECDF of clean validation scores). Clean ticks have a typical JOINT pattern (which layers
co-fire, how strongly). An attack of an unseen type may raise several layers at once, or one layer in a way clean data never does, without any single
layer crossing its own threshold. The detector learns the clean joint pattern from CLEAN validation evidence only (no attack label, no training data
of the layers themselves, whose scores are in-sample there) and scores deviations upward.
Inputs: X (n, m) calibrated layer scores in [0, 1] of the clean validation ticks (fit); X of any ticks (score). Ticks without evidence (all layers exactly
0, e.g. no sample in that second) get novelty 0 and are not used for fitting.
Features: u = -log(1 - s) (exponential for a clean ECDF-calibrated layer, 0 at the bottom), f = log1p(u). Bounded below by 0, so only upward deviations count.
Kinds: "mcd" robust Mahalanobis distance (sklearn MinCovDet, support 0.75, covariance + ridge 0.1 x mean variance, constant columns dropped; median / MAD
diagonal fallback if the MCD fails) and "iforest" (IsolationForest, 200 trees, max_samples 256).
Outputs: raw novelty score (>= 0, larger = more novel); `fit_oof` gives out-of-fold scores of the fit ticks (contiguous-block folds) for ECDF calibration
without in-sample optimism; `explain` lists the layers that deviate most.
References: Rousseeuw 1984 (MCD); Liu, Ting, Zhou 2008 (isolation forest); gps/learned.py (the WP1 S7 L3 uses the same two detectors on motion features).
"""
import numpy as np
from sklearn.covariance import MinCovDet
from sklearn.ensemble import IsolationForest

from common.config import SEED

KINDS = ("mcd", "iforest")
FIT_CAP = 20000


def features(X):
    s = np.clip(np.asarray(X, float), 0.0, 1.0 - 1e-9)
    return np.log1p(-np.log1p(-s))


def has_evidence(X):
    return (np.asarray(X, float) > 0).any(axis=1)


class EvidenceNovelty:
    def __init__(self, kind="mcd", seed=SEED, layer_names=None):
        if kind not in KINDS:
            raise ValueError(kind)
        self.kind, self.seed, self.layer_names = kind, seed, layer_names
        self.keep = self.loc = self.prec = self.model = None

    def fit(self, X):
        X = np.asarray(X, float)
        F = features(X[has_evidence(X)])
        if len(F) > FIT_CAP:
            F = F[np.random.RandomState(self.seed).choice(len(F), FIT_CAP, replace=False)]
        self.keep = F.std(axis=0) > 1e-9
        if not self.keep.any() or len(F) < 5:
            self.keep = np.zeros(X.shape[1], bool)
            return self
        F = F[:, self.keep]
        if self.kind == "iforest":
            self.model = IsolationForest(n_estimators=200, max_samples=min(256, len(F)), random_state=self.seed).fit(F)
            return self
        try:
            mcd = MinCovDet(support_fraction=0.75, random_state=self.seed).fit(F)
            loc, cov = mcd.location_, mcd.covariance_
        except Exception:
            loc = np.median(F, axis=0)
            cov = np.diag((1.4826 * np.median(np.abs(F - loc), axis=0)) ** 2 + 1e-6)
        cov = np.atleast_2d(cov)
        cov = cov + 0.1 * float(np.mean(np.diag(cov)) + 1e-9) * np.eye(len(cov))
        self.loc, self.prec = loc, np.linalg.inv(cov)
        return self

    def score(self, X):
        X = np.asarray(X, float)
        out = np.zeros(len(X), np.float32)
        ev = has_evidence(X)
        if not self.keep.any() or not ev.any():
            return out
        F = features(X[ev])[:, self.keep]
        if self.kind == "iforest":
            out[ev] = -self.model.score_samples(F)
        else:
            D = F - self.loc
            out[ev] = np.einsum("ij,jk,ik->i", D, self.prec, D)
        return out

    def explain(self, x, top=3):
        """Layers that deviate most for one tick (upward, in units of the clean spread). Names = layer_names."""
        f = features(np.asarray(x, float).reshape(1, -1))[0]
        kept = np.flatnonzero(self.keep)
        if self.kind == "mcd" and len(kept):
            d = (f[kept] - self.loc)
            sd = np.sqrt(np.maximum(np.diag(np.linalg.inv(self.prec)), 1e-12))
            z = d / sd
        else:
            z = f[kept] if len(kept) else np.zeros(0)
        order = np.argsort(-z)[:top]
        names = self.layer_names or [str(i) for i in range(len(f))]
        return [(names[kept[i]], float(z[i])) for i in order if z[i] > 0]


def fit_oof(kind, X, blocks, k=5, seed=SEED):
    """Out-of-fold raw scores of the fit rows X: fold = block id % k (contiguous blocks), each fold scored by a detector fitted on the other folds.
    Rows of a fold that cannot be scored (too little data) keep score 0."""
    X = np.asarray(X, float)
    fold = np.asarray(blocks, np.int64) % k
    out = np.zeros(len(X), np.float32)
    for j in range(k):
        te = fold == j
        if not te.any() or te.all():
            continue
        out[te] = EvidenceNovelty(kind, seed).fit(X[~te]).score(X[te])
    return out
