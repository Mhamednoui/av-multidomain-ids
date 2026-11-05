"""WP9 B4 GPS library: AV-GPS sessions (locks/WP9_avgps.json), feature sets F_full / F_nosat / F_kin, XGBoost fit, metrics, session-cluster bootstrap.

Inputs: ../codes/data/AV-GPS-Dataset-*.csv (read only), locks/WP9_avgps.json. Outputs: DataFrames / dicts. References: Abrar et al., arXiv 2405.08359.
Feature sets and rules: notes/WP9_B4.md (pre-registration, 2026-11-05).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

from common.metrics import budget_threshold

AV = ROOT.parent / "codes" / "data" / "AV-GPS-Dataset"
LOCK = json.loads((ROOT / "locks" / "WP9_avgps.json").read_text())
M_PER_DEG = 111_194.9
EXCLUDE = ["Run Time", "Clock Time", "Clock Date", "Hobbs", "GPS MGRS", "EKF Detector", "Data Type"]
SAT = ["GPS HDOP", "GPS VDOP", "Satellite Locks", "Satellite Count"]
KIN = ["pos_step_m", "speed_gap", "heading_gap", "pos_step_m5", "speed_gap5", "heading_gap5", "Velocity (m/s)", "Yaw Rate (deg/s)", "Steering Angle (deg)", "Throttle (%)"]
KIN_NOVS = ["pos_step_m", "speed_gap", "heading_gap", "pos_step_m5", "speed_gap5", "heading_gap5"]          # amendment 1 (2026-11-05, validation seen, test not): no vehicle-state field as such
POS = ["pos_step_m", "pos_step_m5", "course_change", "course_change5", "GPS Course"]                       # amendment 1: position / receiver-course only
PROXY = ["Velocity (m/s)", "Throttle (%)", "Steering Angle (deg)", "Yaw Rate (deg/s)", "Roll (deg)", "Pitch (deg)"]


def derived(g):
    """kinematic features from lat / lon / Velocity / Heading of ONE session (rows 1 s apart, previous row of the same session only)."""
    lat, lon = g["GPS Latitude"].to_numpy(float), g["GPS Longitude"].to_numpy(float)
    dx = np.r_[np.nan, np.diff(lon)] * M_PER_DEG * np.cos(np.radians(lat))
    dy = np.r_[np.nan, np.diff(lat)] * M_PER_DEG
    step = np.hypot(dx, dy)
    brg = (np.degrees(np.arctan2(dx, dy)) + 360) % 360
    hd = np.abs((brg - g["Heading (deg)"].to_numpy(float) + 180) % 360 - 180)
    hd[step < 0.5] = np.nan
    sg = np.abs(step - g["Velocity (m/s)"].to_numpy(float))
    brg2 = brg.copy()
    brg2[step < 0.5] = np.nan
    cc = np.abs((np.r_[np.nan, np.diff(brg2)] + 180) % 360 - 180)
    out = pd.DataFrame({"pos_step_m": step, "speed_gap": sg, "heading_gap": hd, "course_change": cc}, index=g.index)
    for c in ("pos_step_m", "speed_gap", "heading_gap", "course_change"):
        out[c + "5"] = out[c].rolling(5, min_periods=1).mean()
    return out


def load_sessions():
    """DataFrame of every kept session (lock order): original columns, derived columns, session id, file, label y."""
    files = {i: pd.read_csv(AV / f"AV-GPS-Dataset-{i}.csv", low_memory=False) for i in (1, 2, 3)}
    parts = []
    for s in LOCK["sessions"]:
        g = files[s["file"]].iloc[s["start"]:s["end"]].copy()
        for c in g.columns:
            if c not in ("Run Time", "Clock Time", "Clock Date", "GPS MGRS"):
                g[c] = pd.to_numeric(g[c], errors="coerce")
        g = pd.concat([g, derived(g)], axis=1)
        g["session"], g["file"], g["y"], g["k"] = s["session"], s["file"], int(s["label"]), np.arange(len(g))
        parts.append(g.reset_index(drop=True))
    return pd.concat(parts, ignore_index=True)


def feature_sets(df):
    base = [c for c in df.columns if c not in EXCLUDE + ["session", "file", "y", "k", "pos_step_m", "speed_gap", "heading_gap", "pos_step_m5", "speed_gap5", "heading_gap5", "course_change", "course_change5"]]
    return {"F_full": base, "F_nosat": [c for c in base if c not in SAT], "F_kin": KIN, "F_kin_noVS": KIN_NOVS, "F_pos": POS}


def rows(df, ids):
    return df[df.session.isin(ids)]


def fit_xgb(Xtr, ytr, Xva=None, yva=None, depth=5, seed=42, n_rounds=None, weights=None):
    """XGBoost binary; early stopping on validation logloss (patience 20, max 300) when a validation set is given, else n_rounds fixed."""
    prm = dict(n_estimators=n_rounds or 300, learning_rate=0.1, max_depth=depth, tree_method="hist", random_state=seed, n_jobs=4,
               objective="binary:logistic", eval_metric="logloss", subsample=1.0, colsample_bytree=1.0)
    if Xva is not None:
        m = xgb.XGBClassifier(early_stopping_rounds=20, **prm)
        m.fit(Xtr, ytr, eval_set=[(Xva, yva)], sample_weight=weights, verbose=False)
    else:
        m = xgb.XGBClassifier(**prm)
        m.fit(Xtr, ytr, sample_weight=weights, verbose=False)
    return m


def n_trees(m):
    return int(getattr(m, "best_iteration", None) + 1) if getattr(m, "best_iteration", None) is not None else int(m.n_estimators)


def best_f1_threshold(y, s):
    """threshold maximising F1 (attack = 1) over the distinct scores (candidates: up to 2000 quantiles); returns (thr, f1)."""
    y = np.asarray(y)
    cand = np.unique(np.quantile(s, np.linspace(0, 1, 2001)))
    best = (0.5, -1.0)
    for t in cand:
        f = f1_at(y, s >= t)["f1"]
        if f > best[1] + 1e-12:
            best = (float(t), f)
    return best


def f1_at(y, pred):
    y, pred = np.asarray(y).astype(bool), np.asarray(pred).astype(bool)
    tp, fp, fn, tn = (y & pred).sum(), (~y & pred).sum(), (y & ~pred).sum(), (~y & ~pred).sum()
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-12)
    f1n = 2 * tn / max(2 * tn + fn + fp, 1)           # F1 of the normal class
    return {"f1": float(f1), "precision": float(prec), "recall": float(rec), "fpr": float(fp / max(fp + tn, 1)), "accuracy": float((tp + tn) / len(y)),
            "macro_f1": float((f1 + f1n) / 2), "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}


def safe_auc(y, s):
    y = np.asarray(y)
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else float("nan")


def cluster_boot(y, s, pred, groups, n=2000, seed=42):
    """session-cluster bootstrap 95% CI of f1 / recall / fpr / auc / macro_f1 (percentile)."""
    y, s, pred, groups = map(np.asarray, (y, s, pred, groups))
    ug = np.unique(groups)
    idx = {g: np.flatnonzero(groups == g) for g in ug}
    rng = np.random.default_rng(seed)
    acc = {k: [] for k in ("f1", "recall", "fpr", "auc", "macro_f1", "precision")}
    for _ in range(n):
        pick = rng.choice(ug, len(ug))
        ii = np.concatenate([idx[g] for g in pick])
        if not (0 < y[ii].sum() < len(ii)):
            continue
        m = f1_at(y[ii], pred[ii])
        for k in ("f1", "recall", "fpr", "macro_f1", "precision"):
            acc[k].append(m[k])
        acc["auc"].append(safe_auc(y[ii], s[ii]))
    return {k: [float(np.nanquantile(v, 0.025)), float(np.nanquantile(v, 0.975))] for k, v in acc.items() if v} | {"n_valid_resamples": len(acc["f1"])}


def gain_share(m, cols):
    imp = m.get_booster().get_score(importance_type="total_gain")
    tot = sum(imp.values()) or 1.0
    out = {}
    for k, v in imp.items():
        name = cols[int(k[1:])] if k.startswith("f") and k[1:].isdigit() else k
        out[name] = v / tot
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))
