"""WP3 S7 L4: the v2 descriptor model retrained inside the v3 harness on the PHYSICALLY CONSISTENT attack set only.

Purpose: v2 trained an XGBoost on the 211-dim sector descriptor (+ 218 scan-to-scan features, lidar.features, copied in S1) with a
box-cloud phantom class that is denser than any real object. S7 retrains it on calibrated single-return phantoms (replace / budget,
near / far; lidar.phantom), PointDrop and IntensitySpoof; the multi-return add and the box cloud are NEVER training rows.
Inputs: KITTI scans (lidar.data), S2 ring table and calibration, clean descriptor rows of the S1 cache (train4 'Normal' rows).
Outputs: descriptor row tables (meta + 429 columns, cached per drive), XGBoost models, scores 1 - P(Normal), leakage controls
(shuffled-label null, feature importance, leave-one-attack-type-out).
Row layout: lidar.features.feature_names_temporal() (211 + 211 + 7). Row seeds: training [97, drive], evaluation attacks = the S4
seeds [83, drive, scan] (identical attacked scans as S4 / S6, so layers can be compared scan by scan), episodes [89, drive].
References: Chen & Guestrin, XGBoost (KDD 2016); Cao et al. CCS 2019 and Sun et al. USENIX Security 2020 (what a LiDAR spoofer can do).
"""
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import roc_auc_score

from common.config import RESULTS, SEED
from lidar import calibration as C
from lidar import geometry as G
from lidar import phantom as P
from lidar import s4_build as B
from lidar.data import CACHE, group_id, load, scan_files
from lidar.features import apply_attack, attack_params, describe, feature_names_temporal, temporal
from lidar.raycast import eval_params
from lidar.train_xgb import SPACE, class_weights

ROOT = CACHE / "S7"
S2 = RESULTS / "WP3" / "S2"
PHYS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof"]
CLASSES = ["Normal", "PointDrop", "IntensitySpoof", "Phantom"]
CLASS_OF = {"ph_replace_near": 3, "ph_replace_far": 3, "ph_budget_near": 3, "ph_budget_far": 3, "PointDrop": 1, "IntensitySpoof": 2}
NAMES = feature_names_temporal()
TRAIN_STRIDE = 2
EVAL_STRIDE = 3


def tools():
    return G.RingTable.load(S2 / "ring_table.json"), C.load_calib(S2 / "calibration_beta.npz")


def attacked(name, pts, prm, rng, table, calib, rays=None):
    """One physically consistent attack on a scan with parameters prm (phantom: eval_params dict; PointDrop / IntensitySpoof:
    attack_params dict). Returns (attacked scan, parameters actually used)."""
    if name.startswith("ph_"):
        mode = name.split("_")[1]
        rays = P.prepare(pts, table) if rays is None else rays
        att, n, q, idx = P.phantom(pts, rays, prm, rng, mode, calib)
        return att, q
    return apply_attack(name, pts, prm, rng), prm


def train_rows(d, table=None, calib=None, stride=TRAIN_STRIDE):
    """Training / validation attack rows of drive d (every `stride`-th scan from 1): one draw per physical attack type, onset or
    sustained with probability 1/2 (as in v2). Returns (meta DataFrame, X float32)."""
    if table is None:
        table, calib = tools()
    rng = np.random.default_rng([97, int(d)])
    files = scan_files(d)
    meta, X = [], []
    for i in range(1, len(files), stride):
        pts, prev_pts = load(files[i]), load(files[i - 1])
        prev_clean = describe(prev_pts)
        rays = P.prepare(pts, table)
        for name in PHYS:
            if name.startswith("ph_"):
                prm = eval_params(rng, name.split("_")[2])
            else:
                prm = attack_params(name, rng)
            att, q = attacked(name, pts, prm, rng, table, calib, rays)
            cur = describe(att)
            if rng.random() < 0.5:
                mode, prev = "onset", prev_clean
            else:
                mode = "sustained"
                patt, _ = attacked(name, prev_pts, q, rng, table, calib)
                prev = describe(patt)
            X.append(np.r_[cur, temporal(cur, prev)])
            meta.append((d, group_id(d, files[i]), i, name, CLASS_OF[name], mode))
    return pd.DataFrame(meta, columns=["drive", "scan", "idx", "type", "cls", "mode"]), np.array(X, np.float32)


def eval_rows(d, table=None, calib=None, stride=EVAL_STRIDE):
    """S4 evaluation attack set of drive d (scans i % stride == 1, seeds [83, d, i], all nine attacks incl. the comparison rows),
    onset (previous scan clean). meta has n_inj (injected returns, must equal the S4 table)."""
    if table is None:
        table, calib = tools()
    files = scan_files(d)
    meta, X = [], []
    for i in range(1, len(files), stride):
        pts = load(files[i])
        prev_clean = describe(load(files[i - 1]))
        rng = np.random.default_rng([83, int(d), i])
        g = group_id(d, files[i])
        for name, att, idx in B.attack_cases(pts, rng, table, calib):
            cur = describe(att)
            X.append(np.r_[cur, temporal(cur, prev_clean)])
            meta.append((d, f"{g}|{name}", g, i, name, 0 if idx is None else len(idx)))
    return pd.DataFrame(meta, columns=["drive", "scan", "base", "idx", "attack", "n_inj"]), np.array(X, np.float32)


