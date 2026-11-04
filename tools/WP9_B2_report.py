"""WP9 B2: test metrics with cluster-bootstrap CIs (clusters = 10-minute test blocks of one day; 1000 resamples, seed 7).

Metrics (definitions fixed in notes/WP9_B2.md): macro-F1 over eligible classes (>= 20 flows in train and test; the rest listed), FPR (benign test flows predicted
as any attack, argmax), per-class recall / precision / F1, binary AUC (score 1 - P(benign)), detection at a threshold set on VALIDATION benign flows
(1% false alarms), per-class AUC vs benign. Test flows of classes absent from train are dropped from the metrics and counted.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

MIN_N = 20
NBOOT = 1000


def _conf(y, pred, g, ncls, ng, w):
    k = (g.astype(np.int64) * ncls + y) * ncls + pred
    return np.bincount(k, weights=w, minlength=ng * ncls * ncls).reshape(ng, ncls, ncls)


def _macro(C, el):
    tp = np.diag(C).astype(float)
    fp = C.sum(0) - tp
    fn = C.sum(1) - tp
    f1 = np.where(2 * tp + fp + fn > 0, 2 * tp / np.maximum(2 * tp + fp + fn, 1), 0.0)
    return f1, float(np.mean(f1[el]))


def _ci(v):
    v = np.asarray(v, float)
    v = v[~np.isnan(v)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [None, None]


def _wquantile(v, w, q):
    """Weighted quantile (smallest value whose cumulative weight share >= q); equals np.quantile (higher interpolation aside) when w == 1."""
    if np.all(w == w[0]):
        return float(np.quantile(v, q))
    o = np.argsort(v)
    cw = np.cumsum(w[o])
    return float(v[o][min(np.searchsorted(cw, q * cw[-1]), len(v) - 1)])


def _auc_hist(hp, hn):
    """AUC from per-bin positive / negative counts (ties = half)."""
    P, N = hp.sum(), hn.sum()
    if P == 0 or N == 0:
        return np.nan
    below = np.cumsum(hn) - hn
    return float((hp * (below + 0.5 * hn)).sum() / (P * N))


def report(classes, fam_train, fam_val, pv, fam_test, pt, boot_test, w_val=None, w_test=None):
    ncls = len(classes)
    cmap = {c: i for i, c in enumerate(classes)}
    w_val = np.ones(len(fam_val)) if w_val is None else np.asarray(w_val, float)
    w_test = np.ones(len(fam_test)) if w_test is None else np.asarray(w_test, float)
    yt = np.array([cmap.get(c, -1) for c in fam_test])
    unseen = pd.Series(fam_test[yt < 0]).value_counts().to_dict()
    ok = yt >= 0
    yt, pt, bt, wt = yt[ok], pt[ok].astype(np.float32), boot_test[ok], w_test[ok]
    yv = np.array([cmap.get(c, -1) for c in fam_val])
    okv = yv >= 0
    yv, pv, wv = yv[okv], pv[okv].astype(np.float32), w_val[okv]
    # eligible classes
    ce = pd.Series(np.array(classes)[yt]).value_counts()
    ct = pd.Series(fam_train).value_counts()
    el = [i for i, c in enumerate(classes) if ce.get(c, 0) >= MIN_N and ct.get(c, 0) >= MIN_N]
    not_el = {c: {"test": int(ce.get(c, 0)), "train": int(ct.get(c, 0))} for i, c in enumerate(classes) if i not in el}
    pred = pt.argmax(1)
    gu, g = np.unique(bt, return_inverse=True)
    ng = len(gu)
    Cg = _conf(yt, pred, g, ncls, ng, wt)
    C = Cg.sum(0)
    support_raw = np.bincount(yt, minlength=ncls)
    f1, mf1 = _macro(C, el)
    tp = np.diag(C).astype(float)
    rec = tp / np.maximum(C.sum(1), 1)
    prec = tp / np.maximum(C.sum(0), 1)
    ben = yt == 0
    fpr = float(1 - C[0, 0] / C[0].sum())
    s = 1.0 - pt[:, 0]
    auc = float(roc_auc_score(~ben, s, sample_weight=wt))
    # threshold on validation benign flows (1% false alarms)
    sv = 1.0 - pv[:, 0]
    thr = _wquantile(sv[yv == 0], wv[yv == 0], 0.99)
    hit = s > thr
    det_all = float((wt * hit)[~ben].sum() / wt[~ben].sum())
    fpr_thr = float((wt * hit)[ben].sum() / wt[ben].sum())
    det_cls = {classes[i]: float((wt * hit)[yt == i].sum() / wt[yt == i].sum()) for i in range(1, ncls) if (yt == i).sum() > 0}
    auc_cls = {}
    for i in range(1, ncls):
        m = (yt == i) | ben
        if (yt == i).sum() >= MIN_N:
            auc_cls[classes[i]] = float(roc_auc_score(yt[m] == i, pt[m, i], sample_weight=wt[m]))
    # per-group counts for the bootstrap
    edges = np.unique(np.quantile(s, np.linspace(0, 1, 4001)))
    bi = np.clip(np.searchsorted(edges, s, side="left"), 0, len(edges) - 1)
    nb = len(edges)
    hp = np.bincount(g[~ben].astype(np.int64) * nb + bi[~ben], weights=wt[~ben], minlength=ng * nb).reshape(ng, nb)
    hn = np.bincount(g[ben].astype(np.int64) * nb + bi[ben], weights=wt[ben], minlength=ng * nb).reshape(ng, nb)
    n_ben_g = np.bincount(g[ben], weights=wt[ben], minlength=ng)
    n_att_g = np.bincount(g[~ben], weights=wt[~ben], minlength=ng)
    hit_ben_g = np.bincount(g[ben & hit], weights=wt[ben & hit], minlength=ng)
    hit_att_g = np.bincount(g[~ben & hit], weights=wt[~ben & hit], minlength=ng)
    rng = np.random.default_rng(7)
    B = {"macro_f1": [], "fpr": [], "auc": [], "det": [], "fpr_thr": []}
    Bc = {classes[i]: [] for i in range(1, ncls)}
    for _ in range(NBOOT):
        w = np.bincount(rng.integers(0, ng, ng), minlength=ng).astype(float)
        Cb = np.tensordot(w, Cg, axes=(0, 0))
        _, m = _macro(Cb, el)
        B["macro_f1"].append(m)
        nbn = (w * n_ben_g).sum()
        B["fpr"].append(1 - Cb[0, 0] / nbn if nbn > 0 else np.nan)
        B["auc"].append(_auc_hist(w @ hp, w @ hn))
        B["det"].append((w * hit_att_g).sum() / max((w * n_att_g).sum(), 1))
        B["fpr_thr"].append((w * hit_ben_g).sum() / nbn if nbn > 0 else np.nan)
        for i in range(1, ncls):
            r = Cb[i].sum()
            Bc[classes[i]].append(Cb[i, i] / r if r > 0 else np.nan)
    per_class = {classes[i]: {"support": int(support_raw[i]), "weighted_support": float(C[i].sum()), "recall": float(rec[i]), "recall_ci": _ci(Bc[classes[i]]) if i > 0 else None,
                              "precision": float(prec[i]), "f1": float(f1[i]), "eligible": i in el, "det_at_1pct_fa": det_cls.get(classes[i]), "auc_vs_benign": auc_cls.get(classes[i])}
                 for i in range(ncls)}
    sens = float(np.mean(f1[[i for i in range(ncls) if C[i].sum() > 0]]))
    return {"macro_f1": mf1, "macro_f1_ci": _ci(B["macro_f1"]), "macro_f1_all_present_classes": sens, "eligible": [classes[i] for i in el], "not_eligible": not_el,
            "unseen_test_classes_dropped": {k: int(v) for k, v in unseen.items()},
            "fpr": fpr, "fpr_ci": _ci(B["fpr"]), "auc_binary": auc, "auc_binary_ci": _ci(B["auc"]),
            "macro_auc_vs_benign": float(np.mean(list(auc_cls.values()))) if auc_cls else None,
            "threshold_val_1pct": thr, "detection_at_val_1pct": det_all, "detection_at_val_1pct_ci": _ci(B["det"]), "fpr_at_val_1pct": fpr_thr, "fpr_at_val_1pct_ci": _ci(B["fpr_thr"]),
            "accuracy": float(tp.sum() / C.sum()), "n_boot_groups": int(ng), "per_class": per_class}
