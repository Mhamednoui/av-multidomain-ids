"""WP8 S7: vehicle-block records (cross-domain residual tables, GPS-domain tick series, simulated accelerometer) of the 13 H31 KITTI drives: tools/WP8_S6_kitti.build_drive with the
H31 path patches (same seeds, same attacks: clean + drift / accel_drift / doppler_spoof / meaconing / lidar_scale / bias / yaw / can_scale / offset / freeze / gps_can x 10 phases, onset fix 3),
frozen v3 GPS domain and frozen v3 CAN decoder. Needs the LiDAR odometry caches (tools/WP8_S7_odom.py). Output: ../data_extra/cache_v3/WP8/S7/kitti_<drive>.pkl (resumable).
Run: python -u -W ignore tools/WP8_S7_kitti.py [drive ...]"""
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

S7.open_guard()
S7.patch_h31_paths()
import WP8_S6_kitti as K6

from can.domain import CanDomain
from gps.domain import GPSDomain

T0 = time.time()


def main(argv):
    S7.CACHE.mkdir(parents=True, exist_ok=True)
    dom_can = CanDomain.load(S7.ROOT / "results" / "WP2" / "s7_domain")
    gdom = GPSDomain.load(S7.ROOT / "results" / "WP1" / "frozen_gps")
    for d, (name, stratum) in sorted(S7.kitti_drives().items()):
        if argv and d not in argv:
            continue
        f = S7.CACHE / f"kitti_{d}.pkl"
        if f.exists():
            print("skip", d, flush=True)
            continue
        recs = K6.build_drive(d, dom_can, gdom, True)
        tmp = f.with_suffix(".tmp")
        pickle.dump({"drive": d, "name": name, "stratum": stratum, "records": recs}, open(tmp, "wb"), protocol=4)
        tmp.replace(f)
        print(f"[{time.time() - T0:6.0f}s] done {d} {name} {stratum} {len(recs)} records", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
