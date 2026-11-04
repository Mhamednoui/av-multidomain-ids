"""WP8 S2 (v3.1): system fusion with event persistence / hysteresis, per-domain budget allocation, cross-domain de-duplication of the SAFE_STOP corroboration,
and the tick-blame fix of the S6 decision. The v3 system (fusion/system.py SystemV2, fusion/correlator.py, load_system(2)) is NOT changed: this module only
imports from it.

Pipeline per 1 s tick (same order as v3): per-entry density transform (V2X: G(M)^k) -> per-entry ECDF on clean validation ticks -> label-free combiner
(noisy_or, or wsplit = weighted budget split, w = 1 for every entry = max) -> tie-safe system threshold at budget b of clean ticks -> tick blame -> correlator.
Correlator31: alarm ticks closer than `gap` ticks form one episode (hysteresis: an open event survives short quiet stretches); an episode becomes an alert event at
the first tick where >= m of its alarm ticks fall in the last w ticks (persistence). Response = v3 policy (fusion/correlator.respond: DEGRADE the blamed domain
after >= 3 blamed ticks, SAFE_STOP for >= 2 motion-critical blamed domains or a motion-critical degrade lasting >= 30 s) with the SAFE_STOP corroboration counted on
DOMAINS: a domain counts if it raised its own alarm on >= k ticks of the event; with dedup=True the cross-domain layer and the domain it blames count as one (they
are the same evidence); `corroborators` (labelled motion-critical variant) restricts which domains may count. V2X / network alone never exceed DEGRADE (v3 rule).
tick_blame31 (S6 decision; notes/WP8_v31.md "S2 round 1"): (1) on a cross-alarm tick the cross verdict (crossdomain/blame31 A1) or "undecided" (v3 fell back to
the strongest own-alarm entry); (2) on other ticks the strongest non-cross entry with its own alarm; (3) else "undecided" (v3: the strongest entry overall).
Inputs: parts = domain -> per-tick dict (score, count, dom_alarm, blame for cross), as SystemV2. Outputs: dict(X, score, alarm, own, blame, events).
References: fusion/system.py, fusion/correlator.py (v3); notes/WP8_v31.md S2 rules; Basseville & Nikiforov 1993 (persistence / hysteresis in change detection).
"""
import numpy as np

from common import combiner as cb
from common.calibration import ECDFCalibrator
from common.metrics import budget_threshold
from fusion import correlator as CR
from fusion.system import DensityTransform, wsplit_score

MOTION_CRITICAL = CR.MOTION_CRITICAL
MC_OR_CROSS = ("gps", "lidar", "can", "cross")
VERSION = "v3.1-S2"


def tick_blame31(names, X, own, cross_blame=None, cross_alarm=None):
    """names: entry domains (D,), X: (n, D) calibrated scores, own: (n, D) own alarms, cross_blame: (n,) verdicts or None, cross_alarm: (n,) bool or None."""
    names = list(names)
    n = len(X)
    out = np.full(n, "undecided", object)
    nc = np.array([d != "cross" for d in names])
    Xo = np.where(np.asarray(own, bool) & nc[None, :], X, -1.0)
    has_own = Xo.max(axis=1) >= 0
    nm = np.array(names, object)
    out[has_own] = nm[Xo.argmax(axis=1)[has_own]]
    if cross_alarm is not None:
        ca = np.asarray(cross_alarm, bool)
        cbl = np.full(n, "undecided", object) if cross_blame is None else np.array(["undecided" if b is None else str(b) for b in cross_blame], object)
        out[ca] = cbl[ca]
    return out


