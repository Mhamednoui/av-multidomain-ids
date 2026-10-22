"""WP2 S6: L4 timing + payload models on ROAD, TRAIN + VALIDATION captures only (ROAD test is never read).

Stages (resumable, checkpoints under ../data_extra/WP2_S6_cache/road_run/):
  p1    v2 capture split: train on train captures, hyper-parameter search on val; score val captures (seen attack families)
  oof   13 folds (8 ambient captures, 5 attack families), P1 hyper-parameters, pooled out-of-fold scores (unseen families)
  ctrl  gain importance of the P1 models + shuffled-label control (5 seeds) on the validation frames / windows
Usage: python -u -W ignore tools/WP2_S6_road.py p1|oof|ctrl
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import adapters as A
from can import l1 as L
from can import l1_exp as E
from can import l4_exp as X
from can import l4_features as G
from common.config import DATA_EXTRA, RESULTS
from WP2_S6_cache import load

RUN = DATA_EXTRA / "WP2_S6_cache" / "road_run"
OUT = RESULTS / "WP2"
KEEP = 0.10
N_ITER = 6
SEEDS = [11, 12, 13, 14, 15]


def caps_table():
    c = A.road_captures()
    c = c[c["usable"] & c["part"].isin(["train", "val"])].sort_values("name").reset_index(drop=True)
    assert not (c["part"] == "test").any()
    return c


def fam_of(name):
    return A.road_family(name)


def load_all(caps):
    return {n: load("road", n) for n in caps["name"]}


def samples(caps, D):
    rng = np.random.default_rng(42)
    return {n: X.sample_mask(D[n]["label"], KEEP, rng) for n in caps["name"]}


def clean_of(d):
    return E.lead_clean(d["t"], d["label"])


def rev_frames(d):
    return (d["id"] == 0xD0) & ((d["B"][:, 2] & 0x08) > 0)


def build(D, names, sel, period, cols):
    Xs, ys = [], []
    for n in names:
        d, m = D[n], sel[n]
        Xs.append(X.matrix(d, period, cols, m))
        ys.append(d["label"][m].astype(np.int8))
    return np.concatenate(Xs), np.concatenate(ys)


def score_caps(D, names, models, period, codes, base_of, tag):
    """Frame scores + window table (all captures in `names`) for the models {'t': m, 'p': m}."""
    tabs, frames = [], {}
    for n in names:
        d = D[n]
        F = X.cap_F(d, codes, base_of[n], clean_of(d))
        sc = {k: X.predict(m, X.matrix(d, period, X.MODELS[k][1])) for k, m in models.items()}
        ex = {"rev": L.window_reduce(F, rev_frames(d).astype(np.int8)).astype(bool)}
        tb = X.window_rows(F, n, sc, ex)
        tb["fi"] = E.first_injected({"t": d["t"], "label": d["label"]}) if d["label"].any() else np.nan
        tabs.append(tb)
        frames[n] = {"y": d["label"], "att": F["att"], "clean": F["clean"], **sc}
        print(f"  {tag} scored {n} ({len(d['t'])} frames)", flush=True)
    return pd.concat(tabs, ignore_index=True), frames


def stage_p1():
    t0 = time.time()
    RUN.mkdir(parents=True, exist_ok=True)
    caps = caps_table()
    D = load_all(caps)
    sel = samples(caps, D)
    codes = E.AttCodes()
    base_of = {n: i for i, n in enumerate(caps["name"])}
    tr = caps.loc[caps["part"] == "train", "name"].tolist()
    va = caps.loc[caps["part"] == "val", "name"].tolist()
    period = X.period_of((D[n], clean_of(D[n])) for n in tr)
    print(f"period ids {len(period)}; train {tr.__len__()} val {len(va)} captures ({time.time() - t0:.0f}s)", flush=True)
    models, info = {}, {"keep_rate": KEEP, "n_ids_period": len(period), "train": tr, "val": va}
    for k, (nm, cols) in X.MODELS.items():
        Xtr, ytr = build(D, tr, sel, period, cols)
        Xva, yva = build(D, va, sel, period, cols)
        print(f"{nm}: train rows {len(ytr)} (attack {int(ytr.sum())}), val rows {len(yva)} (attack {int(yva.sum())})", flush=True)
        m, s = X.search(Xtr, ytr, Xva, yva, N_ITER)
        models[k] = m
        m.save_model(str(RUN / f"p1_{k}.json"))
        info[k] = {"rows_train": int(len(ytr)), "attack_train": int(ytr.sum()), "rows_val": int(len(yva)),
                   "attack_val": int(yva.sum()), "search": s, "importance": X.importance(m, cols)}
        print(f"{nm} best {s['params']} trees {s['n_trees']} val AP {s['val_ap']:.4f} ({time.time() - t0:.0f}s)", flush=True)
    tbl, frames = score_caps(D, va, models, period, codes, base_of, "p1")
    tbl.to_pickle(RUN / "p1_windows.pkl")
    pickle.dump(frames, open(RUN / "p1_frames.pkl", "wb"))
    json.dump({"period": {str(k): v for k, v in period.items()}, "codes": codes.names, **info}, open(RUN / "p1_info.json", "w"), indent=1)
    print("p1 done", f"({time.time() - t0:.0f}s)", flush=True)


def folds(caps):
    amb = caps.loc[caps["family"] == "ambient", "name"].tolist()
    fams = sorted(set(caps.loc[caps["family"] != "ambient", "family"]))
    out = [(f"amb:{n}", [n]) for n in amb]
    out += [(f"fam:{f}", caps.loc[caps["family"] == f, "name"].tolist()) for f in fams]
    return out


def stage_oof():
    t0 = time.time()
    caps = caps_table()
    D = load_all(caps)
    sel = samples(caps, D)
    base_of = {n: i for i, n in enumerate(caps["name"])}
    info = json.load(open(RUN / "p1_info.json"))
    codes = E.AttCodes()
    codes.names = list(info["codes"])
    allnames = caps["name"].tolist()
    for fname, held in folds(caps):
        out = RUN / ("oof_" + fname.replace(":", "_") + ".pkl")
        if out.exists():
            continue
        trn = [n for n in allnames if n not in held]
        period = X.period_of((D[n], clean_of(D[n])) for n in trn)
        models = {}
        for k, (nm, cols) in X.MODELS.items():
            Xtr, ytr = build(D, trn, sel, period, cols)
            models[k] = X.fit_fixed(Xtr, ytr, info[k]["search"]["params"], info[k]["search"]["n_trees"])
        tbl, frames = score_caps(D, held, models, period, codes, base_of, fname)
        pickle.dump({"tbl": tbl, "frames": frames, "held": held}, open(out, "wb"))
        print(f"fold {fname} done ({time.time() - t0:.0f}s)", flush=True)
    json.dump(codes.names, open(RUN / "oof_codes.json", "w"))


def stage_ctrl():
    t0 = time.time()
    caps = caps_table()
    D = load_all(caps)
    sel = samples(caps, D)
    info = json.load(open(RUN / "p1_info.json"))
    codes = E.AttCodes()
    codes.names = list(info["codes"])
    base_of = {n: i for i, n in enumerate(caps["name"])}
    tr, va = info["train"], info["val"]
    period = X.period_of((D[n], clean_of(D[n])) for n in tr)
    p1w = pd.read_pickle(RUN / "p1_windows.pkl")
    res = {}
    for k, (nm, cols) in X.MODELS.items():
        vi = X.select_variant(p1w, k, codes)["chosen"]
        Xtr, ytr = build(D, tr, sel, period, cols)
        Xva, yva = build(D, va, sel, period, cols)
        prm, nt = info[k]["search"]["params"], info[k]["search"]["n_trees"]
        r = {"variant": vi, "frame_auc": [], "window_auc": []}
        for s in SEEDS:
            ysh = np.random.default_rng(s).permutation(ytr)
            m = X.fit_fixed(Xtr, ysh, prm, nt, seed=s)
            r["frame_auc"].append(X.frame_auc(yva, m.predict_proba(Xva)[:, 1]))
            tb, _ = score_caps(D, va, {k: m}, period, codes, base_of, f"shuf{s}")
            r["window_auc"].append(X.window_auc(tb, k, vi))
            print(f"{nm} seed {s}: frame AUC {r['frame_auc'][-1]:.4f} window AUC {r['window_auc'][-1]:.4f} ({time.time() - t0:.0f}s)", flush=True)
        r["mean_frame_auc"], r["mean_window_auc"] = float(np.mean(r["frame_auc"])), float(np.mean(r["window_auc"]))
        r["bound"] = 0.55
        r["pass"] = bool(r["mean_frame_auc"] <= 0.55 and r["mean_window_auc"] <= 0.55)
        res[nm] = r
    json.dump(res, open(OUT / "s6_road_shuffle.json", "w"), indent=1)
    print("ctrl done")


if __name__ == "__main__":
    {"p1": stage_p1, "oof": stage_oof, "ctrl": stage_ctrl}[sys.argv[1]]()
