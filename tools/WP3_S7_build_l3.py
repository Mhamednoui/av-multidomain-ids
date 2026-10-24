"""WP3 S7: L3 object feature tables (base statistics + track class) from the cached S4 object tables, one pickle per kind and drive in
../data_extra/cache_v3/WP3/S7/ (resumable). Usage: python -u -W ignore tools/WP3_S7_build_l3.py [clean att_val att_test ep_test]"""
import json
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS
from lidar import calibration as C
from lidar import ego
from lidar import learned as L
from lidar.data import CACHE, DRIVES, TEST, VAL, cache_size_gb

S4ROOT = CACHE / "S4" / (json.loads((RESULTS / "WP3" / "S4" / "variant_choice.json").read_text())["variant"] + "_t")
OUT = CACHE / "S7"
KINDS = {"clean": DRIVES, "att_val": VAL, "att_test": TEST, "ep_test": TEST}


def job(args):
    kind, d = args
    f = OUT / f"l3_{kind}_{d}.pkl"
    if f.exists():
        return kind, d, -1
    calib = C.load_calib(RESULTS / "WP3" / "S2" / "calibration_beta.npz")
    poses = ego.poses(d)
    z = pd.read_pickle(S4ROOT / f"{kind}_{d}.pkl")
    if kind == "clean":
        ref = z
    else:
        ref = pd.read_pickle(S4ROOT / f"clean_{d}.pkl")
    F = L.drive_features(z["objs"], z["scans"], ref["objs"], ref["scans"], calib, poses, episodic=kind.startswith("ep"))
    pd.to_pickle({"F": F, "scans": z["scans"][["drive", "idx", "scan", "attack"] + [c for c in ("ep", "step", "n_inj") if c in z["scans"].columns]]}, f)
    return kind, d, len(F)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    kinds = sys.argv[1:] or list(KINDS)
    todo = [(k, d) for k in kinds for d in KINDS[k]]
    t0 = time.time()
    with Pool(3) as pool:
        for kind, d, n in pool.imap_unordered(job, todo):
            print(kind, d, n, f"{time.time() - t0:.0f}s cache {cache_size_gb():.2f} GB", flush=True)
