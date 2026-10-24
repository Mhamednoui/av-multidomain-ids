"""WP3 S9 dry run of the analysis code on VALIDATION frames (no test data): clean = the out-of-fold reference scans of the 3 validation drives,
attacks = validation attacks, episodes = world-fixed validation episodes. Confirms the code path before the single test run; numbers are not used.
Usage: python -u -W ignore tools/WP3_S9_dryrun.py"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP3_S9_lib as L
from WP3_S9_analysis import analyse
from common.config import RESULTS
from lidar.data import drives_of

RES = RESULTS / "WP3" / "S9"


def main():
    fr = pd.read_pickle(L.S9C / "dev_frames.pkl")
    dev = json.loads((RES / "dev.json").read_text())
    method = dev["V1"]["chosen"]
    fr["clean"] = fr["ref"][fr["ref"].drive.isin(drives_of("val"))]
    # the validation world-fixed episodes were built with 3 episodes per kind, S6 used 2: only the first kind has identical draws
    fr["epw"] = fr["epw"][fr["epw"].attack == "epW_replace_near"]
    res, st = analyse(fr, method, optional={"density in L2a": L.HEAD_DENS})
    res.pop("_scores")
    h = res["headline"]
    print("method", method, "FA", h["fa"], "mean_phys", h["mean_phys"], {a: round(v["det"], 3) for a, v in h["det"].items()})
    print("earns", {c: (round(v["largest_loss_when_removed"], 3), v["earns_place"]) for c, v in res["earns_place"].items()})
    print("epw", {k: (v["detected_3s"], v["median_first_alert_s"]) for k, v in res["episodes"]["epw"]["stack"]["kinds"].items()},
          "false-episode", res["episodes"]["epw"]["stack"]["false_episode_rate"])
    (RES / "dryrun_val.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
