"""WP8 S7 packing (format conversion only, no scoring): the saved ROAD test per-window scores (results/WP8/scores/S7/can_test_<capture>.npz) -> the CAN source list of the system composites
(../data_extra/cache_v3/WP8/S7/can.pkl), same layout as WP8_S2_build.stage_can. Accelerator captures (no injected frames) are not composite sources. Family = capture name without '_attack[_n]'.
Added after the freeze commit (hash in results/WP8/S7/freeze_addendum.json)."""
import pickle
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

out = []
for f in sorted(S7.SCORES.glob("can_test_*.npz")):
    name = f.stem[len("can_test_"):]
    if "accelerator" in name:
        continue
    z = np.load(f)
    amb = name.startswith("ambient")
    out.append({"name": name, "group": name, "kind": "clean" if amb else "attack", "family": "none" if amb else re.sub(r"_attack(_\d+)?", "", name),
                "score": z["score"].astype(np.float32), "dom_alarm": z["alarm"].astype(bool), "label": z["y"] > 0,
                "layers": np.column_stack([z[f"score_{l}"] for l in ("L1", "L3c", "L3d")]).astype(np.float32),
                "layer_alarm": np.column_stack([z[f"alarm_{l}"] for l in ("L1", "L3c", "L3d")]).astype(bool)})
    print(name, len(out[-1]["score"]), int(out[-1]["label"].sum()), out[-1]["family"])
pickle.dump({"series": out, "layer_names": ["can.L1", "can.L3c", "can.L3d"]}, open(S7.CACHE / "can.pkl", "wb"), protocol=4)
