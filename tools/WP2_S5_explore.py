"""WP2 S5 exploration (train/val only): continuous signal list, grid sizes, gear/reverse relations."""
import sys, pickle
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP2_S4_run import *
print("cont", len(CAT.cont), "disc", len(CAT.disc))
print([f"{i:#x}.{k}" for i, k in CAT.cont])
st = pickle.load(open(CACHE / "stats" / "ambient_dyno_drive_basic_long.pkl", "rb"))
print(st.Gc.shape, np.isnan(st.Gc).mean())
for n in AMB:
    s = pickle.load(open(CACHE / "stats" / (n + ".pkl"), "rb"))
    print(n, s.Gc.shape)
