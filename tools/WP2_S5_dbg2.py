import sys, pickle
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from WP2_S5_eval import *
from WP2_S5_run import load_grid
from WP2_S4_run import CAT
names = [f"{i:#x}.{k}" for i, k in CAT.cont]
per = {}
for c in LOCO:
    M = pickle.load(open(CACHE / "models" / f"{c}.pkl", "rb"))[False]
    Gc, Gd, g0 = load_grid(c)
    z = P.z_matrix(M, Gc)
    per[c] = ((z > 8).mean(0), M.r2.copy(), M.sigma.copy())
F = np.array([v[0] for v in per.values()])
R2 = np.array([v[1] for v in per.values()])
SG = np.array([v[2] for v in per.values()])
order = np.argsort(-F.max(0))[:30]
for j in order:
    print(names[j], "frac z>8 per fold", np.round(F[:, j], 2), "r2 min %.2f" % R2[:, j].min(), "sigma", np.round(SG[:, j], 3))
