"""WP5 S6: evaluation helpers for the V2X stack: message- and sender-level detection per attack class, delay per attacker,
false alarms, and 95% CIs by block bootstrap over time blocks.

Purpose: one place that turns an alarm array on a labelled message table into the numbers of the M1-V2X report.
Inputs: meta (DataFrame aligned with the alarm array: sender, t, y (bool), atype (str, "normal" for genuine), group (time block id)),
alarm (bool array), kinds (row kind from v2x.l4.row_kinds, optional), the list of attack classes.
Outputs: dict with, per class, message detection on all rows and on scored rows (kind 0), sender detection (>= k alarms), delay of the
detected attackers (first falsified message -> first alarm / k-th alarm) and, for every ratio, a block-bootstrap 95% CI
(resample whole time blocks with replacement; blocks hold disjoint senders, so no sender is split).
The bootstrap resamples the TEST blocks only: it measures how much the numbers move with the traffic / time of day, not model-fitting
variance (one model per run). With ~10 blocks the intervals are wide on purpose.
References: Efron & Tibshirani, An Introduction to the Bootstrap (block resampling); VeReMi split in v2x/splitting.py.
"""
import numpy as np
import pandas as pd

from common.config import SEED


def _sums(gcode, key, hit, nb, nk):
    """Per (block, key) hit counts and sizes; rows with key < 0 are ignored."""
    ok = key >= 0
    idx = gcode[ok] * nk + key[ok]
    H = np.bincount(idx, weights=hit[ok].astype(float), minlength=nb * nk).reshape(nb, nk)
    N = np.bincount(idx, minlength=nb * nk).reshape(nb, nk).astype(float)
    return H, N


def boot_ratio(H, N, subsets=None, B=1000, seed=SEED):
    """Point estimate and 95% CI of sum(H)/sum(N) per key, plus of the mean over each key subset (keys with N == 0 in the
    point estimate or in a resample are skipped). Returns (point[nk], ci[nk, 2], {name: (point, lo, hi)})."""
    nb = H.shape[0]
    rng = np.random.RandomState(seed)
    idx = rng.randint(0, nb, (B, nb))
    Hs, Ns = H[idx].sum(1), N[idx].sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(Ns > 0, Hs / np.maximum(Ns, 1), np.nan)
        point = np.where(N.sum(0) > 0, H.sum(0) / np.maximum(N.sum(0), 1), np.nan)
    ci = np.stack([np.nanpercentile(r, 2.5, axis=0), np.nanpercentile(r, 97.5, axis=0)], 1)
    sub = {}
    for name, keys in (subsets or {}).items():
        keys = list(keys)
        if not keys:
            continue
        m = np.nanmean(r[:, keys], axis=1)
        sub[name] = (float(np.nanmean(point[keys])), float(np.nanpercentile(m, 2.5)), float(np.nanpercentile(m, 97.5)))
    return point, ci, sub


def sender_table(meta, alarm, k=3):
    """One row per sender: class, block, number of messages, number of alarms, delay (s) from its first falsified message to the 1st / k-th alarm."""
    d = meta[["sender", "t", "atype", "group"]].assign(a=np.asarray(alarm, bool))
    d = d.sort_values(["sender", "t"], kind="stable")
    keys = ["sender", "atype"]                       # a vehicle id may appear in several scenarios (Tampa): one row per (sender, attack type)
    g = d.groupby(keys, sort=False)
    out = g.agg(group=("group", "first"), n=("a", "size"), n_alarm=("a", "sum"), t0=("t", "min"))
    ta = d[d["a"]].copy()
    ta["rank"] = ta.groupby(keys, sort=False).cumcount()
    first = ta[ta["rank"] == 0].set_index(keys)["t"]
    kth = ta[ta["rank"] == k - 1].set_index(keys)["t"]
    out["d1"] = (first.reindex(out.index) - out["t0"]).to_numpy()
    out["dk"] = (kth.reindex(out.index) - out["t0"]).to_numpy()
    return out.reset_index()


