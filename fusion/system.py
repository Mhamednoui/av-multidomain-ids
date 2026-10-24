"""WP6 S3: system fusion v3 over the domain Evidence (gps, lidar, can, network, v2x) and the cross-domain Evidence.

Inputs: per composite tick (1 s) the combined score of every present domain (its own calibrated 0..1 score, tick maximum), the domain's own
alarm flag, its per-layer scores / alarms and, for the cross-domain layer, the blamed domain.
Steps: (1) per-domain ECDF of the tick score on CLEAN validation ticks (half A of the group-aware validation halves) -> comparable 0..1;
(2) label-free combiner: "max" or the log-form "noisy_or" of common/combiner.py (rank-equivalent to 1 - prod(1 - s), no saturation); the
labelled seen-attack alternative "logistic" (common.combiner._fit_logistic on half-A ticks) is never the zero-shot headline;
(3) system threshold = tie-safe 2% of clean validation composite ticks (half B) (common.metrics.budget_threshold);
(4) every alarm carries an explanation (SystemAlert): which domains fired, their scores, the layers that fired inside them, the cross-domain blame.
A domain absent in a tick (no sample, e.g. a short capture) contributes score 0.
Reference: ARCHITECTURE.md sections 2-4 (system budget 2%, tie-safe thresholds, group-aware halves); notes/ORCHESTRATOR.md 2026-10-22 "ALL"
(label-free combiners for zero-shot stacks); v2 fusion (codes_v2/fusion/train_eval.py: budget threshold + group halves, copied idea, not code).
"""
from dataclasses import dataclass, field

import numpy as np

from common import combiner as cb
from common.calibration import ECDFCalibrator
from common.metrics import budget_threshold

BUDGET_SYSTEM = 0.02
ZERO_SHOT = ("max", "noisy_or", "wsplit")


def wsplit_score(X, w):
    """Weighted budget split (WP6 S5b): s = 1 - min_d (1 - X_d) / w_d; alarm s >= t <=> some entry's tail (1 - X_d) <= (1 - t) w_d, i.e. entry d gets a share
    of the budget proportional to w_d (w = 1 for every entry = the max combiner)."""
    X = np.asarray(X, float)
    return 1.0 - ((1.0 - X) / np.asarray(w, float)[None, :]).min(axis=1)


@dataclass
class SystemAlert:
    t: int                      # tick (s) inside the composite drive
    score: float
    threshold: float
    method: str
    domains: list               # [{"domain", "score", "domain_alarm", "layers_fired"}], strongest first, only the named ones
    cross_blame: str = None     # blamed domain of the cross-domain layer at this tick, "undecided" or None
    reason: str = ""
    details: dict = field(default_factory=dict)


class SystemFusion:
    def __init__(self, domains, method="max", budget=BUDGET_SYSTEM):
        self.domains, self.method, self.budget = list(domains), method, budget
        self.cal, self.threshold, self.model = {}, None, None
        self.weights = None                     # wsplit only (WP6 S5b)

    # ---- fitting ------------------------------------------------------------------------------------
    def fit_calibration(self, clean_ticks: dict):
        """clean_ticks: domain -> 1-d array of the domain's tick scores on clean validation ticks (half A)."""
        for d in self.domains:
            self.cal[d] = ECDFCalibrator().fit(np.asarray(clean_ticks[d], float))
        return self

    def matrix(self, raw: dict):
        """raw: domain -> (n,) tick scores (0 where absent) -> (n, D) calibrated."""
        return np.column_stack([self.cal[d].transform(np.asarray(raw[d], float)) for d in self.domains])

    def fit_logistic(self, X, y):
        self.model = cb._fit_logistic(X, np.asarray(y, int))
        return self

    def scores(self, X):
        if self.method == "wsplit":
            return wsplit_score(X, self.weights)
        return cb._combine(self.method, np.asarray(X, float), self.model)

    def fit_threshold(self, clean_scores):
        self.threshold = float(budget_threshold(np.asarray(clean_scores, float), self.budget))
        return self

    # ---- explanation --------------------------------------------------------------------------------
    def explain(self, i, X_row, parts: dict, layer_names: dict, score):
        """SystemAlert for tick i. X_row: calibrated domain scores (D,); parts: domain -> segment dict (dom_alarm, layer_alarm, blame);
        layer_names: domain -> list of layer names."""
        order = np.argsort(-X_row)
        named, out = set(), []
        for j in order:
            d = self.domains[j]
            p = parts[d]
            own = bool(p["dom_alarm"][i])
            if own or not named:                      # every domain whose own alarm fired, plus the strongest contributor
                named.add(d)
                fired = [layer_names[d][k] for k in np.flatnonzero(p["layer_alarm"][i])]
                out.append({"domain": d, "score": float(X_row[j]), "domain_alarm": own, "layers_fired": fired})
        blame = None
        if "cross" in parts and parts["cross"].get("blame") is not None:
            b = parts["cross"]["blame"][i]
            blame = None if b is None else str(b)
        own = [x for x in out if x["domain_alarm"]]
        if own:
            who = "; ".join(f"{x['domain']} ({x['score']:.3f}" + (f", layers {', '.join(x['layers_fired'][:3])}" if x["layers_fired"] else "") + ")" for x in own)
            reason = f"system alarm ({self.method}, {score:.4f} >= {self.threshold:.4f}): domains fired: {who}"
        else:
            x = out[0]
            reason = (f"system alarm ({self.method}, {score:.4f} >= {self.threshold:.4f}): no domain alarms alone; strongest evidence "
                      f"{x['domain']} ({x['score']:.3f})")
        if blame is not None:
            reason += f"; cross-domain blame: {blame}"
        return SystemAlert(t=int(i), score=float(score), threshold=float(self.threshold), method=self.method, domains=out, cross_blame=blame, reason=reason)

    def to_dict(self):
        return {"domains": self.domains, "method": self.method, "budget": self.budget, "threshold": self.threshold,
                "weights": None if getattr(self, "weights", None) is None else [float(x) for x in self.weights],
                "cal": {d: c.to_dict() for d, c in self.cal.items()},
                "logistic": None if self.model is None else {"coef": self.model.coef_[0].tolist(), "intercept": float(self.model.intercept_[0])}}


