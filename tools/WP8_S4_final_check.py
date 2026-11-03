"""WP8 S4: Stream31Final (candidate F1, tick-final emission) on D10 validation: (1) fitted on the benign val stream it reproduces the F1 scores of tools/WP8_S4_eval.py (computed there with the v3 layer classes);
(2) streaming (one flow at a time, Evidence at tick close) == batch on three val slices; (3) per-push compute incl. the tick flush, and the stream-time delay of every flow (emission - flow ts).
Output results/WP8/S4/s4_final_check.json; the fitted object is saved to results/WP8/S4/parts/stream31_F1.pkl. Usage: python -u -W ignore -I tools/WP8_S4_final_check.py [slice_flows]"""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
import WP8_S4_eval as E  # noqa: E402

from network.domain import RAW_COLUMNS, NetworkDomain  # noqa: E402
from network.stream31 import Stream31Final  # noqa: E402


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25000
    v = E.load_val()
    vb = v[(v["fam"] == "BENIGN") & ~v["audit"]].reset_index(drop=True)
    F = Stream31Final.from_frozen(NetworkDomain.load(E.FROZEN))
    F.calibrate(vb)
    s, a, X, raw = F.score_table(v)
    z = np.load(os.path.join(E.SCORES, "network_val.npz"))
    sm = E.summary(a, v)
    out = {"reproduces_F1": {"max_abs_score_diff_vs_eval_F1": float(np.abs(s - z["F1_score"].astype(float)).max()), "alarm_mismatches_vs_eval_F1": int((a != z["F1_alarm"]).sum()),
                             "macro": sm["macro"], "fa": sm["fa"], "combined_threshold": F.comb_thr}, "slices": {}}
    F.save(os.path.join(E.PARTS, "stream31_F1.pkl"))
    lat, delay = [], []
    for day in ("2017-07-04", "2017-07-05", "2017-07-07"):
        sl = v[v["day"].astype(str) == day].iloc[:n].reset_index(drop=True)
        s_b, a_b, _, _ = F.score_table(sl)
        recs = sl.assign(ts=sl["t"], src_ip=sl["src_id"], dst_ip=sl["dst_id"])[RAW_COLUMNS].to_dict("records")
        F.reset()
        got, em = {}, {}
        for r in recs:
            t0 = time.perf_counter()
            ev = F.push(r)
            lat.append(time.perf_counter() - t0)
            for e in ev:
                got[int(e.sample_id)], em[int(e.sample_id)] = e, r["ts"]
        t0 = time.perf_counter()
        for e in F.flush():
            got[int(e.sample_id)], em[int(e.sample_id)] = e, recs[-1]["ts"]
        lat.append(time.perf_counter() - t0)
        d = np.array([em[i] - recs[i]["ts"] for i in range(len(recs))])
        delay += list(d)
        out["slices"][day] = {"flows": len(recs), "all_emitted": sorted(got) == list(range(len(recs))), "max_abs_score_diff_stream_vs_batch": float(max(abs(got[i].score - s_b[i]) for i in range(len(recs)))),
                              "alarm_mismatches": int(sum(got[i].alarm != bool(a_b[i]) for i in range(len(recs)))), "delay_median_s": float(np.median(d)), "delay_max_s": float(d.max())}
        print(day, out["slices"][day], flush=True)
    lat = np.array(lat) * 1e3
    out["push_ms"] = {"n": int(len(lat)), "median": float(np.median(lat)), "p99": float(np.percentile(lat, 99)), "max": float(lat.max())}
    out["delay_s_all_slices"] = {"median": float(np.median(delay)), "max": float(np.max(delay))}
    json.dump(out, open(os.path.join(E.OUT, "s4_final_check.json"), "w"), indent=1)
    print(out["reproduces_F1"], out["push_ms"], out["delay_s_all_slices"], flush=True)


if __name__ == "__main__":
    main()
