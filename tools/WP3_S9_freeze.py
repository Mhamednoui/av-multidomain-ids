"""WP3 S9: fit and save the deployable LiDAR domain (lidar/domain.py) in results/WP3/S9/frozen_lidar/. Uses ONLY clean train+val data (no test
table is loaded): layers fitted on the 16 train+val drives, stack = the combiner chosen on validation (results/WP3/S9/dev.json) on the
out-of-fold clean reference. Usage: python -u -W ignore tools/WP3_S9_freeze.py"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP3_S9_lib as L
from WP3_S4_build import prm
from common.config import RESULTS
from lidar import combine as K
from lidar.domain import COLS, IntensityModel, LidarDomain

RES = RESULTS / "WP3" / "S9"
S2 = RESULTS / "WP3" / "S2"


def main():
    t0 = time.time()
    dev = json.loads((RES / "dev.json").read_text())
    method, dens = dev["V1"]["chosen"], dev["V2"]["density_kept"]
    F = L.fit_layers("final", with_test=False)
    ref = L.ref_frame(F)
    if dens:
        ref["raw_L2a"] = ref["raw_L2aF"]
    stack = K.Stack(COLS, method, 0.01).fit(ref)
    parts = {"table": None, "calib": F["calib"], "model": F["model"] if dens else IntensityModel.from_model(F["model"]), "prm": prm(), "l1": F["l1"], "a2": F["a2f"] if dens else F["a2"],
             "l2c": F["l2c"], "l2d": F["l2d"]}
    meta = {"combiner": method, "density_part_in_L2a": bool(dens), "reference_scans": int(len(ref)), "reference_drives": sorted(ref.drive.unique()),
            "fit": "layers fitted on clean train+val drives only; no attack label, no test data", "segment_params": prm(),
            "ego_pose": "planar (x, y, yaw) of every scan, KITTI: OXTS via lidar.ego.poses"}
    from lidar import geometry as G
    parts["table"] = G.RingTable.load(S2 / "ring_table.json")
    dom = LidarDomain(parts, stack, meta)
    dom.save(RES / "frozen_lidar", S2 / "ring_table.json", S2 / "calibration_beta.npz")
    ref.to_pickle(L.S9C / "ref_frame.pkl")
    print("saved", RES / "frozen_lidar", f"{time.time() - t0:.0f}s", "method", method, "density", dens, "threshold", stack.threshold)


if __name__ == "__main__":
    main()
