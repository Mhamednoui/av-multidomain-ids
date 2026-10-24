"""CANRunner: streaming wrapper of the FROZEN CAN domain (can/domain.py CanDomain, results/WP2/s7_domain), one frame at a time (WP7 S1).

Purpose: feed CAN frames (t, arbitration id, dlc, 8 payload bytes) in recorded order; the runner emits the combined Evidence (+ per-layer Evidence) of every 1 s
window once its second has passed (a window is the integer second of the running-max clock), and the one-per-second wheel-speed MotionEstimate (source "can", pop_motion()).
State: all frames of the current capture; reset(capture) clears it.
How: the frozen layers (L1 specification rules, L3c per-signal predictors, L3d reverse-light rule) work on whole captures with a 0.05 s sample-and-hold grid; they are
causal but have no incremental entry point. When the first frame of second s+1 arrives, the runner re-scores the PREFIX (all frames so far) with the frozen code and
emits the windows with second <= s that were not emitted yet; flush() scores the whole buffer and emits the rest (including the last partial window, as the batch
code does on a whole capture). Stream = batch is tested (tests/system, tools/WP7_S1_can.py). Cost: one prefix re-score per second of traffic (grows with the capture length);
a push that does not complete a window only appends the frame (microseconds).
MotionEstimates: from the prefix, strictly before the current running-max time (a frame with equal timestamp could still arrive); flush emits the remaining ones.
Sample: tuple/list (t, id, dlc, payload8) or a mapping with keys t, id, dlc, B. Output: list[Evidence]: [combined, L1, L3c, L3d] per emitted window.
Reference: notes/WP2_brief.md "Frozen CAN domain output"; reports/M1_CAN.md section 9.
"""
from typing import List

import numpy as np

from common.evidence import Evidence
from can.domain import CanDomain
from system.runner import Runner


class _Frames:
    """Growing frame arrays (amortised O(1) append)."""

    def __init__(self, cap=4096):
        self.n = 0
        self.t = np.empty(cap)
        self.id = np.empty(cap, np.int64)
        self.dlc = np.empty(cap, np.int64)
        self.B = np.empty((cap, 8), np.uint8)

    def append(self, t, i, dlc, b):
        if self.n == len(self.t):
            c = 2 * self.n
            self.t, self.id, self.dlc = (np.resize(a, c) for a in (self.t, self.id, self.dlc))
            self.B = np.resize(self.B, (c, 8))
        self.t[self.n], self.id[self.n], self.dlc[self.n] = t, i, dlc
        self.B[self.n] = b
        self.n += 1

    def view(self):
        n = self.n
        return self.t[:n], self.id[:n], self.dlc[:n], self.B[:n]


class CANRunner(Runner):
    domain = "can"
    name = "can.runner"
    status = "frozen"
    period_s = 1.0

    def __init__(self, folder, bus=None, per_layer=True, explain=True):
        super().__init__(bus)
        self.dom = CanDomain.load(folder)
        self.per_layer, self.explain = per_layer, explain
        self._reset("")

    def _reset(self, key):
        self.fr = _Frames()
        self.tm = -np.inf
        self.sec = None              # integer second of the latest frame (running-max clock)
        self.done = -10 ** 9         # windows with second <= done are emitted
        self.done_me = -np.inf       # MotionEstimates with t <= done_me are emitted
        self.motion: List = []

    def _size(self):
        return self.fr.n

    @staticmethod
    def _unpack(sample):
        if isinstance(sample, dict):
            return float(sample["t"]), int(sample["id"]), int(sample["dlc"]), sample["B"]
        t, i, dlc, b = sample
        return float(t), int(i), int(dlc), b

    def _emit(self, upto_sec, final=False) -> List[Evidence]:
        t, ids, dlc, B = self.fr.view()
        name = self.key or "capture"
        comb, per = self.dom.score_capture(t, ids, dlc, B, name=name, explain=self.explain)
        out = []
        pref = name + "/"
        for j, e in enumerate(comb):
            s = int(e.sample_id[len(pref):])
            if s > self.done and (final or s <= upto_sec):
                out.append(e)
                if self.per_layer:
                    out.extend(per[l][j] for l in self.dom.layers)
        if comb:
            last = max(int(e.sample_id[len(pref):]) for e in comb)
            self.done = max(self.done, last if final else min(upto_sec, last))
        # wheel-speed MotionEstimates from the same prefix (strictly before the running-max time unless final)
        for m in self.dom.motion_estimates(t, ids, dlc, B):
            if m.t > self.done_me and (final or m.t < self.tm):
                self.motion.append(m)
                self.done_me = m.t
        return out

    def _push(self, sample) -> List[Evidence]:
        t, i, dlc, b = self._unpack(sample)
        self.fr.append(t, i, dlc, b)
        self.tm = max(self.tm, t)
        sec = int(np.floor(self.tm))
        out = []
        if self.sec is not None and sec > self.sec:
            out = self._emit(sec - 1)
        self.sec = sec
        return out

    def _flush(self) -> List[Evidence]:
        if self.fr.n == 0:
            return []
        return self._emit(None, final=True)

    def pop_motion(self):
        out, self.motion = self.motion, []
        return out
