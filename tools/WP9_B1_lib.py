"""WP9 B1 library: CAN benchmark track (Car-Hacking, ROAD, can-train-and-test), leak-free, seen attack types.

Purpose: parse + deduplicate captures, cut segments (split units), causal frame features, 1 s window features,
metrics with capture/block bootstrap. Used by tools/WP9_B1_{lock,build,fit,test}.py.
Class codes per frame (int8): 0 = normal, 1..K = seen attack class (dataset class list), -1 = attack family
unseen in training (ROAD coolant, D11 test_03 / test_04 families).
Reuses (imports) can/adapters.py, can/frames.py, can/l4_features.stream_raw (WP2/S6 code, same repo).
Inputs: raw datasets (read as text only). Outputs: arrays / dicts. References: Seo 2018 / Song 2020 (Car-Hacking),
Verma 2022 (ROAD), Lampe & Meng 2023 (D11).
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from can import adapters as A
from can.frames import BYTE_COLS, hex_to_bytes
from can.l4_features import stream_raw
from common.config import DATA, DATA_EXTRA, RESULTS, ROOT, SEED

CACHE = DATA_EXTRA / "cache_v3" / "WP9" / "B1"
LOCKS = ROOT / "locks"
OUT = RESULTS / "WP9"
SCORES = OUT / "scores" / "B1"
WIN = 1.0           # window length in seconds
GAP = 1.0           # seconds dropped around a boundary between different parts (Car-Hacking blocks)
CH_CLASSES = ["Normal", "DoS", "Fuzzy", "RPM", "Gear"]
ROAD_SEEN = ["correlated_signal", "fuzzing", "max_speedometer", "reverse_light_off", "reverse_light_on"]
ROAD_CLASSES = ["Normal"] + [c for f in ROAD_SEEN for c in ([f, f + "_masquerade"] if f != "fuzzing" else [f])]
ROAD_UNSEEN = ["max_engine_coolant_temp", "max_engine_coolant_temp_masquerade"]


def sha256_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ fast Car-Hacking parser (same output as adapters.load_carhacking)
def _hex2(col: pd.Series, dlc, i) -> np.ndarray:
    s = col.fillna("00").to_numpy().astype("S2")
    v = np.frombuffer(s.tobytes(), dtype=np.uint8).reshape(len(s), 2)
    hv = np.full(256, 0, np.uint8)
    for k, c in enumerate("0123456789abcdef"):
        hv[ord(c)] = k
        hv[ord(c.upper())] = k
    out = ((hv[v[:, 0]].astype(np.int16) << 4) | hv[v[:, 1]]).astype(np.int16)
    out[i >= dlc] = -1
    return out


def parse_carhacking(name: str) -> dict:
    raw = pd.read_csv(DATA / A.CARHACKING_FILES[name], header=None, names=list(range(12)), dtype=str)
    dlc = raw[2].astype(int).to_numpy()
    B = np.stack([_hex2(raw[3 + i], dlc, i) for i in range(8)], axis=1)
    flag = raw.iloc[:, 3:12].to_numpy()[np.arange(len(raw)), dlc]
    uniq = raw[1].unique()
    ids = raw[1].map({u: int(u, 16) for u in uniq}).to_numpy()
    t = raw[0].astype(float).to_numpy()
    return {"t": t - t[0], "id": ids.astype(np.int32), "dlc": dlc.astype(np.int8), "B": B,
            "lab": (flag == "T").astype(np.int8)}


def parse_carhacking_normal() -> dict:
    """normal_run_data.txt: 'Timestamp: <t>  ID: <id>  000  DLC: <n>  <bytes>' (HCRL text format)."""
    p = DATA / "normal_run_data.txt"
    rows = []
    with open(p, "r", errors="replace") as f:
        for ln in f:
            w = ln.split()
            if len(w) < 7 or w[0] != "Timestamp:":
                continue
            rows.append(w)
    t = np.array([float(w[1]) for w in rows])
    ids = np.array([int(w[3], 16) for w in rows], np.int32)
    dlc = np.array([int(w[6]) for w in rows], np.int8)
    pay = ["".join(w[7:7 + d]) for w, d in zip(rows, dlc)]
    _, B = hex_to_bytes(pay)
    return {"t": t - t[0], "id": ids, "dlc": dlc, "B": B, "lab": np.zeros(len(t), np.int8)}


def parse_road(name: str, caps=None) -> dict:
    f = A.load_road(name, caps)
    lab = f["label"].to_numpy().astype(np.int8)
    att = f["attack"].astype(str).to_numpy()
    return {"t": f["t"].to_numpy(), "id": f["id"].to_numpy(), "dlc": f["dlc"].to_numpy(),
            "B": f[BYTE_COLS].to_numpy().astype(np.int16), "lab": lab, "att": att}


def parse_d11(capture: str, path) -> dict:
    f = A.load_d11(Path(path), capture, "v")
    return {"t": f["t"].to_numpy(), "id": f["id"].to_numpy(), "dlc": f["dlc"].to_numpy(),
            "B": f[BYTE_COLS].to_numpy().astype(np.int16), "lab": f["label"].to_numpy().astype(np.int8),
            "att": f["attack"].astype(str).to_numpy()}


def dedup(d: dict) -> tuple:
    """Drop rows identical in (t, id, dlc, payload), keep the first in recorded order. Returns (d, report)."""
    n = len(d["t"])
    df = pd.DataFrame({"t": d["t"], "id": d["id"], "dlc": d["dlc"]})
    for i in range(8):
        df[f"b{i}"] = d["B"][:, i]
    dup = df.duplicated(keep="first").to_numpy()
    rep = {"rows": int(n), "exact_duplicates": int(dup.sum())}
    if dup.any():
        key = df.drop_duplicates(keep=False)
        full = df.copy()
        full["lab"] = d["lab"]
        conflict = int(full.duplicated(subset=list(df.columns), keep=False).sum() - full.duplicated(keep=False).sum())
        rep["label_conflicts"] = conflict
        keep = ~dup
        d = {k: (v[keep] if isinstance(v, np.ndarray) else v) for k, v in d.items()}
    rep["rows_after"] = int(len(d["t"]))
    return d, rep


# ------------------------------------------------------------------ class codes
def class_codes(d: dict, classes: list, unseen: list = ()) -> np.ndarray:
    """Per-frame code. d['att'] holds the attack name per frame ('normal' for clean)."""
    att = d["att"]
    cls = np.zeros(len(att), np.int8)
    for k, c in enumerate(classes):
        if k:
            cls[att == c] = k
    for c in unseen:
        cls[att == c] = -1
    return cls


# ------------------------------------------------------------------ cache of parsed + raw stream features
def seg_path(ds: str, seg: str) -> Path:
    p = CACHE / ds
    p.mkdir(parents=True, exist_ok=True)
    return p / (seg.replace("/", "__") + ".npz")


def save_atomic(path: Path, **arrs):
    tmp = path.with_name(path.stem + ".tmp.npz")
    np.savez(tmp, **arrs)
    tmp.replace(path)


def build_segment(d: dict, cls: np.ndarray, valid_frame=None) -> dict:
    """Raw per-frame arrays + causal stream features for one segment (recorded order, t from segment start)."""
    t = d["t"] - d["t"][0]
    raw = stream_raw(t, d["id"], d["dlc"], d["B"])
    out = {"t": t, "id": d["id"].astype(np.int32), "dlc": d["dlc"].astype(np.int8), "B": d["B"].astype(np.int16),
           "cls": cls.astype(np.int8), "dt_prev": raw["dt_prev"], "dt_id": raw["dt_id"], "n_id": raw["n_id"],
           "n_uniq": raw["n_uniq"], "bchg": raw["bchg"]}
    out["ok"] = np.ones(len(t), bool) if valid_frame is None else valid_frame.astype(bool)
    return out


def load_segment(ds: str, seg: str) -> dict:
    z = np.load(seg_path(ds, seg), allow_pickle=False)
    return {k: z[k] for k in z.files}


# ------------------------------------------------------------------ features
FRAME_COLS = ["id", "dlc"] + BYTE_COLS + ["dt_prev", "dt_id", "id_known", "dt_id_ratio", "n_id_win",
                                         "n_unique_win", "bytes_changed", "same_payload"]


def period_lookup(period: dict):
    pid = np.array(sorted(period), np.int64)
    return pid, np.array([period[int(i)] for i in pid], np.float64)


def frame_matrix(S: dict, pid, pval, cols=FRAME_COLS) -> np.ndarray:
    ids = S["id"]
    n = len(ids)
    if len(pid):
        pos = np.minimum(np.searchsorted(pid, ids), len(pid) - 1)
        known = pid[pos] == ids
        per = np.where(known, pval[pos], np.nan)
    else:
        known, per = np.zeros(n, bool), np.full(n, np.nan)
    B = S["B"]
    bchg = S["bchg"].astype(np.float32)
    bchg[S["bchg"] < 0] = np.nan
    ratio = (S["dt_id"] / per).astype(np.float32)
    cd = {"id": ids, "dlc": S["dlc"], "dt_prev": S["dt_prev"], "dt_id": S["dt_id"], "id_known": known,
          "dt_id_ratio": ratio, "n_id_win": S["n_id"], "n_unique_win": S["n_uniq"], "bytes_changed": bchg,
          "same_payload": np.where(np.isnan(bchg), np.nan, (bchg == 0).astype(np.float32))}
    X = np.empty((n, len(cols)), np.float32)
    for k, c in enumerate(cols):
        X[:, k] = cd[c] if c in cd else B[:, int(c[1:])]
    return X


WIN_GENERIC = (["n", "n_ids", "id_entropy", "max_id_share", "dt_mean", "dt_std", "dt_min", "dt_max", "dt_burst",
                "ratio_mean", "ratio_std", "ratio_min", "ratio_max", "ratio_lo", "ratio_hi", "unknown_id",
                "nid_mean", "nid_max", "nuniq_mean", "bchg_mean", "same_payload", "first_of_id", "dlc_mean", "dlc_std"]
               + [f"byte_mean{i}" for i in range(8)] + [f"byte_std{i}" for i in range(8)] + ["payload_unique"])


def window_index(t, win=WIN):
    return np.floor((t - t[0]) / win).astype(np.int64)


def _g(df, key, col, fn):
    return getattr(df.groupby(key, sort=True)[col], fn)()


def window_features(S: dict, pid, pval, id_list) -> tuple:
    """One row per 1 s window of the segment. Returns (W float32 (nw, F), names, wid_of_frame int64, frame_count).
    Generic features (ID-agnostic) + per-known-ID counts (names 'cnt_<id>' and 'cnt_other')."""
    wid = window_index(S["t"])
    n = len(wid)
    nw = int(wid.max()) + 1
    X = frame_matrix(S, pid, pval, cols=["dt_prev", "dt_id_ratio", "id_known", "n_id_win", "n_unique_win",
                                         "bytes_changed", "same_payload", "dlc"])
    dtp, ratio, known, nid, nuq, bch, same, dlc = [X[:, i] for i in range(8)]
    df = pd.DataFrame({"w": wid, "dt": dtp, "r": ratio, "known": known, "nid": nid, "nuq": nuq, "bch": bch,
                       "same": same, "dlc": dlc, "id": S["id"]})
    df["burst"] = (df["dt"] < 1e-4).astype(np.float32)
    df["lo"] = (df["r"] < 0.5).astype(np.float32).where(df["r"].notna())
    df["hi"] = (df["r"] > 1.5).astype(np.float32).where(df["r"].notna())
    df["first"] = (S["bchg"] < 0).astype(np.float32)
    df["unk"] = 1.0 - df["known"]
    grp = df.groupby("w", sort=True)
    cnt = np.zeros(nw)
    cnt_s = grp.size()
    cnt[cnt_s.index.to_numpy()] = cnt_s.to_numpy()
    cols = {}

    def put(name, series):
        a = np.full(nw, np.nan, np.float64)
        a[series.index.to_numpy()] = series.to_numpy()
        cols[name] = a
    cols["n"] = cnt
    pc = df.groupby(["w", "id"]).size()
    pw = pc.index.get_level_values(0).to_numpy()
    p = pc.to_numpy() / cnt[pw]
    ent = np.zeros(nw)
    np.add.at(ent, pw, -p * np.log(p))
    cols["id_entropy"] = ent
    nids = np.zeros(nw)
    np.add.at(nids, pw, 1)
    cols["n_ids"] = nids
    mx = np.zeros(nw)
    np.maximum.at(mx, pw, p)
    cols["max_id_share"] = mx
    put("dt_mean", grp["dt"].mean()); put("dt_std", grp["dt"].std()); put("dt_min", grp["dt"].min())
    put("dt_max", grp["dt"].max()); put("dt_burst", grp["burst"].mean())
    put("ratio_mean", grp["r"].mean()); put("ratio_std", grp["r"].std()); put("ratio_min", grp["r"].min())
    put("ratio_max", grp["r"].max()); put("ratio_lo", grp["lo"].mean()); put("ratio_hi", grp["hi"].mean())
    put("unknown_id", grp["unk"].mean())
    put("nid_mean", grp["nid"].mean()); put("nid_max", grp["nid"].max()); put("nuniq_mean", grp["nuq"].mean())
    put("bchg_mean", grp["bch"].mean()); put("same_payload", grp["same"].mean()); put("first_of_id", grp["first"].mean())
    put("dlc_mean", grp["dlc"].mean()); put("dlc_std", grp["dlc"].std())
    B = S["B"].astype(np.float32)
    B[B < 0] = np.nan
    bd = pd.DataFrame(B, columns=[f"b{i}" for i in range(8)])
    bd["w"] = wid
    bg = bd.groupby("w", sort=True)
    bm, bs = bg.mean(), bg.std()
    for i in range(8):
        put(f"byte_mean{i}", bm[f"b{i}"]); put(f"byte_std{i}", bs[f"b{i}"])
    ph = pd.util.hash_array(S["B"].astype(np.int64).dot(256 ** np.arange(8, dtype=np.int64)))
    pu = pd.DataFrame({"w": wid, "h": ph}).groupby("w")["h"].nunique()
    put("payload_unique", pu / pd.Series(cnt[pu.index.to_numpy()], index=pu.index))
    G = np.stack([cols[c] for c in WIN_GENERIC], axis=1)
    # per-ID counts
    il = np.asarray(id_list, np.int64)
    pos = np.searchsorted(il, S["id"])
    pos[pos >= len(il)] = len(il) - 1 if len(il) else 0
    hit = (il[pos] == S["id"]) if len(il) else np.zeros(n, bool)
    col = np.where(hit, pos, len(il))
    C = np.zeros((nw, len(il) + 1), np.float32)
    np.add.at(C, (wid, col), 1.0)
    names = WIN_GENERIC + [f"cnt_{int(i)}" for i in il] + ["cnt_other"]
    return np.concatenate([G.astype(np.float32), C], axis=1), names, wid, cnt


def window_labels(S: dict, wid, nw, n_classes) -> tuple:
    """Per-window class (0 normal; k = attack class code of injected frames, most frequent; -1 unseen family) and
    the number of injected frames. ROAD ambiguity handling is done by the caller through S['ok'] (frames)."""
    c = S["cls"]
    att = c != 0
    n_att = np.bincount(wid[att], minlength=nw)
    y = np.zeros(nw, np.int16)
    if att.any():
        # most frequent attack class per window (classes -1 .. K)
        key = wid[att] * (n_classes + 2) + (c[att].astype(np.int64) + 1)
        u, cnts = np.unique(key, return_counts=True)
        w_of, c_of = u // (n_classes + 2), (u % (n_classes + 2)) - 1
        order = np.lexsort((cnts, w_of))
        last = np.r_[w_of[order][1:] != w_of[order][:-1], True]
        y[w_of[order][last]] = c_of[order][last]
    return y, n_att


# ------------------------------------------------------------------ metrics
def f1(p, r):
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def macro_f1(y, pred, classes_idx):
    out = {}
    for k in classes_idx:
        tp = np.sum((y == k) & (pred == k)); fp = np.sum((y != k) & (pred == k)); fn = np.sum((y == k) & (pred != k))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        out[k] = (f1(p, r), r, p, int(np.sum(y == k)))
    present = [k for k in classes_idx if out[k][3] > 0]
    return float(np.mean([out[k][0] for k in present])), out


def decide(s, c, thr):
    """Alarm if attack score s >= thr; class = c (1..K) on alarm, 0 otherwise."""
    return np.where(s >= thr, c, 0)


def auc_binary(y_bin, s):
    from sklearn.metrics import roc_auc_score
    if y_bin.min() == y_bin.max():
        return float("nan")
    return float(roc_auc_score(y_bin, s))


def summarize(y, s, c, thr, pred_arg=None, groups=None, seen_idx=None, n_boot=1000, seed=SEED):
    """y: window class (0, 1..K, -1 unseen). s: attack score, c: predicted attack class (1..K); alarm = s >= thr.
    pred_arg: optional plain-argmax prediction (no budget). macro-F1 over seen classes present; per-class recall; FPR;
    AUC (attack vs normal); bootstrap over `groups` (capture / block run)."""
    seen_idx = sorted(set(int(k) for k in np.unique(np.r_[y, c, 0]) if k >= 0)) if seen_idx is None else seen_idx
    pred = decide(s, c, thr)

    def stats(ix):
        yy, pp, ss = y[ix], pred[ix], s[ix]
        pa = pred_arg[ix] if pred_arg is not None else pp
        m_idx = [k for k in seen_idx]
        mf, per = macro_f1(yy, pp, m_idx)
        mfa, pera = macro_f1(yy, pa, m_idx)
        neg = yy == 0
        pos = yy != 0
        d = {"macro_f1": mf, "macro_f1_argmax": mfa,
             "fpr": float(np.mean(pp[neg] != 0)) if neg.any() else float("nan"),
             "recall_any": float(np.mean(pp[pos] != 0)) if pos.any() else float("nan"),
             "auc": auc_binary((yy != 0).astype(int), ss),
             "f1_attack_binary": None}
        tp = np.sum(pos & (pp != 0)); fp = np.sum(neg & (pp != 0)); fn = np.sum(pos & (pp == 0))
        pr = tp / (tp + fp) if tp + fp else 0.0; rc = tp / (tp + fn) if tp + fn else 0.0
        d["f1_attack_binary"] = float(f1(pr, rc)); d["precision_binary"] = float(pr)
        d["per_class_recall"] = {str(k): (float(v[1]) if v[3] else None) for k, v in per.items()}
        d["per_class_f1"] = {str(k): (float(v[0]) if v[3] else None) for k, v in per.items()}
        d["per_class_n"] = {str(k): v[3] for k, v in per.items()}
        d["per_class_alarm_recall"] = {str(k): (float(np.mean(pp[yy == k] != 0)) if v[3] and k != 0 else None)
                                       for k, v in per.items()}
        # unseen windows: any-alarm recall
        un = yy == -1
        d["recall_unseen_any"] = float(np.mean(pp[un] != 0)) if un.any() else None
        d["n_unseen"] = int(un.sum())
        return d

    res = stats(np.arange(len(y)))
    res["n_windows"] = int(len(y))
    if groups is not None and n_boot:
        g = np.asarray(groups)
        ug, inv = np.unique(g, return_inverse=True)
        idx = [np.flatnonzero(inv == i) for i in range(len(ug))]
        rng = np.random.default_rng(seed)
        keys = ["macro_f1", "macro_f1_argmax", "fpr", "recall_any", "auc", "f1_attack_binary"]
        boots = {k: [] for k in keys}
        pcr = {}
        for b in range(n_boot):
            pick = rng.integers(len(ug), size=len(ug))
            ix = np.concatenate([idx[i] for i in pick])
            sb = stats(ix)
            for k in keys:
                boots[k].append(sb[k])
            for k, v in sb["per_class_recall"].items():
                pcr.setdefault(k, []).append(np.nan if v is None else v)
        res["ci95"] = {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in boots.items()}
        res["ci95_per_class_recall"] = {k: ([float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
                                            if np.isfinite(v).any() else None) for k, v in pcr.items()}
        res["n_groups"] = int(len(ug))
    return res


def jd(o, path):
    def cv(x):
        if isinstance(x, dict):
            return {str(k): cv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [cv(v) for v in x]
        if isinstance(x, (np.floating, float)):
            return None if not np.isfinite(x) else float(x)
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, np.ndarray):
            return cv(x.tolist())
        return x
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cv(o), f, indent=1)


def journal(msg: str, step: str = "B1"):
    import datetime
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    with open(ROOT / "notes" / "WP8_journal.md", "a", encoding="utf-8") as f:
        f.write(f"{ts} | {step} | {msg}\n")


# ------------------------------------------------------------------ segment windows
def segment_windows(S: dict, pid, pval, id_list, n_classes: int) -> dict:
    """Window table of one cached segment. valid = non-empty, not the last (partial) window, and either contains an injected
    frame or contains no frame flagged not-ok (ambiguous frames, ROAD)."""
    W, names, wid, cnt = window_features(S, pid, pval, id_list)
    nw = W.shape[0]
    y, n_att = window_labels(S, wid, nw, n_classes)
    n_bad = np.bincount(wid[~S["ok"] & (S["cls"] == 0)], minlength=nw)
    valid = (cnt > 0) & ((n_att > 0) | (n_bad == 0))
    valid[nw - 1] = False
    return {"W": W, "names": names, "y": y, "valid": valid, "wid": wid, "cnt": cnt, "n_att": n_att}


def window_scores_from_frames(wid, nw, s, c):
    """Per-window max of frame attack score s and the attack class c of that frame (c: argmax over attack columns, 1-based)."""
    order = np.lexsort((s, wid))
    w_sorted = wid[order]
    last = np.r_[w_sorted[1:] != w_sorted[:-1], True]
    sw = np.zeros(nw, np.float32)
    cw = np.ones(nw, np.int16)
    sw[w_sorted[last]] = s[order][last]
    cw[w_sorted[last]] = c[order][last]
    return sw, cw