def _q(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return [float(np.percentile(x, 25)), float(np.median(x)), float(np.percentile(x, 75))] if len(x) else [None, None, None]


def evaluate_alarms(meta, alarm, classes, kinds=None, seen=None, unseen=None, k=3, min_scored=50, B=1000, seed=SEED):
    """See module docstring. `seen` / `unseen` = class names for the mean rows (unseen are excluded from seen)."""
    alarm = np.asarray(alarm, bool)
    y = meta["y"].to_numpy(bool)
    gcode, uniq = pd.factorize(meta["group"].astype(str))
    nb = int(gcode.max()) + 1
    cls = {c: i for i, c in enumerate(classes)}
    K = len(classes)
    atype = meta["atype"].to_numpy()
    key = np.where(y, [cls.get(a, -1) for a in atype], K).astype(int)
    out = {"n_blocks": nb, "bootstrap_B": B, "classes": list(classes), "k": k}
    seen = [c for c in (seen if seen is not None else classes) if c in cls]
    unseen = [c for c in (unseen or []) if c in cls]
    # --- message level, all rows ---
    H, N = _sums(gcode, key, alarm, nb, K + 1)
    pt, ci, sub = boot_ratio(H, N, {"seen": [cls[c] for c in seen], "unseen": [cls[c] for c in unseen], "all": list(range(K))}, B, seed)
    out["msg_all"] = {c: {"p": _f(pt[i]), "ci": [_f(ci[i, 0]), _f(ci[i, 1])], "n": int(N[:, i].sum())} for c, i in cls.items()}
    out["fa_msg"] = {"p": _f(pt[K]), "ci": [_f(ci[K, 0]), _f(ci[K, 1])], "n": int(N[:, K].sum())}
    out["mean_msg_all"] = {n: {"p": v[0], "ci": [v[1], v[2]]} for n, v in sub.items()}
    # --- message level, scored rows only ---
    if kinds is not None:
        kinds = np.asarray(kinds)
        key0 = np.where(kinds == 0, key, -1)
        H0, N0 = _sums(gcode, key0, alarm, nb, K + 1)
        pt0, ci0, _ = boot_ratio(H0, N0, None, B, seed)
        ok = {c: int(N0[:, cls[c]].sum()) >= min_scored for c in classes}
        subs = {"seen": [cls[c] for c in seen if ok[c]], "unseen": [cls[c] for c in unseen if ok[c]], "all": [cls[c] for c in classes if ok[c]]}
        _, _, sub0 = boot_ratio(H0, N0, subs, B, seed)
        out["msg_scored"] = {c: {"p": _f(pt0[i]), "ci": [_f(ci0[i, 0]), _f(ci0[i, 1])], "n": int(N0[:, i].sum()), "claimed": ok[c]} for c, i in cls.items()}
        out["fa_scored_msg"] = {"p": _f(pt0[K]), "ci": [_f(ci0[K, 0]), _f(ci0[K, 1])], "n": int(N0[:, K].sum())}
        out["mean_msg_scored"] = {n: {"p": v[0], "ci": [v[1], v[2]], "classes": [classes[i] for i in subs[n]]} for n, v in sub0.items()}
        share = {c: float((kinds[(atype == c) & y] == 0).mean()) if ((atype == c) & y).any() else None for c in classes}
        out["scored_share"] = share
    # --- sender level ---
    st = sender_table(meta, alarm, k)
    st["key"] = [cls.get(a, K) if a != "normal" else K for a in st["atype"]]
    gmap = {g: i for i, g in enumerate(uniq)}
    sgc = st["group"].astype(str).map(gmap).to_numpy()
    hit = (st["n_alarm"].to_numpy() >= k)
    Hs, Ns = _sums(sgc, st["key"].to_numpy(), hit, nb, K + 1)
    pts, cis, subs_ = boot_ratio(Hs, Ns, {"seen": [cls[c] for c in seen], "unseen": [cls[c] for c in unseen], "all": list(range(K))}, B, seed)
    out["sender"] = {}
    for c, i in cls.items():
        s = st[st["key"] == i]
        out["sender"][c] = {"p": _f(pts[i]), "ci": [_f(cis[i, 0]), _f(cis[i, 1])], "n_senders": int(len(s)),
                            "delay_first_alarm_s_q25_med_q75": _q(s["d1"]), "delay_kth_alarm_s_q25_med_q75": _q(s["dk"][s["n_alarm"] >= k]),
                            "detected_k": int((s["n_alarm"] >= k).sum())}
    out["fa_sender"] = {"p": _f(pts[K]), "ci": [_f(cis[K, 0]), _f(cis[K, 1])], "n_senders": int(Ns[:, K].sum())}
    out["mean_sender"] = {n: {"p": v[0], "ci": [v[1], v[2]]} for n, v in subs_.items()}
    return out


def _f(x):
    return None if x is None or not np.isfinite(x) else float(x)
