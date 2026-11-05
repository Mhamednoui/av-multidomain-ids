"""WP8 S7 CAN timing re-run on an otherwise idle machine (LABELLED re-run of the TIMING only; the first run, results/WP8/S7/can_summary.json, was taken while 4-5 other processes ran and p99 exceeded 150 ms on
several captures). Same code (tools/WP8_S5_can.run_capture), same captures; Evidence equality is re-checked; per-window scores go to a scratch folder (not the saved H31 scores). Both timings are reported.
Output: results/WP8/S7/can_idle_timing.json. Added after the freeze commit (hash in results/WP8/S7/freeze_addendum.json). Run: python -u -W ignore tools/WP8_S7_can_idle.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import WP8_S5_can as C5

from can import adapters as A
from can.domain import CanDomain


def others():
    r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout.strip().splitlines()
    return max(len([x for x in r if "python" in x]) - 1, 0)


def main():
    S7.open_guard()
    lock = S7.h31()["domains"]["can"]
    names = [Path(x["path"]).stem for x in lock["reused"]["road_test"]] + [Path(x["path"]).stem for x in lock["fresh"]["road_accelerator"]["files"]]
    C5.SC = Path(tempfile.mkdtemp(prefix="can_idle_"))
    caps = A.road_captures()
    dom = CanDomain.load(S7.ROOT / "results" / "WP2" / "s7_domain")
    out = []
    for n in names:
        S7.journal("S7", f"CAN idle timing {n}: start", f"other python processes {others()}")
        r = C5.run_capture(dom, n, caps, "idle")
        out.append({"name": n, "p99_ms": r["window_ms"]["p99"], "median_ms": r["window_ms"]["median"], "max_ms": r["window_ms"]["max"], "growth": r.get("growth"), "alarm_mismatch": r["alarm_mismatch"], "id_mismatch": r["id_mismatch"],
                    "reason_mismatch": r["reason_mismatch"], "motion_mismatch": r["motion_mismatch"], "max_abs_diff": r["max_abs_diff"], "other_python_processes": others()})
        S7.write_json(out, S7.OUT / "can_idle_timing.json")
    S7.journal("S7", "CAN idle timing: done", f"p99 max {max(o['p99_ms'] for o in out):.1f} ms")


if __name__ == "__main__":
    main()
