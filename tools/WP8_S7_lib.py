"""WP8 S7 shared helpers: paths, journal, sha256, H31 path patches, exposure labels.

H31 KITTI drives live in ../data_extra/D04b_kitti_raw_v31/<name>_sync/{oxts,velodyne_points}/ (flat layout); the v3 loaders (gps/stream.py, lidar/data.py, lidar/ego.py,
gps/lidar_odom.py cache file) only know the 23 v3 drives under ../data_extra/kitti_raw/. `patch_h31_paths()` wraps those four functions at run time (v3 files untouched):
a drive id of H31 (4-digit number; no number collides with a v3 drive) is resolved to the D04b folder, the LiDAR odometry cache of an H31 drive goes to
../data_extra/cache_v3/WP8/S7/odom/ instead of results/WP1/cache. `open_guard()` disables the S2-S6 G1 tripwire (WP8_lib.assert_not_h31) inside a S7 process: S7 is the one step that reads H31.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

DATA_EXTRA = ROOT.parent / "data_extra"
D04B = DATA_EXTRA / "D04b_kitti_raw_v31"
CACHE = DATA_EXTRA / "cache_v3" / "WP8" / "S7"
OUT = ROOT / "results" / "WP8" / "S7"
PARTS = OUT / "parts"
SCORES = ROOT / "results" / "WP8" / "scores" / "S7"
LOGS = ROOT / "results" / "WP8" / "logs"
JOURNAL = ROOT / "notes" / "WP8_journal.md"

EXPOSURE = {"fresh": "fresh H31", "reused": "re-used test (exposure n+1)", "site": "same site-day as calibration", "mixed": "partially fresh (vehicle block fresh, CAN / network / V2X streams re-used)"}


def journal(step, what, state=""):
    """One line in notes/WP8_journal.md (written BEFORE the action it announces)."""
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')[:-2]}:00 | {step} | {what} | {state}\n"
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(line)
    print(line, end="", flush=True)


def sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def write_json(obj, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else (list(o) if isinstance(o, (set, tuple)) else str(o))))
    tmp.replace(path)


def h31():
    return json.loads((ROOT / "locks" / "H31.json").read_text(encoding="utf-8"))


def kitti_drives():
    """{4-digit id: (full drive name, stratum)} of the 13 H31 KITTI drives (read from the lock; this reads the lock, not a data file)."""
    out = {}
    for dr in h31()["domains"]["kitti_vehicle_block"]["drives"]:
        name = dr["drive"]
        out[name.split("_drive_")[1]] = (name, dr["stratum"])
    return out


def open_guard():
    """S7 reads H31: disable the S2-S6 G1 tripwire in this process (logged)."""
    import WP8_lib as L8
    L8.assert_not_h31 = lambda items: True
    print("[S7] G1 guard disabled in this process (S7 scores H31)", flush=True)


def patch_h31_paths():
    from gps import lidar_odom as LO
    from gps import stream as GS
    from lidar import data as LD
    from lidar import ego as LE
    names = {k: v[0] for k, v in kitti_drives().items()}
    o_oxts, o_drive, o_cache = GS.oxts_dir, LD.drive_dir, LO.cache_file

    def oxts_dir(d):
        return D04B / (names[d] + "_sync") / "oxts" / "data" if d in names else o_oxts(d)

    def drive_dir(d):
        return D04B / (names[d] + "_sync") / "velodyne_points" / "data" if d in names else o_drive(d)

    def cache_file(d, folder=None):
        if d in names and folder is None:
            return CACHE / "odom" / f"lidar_odom_{d}.npz"
        return o_cache(d, folder)
    GS.oxts_dir, LD.drive_dir, LE.drive_dir, LO.cache_file = oxts_dir, drive_dir, drive_dir, cache_file
    return names


def scan_times(d):
    """Velodyne scan times (s) on the OXTS clock of GS.load_oxts (as tools/WP1_S5_odom_run.scan_times), for an H31 drive."""
    import pandas as pd
    names = kitti_drives()
    r = D04B / (names[d][0] + "_sync")
    rd = lambda p: pd.to_datetime(pd.read_csv(p, header=None)[0])
    t0 = rd(r / "oxts" / "timestamps.txt").iloc[0]
    return (rd(r / "velodyne_points" / "timestamps.txt") - t0).dt.total_seconds().to_numpy()
