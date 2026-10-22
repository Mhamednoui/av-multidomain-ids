"""WP6 S1: wheel-speed statistics of the ROAD vehicle (0x6e0, 4 x 14-bit) on the ROAD TRAIN ambient captures.

Purpose: (1) parameters of the CAN wheel-speed simulator used on KITTI (message period, quantum, short-term
noise, inter-wheel spread); (2) plausibility of the assumed unit 0.01 km/h (acceptance A6 in notes/WP6_crossdomain.md).
Inputs: ROAD signal_extractions CSV (decoded by ROAD with the anonymised DBC), WP2 capture split (can.adapters).
Outputs: results/WP6/s1_road_wheel.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can.adapters import road_captures, road_signals_path  # noqa: E402
from common.config import results_dir  # noqa: E402

UNIT = 0.01 / 3.6        # m/s per raw unit (assumption under test)
WID, SPID = 1760, 208    # 0x6e0 wheel speeds, 0xd0 (speedometer target of the max_speedometer attack)


def read_ids(path):
    cols = ["Time", "ID"] + [f"Signal_{k}_of_ID" for k in range(1, 7)]
    out = []
    for ch in pd.read_csv(path, usecols=cols, chunksize=2_000_000):
        out.append(ch[ch["ID"].isin([WID, SPID])])
    return pd.concat(out)


def stats(name, d):
    w = d[d["ID"] == WID].sort_values("Time")
    t = w["Time"].to_numpy(float)
    W = w[[f"Signal_{k}_of_ID" for k in range(1, 5)]].to_numpy(float)
    v = W.mean(1) * UNIT
    dt = np.diff(t)
    q = np.diff(W, axis=0)
    q = np.abs(q[q != 0])
    mov = v > 1.0
    # short-term noise: residual of each wheel around a centred 0.5 s moving average of itself, moving rows
    n = max(3, int(round(0.5 / np.median(dt))) | 1)
    k = np.ones(n) / n
    res = []
    for j in range(4):
        sm = np.convolve(W[:, j], k, mode="same") * UNIT
        r = (W[:, j] * UNIT - sm)[n:-n]
        res.append(r[mov[n:-n]])
    res = np.concatenate(res) if len(res) else np.array([])
    spread = (W.max(1) - W.min(1)) * UNIT
    # 1 s speed change (acceleration) on a 1 s grid
    g = np.arange(t[0], t[-1], 1.0)
    vg = np.interp(g, t, v)
    acc = np.abs(np.diff(vg))
    sp = d[d["ID"] == SPID].sort_values("Time")
    ratio = None
    if len(sp) > 10 and mov.sum() > 50:
        s5 = np.interp(t, sp["Time"].to_numpy(float), sp["Signal_6_of_ID"].to_numpy(float))
        m = mov & (s5 > 0)
        if m.sum() > 50:
            ratio = float(np.sum(W.mean(1)[m] * s5[m]) / np.sum(s5[m] ** 2))     # wheel_raw = ratio * speedo_raw
    return {"capture": name, "n": int(len(t)), "duration_s": float(t[-1] - t[0]), "period_s_median": float(np.median(dt)),
            "period_s_p99": float(np.percentile(dt, 99)), "quantum_raw_min": float(q.min()) if len(q) else None,
            "raw_max": float(W.max()), "kmh_p99": float(np.percentile(v, 99) * 3.6), "kmh_max": float(v.max() * 3.6),
            "moving_frac": float(mov.mean()), "noise_std_mps": float(res.std()) if len(res) else None,
            "spread_mps_p50_moving": float(np.median(spread[mov])) if mov.any() else None,
            "spread_rel_p50_moving": float(np.median(spread[mov] / v[mov])) if mov.any() else None,
            "acc_p99_mps2": float(np.percentile(acc, 99)) if len(acc) else None, "acc_max_mps2": float(acc.max()) if len(acc) else None,
            "wheel_over_speedo_raw": ratio}


def main():
    caps = road_captures()
    tr = caps[(caps["kind"] == "ambient") & (caps["part"] == "train")]
    rows = []
    for name in tr["name"]:
        p = road_signals_path(name)
        d = read_ids(p)
        r = stats(name, d)
        print(json.dumps(r), flush=True)
        rows.append(r)
    df = pd.DataFrame(rows)
    mv = df[df["moving_frac"] > 0.2]
    hw = df[df["capture"].str.contains("highway")]
    summary = {
        "unit_assumed_mps_per_raw": UNIT, "captures": rows,
        "period_s": float(np.median(df["period_s_median"])), "quantum_raw": float(df["quantum_raw_min"].min()),
        "noise_std_mps_median": float(np.median(mv["noise_std_mps"])), "spread_rel_median": float(np.median(mv["spread_rel_p50_moving"])),
        "A6_i_highway_kmh_p99": [float(x) for x in hw["kmh_p99"]], "A6_ii_acc_p99_max": float(df["acc_p99_mps2"].max()),
    }
    summary["A6_i_pass"] = bool(all(60 <= x <= 160 for x in summary["A6_i_highway_kmh_p99"]))
    summary["A6_ii_pass"] = bool(summary["A6_ii_acc_p99_max"] <= 4.0)
    out = results_dir("WP6") / "s1_road_wheel.json"
    out.write_text(json.dumps(summary, indent=1))
    print({k: v for k, v in summary.items() if k != "captures"})


if __name__ == "__main__":
    main()
