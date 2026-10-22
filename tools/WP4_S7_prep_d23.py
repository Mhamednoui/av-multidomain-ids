"""WP4 S7 prep D23: the S5 fixed-seed sample of cleaned CSE-CIC-IDS2018 flows (tools/WP4_S5_prep_d23.py, same code path and seed 42, so the same rows) rebuilt with the
columns file, row, ts (so rows can be looked up in the Tue-20-02 stage stream and ordered in time). Check: the rebuilt table must equal ../data_extra/cache_v3/WP4/S5/D23_eval.pkl
on the shared columns (same order, same values); then it is saved as S7/d23_eval.pkl and the S5 copy can be deleted.
Usage: python -u -W ignore tools/WP4_S7_prep_d23.py"""
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import SEED
from network.flows import FEATURES
from tools.WP4_S7_lib import S7

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
B = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP4")
KEEP = ["file", "row", "ts", "day", "split", "family", "dst_port", "protocol"] + FEATURES
QUOTA = {("BENIGN", "train"): 400_000, ("BENIGN", "val"): 300_000, ("BENIGN", "test"): 500_000}
CAP = 60_000
RATE = {"train": 0.08, "val": 0.2, "test": 0.3}


def main():
    rng = np.random.RandomState(SEED)
    parts = []
    for p in sorted(glob.glob(os.path.join(B, "D23", "final", "*.pkl"))):
        d = pd.read_pickle(p, compression="gzip")[KEEP]
        d = d[d["split"].astype(str).isin(["train", "val", "test"])]
        fam, sp = d["family"].astype(str).to_numpy(), d["split"].astype(str).to_numpy()
        ben = fam == "BENIGN"
        rate = np.array([RATE[x] for x in ("train", "val", "test")])[pd.Categorical(sp, ["train", "val", "test"]).codes]
        keep = np.where(ben, rng.rand(len(d)) < rate, sp != "train")
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
    e["t"] = e["ts"].astype("int64") / 1e9
    e.loc[e["ts"].isna(), "t"] = np.nan
    old = pd.read_pickle(os.path.join(B, "S5", "D23_eval.pkl"))
    assert len(old) == len(e), (len(old), len(e))
    same = all((old[c].to_numpy() == e[c].to_numpy()).all() if old[c].dtype == object else np.array_equal(old[c].to_numpy(), e[c].to_numpy(), equal_nan=True)
               for c in old.columns)
    print("identical to S5 D23_eval.pkl on all", len(old.columns), "columns:", same, flush=True)
    assert same
    e.to_pickle(os.path.join(S7, "d23_eval.pkl"))
    print("rows", len(e), "NaT ts", int(e["ts"].isna().sum()))


if __name__ == "__main__":
    main()
