"""WP8 S3b: speed (rule L1) and equality of the numba LiDAR domain on the 1,113 V31_val scans of S3.
Streams every V31_val drive through Domain31.stream() with lidar.fast.set_numba(True) (one core; points in memory, file read timed separately),
JIT warm-up reported separately (first push of the process, then 3 untimed pushes), and compares each scan with the S3 scores of frozen_lidar31
(results/WP8/scores/S3/lidar_val.npz, clean rows of the V31_val drives): layer raw scores, combined stat, score, alarm. Another-process count is
sampled (tasklist, python.exe) before, every drive and after. Per-scan outputs -> results/WP8/scores/S3b/lidar_val_<tag>.npz (rule 6).
Run: python -u -W ignore tools/WP8_S3b_speed.py --tag run1 [--numpy]  -> results/WP8/S3b/speed_<tag>.json"""
import argparse, json, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import WP8_S3_lib as L
from lidar import ego, fast
from lidar.data import load, scan_files
from lidar.domain31 import Domain31

OUT = L.ROOT / "results" / "WP8" / "S3b"
SC = L.ROOT / "results" / "WP8" / "scores" / "S3b"


def n_python():
    try:
        o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/NH"], capture_output=True, text=True, timeout=20).stdout
        return sum(1 for l in o.splitlines() if "python.exe" in l)
    except Exception:
        return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="run1"); ap.add_argument("--numpy", action="store_true"); ap.add_argument("--note", default="")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True); SC.mkdir(parents=True, exist_ok=True)
    L.guard(L.VAL)
    dom = Domain31.load(L.ROOT / "results/WP8/S3/frozen_lidar31")
    use = not a.numpy
    warm = 0.0
    if use:
        fast.set_numba(True)
        p = load(scan_files(L.VAL[0])[1])
        pose0 = ego.poses(L.VAL[0])
        t = time.perf_counter(); s0 = dom.stream(); s0.push(load(scan_files(L.VAL[0])[0]), pose0[0]); s0.push(p, pose0[1]); warm = time.perf_counter() - t
        for _ in range(3): s0.push(p, pose0[1])
    z = np.load(L.ROOT / "results/WP8/scores/S3/lidar_val.npz", allow_pickle=True)
    ref = {(d, int(i)): j for j, (d, i, k) in enumerate(zip(z["drive"], z["i"], z["kind"])) if k == "clean" and d in L.VAL}
    procs = [n_python()]
    rec = {k: [] for k in ["drive", "i", "push_ms", "L1", "L2a", "L2c", "L2d", "stat", "score", "alarm", "d_raw", "d_stat", "d_score", "d_alarm"]}
    n_cmp = 0
    for d in L.VAL:
        files, pose = scan_files(d), ego.poses(d)
        s = dom.stream()
        for i, f in enumerate(files):
            pts = load(f)
            t1 = time.perf_counter()
            comb, per = s.push(pts, pose[i], t=i * 0.1032, sample_id=f"{d}/{i}")
            dt = time.perf_counter() - t1
            raw = comb.details["layer_raw"]
            rec["drive"].append(d); rec["i"].append(i); rec["push_ms"].append(dt * 1000)
            for l in ("L1", "L2a", "L2c", "L2d"): rec[l].append(raw[l])
            rec["stat"].append(comb.details["stat"]); rec["score"].append(comb.score); rec["alarm"].append(comb.alarm)
            j = ref.get((d, i))
            if j is not None:
                n_cmp += 1
                rec["d_raw"].append(max(abs(raw[l] - z[f"v31_raw_{l}"][j]) for l in ("L1", "L2a", "L2c", "L2d")))
                rec["d_stat"].append(abs(comb.details["stat"] - z["v31_stat"][j])); rec["d_score"].append(abs(comb.score - z["v31_score"][j]))
                rec["d_alarm"].append(int(comb.alarm != bool(z["v31_alarm"][j])))
        procs.append(n_python())
        print(d, len(rec["i"]), f"median so far {np.median(rec['push_ms']):.1f} ms, python procs {procs[-1]}", flush=True)
    procs.append(n_python())
    tp = np.array(rec["push_ms"])
    np.savez_compressed(SC / f"lidar_val_{a.tag}.npz", **{k: np.array(rec[k]) for k in ["drive", "i", "push_ms", "L1", "L2a", "L2c", "L2d", "stat", "score", "alarm"]})
    res = {"tag": a.tag, "note": a.note, "numba": use, "n_scans": int(len(tp)), "warmup_s": warm,
           "push_ms": {"median": float(np.median(tp)), "mean": float(tp.mean()), "p90": float(np.quantile(tp, .9)), "p99": float(np.quantile(tp, .99)), "max": float(tp.max())},
           "python_processes_sampled": procs, "own_process_included": True,
           "vs_S3_scores": {"n_compared": n_cmp, "alarm_differences": int(sum(rec["d_alarm"])), "max_abs_diff_raw": float(max(rec["d_raw"])),
                            "max_abs_diff_stat": float(max(rec["d_stat"])), "max_abs_diff_score": float(max(rec["d_score"]))},
           "rule_L1": {"median<=100ms": bool(np.median(tp) <= 100), "p99<=250ms": bool(np.quantile(tp, .99) <= 250)}}
    res["equality_met"] = bool(res["vs_S3_scores"]["alarm_differences"] == 0 and max(res["vs_S3_scores"]["max_abs_diff_raw"], res["vs_S3_scores"]["max_abs_diff_stat"], res["vs_S3_scores"]["max_abs_diff_score"]) <= 1e-9)
    (OUT / f"speed_{a.tag}.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
