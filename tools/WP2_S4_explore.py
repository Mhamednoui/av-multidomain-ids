"""WP2 S4: exploration of decoded signals on TRAIN ambient captures only (statistics per signal, written to results/WP2/s4_signal_stats.json).
Usage: python tools/WP2_S4_explore.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import signals as S
from common.config import DATA_EXTRA, RESULTS

TRAIN = ["ambient_dyno_drive_basic_long", "ambient_dyno_drive_extended_long", "ambient_dyno_drive_radio_infotainment",
         "ambient_dyno_exercise_all_bits", "ambient_dyno_idle_radio_infotainment", "ambient_highway_street_driving_long"]


def main():
    dbc = S.parse_dbc()
    acc = {}
    for n in TRAIN:
        B = np.load(DATA_EXTRA / "WP2_S4_cache" / "road" / (n + ".npy"))
        raw = np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (n + ".npz"))
        dec = S.decode_all(raw["id"], B, dbc)
        for i, (rows, V) in dec.items():
            for k in range(V.shape[1]):
                x = V[:, k]
                d = np.diff(x)
                a = acc.setdefault((i, k), {"n": 0, "min": 1e18, "max": -1e18, "vals": set(), "inc1": 0, "chg": 0, "ad": []})
                a["n"] += len(x)
                a["min"], a["max"] = min(a["min"], x.min()), max(a["max"], x.max())
                if len(a["vals"]) < 300:
                    a["vals"] |= set(np.unique(x)[:300].tolist())
                a["inc1"] += int((d == 1).sum())
                a["chg"] += int((d != 0).sum())
                a["ad"].append(np.abs(d)[:: max(1, len(d) // 20000)])
        print(n, flush=True)
    out = {}
    for (i, k), a in sorted(acc.items()):
        ad = np.concatenate(a["ad"])
        out[f"{i:#x}.{k}"] = {"n": a["n"], "len": dbc[i][k].length, "min": a["min"], "max": a["max"],
                              "nuniq": len(a["vals"]), "frac_changing": a["chg"] / max(1, a["n"]),
                              "frac_inc1": a["inc1"] / max(1, a["chg"]), "ad_q999": float(np.quantile(ad, 0.999)) if len(ad) else 0}
    json.dump(out, open(RESULTS / "WP2" / "s4_signal_stats.json", "w"), indent=0)
    nc = sum(1 for v in out.values() if v["nuniq"] > 1)
    print(len(out), "signals,", nc, "non-constant")


if __name__ == "__main__":
    main()
