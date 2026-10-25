"""FusionRunner: the FROZEN system fusion (fusion/system.py SystemV2, config version 2) as a 1 Hz stream with availability times (WP7 S2).

Purpose: the domain runners deliver tick values (score, count, per-layer scores / alarms, own alarm, cross-domain blame) of the 1 s system clock; a tick value reaches the fusion
at its AVAILABILITY time (normally the end of the tick; the network Evidence of a minute only when its 5-minute bin has closed, up to minutes later). At every system second T the
runner knows only what has arrived, evaluates every tick before T whose inputs changed (per-entry density transform + ECDF -> label-free combiner -> system threshold -> tick blame,
all row-wise functions of the frozen SystemV2), and re-runs the frozen temporal correlator (fusion/correlator.py: events, blame by decided majority, response, SAFE_STOP needs two
domains) on the ticks known so far. A late domain can only RAISE a tick's score (monotone combiner), so an alarm that appears late is a late alert, never a retraction.
Recorded: first_known[k] = the first second at which the alarm of tick k was visible; timeline = the events known at each second where they changed (visible_time(lo, hi, level) =
first second at which an event over the ticks lo..hi was known with that response level, WARN / DEGRADE / SAFE_STOP); the wall time of each step (latency). final() returns the same dict as SystemV2.run on the full composite
(tested equal: tests/system/test_fusion_runner.py, and on every composite of WP7 S2).
Nothing is fitted or tuned here; the system object is used as it is. Cost: one numpy evaluation per tick and one correlator pass per second (track_events=True) or at the end only
(track_events=False, used for the 8-hour clean timelines).
Reference: fusion/system.py, fusion/correlator.py, notes/WP7_system.md "S2 start".
"""
import time

import numpy as np

from fusion import correlator as CR
from fusion.system import entry_domain

LEVEL = {l: i for i, l in enumerate(CR.LEVELS)}


