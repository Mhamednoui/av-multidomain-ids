"""WP4 S5 prep: the 76 flow features of the D10 stage rows, aligned to the row order of ../data_extra/cache_v3/WP4/S3/D10_stage.pkl.
Output: ../data_extra/cache_v3/WP4/S5/D10_X.npy (float32, n x 76, inf -> NaN), D10_X_cols.json. Usage: python -u -W ignore tools/WP4_S5_prep.py"""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from network.flows import FEATURES

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4")


def main():
    s3 = pd.read_pickle(os.path.join(B, "S3", "D10_stage.pkl"))[["file", "row"]]
    files = sorted(s3["file"].astype(str).unique())
    fcode = {f: i for i, f in enumerate(files)}
    key3 = s3["file"].astype(str).map(fcode).to_numpy("int64") * 10**8 + s3["row"].to_numpy("int64")
    X = np.full((len(s3), len(FEATURES)), np.nan, dtype=np.float32)
    seen = np.zeros(len(s3), bool)
    order = np.argsort(key3)
    ks = key3[order]
    for p in sorted(glob.glob(os.path.join(B, "D10", "stage", "*.pkl"))):
        d = pd.read_pickle(p, compression="gzip")
        f = d["file"].astype(str).iloc[0]
        if f not in fcode:
            print("skip", f); continue
        k = fcode[f] * 10**8 + d["row"].to_numpy("int64")
        i = np.searchsorted(ks, k)
        ok = (i < len(ks)) & (ks[np.clip(i, 0, len(ks) - 1)] == k)
        pos = order[i[ok]]
        v = d.loc[ok, FEATURES].to_numpy(np.float32)
        v[~np.isfinite(v)] = np.nan
        X[pos] = v
        seen[pos] = True
        print(f, len(d), int(ok.sum()), flush=True)
    print("aligned rows", int(seen.sum()), "of", len(s3))
    assert seen.all()
    out = os.path.join(B, "S5")
    os.makedirs(out, exist_ok=True)
    np.save(os.path.join(out, "D10_X.npy"), X)
    json.dump(FEATURES, open(os.path.join(out, "D10_X_cols.json"), "w"))


if __name__ == "__main__":
    main()
