"""WP6 S5: temporal correlator (per-tick system alarms -> alert EVENTS) and response policy of the M2 system.

Inputs per drive (1 Hz system ticks): alarm (n,) bool = system score >= system threshold; own (n, D) bool = each entry's own domain alarm; blame (n,) str =
per-tick blamed domain ("undecided" when no domain can be named; see tick_blame); optional reasons (n,) str (explanation of the first alarm tick).
Correlator: alarm ticks closer than `gap` ticks belong to one episode; an episode becomes an ALERT EVENT at the first tick where >= m of its alarm ticks fall in the last
w ticks (persistence), or, with corroborate=True, where >= 2 different domains raise their own alarm in the same tick. Alarm ticks of episodes that never confirm are
LOGGED only. An event: start (confirmation tick), first alarm, end (last alarm tick), alarm ticks, domains named, blame counts, blamed domain, response, explanation.
Response policy (fixed a priori, notes/WP6_crossdomain.md "S5 start"): LOG < WARN (every event) < DEGRADE <domain> (blamed domain has >= 3 blamed alarm ticks)
< SAFE_STOP recommendation (>= 2 motion-critical domains blamed >= 3 ticks each, or a motion-critical degrade in an event lasting >= 30 s). V2X and network alone
never exceed DEGRADE. Recommendations only: the evaluation does not feed them back into detection.
Copied logic (re-written, vectorised): codes_v2/temporal/temporal_correlator.py (sliding-window escalation: rate of attack ticks in the last `window` alerts, persistent
domain = most frequent triggering domain) and codes_v2/response/response_module.py (level -> log / warning / alert record / isolate flag). v2 windowing/ (sample
buffering before the detectors) is retired: v3 domains window their own samples, the system runs on a 1 Hz clock.
WP6 S5b (M2 addendum, config version 2): blame_rule "majority_all" / "majority_decided" (event blame = a decided domain with > 50% of the event's alarm
ticks / of its decided alarm ticks (>= 2), else "undecided"; M2 = "plurality") and safe_stop_min_domains = 2 (SAFE_STOP only when >= 2 different domains raised
their own alarm inside the event, else capped at DEGRADE; M2 = 1). Defaults reproduce M2 exactly (old pickles have no such attributes: getattr defaults).
References: ARCHITECTURE.md sections 2-4; WP7 S1b (network Evidence is final only when its 5-minute bin closes: up to ~5 min late in streaming).
"""
from dataclasses import dataclass, field

import numpy as np

LEVELS = ["LOG", "WARN", "DEGRADE", "SAFE_STOP"]
MOTION_CRITICAL = ("gps", "lidar", "can", "imu")
DEGRADE_TICKS = 3
SAFE_STOP_DURATION = 30
ACTIONS = {"gps": "fall back to LiDAR / wheel odometry for localisation; GNSS fixes marked untrusted",
           "lidar": "LiDAR odometry / objects marked untrusted; rely on the other perception sensors",
           "can": "CAN wheel-speed / signals marked untrusted; speed from GNSS / IMU; flag the ECU",
           "imu": "IMU yaw marked untrusted; heading from GNSS course / LiDAR",
           "v2x": "drop the V2X messages that raised the alarm; do not use them for planning",
           "network": "isolate / rate-limit the flagged host on the in-vehicle network"}


@dataclass
class AlertEvent:
    start: int
    first_alarm: int
    end: int
    n_alarm_ticks: int
    corroborated: bool
    domains: list
    blame_counts: dict
    blamed: str
    response: str
    degraded: list = field(default_factory=list)
    actions: list = field(default_factory=list)
    explanation: str = ""


def tick_blame(names, X, own, cross_blame=None, cross_alarm=None):
    """Per tick: (1) the cross-domain blamed domain when the cross layer alarms with a decided blame; (2) else the strongest entry (calibrated score) among the
    non-cross entries with their own alarm; (3) else the strongest entry overall if it is not cross; (4) else "undecided".
    names: entry domains (D,), X: (n, D) calibrated scores, own: (n, D) own alarms, cross_blame: (n,) object or None, cross_alarm: (n,) bool or None."""
    names = list(names)
    n = len(X)
    out = np.full(n, "undecided", object)
    nc = np.array([d != "cross" for d in names])
    Xo = np.where(own & nc[None, :], X, -1.0)
    j_own = Xo.argmax(axis=1)
    has_own = Xo.max(axis=1) >= 0
    j_top = X.argmax(axis=1)
    top_ok = nc[j_top] & (X.max(axis=1) > 0)
    nm = np.array(names, object)
    out[top_ok] = nm[j_top[top_ok]]
    out[has_own] = nm[j_own[has_own]]
    if cross_blame is not None and cross_alarm is not None:
        cb = np.array([None if b is None else str(b) for b in cross_blame], object)
        dec = np.asarray(cross_alarm, bool) & np.array([b is not None and b != "undecided" for b in cb])
        out[dec] = cb[dec]
    return out


BLAME_RULES = ("plurality", "majority_all", "majority_decided")


def event_blame(blame_counts, n_ticks, rule="plurality"):
    """Blamed domain of one event from its tick blame counts (domain -> alarm ticks, incl. "undecided")."""
    dec = {d: c for d, c in blame_counts.items() if d != "undecided"}
    if not dec:
        return "undecided"
    best = max(sorted(dec), key=lambda d: dec[d])
    if rule == "plurality":
        return best
    if rule == "majority_all":
        return best if dec[best] > 0.5 * n_ticks else "undecided"
    if rule == "majority_decided":
        nd = sum(dec.values())
        return best if nd >= 2 and dec[best] > 0.5 * nd else "undecided"
    raise ValueError(rule)


