"""WP6 S2: the FROZEN GPS domain (results/WP1/frozen_gps, gps/domain.py) scored on the KITTI runs used by S2, for the comparison
"does cross-domain catch what the GPS domain missed". No refit: load + prepare + score_arrays only.
Runs: val + test drives, 10 phases: clean r0, WP1 drift / accel_drift / doppler_spoof / meaconing runs, and the coordinated gps_can
runs of tools/WP6_S2_kitti.py (GPS position / Doppler AND wheel odometry spoofed: the wheel odometry is the CAN wheel speed).
Output: ../data_extra/cache_v3/WP6/s2_gpsdomain.pkl (DataFrame run, t, attack, part, alarm, score).
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gps import stream as GS  # noqa: E402
from gps.domain import GPSDomain, prepare  # noqa: E402
import WP6_S1_kitti as S1  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main():
    T0 = time.time()
    dom = GPSDomain.load(ROOT / "results" / "WP1" / "frozen_gps")
    kx = S1.kitti_stream()
    kx = kx[kx["part"].isin(["val", "test"]) & kx["attack"].isin(["none", "drift", "accel_drift", "doppler_spoof", "meaconing"])]
    kx = kx[(kx["attack"] != "none") | kx["run"].str.endswith("/r0")]
    co = pickle.load(open(S1.CACHE / "s2_kitti.pkl", "rb"))["gps_can_runs"][GS.COLUMNS]
    df = pd.concat([kx, co], ignore_index=True).sort_values(["run", "t"], kind="stable").reset_index(drop=True)
    print("rows", len(df), "runs", df["run"].nunique(), flush=True)
    parts = []
    for d, g in df.groupby("drive", sort=True):
        g = prepare(g.reset_index(drop=True))
        S, sc, al = dom.score_arrays(g)
        parts.append(pd.DataFrame({"run": g["run"].to_numpy(), "t": g["t"].to_numpy(float), "attack": g["attack"].to_numpy(), "part": g["part"].to_numpy(),
                                   "label": g["label"].to_numpy(), "onset_t": g["onset_t"].to_numpy(float), "score": sc, "alarm": al}))
        print(f"[{time.time() - T0:5.0f}s] {d}", flush=True)
    out = pd.concat(parts, ignore_index=True)
    pickle.dump(out, open(S1.CACHE / "s2_gpsdomain.pkl", "wb"))
    print(out.groupby(["part", "attack"])["alarm"].mean(), flush=True)


if __name__ == "__main__":
    main()
