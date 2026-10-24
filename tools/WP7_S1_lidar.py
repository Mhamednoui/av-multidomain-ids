"""WP7 S1 LiDAR (INTERIM runner = WP3 S1 retrained v2 baseline): streaming scan by scan (system/placeholder_runners.py LidarInterimRunner, raw KITTI velodyne files)
vs the frozen BATCH rows of the WP3 S1 cache (train4, cls Normal: 429-dim descriptors built by lidar/build.py, scored by the same XGBoost model and ECDF) on VALIDATION drives 0011 and 0035.
A1 exactness: features max |diff| and Evidence score <= 1e-6, alarms identical; A2 truncation; A3 reset; A4 latency (3 repetitions). Test drives are never read.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_lidar.py     Output: results/WP7/S1_lidar.json
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np
import pandas as pd

from lidar.data import CACHE, group_id, load, scan_files
from lidar.features import feature_names_temporal
from system.placeholder_runners import LidarInterimModel, LidarInterimRunner
from system.runner import compare_sequences

DRIVES = ["0011", "0035"]
N_SCANS = 18
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def scans(d, n=N_SCANS):
    files = scan_files(d)[:n]
    return [{"points": load(f), "t": 0.1032 * k, "sample_id": group_id(d, f)} for k, f in enumerate(files)]


def main():
    m = LidarInterimModel(CACHE / "retrained_deployed.json").load_calibration(L.OUT / "frozen_lidar_interim" / "calibration.json")
    run = LidarInterimRunner(m)
    names = feature_names_temporal()
    # ---- A1 ----
    feat_diff, score_diff, alarm_mis, n, nalarm = 0.0, 0.0, 0, 0, 0
    per_drive = []
    streams = {}
    for d in DRIVES:
        p = pd.read_pickle(CACHE / "train4" / f"{d}.pkl")
        keep = (p["meta"]["cls"] == "Normal").to_numpy()
        meta, X = p["meta"][keep].reset_index(drop=True), p["X"][keep]
        row_of = {s: i for i, s in enumerate(meta["scan"])}
        smp = scans(d)
        streams[d] = smp
        out = run.run(smp, key=d)
        raw_b = m.raw(X)
        sc_b = m.cal.transform(raw_b)
        dd = {"drive": d, "scans_streamed": len(smp), "compared": 0}
        # features of the same chain, for the cache comparison (independent of the runner's state)
        r2 = LidarInterimRunner(m)
        r2.reset(d)
        for k, s in enumerate(smp):
            row, first = r2.features(s["points"])
            e = out[k]
            if first:
                assert e.details["first_scan_no_previous"]
                continue
            i = row_of[s["sample_id"]]
            feat_diff = max(feat_diff, float(np.abs(row.astype(np.float64) - X[i].astype(np.float64)).max()))
            score_diff = max(score_diff, abs(e.score - float(sc_b[i])))
            alarm_mis += int(e.alarm != bool(sc_b[i] >= m.threshold))
            nalarm += int(e.alarm)
            n += 1
            dd["compared"] += 1
        per_drive.append(dd)
        log("A1", d, dd)
    a1 = {"scans_compared": n, "drives": per_drive, "max_abs_feature_diff_vs_cache": feat_diff, "max_abs_score_diff": score_diff, "alarm_mismatches": alarm_mis,
          "alarms_in_compared": nalarm, "tolerance_score": 1e-6, "met": bool(n >= 30 and score_diff <= 1e-6 and alarm_mis == 0)}
    # ---- A2 truncation ----
    a2 = []
    full = LidarInterimRunner(m).run(streams[DRIVES[0]], key="x")
    for k in (4, 9, 14):
        a2.append({"scans": k, **compare_sequences(LidarInterimRunner(m).run(streams[DRIVES[0]][:k], key="x"), full[:k], tol=1e-9)})
    a2s = {"checks": a2, "all_identical": all(c["identical"] for c in a2)}
    # ---- A3 reset ----
    r1 = LidarInterimRunner(m)
    r1.run(streams[DRIVES[0]], key="A")
    after = r1.run(streams[DRIVES[1]], key="B")
    fresh = LidarInterimRunner(m).run(streams[DRIVES[1]], key="B")
    a3 = compare_sequences(after, fresh, tol=1e-9)
    # ---- A4 latency ----
    ns, em = [], []
    for rep in range(3):
        rr = LidarInterimRunner(m)
        rr.run(streams[DRIVES[0]], key="lat")
        ns.append(list(rr.latency.ns)), em.append(list(rr.latency.emit))
        log("latency rep", rep, f"median {np.median(ns[-1]) / 1e6:.1f} ms")
    lat = L.pooled(ns, em)
    lat.update({"scans_per_rep": N_SCANS, "scan_period_s": 0.1, "v2_reference_ms": 23.0, "p99_below_period": bool(lat["pooled"]["p99_ms"] < 100.0),
                "note": "describe (211 features) + temporal differences + XGBoost predict_proba + ECDF per scan; file reading excluded; n_jobs=2"})
    res = {"status": "INTERIM: WP3 S1 retrained v2 baseline, not the final LiDAR domain", "data": {"split": "KITTI validation drives " + ",".join(DRIVES), "scans_per_drive": N_SCANS},
           "A1_exactness": a1, "A2_causality_truncation": a2s, "A3_reset": a3, "A4_latency": lat, "machine": L.machine(), "seconds": time.time() - T0}
    L.dump(res, "S1_lidar.json")
    log("done")


if __name__ == "__main__":
    main()
