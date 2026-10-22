"""WP6 S2: cross-domain consistency layer, "which domain lies".

Purpose: several independent witnesses observe the same ego motion (GPS claim, LiDAR odometry, CAN wheel speed, IMU gyro /
compass). Every pair of witnesses (an EDGE, one quantity: speed, lateral displacement, yaw rate) gives a residual normalised
by a train-fitted SigmaModel (crossdomain.witness). A two-sided CUSUM per edge accumulates small persistent disagreements
(slow attacks); edges are calibrated on clean validation data (ECDF per edge, one tie-safe threshold on the max). The
blame logic finds the witness that disagrees with all its partners while those partners agree with each other: the unique
minimum vertex cover of the alarming edges, if it is a single node with >= 2 alarming partners joined by an observed
non-alarming edge. Otherwise the output is "undecided" (2 witnesses only, two liars, or no confirmed agreement).
Inputs: per run, a matrix Z (T x E) of normalised residuals (NaN = edge not observed at that second), the edge list.
Outputs: CUSUM statistics, calibrated edge scores, alarms, blamed node per second, Evidence(domain "cross").
Limits: two coordinated liars that agree with each other make the one honest witness look like the liar (shown in S2).
References: Page 1954 (CUSUM); Basseville & Nikiforov 1993 (detection of abrupt changes); Bar-Shalom et al. 2001
(normalised innovation consistency); fault isolation by structured residuals (Gertler 1998); vertex cover = smallest
set of faulty nodes explaining all inconsistent pairs (Preparata, Metze & Chien 1967, system-level diagnosis).
"""
from dataclasses import dataclass
from itertools import combinations

import numpy as np

from common.calibration import ECDFCalibrator
from common.evidence import Evidence
from common.metrics import budget_threshold

UNDECIDED = "undecided"


@dataclass(frozen=True)
class Edge:
    a: str
    b: str
    quantity: str
    model: str = ""          # key of the SigmaModel

    @property
    def name(self):
        return f"{self.a}-{self.b} {self.quantity}"


def cusum(Z, k):
    """Two-sided CUSUM per column of Z (T x E): S+ = max(0, S+ + z - k), S- = max(0, S- - z - k); stat = max(S+, S-).
    k = "inst" -> stat = |z|. NaN z -> state held (stat NaN until the first observation of the edge)."""
    Z = np.asarray(Z, float)
    if k == "inst":
        return np.abs(Z)
    T, E = Z.shape
    out = np.full((T, E), np.nan)
    sp, sm = np.zeros(E), np.zeros(E)
    seen = np.zeros(E, bool)
    for i in range(T):
        z = Z[i]
        ok = np.isfinite(z)
        zz = np.where(ok, z, 0.0)
        sp = np.where(ok, np.maximum(0.0, sp + zz - k), sp)
        sm = np.where(ok, np.maximum(0.0, sm - zz - k), sm)
        seen |= ok
        out[i] = np.where(seen, np.maximum(sp, sm), np.nan)
    return out


class Calibration:
    """Per-edge ECDF of the clean-validation statistic; tau = tie-safe budget threshold of the max over edges."""

    def __init__(self, budget=0.01):
        self.budget, self.cal, self.tau = budget, None, None

    def fit(self, stats):
        """stats: (N x E) clean statistics pooled over runs (NaN = unobserved)."""
        S = np.asarray(stats, float)
        self.cal = [ECDFCalibrator().fit(S[np.isfinite(S[:, e]), e]) for e in range(S.shape[1])]
        self.tau = budget_threshold(self.layer_score(S), self.budget)
        return self

    def edge_scores(self, stats):
        S = np.asarray(stats, float)
        out = np.zeros(S.shape)
        for e, c in enumerate(self.cal):
            ok = np.isfinite(S[:, e])
            out[ok, e] = c.transform(S[ok, e])
        return out

    def layer_score(self, stats):
        return self.edge_scores(stats).max(axis=1)

    def to_dict(self):
        return {"budget": self.budget, "tau": self.tau, "edges": [c.to_dict() for c in self.cal]}

    @classmethod
    def from_dict(cls, d):
        c = cls(d["budget"])
        c.tau, c.cal = d["tau"], [ECDFCalibrator.from_dict(x) for x in d["edges"]]
        return c


def min_vertex_covers(nodes, pairs):
    """All minimum vertex covers of the graph (nodes, pairs). Brute force (few nodes)."""
    nodes = sorted(nodes)
    if not pairs:
        return [()]
    for r in range(1, len(nodes) + 1):
        cov = [c for c in combinations(nodes, r) if all(a in c or b in c for a, b in pairs)]
        if cov:
            return cov
    return []


