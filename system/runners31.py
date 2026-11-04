"""v3.1 runner wrappers (WP8 S7 step 0): the frozen v3.1 domain objects behind the v3 Runner contract (reset / push / flush -> list[Evidence], latency log).

New file; the v3 runners (system/*_runner.py) are untouched. Each wrapper holds one frozen v3.1 object and adds no logic of its own:
  CanRunner31     can/incremental.py IncrementalCan (constant cost per 1 s window; Evidence + MotionEstimates identical to the v3 batch CanDomain)
  V2XRunner31     v2x/ego_stream.py EgoStream (one receiver; the frozen 12-check stack, bounded state) + V2XPhysicsDomain.evidence for the calibrated Evidence
  LidarRunner31   lidar/domain31.py Domain31 stream (frozen_lidar31; call lidar.fast.set_numba(True) first for the compiled kernels, outputs identical)
  NetRunner31     network/stream31.py Stream31Final (F1: tick-final, 60 s tick) or Stream31 (RC5, labelled variant: Evidence at flow arrival)
  Blame31Stream   crossdomain/blame31.py A1 (channel graph, equal costs, 2-of-5 edge persistence) one tick at a time (== blame_run on the whole run)
  Fusion31Runner  fusion/system31.py SystemV31 + Correlator31 as a 1 Hz stream with availability times (== SystemV31.run on the composite)
Causality: every wrapper sees only what has been pushed. Equality with the batch code is tested in tests/v31/test_s7_runners.py (validation / synthetic material only).
Reference: system/runner.py (contract), notes/WP8_v31.md ("Orchestrator decision on S2 + S7 scope"), reports/WP8_S5.md, WP8_S3b.md, WP8_S4.md, WP8_S6.md, WP8_S2.md.
"""
from collections import deque
from typing import List

import numpy as np
import pandas as pd

from common.evidence import Evidence
from crossdomain import blame31 as B31
from fusion import correlator as CR
from fusion.system import entry_domain
from fusion.system31 import SystemV31
from system.fusion_runner import FusionRunner
from system.runner import Runner
from system.v2x_runner import LAYER_NAMES, V2XPhysicsDomain


class CanRunner31(Runner):
    domain = "can"
    name = "can31.runner"
    status = "frozen"
    period_s = 1.0

    def __init__(self, dom, bus=None, per_layer=True, explain=True):
        super().__init__(bus)
        from can.incremental import IncrementalCan
        self.dom, self.per_layer, self.explain = dom, per_layer, explain
        self.inc = IncrementalCan(dom, name="capture", explain=explain)

    def _reset(self, key):
        self.inc.reset(key or "capture")

    def _size(self):
        return self.inc.n_frames

    def _wrap(self, pairs) -> List[Evidence]:
        out = []
        for comb, per in pairs:
            out.append(comb)
            if self.per_layer:
                out.extend(per[l] for l in self.dom.layers)
        return out

    @staticmethod
    def _unpack(sample):
        if isinstance(sample, dict):
            return float(sample["t"]), int(sample["id"]), int(sample["dlc"]), sample["B"]
        t, i, dlc, b = sample
        return float(t), int(i), int(dlc), b

    def _push(self, sample) -> List[Evidence]:
        t, i, dlc, b = self._unpack(sample)
        return self._wrap(self.inc.push(t, i, dlc, b))

    def _flush(self) -> List[Evidence]:
        return self._wrap(self.inc.flush())

    def pop_motion(self):
        return self.inc.pop_motion()


class V2XRunner31(Runner):
    domain = "v2x"
    name = "v2x31.runner"
    status = "frozen"
    period_s = 0.1

    def __init__(self, dom: V2XPhysicsDomain, bus=None, per_layer=False, use_recv=True):
        super().__init__(bus)
        from v2x.ego_stream import EgoStream
        self.dom, self.per_layer, self.use_recv = dom, per_layer, use_recv
        self.es = EgoStream(dom.tracker, use_recv=use_recv)

    def _reset(self, key):
        self.es.reset()

    def _size(self):
        return self.es.n

    def _push(self, sample) -> List[Evidence]:
        raw = self.es.push(sample)
        df = pd.DataFrame([{"t": float(sample["t"]), "msg_id": str(sample["msg_id"]), "sender": str(sample.get("sender", sample["track"]))}])
        raws = {n: np.array([raw[n]], np.float32) for n in LAYER_NAMES}
        return self.dom.evidence(df, raws, [0], self.per_layer)


