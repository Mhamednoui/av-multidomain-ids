"""WP1 S8 pipeline check on DEV rows only: the new score matrix + fast run-level code must reproduce the S4 dev summaries
(results/WP1/S4_dev.json: B2, EKF NIS, the two selected CUSUM layers at the pooled LODO 1% threshold of the 16 drives).
Run from codes_v3/: python -u -W ignore tools/WP1_S8_check.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S8_lib as W
from gps import stack as ST


def main():
    raw = W.load_raw()
    dev = raw[raw["part"].isin(W.DEV_PARTS)]
    ri = ST.RunIndex(dev)
    s4 = json.loads((W.L.OUT / "S4_dev.json").read_text())
    normal = (dev["label"] == 0).to_numpy()
    sel = s4["selection"]
    pairs = {"gps.dr_resid_10": "gps.dr_resid_10", "gps.ekf_nis": "gps.ekf_nis", sel["best_ekf"]: sel["best_ekf"], sel["best_dr"]: sel["best_dr"]}
    worst = 0.0
    for col, key in pairs.items():
        r = dev[col].to_numpy(float)
        f = r >= ST.raw_threshold(r, normal, 0.01)
        mine = ri.run_level(f)
        ref = s4["candidates"][key]["summary"]["run_detected"]
        j = ri.j(f, sorted(dev["drive"].unique()))
        d = max(abs(mine[a] - ref[a]) for a in ST.ATTACKS)
        worst = max(worst, d, abs(j - s4["candidates"][key]["J"]))
        print(col, "max |run-level diff|", round(d, 6), "J", round(j, 4), "S4 J", round(s4["candidates"][key]["J"], 4), "FA clean", round(ri.clean_fa(f), 4),
              "S4 FA", round(s4["candidates"][key]["summary"]["false_alarm_clean_runs"], 4))
    print("WORST", worst)
    assert worst < 1e-9


if __name__ == "__main__":
    main()
