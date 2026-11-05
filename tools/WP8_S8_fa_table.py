"""WP8 S8 step 1: per-drive clean false-alarm table by layer from SAVED scores (no refit, no new scoring): H31 (S7 caches: kveh.pkl, lidar.pkl) and V31_val (S2 kveh cache, S3 LiDAR LODO scores).
GPS: combined domain alarm per clean tick; cross: combined and per-edge alarms (7 edges); LiDAR: combined scan alarm and per layer (L1 geometry / L2a intensity / L2c background / L2d tracking).
V31_val LiDAR layer split uses the frozen domain31 per-layer thresholds on the LODO raw scores (in-sample reference, labelled); the V31_val LiDAR combined alarm is the proper LODO alarm.
Output results/WP8/S8/fa_by_drive.json. Run: python -u -W ignore tools/WP8_S8_fa_table.py"""
import collections
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
DE = ROOT.parent / "data_extra" / "cache_v3" / "WP8"
OUT = ROOT / "results" / "WP8" / "S8"
LAY = ["L1", "L2a", "L2c", "L2d"]


def veh(path, label):
    k = pickle.load(open(path, "rb"))
    edges = k["edges"]
    acc = collections.defaultdict(lambda: {"n": 0, "gps": 0, "cross": 0, "edges": np.zeros(len(edges))})
    for (d, ph, fam), v in k["series"].items():
        if fam != "none":
            continue
        a = acc[d]
        a["n"] += v["n"]
        a["gps"] += int(v["gps_alarm"].sum())
        a["cross"] += int(v["cross_alarm"].sum())
        a["edges"] += v["cross_layer_alarm"].sum(0)
    out = {}
    for d, a in sorted(acc.items()):
        out[d] = {"set": label, "ticks": a["n"], "gps_fa": a["gps"] / a["n"], "cross_fa": a["cross"] / a["n"], **{"edge:" + e: float(x / a["n"]) for e, x in zip(edges, a["edges"])}}
    return out


def lidar_h31():
    l = pickle.load(open(DE / "S7" / "lidar.pkl", "rb"))
    out = {}
    for d, r in sorted(l["drives"].items()):
        f = r["frame"]
        c = f[f["kind"] == "clean"]
        out[d] = {"scans": int(len(c)), "lidar_fa": float(c["v31_alarm"].mean()), "v3_fa": float(c["v3_alarm"].mean()), **{"fire:" + L: float(c["v31_fire_" + L].mean()) for L in LAY}}
    return out


def lidar_val():
    from lidar.domain31 import Domain31
    dom = Domain31.load(ROOT / "results" / "WP8" / "S3" / "frozen_lidar31")
    z = np.load(ROOT / "results" / "WP8" / "scores" / "S3" / "lidar_val.npz", allow_pickle=True)
    m = z["kind"] == "clean"
    raw = {L: z["v31_raw_" + L][m] for L in LAY}
    fire = dom.union.layer_alarm(raw)
    df = pd.DataFrame({"drive": z["drive"][m], "al": z["v31_alarm"][m], "v3": z["v3rule_alarm"][m]})
    for j, L in enumerate(LAY):
        df["fire:" + L] = fire[:, j]
    out = {}
    for d, g in df.groupby("drive"):
        out[d] = {"scans": int(len(g)), "lidar_fa": float(g["al"].mean()), "v3_fa": float(g["v3"].mean()), **{"fire:" + L: float(g["fire:" + L].mean()) for L in LAY}}
    return out


def main():
    res = {"H31": {"veh": veh(DE / "S7" / "kveh.pkl", "H31"), "lidar": lidar_h31()},
           "V31_val": {"veh": veh(DE / "S2" / "kveh.pkl", "V31_val"), "lidar": lidar_val()}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "fa_by_drive.json").write_text(json.dumps(res, indent=1))
    for s in res:
        print("==", s)
        v, l = res[s]["veh"], res[s]["lidar"]
        rows = []
        for d in sorted(set(v) | set(l)):
            rows.append([d, v.get(d, {}).get("ticks"), v.get(d, {}).get("gps_fa"), v.get(d, {}).get("cross_fa"), l.get(d, {}).get("scans"), l.get(d, {}).get("lidar_fa")] +
                        [l.get(d, {}).get("fire:" + L) for L in LAY])
        df = pd.DataFrame(rows, columns=["drive", "ticks", "gps", "cross", "scans", "lidar", "L1", "L2a", "L2c", "L2d"])
        print(df.round(3).to_string())
        n = df["ticks"].sum()
        print("pooled gps %.4f cross %.4f lidar %.4f" % ((df["gps"] * df["ticks"]).sum() / n, (df["cross"] * df["ticks"]).sum() / n, (df["lidar"] * df["scans"]).sum() / df["scans"].sum()))


if __name__ == "__main__":
    main()
