"""WP8 S3 rules L1 (speed) and L2 (stream == batch) on the frozen v3.1 LiDAR domain (results/WP8/S3/frozen_lidar31).
Streams V31_val clean scans drive by drive through Domain31.stream() (one core), timing push() (points in memory; the file read is timed
separately), and compares every scan with the batch path: the records of tools/WP8_S3_build.py (tiles + statistics stored per drive) scored
with the same fitted objects (domain.scorer on the stored tiles, domain.raw_from_records, domain.evidence).
Run: python -u -W ignore tools/WP8_S3_speed.py [--n 1000] [--tag light|load]   -> results/WP8/S3/speed_<tag>.json"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S3_lib as L
from lidar import ego
from lidar.data import load, scan_files
from lidar.domain31 import Domain31
from lidar.fast import ScanStats

OUT = L.ROOT / "results" / "WP8" / "S3"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--tag", default="light")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    dom = Domain31.load(OUT / "frozen_lidar31")
    L.guard(L.VAL)
    t_push, t_load, rows = [], [], []
    mism_alarm, max_diff, n = 0, 0.0, 0
    for d in L.VAL:
        z = pd.read_pickle(L.PARTS / f"clean_{d}.pkl")
        sc, tl = z["scans"], z["tiles"]
        files, pose = scan_files(d), ego.poses(d)
        s = dom.stream()
        for i, f in enumerate(files):
            t0 = time.perf_counter()
            pts = load(f)
            t1 = time.perf_counter()
            comb, per = s.push(pts, pose[i], t=i * 0.1032, sample_id=f"{d}/{i}")
            t2 = time.perf_counter()
            t_load.append(t1 - t0)
            t_push.append(t2 - t1)
            # batch path
            r = sc.iloc[i]
            tt = tl[tl.si == i]
            av = dom.scorer.scan_stats(tt["range"].to_numpy(), tt["n_points"].to_numpy(), tt["int_mean"].to_numpy())
            pair = None if i == 0 else {k: float(r[k]) for k in L.PAIR_KEYS}
            raw = dom.raw_from_records(np.array([r[k] for k in L.L1_KEYS]), av, pair, dom.scorer.n_valid(tt['range'].to_numpy(), tt['n_points'].to_numpy()))
            bc, _ = dom.evidence(raw, i * 0.1032, f"{d}/{i}", first=(i == 0))
            diff = abs(bc.details["stat"] - comb.details["stat"])
            diff = max(diff, abs(bc.score - comb.score), *[abs(raw[k] - comb.details["layer_raw"][k]) for k in raw])
            max_diff = max(max_diff, diff)
            mism_alarm += int(bc.alarm != comb.alarm)
            n += 1
            if n >= a.n and a.n > 0 and i > 20 and False:
                break
        print(d, n, f"median push so far {1000 * np.median(t_push):.1f} ms", flush=True)
        if a.n > 0 and n >= a.n:
            break
    tp = np.array(t_push) * 1000
    res = {"tag": a.tag, "note": a.note, "n_scans": int(n), "push_ms": {"median": float(np.median(tp)), "mean": float(tp.mean()), "p90": float(np.quantile(tp, 0.9)),
           "p99": float(np.quantile(tp, 0.99)), "max": float(tp.max())}, "file_read_ms_median": float(np.median(t_load) * 1000),
           "stream_vs_batch": {"alarm_mismatches": mism_alarm, "max_abs_diff": float(max_diff), "n_compared": int(n)},
           "rule_L1": {"median<=100ms": bool(np.median(tp) <= 100), "p99<=250ms": bool(np.quantile(tp, 0.99) <= 250)},
           "rule_L2": {"zero_alarm_mismatch": mism_alarm == 0, "max_diff<=1e-9": bool(max_diff <= 1e-9)}}
    (OUT / f"speed_{a.tag}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
