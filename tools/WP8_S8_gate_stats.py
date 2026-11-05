"""WP8 S8 step 3a: where does the pre-registered reference-health gate (system/health31.py) fire? Per drive (H31, V31_val, v3 train): share of degraded OXTS frames, of 1 Hz ticks (10 phases, grid
ph / 10 + k as in the vehicle builders) and of LiDAR scans; the pre-registered rules A1 / A2 (<= 0.5 % on V31_val / train) and the threshold sensitivity (range of POS_ACC_MAX giving the same set of
gated drives). Reads OXTS accuracy fields only. Output results/WP8/S8/gate_stats.json. Run: python -u -W ignore tools/WP8_S8_gate_stats.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

S7.open_guard()
S7.patch_h31_paths()
from gps import stream as GS
from system import health31 as H


def main():
    v = json.loads((S7.ROOT / "locks" / "V31_val.json").read_text())["domains"]["kitti_vehicle_block"]
    sets = [("H31", sorted(S7.kitti_drives())), ("V31_val", v["val"]), ("train", v["train"])]
    out = {"rule": {"pos_acc_max_m": H.POS_ACC_MAX, "vel_acc_max_mps": H.VEL_ACC_MAX}, "drives": {}}
    allp = {}
    for s, ids in sets:
        for d in ids:
            t, pa, va = H.read_oxts_health(GS.oxts_dir(d))
            deg = H.degraded_frames(pa, va)
            ticks = np.concatenate([np.arange(ph / GS.PHASES, t[-1] + 1e-9, 1.0) for ph in range(GS.PHASES)])
            g = np.concatenate([H.tick_gate(t, deg, np.arange(ph / GS.PHASES, t[-1] + 1e-9, 1.0)) for ph in range(GS.PHASES)])
            out["drives"][f"{s}:{d}"] = {"set": s, "frames": int(len(t)), "degraded_frames": int(deg.sum()), "ticks_all_phases": int(len(ticks)), "gated_ticks": int(g.sum()),
                                         "gated_tick_share": float(g.mean()), "pos_acc_min": float(pa.min()), "pos_acc_max": float(pa.max()), "vel_acc_max": float(va.max())}
            allp[f"{s}:{d}"] = (float(pa.min()), float(pa.max()), float(va.max()))
    healthy = [(k, x) for k, x in allp.items() if not out["drives"][k]["degraded_frames"]]
    bad = [k for k in allp if out["drives"][k]["degraded_frames"]]
    for s in ("V31_val", "train", "H31"):
        dd = [r for r in out["drives"].values() if r["set"] == s]
        out[f"summary_{s}"] = {"drives": len(dd), "drives_gated": int(sum(r["degraded_frames"] > 0 for r in dd)), "frames": int(sum(r["frames"] for r in dd)),
                               "degraded_frames": int(sum(r["degraded_frames"] for r in dd)), "gated_tick_share": float(sum(r["gated_ticks"] for r in dd) / sum(r["ticks_all_phases"] for r in dd))}
    # sensitivity: POS_ACC_MAX in (max healthy pos_acc, min pos_acc of the gated drives) gives the same gated set (velocity rule off)
    hi_healthy = max(x[1] for _, x in healthy)
    lo_bad = {k: allp[k][0] for k in bad}
    out["sensitivity_pos_acc_m"] = {"largest_pos_acc_on_ungated_drives": hi_healthy, "gated_drives": bad, "smallest_pos_acc_of_gated_drives": lo_bad,
                                    "note": "any POS_ACC_MAX between the first and the min of the second value gives the same gated drives and ticks on the 36 drives (velocity rule included or not)"}
    S7.write_json(out, S7.ROOT / "results" / "WP8" / "S8" / "gate_stats.json")
    for k in ("summary_V31_val", "summary_train", "summary_H31", "sensitivity_pos_acc_m"):
        print(k, json.dumps(out[k]))


if __name__ == "__main__":
    main()
