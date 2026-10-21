"""WP2 S5: L2b "relations only" scores (decision 2026-10-22) for the harness ablation: S4 variant-0 models and S4 LOCO weights, discrete value / rate
checks dropped (CONT_ONLY), joint checks only for pairs with the reverse bit, S4 3 s in-situ mute kept (documented; to be re-derived in S7).
Output: ../data_extra/WP2_S5_cache/l2b_<group>/<capture>.npz (sparse frame scores per check type). Resumable.
Usage: python -u -W ignore tools/WP2_S5_l2b.py loco|attack|test
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l2b_signals as Z
from WP2_S4_run import CACHE as C4, LOCO, attack_names, load_capture, sparse_save, test_names
from common.config import DATA_EXTRA

OUT = DATA_EXTRA / "WP2_S5_cache"
Z.MUTE_T0 = 3.0
Z.CONT_ONLY = True
Z.JOINT_ONLY = {(0xD0, 2)}


def main():
    group = sys.argv[1]
    names = {"loco": LOCO, "attack": attack_names(1) + attack_names(2), "test": test_names()}[group]
    d = OUT / ("l2b_" + group)
    d.mkdir(parents=True, exist_ok=True)
    W = pickle.load(open(C4 / "weights_m_h0.pkl", "rb"))
    t0 = time.time()
    for c in names:
        p = d / (c + ".npz")
        if p.exists():
            continue
        tm, ids, _, dec = load_capture(c)
        M = pickle.load(open(C4 / "models" / f"h0__{c if group == 'loco' else 'final'}.pkl", "rb"))
        Z.WEIGHTS = W
        sparse_save(p, Z.score_frames(M, tm, dec, len(tm)))
        Z.WEIGHTS = None
        print(f"l2b {group} {c} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