class FusionRunner:
    def __init__(self, system, track_events=True, explain=True, layer_names=None):
        self.sys, self.track, self.explain, self.layer_names = system, track_events, explain, layer_names
        self.domains = list(system.domains)
        self.reset(0)

    # ------------------------------------------------------------------------------------------------------------------
    def reset(self, n_ticks):
        n = int(n_ticks)
        self.n = n
        self.part = {}                                         # domain -> dict of arrays
        self.dirty = set()
        self.X = None
        self.score = np.zeros(n)
        self.alarm = np.zeros(n, bool)
        self.own = np.zeros((n, len(self.domains)), bool)
        self.blame = np.full(n, "undecided", object)
        self.reasons = np.full(n, "", object)
        self.first_known = np.full(n, np.nan)
        self.evaluated = 0
        self.T = 0
        self.timeline = []                                     # [(T, ((start, end, response), ...))] every second at which the set of events known so far changed
        self._last_summary = None
        self.step_ns = []

    def submit(self, domain, k, score, count=1.0, layers=None, dom_alarm=False, layer_alarm=None, blame=None):
        """Tick k of `domain` became available (its Evidence is final for this second)."""
        k = int(k)
        p = self.part.get(domain)
        lay = np.zeros(1) if layers is None else np.atleast_1d(np.asarray(layers, np.float32))
        if p is None:
            m = len(lay)
            p = self.part[domain] = {"score": np.zeros(self.n, np.float32), "count": np.zeros(self.n, np.float32), "layers": np.zeros((self.n, m), np.float32),
                                     "dom_alarm": np.zeros(self.n, bool), "layer_alarm": np.zeros((self.n, m), bool), "blame": np.full(self.n, None, object)}
        p["score"][k], p["count"][k], p["layers"][k], p["dom_alarm"][k] = score, count, lay, dom_alarm
        p["layer_alarm"][k] = False if layer_alarm is None else np.atleast_1d(np.asarray(layer_alarm, bool))
        p["blame"][k] = blame
        self.dirty.add(k)

    def parts(self, sl=None):
        """Parts dict for SystemV2 (all domains; absent ones zero) over slice sl."""
        sl = slice(0, self.n) if sl is None else sl
        out = {}
        for d in self.domains:
            p = self.part.get(d)
            if p is None:
                out[d] = {"score": np.zeros(self.n, np.float32)[sl], "count": np.zeros(self.n, np.float32)[sl], "layers": np.zeros((self.n, 1), np.float32)[sl],
                          "dom_alarm": np.zeros(self.n, bool)[sl], "layer_alarm": np.zeros((self.n, 1), bool)[sl], "blame": np.full(self.n, None, object)[sl]}
            else:
                out[d] = {k: v[sl] for k, v in p.items()}
        return out

    def _eval(self, k):
        s = self.sys
        parts = self.parts(slice(k, k + 1))
        X = s.matrix(parts)
        sc = float(s.fusion.scores(X)[0])
        own, own_e = s.own_by_domain(parts)
        cr = parts.get("cross")
        bl = CR.tick_blame([entry_domain(e) for e in s.entries], X, own_e, None if cr is None else cr["blame"], None if cr is None else cr["dom_alarm"])
        self.score[k], self.alarm[k], self.own[k], self.blame[k] = sc, sc >= s.fusion.threshold, own[0], bl[0]
        if self.X is None:
            self.X = np.zeros((self.n, X.shape[1]))
        self.X[k] = X[0]
        if self.alarm[k]:
            if np.isnan(self.first_known[k]):
                self.first_known[k] = self.T
            if self.explain:
                v = s.views(parts)
                ln = self.layer_names or {e: [f"{e}.layer{j}" for j in range(np.asarray(v[e]["layer_alarm"]).reshape(1, -1).shape[1])] for e in s.entries}
                self.reasons[k] = s.fusion.explain(0, X[0], v, ln, sc).reason
        else:
            self.reasons[k] = ""

    def step(self, T):
        """System second T: every tick k < T is evaluated (new ticks and ticks whose inputs changed)."""
        t0 = time.perf_counter_ns()
        self.T = int(T)
        todo = set(range(self.evaluated, min(self.T, self.n))) | {k for k in self.dirty if k < self.T}
        for k in sorted(todo):
            self._eval(k)
        self.dirty = {k for k in self.dirty if k >= self.T}
        self.evaluated = max(self.evaluated, min(self.T, self.n))
        if self.track and todo:
            self._log_events()
        self.step_ns.append(time.perf_counter_ns() - t0)

    def _events(self, m, explain=True):
        s = self.sys
        return s.correlator.events(self.alarm[:m], self.own[:m], s.domains, self.blame[:m], self.reasons[:m] if explain else None)

    def _log_events(self):
        summ = tuple((e.start, e.end, e.response) for e in self._events(self.evaluated, explain=False))
        if summ != self._last_summary:
            self.timeline.append((self.T, summ))
            self._last_summary = summ

    def visible_time(self, lo, hi, level="WARN"):
        """First second at which an event overlapping the ticks [lo, hi] was known with a response >= level (None if never)."""
        for T, summ in self.timeline:
            if any(s <= hi and e >= lo and LEVEL[r] >= LEVEL[level] for s, e, r in summ):
                return T
        return None

    def final(self):
        """Same dict as SystemV2.run on the full composite (X, score, alarm, own, blame, events)."""
        m = self.evaluated
        return {"X": self.X if self.X is not None else np.zeros((self.n, len(self.sys.entries))), "score": self.score[:m], "alarm": self.alarm[:m], "own": self.own[:m],
                "blame": self.blame[:m], "events": self._events(m)}


def replay(system, parts, avail, n, track_events=True, horizon=None, layer_names=None):
    """Drive a FusionRunner second by second with a composite stored as per-domain tick arrays.
    parts: domain -> dict(score, count, layers, dom_alarm, layer_alarm, blame, present) of length n; avail: domain -> (n,) availability time of each tick (s of the block clock);
    only ticks with present=True are submitted (absent ticks stay zero). Returns the FusionRunner after the last second (horizon = max(n, last availability time))."""
    fr = FusionRunner(system, track_events=track_events, layer_names=layer_names)
    fr.reset(n)
    buckets = {}
    for d, p in parts.items():
        if d not in system.domains:
            continue
        pres = np.asarray(p.get("present", np.ones(n, bool)), bool)
        av = np.ceil(np.maximum(np.asarray(avail[d], float), np.arange(n) + 1.0)).astype(int)
        for k in np.flatnonzero(pres):
            buckets.setdefault(int(av[k]), []).append((d, int(k)))
    last = max(buckets) if buckets else n
    H = int(max(n, last) if horizon is None else horizon)
    for T in range(1, H + 1):
        for d, k in buckets.get(T, ()):
            p = parts[d]
            fr.T = T
            fr.submit(d, k, p["score"][k], p["count"][k], p["layers"][k], p["dom_alarm"][k], p["layer_alarm"][k], None if p.get("blame") is None else p["blame"][k])
        fr.step(T)
    return fr