def alarm_events(alarm):
    """Number of alarm events = maximal runs of consecutive alarm ticks."""
    a = np.asarray(alarm, bool)
    return int(a[0]) + int((a[1:] & ~a[:-1]).sum()) if len(a) else 0


# ---------------------------------------------------------------------------------------------------- WP6 S5 / M2 additions
class DensityTransform:
    """Traffic-density correction of a tick maximum (WP6 S5). A tick holds the maximum M of k samples (V2X messages heard, network flows of the minute);
    q = G(M) ** (k ** alpha), G = ECDF of the per-sample combined score on clean calibration samples. alpha = 0: identity (the S3 tick score, returned
    unchanged), alpha = 1: independent samples (q is uniform under the null for any k). Ticks without a sample (k = 0) score 0."""

    def __init__(self, alpha=0.0):
        self.alpha, self.G = float(alpha), None

    def fit(self, samples):
        if self.alpha > 0:
            self.G = ECDFCalibrator().fit(np.asarray(samples, float))
        return self

    def transform(self, M, k):
        M = np.asarray(M, float)
        if self.alpha == 0:
            return M
        k = np.asarray(k, float)
        q = self.G.transform(M) ** (np.maximum(k, 1.0) ** self.alpha)
        return np.where(k > 0, q, 0.0)

    def to_dict(self):
        return {"alpha": self.alpha, "G": None if self.G is None else self.G.to_dict()}


class M2System:
    """The frozen M2 system (WP6 S5): per-entry density transform -> per-entry ECDF -> label-free combiner -> system threshold -> temporal correlator ->
    response. entries: domain names (each entry = that domain's combined tick score; LiDAR = its label-free L1 union). parts: domain -> dict(score (n,),
    count (n,), dom_alarm (n,), layer_alarm (n, m), blame (n,) for cross) as in fusion/composite.py segments, or the WP7 runtime's per-tick view."""

    def __init__(self, entries, density, fusion, correlator, meta=None):
        self.entries, self.density, self.fusion, self.correlator = list(entries), density, fusion, correlator
        self.meta = meta or {}

    def matrix(self, parts):
        raw = {d: self.density[d].transform(parts[d]["score"], parts[d].get("count", np.ones(len(parts[d]["score"])))) for d in self.entries}
        return self.fusion.matrix(raw)

    def run(self, parts, layer_names=None, explain=True):
        """-> dict(X, score, alarm, own, blame, events) for one drive."""
        from fusion import correlator as CR
        X = self.matrix(parts)
        s = self.fusion.scores(X)
        alarm = s >= self.fusion.threshold
        own = np.column_stack([np.asarray(parts[d]["dom_alarm"], bool) for d in self.entries])
        cr = parts.get("cross")
        blame = CR.tick_blame(self.entries, X, own, None if cr is None else cr.get("blame"), None if cr is None else cr["dom_alarm"])
        reasons = None
        if explain:
            reasons = np.full(len(s), "", object)
            ln = layer_names or {d: [f"{d}.layer{j}" for j in range(np.asarray(parts[d]["layer_alarm"]).reshape(len(s), -1).shape[1])] for d in self.entries}
            for i in np.flatnonzero(alarm):
                reasons[i] = self.fusion.explain(i, X[i], parts, ln, s[i]).reason
        ev = self.correlator.events(alarm, own, self.entries, blame, reasons)
        return {"X": X, "score": s, "alarm": alarm, "own": own, "blame": blame, "events": ev}

    def to_dict(self):
        return {"entries": self.entries, "density": {d: t.to_dict() for d, t in self.density.items()}, "fusion": self.fusion.to_dict(),
                "correlator": self.correlator.to_dict(), "meta": self.meta}