class TemporalCorrelator:
    def __init__(self, m=2, w=3, gap=5, corroborate=False, blame_rule="plurality", safe_stop_min_domains=1):
        assert m >= 1 and w >= m and gap >= 1 and blame_rule in BLAME_RULES
        self.m, self.w, self.gap, self.corroborate = int(m), int(w), int(gap), bool(corroborate)
        self.blame_rule, self.safe_stop_min_domains = blame_rule, int(safe_stop_min_domains)

    def rules(self):
        return getattr(self, "blame_rule", "plurality"), getattr(self, "safe_stop_min_domains", 1)

    def key(self):
        return f"m{self.m}w{self.w}_g{self.gap}_c{int(self.corroborate)}"

    def episodes(self, alarm, own=None):
        """-> list of (alarm tick indices of the episode, confirmation tick or None, corroborated flag)."""
        t = np.flatnonzero(np.asarray(alarm, bool))
        if not len(t):
            return []
        new = np.r_[True, np.diff(t) > self.gap]
        eid = np.cumsum(new) - 1
        first = np.flatnonzero(new)
        lo = np.maximum(np.searchsorted(t, t - self.w + 1, side="left"), first[eid])
        cnt = np.arange(len(t)) - lo + 1
        ok = cnt >= self.m
        cor = np.zeros(len(t), bool)
        if self.corroborate and own is not None:
            cor = np.asarray(own, bool)[t].sum(axis=1) >= 2
            ok = ok | cor
        out = []
        bounds = np.r_[first, len(t)]
        for e in range(len(first)):
            a, b = bounds[e], bounds[e + 1]
            k = np.flatnonzero(ok[a:b])
            if len(k):
                out.append((t[a:b], int(t[a + k[0]]), bool(cor[a + k[0]])))
            else:
                out.append((t[a:b], None, False))
        return out

    def confirmed_mask(self, alarm, own=None):
        """(n,) bool: alarm ticks that belong to an alert event at or after its confirmation (the ticks an operator sees as 'alert open')."""
        n = len(alarm)
        m = np.zeros(n, bool)
        for ticks, s, _ in self.episodes(alarm, own):
            if s is not None:
                m[ticks[ticks >= s]] = True
        return m

    def events(self, alarm, own=None, names=None, blame=None, reasons=None):
        out = []
        for ticks, s, cor in self.episodes(alarm, own):
            if s is None:
                continue
            doms = []
            if own is not None and names is not None:
                hit = np.asarray(own, bool)[ticks].any(axis=0)
                doms = [d for d, h in zip(names, hit) if h]
            bc = {}
            if blame is not None:
                u, c = np.unique(np.asarray(blame, object)[ticks].astype(str), return_counts=True)
                bc = {str(a): int(b) for a, b in zip(u, c)}
            rule, min_dom = self.rules()
            blamed = event_blame(bc, len(ticks), rule)
            resp, degraded = respond(bc, blamed, int(ticks[-1]) - s + 1, len(doms) if own is not None and names is not None else None, min_dom)
            ex = f"alert t={s}..{int(ticks[-1])} ({len(ticks)} alarm ticks{', corroborated' if cor else ''}); domains with own alarms: {', '.join(doms) or 'none'}; blamed: {blamed}"
            if reasons is not None:
                ex += f"; first alarm: {reasons[int(ticks[0])]}"
            out.append(AlertEvent(start=s, first_alarm=int(ticks[0]), end=int(ticks[-1]), n_alarm_ticks=int(len(ticks)), corroborated=cor, domains=doms,
                                  blame_counts=bc, blamed=blamed, response=resp, degraded=degraded, actions=[ACTIONS.get(d, "") for d in degraded], explanation=ex))
        return out

    def log_ticks(self, alarm, own=None):
        """Alarm ticks that never become part of a confirmed event (LOG level)."""
        return int(np.asarray(alarm, bool).sum() - sum(len(t) for t, s, _ in self.episodes(alarm, own) if s is not None))

    def to_dict(self):
        rule, min_dom = self.rules()
        return {"m": self.m, "w": self.w, "gap": self.gap, "corroborate": self.corroborate, "blame_rule": rule, "safe_stop_min_domains": min_dom}


def respond(blame_counts, blamed, duration, n_domains=None, min_domains=1):
    """Response level of one event from its blame counts (domain -> blamed alarm ticks), its blamed domain, its duration (ticks) and the number of
    different domains with their own alarm inside it (SAFE_STOP needs >= min_domains of them; min_domains = 1 is the M2 rule)."""
    degraded = sorted(d for d, c in blame_counts.items() if d != "undecided" and c >= DEGRADE_TICKS)
    mc = [d for d in degraded if d in MOTION_CRITICAL]
    corroborated = min_domains <= 1 or (n_domains is not None and n_domains >= min_domains)
    if (len(mc) >= 2 or (blamed in mc and duration >= SAFE_STOP_DURATION)) and corroborated:
        return "SAFE_STOP", degraded
    if blamed in degraded:
        return "DEGRADE", degraded
    return "WARN", degraded
