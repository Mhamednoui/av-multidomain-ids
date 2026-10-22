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


def drift_cusum(Z, k, tb, freeze=2.0, state=None, return_state=False):
    """S2b drift-compensated two-sided CUSUM per column: a slowly adapting bias b (EWMA, time constant tb samples) is
    subtracted before the CUSUM; b is updated only while the edge's CUSUM statistic is below `freeze` (frozen while
    suspicious, so an attack is not absorbed). state = (S+, S-, b, seen) to continue a run (e.g. from a clean prefix).
    Returns stat (T x E) [, final state]. NaN z -> state held."""
    Z = np.asarray(Z, float)
    T, E = Z.shape
    sp, sm, b, seen = (np.zeros(E), np.zeros(E), np.zeros(E), np.zeros(E, bool)) if state is None else (x.copy() for x in state)
    out = np.full((T, E), np.nan)
    a = 0.0 if tb is None else 1.0 / tb
    for i in range(T):
        z = Z[i]
        ok = np.isfinite(z)
        zz = np.where(ok, z, 0.0)
        y = zz - b
        sp = np.where(ok, np.maximum(0.0, sp + y - k), sp)
        sm = np.where(ok, np.maximum(0.0, sm - y - k), sm)
        seen |= ok
        st = np.maximum(sp, sm)
        upd = ok & (st < freeze)
        b = np.where(upd, b + a * (zz - b), b)
        out[i] = np.where(seen, st, np.nan)
    return (out, (sp, sm, b, seen)) if return_state else out


def robust_cusum(Z, k, tb, c=0.5, warmup=0, zclip=6.0, state=None, return_state=False):
    """S2b round 2: CUSUM with robust bias tracking. Warm-up: the first `warmup` observations of an edge set its bias b
    (running mean of clip(z, +-3)) and emit no statistic (NaN). Then b <- b + clip(z - b, -c, c) / tb at every observation
    (absorption rate bounded by c / tb per sample: a constant sensor bias is learned, a step or fast ramp is not), and a
    two-sided CUSUM runs on clip(z - b, +-zclip). state = (S+, S-, b, n_obs) to continue a run."""
    Z = np.asarray(Z, float)
    T, E = Z.shape
    sp, sm, b, n = (np.zeros(E), np.zeros(E), np.zeros(E), np.zeros(E)) if state is None else (x.copy() for x in state)
    out = np.full((T, E), np.nan)
    for i in range(T):
        z = Z[i]
        ok = np.isfinite(z)
        zz = np.where(ok, z, 0.0)
        warm = ok & (n < warmup)
        b = np.where(warm, b + (np.clip(zz, -3, 3) - b) / np.maximum(n + 1, 1), b)
        run = ok & ~warm
        y = np.clip(zz - b, -zclip, zclip)
        sp = np.where(run, np.maximum(0.0, sp + y - k), sp)
        sm = np.where(run, np.maximum(0.0, sm - y - k), sm)
        b = np.where(run, b + np.clip(zz - b, -c, c) / tb, b)
        n = n + ok
        out[i] = np.where(n > warmup, np.maximum(sp, sm), np.nan)
    return (out, (sp, sm, b, n)) if return_state else out


def stat_states(Z, k, tb=None, freeze=2.0):
    """Statistic and the state BEFORE every row (list of tuples), for splicing an attack into a clean run (S2b)."""
    Z = np.asarray(Z, float)
    states, st, out = [], None, np.full(Z.shape, np.nan)
    for i in range(len(Z)):
        states.append(None if st is None else tuple(x.copy() for x in st))
        if k == "inst":
            out[i] = np.abs(Z[i])
            continue
        o, st = drift_cusum(Z[i:i + 1], k, tb, freeze, st, return_state=True)
        out[i] = o[0]
    return out, states


class Calibration:
    """Per-edge ECDF of the clean-validation statistic; tau = tie-safe budget threshold of the max over edges."""

    def __init__(self, budget=0.01):
        self.budget, self.cal, self.tau = budget, None, None

    def fit(self, stats):
        """stats: (N x E) clean statistics pooled over runs (NaN = unobserved)."""
        S = np.asarray(stats, float)
        self.cal = [ECDFCalibrator().fit(S[np.isfinite(S[:, e]), e]) if np.isfinite(S[:, e]).any() else None for e in range(S.shape[1])]
        self.tau = budget_threshold(self.layer_score(S), self.budget)
        return self

    def edge_scores(self, stats):
        S = np.asarray(stats, float)
        out = np.zeros(S.shape)
        for e, c in enumerate(self.cal):
            if c is None:                       # edge never observed on the calibration data: never alarms
                continue
            ok = np.isfinite(S[:, e])
            out[ok, e] = c.transform(S[ok, e])
        return out

    def layer_score(self, stats):
        return self.edge_scores(stats).max(axis=1)

    def to_dict(self):
        return {"budget": self.budget, "tau": self.tau, "edges": [None if c is None else c.to_dict() for c in self.cal]}

    @classmethod
    def from_dict(cls, d):
        c = cls(d["budget"])
        c.tau, c.cal = d["tau"], [None if x is None else ECDFCalibrator.from_dict(x) for x in d["edges"]]
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


