"""WP8 S7 LiDAR runtime and equality on H31 scans (M4-8 speed / stream == batch, and the v3 literal-code sample check).
(1) speed: system.runners31.LidarRunner31 (frozen_lidar31, numba kernels) pushes the first N_SPEED scans (>= 1,000, spread over the H31 drives, clean order) one at a time; the wall time of each
    push is logged (warm-up excluded: the first 3 scans of the process); median / p95 / p99 / max; the number of other python processes (tasklist) is logged. Rule: median <= 0.10 s, p99 <= 0.25 s.
(2) stream == batch: the Evidence of those pushes equals the per-scan rows of tools/WP8_S7_lidar.py (same statistics, same union) -> score / alarm / four layer raw scores identical (0 differences, max |diff| 0.0).
(3) sample check of the v3 side: the literal frozen v3 LidarDomain (exact clustering, ~2 s per scan) on SAMPLE seeded H31 scans (clean + the S4 attack kinds): its stack statistic and alarm vs the fast-path
    v3 columns of the per-scan rows (agreement of alarms, max |stat diff|). Labelled a sample check.
Output: results/WP8/S7/lidar_check.json (resumable by section). Run: python -u -W ignore tools/WP8_S7_lidar_check.py [speed|equal|v3sample]"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np
import pandas as pd

OUTF = S7.OUT / "lidar_check.json"
N_PER_DRIVE, SAMPLE = 100, 120


def other_python():
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout.strip().splitlines()
        return max(len([x for x in r if "python" in x]) - 1, 0)
    except Exception:
        return None


def rows_of(d):
    return pd.read_pickle(S7.PARTS / f"lidar_clean_{d}.pkl")


def section_speed():
    S7.patch_h31_paths()
    S7.open_guard()
    from lidar import ego
    from lidar.data import load, scan_files
    from system.runners31 import LidarRunner31
    run = LidarRunner31(S7.ROOT / "results" / "WP8" / "S3" / "frozen_lidar31", per_layer=True, numba=True)
    ms, diffs, n_load = [], [], []
    for d in sorted(S7.kitti_drives()):
        files, pose = scan_files(d), ego.poses(d)
        ref = rows_of(d)
        run.reset(d)
        n = min(N_PER_DRIVE, len(files))
        for i in range(n):
            pts = load(files[i])
            n_load.append(other_python())
            t0 = time.perf_counter()
            ev = run.push({"points": pts, "pose": pose[i], "t": 0.0, "sample_id": i})
            dt = time.perf_counter() - t0
            if len(ms) >= 3:
                ms.append(dt * 1e3)
            else:
                ms.append(dt * 1e3)
            r = ref.iloc[i]
            c = ev[0]
            diffs.append(max(abs(c.score - r["v31_score"]), abs(c.details["stat"] - r["v31_stat"]), *[abs(c.details["layer_raw"][l] - r[f"v31_raw_{l}"]) for l in ("L1", "L2a", "L2c", "L2d")]) + float(c.alarm != bool(r["v31_alarm"])))
        print("speed", d, n, flush=True)
    a = np.array(ms[3:])
    return {"scans": int(len(a)), "warmup_excluded": 3, "median_ms": float(np.median(a)), "p95_ms": float(np.percentile(a, 95)), "p99_ms": float(np.percentile(a, 99)), "max_ms": float(a.max()),
            "rule": "median <= 100 ms, p99 <= 250 ms", "met": bool(np.median(a) <= 100 and np.percentile(a, 99) <= 250),
            "other_python_processes_median": float(np.median([x for x in n_load if x is not None])) if n_load else None,
            "stream_equals_batch": {"scans": len(diffs), "max_abs_diff_or_alarm_flip": float(max(diffs)), "mismatches": int(sum(d > 0 for d in diffs))}}


def section_v3sample():
    S7.patch_h31_paths()
    S7.open_guard()
    import WP8_S7_lidar as T
    from lidar import ego
    from lidar.data import load, scan_files
    from lidar.domain import COLS, LidarDomain
    from lidar.fast import PrevScan
    from lidar.s4_build import attack_cases
    g = T.objs()
    v3 = LidarDomain.load(S7.ROOT / "results" / "WP3" / "S9" / "frozen_lidar")
    rng = np.random.default_rng(31)
    items = []
    ids = sorted(S7.kitti_drives())
    for d in ids:
        n = len(scan_files(d))
        for i in sorted(rng.choice(np.arange(1, n, 3), size=max(SAMPLE // len(ids) // 2, 1), replace=False)):
            items.append((d, int(i), "clean"))
            items.append((d, int(i), ["PointDrop", "IntensitySpoof", "ph_replace_near"][len(items) % 3]))
    cache = {d: (pd.read_pickle(S7.PARTS / f"lidar_clean_{d}.pkl"), pd.read_pickle(S7.PARTS / f"lidar_att_{d}.pkl")) for d in ids}
    rows = []
    for d, i, kind in items:
        files, pose = scan_files(d), ego.poses(d)
        pts = load(files[i])
        if kind != "clean":
            pts = {n: a for n, a, _ in attack_cases(pts, np.random.default_rng([83, int(d), i]), g["table"], g["calib"])}[kind]
        prev = PrevScan(load(files[i - 1]), pose[i - 1])
        raw3, _ = v3.raw_scores(pts, pose[i], (prev.pts, prev.pose))
        stat = float(v3.stack.stat(pd.DataFrame([{c: raw3[c[4:]] for c in COLS}]))[0])
        cl, at = cache[d]
        r = cl[cl["i"] == i].iloc[0] if kind == "clean" else at[(at["i"] == i) & (at["attack"] == kind)].iloc[0]
        rows.append({"drive": d, "i": i, "kind": kind, "literal_stat": stat, "fast_stat": float(r["v3_stat"]), "literal_alarm": bool(stat >= v3.stack.threshold), "fast_alarm": bool(r["v3_alarm"])})
    df = pd.DataFrame(rows)
    return {"scans": len(df), "alarm_disagreements": int((df.literal_alarm != df.fast_alarm).sum()), "max_abs_stat_diff": float((df.literal_stat - df.fast_stat).abs().max()),
            "median_abs_stat_diff": float((df.literal_stat - df.fast_stat).abs().median()), "by_kind": {k: {"n": int(len(g)), "alarm_disagreements": int((g.literal_alarm != g.fast_alarm).sum())} for k, g in df.groupby("kind")},
            "label": "sample check of the fast-path v3 columns against the literal frozen v3 LidarDomain (seeded sample of H31 scans)"}


def main():
    names = sys.argv[1:] or ["speed", "v3sample"]
    res = json.loads(OUTF.read_text()) if OUTF.exists() else {}
    for n in names:
        S7.journal("S7", f"lidar check {n}: start", "tools/WP8_S7_lidar_check.py")
        res[n] = {"speed": section_speed, "v3sample": section_v3sample}[n]()
        S7.write_json(res, OUTF)
        S7.journal("S7", f"lidar check {n}: done", json.dumps({k: v for k, v in res[n].items() if not isinstance(v, (dict, list))})[:200])


if __name__ == "__main__":
    main()