class LidarRunner31(Runner):
    domain = "lidar"
    name = "lidar31.runner"
    status = "frozen"
    period_s = 0.1

    def __init__(self, folder_or_domain, bus=None, per_layer=True, numba=True):
        super().__init__(bus)
        from lidar import fast
        from lidar.domain31 import Domain31
        if numba:
            fast.set_numba(True)
        self.dom = folder_or_domain if isinstance(folder_or_domain, Domain31) else Domain31.load(folder_or_domain)
        self.per_layer = per_layer
        self.stream = self.dom.stream()

    def _reset(self, key):
        self.stream.reset()

    def _size(self):
        return self.stream.n

    def _push(self, sample) -> List[Evidence]:
        comb, per = self.stream.push(sample["points"], sample["pose"], float(sample.get("t", 0.0)), sample.get("sample_id"))
        out = [comb]
        if self.per_layer:
            out.extend(per[x] for x in ("L1", "L2a", "L2c", "L2d"))
        return out


class NetRunner31(Runner):
    """variant "F1" = Stream31Final (Evidence when the 60 s tick of the flow has closed; frozen primary), "RC5" = Stream31 carry (Evidence at flow arrival; labelled variant)."""
    domain = "network"
    name = "net31.runner"
    status = "frozen"
    period_s = 0.001

    def __init__(self, stream, bus=None, variant="F1"):
        super().__init__(bus)
        self.s, self.variant = stream, variant

    def _reset(self, key):
        self.s.reset()

    def _size(self):
        return self.s.state.n

    def _push(self, flow) -> List[Evidence]:
        r = self.s.push(flow)
        return list(r) if isinstance(r, list) else [r]

    def _flush(self) -> List[Evidence]:
        return list(self.s.flush()) if hasattr(self.s, "flush") else []


class Blame31Stream:
    """A1 blame one tick at a time: push(edge_alarm, edge_observed, cross_alarm) -> verdict of this tick (None where the cross layer is silent). Equal to blame31.blame_run."""

    def __init__(self, blamer: B31.Blame31, m=B31.PERSIST_M, w=B31.PERSIST_W):
        self.blamer, self.m, self.w = blamer, int(m), int(w)
        self.reset()

    def reset(self):
        self.al, self.ob = deque(maxlen=self.w), deque(maxlen=self.w)

    def push(self, edge_alarm, edge_observed, cross_alarm):
        self.al.append(np.asarray(edge_alarm, bool))
        self.ob.append(np.asarray(edge_observed, bool))
        if not bool(cross_alarm):
            return None
        a, o = np.vstack(self.al), np.vstack(self.ob)
        st = np.full(a.shape[1], -1, np.int8)
        cnt = a.sum(axis=0)
        st[(cnt == 0) & o.any(axis=0)] = 0
        st[cnt >= self.m] = 1
        v = self.blamer.diagnose(st)[0]
        return B31.UNDECIDED if v is None else v


class Fusion31Runner(FusionRunner):
    """SystemV31 as a 1 Hz stream (same submit / step / replay contract as system/fusion_runner.FusionRunner; the per-tick part is the V31 decision, the events come from Correlator31)."""

    def __init__(self, system: SystemV31, track_events=True, explain=True, layer_names=None):
        super().__init__(system, track_events=track_events, explain=explain, layer_names=layer_names)

    def reset(self, n_ticks):
        super().reset(n_ticks)
        self.own = np.zeros((self.n, len(self.sys.entries)), bool)

    def _eval(self, k):
        s = self.sys
        parts = self.parts(slice(k, k + 1))
        X = s.matrix(parts)
        sc = s.combine(X)
        own = np.column_stack([np.asarray(parts[e]["dom_alarm"], bool) for e in s.entries])
        cr = parts.get("cross")
        bl = s.tick_blame(X, own, None if cr is None else cr["blame"], None if cr is None else cr["dom_alarm"])
        self.score[k], self.alarm[k], self.own[k], self.blame[k] = float(sc[0]), bool(sc[0] >= s.threshold), own[0], bl[0]
        if self.X is None:
            self.X = np.zeros((self.n, X.shape[1]))
        self.X[k] = X[0]
        if self.alarm[k]:
            if np.isnan(self.first_known[k]):
                self.first_known[k] = self.T
            if self.explain:
                self.reasons[k] = s.reason(0, X, own, sc)
        else:
            self.reasons[k] = ""

    def _events(self, m, explain=True):
        s = self.sys
        rs = (lambda i: self.reasons[i]) if explain else None
        return s.correlator.events(self.alarm[:m], self.own[:m], s.entries, self.blame[:m], rs)

    def final(self):
        m = self.evaluated
        return {"X": self.X if self.X is not None else np.zeros((self.n, len(self.sys.entries))), "score": self.score[:m], "alarm": self.alarm[:m], "own": self.own[:m],
                "blame": self.blame[:m], "events": self._events(m)}
