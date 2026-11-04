"""WP9 B2: supervised multiclass benchmark on one (table, protocol): candidates -> selection on validation -> shuffled control (validation) -> single test scoring.

Inputs: cache table ../data_extra/cache_v3/WP9/B2/<table>.pkl + <table>_parts.npz (locked splits, locks/WP9_<table>.json).
Outputs: results/WP9/B2/<table>_<proto>_select.json, _control.json, _test.json and parts/ (val metrics per candidate);
         scores results/WP9/scores/B2/<table>_<proto>_{val,test}.npz (labels, probabilities, ids) per WP8 crash-safety rule 6.
Stages (resumable; each stage skips if its output exists): cand, select, control, test. Test is touched only by stage `test`, once.
References: Moczkodan & Ragab arXiv 2606.11098 (protocol bar), codes_v3/network/l4.py (v3 supervised XGBoost layer, class weights), Chen & Guestrin 2016.
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_run.py <table> <T|G|B> [stage ...]
"""
import json, os, sys, time
import numpy as np, pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from network import flows as F
from network import l3
from network.l4 import class_weights

CACHE = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP9", "B2")
RES = os.path.join(ROOT, "results", "WP9", "B2")
SCORES = os.path.join(ROOT, "results", "WP9", "scores", "B2")
FEATS = F.FEATURES
CLEAN = l3.feature_set("clean")
SEED = 42
BENIGN_CAP = 250_000
MIN_N = 20
NJOBS = 4
CANDS = [
    {"id": "xgb_d6_f76", "kind": "xgb", "depth": 6, "feats": "f76"},
    {"id": "xgb_d6_c60", "kind": "xgb", "depth": 6, "feats": "c60"},
    {"id": "xgb_d10_f76", "kind": "xgb", "depth": 10, "feats": "f76"},
    {"id": "rf_f76", "kind": "rf", "feats": "f76"},
    {"id": "rf_c60", "kind": "rf", "feats": "c60"},
]


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def load(table, proto):
    d = pd.read_pickle(os.path.join(CACHE, table + ".pkl"), compression="gzip")
    z = np.load(os.path.join(CACHE, table + "_parts.npz"))
    return d, z[proto], z["boot"]


def cols_of(name):
    return FEATS if name == "f76" else CLEAN


def matrix(d, cols, fill=None):
    x = d[cols].to_numpy(np.float32)
    x = np.where(np.isinf(x), np.nan, x)
    return np.nan_to_num(x, nan=fill) if fill is not None else x


_XC = {}


def mx(d, idx, cols, fill=None):
    """Feature matrix of rows idx: the full float32 matrix of the table is built once (76 columns) and indexed."""
    k = id(d)
    if k not in _XC:
        _XC.clear()
        x = d[FEATS].to_numpy(np.float32)
        _XC[k] = np.where(np.isinf(x), np.nan, x)
    X = _XC[k]
    ci = slice(None) if cols is FEATS else [FEATS.index(c) for c in cols]
    x = X[idx][:, ci] if not isinstance(ci, slice) else X[idx]
    return np.nan_to_num(x, nan=fill) if fill is not None else x


def weights(d):
    return d["wt"].to_numpy(np.float64) if "wt" in d.columns else np.ones(len(d))


CLASS_CAP = {"D23x": 60_000}


def train_sample(d, part, table="D10"):
    fam = d["family"].to_numpy()
    tr = np.where(part == 0)[0]
    ben = tr[fam[tr] == "BENIGN"]
    rng = np.random.default_rng(0)
    if len(ben) > BENIGN_CAP:
        ben = rng.choice(ben, BENIGN_CAP, replace=False)
    cap = CLASS_CAP.get(table, 150_000)
    keep = [ben]
    for c in sorted(set(fam[tr]) - {"BENIGN"}):
        ii = tr[fam[tr] == c]
        keep.append(rng.choice(ii, cap, replace=False) if len(ii) > cap else ii)
    return np.sort(np.concatenate(keep))


