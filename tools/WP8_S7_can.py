"""WP8 S7 CAN: the 15 ROAD test captures (H31 'CAN re-used', exposure n+1) and the 2 ROAD accelerator captures (fresh, no injected frames: capture level) through
IncrementalCan (v3.1 CanRunner31 core) vs the v3 batch CanDomain (equality, per-window timing, growth ratio) = tools/WP8_S5_can.run_capture with the S7 output folders.
The CAN domain is the same frozen v3 object in v3 and v3.1 (results/WP2/s7_domain); IncrementalCan is bit-identical to the batch scoring, so the v3 and v3.1 CAN Evidence are the same numbers.
Output: results/WP8/S7/parts/can_test_<capture>.json, scores results/WP8/scores/S7/can_test_<capture>.npz (resumable). Run: python -u -W ignore tools/WP8_S7_can.py [--only name ...]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import WP8_S5_can as C5

from can import adapters as A
from can.domain import CanDomain


def main():
    only = set(sys.argv[sys.argv.index("--only") + 1:]) if "--only" in sys.argv else None
    lock = S7.h31()["domains"]["can"]
    names = [Path(x["path"]).stem for x in lock["reused"]["road_test"]] + [Path(x["path"]).stem for x in lock["fresh"]["road_accelerator"]["files"]]
    if only:
        names = [n for n in names if n in only]
    C5.SC = S7.SCORES
    caps = A.road_captures()
    dom = CanDomain.load(S7.ROOT / "results" / "WP2" / "s7_domain")
    S7.PARTS.mkdir(parents=True, exist_ok=True)
    for name in names:
        part = S7.PARTS / f"can_test_{name}.json"
        if part.exists():
            C5.log(name, "done already")
            continue
        S7.journal("S7", f"CAN capture {name}: start (IncrementalCan vs batch)", f"part {part.name}")
        res = C5.run_capture(dom, name, caps, "test")
        res["exposure"] = S7.EXPOSURE["fresh"] if "accelerator" in name else S7.EXPOSURE["reused"]
        S7.write_json(res, part)
        C5.log(name, {k: res[k] for k in ("windows_batch", "windows_inc", "max_abs_diff", "alarm_mismatch", "id_mismatch", "reason_mismatch", "motion_mismatch", "window_ms")})
        S7.journal("S7", f"CAN capture {name}: done", f"mismatches {res['alarm_mismatch']}/{res['id_mismatch']}, p99 {res['window_ms']['p99']:.1f} ms")
    allr = [json.load(open(p)) for p in sorted(S7.PARTS.glob("can_test_*.json"))]
    S7.write_json(allr, S7.OUT / "can_summary.json")


if __name__ == "__main__":
    main()
