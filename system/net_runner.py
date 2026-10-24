"""NetworkRunner: streaming wrapper of the FROZEN network domain (network/domain.py NetworkDomain, stack H, results/WP4/s7_domain, M1-NET section 9), one flow at a time (WP7 S1b).

Replaces the S1 placeholder. Input: flow records in time order (mapping with network.domain.RAW_COLUMNS: ts, src_ip, dst_ip, dst_port, protocol + CICFlowMeter columns).
The frozen layers are NOT sample-causal by design: a flow is scored by the value of its minute cell (net.scan, net.bruteforce) and by the peak of the threshold random walk in its
5-minute bin (net.trw); net.tcp_flags is per flow. A flow's Evidence is therefore FINAL only when the longest window containing it has closed. The runner makes that explicit:
  push(flow)  appends it (state = all flows of the capture so far); when a flow of a later 5-minute bin arrives, every flow of the closed bins that was not emitted yet is scored by
              re-scoring the PREFIX with the frozen code (equal to the whole-capture result for those flows, tested) and emitted with details["final"] = True;
  flush()     end of capture: emits the remaining flows exactly as the batch code on the whole capture does (details["final"] as the domain defines it).
So Evidence appears with a delay of up to the window length (<= 5 min of flow time + the rest of the current bin) and nothing later than the closed bins is read: causal at the
level of windows. Cost: one prefix re-score per closed 5-minute bin; the append of a flow is microseconds. sample_id = arrival index of the flow in the capture.
Order contract: nondecreasing ts. Reference: reports/M1_NET.md section 9, network/domain.py docstring.
"""
from typing import List

import numpy as np
import pandas as pd

from common.evidence import Evidence
from network.domain import RAW_COLUMNS, WINDOWS, NetworkDomain
from system.runner import Runner

W_MAX = max(WINDOWS.values())          # minutes, longest window of the stack (net.trw)


class NetworkRunner(Runner):
    domain = "network"
    name = "network.runner"
    status = "frozen"
    period_s = 0.001                   # v2 reference ~1 ms per flow

    def __init__(self, dom: NetworkDomain, bus=None, per_layer=False):
        super().__init__(bus)
        self.dom, self.per_layer = dom, per_layer
        self._reset("")

    def _reset(self, key):
        self.rows: List[dict] = []
        self.minutes: List[int] = []
        self.done = 0                  # flows [0, done) are emitted
        self.out_of_order = 0
        self.last_t = -np.inf

    def _size(self):
        return len(self.rows)

    @staticmethod
    def _t(ts):
        return float(pd.Timestamp(ts).value / 1e9) if not isinstance(ts, (int, float, np.integer, np.floating)) else float(ts)

    def _score(self, upto, final_all):
        df = pd.DataFrame(self.rows)
        comb, per = self.dom.score_stream(df[[c for c in RAW_COLUMNS if c in df.columns]])
        out = []
        for i in range(self.done, upto):
            e = comb[i]
            if not final_all:
                e.details["final"] = True
            out.append(e)
            if self.per_layer:
                out.extend(per[n][i] for n in sorted(per))
        self.done = upto
        return out

    def _push(self, flow) -> List[Evidence]:
        t = self._t(flow["ts"])
        if t < self.last_t:
            self.out_of_order += 1
        self.last_t = max(self.last_t, t)
        self.rows.append(dict(flow))
        m = int(t // 60)
        self.minutes.append(m)
        closed_end = (m // W_MAX) * W_MAX
        upto = int(np.searchsorted(np.asarray(self.minutes), closed_end, side="left"))     # flows of closed bins (minutes are nondecreasing)
        if upto > self.done:
            return self._score(upto, False)
        return []

    def _flush(self) -> List[Evidence]:
        if len(self.rows) > self.done:
            return self._score(len(self.rows), True)
        return []
