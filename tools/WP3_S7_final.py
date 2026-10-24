"""WP3 S7 VERDICT run (test touched once): scores the test sets with the frozen physics layers (S4 / S6 / L1), L3 and the three L4 variants,
saves the score store (results are NOT looked at before the run ends), then runs the analysis. Reads the validation choices
(dev_l3.json, dev_l4.json, dev_stack.json) and the out-of-fold / final models of WP3_S7_oof.py.
Usage: python -u -W ignore tools/WP3_S7_final.py   (analysis only, from the saved store: --analysis-only)"""
import json
import pickle
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP3_S7_stack as ST
from WP3_S7_analysis import analyse
from common.config import RESULTS

RES = RESULTS / "WP3" / "S7"
STORE = ST.CACHE / "S7" / "final_frames.pkl"


def main():
    t0 = time.time()
    if "--analysis-only" in sys.argv:
        fr = pd.read_pickle(STORE)
    else:
        fr = ST.physics("final")
        print("physics", {k: v.shape for k, v in fr.items()}, f"{time.time() - t0:.0f}s", flush=True)
        fr = ST.add_l3(fr, "final")
        for name in ("l4", "l4_nophantom", "l4_v2"):
            fr = ST.add_l4(fr, "final", name)
        pd.to_pickle(fr, STORE)
        print("store written", {k: v.shape for k, v in fr.items()}, f"{time.time() - t0:.0f}s", flush=True)
    combiner = json.loads((RES / "dev_stack.json").read_text())["combiner"]
    res = analyse(fr, combiner)
    res["seconds"] = time.time() - t0
    (RES / "final.json").write_text(json.dumps(res, indent=1, default=float))
    print("done", res["seconds"])


if __name__ == "__main__":
    main()
