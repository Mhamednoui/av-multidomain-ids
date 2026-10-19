"""Evaluation metrics shared by every v3 module.

Copied from codes_v2/common/metrics.py (classification_summary, binary_summary, pct), plus the v3
additions: tie-safe budget threshold, detection at a false-alarm budget, AUC, detection delay.
Inputs: numpy score / label arrays (1 = attack). Outputs: floats / dicts.
Reference: ARCHITECTURE.md section 4 (threshold rule).
"""
import numpy as np
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             precision_recall_fscore_support, roc_auc_score)


def classification_summary(y_true, y_pred, classes) -> dict:
    """Accuracy, weighted / macro F1, per-class precision-recall-F1 and the confusion matrix."""
    labels = list(range(len(classes)))
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        "n": int(len(y_true)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", labels=labels, zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", labels=labels, zero_division=0)),
        "per_class": {c: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
                      for i, c in enumerate(classes)},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "classes": list(classes),
    }


def binary_summary(y_true, y_pred) -> dict:
    """Attack-vs-normal metrics (1 = attack)."""
    y_true = np.asarray(y_true).astype(bool)
    y_pred = np.asarray(y_pred).astype(bool)
    tp = int((y_true & y_pred).sum()); fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum()); tn = int((~y_true & ~y_pred).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "accuracy": (tp + tn) / max(len(y_true), 1),
            "precision": prec, "recall": rec,
            "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "fpr": fp / (fp + tn) if fp + tn else 0.0}


def pct(x: float, d: int = 2) -> str:
    return f"{100 * x:.{d}f}%"


def budget_threshold(normal_scores, budget: float) -> float:
    """Smallest threshold t (alarm = score >= t) whose false-alarm rate on `normal_scores` is <= budget.

    Tie-safe: t is the next float above the k-th largest score, k = floor(budget * n), so tied
    scores can never push the rate over the budget (v2 bug: ties at the quantile exceeded it).
    """
    s = np.sort(np.asarray(normal_scores, dtype=float))[::-1]
    if len(s) == 0:
        raise ValueError("no normal scores")
    k = int(np.floor(budget * len(s) + 1e-9))
    if k >= len(s):
        return float(-np.inf)
    return float(np.nextafter(s[k], np.inf))


def false_alarm_rate(scores, threshold) -> float:
    s = np.asarray(scores, dtype=float)
    return float((s >= threshold).mean()) if len(s) else float("nan")


def auc(y, scores) -> float:
    y = np.asarray(y).astype(int)
    if y.min() == y.max():
        return float("nan")
    return float(roc_auc_score(y, scores))


def detection_at_budget(val_normal_scores, scores, y, attack_type=None, budget: float = 0.01) -> dict:
    """Threshold from validation normal scores; detection rate overall and per attack type on `scores`."""
    thr = budget_threshold(val_normal_scores, budget)
    scores = np.asarray(scores, dtype=float); y = np.asarray(y).astype(bool)
    alarm = scores >= thr
    out = {"threshold": thr, "budget": budget,
           "false_alarm_rate": float(alarm[~y].mean()) if (~y).any() else float("nan"),
           "detection": float(alarm[y].mean()) if y.any() else float("nan"),
           "detection_by_attack": {}}
    if attack_type is not None:
        at = np.asarray(attack_type)
        for a in sorted(set(at[y])):
            m = y & (at == a)
            out["detection_by_attack"][str(a)] = float(alarm[m].mean())
    return out


def detection_delay(t, y, alarm) -> dict:
    """Per attack segment (consecutive y == 1 in time order) of ONE stream: seconds from onset to
    first alarm (None if never). Combine several streams with `merge_delays`."""
    t = np.asarray(t, dtype=float); y = np.asarray(y).astype(bool); alarm = np.asarray(alarm).astype(bool)
    order = np.argsort(t, kind="stable")
    t, y, alarm = t[order], y[order], alarm[order]
    delays, n_seg, i = [], 0, 0
    while i < len(y):
        if y[i]:
            j = i
            while j < len(y) and y[j]:
                j += 1
            n_seg += 1
            hit = np.flatnonzero(alarm[i:j])
            delays.append(float(t[i + hit[0]] - t[i]) if len(hit) else None)
            i = j
        else:
            i += 1
    return {"delays": delays, "n_segments": n_seg}


def merge_delays(parts) -> dict:
    d = [x for p in parts for x in p["delays"]]
    n = sum(p["n_segments"] for p in parts)
    got = [x for x in d if x is not None]
    return {"n_segments": n, "detected_fraction": (len(got) / n) if n else float("nan"),
            "median_delay_s": float(np.median(got)) if got else float("nan"),
            "mean_delay_s": float(np.mean(got)) if got else float("nan")}
