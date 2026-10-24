"""Tests for system/net_runner.py (WP7 S1b): window semantics (a flow is emitted when a later 5-minute bin starts), stream == batch, truncation, reset, flush, per-layer output,
with a stand-in domain whose score depends on the whole 5-minute bin (like net.trw); plus the FROZEN D10 domain on a small validation slice (skipped when the stage cache is absent)."""
import numpy as np
import pandas as pd

from common.evidence import Evidence
from system.net_runner import W_MAX, NetworkRunner
from system.runner import compare_sequences


class Stand:
    """score of a flow = number of flows in its 5-minute bin / 100 (needs the whole bin: not sample-causal); alarm if > 0.2; final as network.domain.final_mask."""

    def score_stream(self, flows):
        t = flows["ts"].to_numpy(float)
        minute = (t // 60).astype(int)
        bin_ = minute // W_MAX
        cnt = pd.Series(bin_).map(pd.Series(bin_).value_counts()).to_numpy()
        end = (minute.max() // W_MAX) * W_MAX
        comb = [Evidence("network", "combined", "network.combined", float(t[i]), float(cnt[i]) / 100, bool(cnt[i] > 20), "r" if cnt[i] > 20 else "", {"final": bool(minute[i] < end)}, str(i))
                for i in range(len(t))]
        per = {"net.x": [Evidence("network", "L2a", "net.x", float(t[i]), float(cnt[i]) / 100, bool(cnt[i] > 20), "", {}, str(i)) for i in range(len(t))]}
        return comb, per


def _flows(n=400, seed=0):
    r = np.random.default_rng(seed)
    t = np.sort(1.0e9 + r.uniform(0, 1500, n))              # 25 minutes -> 5 bins of 5 minutes
    return [{"ts": float(x)} for x in t]


def test_stream_equals_batch_and_emission_follows_closed_bins():
    fl = _flows()
    run = NetworkRunner(Stand())
    got, first_emit = [], None
    for i, f in enumerate(fl):
        out = run.push(f)
        if out and first_emit is None:
            first_emit = i
        got.extend(out)
        # nothing is emitted for a flow whose 5-minute bin is still open
        assert all(int(e.t // 60) < (int(f["ts"] // 60) // W_MAX) * W_MAX for e in out)
    got.extend(run.flush())
    batch, _ = Stand().score_stream(pd.DataFrame(fl))
    c = compare_sequences(got, batch, tol=0.0)
    assert c["identical"], c
    assert first_emit is not None and first_emit > 20 and len(got) == len(fl)
    assert [e.sample_id for e in got] == [str(i) for i in range(len(fl))]
    assert all(e.details["final"] for e in got[: first_emit])


def test_truncation_reset_and_per_layer():
    fl = _flows(300, 1)
    full = NetworkRunner(Stand()).run(fl, key="a")
    for k in (60, 150, 270):
        part = NetworkRunner(Stand()).run(fl[:k], key="a", flush=False)
        assert compare_sequences(part, full[:len(part)], tol=0.0)["identical"]
    r = NetworkRunner(Stand(), per_layer=True)
    r.run(_flows(100, 5), key="other")
    out = r.run(fl, key="a")
    assert len(out) == 2 * len(fl) and compare_sequences(out[0::2], full, tol=0.0)["identical"]
    assert all(e.layer == "L2a" for e in out[1::2])
    assert r.flush() == []


def test_frozen_d10_domain_stream_equals_batch_on_a_small_validation_slice():
    from pathlib import Path
    from common.config import ROOT
    frozen = ROOT / "results" / "WP4" / "s7_domain"
    try:
        from tools.WP4_S3_lib import load, stream
        d = load("D10")
    except Exception:
        d = None
    if d is None or not (frozen / "domain.pkl").exists():
        class Skip(Exception):
            pass
        raise Skip("D10 stage cache / frozen network domain not available")
    from network.domain import RAW_COLUMNS, NetworkDomain
    v = stream(d, "val")
    t0 = float(v["t"].min())
    s = v[(v["t"] >= t0 + 3600) & (v["t"] < t0 + 3600 + 1500)].sort_values(["t", "row"], kind="stable").reset_index(drop=True)
    s["src_ip"] = "h" + s["src_id"].astype(str)
    s["dst_ip"] = "h" + s["dst_id"].astype(str)
    dom = NetworkDomain.load(frozen)
    comb, _ = dom.score_stream(s[RAW_COLUMNS])
    out = NetworkRunner(dom).run(s[RAW_COLUMNS].to_dict("records"), key="d10")
    assert len(s) > 200 and compare_sequences(out, comb, tol=1e-9)["identical"]
