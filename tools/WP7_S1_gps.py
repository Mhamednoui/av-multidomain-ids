"""WP7 S1 GPS: streaming (system/gps_runner.py) vs the frozen BATCH GPSDomain on the 210 VALIDATION runs of KITTI drives 0011, 0035, 0027 (clean + 6 attack types, v2/new attacks of gps/stream.py).
A1 exactness of combined + 16 per-layer Evidence, A2 causality by truncation (batch prefix == batch full, stream prefix == stream full), A3 reset, A4 latency (3 repetitions on a subset).
No test drive is read. Input: the WP1 stream pickle (temp folder, read only; rebuilt identically by tools/WP1_S4_lib.kitti_stream if absent) + cached LiDAR odometry (results/WP1/cache).
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_gps.py     Output: results/WP7/S1_gps.json
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np
import pandas as pd

import WP1_S4_lib as W1
from gps import domain as GD
from gps import lidar_odom as LO
from system.gps_runner import INPUT_COLUMNS, GPSRunner
from system.runner import compare_sequences

FROZEN = L.ROOT / "results" / "WP1" / "frozen_gps"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


merge = L.merge


def samples(df):
    cols = [c for c in INPUT_COLUMNS if c in df.columns]
    return df[cols].to_dict("records")


def main():
    kx = W1.kitti_stream()
    val = kx[kx["part"] == "val"].copy()
    val = val.join(LO.stream_features(val))
    runs = [g.reset_index(drop=True) for _, g in val.groupby("run", sort=False)]
    log("val runs", len(runs), "fixes", len(val), "attacks", sorted(val["attack"].unique()))
    dom = GD.GPSDomain.load(FROZEN)
    run = GPSRunner(FROZEN)
    # ---- A1 exactness ----
    comb_cmp, layer_cmp = [], []
    batch_cache = {}
    for i, r in enumerate(runs):
        ev, per = dom.score(GD.prepare(r, lidar=True), with_layers=True)
        batch_cache[i] = (ev, per)
        out = run.run(samples(r), key=str(r["run"].iloc[0]))
        n = len(dom.names) + 1
        s_comb, s_lay = out[0::n], {nm: out[1 + j::n] for j, nm in enumerate(dom.names)}
        comb_cmp.append(compare_sequences(s_comb, ev))
        layer_cmp.append(merge([compare_sequences(s_lay[nm], per[nm]) for nm in dom.names]))
        if i % 30 == 0:
            log("A1 run", i, "identical so far", all(c["identical"] for c in comb_cmp))
    a1 = {"combined": merge(comb_cmp), "per_layer": merge(layer_cmp), "alarms_in_val_runs": int(sum(e.alarm for ev, _ in batch_cache.values() for e in ev))}
    log("A1", a1["combined"]["all_identical"], a1["per_layer"]["all_identical"], a1["combined"]["max_abs_score_diff"])
    # ---- A2 truncation ----
    rng = np.random.default_rng(7)
    pick = rng.choice(len(runs), 12, replace=False)
    a2 = {"batch_prefix_equals_batch_full": [], "stream_prefix_equals_stream_full": []}
    for i in pick:
        r = runs[i]
        ev_full, per_full = batch_cache[i]
        n = len(r)
        for k in sorted({5, n // 2, n - 3}):
            evk, _ = dom.score(GD.prepare(r.iloc[:k].copy(), lidar=True), with_layers=True)
            a2["batch_prefix_equals_batch_full"].append({"run": r["run"].iloc[0], "k": k, **compare_sequences(evk, ev_full[:k])})
            fresh = GPSRunner(FROZEN, per_layer=False)
            outk = fresh.run(samples(r.iloc[:k]), key="trunc", flush=True)
            outf = GPSRunner(FROZEN, per_layer=False).run(samples(r), key="trunc")
            a2["stream_prefix_equals_stream_full"].append({"run": r["run"].iloc[0], "k": k, **compare_sequences(outk, outf[:k])})
    a2["all_identical"] = all(c["identical"] for key in ("batch_prefix_equals_batch_full", "stream_prefix_equals_stream_full") for c in a2[key])
    a2["n_checks"] = len(a2["batch_prefix_equals_batch_full"]) + len(a2["stream_prefix_equals_stream_full"])
    log("A2", a2["all_identical"])
    # ---- A3 reset ----
    ra, rb = runs[pick[0]], runs[pick[1]]
    r1 = GPSRunner(FROZEN)
    r1.run(samples(ra), key="A")
    after = r1.run(samples(rb), key="B")
    fresh = GPSRunner(FROZEN).run(samples(rb), key="B")
    a3 = compare_sequences(after, fresh)
    log("A3", a3["identical"])
    # ---- A4 latency ----
    sub = runs[::7][:30]
    ns, em, sz = [], [], []
    for rep in range(3):
        rr = GPSRunner(FROZEN)
        for r in sub:
            rr.run(samples(r), key=str(r["run"].iloc[0]))
        ns.append(list(rr.latency.ns)), em.append(list(rr.latency.emit)), sz.append(list(rr.latency.size))
        log("latency rep", rep, f"median {np.median(ns[-1]) / 1e6:.1f} ms")
    lat = L.pooled(ns, em)
    lat["by_context_size"] = L.growth(sz, ns)
    lat["n_runs"] = len(sub)
    lat["fix_period_s"] = 1.0
    lat["p99_below_period"] = bool(lat["pooled"]["p99_ms"] < 1000.0)
    lat["v2_reference_ms"] = 0.8
    lat["note"] = "prefix re-score of the frozen batch code per fix (16 layers); runs of the KITTI stream have 13-25 fixes, longer drives cost more per fix (see by_context_size)"
    res = {"data": {"split": "KITTI validation drives 0011 0035 0027", "n_runs": len(runs), "n_fixes": int(len(val)), "attacks": sorted(val["attack"].unique())},
           "A1_exactness": a1, "A2_causality_truncation": a2, "A3_reset": a3, "A4_latency": lat, "machine": L.machine(), "seconds": time.time() - T0}
    L.dump(res, "S1_gps.json")
    log("done")


if __name__ == "__main__":
    main()
