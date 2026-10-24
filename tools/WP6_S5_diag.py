"""WP6 S5 POST-TEST diagnostic (no choice is made from it): why the M2 clean FA / alert events differ between validation (nested held-out) and test.
Per entry: share of clean ticks with calibrated score >= 0.99 (val nested held-out vs test); strongest entry at clean alarm ticks; blamed domain and response of
clean alert events; alarm ticks per clean event. Run: python -u -W ignore tools/WP6_S5_diag.py      Output: results/WP6/s5_diag.json
"""
import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S5_dev as D  # noqa: E402
import WP6_S5_lib as L  # noqa: E402

OUT = results_dir("WP6")


def clean_stats(sysm, comps, X, s, T):
    doms = sysm.entries
    idx = L3.index_of(comps)
    cm = L.clean_mask(comps)
    al = s >= T
    top = Counter(doms[j] for j in X[cm & al].argmax(axis=1))
    blamed, resp, ticks = Counter(), Counter(), []
    n_clean = n_with = 0
    lens = []
    for ci, c in enumerate(comps):
        if c["family"] != "none":
            continue
        n_clean += 1
        lens.append(c["n"])
        a = al[idx[ci]:idx[ci + 1]]
        if not a.any():
            continue
        Xc = X[idx[ci]:idx[ci + 1]]
        own, bl = L.comp_arrays(c, Xc, doms)
        ev = sysm.correlator.events(a, own, doms, bl)
        n_with += int(len(ev) > 0)
        for e in ev:
            blamed[e.blamed] += 1
            resp[(e.blamed, e.response)] += 1
            ticks.append(e.n_alarm_ticks)
    n_al = int((cm & al).sum())
    return {"share_ge_099": {d: float((X[cm, j] >= 0.99).mean()) for j, d in enumerate(doms)},
            "own_alarm_rate": {d: float(np.concatenate([c["parts"][d]["dom_alarm"] for c in comps if c["family"] == "none"]).mean()) for d in doms},
            "strongest_at_clean_alarm_ticks": {d: v / max(n_al, 1) for d, v in top.most_common()},
            "clean_events_by_blamed": dict(blamed.most_common()), "clean_events_by_blamed_response": {f"{a}|{b}": v for (a, b), v in resp.most_common()},
            "alarm_ticks_per_clean_event_median": float(np.median(ticks)) if ticks else None,
            "clean_composites_with_an_event": n_with / max(n_clean, 1), "clean_composite_median_length_s": float(np.median(lens)), "clean_hours": float(cm.sum() / 3600)}


def main():
    fz = pickle.load(open(OUT / "s5_frozen.pkl", "rb"))
    ch = fz["calibration_choice"]
    out = {"note": "POST-TEST diagnostic, no choice made from it", "val_nested_heldout": {}, "test": {}}
    u = L.load_unique("val")
    folds = fz["folds"]
    packs = L.assemble(u)
    for fam in ("K", "C"):
        comps = L.fold_composites(packs, folds, fam, D.N_CLEAN, D.N_ATT)
        fs = L.FoldScores(u, folds, comps, fam, {"v2x": ch["alpha_v2x"], "network": ch["alpha_net"]})
        ho = L.heldout_scores(fs, ch["method"], ch["procedure"])
        sysm = fz["systems"][fam]
        parts = []
        for f, (s, T) in ho.items():
            X = fs.X[(f, frozenset(set(range(L.N_FOLDS)) - {f}))]
            parts.append(clean_stats(sysm, comps[f], X, s, T))
        out["val_nested_heldout"][fam] = parts
    pt = L.assemble(L.load_unique("test"))
    for fam in ("K", "C"):
        c = fz["composites_test"][fam]
        comps = L3.build_set(fam, pt[fam], None, c["seed"], c["n_clean"], c["n_attack"])
        sysm = fz["systems"][fam]
        X = L.matrix(sysm.density, sysm.fusion, comps)
        s = L.combine(sysm.fusion.method, X)
        out["test"][fam] = clean_stats(sysm, comps, X, s, sysm.fusion.threshold)
        print(fam, json.dumps(out["test"][fam], indent=0)[:1500], flush=True)
    (OUT / "s5_diag.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
