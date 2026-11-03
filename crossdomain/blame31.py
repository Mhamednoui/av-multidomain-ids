"""WP8 S6 (v3.1): channel-level fault isolation for the cross-domain "which domain lies" blame.

Purpose: v3 blames at DOMAIN level with a strict rule (unique one-domain vertex cover, two alarming partners joined by an OBSERVED agreeing edge). It fails in two ways:
(1) comma GNSS spoofs: the GNSS Doppler channel and its position channel are merged and the CAN speed / wheel messages are merged, and the partners (CAN speed, gyro) share no
agreeing edge, so the verdict is "undecided" and the fallback names an unrelated domain; (2) KITTI gps_can: GPS and CAN agree with each other and disagree with LiDAR odometry, which
is the same graph as a lone LiDAR fault. This module scores every hypothesis "this set of measurement channels is faulty" against the edge states and keeps the cheapest.
Inputs: per tick the per-edge alarm / observed flags of the (frozen v3) cross layer, optionally blame-only inertial edges (accelerometer-anchored speed change).
Outputs: per tick the blamed domain ("gps", "can", "lidar", "imu"), "undecided" or None (no alarm edge); the v3 cross layer, its alarms and the detection are not touched.
Cost model (fixed a priori, notes/WP8_v31.md "S6 round 1"): cost(H) = sensor cost of every sensor touched by H + 0.5 per extra faulty channel of a faulty sensor
+ 6 per alarming edge with no faulty endpoint + 3 per agreeing edge with exactly one faulty endpoint + 0.5 per agreeing edge with two faulty endpoints (a coordinated lie).
The best hypothesis is decided only when the best hypothesis with a different BLAMED domain (first domain of its set in attack-surface order) costs >= `margin` (1.0) more (round 2; round 1 compared domain sets).
Inertial edges: u_s(k) = s(k) - V(k) (speed minus integrated accelerometer); D_s(k) = mean(u_s last 3 ticks) - mean(u_s anchor ticks), anchor = 3 ticks starting 12 ticks before the first alarm
of the episode; the edge (s, ins) alarms when |D_s| >= tau * sigma_s(delta), sigma and tau fitted on clean TRAIN runs only (robust sd by delta bin, 99.9th percentile).
References: Preparata, Metze, Chien 1967 (system-level diagnosis); Gertler 1998 (fault detection and diagnosis with structured residuals); Blanke et al. 2016 (diagnosis and fault-tolerant control).
"""
from itertools import combinations

import numpy as np

UNDECIDED = "undecided"
DOMAIN_ORDER = ("gps", "can", "lidar", "imu")           # attack-surface order, used to name one domain of a multi-domain hypothesis
PRIOR_COST = {"gps": 2.0, "can": 3.0, "lidar": 4.0, "imu": 5.0}     # A2 / A3 (a priori from the attack surface, never tuned)
EQUAL_COST = {k: 3.0 for k in PRIOR_COST}                           # A1
C_CHAN, C_MISS, C_FP, C_COLL, MARGIN = 0.5, 6.0, 3.0, 0.5, 1.0
PERSIST_M, PERSIST_W = 2, 5                                         # the v3 correlator's persistence rule
EPISODE_GAP = 15


class Graph:
    """Channel graph: nodes (measurement channels) with their sensor (domain), edges as node pairs."""

    def __init__(self, nodes, sensor_of, edges):
        self.nodes, self.sensor_of, self.edges = list(nodes), dict(sensor_of), [tuple(e) for e in edges]
        idx = {n: i for i, n in enumerate(self.nodes)}
        self.ia = np.array([idx[a] for a, _ in self.edges])
        self.ib = np.array([idx[b] for _, b in self.edges])
        self.sensors = [s for s in DOMAIN_ORDER if s in set(self.sensor_of.values())]
        self.sens_idx = np.array([self.sensors.index(self.sensor_of[n]) for n in self.nodes])
        subsets = [()]
        for r in range(1, 4):
            subsets += list(combinations(range(len(self.nodes)), r))
        self.H = np.zeros((len(subsets), len(self.nodes)), bool)
        for i, s in enumerate(subsets):
            self.H[i, list(s)] = True
        self.H = self.H[1:]
        S = np.zeros((len(self.H), len(self.sensors)), bool)          # sensor touched by H
        n_chan = np.zeros((len(self.H), len(self.sensors)))
        for j in range(len(self.sensors)):
            n_chan[:, j] = self.H[:, self.sens_idx == j].sum(axis=1)
            S[:, j] = n_chan[:, j] > 0
        self.touched, self.n_chan = S, n_chan
        self.in_a, self.in_b = self.H[:, self.ia], self.H[:, self.ib]
        self.covered = self.in_a | self.in_b
        self.both, self.one = self.in_a & self.in_b, self.in_a ^ self.in_b
        self.dom_sets = [tuple(self.sensors[j] for j in range(len(self.sensors)) if S[i, j]) for i in range(len(self.H))]


