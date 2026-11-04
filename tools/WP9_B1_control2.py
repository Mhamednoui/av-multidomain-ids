"""WP9 B1 supplementary control (validation only): within-capture label permutation ("capture-context control").

Usage: python -u -W ignore tools/WP9_B1_control2.py carhacking|road|d11 [set_0N]
Why: the global shuffled-label control (WP9_B1_fit.py) leaves AUCs far from 0.5 in several units (density / outlier structure
of the noise model). This control permutes the training labels INSIDE each training segment (capture / block run), so every
segment keeps its attack rate but the position of the attack inside it is random. A model that scores validation AUC clearly
above 0.5 learned the regime of the segment (e.g. attack captures differ from ambient captures), not the injection.
Uses the units frozen in results/WP9/B1_<tag>_selection.json (chosen model; for E its two parts). Reads only train + val.
Output: results/WP9/B1_<tag>_control2.json.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B1_lib as L
import WP9_B1_fit as FIT
from common.config import SEED


def main():
    ds = sys.argv[1]
    sset = sys.argv[2] if len(sys.argv) > 2 else None
    tag = ds + (f"_{sset}" if sset else "")
    sel = json.load(open(L.OUT / f"B1_{tag}_selection.json"))
    classes, idx = FIT.cfg_for(ds, sset)
    K1 = len(classes)
    b = pickle.load(open(L.CACHE / "models" / tag / "bundle.pkl", "rb"))
    pid, pval = L.period_lookup(b["period"])
    id_list = b["id_list"]
    names, ng = b["names"], b["ng"]
    units = sel["candidates"][sel["chosen"]].get("parts", [sel["chosen"]])
    L.journal(f"control2 {tag}: start units {units}")
    tr = FIT.load_parts(ds, idx, ("train",))
    va = FIT.load_parts(ds, idx, ("val",))
    rng = np.random.default_rng(SEED + 7)
    wtr = []
    for i, S in tr:
        w = L.segment_windows(S, pid, pval, id_list, K1)
        w["group"] = i["seg"]
        wtr.append(w)
    wva = [L.segment_windows(S, pid, pval, id_list, K1) for _, S in va]
    Wtr = np.concatenate([w["W"][w["valid"]] for w in wtr]); ytr = np.concatenate([w["y"][w["valid"]] for w in wtr])
    gtr = np.concatenate([[w["group"]] * int(w["valid"].sum()) for w in wtr])
    Wva = np.concatenate([w["W"][w["valid"]] for w in wva]); yva = np.concatenate([w["y"][w["valid"]] for w in wva])

    def within(y, g):
        out = y.copy()
        for u in np.unique(g):
            m = np.flatnonzero(g == u)
            out[m] = rng.permutation(y[m])
        return out
    res = {}
    for u in units:
        if u.startswith("W_"):
            fs = "generic" if u.endswith("generic") else "ids"
            sl = slice(0, ng) if fs == "generic" else slice(0, None)
            ysh = within(ytr, gtr)
            if u.startswith("W_rf"):
                m = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
                                           n_jobs=4, random_state=SEED).fit(np.nan_to_num(Wtr[:, sl], nan=-1), ysh)
                P = m.predict_proba(np.nan_to_num(Wva[:, sl], nan=-1))
            else:
                c = sel["candidates"][u]
                m = FIT.fit_xgb(Wtr[:, sl], ysh, K1, c["params"], c["n_trees"])
                P = m.predict_proba(Wva[:, sl])
            res[u] = {"unit": "window", "within_capture_shuffled_auc": L.auc_binary((yva != 0).astype(int), 1 - P[:, 0])}
        else:
            cols = b["cols"][u]
            c = sel["candidates"][u]
            ptr = FIT.sample_frames(tr, rng)
            pva = FIT.sample_frames(va, rng, n_norm=300_000, cap_att=100_000)
            gl = np.concatenate([[i["seg"]] * len(ix) for (i, _), (_, ix) in zip(tr, ptr)])
            Xf, yf = FIT.frame_data(ptr, pid, pval, cols)
            Xfv, yfv = FIT.frame_data(pva, pid, pval, cols)
            m = FIT.fit_xgb(Xf, within(yf, gl), K1, c["params"], c["n_trees"])
            Pf = m.predict_proba(Xfv)
            res[u] = {"unit": "frame", "within_capture_shuffled_auc": L.auc_binary((yfv != 0).astype(int), 1 - Pf[:, 0])}
        res[u]["pass_0.42_0.58"] = bool(0.42 <= res[u]["within_capture_shuffled_auc"] <= 0.58)
        print(tag, u, res[u], flush=True)
    L.jd({"tag": tag, "units": res, "note": "labels permuted within each training segment; validation only"},
         L.OUT / f"B1_{tag}_control2.json")
    L.journal(f"control2 {tag}: done results/WP9/B1_{tag}_control2.json")


if __name__ == "__main__":
    main()
