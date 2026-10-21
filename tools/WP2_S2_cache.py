"""WP2 S2: compact per-capture cache (t, id, dlc, label) for ROAD, Car-Hacking, D11.

Purpose: the L1 spec rules need only time, ID, DLC and label, not the payload bytes. Parsing 193 M
D11 frames from CSV is the slow part, so each capture is parsed once and stored as .npz under
../data_extra/WP2_S2_cache/<dataset>/ (not committed). Resumable: existing files are skipped.
Frames stay in RECORDED order (never sorted). t = seconds since the first frame (D11: since epoch).
Usage: python tools/WP2_S2_cache.py road|carhacking|d11 [max_files]
"""
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import adapters as A
from common.config import DATA_EXTRA

OUT = DATA_EXTRA / "WP2_S2_cache"


def save(path: Path, t, ids, dlc, label, attack=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    kw = dict(t=np.asarray(t, np.float64), id=np.asarray(ids, np.int32), dlc=np.asarray(dlc, np.int8),
              label=np.asarray(label, np.int8))
    if attack is not None:      # int8 codes + the (few) names; a per-frame string array took 39 GB
        names, codes = np.unique(np.asarray(attack).astype("U40"), return_inverse=True)
        kw["att_names"], kw["att_codes"] = names, codes.astype(np.int8)
    np.savez(path, **kw)


def d11_fast(path: Path):
    raw = pd.read_csv(path, usecols=["timestamp", "arbitration_id", "data_field", "attack"],
                      dtype={"timestamp": np.float64, "arbitration_id": str, "data_field": str, "attack": np.int8},
                      keep_default_na=False)
    uniq = raw["arbitration_id"].str.strip().unique()
    ids = raw["arbitration_id"].str.strip().map({u: int(u, 16) for u in uniq}).to_numpy()
    dlc = (raw["data_field"].str.strip().str.len() // 2).to_numpy()
    return raw["timestamp"].to_numpy() - A.D11_EPOCH, ids, dlc, raw["attack"].to_numpy()


def main():
    which = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9
    done = 0
    t0 = time.time()
    if which == "d11":
        tab = A.d11_file_table()
        for _, r in tab.iterrows():
            out = OUT / "d11" / (r["capture"].replace("/", "__") + ".npz")
            if out.exists():
                continue
            t, ids, dlc, lab = d11_fast(r["path"])
            save(out, t, ids, dlc, lab, np.where(lab == 1, A.d11_attack_of(r["path"].name), "normal"))
            done += 1
            print(f"{r['capture']} {len(t)} frames ({time.time() - t0:.0f}s)", flush=True)
            if done >= limit:
                break
    elif which == "road":
        caps = A.road_captures()
        for _, r in caps[caps["usable"]].iterrows():
            out = OUT / "road" / (r["name"] + ".npz")
            if out.exists():
                continue
            d = A.load_road(r["name"], caps)
            save(out, d["t"], d["id"], d["dlc"], d["label"], d["attack"].astype(str))
            print(f"{r['name']} {len(d)} frames ({time.time() - t0:.0f}s)", flush=True)
    elif which == "carhacking":
        for k in A.CARHACKING_FILES:
            out = OUT / "carhacking" / (k + ".npz")
            if out.exists():
                continue
            d = A.load_carhacking(k)
            save(out, d["t"], d["id"], d["dlc"], d["label"], d["attack"].astype(str))
            print(f"{k} {len(d)} frames ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