class Blame31:
    """Hypothesis scoring on a Graph. sensor_cost: dict sensor -> cost (PRIOR_COST or EQUAL_COST)."""

    def __init__(self, graph, sensor_cost=PRIOR_COST, margin=MARGIN):
        self.g, self.margin = graph, margin
        sc = np.array([sensor_cost[s] for s in graph.sensors])
        self.base = (graph.touched * sc[None, :]).sum(axis=1) + C_CHAN * np.maximum(graph.n_chan - 1, 0).sum(axis=1)
        self.top = np.array([next((d for d in DOMAIN_ORDER if d in ds), "") for ds in graph.dom_sets])      # blamed domain of every hypothesis
        self._memo = {}

    def diagnose(self, state):
        """state: (E,) int8, 1 = alarm, 0 = agree, -1 = unobserved -> (domain | UNDECIDED | None, best cost, domain set)."""
        key = state.tobytes()
        if key in self._memo:
            return self._memo[key]
        g = self.g
        al, ag = state == 1, state == 0
        if not al.any():
            out = (None, np.nan, ())
        else:
            cost = (self.base + C_MISS * (al[None, :] & ~g.covered).sum(axis=1) + C_FP * (ag[None, :] & g.one).sum(axis=1)
                    + C_COLL * (ag[None, :] & g.both).sum(axis=1))
            i = int(np.argmin(cost))
            ds = g.dom_sets[i]
            top = self.top[i]
            other = self.top != top
            gap = (cost[other].min() - cost[i]) if other.any() else np.inf
            if gap >= self.margin - 1e-9:
                out = (top, float(cost[i]), ds)
            else:
                out = (UNDECIDED, float(cost[i]), ds)
        self._memo[key] = out
        return out

    def blame(self, state):
        """(n, E) int8 states -> (n,) object array of domain | UNDECIDED | None."""
        out = np.empty(len(state), object)
        for i in range(len(state)):
            out[i] = self.diagnose(state[i])[0]
        return out


# ------------------------------------------------------------------------------------------------ edge states with persistence
def persist_states(alarm, observed, m=PERSIST_M, w=PERSIST_W):
    """(n, E) bool alarm / observed -> (n, E) int8: 1 alarm (>= m alarms in the last w ticks), -1 unobserved (observed ticks with 0 < alarms < m, or never observed in the window), 0 agree."""
    alarm, observed = np.asarray(alarm, bool), np.asarray(observed, bool)
    n, E = alarm.shape
    c = np.cumsum(np.vstack([np.zeros((1, E), int), alarm.astype(int)]), axis=0)
    lo = np.maximum(np.arange(n) + 1 - w, 0)
    cnt = c[np.arange(n) + 1] - c[lo]
    co = np.cumsum(np.vstack([np.zeros((1, E), int), observed.astype(int)]), axis=0)
    obs_w = (co[np.arange(n) + 1] - co[lo]) > 0
    st = np.full((n, E), -1, np.int8)
    st[(cnt == 0) & obs_w] = 0
    st[cnt >= m] = 1
    return st


def episodes(tick_alarm, gap=EPISODE_GAP):
    """tick alarm (n,) bool -> list of (first, last) tick of alarm episodes (alarm ticks closer than gap + 1 belong together)."""
    t = np.flatnonzero(np.asarray(tick_alarm, bool))
    if not len(t):
        return []
    br = np.flatnonzero(np.diff(t) > gap)
    first = np.r_[t[0], t[br + 1]]
    last = np.r_[t[br], t[-1]]
    return list(zip(first.tolist(), last.tolist()))


# ------------------------------------------------------------------------------------------------ graphs
K_NODES = ["gps_v", "gps_lat", "lidar_v", "lidar_lat", "lidar_yaw", "can_v", "compass", "gyro", "ins_v"]
K_SENSOR = {"gps_v": "gps", "gps_lat": "gps", "lidar_v": "lidar", "lidar_lat": "lidar", "lidar_yaw": "lidar", "can_v": "can", "compass": "imu", "gyro": "imu", "ins_v": "imu"}
K_EDGES = [("gps_v", "lidar_v"), ("gps_v", "can_v"), ("lidar_v", "can_v"), ("gps_lat", "lidar_lat"), ("compass", "lidar_yaw"), ("compass", "gyro"), ("gyro", "lidar_yaw")]
K_INERTIAL = [("gps_v", "ins_v"), ("lidar_v", "ins_v"), ("can_v", "ins_v")]
C_NODES = ["gnss_vel", "gnss_pos", "gnss_yaw", "can_v", "wheel_v", "gyro"]
C_SENSOR = {"gnss_vel": "gps", "gnss_pos": "gps", "gnss_yaw": "gps", "can_v": "can", "wheel_v": "can", "gyro": "imu"}
C_EDGES = [("gnss_vel", "can_v"), ("gnss_vel", "wheel_v"), ("can_v", "wheel_v"), ("gnss_pos", "can_v"), ("gnss_pos", "wheel_v"), ("gnss_yaw", "gyro")]


def graph_k(inertial):
    nodes = K_NODES if inertial else [n for n in K_NODES if n != "ins_v"]
    return Graph(nodes, K_SENSOR, K_EDGES + (K_INERTIAL if inertial else []))


def graph_c():
    return Graph(C_NODES, C_SENSOR, C_EDGES)


