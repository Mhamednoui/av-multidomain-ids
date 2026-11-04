"""WP9 B3 step 5: the single TEST scoring (B3 test blocks), after selection + controls are committed.

Run from codes_v3/:  python -I -u -W ignore tools/WP9_B3_test.py
Guard: refuses to run if results/WP9/B3_selection.json or B3_controls.json is not committed, if the controls show a RED FLAG, or if B3_test.json already exists.
Scores: chosen multi-class model (operating points H = 1% val budget, S = val-F1-optimal, G = plain argmax), V3 L4 reference (binary, H and S).
Block bootstrap: 8 test blocks, 1000 resamples. Writes results/WP9/B3_test.json, scores/B3/test_chosen.npz, B3_exposure.json.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb

import WP9_B3_fit as FIT
import WP9_B3_lib as L
from v2x import l4

B = 1000


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def committed(path):
    r = subprocess.run(["git", "status", "--porcelain", "--", str(path)], cwd=ROOT, capture_output=True, text=True)
    t = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() == "" and t.returncode == 0


def summaries(meta, s, pred, thr, edges, k):
    return L.block_summaries(meta, s, pred, thr, edges, k_sender=k)


def pack(meta, s, pred, thr, edges, k, B=B):
    bl = summaries(meta, s, pred, thr, edges, k)
    point, ci = L.bootstrap(bl, B=B)
    return {"point": point, "ci95": ci, "n_blocks": len(bl)}


def main():
    out_path = L.OUT / "B3_test.json"
    assert not out_path.exists(), "test already scored once"
    for f in ("B3_selection.json", "B3_controls.json"):
        assert committed(L.OUT / f), f"{f} not committed before test"
    ctl = json.loads((L.OUT / "B3_controls.json").read_text())
    assert not ctl["importance"]["RED_FLAG"], "red flag: stop and report"
    sel = json.loads((L.OUT / "B3_selection.json").read_text())
    c = sel["chosen"]
    feats = L.SETS[c["set"]]
    L.journal("test: START single scoring (chosen " + c["name"] + ")")
    Fte, mte = L.load_part("test")
    yte = mte["label"].to_numpy().astype(int)
    X = Fte[feats].to_numpy(np.float32)
    if c["kind"] == "xgb":
        m = xgb.XGBClassifier()
        m.load_model(str(FIT.MODELS / f"{c['name']}.json"))
        P = m.predict_proba(X, iteration_range=(0, sel["chosen_best_iteration"] + 1))
    else:
        P = joblib.load(FIT.MODELS / f"{c['name']}.joblib").predict_proba(X)
    s = L.attack_score(P)
    cls = L.attack_class(P)
    # guard: reproduce the validation score of the saved model before trusting the test numbers
    Fva, mva = L.load_part("val")
    Pv = np.load(FIT.MODELS / f"{c['name']}_valP.npy")
    Pv2 = (m.predict_proba(Fva[feats].to_numpy(np.float32), iteration_range=(0, sel["chosen_best_iteration"] + 1)) if c["kind"] == "xgb"
           else joblib.load(FIT.MODELS / f"{c['name']}.joblib").predict_proba(Fva[feats].to_numpy(np.float32)))
    assert np.abs(Pv - Pv2).max() < 1e-5, "saved model does not reproduce validation scores"
    log("validation reproduction OK; test rows", len(yte))
    edges = L.score_edges(s)
    res = {"chosen": c, "ops": {}, "test_blocks": sorted(set(map(int, mte["block"].unique())))}
    for name, thr in (("H_budget1pct", sel["thr_H_budget1pct"]), ("S_valF1opt", sel["thr_S_valF1opt"])):
        pred = L.decide(s, cls, thr)
        k = sel["sender_k"]
        r = pack(mte, s, pred, thr, edges, k)
        r["thr"] = thr
        res["ops"][name] = r
        log(name, "macro-F1", round(r["point"]["macro_f1"], 4), r["ci95"]["macro_f1"], "FPR", round(r["point"]["fpr"], 4), "AUC", round(r["point"]["auc"], 4))
    pred_g = np.argmax(P, axis=1)
    sg = (pred_g != 0).astype(np.float64)
    bl = L.block_summaries(mte, sg, pred_g, 0.5, np.array([-np.inf, 0.5, np.inf]), None)
    pt, ci = L.bootstrap(bl, B=B)
    res["ops"]["G_argmax"] = {"point": pt, "ci95": ci, "n_blocks": len(bl)}
    # row-kind diagnostics at H
    predH = L.decide(s, cls, sel["thr_H_budget1pct"])
    kind = mte["kind"].to_numpy()
    kd = {}
    for kk, nm in ((0, "scored"), (1, "first_or_gap"), (2, "exact_repeat")):
        mk = kind == kk
        kd[nm] = {"n": int(mk.sum()), "genuine_n": int((mk & (yte == 0)).sum()), "genuine_alarm_rate": float((predH[mk & (yte == 0)] != 0).mean()) if (mk & (yte == 0)).any() else None,
                  "alarm_recall_by_class": {int(q): float((predH[mk & (yte == q)] != 0).mean()) for q in range(1, 20) if (mk & (yte == q)).any()}}
    res["row_kinds_H"] = kd
    ph = (Fte["x"].to_numpy() == 0) & (Fte["y"].to_numpy() == 0)
    res["class12_placeholder_H"] = {"placeholder_rows": int((ph & (yte == 12)).sum()), "recall_placeholder": float((predH[ph & (yte == 12)] != 0).mean()),
                                    "recall_other_rows": float((predH[~ph & (yte == 12)] != 0).mean()), "other_rows": int((~ph & (yte == 12)).sum())}
    # V3 L4 reference (binary, scored rows)
    g = l4.GBModel(L.V3_REF_FEATURES, {})
    g.model = xgb.XGBClassifier()
    g.model.load_model(str(FIT.MODELS / "v3ref.json"))
    p3 = np.where(kind == 0, g.predict(Fte), 0.0)
    ref = {}
    edges3 = L.score_edges(p3)
    for name, thr in (("H_budget1pct", sel["v3_reference"]["thr_1pct"]), ("S_valF1opt", sel["v3_reference"]["thr_f1opt"])):
        pred3 = np.where(p3 >= thr, 1, 0)
        ref[name] = pack(mte, p3, pred3, thr, edges3, None)
        ref[name]["thr"] = thr
        log("v3ref", name, "FPR", round(ref[name]["point"]["fpr"], 4), "AUC", round(ref[name]["point"]["auc"], 4))
    res["v3_reference"] = ref
    L.jd(res, out_path)
    np.savez_compressed(L.OUT / "scores" / "B3" / "test_chosen.npz", y=yte.astype(np.int8), s=s.astype(np.float32), c=cls.astype(np.int8), argmax=pred_g.astype(np.int8),
                        sender=mte["sender"].to_numpy(), pseudo=mte["pseudo"].to_numpy(), block=mte["block"].to_numpy(), t=mte["t"].to_numpy(), kind=kind, v3ref=p3.astype(np.float32))
    exp = {"VeReMi_B3_test": {"scored_on": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "models": [c["name"], "v3_L4_reference"], "lock": "locks/WP9_veremi.json",
                              "test_blocks": res["test_blocks"], "exposure_count": 1,
                              "note": "first test scoring of these blocks (never WP5/WP8 test); WP5 trained and tuned v3 L4 and its Kalman noise on them as train/val blocks; B3 refits all. H31 reused WP5 test blocks are NOT used in B3."}}
    L.jd(exp, L.OUT / "B3_exposure.json")
    L.journal("test: DONE results/WP9/B3_test.json, exposure registered")
    log("DONE")


if __name__ == "__main__":
    main()
