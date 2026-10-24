"""WP3 S9 VERDICT run (test touched once, 7th exposure of the KITTI LiDAR test drives). Reads the choices of the validation round
(results/WP3/S9/dev.json: combiner, density part), builds the score frames of the headline layers on the test drives (+ optional L2b / L4 rows,
+ the v2 side-by-side), saves the score store BEFORE looking at any number, then runs the analysis. Writes results/WP3/S9/final.json,
test_scores.csv.gz (per-scan stack score table, input of the freeze check). Usage: python -u -W ignore tools/WP3_S9_final.py"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP3_S9_lib as L
from WP3_S9_analysis import PHYS, CMP, analyse, detection_block
from common.config import RESULTS
from common.metrics import budget_threshold
from lidar import combine as K
from lidar import learned_l4 as L4
from lidar import occlusion as O
from lidar import occlusion_eval as E5
from lidar.data import CACHE, TEST, VAL, drives_of

RES = RESULTS / "WP3" / "S9"
STORE = L.S9C / "final_frames_s9.pkl"
S7STORE = CACHE / "S7" / "final_frames.pkl"


def add_l2b(fr):
    v = tuple(json.loads((RESULTS / "WP3" / "S5" / "variant_choice.json").read_text())["variant"])
    alld = list(dict.fromkeys(L.TV + TEST))
    tc, sc = E5.load_kind("clean", alld)
    cf = E5.frame(tc, sc, v)
    lay = O.L2bUnion().calibrate(cf[cf.drive.isin(L.TV)], 0.01)
    src = {"ref": cf[cf.drive.isin(L.TV)], "clean": cf[cf.drive.isin(TEST)], "att": E5.frame(*E5.load_kind("att_test", TEST), v),
           "ep": E5.frame(*E5.load_kind("ep_test", TEST), v)}
    for k, df in src.items():
        r = pd.DataFrame({"scan": df.scan.to_numpy(), "raw_L2b": lay.raw_scores(df)})
        fr[k] = fr[k].merge(r, on="scan", how="inner")
    return fr


def add_l4(fr):
    s7 = pd.read_pickle(S7STORE)
    for k in ("ref", "clean", "att", "ep"):
        fr[k] = fr[k].merge(s7[k][["scan", "raw_L4"]], on="scan", how="inner")
    return fr


def check_vs_s7(fr):
    """The headline layers recomputed here must equal the S7 score store (same scans, same layers)."""
    s7 = pd.read_pickle(S7STORE)
    out = {}
    for k in ("ref", "clean", "att", "ep"):
        m = fr[k].merge(s7[k], on="scan", suffixes=("", "_s7"))
        out[k] = {"rows": int(len(m)), "rows_s7": int(len(s7[k])), **{c: float(np.abs(m[c] - m[c + "_s7"]).max()) for c in L.HEAD}}
    return out


def v2_block(fr_att, fr_clean):
    """The v2 model (retrained v2 descriptor + XGBoost, 4 classes incl. box cloud; threshold = tie-safe 1 % of the validation normal scans, S1
    convention) scored on the SAME attacked and clean test scans, from the cached descriptor rows."""
    import xgboost as xgb
    model = xgb.XGBClassifier()
    model.load_model(str(CACHE / "retrained_deployed.json"))
    model.set_params(device="cpu", n_jobs=2)
    score = lambda X: 1.0 - model.predict_proba(np.asarray(X, np.float32))[:, 0]  # noqa
    _, xv = L4.normal_rows(VAL)
    thr = float(budget_threshold(score(xv), 0.01))
    nm, nx = L4.normal_rows(TEST)
    sc_clean = score(nx)
    metas, Xs = [], []
    for d in TEST:
        z = pd.read_pickle(L4.ROOT / f"l4_ev_{d}.pkl")
        metas.append(z["meta"])
        Xs.append(z["X"])
    meta, X = pd.concat(metas, ignore_index=True), np.vstack(Xs)
    s = score(X)
    meta = meta.assign(s=s, alarm=s >= thr)
    meta = meta[meta.scan.isin(fr_att.scan)]
    names = [a for a in PHYS + CMP if (meta.attack == a).any()]
    out = {"threshold": thr, "fa_test": float((sc_clean >= thr).mean()), "n_clean": int(len(sc_clean)), "det": detection_block(meta.alarm.to_numpy(), meta, names),
           "auc": {a: float(roc_auc_score(np.r_[np.zeros(len(sc_clean)), np.ones(int((meta.attack == a).sum()))], np.r_[sc_clean, meta.s[meta.attack == a]])) for a in names}}
    phys = meta[meta.attack.isin(PHYS)]
    out["auc_pooled_single_return_set"] = float(roc_auc_score(np.r_[np.zeros(len(sc_clean)), np.ones(len(phys))], np.r_[sc_clean, phys.s]))
    return out


def pooled_auc(st, clean, att):
    p = att[att.attack.isin(PHYS)]
    return float(roc_auc_score(np.r_[np.zeros(len(clean)), np.ones(len(p))], np.r_[st.stat(clean), st.stat(p)]))


def main():
    t0 = time.time()
    dev = json.loads((RES / "dev.json").read_text())
    method, dens = dev["V1"]["chosen"], dev["V2"]["density_kept"]
    if STORE.exists():
        fr = pd.read_pickle(STORE)
    else:
        fr = L.physics("final")
        print("physics frames", {k: v.shape for k, v in fr.items()}, f"{time.time() - t0:.0f}s", flush=True)
        fr = add_l4(add_l2b(fr))
        pd.to_pickle(fr, STORE)
        print("store written", {k: v.shape for k, v in fr.items()}, f"{time.time() - t0:.0f}s", flush=True)
    chk = check_vs_s7(fr)
    print("check vs S7 store", chk, flush=True)
    optional = {"L2b alone": ["raw_L2b"], "L4 alone": ["raw_L4"], "headline + L2b (optional)": L.HEAD + ["raw_L2b"],
                "headline + L4 (seen families, never headline)": L.HEAD + ["raw_L4"]}
    if dens:
        for k in fr:
            fr[k]["raw_L2aI"] = fr[k]["raw_L2a"]
            fr[k]["raw_L2a"] = fr[k]["raw_L2aF"]
        optional["intensity-only L2a"] = ["raw_L1", "raw_L2aI", "raw_L2c", "raw_L2d"]
    else:
        optional["density part added to L2a"] = L.HEAD_DENS
    res, st = analyse(fr, method, optional=optional)
    scores = res.pop("_scores")
    res["check_vs_s7_store"] = chk
    res["choices"] = {"combiner": method, "density_kept": bool(dens), "V1": dev["V1"], "V2": dev["V2"]}
    res["v2_side_by_side"] = v2_block(fr["att"], fr["clean"])
    res["v3_auc_pooled_single_return_set"] = pooled_auc(st, fr["clean"], fr["att"])
    res["exposure"] = "7th exposure of the KITTI LiDAR test drives (S1, S2, S3 sanity, S4, S5, S6, S7, S9)"
    res["seconds"] = time.time() - t0
    (RES / "final.json").write_text(json.dumps(res, indent=1, default=float))
    allsc = pd.concat([v.assign(frame=k) for k, v in scores.items()], ignore_index=True)
    allsc.to_csv(RES / "test_scores.csv.gz", index=False)
    h = res["headline"]
    print("FA", h["fa"], h["fa_ci95"], "worst drive", max(h["fa_per_drive"].values()))
    for a, v in h["det"].items():
        print(f"  {a:18s} {v['det']:.3f} [{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}]")
    print("done", res["seconds"])


if __name__ == "__main__":
    main()
