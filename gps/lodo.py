"""WP1 S4: leave-one-drive-out (LODO) threshold calibration (generic helper, proposed for common/).

Policy (supervisor, 2026-10-19): a layer's threshold is the tie-safe budget threshold of the POOLED clean scores of all
development drives, not of 3 validation drives (S3: a threshold from 3 drives gave 2.6% FA on test at a 1% budget).
For layers whose scores depend on a fitted model, the pooled scores must be out-of-fold (fit on the other drives);
for layers with only frozen parameters (CUSUM, EKF, B2) the out-of-fold scores are the plain scores.

Inputs: clean scores (n,), group ids (n,) = drive. Outputs: dict with the pooled threshold and, per held-out drive, the
threshold computed from the OTHER drives and the false-alarm rate it gives on the held-out drive (an honest transfer estimate:
the pooled mean of these is what a new drive would see).
Reference: RULES.md section 5; ARCHITECTURE.md section 4 (tie-safe threshold).
"""
import numpy as np

from common.metrics import budget_threshold


def lodo_report(scores, groups, budget=0.01):
    s, g = np.asarray(scores, float), np.asarray(groups)
    out = {"budget": budget, "n": int(len(s)), "pooled_threshold": budget_threshold(s, budget), "per_drive": {}}
    fp = tot = 0
    for d in sorted(set(g)):
        m = g == d
        if m.all():
            continue
        thr = budget_threshold(s[~m], budget)
        a = int((s[m] >= thr).sum())
        out["per_drive"][str(d)] = {"threshold_from_others": thr, "n": int(m.sum()), "false_alarms": a, "fa": a / int(m.sum())}
        fp += a; tot += int(m.sum())
    out["heldout_fa_pooled"] = fp / tot if tot else float("nan")
    out["heldout_fa_worst_drive"] = max((v["fa"] for v in out["per_drive"].values()), default=float("nan"))
    out["in_sample_fa"] = float((s >= out["pooled_threshold"]).mean())
    return out
