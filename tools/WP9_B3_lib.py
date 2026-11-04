"""WP9 B3 library: feature sets, cached tables, block-additive metrics with block bootstrap (VeReMi Extension, 20 classes).

Metrics are computed from per-block summaries (20x20 confusion matrix, score histograms, sender counts) so a block bootstrap costs milliseconds.
Alarm: s >= thr (s = 1 - P(genuine)); predicted class = argmax over attack classes on alarm, 0 otherwise.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

from common.config import SEED
from common.metrics import budget_threshold
from v2x import l4

CACHE = ROOT.parent / "data_extra" / "cache_v3" / "WP9" / "B3"
OUT = ROOT / "results" / "WP9"
K = 20
DOS = [13, 14, 15, 18, 19]
NAMES = {0: "Genuine", 1: "ConstPos", 2: "ConstPosOffset", 3: "RandomPos", 4: "RandomPosOffset", 5: "ConstSpeed", 6: "ConstSpeedOffset", 7: "RandomSpeed",
         8: "RandomSpeedOffset", 9: "EventualStop", 10: "Disruptive", 11: "DataReplay", 12: "DelayedMessages", 13: "DoS", 14: "DoSRandom", 15: "DoSDisruptive",
         16: "GridSybil", 17: "DataReplaySybil", 18: "DoSRandomSybil", 19: "DoSDisruptiveSybil"}
RAW = ["x", "y", "speed", "hcos", "hsin", "acl", "pos_sigma", "spd_sigma", "acl_sigma"]
T3 = ["track_pos", "dt_prev", "is_first"]
CROSS = ["overlap", "birth_density", "track_birth_density"]
_A = list(l4.FEATURES)
SETS = {
    "A_plaus": _A,
    "A_noT": [f for f in _A if f not in T3],
    "B_plaus_ps": [f for f in _A if f not in CROSS],
    "C_raw": RAW + ["dt_prev", "track_pos", "is_first", "rate"],
    "D_all": _A + RAW,
    "D_noT": [f for f in _A + RAW if f not in T3],
}
V3_REF_FEATURES = [f for f in l4.M_FEATURES if f != "rate"]       # l4.SCORED_SETS["S2_resid"]
assert V3_REF_FEATURES == l4.SCORED_SETS["S2_resid"]["features"]
FORBIDDEN = {"sender", "pseudo", "msg_id", "t", "block", "label", "sendTime", "messageID"}
assert not any(set(v) & FORBIDDEN for v in SETS.values())


def load_part(part, cache=CACHE):
    cols = json.loads((cache / "columns.json").read_text())
    F = pd.DataFrame(np.load(cache / f"{part}_feat.npy"), columns=cols)
    meta = pd.read_pickle(cache / f"{part}_meta.pkl")
    return F, meta


def journal(msg, step="B3"):
    import datetime
    with open(ROOT / "notes" / "WP8_journal.md", "a", encoding="utf-8") as f:
        f.write(f"{datetime.datetime.now().astimezone().isoformat(timespec='seconds')} | {step} | {msg}\n")


def jd(o, path):
    def cv(x):
        if isinstance(x, dict):
            return {str(k): cv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [cv(v) for v in x]
        if isinstance(x, (np.floating, float)):
            return None if not np.isfinite(x) else float(x)
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.ndarray):
            return cv(x.tolist())
        return x
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(cv(o), indent=1))
    tmp.replace(path)


# ----------------------------------------------------------------------------- decisions
def attack_score(P):
    return 1.0 - np.asarray(P[:, 0], dtype=np.float64)


def attack_class(P):
    return 1 + np.argmax(np.asarray(P[:, 1:]), axis=1)


def decide(s, c, thr):
    return np.where(np.asarray(s, dtype=np.float64) >= thr, c, 0)


def thr_budget(s_gen, budget=0.01):
    return budget_threshold(np.asarray(s_gen, dtype=np.float64), budget)


def thr_f1opt(y_att, s, n_grid=2000):
    """Threshold maximising binary attack F1 (natural prevalence) on the given scores (validation)."""
    s = np.asarray(s, dtype=np.float64)
    order = np.argsort(-s)
    ys = np.asarray(y_att, dtype=np.int64)[order]
    tp = np.cumsum(ys)
    k = np.arange(1, len(ys) + 1)
    P = ys.sum()
    f1 = 2 * tp / (k + P)
    i = int(np.argmax(f1))
    thr = float(s[order][i])
    return thr, float(f1[i])


# ----------------------------------------------------------------------------- confusion / macro-F1
def confusion(y, pred):
    return np.bincount(y.astype(np.int64) * K + pred.astype(np.int64), minlength=K * K).reshape(K, K)


def macro_from_conf(C, exclude=()):
    """macro-F1 over classes with support > 0 (exclude: classes dropped from rows AND columns' true side; predictions into them still count as errors)."""
    f1s, per = {}, {}
    for k in range(K):
        n = C[k].sum()
        tp = C[k, k]
        fp = C[:, k].sum() - tp
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / n if n else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        per[k] = {"f1": f, "recall": r, "precision": p, "n": int(n)}
        if n > 0 and k not in exclude:
            f1s[k] = f
    return float(np.mean(list(f1s.values()))), per


def macro_noclass(C, drop):
    """macro-F1 with the rows of class `drop` removed from the evaluation (messages of that class are not scored at all)."""
    C2 = C.copy()
    C2[drop, :] = 0
    return macro_from_conf(C2)[0]


def binary_from_conf(C, w_gen=1.0, classes=None):
    """Attack-vs-genuine counts; classes: attack classes included (None = all 1..19); genuine weighted by w_gen."""
    cl = list(range(1, K)) if classes is None else list(classes)
    tp = float(C[np.ix_(cl, list(range(1, K)))].sum())
    fn = float(C[cl, 0].sum())
    fp = w_gen * float(C[0, 1:].sum())
    tn = w_gen * float(C[0, 0])
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "fpr": fp / (fp + tn) if fp + tn else float("nan")}


