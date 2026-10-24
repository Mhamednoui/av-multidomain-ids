"""WP6 S4 stage 2 (VALIDATION ONLY): fit the evidence-novelty detectors on clean validation half-A ticks, build the zero-day system variants and choose the
configuration on validation half B with SEEN families only (held-out types are excluded from every choice and their validation numbers are not stored).
Grid (fixed in notes/WP6_crossdomain.md "S4 start"): combiner {max, noisy_or} x network {H, H+L3} x novelty {none, mcd, iforest}; tie-break: simpler first.
Run: python -u -W ignore tools/WP6_S4_dev.py      Outputs: results/WP6/s4_dev.json, s4_frozen.pkl
"""
import itertools
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED, results_dir  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S4_lib as L  # noqa: E402

OUT = results_dir("WP6")
N_CLEAN_VAL, N_ATT_VAL = 400, 60
T0 = time.time()
COMP_SEED = {"K": [SEED, 64, 1, ord("K")], "C": [SEED, 64, 1, ord("C")]}
TEST_COMPOSITES = {"K": {"n_clean": 2000, "n_attack": 300, "seed": [SEED, 64, 9, ord("K")]},
                   "C": {"n_clean": 1000, "n_attack": 300, "seed": [SEED, 64, 9, ord("C")]}}
SIMPLICITY = {"method": {"max": 0, "noisy_or": 1}, "net": {"H": 0, "H+L3": 1}, "nov": {None: 0, "mcd": 1, "iforest": 2}}


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def main():
    u = L.load_unique("val")
    H, gA, gB = L.halves_unique(u)
    log("halves A/B sizes", {k: (len(gA[k]), len(gB[k])) for k in gA})
    dets, oof = L.fit_novelty(u, gA)
    log("novelty detectors fitted:", sorted({k for k, _ in dets}))
    packs = L.assemble(L.attach_novelty(u, dets, oof))
    comps = {fam: L3.build_set(fam, packs[fam], H["B"][fam], COMP_SEED[fam], N_CLEAN_VAL, N_ATT_VAL) for fam in ("K", "C")}
    for fam in ("K", "C"):
        fams = sorted({(c["family"], c["attacked"]) for c in comps[fam] if c["family"] != "none"})
        held = [f for f, a in fams if L.category(f, a) == "heldout"]
        log(fam, "val-B composites", len(comps[fam]), "families", len(fams), "held-out families present (excluded from every choice):", held)
    res = {"note": "VALIDATION only. Held-out families are excluded from the selection; their validation numbers are not stored.",
           "n_clean_per_half": N_CLEAN_VAL, "n_attack_per_family": N_ATT_VAL, "grid": {}}
    frozen = {"H": H, "gA": gA, "gB": gB, "dets": dets, "variants": {}, "composites_test": TEST_COMPOSITES, "composite_seed_val": COMP_SEED}
    grid = list(itertools.product(("max", "noisy_or"), ("H", "H+L3"), (None, "mcd", "iforest")))
    pooled = {}
    for method, net, nov in grid:
        key = f"{method}|net={net}|nov={nov}"
        per = {}
        allv = []
        for fam in ("K", "C"):
            var = L.variant(fam, method, net, nov)
            cleanB = [c for c in comps[fam] if c["family"] == "none"]
            fus = L.fit_variant(var, packs[fam], H["A"][fam], cleanB)
            frozen["variants"][L.var_key(var)] = (var, fus)
            X, s = L.score_variant(var, fus, comps[fam], packs[fam])
            m, outs, tab = L.summarize(comps[fam], s, fus.threshold)
            sel = L.selection_families(tab)
            assert not any(L.category(f, tab[f]["attacked"]) == "heldout" for f in sel)
            det = [tab[f]["detection"] for f in sel]
            allv += det
            per[fam] = {"fa_tick_B": m["fa_tick"], "events_per_hour_B": m["fa_events_per_hour"], "mean_detection_seen": float(np.mean(det)), "n_seen_families": len(sel),
                        "by_category": {c: v for c, v in m["by_category"].items() if c != "heldout"}}
        pooled[(method, net, nov)] = float(np.mean(allv))
        res["grid"][key] = {"pooled_mean_detection_seen_K_C": pooled[(method, net, nov)], **per}
        log(key, "pooled seen", round(pooled[(method, net, nov)], 4), "K", round(per["K"]["mean_detection_seen"], 4), "C", round(per["C"]["mean_detection_seen"], 4),
            "FA_B K/C", round(per["K"]["fa_tick_B"], 4), round(per["C"]["fa_tick_B"], 4))
    best = max(grid, key=lambda g: (round(pooled[g], 6), -SIMPLICITY["method"][g[0]], -SIMPLICITY["net"][g[1]], -SIMPLICITY["nov"][g[2]]))
    chosen = {"method": best[0], "net": best[1], "nov": best[2]}
    res["chosen"] = chosen
    res["selection_rule"] = "highest pooled (K + C) mean detection over the non-held-out validation half-B families at the 2% tie-safe threshold; ties -> simpler"
    log("CHOSEN", chosen, pooled[best])
    # matched ablation partners + tier ablation systems (chosen combiner / network) are fitted now and frozen
    for fam in ("K", "C"):
        cleanB = [c for c in comps[fam] if c["family"] == "none"]
        extra = [L.variant(fam, best[0], best[1], best[2]), L.variant(fam, best[0], best[1], None)]
        for nv in L.NOV_KINDS:
            extra.append(L.variant(fam, best[0], best[1], nv))
        for g in ("rules", "l3"):
            extra.append(L.variant(fam, best[0], best[1], None, groups=g))
        for var in extra:
            k = L.var_key(var)
            if k in frozen["variants"]:
                continue
            frozen["variants"][k] = (var, L.fit_variant(var, packs[fam], H["A"][fam], cleanB))
    frozen["chosen"] = chosen
    pickle.dump(frozen, open(OUT / "s4_frozen.pkl", "wb"))
    res["frozen_variants"] = {k: {"threshold": f.threshold, "entries": [e[0] for e in v["entries"]]} for k, (v, f) in frozen["variants"].items()}
    (OUT / "s4_dev.json").write_text(json.dumps(res, indent=1, default=str))
    log("frozen", len(frozen["variants"]), "variants")


if __name__ == "__main__":
    main()
