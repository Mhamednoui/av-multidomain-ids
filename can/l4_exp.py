"""WP2 S6: experiment machinery for the L4 models (training, window tables, variant choice, controls).

Shared by tools/WP2_S6_road.py, _ch.py and _d11.py. A capture is a cache dict (tools/WP2_S6_cache.py) turned into a
feature dict F (can.l1.make_features, windows) plus period-resolved float32 matrices. Window table = one row per 1 s
window (group, sec, w_end, y, att, clean) with the 14 variant scores of each model (columns 't0'..'t13', 'p0'..'p13').
Nothing here reads test labels to choose anything.
Inputs: cache dicts. Outputs: models (XGBoost), DataFrames, dicts for results/WP2/s6_*.json.
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, roc_auc_score

from can import l1 as L
from can import l1_exp as E
from can import l4_features as G
from common.metrics import budget_threshold

SPACE = {"max_depth": [3, 4, 5, 6, 8, 10], "learning_rate": [0.03, 0.05, 0.1, 0.2], "subsample": [0.7, 0.8, 0.9, 1.0],
         "colsample_bytree": [0.5, 0.7, 0.9, 1.0], "min_child_weight": [1, 3, 5], "reg_lambda": [0.5, 1.0, 3.0]}
MODELS = {"t": ("can.l4_timing", G.TIMING), "p": ("can.l4_payload", G.FEATURES)}
N_JOBS = 4
MAX_TREES = 500


def class_weights(y, power=0.5):
    counts = np.bincount(y, minlength=2)
    w = (counts.max() / np.maximum(counts, 1)) ** power
    w = w[y]
    return w / w.mean()


def _clf(params, n_trees, seed, es=None):
    kw = dict(early_stopping_rounds=es) if es else {}
    return xgb.XGBClassifier(n_estimators=n_trees, tree_method="hist", device="cpu", n_jobs=N_JOBS, random_state=seed,
                             objective="binary:logistic", eval_metric="logloss", **kw, **params)


def search(Xtr, ytr, Xva, yva, n_iter, seed=42, log=print):
    """v2 random search; early stopping on validation logloss; choice = validation frame average precision."""
    rng = np.random.default_rng(seed)
    best, trials = None, []
    for k in range(n_iter):
        params = {key: vals[rng.integers(len(vals))] for key, vals in SPACE.items()}
        m = _clf(params, MAX_TREES, 42, es=30)
        m.fit(Xtr, ytr, sample_weight=class_weights(ytr), eval_set=[(Xva, yva)], verbose=False)
        ap = float(average_precision_score(yva, m.predict_proba(Xva)[:, 1]))
        trials.append({"params": params, "val_ap": ap, "n_trees": int(m.best_iteration + 1)})
        if best is None or ap > best[1]:
            best = (m, ap, params, int(m.best_iteration + 1))
        log(f"  trial {k + 1}/{n_iter} val AP {ap:.4f} trees {trials[-1]['n_trees']} best {best[1]:.4f}")
    return best[0], {"params": best[2], "n_trees": best[3], "val_ap": best[1], "trials": trials}


def fit_fixed(X, y, params, n_trees, seed=42):
    m = _clf(params, n_trees, seed)
    m.fit(X, y, sample_weight=class_weights(y), verbose=False)
    return m


def importance(model, cols) -> dict:
    g = model.get_booster().get_score(importance_type="total_gain")
    tot = sum(g.values()) or 1.0
    return {c: float(g.get(f"f{i}", 0.0) / tot) for i, c in enumerate(cols)}


# ------------------------------------------------------------------ captures
def cap_F(d: dict, codes: E.AttCodes, base: int, clean, windows=True) -> dict:
    att = codes.map(d["att_names"], d["att_codes"])
    return L.make_features(d["t"], d["id"], d["dlc"], d["label"], att, clean, group_code=base, windows=windows)


def raw_of(d: dict, m=None) -> dict:
    keys = ("dt_prev", "dt_id", "n_id", "n_uniq", "bchg")
    return {k: (d[k] if m is None else d[k][m]) for k in keys}


def matrix(d: dict, period: dict, cols, m=None) -> np.ndarray:
    ids, dlc, B = (d["id"], d["dlc"], d["B"]) if m is None else (d["id"][m], d["dlc"][m], d["B"][m])
    return G.feature_matrix(raw_of(d, m), ids, dlc, B, period, cols)


def period_of(items) -> dict:
    """items: iterable of (cache dict, clean-frame mask)."""
    pb = G.PeriodBuilder()
    for d, m in items:
        pb.add(d["id"][m], d["dt_id"][m])
    return pb.finish()


def sample_mask(label, rate, rng):
    return (label != 0) | (rng.random(len(label)) < rate)


def predict(model, X, chunk=2_000_000):
    """Frame score = raw log-odds margin (monotone in the probability; no float32 saturation at p = 1, which created
    tie blocks above the clean-window threshold: design change 1, ROAD validation)."""
    out = np.empty(len(X), np.float32)
    for a in range(0, len(X), chunk):
        out[a:a + chunk] = model.predict(X[a:a + chunk], output_margin=True)
    return out


# ------------------------------------------------------------------ windows
def window_rows(F: dict, group: str, scores: dict, extra=None) -> pd.DataFrame:
    """scores: {'t': frame p of the timing model, 'p': payload}. One row per window."""
    wk = F["wkeys"]
    d = {"group": np.full(len(wk), group, dtype=object), "sec": (wk % L.WIN_SPAN).astype(np.int64), "w_end": F["w_end"],
         "y": L.window_reduce(F, F["label"]).astype(np.int8),
         "att": L.window_reduce(F, np.where(F["label"] > 0, F["att"], 0)).astype(np.int16),
         "clean": L.window_reduce(F, F["clean"].astype(np.int8), "min").astype(bool),
         "nf": np.diff(np.r_[F["ws"], len(F["wo"])]).astype(np.int32)}
    for k, p in scores.items():
        W = G.window_kth(F, p, F["id"])
        for vi in range(W.shape[1]):
            d[f"{k}{vi}"] = W[:, vi]
    if extra:
        d.update(extra)
    return pd.DataFrame(d)


def clean_mask(tbl):
    return (tbl["clean"] & (tbl["y"] == 0)).to_numpy()


def select_variant(tbl: pd.DataFrame, k: str, codes: E.AttCodes, budget=0.01) -> dict:
    """Variant with the highest mean window recall over attack types at the tie-safe budget on the clean windows of tbl."""
    y, att, cl = (tbl["y"] == 1).to_numpy(), tbl["att"].to_numpy(), clean_mask(tbl)
    types = sorted({int(a) for a in np.unique(att[y])})
    res = {}
    for vi, v in enumerate(G.VARIANTS):
        raw = tbl[f"{k}{vi}"].to_numpy()
        thr = budget_threshold(raw[cl], budget)
        al = raw >= thr
        rec = {codes.names[a]: float(al[y & (att == a)].mean()) for a in types}
        res[vi] = {"variant": list(v), "mean_recall": float(np.mean(list(rec.values()))) if rec else 0.0, "recall": rec,
                   "threshold": float(thr), "fa_clean": float(al[cl].mean())}
    best = max(res, key=lambda i: (res[i]["mean_recall"], -i))
    return {"chosen": int(best), "variants": {str(i): v for i, v in res.items()}}


def alarms(tbl, k, vi, thr):
    return tbl[f"{k}{vi}"].to_numpy() >= thr


def window_auc(tbl, k, vi) -> float:
    y = (tbl["y"] == 1).to_numpy()
    keep = y | clean_mask(tbl)
    if y[keep].min() == y[keep].max():
        return float("nan")
    return float(roc_auc_score(y[keep], tbl[f"{k}{vi}"].to_numpy()[keep]))


def count_auc(tbl) -> float:
    """AUC of the number of frames in the window as a score: the reference for a window k-th-largest score of pure noise
    (more frames in a window = a larger k-th largest of noise)."""
    y = (tbl["y"] == 1).to_numpy()
    keep = y | clean_mask(tbl)
    return float(roc_auc_score(y[keep], tbl["nf"].to_numpy()[keep]))


def frame_auc(y, p) -> float:
    return float(roc_auc_score(y, p)) if y.min() != y.max() else float("nan")


def capture_table(tbl, al, first_inj, codes):
    return E.per_group(tbl, {"alarm": al}, first_inj, codes)
