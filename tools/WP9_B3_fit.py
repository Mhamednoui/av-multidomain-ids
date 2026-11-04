"""WP9 B3 step 3: fit the pre-registered candidates on B3 train, evaluate on B3 VALIDATION only, select (notes/WP9_B3.md).

Run from codes_v3/:  python -I -u -W ignore tools/WP9_B3_fit.py [--select]
Resumable: one results/WP9/B3_parts/val_<cand>.json per candidate (skipped if present); models + validation probabilities in the cache.
--select writes results/WP9/B3_selection.json (chosen candidate, thresholds H and S, V3 L4 reference) and the validation score file; the TEST part is never read.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import joblib
import numpy as np
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier

import WP9_B3_lib as L
from common.config import SEED
from v2x import l4

PARTS = L.OUT / "B3_parts"
MODELS = L.CACHE / "models"
CANDS = ([{"name": f"xgb_{s}_d{d}", "kind": "xgb", "set": s, "depth": d} for s in L.SETS for d in (6, 8)]
         + [{"name": f"rf_{s}", "kind": "rf", "set": s, "depth": 99} for s in ("A_plaus", "D_all")])
XGB_PARAMS = dict(learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, reg_lambda=1.0, min_child_weight=1)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def fit_xgb(X, y, Xv, yv, depth, seed=SEED, max_rounds=300, patience=20):
    m = xgb.XGBClassifier(objective="multi:softprob", num_class=L.K, n_estimators=max_rounds, max_depth=depth, tree_method="hist", n_jobs=4, random_state=seed,
                          eval_metric="mlogloss", early_stopping_rounds=patience, **XGB_PARAMS)
    m.fit(X, y, eval_set=[(Xv, yv)], verbose=False)
    return m, int(m.best_iteration)


def fit_rf(X, y, seed=SEED):
    m = RandomForestClassifier(n_estimators=100, min_samples_leaf=20, max_features="sqrt", max_samples=0.3, n_jobs=4, random_state=seed)
    return m.fit(X, y)


def predict(m, kind, X, best=None):
    if kind == "xgb":
        return m.predict_proba(X, iteration_range=(0, best + 1))
    return m.predict_proba(X)


def run_candidate(c, Ftr, ytr, Fva, yva):
    feats = L.SETS[c["set"]]
    X, Xv = Ftr[feats].to_numpy(np.float32), Fva[feats].to_numpy(np.float32)
    t0 = time.time()
    if c["kind"] == "xgb":
        m, best = fit_xgb(X, ytr, Xv, yva, c["depth"])
        m.save_model(str(MODELS / f"{c['name']}.json"))
    else:
        m, best = fit_rf(X, ytr), None
        joblib.dump(m, MODELS / f"{c['name']}.joblib")
    P = predict(m, c["kind"], Xv, best).astype(np.float32)
    np.save(MODELS / f"{c['name']}_valP.npy", P)
    return P, best, time.time() - t0


def v3_reference(Ftr, mtr, Fva, mva):
    """v3 L4Scored recipe (binary XGBoost, S2_resid features, scored rows only; d5_mcw1 as chosen in WP5 S6), retrained on B3 train."""
    dev = json.loads((ROOT / "results/WP5/s6_dev.json").read_text())
    params = dev["chosen_params"]
    ktr, kva = mtr["kind"].to_numpy(), mva["kind"].to_numpy()
    s, sv = ktr == 0, kva == 0
    gb = l4.GBModel(L.V3_REF_FEATURES, params).fit(Ftr[s], (mtr["label"].to_numpy()[s] > 0).astype(int), Fva[sv], (mva["label"].to_numpy()[sv] > 0).astype(int))
    gb.model.save_model(str(MODELS / "v3ref.json"))
    p = np.where(kva == 0, gb.predict(Fva), 0.0)
    return gb, p


def main():
    PARTS.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)
    Ftr, mtr = L.load_part("train")
    Fva, mva = L.load_part("val")
    ytr, yva = mtr["label"].to_numpy().astype(int), mva["label"].to_numpy().astype(int)
    log("train", Ftr.shape, "val", Fva.shape)
    for c in CANDS:
        out = PARTS / f"val_{c['name']}.json"
        if out.exists():
            continue
        L.journal(f"fit {c['name']}: START (log results/WP9/logs/B3_fit.log)")
        P, best, sec = run_candidate(c, Ftr, ytr, Fva, yva)
        r = {"cand": c, "n_features": len(L.SETS[c["set"]]), "best_iteration": best, "seconds": sec, "val": L.val_summary(mva, P)}
        L.jd(r, out)
        log(c["name"], "best_it", best, f"{sec:.0f}s", {k: round(v, 4) for k, v in r["val"].items()})
        L.journal(f"fit {c['name']}: DONE val macro-F1 {r['val']['macro_f1']:.4f} FPR {r['val']['fpr']:.4f}")
    if "--select" in sys.argv:
        select(Ftr, mtr, Fva, mva)


def select(Ftr, mtr, Fva, mva):
    rows = [json.loads(p.read_text()) for p in sorted(PARTS.glob("val_*.json")) if not p.name.startswith("val_v3")]
    assert len(rows) == len(CANDS), (len(rows), len(CANDS))
    best = max(r["val"]["macro_f1"] for r in rows)
    tied = [r for r in rows if best - r["val"]["macro_f1"] < 0.002]
    tied.sort(key=lambda r: (r["n_features"], r["cand"]["depth"], 0 if r["cand"]["kind"] == "xgb" else 1))
    ch = tied[0]
    c = ch["cand"]
    P = np.load(MODELS / f"{c['name']}_valP.npy")
    yva = mva["label"].to_numpy()
    s = L.attack_score(P)
    thr_h = L.thr_budget(s[yva == 0], 0.01)
    thr_s, f1_s = L.thr_f1opt((yva > 0).astype(int), s)
    sec = L.val_summary(mva, P, thr_s)
    # sender-level k (validation): smallest k with <= 1% of genuine validation senders flagged
    import pandas as pd
    al = pd.DataFrame({"sender": mva["sender"].to_numpy(), "y": yva, "a": (s >= thr_h).astype(int)}).groupby("sender").agg(y=("y", "first"), a=("a", "sum"))
    cnt = al["a"].to_numpy()[al["y"].to_numpy() == 0]
    k = 1
    while (cnt >= k).mean() > 0.01 and k < 100000:
        k += 1
    gb, p3 = v3_reference(Ftr, mtr, Fva, mva)
    thr3 = L.thr_budget(p3[yva == 0], 0.01)
    from sklearn.metrics import roc_auc_score
    ref = {"auc": float(roc_auc_score((yva > 0).astype(int), p3)), "thr_1pct": float(thr3), "val_fpr": float((p3[yva == 0] >= thr3).mean()),
           "val_alarm_recall_mean_classes": float(np.mean([(p3[yva == k_] >= thr3).mean() for k_ in range(1, 20)])), "best_iteration": gb.best_iteration,
           "thr_f1opt": L.thr_f1opt((yva > 0).astype(int), p3)[0]}
    sel = {"rule": "max validation 20-class macro-F1 at the 1% genuine budget; ties (< 0.002) -> fewer features, smaller depth, XGB before RF",
           "chosen": c, "chosen_best_iteration": ch["best_iteration"], "chosen_val": ch["val"], "tied_with_best": [r["cand"]["name"] for r in tied],
           "thr_H_budget1pct": float(thr_h), "thr_S_valF1opt": float(thr_s), "val_binary_f1_at_S": f1_s, "val_at_S": sec, "sender_k": int(k),
           "val_genuine_sender_fa_at_k": float((cnt >= k).mean()),
           "v3_reference": ref, "all_candidates": {r["cand"]["name"]: r["val"] for r in rows}}
    L.jd(sel, L.OUT / "B3_selection.json")
    np.savez_compressed(L.OUT / "scores" / "B3" / "val_chosen.npz", y=yva.astype(np.int8), s=s.astype(np.float32), c=L.attack_class(P).astype(np.int8),
                        sender=mva["sender"].to_numpy(), block=mva["block"].to_numpy(), v3ref=p3.astype(np.float32))
    log("CHOSEN", c["name"], ch["val"], "thr_H", thr_h, "thr_S", thr_s, "k", k)
    L.journal(f"select: chosen {c['name']} val macro-F1 {ch['val']['macro_f1']:.4f}; results/WP9/B3_selection.json")


if __name__ == "__main__":
    (L.OUT / "scores" / "B3").mkdir(parents=True, exist_ok=True)
    main()
