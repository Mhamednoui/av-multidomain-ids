"""WP8 S4 prep: rebuild the D10 pre-dedup stage stream (the WP4 caches were deleted) and write a TRAIN+VAL-only copy for all S4 work.

The WP4 S1 build (tools/WP4_s1_build.py D10, same code, same split) was re-run first; this script calls tools/WP4_S3_prep.build for D10 only (D23 is H31 material,
never touched in S4) and then drops every 'test' and 'gap' row: S4 choices use split in {train, val} (V31_val network = D10 val, locks/V31_val.json). The unfiltered
file D10_stage.pkl stays in ../data_extra/cache_v3/WP4/S3/ for S7 (not read by S4 tools).
Output: ../data_extra/cache_v3/WP8/S4/D10_trainval_stage.pkl ; results/WP8/S4/prep.json (counts compared with results/WP4/s3_prep.json).
Usage: python -u -W ignore -I tools/WP8_S4_prep.py
"""
import glob
import json
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import WP4_S3_prep as P  # noqa: E402

OUT = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP8", "S4")


def main():
    info = P.build("D10", sorted(glob.glob(os.path.join(P.B, "D10", "stage", "*.pkl"))),
                   sorted(glob.glob(os.path.join(P.B, "D10", "final", "*.pkl"))), "D10_stage.pkl")
    old = json.load(open(os.path.join(ROOT, "results", "WP4", "s3_prep.json")))["D10"]
    same = info["by_split"] == old["by_split"] and info["by_family_split"] == old["by_family_split"]
    d = pd.read_pickle(os.path.join(P.OUT, "D10_stage.pkl"))
    d = d[d["split"].astype(str).isin(["train", "val"])].reset_index(drop=True)
    os.makedirs(OUT, exist_ok=True)
    d.to_pickle(os.path.join(OUT, "D10_trainval_stage.pkl"))
    res = {"rebuilt_counts_equal_v3_s3_prep": bool(same), "n_trainval": int(len(d)), "by_split": d["split"].astype(str).value_counts().to_dict()}
    os.makedirs(os.path.join(ROOT, "results", "WP8", "S4"), exist_ok=True)
    json.dump(res, open(os.path.join(ROOT, "results", "WP8", "S4", "prep.json"), "w"), indent=1)
    print(res, flush=True)


if __name__ == "__main__":
    main()
