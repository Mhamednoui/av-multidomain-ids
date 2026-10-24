"""WP7 S1 V2X: streaming (system/v2x_runner.py, one received message at a time) vs the BATCH physics-only domain (V2XPhysicsDomain.score_table on the whole block table) on VeReMi
VALIDATION time blocks (groups 1, 3, 4, 6 of results/WP5/splits_veremi.json 'val'; held-out types 6 / 12 / 17 removed like WP5 S6; messages sorted by time).
A1 exactness (combined + 12 per-check Evidence), A2 causality by truncation (batch and stream), A3 reset, A4 latency (3 repetitions, block 4). No test message is read.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_v2x.py     Output: results/WP7/S1_v2x.json
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np

from v2x import splitting
import WP5_S5_dev as dev5
from system.runner import compare_sequences
from system.v2x_runner import HELDOUT, V2XPhysicsDomain, V2XRunner

BLOCKS = ["1", "3", "4", "6"]
LAT_BLOCK = "4"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


merge = L.merge


def records(df):
    return df.to_dict("records")


def main():
    v, sp = dev5.load_frames()
    va = splitting.rows_of(v, sp["val"])
    va = va[~va["label"].isin(HELDOUT)]
    dom = V2XPhysicsDomain.load(L.OUT / "frozen_v2x")
    blocks = {b: va[va["group"] == b].sort_values("t", kind="stable").reset_index(drop=True) for b in BLOCKS}
    log("blocks", {b: len(x) for b, x in blocks.items()})
    names = ["combined"] + [None] * 12
    comb_c, lay_c, info, batch = [], [], [], {}
    run = V2XRunner(dom, per_layer=True)
    for b, df in blocks.items():
        ev = dom.score_table(df, per_layer=True)
        batch[b] = ev
        out = run.run(records(df), key=b)
        s_comb, b_comb = out[0::13], ev[0::13]
        comb_c.append(compare_sequences(s_comb, b_comb))
        lay_c.append(merge([compare_sequences(out[1 + j::13], ev[1 + j::13]) for j in range(12)]))
        lab = df["label"].to_numpy()
        info.append({"block": b, "messages": len(df), "classes_present": sorted(int(c) for c in set(lab) if c > 0), "n_attack_msgs": int((lab > 0).sum()),
                     "alarms": int(sum(e.alarm for e in b_comb)), "identical_combined": comb_c[-1]["identical"], "identical_layers": lay_c[-1]["all_identical"],
                     "tie_events": run.tie_events, "out_of_order": run.out_of_order, "ctx_rows_median": float(np.median(run.n_ctx_rows)), "ctx_rows_max": int(max(run.n_ctx_rows)),
                     "max_abs_score_diff": comb_c[-1]["max_abs_score_diff"], "first_mismatch": comb_c[-1]["first_mismatch"]})
        log("A1 block", b, info[-1])
    classes = sorted({c for i in info for c in i["classes_present"]})
    a1 = {"combined": merge(comb_c), "per_layer": merge(lay_c), "blocks": info, "attack_classes_in_blocks": classes, "n_classes": len(classes)}
    # ---- A2 truncation ----
    a2 = {"batch_prefix_equals_batch_full": [], "stream_prefix_equals_stream_full": []}
    for b in ("4", "6"):
        df = blocks[b]
        n = len(df)
        full_stream = V2XRunner(dom, per_layer=False).run(records(df), key=b)
        for frac in (0.25, 0.5, 0.85):
            k = int(frac * n)
            evk = dom.score_table(df.iloc[:k].reset_index(drop=True))
            a2["batch_prefix_equals_batch_full"].append({"block": b, "messages": k, **compare_sequences(evk, batch[b][0::13][:k])})
            outk = V2XRunner(dom, per_layer=False).run(records(df.iloc[:k]), key=b)
            a2["stream_prefix_equals_stream_full"].append({"block": b, "messages": k, **compare_sequences(outk, full_stream[:k])})
    allc = a2["batch_prefix_equals_batch_full"] + a2["stream_prefix_equals_stream_full"]
    a2["all_identical"] = all(c["identical"] for c in allc)
    a2["n_checks"] = len(allc)
    log("A2", a2["all_identical"])
    # ---- A3 reset ----
    r1 = V2XRunner(dom, per_layer=False)
    r1.run(records(blocks["1"]), key="A")
    after = r1.run(records(blocks["3"]), key="B")
    fresh = V2XRunner(dom, per_layer=False).run(records(blocks["3"]), key="B")
    a3 = compare_sequences(after, fresh)
    log("A3", a3["identical"])
    # ---- A4 latency ----
    ns, em, sz, ctx = [], [], [], []
    for rep in range(3):
        rr = V2XRunner(dom, per_layer=False)
        rr.run(records(blocks[LAT_BLOCK]), key=LAT_BLOCK)
        ns.append(list(rr.latency.ns)), em.append(list(rr.latency.emit)), sz.append(list(rr.latency.size)), ctx.append(list(rr.n_ctx_rows))
        log("latency rep", rep, f"median {np.median(ns[-1]) / 1e6:.1f} ms")
    lat = L.pooled(ns, em)
    lat["by_messages_so_far"] = L.growth(sz, ns)
    lat["by_context_rows"] = L.growth(ctx, ns)
    lat["block"], lat["messages"] = LAT_BLOCK, len(blocks[LAT_BLOCK])
    lat["message_period_s"] = 0.1
    lat["p99_below_period"] = bool(lat["pooled"]["p99_ms"] < 100.0)
    lat["v2_reference"] = "none (V2X is new in v3)"
    lat["note"] = "context table (own track + last-second traffic + births) re-scored with the frozen raw-score code per message; per_layer=False"
    res = {"data": {"split": "VeReMi validation blocks " + ",".join(BLOCKS), "domain": "physics-only L1+L2+L3, combiner max, fitted on VeReMi validation"},
           "A1_exactness": a1, "A2_causality_truncation": a2, "A3_reset": a3, "A4_latency": lat, "machine": L.machine(), "seconds": time.time() - T0}
    L.dump(res, "S1_v2x.json")
    log("done")


if __name__ == "__main__":
    main()