def fit_predict(cand, d, tr_idx, y_tr, classes, ev_sets, seed=SEED, val_idx=None, y_val=None):
    """Fit one candidate on train rows tr_idx (labels y_tr = class codes) and return probabilities for each index array in ev_sets."""
    cols = cols_of(cand["feats"])
    ncls = len(classes)
    w = class_weights(np.array(classes)[y_tr], 0.5)
    if cand["kind"] == "xgb":
        import xgboost as xgb
        Xtr = mx(d, tr_idx, cols)
        m = xgb.XGBClassifier(n_estimators=300, max_depth=cand["depth"], learning_rate=0.2, subsample=0.8, colsample_bytree=0.7, min_child_weight=1,
                              tree_method="hist", n_jobs=NJOBS, objective="multi:softprob", num_class=ncls, eval_metric="mlogloss",
                              early_stopping_rounds=30 if val_idx is not None else None, random_state=seed)
        kw = {}
        if val_idx is not None:
            kw["eval_set"] = [(mx(d, val_idx, cols), y_val)]
        m.fit(Xtr, y_tr, sample_weight=w, verbose=False, **kw)
        imp = m.get_booster().get_score(importance_type="total_gain")
        tot = sum(imp.values()) or 1.0
        imp = {cols[int(k[1:])]: v / tot for k, v in imp.items()}
        info = {"best_iteration": int(getattr(m, "best_iteration", 299)) + 1}
        n_use = info["best_iteration"] if val_idx is not None else 300
        predict = lambda idx: m.predict_proba(mx(d, idx, cols), iteration_range=(0, n_use))
    else:
        from sklearn.ensemble import RandomForestClassifier
        Xtr = mx(d, tr_idx, cols, fill=-1.0)
        m = RandomForestClassifier(n_estimators=150, max_depth=30, min_samples_leaf=2, max_features="sqrt", class_weight="balanced_subsample",
                                   n_jobs=NJOBS, random_state=seed)
        m.fit(Xtr, y_tr)
        imp = dict(zip(cols, m.feature_importances_.tolist()))
        info = {}
        predict = lambda idx: m.predict_proba(mx(d, idx, cols, fill=-1.0))
    imp = dict(sorted(imp.items(), key=lambda kv: -kv[1]))
    out = []
    for idx in ev_sets:
        pr = np.zeros((len(idx), ncls), np.float32)
        for a in range(0, len(idx), 200_000):
            pr[a:a + 200_000] = predict(idx[a:a + 200_000]).astype(np.float32)
        out.append(pr)
    return out, imp, info


def encode(d, part):
    fam = d["family"].to_numpy()
    classes = sorted(set(fam[part == 0]), key=lambda c: (c != "BENIGN", c))
    assert classes[0] == "BENIGN"
    return classes, {c: i for i, c in enumerate(classes)}


def eligible(fam_eval, fam_train, classes):
    ce = pd.Series(fam_eval).value_counts()
    ct = pd.Series(fam_train).value_counts()
    return [c for c in classes if ce.get(c, 0) >= MIN_N and ct.get(c, 0) >= MIN_N]


def conf_counts(y, pred, grp, ncls, ng, w=None):
    """counts[g, true, pred] (weighted by w when given)"""
    k = (grp.astype(np.int64) * ncls + y) * ncls + pred
    return np.bincount(k, weights=w, minlength=ng * ncls * ncls).reshape(ng, ncls, ncls)


def f1_from_conf(C, elig_idx):
    tp = np.diag(C).astype(float)
    fp = C.sum(0) - tp
    fn = C.sum(1) - tp
    f1 = np.where(2 * tp + fp + fn > 0, 2 * tp / np.maximum(2 * tp + fp + fn, 1), 0.0)
    rec = np.where(tp + fn > 0, tp / np.maximum(tp + fn, 1), np.nan)
    prec = np.where(tp + fp > 0, tp / np.maximum(tp + fp, 1), np.nan)
    return f1, rec, prec, float(np.mean(f1[elig_idx]))


