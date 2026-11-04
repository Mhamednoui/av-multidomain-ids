"""WP9 B1: fit + validation-only selection + controls. NEVER reads a test segment.

Usage: python -u -W ignore tools/WP9_B1_fit.py carhacking|road|d11 [set_01..set_04]
Candidates: F_xgb{a,b} (frame XGBoost multi-class, window = max attack score), W_xgb{a,b,c} x {generic, generic+ids},
W_rf x {generic, generic+ids}, F_noid (ablation), E (ensemble of best F and best W).
Selection: validation macro-F1 at the validation 1% false-alarm budget (see notes/WP9_B1.md, written before this run).
Outputs: results/WP9/B1_<ds>[_set]_selection.json, scores results/WP9/scores/B1/<ds>[_set]_val.npz,
models + bundle in data_extra/cache_v3/WP9/B1/models/<ds>[_set]/. Resumable per candidate (bundle files).
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP9_B1_lib as L
from common.config import SEED
from common.metrics import budget_threshold

N_JOBS = 4
N_NORM_FRAMES = 1_200_000
CAP_ATT = 150_000
F_GRID = {"Fa": dict(max_depth=6, learning_rate=0.15, subsample=0.8, colsample_bytree=0.8, min_child_weight=3),
          "Fb": dict(max_depth=9, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, min_child_weight=3)}
W_GRID = {"a": dict(max_depth=3, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, min_child_weight=1),
          "b": dict(max_depth=5, learning_rate=0.1, subsample=0.8, colsample_bytree=0.8, min_child_weight=1),
          "c": dict(max_depth=7, learning_rate=0.05, subsample=0.8, colsample_bytree=0.6, min_child_weight=2)}
SIMPLICITY = ["W_rf_generic", "W_xgb_a_generic", "W_xgb_b_generic", "W_xgb_c_generic", "W_rf_ids", "W_xgb_a_ids",
              "W_xgb_b_ids", "W_xgb_c_ids", "F_noid", "Fa", "Fb", "E"]


def log(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def cfg_for(ds, sset):
    idx = json.load(open(L.CACHE / ds / "index.json"))
    if ds == "carhacking":
        classes = L.CH_CLASSES
    elif ds == "road":
        classes = L.ROAD_CLASSES
    else:
        lock = json.load(open(L.LOCKS / "WP9_d11.json"))
        classes = lock["sets"][sset]["classes"]
        idx = [i for i in idx if i["set"] == sset]
    return classes, idx


def load_parts(ds, idx, parts):
    return [(i, L.load_segment(ds, i["seg"])) for i in idx if i["part"] in parts]


def make_period(segs):
    ids, dts = [], []
    for _, S in segs:
        m = (S["cls"] == 0) & S["ok"] & np.isfinite(S["dt_id"]) & (S["dt_id"] > 0)
        k = max(1, int(m.sum() // 400_000))
        ids.append(S["id"][m][::k]); dts.append(S["dt_id"][m][::k])
    df = pd.DataFrame({"id": np.concatenate(ids), "dt": np.concatenate(dts)})
    per = df.groupby("id")["dt"].median()
    return {int(k): float(v) for k, v in per.items()}


def make_id_list(segs, top=128, min_count=100):
    c = {}
    for _, S in segs:
        u, n = np.unique(S["id"][S["cls"] == 0], return_counts=True)
        for a, b in zip(u, n):
            c[int(a)] = c.get(int(a), 0) + int(b)
    keep = sorted([k for k, v in sorted(c.items(), key=lambda kv: -kv[1])[:top] if v >= min_count])
    return keep


def class_weights(y, power=0.5):
    cnt = np.bincount(y, minlength=y.max() + 1).astype(float)
    w = (cnt.max() / np.maximum(cnt, 1)) ** power
    w = w[y]
    return w / w.mean()


def sample_frames(segs, rng, n_norm=N_NORM_FRAMES, cap_att=CAP_ATT):
    tot_norm = sum(int(((S["cls"] == 0) & S["ok"]).sum()) for _, S in segs)
    rate = min(1.0, n_norm / max(tot_norm, 1))
    att_tot = {}
    for _, S in segs:
        u, n = np.unique(S["cls"][S["cls"] > 0], return_counts=True)
        for a, b in zip(u, n):
            att_tot[int(a)] = att_tot.get(int(a), 0) + int(b)
    parts = []
    for _, S in segs:
        c = S["cls"]
        keep = np.zeros(len(c), bool)
        norm = (c == 0) & S["ok"]
        keep[norm] = rng.random(int(norm.sum())) < rate
        for a, tot in att_tot.items():
            m = c == a
            keep[m] = rng.random(int(m.sum())) < min(1.0, cap_att / tot)
        parts.append((S, np.flatnonzero(keep)))
    return parts


def frame_data(parts, pid, pval, cols):
    X, y = [], []
    for S, ix in parts:
        sub = {k: S[k][ix] for k in ("id", "dlc", "B", "dt_prev", "dt_id", "n_id", "n_uniq", "bchg", "cls")}
        X.append(L.frame_matrix(sub, pid, pval, cols)); y.append(sub["cls"].astype(np.int64))
    return np.concatenate(X), np.concatenate(y)


def fit_xgb(X, y, K1, params, n_trees, Xv=None, yv=None, es=20, seed=SEED):
    kw = dict(early_stopping_rounds=es) if Xv is not None else {}
    m = xgb.XGBClassifier(n_estimators=n_trees, tree_method="hist", n_jobs=N_JOBS, random_state=seed,
                          objective="multi:softprob", num_class=K1, eval_metric="mlogloss", **kw, **params)
    if Xv is not None:
        m.fit(X, y, sample_weight=class_weights(y), eval_set=[(Xv, yv)], verbose=False)
    else:
        m.fit(X, y, sample_weight=class_weights(y), verbose=False)
    return m


def proba(m, X, K1, chunk=1_000_000):
    out = np.empty((len(X), K1), np.float32)
    for a in range(0, len(X), chunk):
        out[a:a + chunk] = m.predict_proba(X[a:a + chunk])
    return out


def sc(P):
    return (1.0 - P[:, 0]).astype(np.float32), (1 + np.argmax(P[:, 1:], axis=1)).astype(np.int16)


def importance_xgb(m, cols):
    g = m.get_booster().get_score(importance_type="total_gain")
    tot = sum(g.values()) or 1.0
    d = {c: float(g.get(f"f{i}", 0.0) / tot) for i, c in enumerate(cols)}
    return dict(sorted(d.items(), key=lambda kv: -kv[1])[:8])


def eval_val(y, s, c, groups, thr_budget=0.01, n_boot=0):
    thr = budget_threshold(s[y == 0], thr_budget)
    r = L.summarize(y, s, c, thr, groups=groups, n_boot=n_boot)
    return thr, r


def main():
    ds = sys.argv[1]
    sset = sys.argv[2] if len(sys.argv) > 2 else None
    tag = ds + (f"_{sset}" if sset else "")
    classes, idx = cfg_for(ds, sset)
    K1 = len(classes)
    mdir = L.CACHE / "models" / tag
    mdir.mkdir(parents=True, exist_ok=True)
    L.journal(f"fit {tag}: start (K+1={K1}); log results/WP9/logs/B1_fit_{tag}.log")
    rng = np.random.default_rng(SEED)
    tr = load_parts(ds, idx, ("train",))
    va = load_parts(ds, idx, ("val",))
    log(f"train segments {len(tr)} frames {sum(len(S['t']) for _, S in tr)}; val segments {len(va)} frames {sum(len(S['t']) for _, S in va)}")
    period = make_period(tr)
    id_list = make_id_list(tr)
    pid, pval = L.period_lookup(period)
    log(f"period ids {len(period)}, id_list {len(id_list)}")

    # ---------------- windows
    def windows(segs):
        out = []
        for i, S in segs:
            w = L.segment_windows(S, pid, pval, id_list, K1)
            w["group"] = i["group"]; w["seg"] = i["seg"]
            out.append(w)
        return out
    wtr, wva = windows(tr), windows(va)
    names = wtr[0]["names"]
    ng = len(L.WIN_GENERIC)

    def cat(ws, key, valid=True):
        return np.concatenate([w[key][w["valid"]] if valid else w[key] for w in ws])
    Wtr, ytr = cat(wtr, "W"), cat(wtr, "y")
    Wva, yva = cat(wva, "W"), cat(wva, "y")
    gva = np.concatenate([[w["group"]] * int(w["valid"].sum()) for w in wva])
    log(f"windows train {len(ytr)} class counts {np.bincount(ytr, minlength=K1).tolist()}; val {len(yva)} {np.bincount(yva, minlength=K1).tolist()}")
    assert (np.bincount(ytr, minlength=K1) > 0).all(), "a class has no training window"

    cands = {}       # name -> dict(s, c, P?)
    info = {"classes": classes, "train_windows": np.bincount(ytr, minlength=K1).tolist(),
            "val_windows": np.bincount(yva, minlength=K1).tolist(), "candidates": {}}
    sets = {"generic": slice(0, ng), "ids": slice(0, None)}
    controls, importance = {}, {}

    # ---------------- window models
    for fs, sl in sets.items():
        Xt, Xv = Wtr[:, sl], Wva[:, sl]
        cols = names[sl]
        for g, par in W_GRID.items():
            nm = f"W_xgb_{g}_{fs}"
            m = fit_xgb(Xt, ytr, K1, par, 400, Xv, yva)
            P = proba(m, Xv, K1)
            cands[nm] = {"s": sc(P)[0], "c": sc(P)[1], "P": P, "kind": "W", "fs": fs, "model": m, "params": par,
                         "n_trees": int(m.best_iteration + 1)}
            log(f"{nm} trees {m.best_iteration + 1}")
        nm = f"W_rf_{fs}"
        rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
                                    n_jobs=N_JOBS, random_state=SEED).fit(np.nan_to_num(Xt, nan=-1), ytr)
        P = rf.predict_proba(np.nan_to_num(Xv, nan=-1)).astype(np.float32)
        if P.shape[1] != K1:
            raise RuntimeError("rf classes")
        cands[nm] = {"s": sc(P)[0], "c": sc(P)[1], "P": P, "kind": "W", "fs": fs, "model": rf, "params": "rf300"}
        log(f"{nm} done")

    # ---------------- frame models
    ptr = sample_frames(tr, rng)
    pva = sample_frames(va, rng, n_norm=300_000, cap_att=100_000)
    for cols_name, cols in (("F", L.FRAME_COLS), ("F_noid", [c for c in L.FRAME_COLS if c != "id"])):
        Xf, yf = frame_data(ptr, pid, pval, cols)
        Xfv, yfv = frame_data(pva, pid, pval, cols)
        log(f"{cols_name} frame sample train {len(yf)} {np.bincount(yf, minlength=K1).tolist()} val {len(yfv)}")
        grid = F_GRID if cols_name == "F" else {"F_noid": F_GRID["Fa"]}
        for g, par in grid.items():
            m = fit_xgb(Xf, yf, K1, par, 300, Xfv, yfv)
            s_all, c_all, sw, cw = [], [], [], []
            ys = []
            for (i, S), w in zip(va, wva):
                P = proba(m, L.frame_matrix(S, pid, pval, cols), K1)
                s, c = sc(P)
                a, b = L.window_scores_from_frames(w["wid"], len(w["y"]), s, c)
                sw.append(a[w["valid"]]); cw.append(b[w["valid"]])
            cands[g] = {"s": np.concatenate(sw), "c": np.concatenate(cw), "kind": "F", "model": m, "params": par,
                        "cols": cols, "n_trees": int(m.best_iteration + 1)}
            log(f"{g} trees {m.best_iteration + 1}")
        if cols_name == "F":
            Fsample = (Xf, yf, Xfv, yfv)
    # ---------------- evaluation on validation
    for nm, c in cands.items():
        thr, r = eval_val(yva, c["s"], c["c"], gva)
        c["thr"] = thr
        info["candidates"][nm] = {"kind": c["kind"], "thr": thr, "val_macro_f1": r["macro_f1"], "val_fpr": r["fpr"],
                                  "val_recall_any": r["recall_any"], "val_auc": r["auc"],
                                  "val_macro_f1_argmax": r["macro_f1_argmax"], "params": c["params"],
                                  "n_trees": c.get("n_trees")}
        log(f"VAL {nm}: macroF1@1% {r['macro_f1']:.4f} FPR {r['fpr']:.4f} recall {r['recall_any']:.4f} AUC {r['auc']:.4f}")
    # ensemble of best F and best W (by val macro-F1)
    bestF = max([n for n in cands if cands[n]["kind"] == "F" and n != "F_noid"], key=lambda n: info["candidates"][n]["val_macro_f1"])
    bestW = max([n for n in cands if cands[n]["kind"] == "W"], key=lambda n: info["candidates"][n]["val_macro_f1"])
    ref = {n: np.sort(cands[n]["s"][yva == 0]) for n in (bestF, bestW)}

    def ecdf(n, s):
        return np.searchsorted(ref[n], s, side="right") / len(ref[n])
    uF, uW = ecdf(bestF, cands[bestF]["s"]), ecdf(bestW, cands[bestW]["s"])
    cands["E"] = {"s": ((uF + uW) / 2).astype(np.float32), "c": np.where(uW >= uF, cands[bestW]["c"], cands[bestF]["c"]),
                  "kind": "E", "parts": [bestF, bestW], "params": "ensemble"}
    thr, r = eval_val(yva, cands["E"]["s"], cands["E"]["c"], gva)
    cands["E"]["thr"] = thr
    info["candidates"]["E"] = {"kind": "E", "thr": thr, "val_macro_f1": r["macro_f1"], "val_fpr": r["fpr"],
                               "val_recall_any": r["recall_any"], "val_auc": r["auc"], "parts": [bestF, bestW]}
    log(f"VAL E({bestF},{bestW}): macroF1@1% {r['macro_f1']:.4f} FPR {r['fpr']:.4f} recall {r['recall_any']:.4f}")

    # ---------------- selection: best val macro-F1; ties (within 0.002) -> simpler
    best = max(info["candidates"][n]["val_macro_f1"] for n in cands)
    tied = [n for n in SIMPLICITY if n in cands and info["candidates"][n]["val_macro_f1"] >= best - 0.002]
    chosen = tied[0]
    generic = [n for n in cands if n.endswith("_generic")]
    chosen_generic = max(generic, key=lambda n: info["candidates"][n]["val_macro_f1"])
    log(f"CHOSEN {chosen} (best val macro-F1 {best:.4f}); vehicle-agnostic secondary {chosen_generic}")

    # ---------------- controls: shuffled labels, selected learned units
    prng = np.random.default_rng(SEED + 1)
    units = {n for n in ([chosen] + ([cands[chosen]["parts"][0], cands[chosen]["parts"][1]] if chosen == "E" else [])
                         + [chosen_generic, bestF, bestW])} - {"E"}
    for n in sorted(units):
        c = cands[n]
        if c["kind"] == "W":
            sl = sets[c["fs"]]
            ysh = prng.permutation(ytr)
            if n.startswith("W_rf"):
                mm = RandomForestClassifier(n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
                                            n_jobs=N_JOBS, random_state=SEED).fit(np.nan_to_num(Wtr[:, sl], nan=-1), ysh)
                P = mm.predict_proba(np.nan_to_num(Wva[:, sl], nan=-1))
            else:
                mm = fit_xgb(Wtr[:, sl], ysh, K1, c["params"], c["n_trees"])
                P = mm.predict_proba(Wva[:, sl])
            auc = L.auc_binary((yva != 0).astype(int), 1 - P[:, 0])
            controls[n] = {"unit": "window", "shuffled_auc_window": auc, "pass": bool(0.42 <= auc <= 0.58)}
        elif c["kind"] == "F":
            cols = c["cols"]
            Xf, yf = frame_data(ptr, pid, pval, cols)
            Xfv, yfv = frame_data(pva, pid, pval, cols)
            ysh = prng.permutation(yf)
            mm = fit_xgb(Xf, ysh, K1, c["params"], c["n_trees"])
            Pf = mm.predict_proba(Xfv)
            auc_f = L.auc_binary((yfv != 0).astype(int), 1 - Pf[:, 0])
            sw = []
            for (i, S), w in zip(va, wva):
                P = proba(mm, L.frame_matrix(S, pid, pval, cols), K1)
                s, cc = sc(P)
                a, _ = L.window_scores_from_frames(w["wid"], len(w["y"]), s, cc)
                sw.append(a[w["valid"]])
            auc_w = L.auc_binary((yva != 0).astype(int), np.concatenate(sw))
            controls[n] = {"unit": "frame", "shuffled_auc_frame": auc_f, "shuffled_auc_window_max": auc_w,
                           "pass": bool(0.42 <= auc_f <= 0.58)}
        log(f"CONTROL {n}: {controls[n]}")
    # importance
    for n in sorted(units):
        c = cands[n]
        if c["kind"] == "W" and n.startswith("W_xgb"):
            importance[n] = importance_xgb(c["model"], names[sets[c["fs"]]])
        elif c["kind"] == "W":
            fi = c["model"].feature_importances_
            cols = names[sets[c["fs"]]]
            importance[n] = dict(sorted({cols[i]: float(fi[i]) for i in range(len(cols))}.items(), key=lambda kv: -kv[1])[:8])
        elif c["kind"] == "F":
            importance[n] = importance_xgb(c["model"], c["cols"])
        log(f"IMPORTANCE {n}: {list(importance[n].items())[:5]}")

    # ---------------- save
    models = {}
    for n, c in cands.items():
        if "model" in c:
            if n.startswith("W_rf"):
                with open(mdir / f"{n}.pkl", "wb") as f:
                    pickle.dump(c["model"], f)
            else:
                c["model"].save_model(str(mdir / f"{n}.ubj"))
    bundle = {"period": period, "id_list": id_list, "classes": classes, "names": names, "ng": ng, "chosen": chosen,
              "chosen_generic": chosen_generic, "thr": {n: c["thr"] for n, c in cands.items()},
              "ensemble": {"parts": cands["E"]["parts"], "ref": {n: ref[n] for n in ref}},
              "cols": {n: c.get("cols") for n, c in cands.items() if c["kind"] == "F"},
              "fs": {n: c.get("fs") for n, c in cands.items() if c["kind"] == "W"}, "K1": K1}
    with open(mdir / "bundle.pkl", "wb") as f:
        pickle.dump(bundle, f)
    np.savez(L.SCORES / f"{tag}_val.npz", y=yva, group=gva, **{f"s_{n}": c["s"] for n, c in cands.items()},
             **{f"c_{n}": c["c"] for n, c in cands.items()})
    # final validation numbers with bootstrap for the chosen model
    thr, rv = eval_val(yva, cands[chosen]["s"], cands[chosen]["c"], gva, n_boot=300)
    info.update({"dataset": ds, "set": sset, "chosen": chosen, "chosen_vehicle_agnostic": chosen_generic,
                 "chosen_val": rv, "controls": controls, "importance": importance, "period_ids": len(period),
                 "id_list": id_list, "n_frames_train_sample": int(len(Fsample[1])), "ablation_noid_val_macro_f1":
                 info["candidates"].get("F_noid", {}).get("val_macro_f1"), "selection_rule":
                 "max validation macro-F1 at the validation 1% FA budget; ties within 0.002 -> simpler (SIMPLICITY order)",
                 "lock": str(L.LOCKS / f"WP9_{ds}.json"), "bundle": str(mdir / "bundle.pkl")})
    L.jd(info, L.OUT / f"B1_{tag}_selection.json")
    L.journal(f"fit {tag}: done, chosen {chosen}; results/WP9/B1_{tag}_selection.json")
    log("done")


if __name__ == "__main__":
    L.SCORES.mkdir(parents=True, exist_ok=True)
    main()
