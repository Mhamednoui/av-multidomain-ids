"""WP9 B3 step 4: controls on VALIDATION for the selected configuration + the v3 L4 reference (notes/WP9_B3.md, 'Controls'). TEST is never read.

1 shuffled-label (row permutation of train labels)  2 within-block sender-label permutation  3 proxy-only model (time, sender id, pseudonym)
4 feature importance + red-flag rule.  Pass band for AUC (attack vs genuine on validation): [0.42, 0.58].
Run from codes_v3/:  python -I -u -W ignore tools/WP9_B3_controls.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

import WP9_B3_fit as FIT
import WP9_B3_lib as L
from common.config import SEED
from v2x import l4

BAND = (0.42, 0.58)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def val_auc(P, yva):
    return float(roc_auc_score((yva > 0).astype(int), L.attack_score(P)))


def fit_fixed(c, X, y, best):
    if c["kind"] == "xgb":
        m = xgb.XGBClassifier(objective="multi:softprob", num_class=L.K, n_estimators=best + 1, max_depth=c["depth"], tree_method="hist", n_jobs=4, random_state=SEED,
                              eval_metric="mlogloss", **FIT.XGB_PARAMS)
        m.fit(X, y, verbose=False)
        return m
    return FIT.fit_rf(X, y)


def importance(c, m, feats):
    if c["kind"] == "xgb":
        g = m.get_booster().get_score(importance_type="total_gain")
        tot = sum(g.values()) or 1.0
        imp = {feats[int(k[1:])]: v / tot for k, v in g.items()}
    else:
        imp = dict(zip(feats, m.feature_importances_.tolist()))
    return dict(sorted(imp.items(), key=lambda kv: -kv[1]))


def main():
    sel = json.loads((L.OUT / "B3_selection.json").read_text())
    c, best = sel["chosen"], sel["chosen_best_iteration"]
    feats = L.SETS[c["set"]]
    Ftr, mtr = L.load_part("train")
    Fva, mva = L.load_part("val")
    ytr, yva = mtr["label"].to_numpy().astype(int), mva["label"].to_numpy().astype(int)
    X, Xv = Ftr[feats].to_numpy(np.float32), Fva[feats].to_numpy(np.float32)
    out = {"chosen": c, "band": BAND, "units": {}}
    rng = np.random.RandomState(SEED)
    # --- chosen unit, true labels (importance) ---
    L.journal("controls: START chosen-unit importance + shuffled + within-block permutation (log results/WP9/logs/B3_controls.log)")
    m_true = FIT.fit_xgb if False else None
    if c["kind"] == "xgb":
        m = xgb.XGBClassifier()
        m.load_model(str(FIT.MODELS / f"{c['name']}.json"))
    else:
        import joblib
        m = joblib.load(FIT.MODELS / f"{c['name']}.joblib")
    imp = importance(c, m, feats)
    top = list(imp.items())[:10]
    t_share = sum(v for k, v in imp.items() if k in L.T3)
    xy_share = sum(v for k, v in imp.items() if k in ("x", "y"))
    flag = bool(max(imp.values()) > 0.5 or t_share > 0.5 or xy_share > 0.5)
    out["importance"] = {"top10": top, "track_descriptor_share": t_share, "raw_xy_share": xy_share, "max_share": max(imp.values()), "RED_FLAG": flag,
                         "all": imp}
    log("importance top", [(k, round(v, 3)) for k, v in top[:6]], "T share", round(t_share, 3), "xy share", round(xy_share, 3), "RED FLAG" if flag else "no flag")
    # 1 shuffled labels
    y_sh = rng.permutation(ytr)
    ms = fit_fixed(c, X, y_sh, best)
    Ps = FIT.predict(ms, c["kind"], Xv, best)
    out["units"]["chosen_shuffled_rows"] = {"val_auc": val_auc(Ps, yva)}
    log("shuffled rows", out["units"]["chosen_shuffled_rows"])
    # 2 within-block sender permutation
    y_wb = ytr.copy()
    for b in np.unique(mtr["block"].to_numpy()):
        idx = np.flatnonzero(mtr["block"].to_numpy() == b)
        snd = mtr["sender"].to_numpy()[idx]
        us, first = np.unique(snd, return_index=True)
        lab = ytr[idx][first]
        perm = dict(zip(us, rng.permutation(lab)))
        y_wb[idx] = np.array([perm[s] for s in snd])
    mw = fit_fixed(c, X, y_wb, best)
    Pw = FIT.predict(mw, c["kind"], Xv, best)
    out["units"]["chosen_within_block_sender_permutation"] = {"val_auc": val_auc(Pw, yva)}
    log("within-block", out["units"]["chosen_within_block_sender_permutation"])
    # 2b sender-label permutation over the whole train (labels constant inside a sender, shuffled across senders)
    us, first = np.unique(mtr["sender"].to_numpy(), return_index=True)
    lab = ytr[first]
    perm = dict(zip(us, rng.permutation(lab)))
    y_sp = np.array([perm[s] for s in mtr["sender"].to_numpy()])
    mp = fit_fixed(c, X, y_sp, best)
    out["units"]["chosen_sender_permutation_global"] = {"val_auc": val_auc(FIT.predict(mp, c["kind"], Xv, best), yva)}
    log("sender permutation global", out["units"]["chosen_sender_permutation_global"])
    # 3 proxy-only model
    prox = ["t", "sender", "pseudo"]
    Xp, Xpv = mtr[prox].to_numpy(np.float64), mva[prox].to_numpy(np.float64)
    mpx = xgb.XGBClassifier(n_estimators=200, max_depth=6, learning_rate=0.1, tree_method="hist", n_jobs=4, random_state=SEED, eval_metric="logloss")
    mpx.fit(Xp, (ytr > 0).astype(int), verbose=False)
    out["units"]["proxy_only_t_sender_pseudo"] = {"val_auc": float(roc_auc_score((yva > 0).astype(int), mpx.predict_proba(Xpv)[:, 1]))}
    log("proxy only", out["units"]["proxy_only_t_sender_pseudo"])
    # V3 reference unit: shuffled labels + within-block permutation (binary, scored rows)
    dev = json.loads((ROOT / "results/WP5/s6_dev.json").read_text())
    ktr, kva = mtr["kind"].to_numpy(), mva["kind"].to_numpy()
    s_tr, s_va = ktr == 0, kva == 0
    nb = sel["v3_reference"]["best_iteration"]
    for nm, yy in (("v3ref_shuffled_rows", rng.permutation(ytr)), ("v3ref_within_block_sender_permutation", y_wb)):
        g = l4.GBModel(L.V3_REF_FEATURES, dev["chosen_params"], n_estimators=nb + 1).fit(Ftr[s_tr], (yy[s_tr] > 0).astype(int))
        p = np.where(s_va, g.predict(Fva), 0.0)
        out["units"][nm] = {"val_auc": float(roc_auc_score((yva > 0).astype(int), p)), "val_auc_scored_rows": float(roc_auc_score((yva[s_va] > 0).astype(int), p[s_va]))}
        log(nm, out["units"][nm])
    for k, v in out["units"].items():
        v["pass"] = bool(BAND[0] <= v["val_auc"] <= BAND[1])
    out["all_pass"] = all(v["pass"] for v in out["units"].values())
    L.jd(out, L.OUT / "B3_controls.json")
    L.journal(f"controls: DONE all_pass={out['all_pass']} red_flag={flag}; results/WP9/B3_controls.json")
    log("DONE all_pass", out["all_pass"], "red_flag", flag)


if __name__ == "__main__":
    main()