def metrics_basic(y, pr, classes, fam_train, fam_eval, w=None):
    """macro-F1 over eligible classes, FPR, binary AUC (score 1 - P(benign))."""
    from sklearn.metrics import roc_auc_score
    ncls = len(classes)
    pred = pr.argmax(1)
    C = conf_counts(y, pred, np.zeros(len(y), int), ncls, 1, w)[0]
    el = [classes.index(c) for c in eligible(fam_eval, fam_train, classes)]
    f1, rec, prec, mf1 = f1_from_conf(C, el)
    ben = y == 0
    out = {"macro_f1": mf1, "eligible": [classes[i] for i in el], "fpr": float(1 - C[0, 0] / C[0].sum()) if ben.any() else None,
           "per_class_recall": {c: (None if np.isnan(rec[i]) else float(rec[i])) for i, c in enumerate(classes)},
           "per_class_f1": {c: float(f1[i]) for i, c in enumerate(classes)}}
    out["auc_binary"] = float(roc_auc_score(~ben, 1.0 - pr[:, 0], sample_weight=w)) if ben.any() and (~ben).any() else None
    return out


def prep(table, proto):
    d, part, boot = load(table, proto)
    classes, cmap = encode(d, part)
    fam = d["family"].to_numpy()
    tr_all = train_sample(d, part, table)
    y_tr = np.array([cmap[c] for c in fam[tr_all]])
    va = np.where(part == 1)[0]
    y_va = np.array([cmap.get(c, -1) for c in fam[va]])
    return d, part, boot, classes, cmap, fam, tr_all, y_tr, va, y_va


def run_cands(table, proto):
    d, part, boot, classes, cmap, fam, tr_all, y_tr, va, y_va = prep(table, proto)
    keep = y_va >= 0
    od = os.path.join(RES, "parts")
    os.makedirs(od, exist_ok=True)
    log("cands", table, proto, "train", len(tr_all), "val", len(va), "classes", classes)
    for c in CANDS:
        p = os.path.join(od, "%s_%s_%s.json" % (table, proto, c["id"]))
        if os.path.exists(p):
            continue
        t0 = time.time()
        is_x = c["kind"] == "xgb"
        (pr,), imp, info = fit_predict(c, d, tr_all, y_tr, classes, [va], val_idx=va[keep] if is_x else None, y_val=y_va[keep] if is_x else None)
        m = metrics_basic(y_va[keep], pr[keep], classes, fam[tr_all], fam[va][keep], weights(d)[va][keep])
        m.update({"cand": c, "importance_top5": dict(list(imp.items())[:5]), "info": info, "seconds": round(time.time() - t0, 1)})
        json.dump(m, open(p + ".tmp", "w"), indent=1)
        os.replace(p + ".tmp", p)
        log(table, proto, c["id"], "val macroF1 %.4f fpr %.4f auc %.4f" % (m["macro_f1"], m["fpr"], m["auc_binary"]), "top", list(imp.items())[:2], "%ss" % m["seconds"])


def run_select(table, proto):
    p = os.path.join(RES, "%s_%s_select.json" % (table, proto))
    if os.path.exists(p):
        return
    rows = [json.load(open(os.path.join(RES, "parts", "%s_%s_%s.json" % (table, proto, c["id"])))) for c in CANDS]
    best = max(rows, key=lambda r: (round(r["macro_f1"], 6), r["cand"]["feats"] == "c60"))
    sel = {"selected": best["cand"], "eligible_val": best["eligible"],
           "val": {r["cand"]["id"]: {"macro_f1": r["macro_f1"], "fpr": r["fpr"], "auc": r["auc_binary"], "top_feature": list(r["importance_top5"].items())[0]} for r in rows},
           "rule": "max val macro-F1 over eligible classes (>=20 in train and val); tie -> clean60"}
    json.dump(sel, open(p, "w"), indent=1)
    log("selected", best["cand"]["id"], {k: round(v["macro_f1"], 4) for k, v in sel["val"].items()})