def blame_pattern(edges, alarm, observed):
    """Blamed node (str), UNDECIDED, or None (no alarm) for one second. alarm / observed: bool per edge."""
    pairs = {tuple(sorted((e.a, e.b))) for e, al in zip(edges, alarm) if al}
    if not pairs:
        return None
    nodes = {n for p in pairs for n in p}
    cov = min_vertex_covers(nodes, sorted(pairs))
    if len(cov) != 1 or len(cov[0]) != 1:
        return UNDECIDED
    d = cov[0][0]
    partners = {a if b == d else b for a, b in pairs}
    if len(partners) < 2:
        return UNDECIDED
    agree = {tuple(sorted((e.a, e.b))) for e, al, ob in zip(edges, alarm, observed) if ob and not al}
    alarmed = pairs
    for p, q in combinations(sorted(partners), 2):
        if (p, q) in agree and (p, q) not in alarmed:
            return d
    return UNDECIDED


def blame(edges, alarm, observed):
    """Per second (rows of the T x E bool matrices) -> array of object (node, UNDECIDED or None). Patterns are cached."""
    alarm, observed = np.asarray(alarm, bool), np.asarray(observed, bool)
    out = np.empty(len(alarm), object)
    memo = {}
    for i in range(len(alarm)):
        key = (alarm[i].tobytes(), observed[i].tobytes())
        if key not in memo:
            memo[key] = blame_pattern(edges, alarm[i], observed[i])
        out[i] = memo[key]
    return out


class WhichDomainLies:
    """The S2 layer for one witness graph: edges + SigmaModel z (computed by the caller) -> CUSUM -> calibration -> blame."""

    def __init__(self, edges, domain_of, k=0.5, budget=0.01):
        self.edges, self.domain_of, self.k, self.budget = list(edges), dict(domain_of), k, budget
        self.calibration = None

    def statistics(self, Z):
        return cusum(Z, self.k)

    def fit(self, Z_runs):
        """Z_runs: list of clean validation runs (T x E)."""
        self.calibration = Calibration(self.budget).fit(np.vstack([self.statistics(Z) for Z in Z_runs]))
        return self

    def run(self, Z):
        """One run -> dict(stat, edge_score, score, alarm (T x E), layer_alarm, observed, blamed)."""
        S = self.statistics(Z)
        es = self.calibration.edge_scores(S)
        al = es >= self.calibration.tau
        obs = np.isfinite(S)
        return {"stat": S, "edge_score": es, "score": es.max(axis=1), "alarm": al, "layer_alarm": al.any(axis=1), "observed": obs,
                "blamed": blame(self.edges, al, obs)}

    def evidence(self, t, Z, sample_ids=None):
        """Evidence list (domain "cross", layer "L2", name "cross.which_domain_lies") for one run."""
        r = self.run(Z)
        out = []
        for i in range(len(t)):
            b = r["blamed"][i]
            details = {"edge_z": {e.name: (None if not np.isfinite(Z[i, j]) else float(Z[i, j])) for j, e in enumerate(self.edges)},
                       "edge_stat": {e.name: (None if not np.isfinite(r["stat"][i, j]) else float(r["stat"][i, j])) for j, e in enumerate(self.edges)},
                       "alarming_edges": [e.name for j, e in enumerate(self.edges) if r["alarm"][i, j]],
                       "blamed_witness": b, "blamed_domain": None if b in (None, UNDECIDED) else self.domain_of[b]}
            reason = ""
            if r["layer_alarm"][i]:
                bad = ", ".join(details["alarming_edges"])
                if b == UNDECIDED:
                    reason = f"motion witnesses disagree ({bad}) but no single witness explains it (2 witnesses only, two liars or no confirmed agreement): undecided"
                else:
                    reason = (f"{b} ({self.domain_of[b]} domain) disagrees with every partner ({bad}) while the other witnesses agree: "
                              f"the {self.domain_of[b]} domain is blamed")
            out.append(Evidence(domain="cross", layer="L2", name="cross.which_domain_lies", t=float(t[i]), score=float(r["score"][i]),
                                alarm=bool(r["layer_alarm"][i]), reason=reason, details=details,
                                sample_id="" if sample_ids is None else str(sample_ids[i])))
        return out

    def to_dict(self):
        return {"edges": [e.__dict__ for e in self.edges], "domain_of": self.domain_of, "k": self.k, "budget": self.budget,
                "calibration": self.calibration.to_dict() if self.calibration else None}

    @classmethod
    def from_dict(cls, d):
        m = cls([Edge(**e) for e in d["edges"]], d["domain_of"], d["k"], d["budget"])
        if d["calibration"]:
            m.calibration = Calibration.from_dict(d["calibration"])
        return m


def run_outcome(t, onset_t, res):
    """Run-level outcome of an attacked run (onset_t finite) or a clean run (onset_t NaN):
    detected, first alarm time, delay, blame (first decided blame at/after onset; UNDECIDED if alarms but none decided)."""
    t = np.asarray(t, float)
    post = t >= onset_t if np.isfinite(onset_t) else np.ones(len(t), bool)
    al = res["layer_alarm"] & post
    if not al.any():
        return {"detected": False, "delay": None, "blame": None}
    i = int(np.flatnonzero(al)[0])
    dec = [b for b, p in zip(res["blamed"], post) if p and b not in (None, UNDECIDED)]
    return {"detected": True, "delay": float(t[i] - onset_t) if np.isfinite(onset_t) else None, "blame": dec[0] if dec else UNDECIDED}
