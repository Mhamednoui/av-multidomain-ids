"""WP8 S4: streaming object checks on REAL D10 validation flows for the selected candidate (RC5 by default; Stream31 saved by tools/WP8_S4_eval.py).
E1 real: three contiguous val slices (days 2017-07-04, 07-05, 07-07; first SLICE flows of the day in arrival order): Stream31.push (one flow at a time, Evidence objects) == Stream31.score_table
(batch path of the same fitted object): max |score diff|, alarm mismatches. N3: per-push compute (perf_counter around push, includes the one-row tcp_flags frame), median / p99 / max, one core.
Causality: scores of the first half of a slice pushed alone equal those of the full run. Output results/WP8/S4/s4_stream_check.json (+ machine load).
Usage: python -u -W ignore -I tools/WP8_S4_stream_check.py [name] [slice_flows]
"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
import WP8_S4_eval as E  # noqa: E402

from network.domain import RAW_COLUMNS  # noqa: E402
from network.stream31 import Stream31  # noqa: E402


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "RC5"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 25000
    S = Stream31.load(os.path.join(E.PARTS, f"stream31_{name}.pkl"))
    v = E.load_val()
    out = {"candidate": name, "slice_flows": n, "slices": {}}
    lat = []
    for day in ("2017-07-04", "2017-07-05", "2017-07-07"):
        sl = v[v["day"].astype(str) == day].iloc[:n].reset_index(drop=True)
        s_b, a_b, _, _ = S.score_table(sl)
        recs = sl.assign(ts=sl["t"], src_ip=sl["src_id"], dst_ip=sl["dst_id"])[RAW_COLUMNS].to_dict("records")
        S.reset()
        ev, ts_ = [], []
        for r in recs:
            t0 = time.perf_counter()
            ev.append(S.push(r))
            ts_.append(time.perf_counter() - t0)
        sc = np.array([e.score for e in ev])
        lat += ts_
        S.reset()
        half = [S.push(r).score for r in recs[: len(recs) // 2]]
        fam = sl["fam"].to_numpy()
        out["slices"][day] = {"flows": len(sl), "families": {f: int((fam == f).sum()) for f in sorted(set(fam))}, "max_abs_score_diff_stream_vs_batch": float(np.abs(sc - s_b).max()),
                              "alarm_mismatches": int((np.array([e.alarm for e in ev]) != a_b).sum()), "alarms": int(a_b.sum()),
                              "prefix_equal_full": bool(np.array_equal(np.array(half), sc[: len(half)])), "evidence_t_equals_flow_ts": bool(all(e.t == r["ts"] for e, r in zip(ev, recs)))}
        print(day, out["slices"][day], flush=True)
    lat = np.array(lat) * 1e3
    out["push_ms"] = {"n": int(len(lat)), "median": float(np.median(lat)), "p95": float(np.percentile(lat, 95)), "p99": float(np.percentile(lat, 99)), "max": float(lat.max())}
    out["N3_p99_le_1000ms"] = bool(out["push_ms"]["p99"] <= 1000.0)
    try:
        import psutil
        out["machine"] = {"cpu_percent_system": psutil.cpu_percent(interval=1.0), "cores": os.cpu_count()}
    except Exception:
        out["machine"] = {"cores": os.cpu_count(), "note": "psutil not available; other workers were running (S1 downloads, S3 LiDAR)"}
    out["v3_reference"] = "v3 stall at each bin close: 1.4 s median / 7.7 s max (reports/M3.md, results/WP7/S1b_net.json A4)"
    json.dump(out, open(os.path.join(E.OUT, "s4_stream_check.json"), "w"), indent=1)
    print(out["push_ms"], flush=True)


if __name__ == "__main__":
    main()
