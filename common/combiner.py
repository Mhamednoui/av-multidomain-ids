"""DomainCombiner: merges the calibrated Evidence of all layers of one domain into one
Evidence(layer="combined"). Methods: "noisy_or" (1 - prod(1 - s)), "max", "logistic" (fitted on
validation). method="auto" picks the best on group-aware validation halves.

Inputs: dict layer_name -> list[Evidence], aligned by sample (same order). Outputs: list[Evidence].
Tie-safe threshold via metrics.budget_threshold. Validation halves are split BY GROUP (never rows):
v2 random halves let a meta-classifier memorise drives. The logistic model is fitted on half A and
its threshold set on the normal samples of half B (so the threshold is not on training rows).
Reference: ARCHITECTURE.md sections 3-4.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression

from common.config import BUDGET_DOMAIN, SEED
from common.evidence import Evidence
from common.metrics import budget_threshold
from common.splits import group_halves, mask

METHODS = ("noisy_or", "logistic", "max")


def _combine(method, X, model=None):
    if method == "noisy_or":
        return 1.0 - np.prod(1.0 - X, axis=1)
    if method == "max":
        return X.max(axis=1)
    if method == "logistic":
        return model.predict_proba(_surprise(X))[:, 1]
    raise ValueError(method)


def _surprise(X):
    """-log(1 - s + eps): stretches the top tail that the empirical-CDF calibration squeezes into [0.99, 1]."""
    return -np.log(1.0 - X + 1e-3)


def _fit_logistic(X, y):
    X = _surprise(X)
    return LogisticRegression(C=1.0, class_weight="balanced", max_iter=1000, random_state=SEED).fit(X, y)


class DomainCombiner:
    def __init__(self, method="auto", budget=BUDGET_DOMAIN, seed=SEED):
        self.method, self.budget, self.seed = method, budget, seed
        self.layer_names, self.model, self.threshold = None, None, None
        self.selection = {}      # per-method held-out-half detection when method="auto"

    # ---- fitting ----------------------------------------------------------------------
    def fit(self, val_evidence: dict, y, groups):
        """val_evidence: layer_name -> list[Evidence]; y: 1 = attack; groups: group id per sample."""
        self.layer_names = sorted(val_evidence)
        X = self._matrix(val_evidence)
        y = np.asarray(y).astype(int); groups = np.asarray(groups)
        if self.method == "auto":
            self.selection = self._select(X, y, groups)
            self.method = max(self.selection, key=lambda m: (self.selection[m], -METHODS.index(m)))
        if self.method == "logistic":
            ga, gb = group_halves(groups, self.seed)
            ma, mb = mask(groups, ga), mask(groups, gb)
            self.model = _fit_logistic(X[ma], y[ma])
            norm = (y[mb] == 0)
            self.threshold = budget_threshold(_combine("logistic", X[mb], self.model)[norm], self.budget)
        else:
            s = _combine(self.method, X)
            self.threshold = budget_threshold(s[y == 0], self.budget)
        return self

    def _select(self, X, y, groups):
        """Detection at the budget on the held-out half, averaged over both directions."""
        ga, gb = group_halves(groups, self.seed)
        ma, mb = mask(groups, ga), mask(groups, gb)
        out = {}
        for m in METHODS:
            det = []
            for tr, te in ((ma, mb), (mb, ma)):
                model = _fit_logistic(X[tr], y[tr]) if m == "logistic" else None
                thr = budget_threshold(_combine(m, X[tr], model)[y[tr] == 0], self.budget)
                s = _combine(m, X[te], model)
                det.append(float((s[y[te] == 1] >= thr).mean()))
            out[m] = float(np.mean(det))
        return out

    def _matrix(self, evidence):
        return np.column_stack([[e.score for e in evidence[n]] for n in self.layer_names])

    # ---- scoring ----------------------------------------------------------------------
    def combine(self, evidence: dict) -> list:
        X = self._matrix(evidence)
        s = _combine(self.method, X, self.model)
        first = evidence[self.layer_names[0]]
        out = []
        for i in range(len(s)):
            alarm = bool(s[i] >= self.threshold)
            fired = sorted([(evidence[n][i].score, n) for n in self.layer_names if evidence[n][i].alarm],
                           reverse=True)
            reason = ""
            if alarm:
                who = ", ".join(f"{n} ({sc:.2f})" for sc, n in fired) if fired else "none alone, evidence adds up"
                reason = f"Combined alarm ({self.method}); layers fired: {who}."
            out.append(Evidence(domain=first[i].domain, layer="combined", name=f"{first[i].domain}.combined",
                                t=first[i].t, score=float(s[i]), alarm=alarm, reason=reason,
                                details={"method": self.method,
                                         "layer_scores": {n: evidence[n][i].score for n in self.layer_names}},
                                sample_id=first[i].sample_id))
        return out
