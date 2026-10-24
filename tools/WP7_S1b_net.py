"""WP7 S1b network: streaming (system/net_runner.py, one flow at a time) vs the frozen BATCH NetworkDomain.score_stream (stack H, results/WP4/s7_domain) on D10 VALIDATION flows:
four 30-minute slices of the validation stream (the ones with the most distinct traffic families, <= 20,000 flows; the choice uses family labels only, no scores).
A1 exactness (combined + per-layer Evidence), A2 causality by truncation (batch and stream), A3 reset, A4 latency (3 repetitions; per push, per emitting push, amortised per flow),
A5/A6 not repeated here. The D10 test split is never read. Addresses of the stage table are dense ids; they are turned into strings (the domain groups by address only).
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1b_net.py     Output: results/WP7/S1b_net.json
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np

from network.domain import RAW_COLUMNS, NetworkDomain
from system.net_runner import NetworkRunner
from system.runner import compare_sequences
from tools.WP4_S3_lib import load, stream

FROZEN = L.ROOT / "results" / "WP4" / "s7_domain"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def flows_of(df):
    return df[RAW_COLUMNS].to_dict("records")


def per_pairs(per_s, per_b, names):
    return [compare_sequences(per_s[n], per_b[n]) for n in names]


def main():
    dom = NetworkDomain.load(FROZEN)
    d = load("D10")
    v = stream(d, "val")
    del d
    v["src_ip"] = "h" + v["src_id"].astype(str)
    v["dst_ip"] = "h" + v["dst_id"].astype(str)
    b = (v["t"] // 1800).astype(int)
    g = v.groupby(b).agg(n=("t", "size"), fams=("family", "nunique"))
    g = g[g["n"] <= 20000].sort_values(["fams", "n"], ascending=[False, False])
    keys = list(g.index[:4])
    slices = {}
    for k in keys:
        s = v[b == k].sort_values(["t", "row"], kind="stable").reset_index(drop=True)
        slices[int(k)] = s
    log("slices", {k: (len(s), s["family"].value_counts()[lambda x: x > 0].to_dict()) for k, s in slices.items()})
    run = NetworkRunner(dom, per_layer=True)
    comb_c, lay_c, info, batch = [], [], [], {}
    for k, s in slices.items():
        fl = flows_of(s)
        comb, per = dom.score_stream(s[RAW_COLUMNS])
        batch[k] = (comb, per)
        out = run.run(fl, key=str(k))
        names = sorted(per)
        n = 1 + len(names)
        s_comb, s_per = out[0::n], {nm: out[1 + j::n] for j, nm in enumerate(names)}
        comb_c.append(compare_sequences(s_comb, comb))
        lay_c.append(L.merge(per_pairs(s_per, per, names)))
        fin = [e.details["final"] for e in comb]
        info.append({"slice": k, "flows": len(s), "families": {f: int(c) for f, c in s["family"].value_counts().items() if c > 0}, "alarms": int(sum(e.alarm for e in comb)),
                     "batch_final_flows": int(sum(fin)), "identical_combined": comb_c[-1]["identical"], "identical_layers": lay_c[-1]["all_identical"],
                     "max_abs_score_diff": comb_c[-1]["max_abs_score_diff"], "out_of_order": run.out_of_order})
        log("A1 slice", k, info[-1])
    a1 = {"combined": L.merge(comb_c), "per_layer": L.merge(lay_c), "slices": info, "n_flows": int(sum(i["flows"] for i in info)), "n_families": len({f for i in info for f in i["families"]})}
    # ---- A2 truncation ----
    a2 = {"batch_prefix_final_flows_equal_batch_full": [], "stream_prefix_equals_stream_full": []}
    for k in list(slices)[:2]:
        s = slices[k]
        fl = flows_of(s)
        full = NetworkRunner(dom).run(fl, key=str(k))
        for frac in (0.3, 0.6, 0.9):
            m = int(frac * len(s))
            combk, _ = dom.score_stream(s.iloc[:m][RAW_COLUMNS])
            nfin = int(sum(e.details["final"] for e in combk))
            a2["batch_prefix_final_flows_equal_batch_full"].append({"slice": k, "flows": m, "final_flows_compared": nfin, **compare_sequences(combk[:nfin], batch[k][0][:nfin])})
            outk = NetworkRunner(dom).run(fl[:m], key=str(k), flush=False)
            a2["stream_prefix_equals_stream_full"].append({"slice": k, "flows": m, "emitted": len(outk), **compare_sequences(outk, full[:len(outk)])})
    allc = [c for key in a2 for c in a2[key]]
    a2["all_identical"] = all(c["identical"] for c in allc)
    a2["n_checks"] = len(allc)
    a2["min_delay_note"] = "Evidence is emitted when a flow of a later 5-minute bin arrives (window semantics of the frozen domain); the delay is flow time, not compute time"
    log("A2", a2["all_identical"])
    # ---- A3 reset ----
    ks = list(slices)
    r1 = NetworkRunner(dom)
    r1.run(flows_of(slices[ks[1]]), key="A")
    after = r1.run(flows_of(slices[ks[0]]), key="B")
    fresh = NetworkRunner(dom).run(flows_of(slices[ks[0]]), key="B")
    a3 = compare_sequences(after, fresh)
    log("A3", a3["identical"])
    # ---- A4 latency ----
    ns, em, sz = [], [], []
    tot_ms, tot_flows = [], 0
    for rep in range(3):
        rr = NetworkRunner(dom)
        t0 = time.perf_counter()
        n_fl = 0
        for k in ks:
            fl = flows_of(slices[k])
            rr.run(fl, key=str(k))
            n_fl += len(fl)
        tot_ms.append((time.perf_counter() - t0) * 1e3)
        tot_flows = n_fl
        ns.append(list(rr.latency.ns)), em.append(list(rr.latency.emit)), sz.append(list(rr.latency.size))
        log("latency rep", rep, f"amortised {tot_ms[-1] / n_fl:.4f} ms/flow")
    lat = {"per_push_all_calls": L.pooled(ns, em), "per_emitting_push": L.pooled(ns, em, only_emitting=True), "emitting_by_buffer_flows": L.growth(sz, ns, em, only_emitting=True),
           "amortised_ms_per_flow_per_repetition": [t / tot_flows for t in tot_ms], "flows_per_repetition": tot_flows, "v2_reference_ms": 1.0,
           "note": "a push that closes a 5-minute bin re-scores the whole buffer of the capture (all four layers of stack H + combiner) and emits all flows of the closed bins; other pushes only append. "
                   "Wall-clock includes the python dict handling of the stream; per-flow v2 ~1 ms."}
    lat["amortised_ms_per_flow_median"] = float(np.median(lat["amortised_ms_per_flow_per_repetition"]))
    res = {"data": {"split": "D10 validation stream, four 30-minute slices", "slices": {str(k): len(s) for k, s in slices.items()}, "domain": "stack H, combiner max (results/WP4/s7_domain)"},
           "A1_exactness": a1, "A2_causality_truncation": a2, "A3_reset": a3, "A4_latency": lat, "machine": L.machine(), "seconds": time.time() - T0}
    L.dump(res, "S1b_net.json")
    log("done")


if __name__ == "__main__":
    main()
