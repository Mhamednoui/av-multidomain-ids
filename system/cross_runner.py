"""CrossRunner: the cross-domain "which domain lies" layer of WP6 (crossdomain/consistency.py WhichDomainLies) as a stream of 1 s witness steps (WP7 S1).

Purpose: ingest the MotionEstimate streams of the independent witnesses (gps claim, lidar odometry, can wheel speed, imu gyro / compass) as they are published, align them on
the 1 s grid of the GPS fixes with the SAME functions as the batch pipeline (crossdomain.witness.to_grid on the few buffered samples), form the 7 edge residuals of WP6 S2 design R
(speed gps-lidar / gps-can / lidar-can, lateral gps-lidar, yaw compass-lidar / compass-gyro / gyro-lidar), normalise them with the train-fitted SigmaModels, update the per-edge
statistic (S2b choice "inst" = |z|; drift-compensated CUSUM state is carried when the object uses it), apply the per-edge ECDF + tie-safe tau and the blame logic, and publish
Evidence(domain "cross", layer "L2", name "cross.which_domain_lies") for that second.
State: sample buffers of each source, the grid points still waiting for their witnesses, the CUSUM state. reset(key) clears it. Buffers keep the whole history by default (keep_s=None): the interval means of crossdomain.witness.to_grid are differences of cumulative sums, so only the full history
reproduces the batch numbers bit for bit; keep_s=<seconds> bounds the memory but changes z by ~1e-13, which can move one ECDF step (measured in results/WP7/S1_cross.json).
A grid point g is resolved when every required
source has delivered a sample at or after g (mean sources: within 0.05 s of g), when `max_wait_s` of stream time has passed, or at flush(); so an interval-mean witness (CAN, IMU) adds
at most its sample period of delay. Inputs: common.motion.MotionEstimate objects (push) or, for tests at residual level, a dict {"t", "r": {edge: residual}, "v": {edge: speed}}.
CrossObject: the fitted runtime object (SigmaModels per edge + WhichDomainLies). It is fitted by tools/WP7_S1_cross_fit.py on the WP6 S2b DEV cache (clean KITTI runs of train +
validation drives) for the runtime test: it is NOT the WP6 verdict model (WP6 S3 not started). The residual design (edges, forward-speed R4) is copied from tools/WP6_S2_kitti.py.
Reference: crossdomain/consistency.py, crossdomain/witness.py, notes/WP6_brief.md.
"""
import json
from collections import deque
from pathlib import Path
from typing import List

import numpy as np

from common.evidence import Evidence
from common.motion import MotionEstimate
from crossdomain import consistency as CS
from crossdomain import witness as W
from crossdomain.kitti import forward_speed
from system.runner import Runner

# (node a, node b, quantity, S1 model key) as tools/WP6_S2_kitti.py EDGES
EDGES = [("gps", "lidar", "speed", "gps-lidar speed"), ("gps", "can", "speed", "gps-can speed"), ("lidar", "can", "speed", "lidar-can speed"),
         ("gps", "lidar", "lateral", "gps-lidar lateral"), ("compass", "lidar", "yaw", "gps-lidar yaw_rate"),
         ("compass", "gyro", "yaw", "gps-imu yaw_rate"), ("gyro", "lidar", "yaw", "imu-lidar yaw_rate")]
DOMAIN_OF = {"gps": "gps", "lidar": "lidar", "can": "can", "gyro": "imu", "compass": "imu"}
SOURCES = ("gps", "lidar", "can", "imu")


def edge_list():
    return [CS.Edge(a, b, q, m) for a, b, q, m in EDGES]


def residuals(G):
    """Copy of tools/WP6_S2_kitti.residuals: grids of gps, lidar (R4 forward speed), can, imu -> {edge name: (r, v)}."""
    sp = lambda s: G[s]["speed"].to_numpy(float)
    yw = lambda s: G[s]["yaw_rate"].to_numpy(float)
    mean2 = lambda a, b: np.nanmean(np.c_[a, b], axis=1)
    out = {}
    out["gps-lidar speed"] = (sp("gps") - sp("lidar"), mean2(sp("gps"), sp("lidar")))
    out["gps-can speed"] = (sp("gps") - sp("can"), mean2(sp("gps"), sp("can")))
    out["lidar-can speed"] = (sp("lidar") - sp("can"), mean2(sp("lidar"), sp("can")))
    out["gps-lidar lateral"] = (G["gps"]["dy"].to_numpy(float) - G["lidar"]["dy"].to_numpy(float), sp("lidar"))
    out["compass-lidar yaw"] = (yw("gps") - yw("lidar"), mean2(sp("gps"), sp("lidar")))
    out["compass-gyro yaw"] = (yw("gps") - yw("imu"), sp("gps"))
    out["gyro-lidar yaw"] = (yw("imu") - yw("lidar"), sp("lidar"))
    return out


class CrossObject:
    """Edges + SigmaModel per edge + fitted WhichDomainLies; JSON persistence."""

    def __init__(self, models, model):
        self.models, self.model = models, model
        self.edges = model.edges

    def z(self, r_row, v_row):
        """r_row / v_row: arrays over the edges -> z array (NaN where not observed)."""
        out = np.full(len(self.edges), np.nan)
        for j, e in enumerate(self.edges):
            out[j] = self.models[e.name].z(r_row[j], v_row[j])
        return out

    def save(self, folder):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "cross.json").write_text(json.dumps({"schema": 1, "sigma_models": {n: m.to_dict() for n, m in self.models.items()},
                                                       "model": self.model.to_dict(), "note": "runtime-test object fitted on the WP6 S2b DEV cache; not the WP6 verdict model"}))

    @classmethod
    def load(cls, folder):
        d = json.loads((Path(folder) / "cross.json").read_text())
        return cls({n: W.SigmaModel.from_dict(m) for n, m in d["sigma_models"].items()}, CS.WhichDomainLies.from_dict(d["model"]))


