"""Tests for system/bus.py and system/runner.py (WP7 S1): Evidence bus order / subscriptions / delay, Runner contract (reset, push, flush, latency log,
status labels), evidence comparison helpers."""
import time

from common.evidence import Evidence
from system.bus import EvidenceBus
from system.runner import LatencyLog, Runner, compare_sequences, same_evidence


def ev(domain="gps", layer="combined", t=0.0, score=0.1, alarm=False, sid=""):
    return Evidence(domain=domain, layer=layer, name=f"{domain}.x", t=t, score=score, alarm=alarm, reason="r" if alarm else "", details={}, sample_id=sid)


class Echo(Runner):
    domain, name, status = "gps", "echo", "frozen"

    def _reset(self, key):
        self.seen = []

    def _push(self, s):
        self.seen.append(s)
        return [ev(t=float(s), sid=f"{self.key}/{len(self.seen) - 1}")] if s % 2 == 0 else []

    def _flush(self):
        return [ev(t=99.0, sid="last")]

    def _size(self):
        return len(self.seen)


class Interim(Echo):
    status = "interim"


def test_bus_order_subscribe_and_delay():
    bus = EvidenceBus()
    got = []
    bus.subscribe(got.append, domain="can")
    bus.publish(ev("gps", t=5.0), "a")
    bus.publish(ev("can", t=1.0), "b", status="interim")
    bus.publish(ev("can", t=3.0, alarm=True), "b")
    assert [r.evidence.t for r in bus.merged()] == [1.0, 3.0, 5.0]
    assert [r.seq for r in bus.records] == [0, 1, 2]
    assert len(got) == 2 and all(r.evidence.domain == "can" for r in got)
    assert bus.counts()[("can", "combined")] == 2 and len(bus.by_domain("gps")) == 1
    assert bus.latest("can").evidence.t == 3.0 and len(bus.alarms()) == 1
    assert [r.evidence.t for r in bus.since(3.0)] == [3.0, 5.0]
    r = bus.publish(ev(t=0.0), "x", ingest_ns=time.perf_counter_ns() - 2_000_000)
    assert r.delay_ms >= 2.0 and r.wall_ns >= r.ingest_ns
    assert bus.to_dicts()[0]["evidence"]["domain"] in ("gps", "can")


def test_runner_contract_reset_flush_latency_bus():
    bus = EvidenceBus()
    r = Echo(bus)
    out = r.run([0, 1, 2, 3, 4], key="k1")
    assert [e.sample_id for e in out] == ["k1/0", "k1/2", "k1/4", "last"]
    assert len(bus.records) == 4 and all(rec.runner == "echo" and rec.status == "frozen" for rec in bus.records)
    s = r.latency.summary()
    assert s["all_calls"]["n"] == 5 and s["emitting_calls"]["n"] == 3 and s["silent_calls"]["n"] == 2   # flush is not a timed sample
    assert r.latency.size == [0, 1, 2, 3, 4]
    r.reset("k2")
    assert r.seen == [] and r.key == "k2"
    out2 = r.run([0], flush=False)
    assert out2[0].sample_id == "k2/0"


def test_interim_status_label_in_every_evidence():
    out = Interim().run([0, 2], key="x")
    assert all(e.details.get("status") == "interim" for e in out)
    assert all("status" not in e.details for e in Echo().run([0, 2], key="x"))


def test_compare_sequences_detects_each_kind_of_difference():
    a = [ev(t=1.0, score=0.5, alarm=False, sid="s0"), ev(t=2.0, score=0.9, alarm=True, sid="s1")]
    assert compare_sequences(a, [ev(t=1.0, score=0.5, sid="s0"), ev(t=2.0, score=0.9, alarm=True, sid="s1")])["identical"]
    b = [ev(t=1.0, score=0.5 + 1e-12, sid="s0"), ev(t=2.0, score=0.9, alarm=True, sid="s1")]
    assert compare_sequences(a, b)["identical"] and not compare_sequences(a, b, tol=1e-15)["identical"]
    c = [ev(t=1.0, score=0.5, sid="s0"), ev(t=2.0, score=0.9, alarm=False, sid="s1")]
    r = compare_sequences(a, c)
    assert not r["identical"] and r["alarm_mismatches"] == 1 and r["first_mismatch"]["sample_id"] == "s1"
    assert not compare_sequences(a, a[:1])["same_count"]
    d = ev(t=2.0, score=0.9, alarm=True, sid="s1")
    d.reason = "other"
    assert same_evidence(a[1], d) == (False, "reason differs")


def test_latency_stats_percentiles():
    ms = list(range(1, 101))
    st = LatencyLog.stats(ms)
    assert st["n"] == 100 and abs(st["median_ms"] - 50.5) < 1e-9 and st["p99_ms"] > st["p95_ms"] > st["median_ms"] and st["max_ms"] == 100
    assert LatencyLog.stats([]) == {"n": 0}
