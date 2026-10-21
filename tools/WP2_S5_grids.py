"""WP2 S5: 0.05 s sample-and-hold grids of the continuous signals (138) and of the reverse bit + 3 gear copies, per ROAD capture.
Output: ../data_extra/WP2_S5_cache/grids/<capture>.npz  (Gc float32 n x 138, Gd float32 n x 4, t0). Resumable.
Same grid as the S4 statistics (starts 1 s after the first frame).  Usage: python -u -W ignore tools/WP2_S5_grids.py
"""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP2_S4_run import AMB, CAT, attack_names, load_capture, test_names
from can import l2b_signals as Z
from common.config import DATA_EXTRA

OUT = DATA_EXTRA / "WP2_S5_cache" / "grids"
DISC = [(0xD0, 2), (0x295, 0), (0xC0, 0), (0x274, 14)]      # reverse bit, 3 gear copies


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for n in AMB + attack_names(1) + attack_names(2) + test_names():
        p = OUT / (n + ".npz")
        if p.exists():
            continue
        tm, ids, _, dec = load_capture(n)
        g = np.arange(tm[0] + 1.0, tm[-1], Z.GRID_DT)
        Gc = np.full((len(g), len(CAT.cont)), np.nan, np.float32)
        Gd = np.full((len(g), len(DISC)), np.nan, np.float32)
        for (i, k), c in CAT.cont_ix.items():
            if i in dec:
                rows, V = dec[i]
                Gc[:, c] = Z.held(tm[rows], V[:, k], g)
        for c, (i, k) in enumerate(DISC):
            if i in dec:
                rows, V = dec[i]
                Gd[:, c] = Z.held(tm[rows], V[:, k], g)
        np.savez(p, Gc=Gc, Gd=Gd, t0=g[0])
        print(f"{n} {Gc.shape} nan_cols={int(np.isnan(Gc).all(0).sum())} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