def run_control(table, proto):
    p = os.path.join(RES, "%s_%s_control.json" % (table, proto))
    if os.path.exists(p):
        return
    sel = json.load(open(os.path.join(RES, "%s_%s_select.json" % (table, proto))))
    cand = sel["selected"]
    d, part, boot, classes, cmap, fam, tr_all, y_tr, va, y_va = prep(table, proto)
    keep = y_va >= 0
    is_x = cand["kind"] == "xgb"
    res = []
    for seed in (1, 2, 3):
        y_sh = np.random.default_rng(seed).permutation(y_tr)
        (pr,), imp, info = fit_predict(cand, d, tr_all, y_sh, classes, [va], seed=seed, val_idx=va[keep] if is_x else None, y_val=y_va[keep] if is_x else None)
        m = metrics_basic(y_va[keep], pr[keep], classes, fam[tr_all], fam[va][keep], weights(d)[va][keep])
        res.append({"seed": seed, "macro_f1": m["macro_f1"], "auc_binary": m["auc_binary"], "fpr": m["fpr"]})
        log("control", table, proto, res[-1])
    real = sel["val"][cand["id"]]
    ok = bool(max(r["auc_binary"] for r in res) <= 0.55 and np.mean([r["macro_f1"] for r in res]) < 0.5 * real["macro_f1"])
    json.dump({"cand": cand, "runs": res, "real_val": real, "pass": ok,
               "rule": "max AUC <= 0.55 and mean macro-F1 < 0.5 x real val macro-F1; scored on validation only"}, open(p, "w"), indent=1)


def run_test(table, proto):
    p = os.path.join(RES, "%s_%s_test.json" % (table, proto))
    if os.path.exists(p):
        log("test already scored; refusing to rescore", p)
        return
    from WP9_B2_report import report
    sel = json.load(open(os.path.join(RES, "%s_%s_select.json" % (table, proto))))
    cand = sel["selected"]
    d, part, boot, classes, cmap, fam, tr_all, y_tr, va, y_va = prep(table, proto)
    te = np.where(part == 2)[0]
    keep = y_va >= 0
    is_x = cand["kind"] == "xgb"
    log("TEST scoring once", table, proto, cand)
    (pv, pt), imp, info = fit_predict(cand, d, tr_all, y_tr, classes, [va, te], val_idx=va[keep] if is_x else None, y_val=y_va[keep] if is_x else None)
    os.makedirs(SCORES, exist_ok=True)
    cls_arr = np.array(classes)
    y_te = np.array([cmap.get(c, -1) for c in fam[te]])
    np.savez_compressed(os.path.join(SCORES, "%s_%s_val.npz" % (table, proto)), idx=va, y=y_va, family=fam[va], proba=pv.astype(np.float16), classes=cls_arr, boot=boot[va])
    np.savez_compressed(os.path.join(SCORES, "%s_%s_test.npz" % (table, proto)), idx=te, y=y_te, family=fam[te], proba=pt.astype(np.float16), classes=cls_arr, boot=boot[te])
    rep = report(classes, fam[tr_all], fam[va], pv, fam[te], pt, boot[te], weights(d)[va], weights(d)[te])
    rep.update({"table": table, "protocol": proto, "cand": cand, "importance_top10": dict(list(imp.items())[:10]), "fit_info": info, "train_rows": int(len(tr_all)),
                "test_rows": int(len(te)), "scored_once": True, "time": time.strftime("%Y-%m-%dT%H:%M:%S")})
    json.dump(rep, open(p, "w"), indent=1)
    log("TEST", table, proto, "macroF1 %.4f [%.4f, %.4f] fpr %.4f auc %.4f" % (rep["macro_f1"], rep["macro_f1_ci"][0], rep["macro_f1_ci"][1], rep["fpr"], rep["auc_binary"]))


if __name__ == "__main__":
    table, proto = sys.argv[1], sys.argv[2]
    stages = sys.argv[3:] or ["cand", "select", "control", "test"]
    os.makedirs(RES, exist_ok=True)
    for s in stages:
        {"cand": run_cands, "select": run_select, "control": run_control, "test": run_test}[s](table, proto)
