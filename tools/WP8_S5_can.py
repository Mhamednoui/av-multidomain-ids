"""WP8 S5 CAN: incremental windows vs the v3 batch CanDomain (equality) and per-window timing, V31_val ROAD captures (+ long train captures for timing only).

For every capture: batch = CanDomain.score_capture(whole capture); incremental = IncrementalCan fed FRAME BY FRAME (push) with the wall time of every push
that completes a window recorded. Equality: window ids, score, alarm, reason, t, per-layer scores / alarms, MotionEstimates. Timing rules (notes/WP8_v31.md S5 C2):
p99 window compute <= 0.15 s on every capture; p99(windows after 600k frames) / p99(windows before 100k frames) <= 1.5 on the longest capture.
Outputs: results/WP8/S5/parts/can_<capture>.json (resumable, one per capture), results/WP8/scores/S5/can_<capture>.npz (per-window scores + labels, rule 6),
results/WP8/S5/can_summary.json. Usage: python -u -W ignore tools/WP8_S5_can.py [--long] [--only name ...]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np

from can import adapters as A
from can.domain import CanDomain
from can.incremental import IncrementalCan

OUT = ROOT / "results" / "WP8" / "S5"
SC = ROOT / "results" / "WP8" / "scores" / "S5"
FROZEN = ROOT / "results" / "WP2" / "s7_domain"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def load(name, caps):
    d = A.load_road(name, caps)
    B = np.maximum(d[A.BYTE_COLS].to_numpy(), 0).astype(np.uint8)
    return d["t"].to_numpy(), d["id"].to_numpy().astype(np.int64), d["dlc"].to_numpy().astype(np.int64), B, d["label"].to_numpy()


def compare(comb, per, stream, layers):
    """Max |score diff| and mismatch counts between the batch lists and the incremental (comb, per) tuples."""
    res = {"windows_batch": len(comb), "windows_inc": len(stream), "id_mismatch": 0, "alarm_mismatch": 0, "reason_mismatch": 0, "t_mismatch": 0,
           "max_abs_diff": 0.0, "detail_mismatch": 0}
    if len(comb) != len(stream):
        res["id_mismatch"] = abs(len(comb) - len(stream))
    for j in range(min(len(comb), len(stream))):
        c, p = stream[j]
        b = comb[j]
        if c.sample_id != b.sample_id:
            res["id_mismatch"] += 1
            continue
        res["alarm_mismatch"] += int(c.alarm != b.alarm)
        res["reason_mismatch"] += int(c.reason != b.reason)
        res["t_mismatch"] += int(c.t != b.t)
        res["detail_mismatch"] += int(c.details != b.details)
        res["max_abs_diff"] = max(res["max_abs_diff"], abs(c.score - b.score))
        for l in layers:
            e, f = p[l], per[l][j]
            res["alarm_mismatch"] += int(e.alarm != f.alarm)
            res["t_mismatch"] += int(e.t != f.t or e.sample_id != f.sample_id)
            res["max_abs_diff"] = max(res["max_abs_diff"], abs(e.score - f.score))
    return res


def run_capture(dom, name, caps, tag):
    t, ids, dlc, B, lab = load(name, caps)
    n = len(t)
    log(name, n, "frames: batch")
    t1 = time.time()
    comb, per = dom.score_capture(t, ids, dlc, B, name=name, explain=True)
    t_batch = time.time() - t1
    me_b = dom.motion_estimates(t, ids, dlc, B)
    log(name, f"batch done {t_batch:.1f}s, {len(comb)} windows; incremental frame by frame")
    inc = IncrementalCan(dom, name=name, explain=True)
    stream, wall, at_frame = [], [], []
    t1 = time.time()
    for i in range(n):
        s = time.perf_counter()
        out = inc.push(t[i], ids[i], dlc[i], B[i])
        if out:
            wall.append(time.perf_counter() - s)
            at_frame.append(i)
            stream.extend(out)
    s = time.perf_counter()
    out = inc.flush()
    stream.extend(out)
    t_inc = time.time() - t1
    me_i = inc.pop_motion()
    res = compare(comb, per, stream, dom.layers)
    res["motion_batch"], res["motion_inc"] = len(me_b), len(me_i)
    res["motion_max_diff"] = float(max([abs(a.speed - b.speed) for a, b in zip(me_b, me_i)] + [abs(a.t - b.t) for a, b in zip(me_b, me_i)] + [0.0]))
    res["motion_mismatch"] = int(len(me_b) != len(me_i)) + int(sum(a.t != b.t or a.sigma != b.sigma for a, b in zip(me_b, me_i)))
    wall = np.array(wall)
    at_frame = np.array(at_frame)
    res.update({"name": name, "frames": int(n), "seconds": float(t[-1] - t[0]), "t_batch_s": t_batch, "t_inc_total_s": t_inc,
                "window_ms": {"median": float(np.median(wall) * 1e3), "p99": float(np.percentile(wall, 99) * 1e3), "max": float(wall.max() * 1e3)},
                "p99_s": float(np.percentile(wall, 99))})
    early = wall[at_frame < 100_000]
    late = wall[at_frame > 600_000]
    if len(early) >= 5 and len(late) >= 5:
        res["growth"] = {"p99_before_100k_ms": float(np.percentile(early, 99) * 1e3), "p99_after_600k_ms": float(np.percentile(late, 99) * 1e3),
                         "ratio": float(np.percentile(late, 99) / np.percentile(early, 99)), "n_early": int(len(early)), "n_late": int(len(late))}
    # scores per window (rule 6)
    sec = np.array([int(e.sample_id.split("/")[-1]) for e, _ in stream])
    tm = np.maximum.accumulate(t)
    wsec = np.floor(tm).astype(np.int64)
    wl = {}
    for s_, l_ in zip(wsec[lab > 0], lab[lab > 0]):
        wl[int(s_)] = 1
    SC.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(SC / f"can_{tag}_{name}.npz", sec=sec, y=np.array([wl.get(int(s), 0) for s in sec], np.int8),
                        score=np.array([c.score for c, _ in stream], np.float64), alarm=np.array([c.alarm for c, _ in stream]),
                        **{f"score_{l}": np.array([p[l].score for _, p in stream]) for l in dom.layers},
                        **{f"alarm_{l}": np.array([p[l].alarm for _, p in stream]) for l in dom.layers},
                        batch_score=np.array([e.score for e in comb], np.float64), wall_s=wall, at_frame=at_frame)
    return res


def main():
    long = "--long" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = set(a for a in sys.argv[sys.argv.index("--only") + 1:] if not a.startswith("--"))
    lock = json.load(open(ROOT / "locks" / "V31_val.json"))["domains"]["can"]["road_val"]
    names = [Path(r["path"]).stem for r in lock]
    tag = "val"
    if long:
        names = ["ambient_highway_street_driving_long", "ambient_dyno_drive_basic_long"]
        tag = "long"
    if only:
        names = [n for n in names if n in only]
    caps = A.road_captures()
    dom = CanDomain.load(FROZEN)
    (OUT / "parts").mkdir(parents=True, exist_ok=True)
    for name in names:
        part = OUT / "parts" / f"can_{tag}_{name}.json"
        if part.exists():
            log(name, "done already")
            continue
        res = run_capture(dom, name, caps, tag)
        tmp = part.with_suffix(".tmp")
        tmp.write_text(json.dumps(res, indent=1))
        tmp.replace(part)
        log(name, {k: res[k] for k in ("windows_batch", "windows_inc", "max_abs_diff", "alarm_mismatch", "id_mismatch", "reason_mismatch", "motion_mismatch", "window_ms")})
    allr = [json.load(open(p)) for p in sorted((OUT / "parts").glob(f"can_{tag}_*.json"))]
    (OUT / f"can_summary_{tag}.json").write_text(json.dumps(allr, indent=1))


if __name__ == "__main__":
    main()