def load_m2(path=None):
    """The frozen M2 system (WP6 S5): {"K": M2System (gps, lidar, can, network, v2x, cross), "C": M2System (can, network, v2x, cross)}.
    Config summary: results/WP6/m2_system.json. LiDAR entry is INTERIM (label-free L1 union) until M1-LiDAR closes."""
    import pickle
    from pathlib import Path
    p = Path(path) if path else Path(__file__).resolve().parent.parent / "results" / "WP6" / "m2_system.pkl"
    return pickle.load(open(p, "rb"))


# ---------------------------------------------------------------------------------------------------- WP6 S5b / M2 addendum (config version 2)
CONFIG_VERSION = 2


def entry_domain(entry):
    """Entry name -> domain ("lidar.L2c" -> "lidar"); a domain may feed several entries (per-layer LiDAR Evidence)."""
    return entry.split(".")[0]


def entry_part(parts, entry):
    """Per-tick view of one entry from the composite / runtime parts: a whole domain ("lidar") or one layer of it ("lidar.L2c" = column j of the domain's
    layers, own alarm = that layer's own alarm)."""
    if "." not in entry:
        return parts[entry]
    d, lay = entry.split(".")
    p = parts[d]
    j = SystemV2.LIDAR_LAYERS.index(lay)
    la = np.asarray(p["layer_alarm"], bool)
    return {"score": np.asarray(p["layers"])[:, j], "count": p.get("count", np.ones(len(p["score"]))), "dom_alarm": la[:, j], "layer_alarm": la[:, j:j + 1],
            "blame": None, "present": p.get("present")}


class SystemV2(M2System):
    """The re-frozen system after the M2 addendum (WP6 S5b, config version 2): frozen LiDAR domain (lidar/domain.py; entry = the combined LiDAR score or its
    four per-layer Evidence, chosen on validation), label-free budget allocation (noisy_or / max / weighted split, chosen on validation), event blame by decided
    majority and SAFE_STOP only with >= 2 corroborating domains (both inside the correlator). Blame, corroboration and response work on DOMAINS
    (entry_domain), so the LiDAR layers count as one domain."""
    LIDAR_LAYERS = ("L1", "L2a", "L2c", "L2d")

    def __init__(self, entries, density, fusion, correlator, meta=None):
        super().__init__(entries, density, fusion, correlator, meta)
        self.domains = list(dict.fromkeys(entry_domain(e) for e in self.entries))
        self.config_version = CONFIG_VERSION

    def views(self, parts):
        return {e: entry_part(parts, e) for e in self.entries}

    def matrix(self, parts):
        v = self.views(parts)
        raw = {e: self.density[e].transform(v[e]["score"], v[e].get("count", np.ones(len(v[e]["score"])))) for e in self.entries}
        return self.fusion.matrix(raw)

    def own_by_domain(self, parts):
        """(n, len(domains)) own alarm per DOMAIN (any of its entries)."""
        v = self.views(parts)
        own_e = np.column_stack([np.asarray(v[e]["dom_alarm"], bool) for e in self.entries])
        return np.column_stack([own_e[:, [i for i, e in enumerate(self.entries) if entry_domain(e) == d]].any(axis=1) for d in self.domains]), own_e

    def run(self, parts, layer_names=None, explain=True):
        """-> dict(X, score, alarm, own (per domain), blame, events) for one drive. parts: domain -> per-tick dict (score, count, layers, dom_alarm, layer_alarm,
        blame for cross); the LiDAR part must carry the 4 per-layer columns (L1, L2a, L2c, L2d) in layers / layer_alarm when the entries are per layer."""
        from fusion import correlator as CR
        X = self.matrix(parts)
        s = self.fusion.scores(X)
        alarm = s >= self.fusion.threshold
        own, own_e = self.own_by_domain(parts)
        cr = parts.get("cross")
        blame = CR.tick_blame([entry_domain(e) for e in self.entries], X, own_e, None if cr is None else cr.get("blame"), None if cr is None else cr["dom_alarm"])
        reasons = None
        if explain:
            v = self.views(parts)
            reasons = np.full(len(s), "", object)
            ln = layer_names or {e: [f"{e}.layer{j}" for j in range(np.asarray(v[e]["layer_alarm"]).reshape(len(s), -1).shape[1])] for e in self.entries}
            for i in np.flatnonzero(alarm):
                reasons[i] = self.fusion.explain(i, X[i], v, ln, s[i]).reason
        ev = self.correlator.events(alarm, own, self.domains, blame, reasons)
        return {"X": X, "score": s, "alarm": alarm, "own": own, "blame": blame, "events": ev}

    def to_dict(self):
        d = super().to_dict()
        d.update(config_version=self.config_version, domains=self.domains)
        return d


def load_system(version=2, path=None):
    """version 1 = the M2 system (load_m2); version 2 = the system re-frozen after the M2 addendum (WP6 S5b): {"K": SystemV2, "C": SystemV2}.
    Config summary: results/WP6/system_v2.json."""
    import pickle
    from pathlib import Path
    if version == 1:
        return load_m2(path)
    p = Path(path) if path else Path(__file__).resolve().parent.parent / "results" / "WP6" / "system_v2.pkl"
    return pickle.load(open(p, "rb"))