class Correlator31:
    def __init__(self, m=2, w=5, gap=15, dedup=False, k_corr=1, min_domains=2, blame_rule="majority_decided", corroborators=None):
        self.base = CR.TemporalCorrelator(m=m, w=w, gap=gap, blame_rule=blame_rule, safe_stop_min_domains=min_domains)
        self.m, self.w, self.gap, self.dedup, self.k_corr, self.min_domains = int(m), int(w), int(gap), bool(dedup), int(k_corr), int(min_domains)
        self.blame_rule, self.corroborators = blame_rule, (None if corroborators is None else tuple(corroborators))

    def key(self):
        return f"m{self.m}w{self.w}_g{self.gap}_d{int(self.dedup)}_k{self.k_corr}" + ("" if self.corroborators is None else "_mc")

    def episodes(self, alarm):
        return self.base.episodes(alarm, None)

    def counted_domains(self, own_counts, names, blamed):
        """Domains that corroborate a SAFE_STOP: own alarm on >= k_corr event ticks; dedup: cross + the domain it blames = one."""
        doms = [d for d, c in zip(names, own_counts) if c >= self.k_corr]
        if self.corroborators is not None:
            doms = [d for d in doms if d in self.corroborators]
        if self.dedup and "cross" in doms and blamed in doms:
            doms = [d for d in doms if d != "cross"]
        return doms

    def event_from(self, ticks, s, alarm, own, names, blame, reason=None):
        oc = np.asarray(own, bool)[ticks].sum(axis=0)
        doms = [d for d, c in zip(names, oc) if c > 0]
        u, c = np.unique(np.asarray(blame, object)[ticks].astype(str), return_counts=True)
        bc = {str(a): int(b) for a, b in zip(u, c)}
        blamed = CR.event_blame(bc, len(ticks), self.blame_rule)
        cnt = self.counted_domains(oc, names, blamed)
        resp, degraded = CR.respond(bc, blamed, int(ticks[-1]) - s + 1, len(cnt), self.min_domains)
        ex = f"alert t={s}..{int(ticks[-1])} ({len(ticks)} alarm ticks); domains with own alarms: {', '.join(doms) or 'none'}; blamed: {blamed}"
        if reason is not None:
            ex += f"; first alarm: {reason(int(ticks[0]))}"
        return CR.AlertEvent(start=int(s), first_alarm=int(ticks[0]), end=int(ticks[-1]), n_alarm_ticks=int(len(ticks)), corroborated=False, domains=doms,
                             blame_counts=bc, blamed=blamed, response=resp, degraded=degraded, actions=[CR.ACTIONS.get(d, "") for d in degraded], explanation=ex)

    def events(self, alarm, own, names, blame, reason=None):
        return [self.event_from(t, s, alarm, own, names, blame, reason) for t, s, _ in self.episodes(alarm) if s is not None]

    def to_dict(self):
        return {"m": self.m, "w": self.w, "gap": self.gap, "dedup": self.dedup, "k_corr": self.k_corr, "min_domains": self.min_domains, "blame_rule": self.blame_rule,
                "corroborators": None if self.corroborators is None else list(self.corroborators)}


