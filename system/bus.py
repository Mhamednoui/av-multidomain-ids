"""EvidenceBus: the common, time-stamped channel every runner publishes its Evidence on (WP7 S1).

Purpose: one place where the Evidence of all domains meets (later: fusion, correlator, response). Every record keeps the STREAM time of the
sample (Evidence.t), the WALL time of publication and the wall time at which the sample entered its runner, so the end-to-end delay of the runtime is measurable.
Inputs: Evidence objects (common.evidence) + the name of the runner. Outputs: ordered records, per-domain views, subscriptions, JSON-friendly dicts.
Order: `merged()` sorts by (stream time, publication sequence); `records` keeps publication order.
No detection logic here.
Reference: ARCHITECTURE.md sections 1-2.
"""
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from common.evidence import Evidence


@dataclass
class BusRecord:
    seq: int                 # publication order
    wall_ns: int             # time.perf_counter_ns() at publication
    ingest_ns: int           # time.perf_counter_ns() when the sample that produced it entered the runner
    runner: str
    evidence: Evidence
    status: str = "frozen"   # "frozen" | "interim" | "placeholder"

    @property
    def delay_ms(self) -> float:
        return (self.wall_ns - self.ingest_ns) / 1e6

    def to_dict(self) -> dict:
        return {"seq": self.seq, "wall_ns": self.wall_ns, "ingest_ns": self.ingest_ns, "runner": self.runner, "status": self.status,
                "delay_ms": self.delay_ms, "evidence": self.evidence.to_dict()}


class EvidenceBus:
    def __init__(self, clock: Callable[[], int] = time.perf_counter_ns):
        self.clock = clock
        self.records: List[BusRecord] = []
        self._subs = []

    def publish(self, ev: Evidence, runner: str = "", status: str = "frozen", ingest_ns: Optional[int] = None) -> BusRecord:
        now = self.clock()
        rec = BusRecord(len(self.records), now, now if ingest_ns is None else ingest_ns, runner, ev, status)
        self.records.append(rec)
        for fn, dom, lay in self._subs:
            if (dom is None or ev.domain == dom) and (lay is None or ev.layer == lay):
                fn(rec)
        return rec

    def subscribe(self, fn: Callable[[BusRecord], None], domain: Optional[str] = None, layer: Optional[str] = None):
        self._subs.append((fn, domain, layer))

    def by_domain(self, domain: str, layer: Optional[str] = None) -> List[BusRecord]:
        return [r for r in self.records if r.evidence.domain == domain and (layer is None or r.evidence.layer == layer)]

    def latest(self, domain: str, layer: str = "combined") -> Optional[BusRecord]:
        for r in reversed(self.records):
            if r.evidence.domain == domain and r.evidence.layer == layer:
                return r
        return None

    def alarms(self, layer: str = "combined") -> List[BusRecord]:
        return [r for r in self.records if r.evidence.layer == layer and r.evidence.alarm]

    def since(self, t: float, layer: Optional[str] = "combined") -> List[BusRecord]:
        return [r for r in self.merged() if r.evidence.t >= t and (layer is None or r.evidence.layer == layer)]

    def merged(self) -> List[BusRecord]:
        return sorted(self.records, key=lambda r: (r.evidence.t, r.seq))

    def counts(self) -> dict:
        out = {}
        for r in self.records:
            k = (r.evidence.domain, r.evidence.layer)
            out[k] = out.get(k, 0) + 1
        return out

    def clear(self):
        self.records.clear()

    def to_dicts(self) -> list:
        return [r.to_dict() for r in self.merged()]
