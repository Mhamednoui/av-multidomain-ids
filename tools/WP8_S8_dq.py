"""WP8 S8 step 1: data-quality table of the KITTI drives (H31, V31_val, v3 train): OXTS receiver fields (navstat, numsats, posmode/velmode/orimode, accuracy fields),
OXTS and Velodyne timestamp gaps / duplicates / drops, scan point counts, speed / yaw-rate envelope, OXTS-vs-scan clock offset, calibration file date.
No model, no labels, no thresholds: pure descriptive statistics of the recordings. Reads (not modifies) the data folders. Output results/WP8/S8/dq.json.
Run: python -u -W ignore tools/WP8_S8_dq.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
DE = ROOT.parent / "data_extra"
OUT = ROOT / "results" / "WP8" / "S8"
COLS = ["lat", "lon", "alt", "roll", "pitch", "yaw", "vn", "ve", "vf", "vl", "vu", "ax", "ay", "az", "af", "al", "au", "wx", "wy", "wz", "wf", "wl", "wu",
        "pos_acc", "vel_acc", "navstat", "numsats", "posmode", "velmode", "orimode"]


def folder(name, d):
    """(drive root with oxts/ and velodyne_points/, set) for a drive id."""
    if d in ("0001", "0015"):
        return ROOT.parent / "codes" / "data" / "Depth" / f"2011_09_26_drive_{d}_sync" / "2011_09_26" / f"2011_09_26_drive_{d}_sync"
    p = DE / "kitti_raw" / f"2011_09_26_drive_{d}_sync" / "2011_09_26" / f"2011_09_26_drive_{d}_sync"
    return p


def stats(root):
    ox = root / "oxts"
    files = sorted((ox / "data").glob("*.txt"))
    a = np.array([np.loadtxt(f) for f in files])
    df = pd.DataFrame(a, columns=COLS)
    ts = pd.to_datetime(pd.read_csv(ox / "timestamps.txt", header=None)[0])
    t = (ts - ts.iloc[0]).dt.total_seconds().to_numpy()
    dt = np.diff(t)
    vt = root / "velodyne_points"
    vts = pd.to_datetime(pd.read_csv(vt / "timestamps.txt", header=None)[0])
    tv = (vts - ts.iloc[0]).dt.total_seconds().to_numpy()
    dtv = np.diff(tv)
    ns = [(f.stat().st_size // 16) for f in sorted((vt / "data").glob("*.bin"))]
    sp = df["vf"].to_numpy()
    g = lambda c: {"min": float(df[c].min()), "mean": float(df[c].mean()), "max": float(df[c].max())}
    return {
        "n_oxts": len(df), "dur_s": float(t[-1]), "oxts_dt": {"min": float(dt.min()), "median": float(np.median(dt)), "max": float(dt.max()), "n_dup": int((dt <= 0).sum()), "n_gap_gt_0p15": int((dt > 0.15).sum())},
        "n_scans": len(ns), "scan_dt": {"min": float(dtv.min()), "median": float(np.median(dtv)), "max": float(dtv.max()), "n_dup": int((dtv <= 0).sum()), "n_gap_gt_0p15": int((dtv > 0.15).sum())},
        "scan_points": {"min": int(min(ns)), "mean": float(np.mean(ns)), "max": int(max(ns))},
        "scan_t0_minus_oxts_t0_s": float(tv[0]), "scan_tend_minus_oxts_tend_s": float(tv[-1] - t[-1]),
        "navstat": {int(k): int(v) for k, v in df["navstat"].value_counts().items()}, "posmode": {int(k): int(v) for k, v in df["posmode"].value_counts().items()},
        "velmode": {int(k): int(v) for k, v in df["velmode"].value_counts().items()}, "orimode": {int(k): int(v) for k, v in df["orimode"].value_counts().items()},
        "numsats": g("numsats"), "pos_acc": g("pos_acc"), "vel_acc": g("vel_acc"),
        "speed_vf": {"min": float(sp.min()), "mean": float(sp.mean()), "p95": float(np.percentile(sp, 95)), "max": float(sp.max()), "frac_below_0p5": float((sp < 0.5).mean())},
        "wz_abs": {"mean": float(df["wz"].abs().mean()), "p95": float(df["wz"].abs().quantile(0.95)), "max": float(df["wz"].abs().max())},
        "af_abs_p95": float(df["af"].abs().quantile(0.95)), "vl_abs_max": float(df["vl"].abs().max()), "vu_abs_max": float(df["vu"].abs().max()),
        "path_len_m": float(np.sum(np.r_[0, np.diff(t)] * sp)),
    }


def main():
    lock = json.loads((ROOT / "locks" / "H31.json").read_text())["domains"]["kitti_vehicle_block"]["drives"]
    v31 = json.loads((ROOT / "locks" / "V31_val.json").read_text())["domains"]["kitti_vehicle_block"]
    out = {}
    for dr in lock:
        d = dr["drive"].split("_drive_")[1]
        r = DE / "D04b_kitti_raw_v31" / (dr["drive"] + "_sync")
        s = stats(r)
        s.update({"set": "H31", "drive": dr["drive"], "stratum": dr["stratum"], "scene": dr.get("scene")})
        cal = sorted((r / "calib").glob("*")) if (r / "calib").exists() else []
        s["calib_files"] = [c.name for c in cal]
        out[f"H31:{d}"] = s
    for sp, ids in (("V31_val", v31["val"]), ("train", v31["train"])):
        for d in ids:
            s = stats(folder(sp, d))
            s.update({"set": sp, "drive": "2011_09_26_drive_" + d})
            out[f"{sp}:{d}"] = s
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dq.json").write_text(json.dumps(out, indent=1))
    rows = []
    for k, s in out.items():
        rows.append((k, s["n_oxts"], s["n_scans"], s["oxts_dt"]["max"], s["scan_dt"]["max"], s["scan_points"]["mean"], s["numsats"]["min"], s["numsats"]["mean"], s["pos_acc"]["max"], s["vel_acc"]["max"],
                     str(s["posmode"]), str(s["navstat"]), s["speed_vf"]["mean"], s["speed_vf"]["max"], s["speed_vf"]["frac_below_0p5"], s["wz_abs"]["p95"], s["wz_abs"]["max"], s["scan_t0_minus_oxts_t0_s"]))
    print(pd.DataFrame(rows, columns=["id", "nox", "nsc", "ox_dtmax", "sc_dtmax", "pts", "nsat_min", "nsat_mean", "pacc_max", "vacc_max", "posmode", "navstat", "v_mean", "v_max", "f_still", "wz95", "wzmax", "sc_t0"]).round(3).to_string())


if __name__ == "__main__":
    main()