class SystemV31:
    """entries: domain names (each entry = that domain's combined tick score). method: "noisy_or" | "wsplit" (weights per entry). blame: "A1" (tick_blame31 on the
    cross verdict carried in parts["cross"]["blame"]) | "v3" (fusion/correlator.tick_blame)."""

    def __init__(self, entries, method="noisy_or", weights=None, budget=0.02, correlator=None, density_alpha=None, blame="A1", meta=None):
        self.entries, self.domains = list(entries), list(entries)
        self.method, self.budget, self.blame = method, float(budget), blame
        self.weights = None if weights is None else np.asarray([float(weights[e]) for e in self.entries])
        self.density = {e: DensityTransform((density_alpha or {}).get(e, 0.0)) for e in self.entries}
        self.cal, self.threshold = {}, None
        self.correlator = correlator or Correlator31()
        self.meta = meta or {}
        self.version = VERSION

    # ---- fitting (clean validation data only) -------------------------------------------------------------------
    def fit_entries(self, clean, samples=None):
        """clean: entry -> (scores, counts) of the clean validation ticks; samples: entry -> per-sample clean scores for a density transform."""
        for e in self.entries:
            self.density[e].fit((samples or {}).get(e, np.zeros(1)))
            s, k = clean[e]
            self.cal[e] = ECDFCalibrator().fit(self.density[e].transform(np.asarray(s, float), np.asarray(k, float)))
        return self

    def fit_threshold(self, clean_X):
        self.threshold = float(budget_threshold(self.combine(np.vstack(clean_X)), self.budget))
        return self

    # ---- per tick ----------------------------------------------------------------------------------------------
    def matrix(self, parts):
        n = len(parts[self.entries[0]]["score"])
        cols = []
        for e in self.entries:
            p = parts[e]
            cnt = p.get("count", np.ones(n))
            cols.append(self.cal[e].transform(self.density[e].transform(np.asarray(p["score"], float), np.asarray(cnt, float))))
        return np.column_stack(cols)

    def combine(self, X):
        X = np.asarray(X, float)
        if self.method == "wsplit":
            return wsplit_score(X, self.weights)
        return cb._combine(self.method, X)

    def tick_blame(self, X, own, cross_blame, cross_alarm):
        if self.blame == "v3":
            return CR.tick_blame(self.entries, X, own, cross_blame, cross_alarm)
        return tick_blame31(self.entries, X, own, cross_blame, cross_alarm)

    def reason(self, i, X, own, s):
        own_d = [(self.entries[j], X[i, j]) for j in np.argsort(-X[i]) if own[i, j]]
        if own_d:
            who = "; ".join(f"{d} ({x:.3f})" for d, x in own_d)
            return f"system alarm ({self.method}, {s[i]:.4f} >= {self.threshold:.4f}): domains fired: {who}"
        j = int(np.argmax(X[i]))
        return f"system alarm ({self.method}, {s[i]:.4f} >= {self.threshold:.4f}): no domain alarms alone; strongest evidence {self.entries[j]} ({X[i, j]:.3f})"

    def decide(self, X, own, cross_blame=None, cross_alarm=None, threshold=None, explain=True):
        """Calibrated X (n, D), own alarms (n, D) -> dict(score, alarm, blame, events). threshold overrides the fitted one (cross-fitting)."""
        thr = self.threshold if threshold is None else threshold
        s = self.combine(X)
        alarm = s >= thr
        own = np.asarray(own, bool)
        blame = self.tick_blame(X, own, cross_blame, cross_alarm)
        rs = (lambda i: self.reason(i, X, own, s)) if explain else None
        ev = self.correlator.events(alarm, own, self.entries, blame, rs)
        return {"X": X, "score": s, "alarm": alarm, "own": own, "blame": blame, "events": ev}

    def run(self, parts, explain=True):
        X = self.matrix(parts)
        own = np.column_stack([np.asarray(parts[e]["dom_alarm"], bool) for e in self.entries])
        cr = parts.get("cross")
        return self.decide(X, own, None if cr is None else cr.get("blame"), None if cr is None else cr["dom_alarm"], explain=explain)

    def to_dict(self):
        return {"version": self.version, "entries": self.entries, "method": self.method, "budget": self.budget, "threshold": self.threshold, "blame": self.blame,
                "weights": None if self.weights is None else dict(zip(self.entries, self.weights.tolist())),
                "density": {e: t.to_dict() for e, t in self.density.items()}, "cal": {e: c.to_dict() for e, c in self.cal.items()},
                "correlator": self.correlator.to_dict(), "meta": self.meta}


def load_system31(path=None):
    """The frozen v3.1 system (WP8 S2): {"K": SystemV31, "C": SystemV31}; default results/WP8/S2/frozen_system31/system31.pkl."""
    import pickle
    from pathlib import Path
    p = Path(path) if path else Path(__file__).resolve().parent.parent / "results" / "WP8" / "S2" / "frozen_system31" / "system31.pkl"
    return pickle.load(open(p, "rb"))
