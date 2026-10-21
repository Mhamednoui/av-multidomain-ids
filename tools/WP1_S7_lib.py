"""WP1 S7 shared helpers: feature frames (stack residuals + C2 features), nested LODO for L3, nested LODO for L4, the default stack layers.
Used by tools/WP1_S7_dev.py (train+val drives only), tools/WP1_S7_test.py (one test pass), tools/WP1_S7_tables.py.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import WP1_S4_lib as L
import WP1_S4_test as T4
from common.metrics import budget_threshold
from gps import ekf, l1, learned
from gps import lidar_odom as LO
from gps.lodo import lodo_report

BUDGET = 0.01
OUT = L.OUT
CACHE = OUT / "cache"
CACHE.mkdir(exist_ok=True)
ATT = L.ATT
V2_ATTACKS = ("drift", "accel_drift", "jump", "freeze")
L2D_NAMES = ["lid_z_1", "lid_z_3", "lid_z_10", "lid_resid_1", "lid_resid_3", "lid_course"]
VAL_DRIVES = ["0011", "0035", "0027"]


def stack_layers():
    """Default stack: B2 + L1 (5 kinematic + e_velpos) + L2a ekf_nis + L2b (cusum_ekf, cusum_dr from S4_dev) + L2d (6 instantaneous). Returns layer dict."""
    sel = json.loads((OUT / "S4_dev.json").read_text())["selection"]
    lay_e, lay_d, _, _, _, _ = T4.make_layers(sel)
    rules = l1.make_rules(l1.COVERAGE["kitti"]["evaluated"])
    b2 = L.S1.B2Layer()
    ek = ekf.EKFLayer(L.ekf_cfg(), "gps.ekf_nis")
    l2d = [LO.LidarLayer(c) for c in L2D_NAMES]
    base = rules + [b2, ek, lay_e, lay_d]
    return {"rules": rules, "b2": b2, "ekf": ek, "cusum_ekf": lay_e, "cusum_dr": lay_d, "l2d": l2d, "base": base, "stack": base + l2d}


def feature_frame(df, cache_name=None):
    """Stream rows `df` (whole runs) -> df + LiDAR columns + residual columns of L3 (r3_*) + C2 features (c2_*). Cached by name."""
    p = CACHE / f"s7_feat_{cache_name}.pkl" if cache_name else None
    if p is not None and p.exists():
        return pd.read_pickle(p)
    s = stack_layers()
    out = df.join(LO.stream_features(df))
    out["r3_nis"] = s["ekf"].raw_scores(out)
    out["r3_cusum_ekf"] = s["cusum_ekf"].raw_scores(out)
    out["r3_cusum_dr"] = s["cusum_dr"].raw_scores(out)
    c2 = learned.c2_features(out)
    for c in c2.columns:
        out["c2_" + c] = c2[c]
    if p is not None:
        out.to_pickle(p)
    return out


def c2_frame(df):
    return df[["c2_" + c for c in learned.C2_ALL]].rename(columns=lambda c: c[3:])


def j_of(df, flag):
    return L.j_criterion(L.summarize(df, flag))


# ----------------------------------------------------------------------------------------------------------------------------
# L3: leave-one-drive-out and leave-two-out scores (strictly nested selection)
# ----------------------------------------------------------------------------------------------------------------------------
def l3_scores(dev, candidates=None, log=print):
    """For every candidate: OOF[c][d] = scores of the rows of drive d from a model fit on the label-0 rows of all other drives;
    PAIR[c][(d, e)] = scores of drive e's rows from a model fit without d and e (inner loop of the nested selection)."""
    drives = sorted(dev["drive"].unique())
    drive = dev["drive"].to_numpy()
    normal = (dev["label"] == 0).to_numpy()
    cands = candidates or learned.L3_CANDIDATES
    oof, pair = {}, {}
    for c, (setname, kind) in cands.items():
        cols = learned.res_cols(setname)
        oof[c] = np.zeros(len(dev))
        pair[c] = {}
        for i, d in enumerate(drives):
            m = learned.ResidualNormalModel(kind, cols).fit(dev[normal & (drive != d)])
            oof[c][drive == d] = m.score(dev[drive == d])
        for i, d in enumerate(drives):
            for e in drives[i + 1:]:
                m = learned.ResidualNormalModel(kind, cols).fit(dev[normal & (drive != d) & (drive != e)])
                pair[c][(d, e)] = (m.score(dev[drive == d]), m.score(dev[drive == e]))
        log(f"  L3 scores done: {c}", flush=True)
    return oof, pair, drives