# ------------------------------------------------------------------------------------------------ inertial edges (K)
DELTA_BINS = (5, 8, 12, 20, 35, 70)
ANCHOR_PRE, ANCHOR_N, SMOOTH = 12, 3, 3


def inertial_u(speed, A):
    """speed (n, 3) gps / lidar / can forward speed, A (n,) accelerometer increments -> u = speed - cumulative integral (n, 3)."""
    return np.asarray(speed, float) - np.cumsum(np.asarray(A, float))[:, None]


def _nanmean(x):
    """Mean over the finite ticks per column (NaN when none): the first grid tick of a displacement-based speed is NaN."""
    ok = np.isfinite(x)
    n = ok.sum(axis=0)
    return np.where(n > 0, np.where(ok, x, 0.0).sum(axis=0) / np.maximum(n, 1), np.nan)


def deviation(u, a, k):
    """D at tick k for an anchor starting at a: mean of the last SMOOTH ticks minus mean of the anchor ticks (needs k - SMOOTH + 1 >= a + ANCHOR_N)."""
    return _nanmean(u[k - SMOOTH + 1:k + 1]) - _nanmean(u[a:a + ANCHOR_N])


class InertialModel:
    """sigma_s(delta) and threshold tau of the inertial edges, fitted on clean TRAIN runs (every possible anchor)."""

    def __init__(self):
        self.sigma, self.tau = None, None

    def fit(self, runs):
        """runs: list of (speed (n, 3), A (n,)) clean runs."""
        by = [[[] for _ in range(len(DELTA_BINS) - 1)] for _ in range(3)]
        for speed, A in runs:
            u = inertial_u(speed, A)
            n = len(u)
            for a in range(0, n):
                for k in range(a + ANCHOR_N + SMOOTH - 1, n):
                    D = deviation(u, a, k)
                    b = np.searchsorted(DELTA_BINS, k - a, side="right") - 1
                    if b < 0:
                        continue
                    b = min(b, len(DELTA_BINS) - 2)
                    for s in range(3):
                        if np.isfinite(D[s]):
                            by[s][b].append(D[s])
        sig = np.zeros((3, len(DELTA_BINS) - 1))
        for s in range(3):
            for b in range(len(DELTA_BINS) - 1):
                x = np.asarray(by[s][b])
                sig[s, b] = 1.4826 * np.median(np.abs(x - np.median(x))) if len(x) >= 20 else np.nan
            ok = np.isfinite(sig[s])
            sig[s] = np.where(ok, sig[s], sig[s][ok][-1] if ok.any() else 1.0)
            sig[s] = np.maximum.accumulate(sig[s])             # sigma does not shrink with delta
        self.sigma = sig
        zs = []
        for s in range(3):
            for b in range(len(DELTA_BINS) - 1):
                zs += list(np.abs(np.asarray(by[s][b])) / sig[s, b])
        self.tau = float(max(3.5, np.percentile(zs, 99.9)))
        return self

    def sigma_at(self, delta):
        b = min(max(np.searchsorted(DELTA_BINS, delta, side="right") - 1, 0), len(DELTA_BINS) - 2)
        return self.sigma[:, b]

    def edges(self, speed, A, tick_alarm):
        """Inertial edge flags for one run: (alarm (n, 3), observed (n, 3)); evaluated inside the alarm episodes of `tick_alarm` only."""
        n = len(speed)
        al, ob = np.zeros((n, 3), bool), np.zeros((n, 3), bool)
        u = inertial_u(speed, A)
        for first, last in episodes(tick_alarm):
            a = max(0, first - ANCHOR_PRE)
            for k in range(max(first, a + ANCHOR_N + SMOOTH - 1), min(n, last + 1)):
                D = deviation(u, a, k)
                z = np.abs(D) / self.sigma_at(k - a)
                ok = np.isfinite(z)
                ob[k] = ok
                al[k] = ok & (z >= self.tau)
        return al, ob

    def to_dict(self):
        return {"sigma": self.sigma.tolist(), "tau": self.tau, "delta_bins": list(DELTA_BINS)}


# ------------------------------------------------------------------------------------------------ run-level API
def blame_run(blamer, graph_edges_alarm, graph_edges_observed, cross_alarm, extra_alarm=None, extra_observed=None):
    """Cross-layer blame per tick for one run. graph_edges_*: (n, E0) v3 edge alarm / observed flags; extra_*: (n, E1) blame-only edges appended after them (or None).
    Returns (n,) object: None where the cross layer has no alarm, else the verdict (a cross-alarm tick with no persistent alarm edge gets UNDECIDED)."""
    al = np.asarray(graph_edges_alarm, bool)
    ob = np.asarray(graph_edges_observed, bool)
    if extra_alarm is not None:
        al = np.hstack([al, extra_alarm])
        ob = np.hstack([ob, extra_observed])
    st = persist_states(al, ob)
    out = blamer.blame(st)
    ca = np.asarray(cross_alarm, bool)
    res = np.full(len(ca), None, object)
    for i in np.flatnonzero(ca):
        res[i] = UNDECIDED if out[i] is None else out[i]
    return res
