"""Runner: base class of the per-domain streaming runners, and the latency log (WP7 S1).

Purpose: a common interface for "feed one sample, get the Evidence of that sample" over the FROZEN domain detectors, with
  reset(key)  start of a new drive / capture / sender context (all stream state cleared),
  push(sample) -> list[Evidence]  one sample in; 0..n Evidence out (a CAN window is emitted when its second has passed),
  flush() -> list[Evidence]  end of stream (emits what is still pending, e.g. the last partial CAN window), as the batch code does for a whole capture,
  every call timed with perf_counter_ns (LatencyLog) and published on an EvidenceBus when one is attached.
Causality contract: push() sees only the samples pushed so far; the runner never has access to later samples (tested by truncation in tests/system).
Status labels: `status` is "frozen" for frozen domain outputs, "interim" (LiDAR: WP3 S1 v2 baseline), "placeholder" (network until M1-NET); the label is also written
into Evidence.details["status"] of interim / placeholder runners so no downstream consumer can mistake it for a frozen result.
Reference: ARCHITECTURE.md sections 1-3; notes/WP7_system.md (design decision: prefix re-scoring of the frozen causal batch code).
"""
import time
from typing import List, Optional

import numpy as np

from common.evidence import Evidence


class LatencyLog:
    """Wall-clock durations (ns) of push() calls; `emit` marks the calls that produced Evidence (a window / a sample result)."""

    def __init__(self):
        self.ns: List[int] = []
        self.emit: List[int] = []         # number of Evidence (combined layer) returned by that call
        self.size: List[int] = []         # context size when the call started (samples already in the stream), for growth analysis

    def add(self, ns, n_emit, size):
        self.ns.append(ns)
        self.emit.append(n_emit)
        self.size.append(size)

    def clear(self):
        self.ns, self.emit, self.size = [], [], []

    @staticmethod
    def stats(ms):
        a = np.asarray(ms, float)
        if not len(a):
            return {"n": 0}
        return {"n": int(len(a)), "median_ms": float(np.median(a)), "p95_ms": float(np.percentile(a, 95)), "p99_ms": float(np.percentile(a, 99)),
                "mean_ms": float(a.mean()), "max_ms": float(a.max())}

    def summary(self) -> dict:
        ms = np.asarray(self.ns, float) / 1e6
        em = np.asarray(self.emit)
        out = {"all_calls": self.stats(ms)}
        if len(ms) and (em > 0).any():
            out["emitting_calls"] = self.stats(ms[em > 0])
        if len(ms) and (em == 0).any():
            out["silent_calls"] = self.stats(ms[em == 0])
        return out


class Runner:
    domain = "unknown"
    name = "unknown"
    status = "frozen"            # "frozen" | "interim" | "placeholder"
    period_s = 1.0               # nominal period of one sample of this stream (real-time check)
    primary_layer = "combined"   # Evidence.layer that counts as "the" result of a sample (latency 'emitting calls')

    def __init__(self, bus=None):
        self.bus = bus
        self.latency = LatencyLog()
        self.key = ""

    # --- to override -----------------------------------------------------------------------------
    def _reset(self, key):
        raise NotImplementedError

    def _push(self, sample) -> List[Evidence]:
        raise NotImplementedError

    def _flush(self) -> List[Evidence]:
        return []

    def _size(self) -> int:
        return 0

    # --- contract --------------------------------------------------------------------------------
    def reset(self, key=""):
        self.key = key
        self._reset(key)

    def push(self, sample) -> List[Evidence]:
        t0 = time.perf_counter_ns()
        size = self._size()
        out = self._push(sample)
        self._finish(out, t0, size)
        return out

    def flush(self) -> List[Evidence]:
        t0 = time.perf_counter_ns()
        out = self._flush()
        self._finish(out, t0, self._size(), timed=False)
        return out

    def _finish(self, out, t0, size, timed=True):
        t1 = time.perf_counter_ns()
        if self.status != "frozen":
            for e in out:
                e.details["status"] = self.status
        if timed:
            self.latency.add(t1 - t0, sum(1 for e in out if e.layer == self.primary_layer), size)
        if self.bus is not None:
            for e in out:
                self.bus.publish(e, runner=self.name, status=self.status, ingest_ns=t0)

    def run(self, samples, key=None, flush=True) -> List[Evidence]:
        """Convenience: reset (if key given), push every sample, flush; returns all Evidence in emission order."""
        if key is not None:
            self.reset(key)
        out = []
        for s in samples:
            out.extend(self.push(s))
        if flush:
            out.extend(self.flush())
        return out


def same_evidence(a: Evidence, b: Evidence, tol=1e-9):
    """(equal?, reason). Equal = same domain/layer/name/sample_id/t, same alarm and reason, |score diff| <= tol."""
    for f in ("domain", "layer", "name", "sample_id"):
        if getattr(a, f) != getattr(b, f):
            return False, f"{f}: {getattr(a, f)!r} != {getattr(b, f)!r}"
    if abs(a.t - b.t) > 1e-9:
        return False, f"t: {a.t} != {b.t}"
    if a.alarm != b.alarm:
        return False, "alarm differs"
    if a.reason != b.reason:
        return False, "reason differs"
    if abs(a.score - b.score) > tol:
        return False, f"score differs by {abs(a.score - b.score):.3g}"
    return True, ""


def compare_sequences(stream: List[Evidence], batch: List[Evidence], tol=1e-9) -> dict:
    """Compare two Evidence sequences (same order expected). Returns counts and the largest score difference."""
    res = {"n_stream": len(stream), "n_batch": len(batch), "same_count": len(stream) == len(batch), "mismatches": 0, "alarm_mismatches": 0,
           "reason_mismatches": 0, "max_abs_score_diff": 0.0, "first_mismatch": None}
    for a, b in zip(stream, batch):
        ok, why = same_evidence(a, b, tol)
        res["max_abs_score_diff"] = max(res["max_abs_score_diff"], abs(a.score - b.score))
        if not ok:
            res["mismatches"] += 1
            res["alarm_mismatches"] += int(a.alarm != b.alarm)
            res["reason_mismatches"] += int(a.reason != b.reason)
            if res["first_mismatch"] is None:
                res["first_mismatch"] = {"sample_id": a.sample_id, "why": why}
    res["identical"] = bool(res["same_count"] and res["mismatches"] == 0)
    return res
