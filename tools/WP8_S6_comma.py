"""WP8 S6 comma builder: cross-domain residual tables of the comma2k19 Chunk_1 routes (RAV4, dongle b0c9d2329ad1606b) for the S6 blame evaluation.

Routes: the 13 v3 TRAIN routes (whole clean routes, fits only) and the 8 V31_val routes (v3 val + v3 test, locks/V31_val.json). Never a Chunk_2 / Chunk_4 (H31) route (G1 guard).
Per route: whole-route residual table of the 6 frozen edges (tools/WP6_S2_comma.residuals with the S1 lags / gyro axis of results/WP6/s1_sigma_models.json comma_R);
for V31_val routes also the 120 s windows of tools/WP7_S2_veh.comma_windows: clean + the 9 attacks x 2 repetitions of WP6 S2 with the WP7 S2 fixed onset (+3 s) and seeds
[42, 77, 5, route index, window, attack, rep] (route index = position in the sorted list of the 21 routes).
Output (resumable, one pickle per route, temp name then rename): ../data_extra/cache_v3/WP8/S6/comma_<route>.pkl
Run from codes_v3/: python -I -u -W ignore tools/WP8_S6_comma.py [route ...]
"""
import json
import pickle
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np

import WP6_S2_comma as SC
import WP8_lib as L8
from common.config import DATA_EXTRA, SEED
from crossdomain import comma as C

CACHE = DATA_EXTRA / "cache_v3" / "WP8" / "S6"
CHUNK = DATA_EXTRA / "D22_comma2k19" / "Chunk_1"
ONSET = 3
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def lock_routes():
    d = json.loads((ROOT / "locks" / "V31_val.json").read_text())["domains"]["comma"]["rav4_chunk1"]
    return list(d["train"]), list(d["val"])


def stack(res, edges):
    return (np.column_stack([res[e][0] for e in edges]), np.column_stack([res[e][1] for e in edges]))


def build_route(n, ri, val, lags, gyro):
    L8.assert_not_h31([str(CHUNK / n)])
    r = C.load_route(CHUNK / n)
    sig = SC.native(r)
    t0 = max(r["can_t"][0], r["gnss_t"][0], r["gyro_t"][0])
    t1 = min(r["can_t"][-1], r["gnss_t"][-1], r["gyro_t"][-1])
    grid = np.arange(np.ceil(t0) + 1.0, np.floor(t1) - 1.0, 1.0)
    edges = SC.EDGE_NAMES
    R, V = stack(SC.residuals(sig, grid, lags, gyro), edges)
    out = {"route": n, "index": ri, "split": "val" if val else "train", "gyro_hz": SC.rate(r["gyro_t"]), "gnss_hz": SC.rate(r["gnss_t"]), "edges": edges,
           "route_t": grid, "route_R": R, "route_V": V, "episodes": []}
    if val:
        for wi in range(len(grid) // SC.WIN):
            g = grid[wi * SC.WIN:(wi + 1) * SC.WIN]
            sw = SC.cut(sig, g[0] - 4.0, g[-1] + 2.0)

            def add(fam, rep, res, t_on):
                Rw, Vw = stack(res, edges)
                out["episodes"].append({"window": wi, "family": fam, "rep": rep, "t": g, "R": Rw, "V": Vw, "onset_t": t_on})
            add("none", 0, SC.residuals(sw, g, lags, gyro), np.nan)
            for ai, a in enumerate(SC.ATTACKS):
                for rep in range(SC.REPS):
                    rng = np.random.default_rng([SEED, 77, 5, ri, wi, ai, rep])
                    t_on = float(g[0] + ONSET)
                    _ = rng.uniform(SC.ON_LO, SC.ON_HI)          # keeps the draw pattern of WP6 S2 / WP7 S2 (onset draw replaced by the fixed onset)
                    s2, sev = SC.attack(sw, a, t_on, rng)
                    add(a, rep, SC.residuals(s2, g, lags, gyro), t_on)
    return out


def main(argv):
    CACHE.mkdir(parents=True, exist_ok=True)
    train, val = lock_routes()
    allr = sorted(train + val)
    assert len(allr) == 21
    sm = json.loads((ROOT / "results" / "WP6" / "s1_sigma_models.json").read_text())["comma_R"]
    lags, gyro = sm["lags"], (sm["gyro"]["axis"], sm["gyro"]["sign"])
    for ri, n in enumerate(allr):
        if argv and n not in argv:
            continue
        f = CACHE / f"comma_{n}.pkl"
        if f.exists():
            log("skip", n)
            continue
        rec = build_route(n, ri, n in val, lags, gyro)
        tmp = f.with_suffix(".tmp")
        pickle.dump(rec, open(tmp, "wb"), protocol=4)
        tmp.replace(f)
        log("done", n, rec["split"], "grid", len(rec["route_t"]), "episodes", len(rec["episodes"]), f"gyro {rec['gyro_hz']:.0f} Hz")


if __name__ == "__main__":
    main(sys.argv[1:])