def l3_nested(dev, pair, oof, drives, cands):
    """Outer fold d: inner scores of every other drive e come from the model fit without d and e; threshold = pooled 1% of those clean scores;
    J on the other drives picks the candidate; drive d is then scored by the OOF model of the pick (fit without d) with that threshold."""
    drive = dev["drive"].to_numpy()
    normal = (dev["label"] == 0).to_numpy()
    flag = np.zeros(len(dev), bool)
    choices = {}
    for d in drives:
        m = drive == d
        js, thr = {}, {}
        for c in cands:
            s = np.zeros(len(dev))
            for e in drives:
                if e == d:
                    continue
                key = (d, e) if (d, e) in pair[c] else (e, d)
                sd, se = pair[c][key]
                s[drive == e] = se if key == (d, e) else sd
            thr[c] = budget_threshold(s[normal & ~m], BUDGET)
            js[c] = j_of(dev[~m], s[~m] >= thr[c])
        c = max(js, key=js.get)
        flag[m] = oof[c][m] >= thr[c]
        choices[d] = {"choice": c, "J_on_other_drives": js[c], "threshold": thr[c],
                      "heldout_fa": float(flag[m & normal].mean()) if (m & normal).any() else None}
    sm = L.summarize(dev, flag)
    return {"choices": choices, "heldout_fa_pooled": float(flag[normal].mean()), "summary": sm, "J": L.j_criterion(sm),
            "choice_counts": {c: sum(1 for v in choices.values() if v["choice"] == c) for c in cands}}


# ----------------------------------------------------------------------------------------------------------------------------
# L4: nested LODO for the supervised model
# ----------------------------------------------------------------------------------------------------------------------------
def l4_rows(df, attacks):
    return df["attack"].isin(("none",) + tuple(attacks)).to_numpy()


def l4_fit(F, y, tr, va, features, attacks_mask, n_iter=15, shuffle_seed=None):
    """Fit a C2Model on rows tr (train) with selection on rows va; both restricted to the attack types of attacks_mask."""
    tr, va = tr & attacks_mask, va & attacks_mask
    ytr, yva = y[tr].copy(), y[va].copy()
    if shuffle_seed is not None:
        rng = np.random.default_rng(shuffle_seed)
        ytr, yva = rng.permutation(ytr), rng.permutation(yva)
    return learned.C2Model(features, n_iter=n_iter).fit(F[tr], ytr, F[va], yva)


def l4_oof(dev, F, features, attacks, n_iter=15, log=print):
    """Outer fold = one held-out drive. Validation (early stopping + random search) = the original val drives other than the held-out one;
    training = the remaining drives. Returns OOF scores aligned to dev, per-fold info and importances."""
    drive = dev["drive"].to_numpy()
    y = dev["label"].to_numpy()
    mask = l4_rows(dev, attacks)
    oof = np.zeros(len(dev))
    info, imps = {}, []
    for d in sorted(set(drive)):
        va_dr = [v for v in VAL_DRIVES if v != d]
        va = np.isin(drive, va_dr)
        tr = (drive != d) & ~va
        mdl = l4_fit(F, y, tr, va, features, mask, n_iter)
        oof[drive == d] = mdl.score(F[drive == d])
        info[d] = {"best": mdl.info["best"], "val_f1": mdl.info["val_f1_macro"], "n_train_rows": int((tr & mask).sum())}
        imps.append(mdl.importance())
        log(f"  L4 fold {d} done (val F1 {mdl.info['val_f1_macro']:.3f}, trees {mdl.info['best']['n_trees']})", flush=True)
    imp = {k: float(np.mean([i[k] for i in imps])) for k in imps[0]}
    return oof, info, imp


def evaluate_scores(dev, score, name):
    """LODO pooled 1% threshold, held-out FA per drive, run-level detections, J (as D4.evaluate)."""
    import WP1_S4_dev as D4
    return D4.evaluate(dev, score, name)


def per_drive_fa(df, flag):
    n = (df["label"] == 0).to_numpy()
    d = df["drive"].to_numpy()
    return {k: float(flag[n & (d == k)].mean()) for k in sorted(set(d[n]))}
