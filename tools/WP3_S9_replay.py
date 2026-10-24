"""WP3 S9 freeze check: replay RAW scans through the saved domain (results/WP3/S9/frozen_lidar) and compare with the stored test scores.
Clean scans of the given drives (every scan idx >= 1, previous scan = the clean scan before) and, for the drives in --attack-drives, the S4
evaluation attacks regenerated with their seeds [83, drive, i] (previous scan = the clean scan before: onset). Compares the per-layer raw scores,
the stack statistic and the alarm with results/WP3/S9/test_scores.csv.gz (written by tools/WP3_S9_final.py). Writes results/WP3/S9/freeze_check.json.
Usage: python -u -W ignore tools/WP3_S9_replay.py [--procs 4] [--attack-drives 0052,0079,0001] [--drives all]"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import ego
from lidar.data import TEST, group_id, load, scan_files
from lidar.domain import COLS, LAYERS, LidarDomain
from lidar.s4_build import attack_cases

RES = RESULTS / "WP3" / "S9"
_D = None


def dom():
    global _D
    if _D is None:
        _D = LidarDomain.load(RES / "frozen_lidar")
    return _D


def row(d, sid, kind, pts, pose, prev):
    c, per = dom().score_scan(pts, pose, prev, t=0.0, sample_id=sid)
    return dict(scan=sid, kind=kind, stat=c.details["stat"], score=c.score, alarm=c.alarm, **{"raw_" + x: c.details["layer_raw"][x] for x in LAYERS},
                **{"alarm_" + x: per[x].alarm for x in LAYERS})


def job(args):
    d, with_att = args
    files, pose = scan_files(d), ego.poses(d)
    out, prev = [], None
    for i, f in enumerate(files):
        pts = load(f)
        if i >= 1:
            out.append(row(d, group_id(d, f), "clean", pts, pose[i], (prev, pose[i - 1])))
            if with_att and i % 3 == 1:
                rng = np.random.default_rng([83, int(d), i])
                g = group_id(d, f)
                for name, att, idx in attack_cases(pts, rng, dom().table, dom().calib):
                    out.append(row(d, f"{g}|{name}", "att", att, pose[i], (prev, pose[i - 1])))
        prev = pts
    return d, pd.DataFrame(out)


if __name__ == "__main__":
    a = sys.argv
    procs = int(a[a.index("--procs") + 1]) if "--procs" in a else 4
    att_dr = a[a.index("--attack-drives") + 1].split(",") if "--attack-drives" in a else ["0052", "0079", "0001"]
    todo = [(d, d in att_dr) for d in TEST]
    todo.sort(key=lambda x: -len(scan_files(x[0])))
    t0 = time.time()
    frames = []
    with Pool(procs) as p:
        for d, df in p.imap_unordered(job, todo):
            frames.append(df)
            print(d, len(df), f"{time.time() - t0:.0f}s", flush=True)
    R = pd.concat(frames, ignore_index=True)
    S = pd.read_csv(RES / "test_scores.csv.gz", dtype={"scan": str, "drive": str})
    S = S.drop_duplicates("scan").set_index("scan")
    M = R.merge(S, left_on="scan", right_index=True, how="left", suffixes=("", "_stored"))
    miss = int(M["stat_stored"].isna().sum())
    M = M[M["stat_stored"].notna()]
    res = {"replayed_scans": int(len(R)), "matched_to_stored": int(len(M)), "unmatched": miss, "clean": int((M.kind == "clean").sum()),
           "attacked": int((M.kind == "att").sum()), "attack_drives": att_dr, "seconds": time.time() - t0}
    res["max_abs_diff"] = {"stat": float(np.abs(M["stat"] - M["stat_stored"]).max()), "score": float(np.abs(M["score"] - M["score_stored"]).max()),
                           **{c: float(np.abs(M[c] - M[c + "_stored"]).max()) for c in COLS}}
    res["alarm_differences"] = int((M["alarm"].astype(bool) != M["alarm_stored"].astype(bool)).sum())
    res["exact"] = bool(max(res["max_abs_diff"].values()) <= 1e-9 and res["alarm_differences"] == 0)
    res["seconds_per_scan_per_process"] = res["seconds"] * procs / max(len(R), 1)
    (RES / "freeze_check.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
