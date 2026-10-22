"""WP2 S7: fit stage. Resumable; cache ../data_extra/WP2_S7_cache/.
  prep     per ambient unit (6 dyno, 4 highway blocks, exercise_all_bits): L1 builder, grid, Gram, L2b CapStats; L1 builders of the clean leads of
           the 18 train / val attack captures; L2b code maps
  fold     for each LOCO fold (10) and 'final': RoadModels fitted WITHOUT the held-out unit (L1 profile, L2b model, L3c M0 / M1, L3d)
  weights  L2b surprise weights from the held-out violation counts of the fold models (pooled over the 10 folds)
  loo      leave-capture-out L1 profiles for the validation attack captures (capture and its masquerade twin left out)
Usage: python -u -W ignore tools/WP2_S7_fit.py prep|fold|weights|loo
Design and rules: notes/WP2_can.md "S7 start". No attack frame is used in any fit; no test capture is read.
"""
import pickle
import sys
import time

import numpy as np

from WP2_S7_lib import (AMB_UNITS, CACHE, DYNO, FOLDS, S5, VAL_ATTACK, attack_names, base_of, load_unit, twin)
from can import l1 as L
from can import l2b_signals as Z
from can import l3_predictors as P
from can import signals as S
from can.stack_core import CAT, DBC, RoadModels, l1_builder, l2b_trace, lead_clean, make_grid, merge_builders


def pk(path, obj=None):
    if obj is None:
        return pickle.load(open(path, "rb"))
    path.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(obj, open(path, "wb"))


def lead_groups():
    """Distinct lead groups of the 18 train / val attack captures (original + masquerade copy share the lead)."""
    return sorted({base_of(n) for n in VAL_ATTACK})


def stage_prep():
    t0 = time.time()
    mu, sd = pk(S5 / "scale.pkl")
    grams, stats = {}, {}
    for u in AMB_UNITS:
        p_b = CACHE / "l1b" / (u + ".pkl")
        p_g = CACHE / "grid" / (u + ".npz")
        p_s = CACHE / "stats" / (u + ".pkl")
        if p_b.exists() and p_g.exists() and p_s.exists():
            continue
        U = load_unit(u)
        dec = S.decode_all(U.id, U.B, DBC)
        tm = U.tm
        pk(p_b, l1_builder(U, np.ones(len(U), bool)))
        Gc, Gd, g0 = make_grid(tm, dec)
        p_g.parent.mkdir(parents=True, exist_ok=True)
        np.savez(p_g, Gc=Gc, Gd=Gd, t0=g0)
        pk(p_s, Z.capture_stats(u, tm, dec, CAT))
        print(f"prep {u} frames {len(U)} grid {Gc.shape} ({time.time() - t0:.0f}s)", flush=True)
    for u in AMB_UNITS:
        if u not in grams:
            z = np.load(CACHE / "grid" / (u + ".npz"))
            grams[u] = P.Gram(z["Gc"], mu, sd)
    pk(CACHE / "grams.pkl", grams)
    st = {u: pk(CACHE / "stats" / (u + ".pkl")) for u in AMB_UNITS}
    pk(CACHE / "maps.pkl", Z.build_codemaps(list(st.values()), CAT))
    for g in lead_groups():
        p = CACHE / "l1b" / (g + ".pkl")
        if p.exists():
            continue
        U = load_unit(g)
        pk(p, l1_builder(U, lead_clean(U)))
        print(f"lead builder {g} ({time.time() - t0:.0f}s)", flush=True)
    print("prep done", flush=True)


def fit_models(fit_units, name) -> RoadModels:
    """RoadModels from the clean units `fit_units` (all attack leads included for L1)."""
    t0 = time.time()
    M = RoadModels()
    bs = [pk(CACHE / "l1b" / (u + ".pkl")) for u in fit_units] + [pk(CACHE / "l1b" / (g + ".pkl")) for g in lead_groups()]
    M.profile = merge_builders(bs).finish()
    st = [pk(CACHE / "stats" / (u + ".pkl")) for u in fit_units]
    maps = pk(CACHE / "maps.pkl")
    M.l2b = Z.fit_model(st, [Z.grid_codes(s, maps) for s in st], CAT, maps, 0.98, 1)
    mu, sd = pk(S5 / "scale.pkl")
    grams = pk(CACHE / "grams.pkl")
    inner0 = [u for u in fit_units if u in DYNO]
    inner1 = [u for u in fit_units if u in FOLDS]
    M.l3c = {"M0": P.fit_l3c(grams, fit_units, inner0, mu, sd, True), "M1": P.fit_l3c(grams, fit_units, inner1, mu, sd, True)}
    M.l3d = P.fit_l3d([np.load(CACHE / "grid" / (u + ".npz"))["Gd"] for u in fit_units])
    print(f"fit {name}: {len(fit_units)} units, inner0 {len(inner0)} inner1 {len(inner1)}, lin={len(M.l2b.lin)} joint={len(M.l2b.joint)} "
          f"({time.time() - t0:.0f}s)", flush=True)
    return M


def stage_fold():
    order = FOLDS + ["final"]
    if len(sys.argv) > 2 and sys.argv[2] == "rev":          # a second process works from the other end (the machine is shared)
        order = order[::-1]
    for f in order:
        p = CACHE / "models" / (f + ".pkl")
        if p.exists():
            continue
        fit_units = [u for u in AMB_UNITS if u != f]
        pk(p, fit_models(fit_units, f))


def stage_weights():
    """L2b surprise weights: -log2 of the violation rate of every check on the held-out clean frames of the 10 folds (add-one smoothing)."""
    tot = {}
    for f in FOLDS:
        M = pk(CACHE / "models" / (f + ".pkl"))
        U = load_unit(f)
        dec = S.decode_all(U.id, U.B, DBC)
        for tag, (n, v) in l2b_trace(M.l2b, U.tm, dec, len(U)).items():
            a = tot.setdefault(tag, [0, 0])
            a[0] += n
            a[1] += v
        print(f"weights trace {f}", flush=True)
    W = {tag: Z.check_weight(v, n) for tag, (n, v) in tot.items()}
    pk(CACHE / "weights.pkl", W)
    w = np.array(list(W.values()))
    print(f"{len(W)} checks, never fire in LOCO: {sum(1 for n, v in tot.values() if v == 0)}, weight quantiles {np.quantile(w, [0, .1, .5, .9, 1]).round(2)}")


def stage_loo():
    """Leave-capture-out L1 profiles for the validation attack captures (one per lead group)."""
    for g in lead_groups():
        p = CACHE / "models" / ("l1loo_" + g + ".pkl")
        if p.exists():
            continue
        bs = [pk(CACHE / "l1b" / (u + ".pkl")) for u in AMB_UNITS] + [pk(CACHE / "l1b" / (h + ".pkl")) for h in lead_groups() if h != g]
        pk(p, merge_builders(bs).finish())
        print(f"loo profile without {g}", flush=True)


if __name__ == "__main__":
    {"prep": stage_prep, "fold": stage_fold, "weights": stage_weights, "loo": stage_loo}[sys.argv[1]]()
