"""WP3 S7 validation round for the stack: physics layers (L1, L2a intensity, L2c, L2d) with and without L3 / L4, label-free combiner
(max or noisy-or of ECDF ranks) chosen on VALIDATION. Models fitted on the train drives, reference = clean validation scans (3 drives),
sets = validation attacks. Test is not read. Writes results/WP3/S7/dev_stack.json. Usage: python -u -W ignore tools/WP3_S7_dev_stack.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP3_S7_lib import *  # noqa
import WP3_S7_stack as ST
from common.config import RESULTS
from lidar import learned_eval as LE

RES = RESULTS / "WP3" / "S7"
PHYSICS = ["raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"]
STACKS = {"physics": PHYSICS, "physics+L3": PHYSICS + ["raw_L3"], "physics+L4": PHYSICS + ["raw_L4"], "physics+L3+L4": PHYSICS + ["raw_L3", "raw_L4"],
          "L3": ["raw_L3"], "L4": ["raw_L4"]}


def main():
    t0 = time.time()
    ch = json.loads((RES / "dev_l4.json").read_text())["choice"]
    tr = drives_of("train")
    X, y, _ = train_set(tr)
    model = L4.fit_xgb(X, y, ch["params"], ch["n_trees"])
    fr = ST.physics("dev")
    fr = ST.add_l3(fr, "dev")
    fr = ST.add_l4(fr, "dev", "l4", model)
    print("frames", {k: v.shape for k, v in fr.items()}, f"{time.time() - t0:.0f}s", flush=True)
    ref, att = fr["ref"], fr["att"]
    out = {"n_ref_scans": int(len(ref)), "stacks": {}}
    for method in ("max", "noisy_or"):
        for name, cols in STACKS.items():
            r = LE.evaluate_stack(ref, ref, att, cols, method)
            r.pop("alarm"), r.pop("ref_scores")
            r["mean_phys"] = float(np.mean([r["det"][a] for a in LE.PHYS]))
            out["stacks"][f"{name}/{method}"] = r
            print(method, name, f"mean_phys {r['mean_phys']:.3f}", {a: round(r["det"][a], 3) for a in LE.PHYS}, flush=True)
    score = {m: float(np.mean([out["stacks"][f"{n}/{m}"]["mean_phys"] for n in ("physics", "physics+L3", "physics+L4", "physics+L3+L4")]))
             for m in ("max", "noisy_or")}
    out["combiner_scores"] = score
    out["combiner"] = max(score, key=score.get)
    print("COMBINER", out["combiner"], score)
    (RES / "dev_stack.json").write_text(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
