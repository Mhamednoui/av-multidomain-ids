"""WP4 S5 prep D23: fixed-seed stratified sample of the cleaned CSE-CIC-IDS2018 flows (all days, final tables) for the L3 transfer test.
Drawn ONCE, before any model is scored: benign train 400k, benign val 300k, benign test 500k (uniform over benign rows of the split), attack flows of val / test capped
at 60k per (family, split) (uniform). Splits are the S1 time splits. Columns: file, day, split, family, dst_port, protocol + the 76 features (float32).
Output ../data_extra/cache_v3/WP4/S5/D23_eval.pkl. Usage: python -u -W ignore tools/WP4_S5_prep_d23.py"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import SEED
from network.flows import FEATURES

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4")
KEEP = ["file", "day", "split", "family", "dst_port", "protocol"] + FEATURES
QUOTA = {("BENIGN", "train"): 400_000, ("BENIGN", "val"): 300_000, ("BENIGN", "test"): 500_000}
CAP = 60_000
RATE = {"train": 0.08, "val": 0.2, "test": 0.3}


def main():
    rng = np.random.RandomState(SEED)
    parts, tot = [], {}
    for p in sorted(glob.glob(os.path.join(B, "D23", "final", "*.pkl"))):
        d = pd.read_pickle(p, compression="gzip")[KEEP]
        d = d[d["split"].astype(str).isin(["train", "val", "test"])]
        fam, sp = d["family"].astype(str).to_numpy(), d["split"].astype(str).to_numpy()
        ben = fam == "BENIGN"
        for k, c in pd.Series(list(zip(fam, sp))).value_counts().items():
            tot[k] = tot.get(k, 0) + int(c)
        rate = np.array([RATE[x] for x in ("train", "val", "test")])[pd.Categorical(sp, ["train", "val", "test"]).codes]
        keep = np.where(ben, rng.rand(len(d)) < rate, sp != "train")   # attack flows of the train split are not needed (normal-only models)
        e = d.loc[keep].copy()
        for c in ("file", "day", "split", "family"):
            e[c] = e[c].astype(str)
        parts.append(e)
        print(os.path.basename(p), len(d), len(e), flush=True)
    e = pd.concat(parts, ignore_index=True)
    del parts
    out = []
    for (f, sp), g in e.groupby(["family", "split"]):
        q = QUOTA.get((f, sp), CAP)
        if len(g) > q:
            g = g.iloc[np.sort(rng.choice(len(g), q, replace=False))]
        out.append(g)
    e = pd.concat(out, ignore_index=True)
    for c in FEATURES:
        e[c] = e[c].astype("float32")
    e["dst_port"] = pd.to_numeric(e["dst_port"], errors="coerce").fillna(-1).astype("int32")
    e["protocol"] = pd.to_numeric(e["protocol"], errors="coerce").fillna(-1).astype("int16")
    e.to_pickle(os.path.join(B, "S5", "D23_eval.pkl"))
    print("full counts (family, split):", {k: v for k, v in sorted(tot.items())})
    print(e.groupby(["family", "split"]).size().unstack(1).fillna(0).astype(int))
    print("rows", len(e), "GB", e.memory_usage().sum() / 1e9)


if __name__ == "__main__":
    main()
