"""WP2 S6: per-capture cache of raw L4 stream features for ROAD (train + val captures ONLY) and Car-Hacking.

The ROAD test captures are never read in S6 (supervisor decision 2026-10-22). Cache: ../data_extra/WP2_S6_cache/<dataset>/<name>.npz
(t, id, dlc, B as uint8, dt_prev, dt_id, n_id, n_uniq, bchg, label, att names / codes). Resumable.
Usage: python tools/WP2_S6_cache.py road|carhacking
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import adapters as A
from can import l4_features as G
from common.config import DATA_EXTRA

OUT = DATA_EXTRA / "WP2_S6_cache"


def save(path, d):
    t = d["t"].to_numpy()
    ids = d["id"].to_numpy()
    dlc = d["dlc"].to_numpy()
    B = d[A.BYTE_COLS].to_numpy()
    raw = G.stream_raw(t, ids, dlc, B)
    names, codes = np.unique(d["attack"].astype(str).to_numpy().astype("U40"), return_inverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, t=t, id=ids.astype(np.int32), dlc=dlc.astype(np.int8), B=np.maximum(B, 0).astype(np.uint8),
             dt_prev=raw["dt_prev"], dt_id=raw["dt_id"], n_id=raw["n_id"], n_uniq=raw["n_uniq"], bchg=raw["bchg"],
             label=d["label"].to_numpy().astype(np.int8), att_names=names, att_codes=codes.astype(np.int8))


def load(dataset, name) -> dict:
    z = np.load(OUT / dataset / (name + ".npz"))
    d = {k: z[k] for k in z.files}
    B = d["B"].astype(np.int16)
    B[np.arange(8)[None, :] >= d["dlc"][:, None]] = -1
    d["B"] = B
    return d


def main():
    which = sys.argv[1]
    t0 = time.time()
    if which == "road":
        caps = A.road_captures()
        caps = caps[caps["usable"] & caps["part"].isin(["train", "val"])]      # NEVER test
        for _, r in caps.iterrows():
            out = OUT / "road" / (r["name"] + ".npz")
            if out.exists():
                continue
            save(out, A.load_road(r["name"], caps))
            print(f"{r['name']} ({time.time() - t0:.0f}s)", flush=True)
    elif which == "carhacking":
        for k in A.CARHACKING_FILES:
            out = OUT / "carhacking" / (k + ".npz")
            if out.exists():
                continue
            save(out, A.load_carhacking(k))
            print(f"{k} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
