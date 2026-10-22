"""WP2 S7: per-window raw score tables of every layer (cache ../data_extra/WP2_S7_cache/tables/<group>/<unit>.npz). Resumable.
  folds   the 10 LOCO units scored by their own fold models (held out)
  val     the 18 train / val attack captures scored by the final models (L1: leave-capture-out profile)
  test    the 15 ROAD test captures with the FINAL models (ONE run; refuses to start unless results/WP2/s7_frozen.json exists)
  accel   the 4 accelerator captures with the final models (same guard)
Usage: python -u -W ignore tools/WP2_S7_tables.py folds|val|test|accel
"""
import pickle
import sys
import time

import numpy as np

from WP2_S7_lib import ACCEL, CACHE, FOLDS, OUT, TEST, VAL_ATTACK, base_of, load_unit
from can import l1 as L
from can.stack_core import window_raws


def pk(path):
    return pickle.load(open(path, "rb"))


def save(group, name, d):
    p = CACHE / "tables" / group / (name + ".npz")
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez(p, **d)


def main():
    group = sys.argv[1]
    if group in ("test", "accel") and not (OUT / "s7_frozen.json").exists():
        raise SystemExit("refusing: results/WP2/s7_frozen.json (frozen design) does not exist")
    W = pk(CACHE / "weights.pkl")
    t0 = time.time()
    if group == "folds":
        for f in FOLDS:
            if (CACHE / "tables" / "folds" / (f + ".npz")).exists():
                continue
            M = pk(CACHE / "models" / (f + ".pkl"))
            M.l2b_weights = W
            save("folds", f, window_raws(M, load_unit(f)))
            print(f"folds {f} ({time.time() - t0:.0f}s)", flush=True)
        return
    M = pk(CACHE / "models" / "final.pkl")
    M.l2b_weights = W
    names = {"val": VAL_ATTACK, "test": TEST, "accel": ACCEL}[group]
    for n in names:
        if (CACHE / "tables" / group / (n + ".npz")).exists():
            continue
        prof = pk(CACHE / "models" / ("l1loo_" + base_of(n) + ".pkl")) if group == "val" else None
        save(group, n, window_raws(M, load_unit(n), profile=prof))
        print(f"{group} {n} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    main()
