"""WP7 S1 shared helpers for the stream-vs-batch tools: paths, JSON dump, latency repetition summaries, latency growth with context size.
Machine caveat (RULES: loaded by other workers): every latency is measured in `reps` repetitions; the spread across repetitions is reported next to the pooled numbers.
"""
import json
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np

OUT = ROOT / "results" / "WP7"
OUT.mkdir(parents=True, exist_ok=True)


def dump(obj, name):
    def conv(o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))
    (OUT / name).write_text(json.dumps(obj, indent=1, default=conv))


def machine():
    import os
    return {"python": platform.python_version(), "cpu_count": os.cpu_count(), "platform": platform.platform(), "note": "shared machine, other workers running; numbers are an upper envelope of the quiet-machine values"}


def pooled(ns_lists, emit_lists=None, only_emitting=False):
    """Pooled stats (ms) over several repetitions of per-call durations in ns (optionally only calls that emitted a result)."""
    from system.runner import LatencyLog
    ms = []
    for k, ns in enumerate(ns_lists):
        a = np.asarray(ns, float) / 1e6
        if only_emitting and emit_lists is not None:
            a = a[np.asarray(emit_lists[k]) > 0]
        ms.append(a)
    allv = np.concatenate(ms) if ms else np.zeros(0)
    per = [LatencyLog.stats(a) for a in ms]
    out = {"pooled": LatencyLog.stats(allv), "per_repetition": per}
    for key in ("median_ms", "p95_ms", "p99_ms"):
        v = [p[key] for p in per if p.get("n")]
        out[f"spread_{key}"] = {"min": float(min(v)), "max": float(max(v))} if v else None
    return out


def growth(size_lists, ns_lists, emit_lists=None, only_emitting=False, nbins=4):
    """Median latency (ms) by quantile bin of the context size (samples already in the stream when the call started)."""
    s = np.concatenate([np.asarray(x, float) for x in size_lists])
    t = np.concatenate([np.asarray(x, float) for x in ns_lists]) / 1e6
    if only_emitting and emit_lists is not None:
        e = np.concatenate([np.asarray(x) for x in emit_lists])
        s, t = s[e > 0], t[e > 0]
    if len(s) < 2 * nbins:
        return None
    q = np.unique(np.quantile(s, np.linspace(0, 1, nbins + 1)))
    out = []
    for lo, hi in zip(q[:-1], q[1:]):
        m = (s >= lo) & (s <= hi if hi == q[-1] else s < hi)
        if m.any():
            out.append({"size_from": float(lo), "size_to": float(hi), "n": int(m.sum()), "median_ms": float(np.median(t[m])), "p95_ms": float(np.percentile(t[m], 95))})
    return out


def merge(cmps):
    """Merge compare_sequences() results (or earlier merges) into one summary."""
    ident = lambda c: c.get("identical", c.get("all_identical"))
    n = lambda c: c.get("n_stream", c.get("n_evidence", 0))
    return {"n_units": len(cmps), "n_evidence": int(sum(n(c) for c in cmps)), "all_identical": all(ident(c) for c in cmps),
            "mismatches": int(sum(c["mismatches"] for c in cmps)), "alarm_mismatches": int(sum(c["alarm_mismatches"] for c in cmps)),
            "reason_mismatches": int(sum(c["reason_mismatches"] for c in cmps)), "max_abs_score_diff": float(max(c["max_abs_score_diff"] for c in cmps)),
            "first_mismatch": next((c["first_mismatch"] for c in cmps if c["first_mismatch"]), None)}