def episode_rows(d, table=None, calib=None, n_ep=3):
    """S4 sensor-fixed persistent phantom episodes of drive d (same draws as lidar.s4_build.drive_episodes): descriptor of every step;
    previous scan = clean scan before the first step, then the previous attacked scan."""
    if table is None:
        table, calib = tools()
    files = scan_files(d)
    rng = np.random.default_rng([89, int(d)])
    meta, X = [], []
    for mode, band in B.EP_KINDS:
        for j in range(n_ep):
            p = eval_params(rng, band)
            s0 = int(rng.integers(1, max(2, len(files) - B.EP_LEN)))
            kind = f"ep_{mode}_{band}"
            prev = describe(load(files[s0 - 1]))
            for k in range(s0, min(len(files), s0 + B.EP_LEN)):
                pts = load(files[k])
                att, n, q, idx = P.phantom(pts, P.prepare(pts, table), p, rng, mode, calib)
                cur = describe(att)
                X.append(np.r_[cur, temporal(cur, prev)])
                prev = cur
                meta.append((d, f"{group_id(d, files[k])}|{kind}|{j}", k, kind, j, k - s0 + 1, len(idx)))
    return pd.DataFrame(meta, columns=["drive", "scan", "idx", "attack", "ep", "step", "n_inj"]), np.array(X, np.float32)


def normal_rows(drives):
    """Clean descriptor rows (S1 cache, train4 'Normal' rows) of the given drives: (meta with idx, X). idx = scan index in the drive."""
    metas, Xs = [], []
    for d in drives:
        z = pd.read_pickle(CACHE / "train4" / f"{d}.pkl")
        m = z["meta"]
        sel = (m.cls == "Normal").to_numpy()
        mm = m[sel][["drive", "scan"]].reset_index(drop=True)
        mm["idx"] = np.arange(1, len(mm) + 1)
        metas.append(mm)
        Xs.append(np.asarray(z["X"])[sel])
    return pd.concat(metas, ignore_index=True), np.vstack(Xs).astype(np.float32)


def v2_rows(drives):
    """v2 training rows (train4 cache: Normal, PointDrop, IntensitySpoof, box cloud) as (meta, X, y) for the comparison model L4_v2."""
    cls = {"Normal": 0, "PointDrop": 1, "IntensitySpoof": 2, "GhostCluster": 3}
    metas, Xs = [], []
    for d in drives:
        z = pd.read_pickle(CACHE / "train4" / f"{d}.pkl")
        metas.append(z["meta"])
        Xs.append(np.asarray(z["X"]))
    m = pd.concat(metas, ignore_index=True)
    return m, np.vstack(Xs).astype(np.float32), m.cls.map(cls).to_numpy()


def fit_xgb(X, y, params, n_trees, seed=SEED, n_jobs=4, Xva=None, yva=None, weight_power=0.5):
    """XGBoost multi-class (softprob) with v2-style class weights. With Xva given: early stopping on validation logloss (50 rounds)."""
    y = np.unique(y, return_inverse=True)[1]          # contiguous labels (a held-out class may be missing); class 0 = Normal stays 0
    if yva is not None:
        yva = np.unique(yva, return_inverse=True)[1]
    k = int(y.max()) + 1
    kw = dict(n_estimators=n_trees, tree_method="hist", device="cpu", n_jobs=n_jobs, random_state=seed, objective="multi:softprob",
              num_class=k, eval_metric="mlogloss", **params)
    if Xva is not None:
        m = xgb.XGBClassifier(early_stopping_rounds=50, **kw)
        m.fit(X, y, sample_weight=class_weights(y, weight_power), eval_set=[(Xva, yva)], verbose=False)
    else:
        m = xgb.XGBClassifier(**kw)
        m.fit(X, y, sample_weight=class_weights(y, weight_power), verbose=False)
    return m


def attack_score(model, X):
    """1 - P(Normal)."""
    return 1.0 - model.predict_proba(X)[:, 0]


def random_params(rng):
    return {k: v[rng.integers(len(v))] for k, v in SPACE.items()}


def auc(y, s):
    return float(roc_auc_score(np.asarray(y), np.asarray(s)))


def null_aucs(X, y, params, n_trees, Xe, ye, seeds=(11, 12, 13, 14, 15)):
    """Shuffled-label null control: all training labels permuted, same model; AUC (attack vs normal) on the evaluation rows."""
    out = []
    for s in seeds:
        yp = np.random.default_rng(s).permutation(y)
        out.append(auc(ye, attack_score(fit_xgb(X, yp, params, n_trees), Xe)))
    return out


def importance_table(model, names=NAMES):
    """Gain importance per feature (normalised to 1), sorted."""
    g = model.get_booster().get_score(importance_type="total_gain")
    s = pd.Series({names[int(k[1:])]: v for k, v in g.items()}, dtype=float)
    return (s / s.sum()).sort_values(ascending=False)


def feature_group(name):
    """Physical group of a descriptor column (temporal columns 'd_*' are scan-to-scan differences of the same group)."""
    n = name[2:] if name.startswith("d_") else name
    pre = "temporal " if name.startswith("d_") or name.startswith("dt_") else ""
    if n.startswith("elev_") and n[5:].isdigit():
        g = "elevation histogram"
    elif n.startswith("dist_"):
        g = "range histogram"
    elif n.startswith("sect_cnt_"):
        g = "sector counts"
    elif n.startswith("sect_imean_"):
        g = "sector intensity"
    elif n.startswith("sect_hifrac_"):
        g = "sector bright fraction"
    elif n.startswith("double_return") or n.startswith("dr_patch"):
        g = "double-return (multi-return) cells"
    elif n.startswith("sect_") or n in ("obst_peak_ratio", "n_sparse_sect") or n.startswith("dt_cnt") or n.startswith("dt_imean") or n.startswith("dt_hifrac"):
        g = "sector summaries"
    elif n.startswith("dt_double"):
        g = "double-return (multi-return) cells"
    else:
        g = "global statistics"
    return pre + g