def evidence_row(model, t, z, stat, es, al, obs, blamed, sample_id="") -> Evidence:
    """One-second Evidence, same fields as WhichDomainLies.evidence for that second."""
    edges = model.edges
    details = {"edge_z": {e.name: (None if not np.isfinite(z[j]) else float(z[j])) for j, e in enumerate(edges)},
               "edge_stat": {e.name: (None if not np.isfinite(stat[j]) else float(stat[j])) for j, e in enumerate(edges)},
               "alarming_edges": [e.name for j, e in enumerate(edges) if al[j]],
               "blamed_witness": None if model.domain_level else blamed,
               "blamed_domain": None if blamed in (None, CS.UNDECIDED) else model.domain_of.get(blamed, blamed)}
    reason = ""
    if bool(al.any()):
        bad = ", ".join(details["alarming_edges"])
        if blamed == CS.UNDECIDED:
            reason = f"motion witnesses disagree ({bad}) but no single witness explains it (2 witnesses only, two liars or no confirmed agreement): undecided"
        else:
            dn = model.domain_of.get(blamed, blamed)
            reason = (f"{blamed} ({dn} domain) disagrees with every partner ({bad}) while the other witnesses agree: "
                      f"the {dn} domain is blamed")
    return Evidence(domain="cross", layer="L2", name="cross.which_domain_lies", t=float(t), score=float(es.max()), alarm=bool(al.any()), reason=reason,
                    details=details, sample_id=str(sample_id))


class CrossRunner(Runner):
    domain = "cross"
    name = "cross.runner"
    status = "frozen"
    period_s = 1.0
    primary_layer = "L2"

    def __init__(self, obj: CrossObject, bus=None, sources=SOURCES, max_wait_s=2.5, keep_s=None):
        super().__init__(bus)
        self.obj, self.sources, self.max_wait_s, self.keep_s = obj, tuple(sources), max_wait_s, keep_s
        self._reset("")

    def _reset(self, key):
        self.buf = {s: deque() for s in self.sources}       # MotionEstimate per source
        self.latest = {s: -np.inf for s in self.sources}
        self.pending = deque()                              # grid times (GPS estimate times) waiting for their witnesses
        self.state = None                                   # CUSUM state (None for "inst")
        self.step = 0
        self.t_now = -np.inf

    def _size(self):
        return self.step

    # ---- row statistic -------------------------------------------------------------------------------
    def _row_evidence(self, t, z) -> Evidence:
        m = self.obj.model
        Z = z[None, :]
        if m.k == "inst":
            S = np.abs(Z)
        else:                                               # plain CUSUM is drift_cusum with tb None (b stays 0)
            S, self.state = CS.drift_cusum(Z, m.k, m.tb, m.freeze, self.state, return_state=True)
        es = m.calibration.edge_scores(S)
        al = es >= m.calibration.tau
        obs = np.isfinite(S)
        blamed = CS.blame(m.edges, al, obs, m.domain_of if m.domain_level else None)[0]
        ev = evidence_row(m, t, z, S[0], es[0], al[0], obs[0], blamed, sample_id=f"{self.key}/{self.step}" if self.key else str(self.step))
        self.step += 1
        return ev

    def step_residuals(self, t, r, v) -> Evidence:
        """Residual-level entry: r, v dicts edge name -> value (missing = NaN)."""
        rr = np.array([r.get(e.name, np.nan) for e in self.obj.edges], float)
        vv = np.array([v.get(e.name, np.nan) for e in self.obj.edges], float)
        return self._row_evidence(t, self.obj.z(rr, vv))

    # ---- alignment -----------------------------------------------------------------------------------
    def _grids(self, g):
        G = {}
        for s in SOURCES:
            frame = W.to_frame(list(self.buf[s]), source=s)
            G[s] = W.to_grid(frame, [g])
        G["gps"] = forward_speed(G["gps"])
        G["lidar"] = forward_speed(G["lidar"])
        return G

    def _resolve(self, g) -> Evidence:
        G = self._grids(g)
        res = residuals(G)
        r = {k: float(x[0][0]) for k, x in res.items()}
        v = {k: float(x[1][0]) for k, x in res.items()}
        return self.step_residuals(g, r, v)

    def _ready(self, g):
        if self.t_now - g > self.max_wait_s:
            return True
        for s in self.sources:
            need = g - (0.05 if W.SOURCE_KIND.get(s, "inst") == "mean" else 1e-9)
            if self.latest[s] < need:
                return False
        return True

    def _drain(self, final=False) -> List[Evidence]:
        out = []
        while self.pending and (final or self._ready(self.pending[0])):
            g = self.pending.popleft()
            out.append(self._resolve(g))
            if self.keep_s is not None:                     # bounded buffers: forget samples no later grid point can use (keep the last one before the window)
                for s in self.sources:
                    b = self.buf[s]
                    lim = (self.pending[0] if self.pending else g) - self.keep_s
                    while len(b) > 1 and b[1].t < lim:
                        b.popleft()
        return out

    def _push(self, sample) -> List[Evidence]:
        if isinstance(sample, dict):                        # residual-level witness step
            return [self.step_residuals(sample["t"], sample["r"], sample["v"])]
        me: MotionEstimate = sample
        s = me.source
        if s not in self.buf:
            raise ValueError(f"unknown source {s!r}")
        self.buf[s].append(me)
        self.latest[s] = max(self.latest[s], me.t)
        self.t_now = max(self.t_now, me.t)
        if s == "gps":
            self.pending.append(me.t)
        return self._drain()

    def _flush(self) -> List[Evidence]:
        return self._drain(final=True)
