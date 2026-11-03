"""WP8 S3 regression + voxel equivalence on a sample of V31_val scans (150: 75 clean, 75 attacked).
For every sample scan: (1) the frozen v3 LidarDomain.raw_scores (v3 code, exact clustering, ~2 s per scan); (2) the same four layer raw
scores from lidar.fast statistics with the EXACT clustering (must equal v3: regression of the fast path); (3) with the voxel-0.1 clustering (v3.1:
how far L2a moves). Output results/WP8/S3/equiv.json. Resumable: per-scan rows appended to results/WP8/S3/parts/equiv_rows.jsonl."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S3_lib as L
from lidar import ego
from lidar.data import load, scan_files
from lidar.domain import COLS, LAYERS, LidarDomain
from lidar.fast import PrevScan, ScanStats
from lidar.s4_build import attack_cases
from lidar import s4_eval as E4

ROW = L.ROOT / "results" / "WP8" / "S3" / "equiv_rows.jsonl"
OUT = L.ROOT / "results" / "WP8" / "S3" / "equiv.json"
DR = ["0011", "0027", "0035", "0052", "0079"]


def sample():
    rng = np.random.default_rng(31)
    items = []
    for d in DR:
        n = len(scan_files(d))
        for i in sorted(rng.choice(np.arange(1, n), 15, replace=False)):
            items.append((d, int(i), "clean"))
        for i in sorted(rng.choice(np.arange(1, n, 3), 5, replace=False)):
            for a in ("PointDrop", "IntensitySpoof", "ph_replace_near"):
                items.append((d, int(i), a))
    return items


def main():
    L.guard(DR)
    done = set()
    if ROW.exists():
        done = {(r["drive"], r["i"], r["kind"]) for r in map(json.loads, ROW.read_text().splitlines())}
    v3 = LidarDomain.load(L.ROOT / "results" / "WP3" / "S9" / "frozen_lidar")
    table, calib = L.table(), L.calib()
    ex, vx = ScanStats(table, dict(L.PRM, vox=0)), ScanStats(table, L.PRM)
    for d, i, kind in sample():
        if (d, i, kind) in done:
            continue
        files, pose = scan_files(d), ego.poses(d)
        pts = load(files[i])
        if kind != "clean":
            rng = np.random.default_rng([83, int(d), i])
            att = {n: a for n, a, _ in attack_cases(pts, rng, table, calib)}[kind]
        else:
            att = pts
        prev = PrevScan(load(files[i - 1]), pose[i - 1])
        raw3, _ = v3.raw_scores(att, pose[i], (prev.pts, prev.pose))
        row = {"drive": d, "i": i, "kind": kind, **{f"v3_{k}": v for k, v in raw3.items()}}
        for tag, ss in (("exact", ex), ("vox", vx)):
            l1, tl, pair, _ = ss.compute(att, pose[i], prev)
            tl = tl.copy()
            tl.insert(0, "scan", "s")
            tl["ring_min"], tl["ring_max"], tl["az_span"] = 0.0, 7.0, 2.0 - 0.1728
            a2 = E4.scan_frame(v3.model, tl, pd.DataFrame({"scan": ["s"]}))
            l1df = pd.DataFrame([dict(zip(L.L1_KEYS, l1))])
            s6 = pd.DataFrame([pair])
            raw = {"L1": float(v3.layers["L1"].raw_scores(l1df)[0]), "L2a": float(v3.layers["L2a"].raw_scores(a2)[0]),
                   "L2c": float(v3.layers["L2c"].raw_scores(s6)[0]), "L2d": float(v3.layers["L2d"].raw_scores(s6)[0])}
            row.update({f"{tag}_{k}": v for k, v in raw.items()})
            row[f"{tag}_stat"] = float(v3.stack.stat(pd.DataFrame([{c: raw[c[4:]] for c in COLS}]))[0])
        row["v3_stat"] = float(v3.stack.stat(pd.DataFrame([{c: raw3[c[4:]] for c in COLS}]))[0])
        with open(ROW, "a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(d, i, kind, flush=True)
    df = pd.DataFrame([json.loads(x) for x in ROW.read_text().splitlines()])
    thr = float(v3.stack.threshold)
    res = {"n": len(df), "n_clean": int((df.kind == "clean").sum()), "frozen_v3_threshold": thr}
    for tag in ("exact", "vox"):
        res[tag] = {l: float(np.abs(df[f"{tag}_{l}"] - df[f"v3_{l}"]).max()) for l in LAYERS}
        res[tag]["stat_max_abs_diff"] = float(np.abs(df[f"{tag}_stat"] - df["v3_stat"]).max())
        res[tag]["alarm_differences_vs_v3"] = int(((df[f"{tag}_stat"] >= thr) != (df["v3_stat"] >= thr)).sum())
        res[tag]["L2a_alarm_agreement_own_threshold"] = float(((df[f"{tag}_L2a"] >= v3.layers["L2a"].threshold) == (df["v3_L2a"] >= v3.layers["L2a"].threshold)).mean())
    res["per_kind_L2a_mean_abs_diff_vox"] = {k: float(np.abs(g["vox_L2a"] - g["v3_L2a"]).mean()) for k, g in df.groupby("kind")}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