# ----------------------------------------------------------------------------- block summaries
def block_summaries(meta, s, pred, thr, edges, k_sender=None):
    """One dict per block id: confusion, score histograms (genuine / attack), sender counts per class, flagged-sender counts per class (alarms >= k)."""
    out = {}
    y = meta["label"].to_numpy().astype(np.int64)
    blk = meta["block"].to_numpy()
    snd = meta["sender"].to_numpy()
    alarm = np.asarray(s, dtype=np.float64) >= thr
    nb = len(edges) - 1
    bins = np.clip(np.searchsorted(edges, np.asarray(s, dtype=np.float64), side="right") - 1, 0, nb - 1)
    for b in np.unique(blk):
        m = blk == b
        yy, pp, bb = y[m], pred[m], bins[m]
        hg = np.bincount(bb[yy == 0], minlength=nb)
        ha = np.bincount(bb[yy > 0], minlength=nb)
        sd = pd.DataFrame({"sender": snd[m], "y": yy, "a": alarm[m].astype(np.int64)}).groupby("sender").agg(y=("y", "first"), a=("a", "sum"))
        sc = np.bincount(sd["y"].to_numpy(), minlength=K)
        d = {"C": confusion(yy, pp), "hg": hg, "ha": ha, "S": sc}
        if k_sender is not None:
            d["FS"] = np.bincount(sd["y"].to_numpy()[sd["a"].to_numpy() >= k_sender], minlength=K)
        out[int(b)] = d
    return out


def auc_from_hist(hg, ha):
    """AUC (ties 0.5) from per-bin counts, bins in increasing score."""
    hg, ha = hg.astype(float), ha.astype(float)
    cg = np.cumsum(hg) - hg
    num = float((ha * (cg + 0.5 * hg)).sum())
    den = hg.sum() * ha.sum()
    return num / den if den else float("nan")


