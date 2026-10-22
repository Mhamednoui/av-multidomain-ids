"""WP2 S6: L4 timing + payload models on Car-Hacking (v2 block split from S1) and the L1 comparison.

Stages: fit (train, search on val blocks, variant + thresholds from val blocks; no test frame is scored),
        test (score the test blocks ONCE with the frozen models/thresholds, L1 regime A recomputed as in S2),
        ctrl (importance + shuffled-label control, validation only).
Usage: python -u -W ignore tools/WP2_S6_ch.py fit|test|ctrl
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
from can import l1 as L
from can import l1_exp as E
from can import l4_exp as X
from can import l4_features as G
from can.splits import block_index
from common.config import DATA_EXTRA, RESULTS
from common.metrics import budget_threshold
from WP2_S2_run import fit_profile, frame_summary
from WP2_S6_cache import load

RUN = DATA_EXTRA / "WP2_S6_cache" / "ch_run_m"
OUT = RESULTS / "WP2"
NAMES = ["DoS", "Fuzzy", "RPM", "Gear"]
KEEP = 0.25
N_ITER = 6
SEEDS = [11, 12, 13, 14, 15]
LUT = {"train": E.ROLE_FIT, "val": E.ROLE_VAL, "test": E.ROLE_TEST}


def setup():
    blocks = json.load(open(OUT / "splits_carhacking.json"))["blocks"]
    codes = E.AttCodes()
    D, roles, clean = {}, {}, {}
    for i, n in enumerate(NAMES):
        d = load("carhacking", n)
        bi = block_index(len(d["t"]))
        has = np.zeros(100, bool)
        has[np.unique(bi[d["label"] != 0])] = True
        roles[n] = np.array([LUT[p] for p in blocks[n]], np.int8)[bi]
        clean[n] = ~has[bi]
        D[n] = d
    return D, roles, clean, codes


def make_F(D, roles, clean, codes, i, n, windows=True):
    d = D[n]
    att = codes.map(d["att_names"], d["att_codes"])
    F = L.make_features(d["t"], d["id"], d["dlc"], d["label"], att, clean[n], group_code=i * 4 + roles[n].astype(np.int64),
                        windows=windows)
    F["role"] = roles[n]
    return F


def rows(D, roles, clean, role, period, cols, rng):
    Xs, ys = [], []
    for n in NAMES:
        m = (roles[n] == role) & X.sample_mask(D[n]["label"], KEEP, rng)
        Xs.append(X.matrix(D[n], period, cols, m))
        ys.append(D[n]["label"][m].astype(np.int8))
    return np.concatenate(Xs), np.concatenate(ys)


def stage_fit():
    t0 = time.time()
    RUN.mkdir(parents=True, exist_ok=True)
    D, roles, clean, codes = setup()
    period = X.period_of((D[n], (roles[n] == E.ROLE_FIT) & clean[n]) for n in NAMES)
    print(f"period ids {len(period)} ({time.time() - t0:.0f}s)", flush=True)
    info = {"keep_rate": KEEP, "n_ids_period": len(period)}
    models = {}
    for k, (nm, cols) in X.MODELS.items():
        Xtr, ytr = rows(D, roles, clean, E.ROLE_FIT, period, cols, np.random.default_rng(42))
        Xva, yva = rows(D, roles, clean, E.ROLE_VAL, period, cols, np.random.default_rng(43))
        print(f"{nm}: train rows {len(ytr)} (attack {int(ytr.sum())}), val rows {len(yva)} (attack {int(yva.sum())})", flush=True)
        m, s = X.search(Xtr, ytr, Xva, yva, N_ITER)
        m.save_model(str(RUN / f"{k}.json"))
        models[k] = m
        info[k] = {"rows_train": int(len(ytr)), "attack_train": int(ytr.sum()), "rows_val": int(len(yva)), "search": s,
                   "importance": X.importance(m, cols)}
        print(f"{nm} best {s['params']} trees {s['n_trees']} AP {s['val_ap']:.4f} ({time.time() - t0:.0f}s)", flush=True)
    # validation windows (role val only; features of other roles are not needed for val windows but are causal)
    tabs, fr_thr = [], {}
    vals = {k: [] for k in models}
    yv_l = []
    for i, n in enumerate(NAMES):
        F = make_F(D, roles, clean, codes, i, n)
        mv = roles[n] == E.ROLE_VAL
        sc = {}
        for k, (nm, cols) in X.MODELS.items():
            p = np.zeros(len(mv), np.float32)
            p[mv] = X.predict(models[k], X.matrix(D[n], period, cols, mv))
            sc[k] = p
            vals[k].append(p[mv & clean[n]])
        tb = X.window_rows(F, n, sc, {"role": ((F["wkeys"] // L.WIN_SPAN) % 4).astype(np.int8)})
        tabs.append(tb[tb["role"] == E.ROLE_VAL])
        print(f"  val scored {n} ({time.time() - t0:.0f}s)", flush=True)
    vt = pd.concat(tabs, ignore_index=True)
    sel = {k: X.select_variant(vt, k, codes) for k in models}
    for k in models:
        vi = sel[k]["chosen"]
        raw = vt[f"{k}{vi}"].to_numpy()
        info[k]["variant_selection"] = sel[k]
        info[k]["window_threshold"] = float(budget_threshold(raw[X.clean_mask(vt)], 0.01))
        info[k]["frame_threshold"] = float(budget_threshold(np.concatenate(vals[k]), 0.01))
        print(k, "variant", sel[k]["chosen"], G.VARIANTS[vi], "recall", round(sel[k]["variants"][str(vi)]["mean_recall"], 3),
              "win thr", info[k]["window_threshold"], "frame thr", info[k]["frame_threshold"], flush=True)
    info["codes"] = codes.names
    info["period"] = {str(a): b for a, b in period.items()}
    vt.to_pickle(RUN / "val_windows.pkl")
    json.dump(info, open(RUN / "fit_info.json", "w"), indent=1)
    print("fit done", f"({time.time() - t0:.0f}s)", flush=True)


def stage_test():
    """Single scoring of the test blocks. Refuses to run twice."""
    t0 = time.time()
    done = RUN / "test_done.flag"
    assert not done.exists(), "test already scored once"
    info = json.load(open(RUN / "fit_info.json"))
    D, roles, clean, codes = setup()
    codes.names = list(info["codes"])
    period = {int(a): b for a, b in info["period"].items()}
    models = {}
    for k in X.MODELS:
        models[k] = xgb.XGBClassifier()
        models[k].load_model(str(RUN / f"{k}.json"))
    # L1 regime A as in S2 (profile from train clean frames, variant from val windows, thresholds from clean val)
    fit_items = [(D[n], (roles[n] == E.ROLE_FIT) & clean[n]) for n in NAMES]
    for d, m in fit_items:                                   # fit_profile expects raw dicts with t/id/dlc
        pass
    profile = fit_profile(fit_items)
    store = E.Store()
    for i, n in enumerate(NAMES):
        F = make_F(D, roles, clean, codes, i, n)
        store.add(F, E.raw_frames(profile, F, range(len(L.VARIANTS))), E.ROLE_VAL)
    store.done()
    sel1 = E.select_variant(profile, store, codes)
    reg = {"A": E.build_regime("A", profile, store, sel1["chosen"], 0.01)}
    print("L1 variant", sel1["chosen"], f"({time.time() - t0:.0f}s)", flush=True)
    tallies, wrows = {"A": E.Tally(E.RULE_NAMES)}, {"A": []}
    tabs, frame_t = [], {k: {"inj": {}, "clean": [0, 0], "normal": [0, 0]} for k in models}
    for i, n in enumerate(NAMES):
        F = make_F(D, roles, clean, codes, i, n)
        E.score_file(reg, F, n, tallies, wrows, codes)
        mt = roles[n] == E.ROLE_TEST
        sc = {}
        for k, (nm, cols) in X.MODELS.items():
            p = np.zeros(len(mt), np.float32)
            p[mt] = X.predict(models[k], X.matrix(D[n], period, cols, mt))
            sc[k] = p
            fl = p[mt] >= info[k]["frame_threshold"]
            lab, att, cl = F["label"][mt], F["att"][mt], F["clean"][mt]
            ft = frame_t[k]
            for a in np.unique(att[lab == 1]):
                m = (lab == 1) & (att == a)
                v = ft["inj"].setdefault(codes.names[int(a)], [0, 0])
                v[0] += int(m.sum()); v[1] += int(fl[m].sum())
            nm_ = lab == 0
            ft["clean"][0] += int((nm_ & cl).sum()); ft["clean"][1] += int((fl & nm_ & cl).sum())
            ft["normal"][0] += int(nm_.sum()); ft["normal"][1] += int((fl & nm_).sum())
        tb = X.window_rows(F, n, sc, {"role": ((F["wkeys"] // L.WIN_SPAN) % 4).astype(np.int8), "wkey": F["wkeys"]})
        tabs.append(tb[tb["role"] == E.ROLE_TEST])
        print(f"  test scored {n} ({time.time() - t0:.0f}s)", flush=True)
    tt = pd.concat(tabs, ignore_index=True)
    l1 = E.window_table(wrows["A"])
    R = reg["A"]
    l1_al = np.zeros(len(l1), bool)
    for r in E.RULE_NAMES:
        l1_al |= R.wr[r].alarms(l1[f"raw_{r}"].to_numpy())
    l1 = l1.assign(l1_alarm=l1_al)
    tt = tt.merge(l1[["wkey", "l1_alarm"]], on="wkey", how="left")
    assert tt["l1_alarm"].notna().all()
    tt["l1_alarm"] = tt["l1_alarm"].astype(bool)
    tt.to_pickle(RUN / "test_windows.pkl")
    json.dump({"frame": {k: v for k, v in frame_t.items()}, "l1_variant": sel1, "l1_frame": frame_summary(tallies["A"].to_dict(), E.RULE_NAMES + ["combined"])},
              open(RUN / "test_frames.json", "w"), indent=1)
    done.write_text("scored once")
    print("test done", f"({time.time() - t0:.0f}s)", flush=True)


def stage_ctrl():
    t0 = time.time()
    info = json.load(open(RUN / "fit_info.json"))
    D, roles, clean, codes = setup()
    codes.names = list(info["codes"])
    period = {int(a): b for a, b in info["period"].items()}
    res = {}
    for k, (nm, cols) in X.MODELS.items():
        Xtr, ytr = rows(D, roles, clean, E.ROLE_FIT, period, cols, np.random.default_rng(42))
        Xva, yva = rows(D, roles, clean, E.ROLE_VAL, period, cols, np.random.default_rng(43))
        prm, nt = info[k]["search"]["params"], info[k]["search"]["n_trees"]
        vi = info[k]["variant_selection"]["chosen"]
        r = {"variant": vi, "frame_auc": [], "window_auc": []}
        for s in SEEDS:
            m = X.fit_fixed(Xtr, np.random.default_rng(s).permutation(ytr), prm, nt, seed=s)
            r["frame_auc"].append(X.frame_auc(yva, m.predict_proba(Xva)[:, 1]))
            tabs = []
            for i, n in enumerate(NAMES):
                F = make_F(D, roles, clean, codes, i, n)
                mv = roles[n] == E.ROLE_VAL
                p = np.zeros(len(mv), np.float32)
                p[mv] = X.predict(m, X.matrix(D[n], period, cols, mv))
                tb = X.window_rows(F, n, {k: p}, {"role": ((F["wkeys"] // L.WIN_SPAN) % 4).astype(np.int8)})
                tabs.append(tb[tb["role"] == E.ROLE_VAL])
            vtab = pd.concat(tabs, ignore_index=True)
            r["window_auc"].append(X.window_auc(vtab, k, vi))
            r["count_auc_reference"] = X.count_auc(vtab)
            print(f"{nm} seed {s}: frame AUC {r['frame_auc'][-1]:.4f} window AUC {r['window_auc'][-1]:.4f} ({time.time() - t0:.0f}s)", flush=True)
        r["mean_frame_auc"], r["mean_window_auc"] = float(np.mean(r["frame_auc"])), float(np.mean(r["window_auc"]))
        r["bound"] = 0.55
        r["pass"] = bool(r["mean_frame_auc"] <= 0.55 and r["mean_window_auc"] <= 0.55)
        res[nm] = r
    json.dump(res, open(OUT / "s6_ch_shuffle.json", "w"), indent=1)


if __name__ == "__main__":
    {"fit": stage_fit, "test": stage_test, "ctrl": stage_ctrl}[sys.argv[1]]()
