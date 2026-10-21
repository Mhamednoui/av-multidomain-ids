"""WP2 S5: L3 per-signal predictors on ROAD. Stages (resumable, cache ../data_extra/WP2_S5_cache/):
  grams   scaling constants + Gram matrices of the 8 clean ambient captures
  fold    for each LOCO outer fold (7) and the final model: L3c (cross, cross+own) with nested lambda / sigma / R2, and L3d map
  score   grid-level scores of every variant for  loco | attack | test  captures (test = ONE run)
Usage: python -u -W ignore tools/WP2_S5_run.py grams|fold|score loco|attack|test
Protocol and acceptance rule: notes/WP2_can.md "S5 start".
"""
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l3_predictors as P
from common.config import DATA_EXTRA
from WP2_S4_run import AMB, attack_names, test_names

CACHE = DATA_EXTRA / "WP2_S5_cache"
# Fit-only captures: the only captures of their regime (design change 1, 2026-10-22): exercise_all_bits (as in S4) and the highway drive (every dyno
# fold that leaves it out extrapolates to speeds / wheel-speed gains never seen: z > 5 in 70% of its steps, which alone fixed the pooled threshold).
FIT_ONLY = ["ambient_dyno_exercise_all_bits", "ambient_highway_street_driving_long"]
LOCO = [n for n in AMB if n not in FIT_ONLY]
VARIANTS = [(own, rmin, agg) for own in (False, True) for rmin in (0.0, 0.9) for agg in ("max", "cusum")]


def vname(v):
    return f"{'own' if v[0] else 'cross'}_r{v[1]}_{v[2]}"


def load_grid(name):
    z = np.load(CACHE / "grids" / (name + ".npz"))
    return z["Gc"], z["Gd"], float(z["t0"])


def stage_grams():
    (CACHE / "models").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    grids = {n: load_grid(n) for n in AMB}
    mu, sd = P.scale_constants([g[0] for g in grids.values()])
    pickle.dump((mu, sd), open(CACHE / "scale.pkl", "wb"))
    grams = {n: P.Gram(grids[n][0], mu, sd) for n in AMB}
    pickle.dump(grams, open(CACHE / "grams.pkl", "wb"))
    print(f"grams done ({time.time() - t0:.0f}s)", flush=True)


def stage_fold():
    mu, sd = pickle.load(open(CACHE / "scale.pkl", "rb"))
    grams = pickle.load(open(CACHE / "grams.pkl", "rb"))
    t0 = time.time()
    for c in LOCO + ["final"]:
        p = CACHE / "models" / f"{c}.pkl"
        if p.exists():
            continue
        fit_names = AMB if c == "final" else [n for n in AMB if n != c]
        inner = [n for n in fit_names if n in LOCO]
        out = {}
        for own in (False, True):
            out[own] = P.fit_l3c(grams, fit_names, inner, mu, sd, own)
            M = out[own]
            print(f"fold {c} own={own}: r2>=0.9 {int((M.r2 >= 0.9).sum())} r2>=0.5 {int((M.r2 >= 0.5).sum())} median lam {np.median(M.lam):g} ({time.time() - t0:.0f}s)", flush=True)
        out["d"] = P.fit_l3d([load_grid(n)[1] for n in fit_names])
        pickle.dump(out, open(p, "wb"))


def stage_score():
    group = sys.argv[2]
    only = {int(x) for x in sys.argv[3].split(",")} if len(sys.argv) > 3 else None      # test: only the variant chosen on validation
    names = {"loco": LOCO, "attack": attack_names(1) + attack_names(2), "test": test_names()}[group]
    d = CACHE / ("scores_" + group)
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for c in names:
        p = d / (c + ".npz")
        if p.exists():
            continue
        M = pickle.load(open(CACHE / "models" / f"{c if group == 'loco' else 'final'}.pkl", "rb"))
        Gc, Gd, g0 = load_grid(c)
        out = {"t0": g0, "d": P.l3d_scores(M["d"], Gd)}
        for vi, v in enumerate(VARIANTS):
            if only is None or vi in only:
                out[vname(v)] = P.grid_scores(M[v[0]], Gc, v[1], v[2])
        np.savez(p, **out)
        print(f"score {group} {c} ({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    {"grams": stage_grams, "fold": stage_fold, "score": stage_score}[sys.argv[1]]()
