"""WP8 S7 POST-HOC DIAGNOSTIC (labelled; NOT a verdict row, NOT used for M4): the same frozen v3 and v3.1 systems on the same construction after removing KITTI H31 drive 2011_09_26_drive_0093
from the K sources (its clean GPS and cross alarms fire on 94 % / 91 % of the ticks and dominate the clean-timeline false alarms). Written after the H31 scoring, after the M4 numbers were seen.
No code of the sim changes: the filtered source folder is passed through WP8_S7_lib.CACHE. Output: results/WP8/S7/system_h31_no0093.json (tag h31_no0093).
Run: python -u -W ignore tools/WP8_S7_posthoc.py"""
import pickle
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

DROP = "0093"


def main():
    src = S7.CACHE
    dst = src / "no0093"
    dst.mkdir(exist_ok=True)
    for f in ("cveh.pkl", "can.pkl", "v2x.pkl", "net.pkl"):
        shutil.copy(src / f, dst / f)
    k = pickle.load(open(src / "kveh.pkl", "rb"))
    k["series"] = {key: v for key, v in k["series"].items() if key[0] != DROP}
    pickle.dump(k, open(dst / "kveh.pkl", "wb"), protocol=4)
    lid = pickle.load(open(src / "lidar.pkl", "rb"))
    lid["drives"] = {d: r for d, r in lid["drives"].items() if d != DROP}
    pickle.dump(lid, open(dst / "lidar.pkl", "wb"), protocol=4)
    S7.journal("S7", "POST-HOC diagnostic (labelled, not a verdict): sim without KITTI drive 0093, tag h31_no0093", "tools/WP8_S7_posthoc.py")
    S7.CACHE = dst
    import WP8_S7_sim as T
    sys.argv = ["x", "--material", "h31", "--tag", "h31_no0093", "--runs", "v31,v3"]
    T.main()


if __name__ == "__main__":
    main()