def blame_domain_pattern(edges, alarm, observed, domain_of):
    """S2b domain-level blame (one second). Intra-domain alarming edges mark a domain self-inconsistent. Exactly one
    self-inconsistent domain D whose every alarming cross-domain edge contains D -> D. No self-inconsistent domain -> the
    S2 rule on the domain graph (unique 1-domain minimum vertex cover, >= 2 alarming partner domains joined by an observed
    non-alarming cross edge). Else UNDECIDED; no alarm -> None. Returns a DOMAIN name."""
    dom = lambda n: domain_of[n]
    cross_al, intra_al, agree = set(), set(), set()
    for e, al, ob in zip(edges, alarm, observed):
        da, db = dom(e.a), dom(e.b)
        p = tuple(sorted((da, db)))
        if al:
            (intra_al.add(da) if da == db else cross_al.add(p))
        elif ob and da != db:
            agree.add(p)
    if not cross_al and not intra_al:
        return None
    if len(intra_al) > 1:
        return UNDECIDED
    if len(intra_al) == 1:
        d = next(iter(intra_al))
        return d if all(d in p for p in cross_al) else UNDECIDED
    nodes = {n for p in cross_al for n in p}
    cov = min_vertex_covers(nodes, sorted(cross_al))
    if len(cov) != 1 or len(cov[0]) != 1:
        return UNDECIDED
    d = cov[0][0]
    partners = {a if b == d else b for a, b in cross_al}
    if len(partners) < 2:
        return UNDECIDED
    for p, q in combinations(sorted(partners), 2):
        if (p, q) in agree and (p, q) not in cross_al:
            return d
    return UNDECIDED


def blame(edges, alarm, observed, domain_of=None):
    """Per second (rows of the T x E bool matrices) -> array of object (node, UNDECIDED or None). Patterns are cached."""
    alarm, observed = np.asarray(alarm, bool), np.asarray(observed, bool)
    out = np.empty(len(alarm), object)
    memo = {}
    for i in range(len(alarm)):
        key = (alarm[i].tobytes(), observed[i].tobytes())
        if key not in memo:
            memo[key] = (blame_pattern(edges, alarm[i], observed[i]) if domain_of is None
                         else blame_domain_pattern(edges, alarm[i], observed[i], domain_of))
        out[i] = memo[key]
    return out


class WhichDomainLies:
    """The S2 layer for one witness graph: edges + SigmaModel z (computed by the caller) -> CUSUM -> calibration -> blame."""

    def __init__(self, edges, domain_of, k=0.5, budget=0.01, tb=None, freeze=2.0, domain_level=False):
        self.edges, self.domain_of, self.k, self.budget = list(edges), dict(domain_of), k, budget
        self.tb, self.freeze, self.domain_level = tb, freeze, domain_level      # S2b: drift compensation, domain-level blame
        self.calibration = None

    def statistics(self, Z):
        if self.k == "inst" or self.tb is None:
            return cusum(Z, self.k)
        return drift_cusum(Z, self.k, self.tb, self.freeze)

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
                "blamed": blame(self.edges, al, obs, self.domain_of if self.domain_level else None)}

    def evidence(self, t, Z, sample_ids=None):
        """Evidence list (domain "cross", layer "L2", name "cross.which_domain_lies") for one run."""
        r = self.run(Z)
        out = []
        for i in range(len(t)):
            b = r["blamed"][i]
            details = {"edge_z": {e.name: (None if not np.isfinite(Z[i, j]) else float(Z[i, j])) for j, e in enumerate(self.edges)},
                       "edge_stat": {e.name: (None if not np.isfinite(r["stat"][i, j]) else float(r["stat"][i, j])) for j, e in enumerate(self.edges)},
                       "alarming_edges": [e.name for j, e in enumerate(self.edges) if r["alarm"][i, j]],
                       "blamed_witness": None if self.domain_level else b,
                       "blamed_domain": None if b in (None, UNDECIDED) else self.domain_of.get(b, b)}
            reason = ""
            if r["layer_alarm"][i]:
                bad = ", ".join(details["alarming_edges"])
                if b == UNDECIDED:
                    reason = f"motion witnesses disagree ({bad}) but no single witness explains it (2 witnesses only, two liars or no confirmed agreement): undecided"
                else:
                    dn = self.domain_of.get(b, b)
                    reason = (f"{b} ({dn} domain) disagrees with every partner ({bad}) while the other witnesses agree: "
                              f"the {dn} domain is blamed")
            out.append(Evidence(domain="cross", layer="L2", name="cross.which_domain_lies", t=float(t[i]), score=float(r["score"][i]),
                                alarm=bool(r["layer_alarm"][i]), reason=reason, details=details,
                                sample_id="" if sample_ids is None else str(sample_ids[i])))
        return out

    def to_dict(self):
        return {"edges": [e.__dict__ for e in self.edges], "domain_of": self.domain_of, "k": self.k, "budget": self.budget, "tb": self.tb, "freeze": self.freeze, "domain_level": self.domain_level,
                "calibration": self.calibration.to_dict() if self.calibration else None}

    @classmethod
    def from_dict(cls, d):
        m = cls([Edge(**e) for e in d["edges"]], d["domain_of"], d["k"], d["budget"], d.get("tb"), d.get("freeze", 2.0), d.get("domain_level", False))
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
