"""WP9 B4 step 1: dedup + split locks for AV-GPS (GPS) and KITTI (LiDAR), written BEFORE any B4 model is fitted.

AV-GPS (D03, Abrar et al. arXiv 2405.08359; read from ../codes/data/AV-GPS-Dataset, the public GitHub clone, files 0-3):
  session = contiguous block with one label and no Run Time reset / gap > 5 s. Findings (tools/WP9_B4_gps_explore2.py): file 0 is a subset of file 1
  (all 46,287 normal rows), two spoofed sessions of file 1 are exact copies of two others, two spoofed sessions of file 3 are 94-96% copies of file 2 sessions.
  Dedup: drop file 0; drop exact duplicate sessions (lat/lon sequence hash) keeping the first; drop sessions of file 3 with >= 50% of rows in file 2;
  drop sessions with < 10 rows. Dataset DS1 = file 1, DS2 = file 2, DS3 = file 3 (left with normal sessions only).
  Case I: train = DS1 train sessions, val = DS1 val sessions (stratified draw, seed SEED), test = DS2 (+ DS3 normals for false alarms only).
  Case II: train = DS2 (no validation: fixed config), test = DS1 (+ DS3 normals).
KITTI (D04 old 23 drives; WP1 / WP3 drive split train 13 / val 3 / test 7); H31 drives are not on the list: overlap asserted 0.
Output: locks/WP9_avgps.json, locks/WP9_kitti.json.   Run: python -I -u -W ignore tools/WP9_B4_lock.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from common.config import SEED
from common.splits import group_split

AV = ROOT.parent / "codes" / "data" / "AV-GPS-Dataset"
MIN_ROWS = 10


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def sessions(df):
    rt = pd.to_timedelta(df["Run Time"], errors="coerce").dt.total_seconds()
    d = rt.diff()
    lab = df["Data Type"].values
    new = (d < 0) | (d > 5) | (np.r_[False, np.diff(lab) != 0])
    return np.cumsum(new.values)


def keys(df):
    return list(zip(df["GPS Latitude"].round(7), df["GPS Longitude"].round(7), df["Clock Time"].astype(str), df["Heading (deg)"]))


def avgps_lock():
    dfs = [pd.read_csv(AV / f"AV-GPS-Dataset-{i}.csv", low_memory=False) for i in range(4)]
    K = [set(keys(d)) for d in dfs]
    sess, seen_hash = [], {}
    drop = []
    for fi in (1, 2, 3):
        df = dfs[fi]
        sid = sessions(df)
        kk = keys(df)
        for s in np.unique(sid):
            m = np.where(sid == s)[0]
            a, b = int(m[0]), int(m[-1]) + 1
            name = f"f{fi}:{a}-{b}"
            lab = int(df["Data Type"].iloc[a])
            h = hashlib.md5(df[["GPS Latitude", "GPS Longitude"]].iloc[m].round(6).values.tobytes()).hexdigest()
            rec = {"session": name, "file": fi, "start": a, "end": b, "rows": len(m), "label": lab, "latlon_md5": h}
            if len(m) < MIN_ROWS:
                drop.append(dict(rec, reason=f"fewer than {MIN_ROWS} rows"))
                continue
            if h in seen_hash:
                drop.append(dict(rec, reason=f"exact duplicate of session {seen_hash[h]} (lat/lon sequence)"))
                continue
            if fi == 3:
                frac = float(np.mean([kk[j] in K[2] for j in m]))
                rec["frac_rows_in_file2"] = frac
                if frac >= 0.5:
                    drop.append(dict(rec, reason=f"{frac:.2f} of the rows also in file 2"))
                    continue
            seen_hash[h] = name
            sess.append(rec)
    S = pd.DataFrame(sess)
    ds1 = S[S.file == 1]
    rng_parts = {}
    for lab in (0, 1):
        ids = ds1[ds1.label == lab].session.tolist()
        parts = group_split(ids, fractions=(0.7, 0.3), names=("train", "val"), seed=SEED)
        rng_parts[lab] = parts
    case1 = {"train": sorted(rng_parts[0]["train"] + rng_parts[1]["train"]), "val": sorted(rng_parts[0]["val"] + rng_parts[1]["val"]),
             "test": S[S.file == 2].session.tolist(), "test_normal_only_extra": S[S.file == 3].session.tolist()}
    case2 = {"train": S[S.file == 2].session.tolist(), "val": [], "test": ds1.session.tolist(), "test_normal_only_extra": S[S.file == 3].session.tolist()}
    for c in (case1, case2):
        a, b = set(c["train"] + c["val"]), set(c["test"] + c["test_normal_only_extra"])
        assert not a & b
    assert not set(case1["train"]) & set(case1["val"])
    lab_of = dict(zip(S.session, S.label))
    rows_of = dict(zip(S.session, S.rows))

    def summ(ids):
        return {"sessions": len(ids), "normal_sessions": sum(lab_of[i] == 0 for i in ids), "spoof_sessions": sum(lab_of[i] == 1 for i in ids),
                "normal_rows": int(sum(rows_of[i] for i in ids if lab_of[i] == 0)), "spoof_rows": int(sum(rows_of[i] for i in ids if lab_of[i] == 1))}
    return {
        "_note": "WP9 B4 AV-GPS lock, written BEFORE any B4 model was fitted (2026-11-05). Source: public GitHub clone of the dataset already on disk (../codes/data/AV-GPS-Dataset); nothing downloaded.",
        "dataset": "D03 AV-GPS-Dataset (Abrar et al., arXiv 2405.08359)",
        "files_sha256": {f"AV-GPS-Dataset-{i}.csv": sha256(AV / f"AV-GPS-Dataset-{i}.csv") for i in range(4)},
        "session_rule": "contiguous rows with one Data Type label and no Run Time reset (<0) or gap (>5 s)",
        "dedup": {"file0": "dropped entirely: all 46,287 rows are normal rows of file 1 (key lat, lon, clock time, heading)",
                  "rule": "exact duplicate sessions (lat/lon md5) keep first; file-3 sessions with >= 50% rows in file 2 dropped; sessions < 10 rows dropped",
                  "dropped_sessions": drop},
        "sessions": sess,
        "case_I": dict(case1, summary={k: summ(case1[k]) for k in case1}),
        "case_II": dict(case2, summary={k: summ(case2[k]) for k in case2}),
        "case_III": "train on dataset 3 cannot be formed: after dedup dataset 3 has normal sessions only (its two spoofed sessions are copies of file 2)",
        "h31_overlap": 0,
        "h31_note": "H31 has no GPS-spoof dataset of this kind (kitti / comma / veremi / ...); nothing in AV-GPS is listed in locks/H31.json",
        "val_draw": f"per label, group_split(fractions 0.7/0.3, seed SEED={SEED}) of DS1 sessions",
    }


def kitti_lock():
    from lidar import data as D
    from WP8_lib import assert_not_h31
    h31 = json.loads((ROOT / "locks" / "H31.json").read_text())["domains"]["kitti_vehicle_block"]
    h31_drives = {x["drive"] for x in h31["drives"]}
    parts = {p: D.drives_of(p) for p in ("train", "val", "test")}
    alld = sorted(sum(parts.values(), []))
    names = [f"2011_09_26_drive_{d}" for d in alld]
    assert_not_h31(names)
    assert not (set(names) & h31_drives)
    assert len(alld) == len(set(alld)) == 23
    info = {}
    for p, ds in parts.items():
        info[p] = {"drives": ds, "n_scans": {d: len(D.scan_files(d)) for d in ds}}
        info[p]["total_scans"] = int(sum(info[p]["n_scans"].values()))
    gid = sorted(D.group_id(d, f) for d in alld for f in D.scan_files(d))
    return {
        "_note": "WP9 B4 KITTI lock (LiDAR), written BEFORE any B4 model was fitted (2026-11-05). WP1 / WP3 drive split of the 23 old drives (TEST 7, VAL 3, train 13).",
        "group": "drive (group id of a scan = <drive>/<file>)",
        "parts": info,
        "scan_groups_sha256": hashlib.sha256("\n".join(gid).encode()).hexdigest(),
        "h31_drives_excluded": sorted(h31_drives),
        "h31_overlap": 0,
        "exposure_note": "the 7 test drives were scored by v3 frozen layers (WP3 S1-S9, WP1) and used as V31_val material by v3.1 (WP8 S2-S6): they are NOT fresh for v3 / v3.1. "
                         "For the B4 SUPERVISED model they are scored for the first time (exposure 1 for that model).",
        "attack_seeds": "training rows: rng [97, drive, scan] on every 2nd scan (B4); evaluation attacks = the S4 / WP8 S3 set: scans i % 3 == 1, rng [83, drive, i] (lidar.s4_build.attack_cases)",
    }


if __name__ == "__main__":
    g = avgps_lock()
    (ROOT / "locks" / "WP9_avgps.json").write_text(json.dumps(g, indent=1))
    print("case I", json.dumps(g["case_I"]["summary"]), flush=True)
    print("case II", json.dumps(g["case_II"]["summary"]))
    print("dropped", [(d["session"], d["reason"]) for d in g["dedup"]["dropped_sessions"]])
    k = kitti_lock()
    (ROOT / "locks" / "WP9_kitti.json").write_text(json.dumps(k, indent=1))
    print("kitti", {p: (v["drives"], v["total_scans"]) for p, v in k["parts"].items()})
