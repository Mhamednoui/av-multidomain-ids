"""WP9 B4 LiDAR: per-scan scores of the v3.1 stack (WP8 S3 config tail2h|zmulti|E7, per-layer-budget union, B 1%) from the WP8 S3 frame, leave-one-drive-out over the 10 V31_val drives.
frame = results/WP8/S3/frame.pkl (per-scan statistics of the clean scans of the 23 drives and of the 9 attack kinds of the 10 V31_val drives, built by WP8 S3 with lidar.fast / numba, identical outputs;
no H31 scan is in it). Fold d: stack fitted on the clean reference scans of all drives except d (tools/WP8_S3_an.fit_fold), scores of d's clean scans (i >= 1) and attacked scans.
Output (DataFrame): drive, i, attack ('clean' or kind), score (ECDF of the union statistic), alarm (native 1% rule). Read-only on WP8 files.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

import WP8_S3_an as A

FRAME = ROOT / "results" / "WP8" / "S3" / "frame.pkl"


def v31_scores(drives):
    cfg = json.loads((ROOT / "results" / "WP8" / "S3" / "selection_r3.json").read_text())["chosen_cfg"]
    cfg = dict(cfg, bud=tuple(cfg["bud"]))
    frame = pd.read_pickle(FRAME)
    out = []
    for d in drives:
        st, ref = A.fit_fold(frame, [d], cfg)
        for kind in ("clean", "att"):
            df = frame[(frame.kind == kind) & (frame.drive == d)]
            if kind == "clean":
                df = df[df.i >= 1]
            raw = A.layer_raw(ref, df, st.cs, st.as_)
            sc, al = st.score(raw), st.alarm(raw)
            o = pd.DataFrame({"drive": d, "i": df.i.to_numpy(), "attack": "clean" if kind == "clean" else df.attack.to_numpy(), "score": sc, "alarm": al})
            out.append(o)
    return pd.concat(out, ignore_index=True), cfg
