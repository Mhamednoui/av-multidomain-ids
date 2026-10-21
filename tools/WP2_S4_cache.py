"""WP2 S4: payload cache for ROAD (uint8 n x 8 per capture), aligned with the S2 cache (same frame order).

Purpose: the signal-physics layer (can/l2b_signals.py) decodes DBC signals from the payload bytes; the S2 cache keeps no payload.
Output: ../data_extra/WP2_S4_cache/road/<capture>.npy (uint8, zero padded beyond DLC). About 220 MB for all 41 captures.
Resumable: existing files are skipped. Check: frame count and time stamps equal to the S2 cache.
Usage: python tools/WP2_S4_cache.py
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import adapters as A
from common.config import DATA_EXTRA

OUT = DATA_EXTRA / "WP2_S4_cache" / "road"
S2 = DATA_EXTRA / "WP2_S2_cache" / "road"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    caps = A.road_captures()
    t0 = time.time()
    for _, r in caps[caps["usable"]].iterrows():
        out = OUT / (r["name"] + ".npy")
        if out.exists():
            continue
        p = A.road_parse_log(r["path"])
        ref = np.load(S2 / (r["name"] + ".npz"))["t"]
        if len(ref) != len(p["t"]) or not np.allclose(ref, p["t"]):
            raise RuntimeError("misaligned with S2 cache: " + r["name"])
        np.save(out, np.maximum(p["B"], 0).astype(np.uint8))
        print(f"{r['name']} {len(ref)} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
