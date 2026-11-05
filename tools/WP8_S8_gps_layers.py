"""WP8 S8 step 1: which GPS-domain layer fires on the CLEAN runs of each drive (H31 and V31_val), frozen v3 GPS domain, no refit. Clean run = the S7 / WP7_S2_veh construction
(gps.stream.make_run, seeds [42, 77, 4/6, drive, phase, 0], 10 phases, LiDAR-odometry columns); per layer the Evidence alarm fraction (layer threshold at the 1 % budget) and the combined domain alarm.
Output results/WP8/S8/gps_layers.json (resumable per drive in results/WP8/S8/parts). Run: python -u -W ignore tools/WP8_S8_gps_layers.py [drive ...]"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np
import pandas as pd

S7.open_guard()
S7.patch_h31_paths()
import WP6_S2_kitti  # noqa: F401  (import side effects as in the veh builder)
from common.config import SEED
from gps import lidar_odom as LO
from gps import stream as GS
from gps.domain import GPSDomain, prepare

OUT = S7.ROOT / "results" / "WP8" / "S8"
PARTS = OUT / "parts"
T0 = time.time()


def clean_frames(d):
    ox = GS.load_oxts(d)
    frames = []
    for ph in range(GS.PHASES):
        g = GS.resample_1hz(ox, ph / GS.PHASES)
        if len(g["t"]) < 6:
            continue
        rng = lambda *x: np.random.default_rng([SEED, 77, *x])
        f = GS.make_run(ox, g, rng(4, int(d), ph, 0), None, rng(6, int(d), ph, 0))
        f["drive"], f["part"], f["run"], f["k"] = d, "test", f"{d}/p{ph}/r0", np.arange(len(f))
        f = f[GS.COLUMNS]
        frames.append(f.join(LO.stream_features(f)))
    return pd.concat(frames, ignore_index=True)


def main(argv):
    PARTS.mkdir(parents=True, exist_ok=True)
    gdom = GPSDomain.load(S7.ROOT / "results" / "WP1" / "frozen_gps")
    drives = [(d, "H31") for d in sorted(S7.kitti_drives())] + [(d, "V31_val") for d in ["0001", "0005", "0011", "0027", "0028", "0035", "0039", "0052", "0079", "0095"]]
    for d, s in drives:
        if argv and d not in argv:
            continue
        f = PARTS / f"gps_layers_{d}.json"
        if f.exists():
            print("skip", d, flush=True)
            continue
        df = prepare(clean_frames(d))
        ev, per = gdom.score(df, with_layers=True)
        n = len(df)
        r = {"set": s, "ticks": n, "combined": float(np.mean([e.alarm for e in ev])), "layers": {k: float(np.mean([e.alarm for e in v])) for k, v in per.items()}}
        f.with_suffix(".tmp").write_text(json.dumps(r, indent=1))
        f.with_suffix(".tmp").replace(f)
        print(f"[{time.time() - T0:5.0f}s] {d} {s} n={n} combined {r['combined']:.3f}", flush=True)
    res = {p.stem.split("_")[-1]: json.loads(p.read_text()) for p in sorted(PARTS.glob("gps_layers_*.json"))}
    (OUT / "gps_layers.json").write_text(json.dumps(res, indent=1))
    df = pd.DataFrame({d: {"set": r["set"], "comb": r["combined"], **{k.replace("gps.", ""): v for k, v in r["layers"].items()}} for d, r in res.items()}).T
    print(df.to_string())


if __name__ == "__main__":
    main(sys.argv[1:])
