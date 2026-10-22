"""WP2 S6: L4 timing + payload models on can-train-and-test (D11), one experiment per set (set_01..set_04).

Stages: fit <set>  train on the set's train files, search on its val hold-out files, variant + regime-A thresholds from val,
                   importance, shuffled-label control (5 seeds), dt==0 check. NO test file is read.
        test <set> score the four test subsets ONCE (regime A zero-shot; regime B on-vehicle: periods from the first 30 s,
                   thresholds from clean windows of 30-60 s, scored from t >= 60 s, as S2), with L1 recomputed as in S2.
Payload bytes come from the CSV (data_field); everything else from the S2 cache. Files are processed one at a time.
Usage: python -u -W ignore tools/WP2_S6_d11.py fit|test set_01 [set_02 ...]
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
from can.frames import hex_to_bytes
from common.config import DATA_EXTRA, RESULTS
from common.metrics import budget_threshold
from WP2_S2_run import fit_profile, D11_PROFILE_S, D11_CAL_S, D11_SKIP_S, MIN_ELIGIBLE

RUN = DATA_EXTRA / "WP2_S6_cache" / "d11_run"
OUT = RESULTS / "WP2"
KEEP = 0.10
ATT_CAP = 200_000          # injected frames kept per training / validation file (deterministic random subsample)
N_ITER = 4
SEEDS = [11, 12, 13, 14, 15]
PATHS = None


def cname(c):
    return c.replace("/", "__")


def paths():
    global PATHS
    if PATHS is None:
        PATHS = {r["capture"]: r["path"] for _, r in A.d11_file_table().iterrows()}
    return PATHS


def prep(c, n_rows=None) -> dict:
    """Cache arrays + payload bytes + raw L4 features of one D11 file (optionally only the first n_rows frames)."""
    d = E.load_cached("d11", cname(c))
    if n_rows is not None:
        d = {k: (v[:n_rows] if k in ("t", "id", "dlc", "label", "att_codes") else v) for k, v in d.items()}
    raw = pd.read_csv(paths()[c], usecols=["data_field"], dtype=str, keep_default_na=False, nrows=n_rows)["data_field"]
    dlc, B = hex_to_bytes(raw)
    assert len(B) == len(d["t"]) and (dlc == d["dlc"]).all(), c
    d["B"] = B
    d.update(G.stream_raw(d["t"], d["id"], d["dlc"], B))
    return d


def sample_rows(label, rng):
    keep = rng.random(len(label)) < KEEP
    inj = np.flatnonzero(label)
    if len(inj) > ATT_CAP:
        keep[inj] = False
        keep[rng.choice(inj, ATT_CAP, replace=False)] = True
    else:
        keep[inj] = True
    return keep


def take(d, m):
    return {k: d[k][m] for k in ("id", "dlc", "B", "dt_prev", "dt_id", "n_id", "n_uniq", "bchg", "label")}


def concat_slices(sl):
    return {k: np.concatenate([s[k] for s in sl]) for k in sl[0]}


def mat(sl, period, cols):
    return G.feature_matrix({k: sl[k] for k in ("dt_prev", "dt_id", "n_id", "n_uniq", "bchg")}, sl["id"], sl["dlc"], sl["B"], period, cols)


def role_const(n, r):
    return np.full(n, r, np.int8)


def window_extra(F):
    return {"role": ((F["wkeys"] // L.WIN_SPAN) % 4).astype(np.int8), "wkey": F["wkeys"]}


def load_splits():
    return json.load(open(OUT / "splits_d11.json"))["splits"]


# ------------------------------------------------------------------ fit
def stage_fit(set_name):
    t0 = time.time()
    outp = RUN / f"fit_{set_name}.json"
    if outp.exists():
        print("skip", set_name)
        return
    RUN.mkdir(parents=True, exist_ok=True)
    sp = load_splits()[set_name]
    codes = E.AttCodes()
    all_caps = sorted({c for k, v in sp.items() if k != "excluded_duplicates" for c in v})
    base_of = {c: i for i, c in enumerate(all_caps)}
    # --- train rows + period
    pb, rng, trs, zero_stats = G.PeriodBuilder(), np.random.default_rng(42), [], [0, 0, 0, 0]
    for c in sp["train"]:
        d = prep(c)
        cl = E.lead_clean(d["t"], d["label"])
        pb.add(d["id"][cl], d["dt_id"][cl])
        m = sample_rows(d["label"], rng)
        trs.append(take(d, m))
        z = d["dt_prev"] == 0
        zero_stats[0] += int(((d["label"] == 0) & z).sum()); zero_stats[1] += int((d["label"] == 0).sum())
        zero_stats[2] += int(((d["label"] == 1) & z).sum()); zero_stats[3] += int((d["label"] == 1).sum())
        del d
    period = pb.finish()
    tr = concat_slices(trs)
    del trs
    print(f"{set_name} train rows {len(tr['label'])} attack {int(tr['label'].sum())} period ids {len(period)} ({time.time() - t0:.0f}s)", flush=True)
    # --- validation files kept in memory (matrices + window structure)
    rng = np.random.default_rng(43)
    vals, val_rows = [], []
    for c in sp["val"]:
        d = prep(c)
        cl = E.lead_clean(d["t"], d["label"])
        F = E.make_F(d, codes, base_of[c], role_const(len(d["t"]), E.ROLE_VAL), cl)
        m = sample_rows(d["label"], rng)
        val_rows.append(take(d, m))
        vals.append({"c": c, "F": F, "X": mat(take(d, slice(None)), period, G.FEATURES), "inj": E.first_injected(d)})
        del d
    vr = concat_slices(val_rows)
    print(f"{set_name} val files {len(vals)} val rows {len(vr['label'])} attack {int(vr['label'].sum())} ({time.time() - t0:.0f}s)", flush=True)
    info = {"set": set_name, "keep_rate": KEEP, "att_cap": ATT_CAP, "n_ids_period": len(period),
            "dt_prev_zero": {"clean_zero": zero_stats[0], "clean_n": zero_stats[1], "inj_zero": zero_stats[2], "inj_n": zero_stats[3]}}
    cols_idx = {k: [G.FEATURES.index(c) for c in cols] for k, (_, cols) in X.MODELS.items()}
    models = {}
    for k, (nm, cols) in X.MODELS.items():
        Xtr, ytr = mat(tr, period, cols), tr["label"].astype(np.int8)
        Xva, yva = mat(vr, period, cols), vr["label"].astype(np.int8)
        m, s = X.search(Xtr, ytr, Xva, yva, N_ITER)
        m.save_model(str(RUN / f"{set_name}_{k}.json"))
        models[k] = m
        info[k] = {"rows_train": int(len(ytr)), "attack_train": int(ytr.sum()), "rows_val": int(len(yva)), "search": s,
                   "importance": X.importance(m, cols)}
        print(f"{nm} best {s['params']} trees {s['n_trees']} AP {s['val_ap']:.4f} ({time.time() - t0:.0f}s)", flush=True)

    def val_table(mods):
        tabs, fr = [], {k: [] for k in mods}
        for v in vals:
            sc = {k: X.predict(mods[k], v["X"][:, cols_idx[k]]) for k in mods}
            tabs.append(X.window_rows(v["F"], v["c"], sc, window_extra(v["F"])))
            for k in mods:
                fr[k].append(sc[k][v["F"]["clean"]])
        return pd.concat(tabs, ignore_index=True), {k: np.concatenate(a) for k, a in fr.items()}

    vt, vfr = val_table(models)
    sel = {k: X.select_variant(vt, k, codes) for k in models}
    for k in models:
        vi = sel[k]["chosen"]
        info[k]["variant_selection"] = sel[k]
        info[k]["window_threshold"] = float(budget_threshold(vt[f"{k}{vi}"].to_numpy()[X.clean_mask(vt)], 0.01))
        info[k]["frame_threshold"] = float(budget_threshold(vfr[k], 0.01))
        info[k]["val_window_auc"] = X.window_auc(vt, k, vi)
        print(k, "variant", vi, G.VARIANTS[vi], "recall", round(sel[k]["variants"][str(vi)]["mean_recall"], 3), flush=True)
    vt.to_pickle(RUN / f"valwin_{set_name}.pkl")
    # --- shuffled-label control
    ctrl = {}
    for k, (nm, cols) in X.MODELS.items():
        Xtr, ytr = mat(tr, period, cols), tr["label"].astype(np.int8)
        Xva, yva = mat(vr, period, cols), vr["label"].astype(np.int8)
        prm, nt = info[k]["search"]["params"], info[k]["search"]["n_trees"]
        vi = info[k]["variant_selection"]["chosen"]
        r = {"frame_auc": [], "window_auc": []}
        for s in SEEDS:
            ms = X.fit_fixed(Xtr, np.random.default_rng(s).permutation(ytr), prm, nt, seed=s)
            r["frame_auc"].append(X.frame_auc(yva, ms.predict_proba(Xva)[:, 1]))
            tb, _ = val_table({k: ms})
            r["window_auc"].append(X.window_auc(tb, k, vi))
            print(f"  shuffle {nm} seed {s}: frame AUC {r['frame_auc'][-1]:.4f} window AUC {r['window_auc'][-1]:.4f} ({time.time() - t0:.0f}s)", flush=True)
        r["mean_frame_auc"], r["mean_window_auc"] = float(np.mean(r["frame_auc"])), float(np.mean(r["window_auc"]))
        r["count_auc_reference"] = X.count_auc(vt)
        r["pass"] = bool(r["mean_frame_auc"] <= 0.55 and r["mean_window_auc"] <= 0.55)
        ctrl[nm] = r
    info["shuffle"] = ctrl
    # --- dt == 0 ablation (timing model, same params and trees), descriptive
    if set_name == "set_01":
        cols = X.MODELS["t"][1]
        def nozero(M):
            M = M.copy()
            for cn in ("dt_prev", "dt_id", "dt_id_ratio"):
                j = cols.index(cn)
                M[M[:, j] == 0, j] = np.nan
            return M
        Xtr, ytr = nozero(mat(tr, period, cols)), tr["label"].astype(np.int8)
        Xva, yva = nozero(mat(vr, period, cols)), vr["label"].astype(np.int8)
        ma = X.fit_fixed(Xtr, ytr, info["t"]["search"]["params"], info["t"]["search"]["n_trees"])
        from sklearn.metrics import average_precision_score
        ap0 = float(average_precision_score(yva, ma.predict_proba(Xva)[:, 1]))
        info["dt_zero_ablation"] = {"val_ap_with_zero_dt": info["t"]["search"]["val_ap"], "val_ap_zero_dt_set_nan": ap0}
        print("dt==0 ablation", info["dt_zero_ablation"], flush=True)
    info["codes"] = codes.names
    info["period"] = {str(a): b for a, b in period.items()}
    json.dump(info, open(outp, "w"), indent=1)
    print("fit done", set_name, f"({time.time() - t0:.0f}s)", flush=True)


# ------------------------------------------------------------------ test
def frame_tally(ft, F, mt, p, thr, codes):
    fl = p[mt] >= thr
    lab, att, cl = F["label"][mt], F["att"][mt], F["clean"][mt]
    for a in np.unique(att[lab == 1]):
        m = (lab == 1) & (att == a)
        v = ft["inj"].setdefault(codes.names[int(a)], [0, 0])
        v[0] += int(m.sum()); v[1] += int(fl[m].sum())
    nm = lab == 0
    ft["clean"][0] += int((nm & cl).sum()); ft["clean"][1] += int((fl & nm & cl).sum())
    ft["normal"][0] += int(nm.sum()); ft["normal"][1] += int((fl & nm).sum())


def stage_test(set_name):
    t0 = time.time()
    outp = OUT / f"s6_d11_{set_name}.json"
    flag = RUN / f"test_done_{set_name}.flag"
    assert not flag.exists(), "test already scored once"
    sp = load_splits()[set_name]
    info = json.load(open(RUN / f"fit_{set_name}.json"))
    codes = E.AttCodes()
    codes.names = list(info["codes"])
    all_caps = sorted({c for k, v in sp.items() if k != "excluded_duplicates" for c in v})
    base_of = {c: i for i, c in enumerate(all_caps)}
    periodA = {int(a): b for a, b in info["period"].items()}
    models = {}
    for k in X.MODELS:
        models[k] = xgb.XGBClassifier()
        models[k].load_model(str(RUN / f"{set_name}_{k}.json"))
    cols_idx = {k: [G.FEATURES.index(c) for c in cols] for k, (_, cols) in X.MODELS.items()}
    # --- L1 regime A exactly as S2 (cache only)
    fit_items = []
    for c in sp["train"]:
        raw = E.load_cached("d11", cname(c))
        fit_items.append((raw, E.lead_clean(raw["t"], raw["label"])))
    profA = fit_profile(fit_items)
    del fit_items
    store = E.Store()
    for c in sp["val"]:
        raw = E.load_cached("d11", cname(c))
        F = E.make_F(raw, codes, base_of[c], role_const(len(raw["t"]), E.ROLE_VAL), E.lead_clean(raw["t"], raw["label"]))
        store.add(F, E.raw_frames(profA, F, range(len(L.VARIANTS))), E.ROLE_VAL)
    store.done()
    sel1 = E.select_variant(profA, store, codes)
    k1 = sel1["chosen"]
    regA = E.build_regime("A", profA, store, k1, 0.01)
    print(f"{set_name} L1 variant {k1} ({time.time() - t0:.0f}s)", flush=True)
    res = {"set": set_name, "l1_variant": sel1, "subsets": {}}
    vehicles = json.load(open(OUT / "s1_d11_vehicles.json"))
    for sub in ("test_01", "test_02", "test_03", "test_04"):
        files = sp[sub]
        elig = []
        for c in files:
            raw = E.load_cached("d11", cname(c))
            fi = E.first_injected(raw)
            if fi is None or fi >= D11_SKIP_S:
                elig.append(c)
        l1reg = {"A": regA}
        l4 = {"A": {"period": periodA, **{k: {"win_thr": info[k]["window_threshold"], "frame_thr": info[k]["frame_threshold"]} for k in models}}}
        sinfo = {"vehicle": sorted({vehicles[c]["vehicle"] for c in files}), "n_files": len(files), "n_eligible": len(elig)}
        if len(elig) >= MIN_ELIGIBLE:
            items, pbB = [], G.PeriodBuilder()
            cal = {k: [] for k in models}
            cal_fr = {k: [] for k in models}
            for c in elig:
                raw = E.load_cached("d11", cname(c))
                tm = np.maximum.accumulate(raw["t"])
                items.append((raw, E.lead_clean(raw["t"], raw["label"]) & (tm < D11_PROFILE_S)))
            profB = fit_profile(items)
            del items
            stB = E.Store()
            pre = {}
            for c in elig:
                raw = E.load_cached("d11", cname(c))
                tm = np.maximum.accumulate(raw["t"])
                r = np.full(len(tm), E.ROLE_NONE, np.int8)
                r[(tm >= D11_PROFILE_S) & (tm < D11_CAL_S)] = E.ROLE_VAL
                F = E.make_F(raw, codes, base_of[c], r, E.lead_clean(raw["t"], raw["label"]))
                stB.add(F, E.raw_frames(profB, F, [k1]), E.ROLE_VAL)
                # L4 on the first 60 s only (features are causal: the prefix gives identical values)
                n60 = int(np.searchsorted(tm, D11_CAL_S, side="left"))
                d = prep(c, n60)
                cl = E.lead_clean(d["t"], d["label"])
                tmp = np.maximum.accumulate(d["t"])
                pbB.add(d["id"][cl & (tmp < D11_PROFILE_S)], d["dt_id"][cl & (tmp < D11_PROFILE_S)])
                pre[c] = d
            stB.done()
            regB = E.build_regime("B", profB, stB, k1, 0.01)
            periodB = pbB.finish()
            for c, d in pre.items():
                tmp = np.maximum.accumulate(d["t"])
                r = np.full(len(tmp), E.ROLE_NONE, np.int8)
                r[(tmp >= D11_PROFILE_S) & (tmp < D11_CAL_S)] = E.ROLE_VAL
                F = E.make_F(d, codes, base_of[c], r, E.lead_clean(d["t"], d["label"]))
                XB = mat(take(d, slice(None)), periodB, G.FEATURES)
                sc = {k: X.predict(models[k], XB[:, cols_idx[k]]) for k in models}
                tb = X.window_rows(F, c, sc, window_extra(F))
                tb = tb[tb["role"] == E.ROLE_VAL]
                for k in models:
                    cal[k].append(tb)
                    cal_fr[k].append(sc[k][(r == E.ROLE_VAL) & F["clean"]])
            del pre
            l4["B"] = {"period": periodB}
            ct = pd.concat(cal["t"], ignore_index=True)
            for k in models:
                vi = info[k]["variant_selection"]["chosen"]
                l4["B"][k] = {"win_thr": float(budget_threshold(ct[f"{k}{vi}"].to_numpy()[X.clean_mask(ct)], 0.01)),
                              "frame_thr": float(budget_threshold(np.concatenate(cal_fr[k]), 0.01))}
            l1reg["B"] = regB
            sinfo["cal_B"] = {"clean_windows": int(X.clean_mask(ct).sum()), "frames": int(sum(len(a) for a in cal_fr["t"])),
                              "n_ids_period": len(periodB)}
            print(f"{set_name} {sub} B calibrated: {sinfo['cal_B']} ({time.time() - t0:.0f}s)", flush=True)
        tallies = {rn: E.Tally(E.RULE_NAMES) for rn in l1reg}
        wrows = {rn: [] for rn in l1reg}
        ft = {rn: {k: {"inj": {}, "clean": [0, 0], "normal": [0, 0]} for k in models} for rn in l1reg}
        l4tabs = {rn: [] for rn in l1reg}
        elig_set = set(elig)
        for c in files:
            d = prep(c)
            tm = np.maximum.accumulate(d["t"])
            r = np.full(len(tm), E.ROLE_TEST, np.int8)
            if c in elig_set:
                r[tm < D11_SKIP_S] = E.ROLE_NONE
            F = E.make_F(d, codes, base_of[c], r, E.lead_clean(d["t"], d["label"]))
            E.score_file(l1reg, F, c, tallies, wrows, codes)
            mt = r == E.ROLE_TEST
            sl = take(d, slice(None))
            del d
            for rn in l1reg:
                Xm = mat(sl, l4[rn]["period"], G.FEATURES)
                sc = {}
                for k in models:
                    p = np.zeros(len(mt), np.float32)
                    p[mt] = X.predict(models[k], Xm[mt][:, cols_idx[k]])
                    sc[k] = p
                    frame_tally(ft[rn][k], F, mt, p, l4[rn][k]["frame_thr"], codes)
                tb = X.window_rows(F, c, sc, window_extra(F))
                l4tabs[rn].append(tb[tb["role"] == E.ROLE_TEST])
                del Xm
            print(f"  {c} ({time.time() - t0:.0f}s)", flush=True)
        sinfo["regimes"] = {}
        for rn in l1reg:
            R = l1reg[rn]
            l1 = E.window_table(wrows[rn])
            al = np.zeros(len(l1), bool)
            for rule in E.RULE_NAMES:
                al |= R.wr[rule].alarms(l1[f"raw_{rule}"].to_numpy())
            l1 = l1.assign(l1_alarm=al)
            tt = pd.concat(l4tabs[rn], ignore_index=True).merge(l1[["wkey", "l1_alarm"]], on="wkey", how="left")
            assert tt["l1_alarm"].notna().all()
            tt["l1_alarm"] = tt["l1_alarm"].astype(bool)
            tt.to_pickle(RUN / f"testwin_{set_name}_{sub}_{rn}.pkl")
            sinfo["regimes"][rn] = {"thresholds": {k: l4[rn][k] for k in models}, "frame": ft[rn],
                                    "first_inj": {g: f["first_inj_t"] for g, f in tallies[rn].files.items()}}
        res["subsets"][sub] = sinfo
    res["attack_names"] = codes.names
    json.dump(res, open(outp, "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    flag.write_text("scored once")
    print("test done", set_name, f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    stage = {"fit": stage_fit, "test": stage_test}[sys.argv[1]]
    for s in sys.argv[2:]:
        stage(s)
