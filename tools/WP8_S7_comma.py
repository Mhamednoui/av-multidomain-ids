"""WP8 S7: cross-domain residual tables and 120 s attack windows of the comma2k19 Chunk_2 routes (RAV4, H31 primary C): tools/WP8_S6_comma.build_route with the Chunk_2 folder.
Same edges, lags, gyro axis, windows, attacks, seeds [42, 77, 5, route index, window, attack, rep] as WP7 S2 / WP8 S6; route index = position in the sorted list of the 21 Chunk_2 routes.
Civic (Chunk_4) is NOT built: the Civic CAN wheel speed is not at 0xAA and no Civic decoder was written (stratum C2 not scored in S7, stated in the report).
Output ../data_extra/cache_v3/WP8/S7/comma_<route>.pkl (resumable). Run: python -u -W ignore tools/WP8_S7_comma.py [route ...]"""
import json
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

S7.open_guard()
import WP8_S6_comma as C6

T0 = time.time()
CHUNK2 = S7.DATA_EXTRA / "D22_comma2k19" / "Chunk_2"


def main(argv):
    S7.CACHE.mkdir(parents=True, exist_ok=True)
    C6.CHUNK = CHUNK2
    routes = sorted(r.replace("|", "_") for r in S7.h31()["domains"]["comma_vehicle_block"]["rav4"]["routes"])
    assert len(routes) == 21
    sm = json.loads((S7.ROOT / "results" / "WP6" / "s1_sigma_models.json").read_text())["comma_R"]
    lags, gyro = sm["lags"], (sm["gyro"]["axis"], sm["gyro"]["sign"])
    for ri, n in enumerate(routes):
        if argv and n not in argv:
            continue
        f = S7.CACHE / f"comma_{n}.pkl"
        if f.exists():
            print("skip", n, flush=True)
            continue
        rec = C6.build_route(n, ri, True, lags, gyro)
        tmp = f.with_suffix(".tmp")
        pickle.dump(rec, open(tmp, "wb"), protocol=4)
        tmp.replace(f)
        print(f"[{time.time() - T0:6.0f}s] done {n} grid {len(rec['route_t'])} episodes {len(rec['episodes'])} gyro {rec['gyro_hz']:.0f} Hz", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
