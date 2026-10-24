"""WP6 S3 stage 2 (VALIDATION ONLY): fit and choose the system fusion on group-aware validation halves, freeze everything the test run needs.
Half A: per-domain ECDF of clean ticks (and the labelled seen-attack logistic). Half B: tie-safe 2% system threshold on clean composite ticks,
choice max vs noisy_or (higher mean detection over the half-B attack families of K and C, v2-comparison rows excluded), ablation thresholds
(each domain removed / alone, same combiner), the domain-alone rows of G5 and the no-cross row of G3.
Run: python -u -W ignore tools/WP6_S3_dev.py      Outputs: results/WP6/s3_dev.json, s3_frozen.pkl (+ s3_frozen.json summary)
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED, results_dir  # noqa: E402
from fusion import composite as CP  # noqa: E402
import WP6_S3_lib as L  # noqa: E402

OUT = results_dir("WP6")
N_CLEAN_VAL, N_ATT_VAL = 400, 60
DOMS = {"K": CP.K_DOMAINS, "C": CP.C_DOMAINS}
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def configs(fam):
    d = DOMS[fam]
    out = {"all": d}
    for x in d:
        out[f"without {x}"] = [y for y in d if y != x]
        out[f"{x} alone"] = [x]
    return out


def main():
    pv = L.load_packs("val")
    H = L.halves(pv)
    log("halves", {f: {d: (len(H["A"][f][d]), len(H["B"][f][d])) for d in H["A"][f]} for f in ("K", "C")})
    comps = {}
    for fam in ("K", "C"):
        comps[("B", fam)] = L.build_set(fam, pv[fam], H["B"][fam], [SEED, 63, 1, ord(fam)], N_CLEAN_VAL, N_ATT_VAL)
        comps[("A", fam)] = L.build_set(fam, pv[fam], H["A"][fam], [SEED, 63, 2, ord(fam)], N_CLEAN_VAL, N_ATT_VAL)
        log(fam, "composites B", len(comps[("B", fam)]), "A", len(comps[("A", fam)]))
    res = {"note": "VALIDATION halves only; no test data", "n_clean_per_half": N_CLEAN_VAL, "n_attack_per_family_per_half": N_ATT_VAL,
           "halves": {h: {f: {d: sorted(v) for d, v in H[h][f].items()} for f in ("K", "C")} for h in ("A", "B")}, "methods": {}}
    frozen = {"halves": res["halves"], "fusions": {}}
    sel = {}
    for method in ("max", "noisy_or"):
        res["methods"][method] = {}
        pooled = []
        for fam in ("K", "C"):
            fus = L.make_fusion(DOMS[fam], method, pv, H, fam)
            cb = [c for c in comps[("B", fam)] if c["family"] == "none"]
            L.threshold_on(fus, cb)
            m, outs = L.evaluate(fus, comps[("B", fam)])
            tab = L.family_table(outs)
            fams = L.single_families(tab, fam)
            m["mean_detection_single"] = L.mean_detection(tab, fams)
            m["families"] = tab
            res["methods"][method][fam] = m
            pooled += [tab[f]["detection"] for f in fams]
            frozen["fusions"][(method, fam, "all")] = fus
            log(method, fam, "B FA tick", round(m["fa_tick"], 4), "events/h", round(m["fa_events_per_hour"], 2), "mean det", round(m["mean_detection_single"], 3))
        sel[method] = float(np.mean(pooled))
    chosen = max(sel, key=lambda k: (sel[k], k == "max"))
    res["selection"] = {"pooled_mean_detection_half_B": sel, "chosen": chosen, "rule": "higher pooled mean detection over the half-B single-domain families (K + C)"}
    log("chosen", chosen, sel)
    # ---- ablation / domain-alone / no-cross thresholds with the chosen combiner (half B) ----
    res["ablation_val"] = {}
    for fam in ("K", "C"):
        cb = [c for c in comps[("B", fam)] if c["family"] == "none"]
        res["ablation_val"][fam] = {}
        for name, doms in configs(fam).items():
            if name == "all":
                fus = frozen["fusions"][(chosen, fam, "all")]
            else:
                fus = L.make_fusion(doms, chosen, pv, H, fam)
                L.threshold_on(fus, cb)
                frozen["fusions"][(chosen, fam, name)] = fus
            m, outs = L.evaluate(fus, comps[("B", fam)])
            tab = L.family_table(outs)
            res["ablation_val"][fam][name] = {"fa_tick": m["fa_tick"], "mean_detection_single": L.mean_detection(tab, L.single_families(tab, fam)),
                                              "families": {f: v["detection"] for f, v in tab.items()}}
        # seen-attack logistic (labelled; never the headline)
        fus = L.make_fusion(DOMS[fam], "logistic", pv, H, fam)
        L.logistic_fit(fus, comps[("A", fam)])
        L.threshold_on(fus, cb)
        frozen["fusions"][("logistic", fam, "all")] = fus
        m, outs = L.evaluate(fus, comps[("B", fam)])
        tab = L.family_table(outs)
        res["ablation_val"][fam]["seen-attack logistic (labelled)"] = {"fa_tick": m["fa_tick"], "mean_detection_single": L.mean_detection(tab, L.single_families(tab, fam)),
                                                                     "coef": dict(zip(fus.domains, np.round(fus.model.coef_[0], 3).tolist()))}
        log(fam, "ablation done")
    frozen["chosen"] = chosen
    frozen["composites"] = {"K": {"n_clean": 2000, "n_attack": 300, "seed": [SEED, 63, 9, ord("K")]},
                            "C": {"n_clean": 1000, "n_attack": 300, "seed": [SEED, 63, 9, ord("C")]}}
    pickle.dump(frozen, open(OUT / "s3_frozen.pkl", "wb"))
    summ = {"chosen": chosen, "composites_test": frozen["composites"],
            "fusions": {" | ".join(k): {"domains": f.domains, "threshold": f.threshold} for k, f in frozen["fusions"].items()}}
    (OUT / "s3_frozen.json").write_text(json.dumps(summ, indent=1))
    (OUT / "s3_dev.json").write_text(json.dumps(res, indent=1, default=str))
    log("frozen", len(frozen["fusions"]), "fusions")


if __name__ == "__main__":
    main()