def stats_from_blocks(blocks, w_match=True):
    """All reported statistics from a list of block summaries (summed)."""
    C = sum(b["C"] for b in blocks)
    hg = sum(b["hg"] for b in blocks)
    ha = sum(b["ha"] for b in blocks)
    S = sum(b["S"] for b in blocks)
    mf, per = macro_from_conf(C)
    res = {"macro_f1": mf, "macro_f1_no12": macro_noclass(C, 12), "auc": auc_from_hist(hg, ha)}
    res["binary"] = binary_from_conf(C)
    res["fpr"] = res["binary"]["fpr"]
    res["alarm_recall"] = {k: (1.0 - C[k, 0] / C[k].sum() if C[k].sum() else float("nan")) for k in range(1, K)}
    res["class_recall"] = {k: (C[k, k] / C[k].sum() if C[k].sum() else float("nan")) for k in range(1, K)}
    res["mean_alarm_recall"] = float(np.nanmean(list(res["alarm_recall"].values())))
    res["mean_alarm_recall_no12"] = float(np.nanmean([v for k, v in res["alarm_recall"].items() if k != 12]))
    res["per_class_f1"] = {k: per[k]["f1"] for k in range(K)}
    dos = {}
    for k in DOS + ["pooled"]:
        cl = DOS if k == "pooled" else [k]
        nat = binary_from_conf(C, 1.0, cl)
        s_att = float(S[cl].sum())
        s_gen = float(S[0])
        w = (7.0 / 3.0) * s_att / s_gen if s_gen else float("nan")
        mat = binary_from_conf(C, w, cl)
        dos[str(k)] = {"natural": nat, "matched": mat, "w_gen": w}
    res["dos"] = dos
    if "FS" in blocks[0]:
        FS = sum(b["FS"] for b in blocks)
        res["sender_detection"] = {k: (FS[k] / S[k] if S[k] else float("nan")) for k in range(1, K)}
        res["sender_fa"] = float(FS[0] / S[0]) if S[0] else float("nan")
        res["sender_mean"] = float(np.nanmean(list(res["sender_detection"].values())))
    return res


def flat_numeric(res, prefix=""):
    out = {}
    for k, v in res.items():
        if isinstance(v, dict):
            out.update(flat_numeric(v, f"{prefix}{k}."))
        elif isinstance(v, (int, float, np.floating)):
            out[f"{prefix}{k}"] = float(v)
    return out


def bootstrap(blocks_by_id, B=1000, seed=SEED):
    ids = sorted(blocks_by_id)
    point = flat_numeric(stats_from_blocks([blocks_by_id[i] for i in ids]))
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(B):
        pick = rng.integers(len(ids), size=len(ids))
        rows.append(flat_numeric(stats_from_blocks([blocks_by_id[ids[j]] for j in pick])))
    df = pd.DataFrame(rows)
    ci = {k: [float(np.nanpercentile(df[k], 2.5)), float(np.nanpercentile(df[k], 97.5))] for k in df.columns}
    return point, ci


def score_edges(s_all, n_bins=4000):
    q = np.unique(np.quantile(np.asarray(s_all, dtype=np.float64), np.linspace(0, 1, n_bins + 1)))
    q[0], q[-1] = -np.inf, np.inf
    return q


def val_summary(meta, P, thr_h=None):
    """Validation metrics at the 1% budget threshold (no bootstrap): returns thr, macro-F1, FPR, mean alarm recall, AUC."""
    y = meta["label"].to_numpy()
    s = attack_score(P)
    c = attack_class(P)
    thr = thr_budget(s[y == 0], 0.01) if thr_h is None else thr_h
    pred = decide(s, c, thr)
    C = confusion(y, pred)
    mf, per = macro_from_conf(C)
    from sklearn.metrics import roc_auc_score
    return {"thr": float(thr), "macro_f1": mf, "fpr": float((pred[y == 0] != 0).mean()), "mean_alarm_recall": float(np.mean([1 - C[k, 0] / C[k].sum() for k in range(1, K)])),
            "auc": float(roc_auc_score((y > 0).astype(int), s)), "binary_f1": binary_from_conf(C)["f1"]}
