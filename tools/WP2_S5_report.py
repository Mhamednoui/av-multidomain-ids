"""WP2 S5: report tables for L3 (+ harness ablation with L1 and L2b relations-only).
Usage: python -u -W ignore tools/WP2_S5_report.py val <variant>   -> results/WP2/s5_val.json, s5_val_tables.md  (train/val attack captures; no test read)
       python -u -W ignore tools/WP2_S5_report.py test <variant>  -> results/WP2/s5_test.json, s5_test_tables.md (ROAD test, exposure 5, run ONCE)
Windows: 1 s by running-max time. All layers are compared on the same scored windows (grid exists and second >= 4: L2b relations-only keeps the S4 3 s mute).
Protocol: notes/WP2_can.md "S5 start".
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l2b_signals as Z
from can import l3_predictors as P
from common.calibration import ECDFCalibrator
from common.metrics import auc, budget_threshold
from WP2_S4_run import CAT, attack_names, sparse_load, test_names
from WP2_S5_eval import BUDGET, CACHE, LOCO, OUT, VARIANTS, calib, calib_d, l3_arrays, loco_pool, vname, win_table
from WP2_S5_run import load_grid

SKIP_SEC = 4
COMBOS = ["L1", "L2b", "L3c", "L3d", "L3", "L2b+L3", "L1+L2b", "L1+L2b+L3", "L1+L3"]
SHOW = ["L3c", "L3d", "L3", "L2b", "L1", "L1+L2b", "L1+L2b+L3"]


def l1_alarms():
    """L1 (S2 run-1 design, as in S4): five rules, window level, calibrated on clean validation windows at 1% each, OR (test captures only)."""
    fz = OUT / "s3_run1_frozen"
    val = pd.read_csv(fz / "s3_road_windows_val.csv.gz")
    test = pd.read_csv(fz / "s3_road_windows_test_A.csv.gz")
    cols = [c for c in test.columns if c.startswith("raw_can.l1_")]
    al = np.zeros(len(test), bool)
    clean_val = val["clean"].astype(bool) & (val["y"] == 0)
    for c in cols:
        cal = ECDFCalibrator().fit(val.loc[clean_val, c].to_numpy())
        thr = budget_threshold(cal.transform(val.loc[clean_val, c].to_numpy()), BUDGET)
        al |= cal.transform(test[c].to_numpy()) >= thr
    test = test.assign(l1_alarm=al, sec=(test["wkey"] % 10 ** 7).astype(int))
    return test[["group", "sec", "l1_alarm"]]


def l2b_calibration():
    """L2b relations-only thresholds from the same 6 LOCO folds (S4 models, S4 weights, mute 3 s)."""
    wins, frs = [], []
    for c in LOCO:
        comb = Z.combine(sparse_load(CACHE / "l2b_loco" / (c + ".npz")))
        W = win_table(c)
        wins.append(Z.window_max(comb, W["st"])[np.floor(W["tm"][W["st"]]) >= SKIP_SEC])
        frs.append(comb[W["tm"] > W["tm"][0] + 3.0])
    return calib(wins, frs)


def per_cap(W, al, valid):
    y = (W["y"] == 1) & valid
    cl = W["clean"] & ~(W["y"] == 1) & valid
    r = {"attack_windows": int(y.sum()), "clean_windows": int(cl.sum()), "false_alerts_clean": int(al[cl].sum()),
         "fa_clean_rate": float(al[cl].mean()) if cl.any() else None}
    if y.any():
        r["detected"] = bool(al[y].any())
        r["window_recall"] = float(al[y].mean())
        idx = np.flatnonzero(al & y)
        r["delay_s"] = float(max(W["w_end"][idx[0]] - W["fi"], 0.0)) if len(idx) else None
    return r


def top_signals(name, vi, topn=4):
    """Continuous signals that drive the L3c score in the attack grid steps (argmax signal per step, share of steps)."""
    own, rmin, agg = VARIANTS[vi]
    M = pickle.load(open(CACHE / "models" / "final.pkl", "rb"))[own]
    Gc, _, g0 = load_grid(name)
    sc, am = P.grid_scores(M, Gc, rmin, agg, return_argmax=True)
    W = win_table(name)
    g = g0 + P.GRID_DT * np.arange(len(sc))
    att = g >= W["fi"]
    if not att.any():
        return {}
    ids, cnt = np.unique(am[att], return_counts=True)
    o = np.argsort(-cnt)[:topn]
    return {f"{CAT.cont[ids[i]][0]:#x}.{CAT.cont[ids[i]][1]}": round(float(cnt[i] / att.sum()), 3) for i in o}


def z_profile(name, vi, topn=6):
    """Median standardised residual of the signals with the largest median z in the attack steps (no r_min filter): shows whether the related
    signals disagree with the overwritten one (cross-signal inconsistency) or the whole group moved together."""
    own = VARIANTS[vi][0]
    M = pickle.load(open(CACHE / "models" / "final.pkl", "rb"))[own]
    Gc, _, g0 = load_grid(name)
    z = P.z_matrix(M, Gc)
    W = win_table(name)
    att = (g0 + P.GRID_DT * np.arange(len(z))) >= W["fi"]
    if not att.any():
        return {}
    med = np.median(z[att], axis=0)
    o = np.argsort(-med)[:topn]
    return {f"{CAT.cont[j][0]:#x}.{CAT.cont[j][1]}": [round(float(med[j]), 1), round(float(M.r2[j]), 2)] for j in o}


def report(group, vi):
    key = vname(VARIANTS[vi])
    names = {"attack": attack_names(1) + attack_names(2), "test": test_names()}[group]
    tag = "s5_val" if group == "attack" else "s5_test"
    wsl, fsl, _ = loco_pool(key)
    wc, fc = calib(wsl, fsl)
    wsd, fsd, _ = loco_pool("d")
    wd, fd = calib_d(wsd, fsd)
    w2, f2 = l2b_calibration()
    l1 = l1_alarms() if group == "test" else None
    out = {"variant": vi, "variant_name": key, "group": group,
           "thresholds": {"l3c_window": wc.threshold, "l3c_frame": fc.threshold, "l3d_window": wd.threshold, "l3d_frame": fd.threshold,
                          "l2b_rel_window": w2.threshold, "l2b_rel_frame": f2.threshold},
           "loco_fa_per_fold": {c: {"l3c": float(wc.alarms(w).mean()), "l3d": float(wd.alarms(x).mean()), "windows": int(len(w))}
                                for c, w, x in zip(LOCO, wsl, wsd)}, "captures": {}}
    allw = []
    for c in names:
        Wt, wsc, ok, fsc = l3_arrays(c, group, key)
        _, wsd_, _, fsd_ = l3_arrays(c, group, "d")
        valid = ok & (np.floor(Wt["tm"][Wt["st"]]) >= SKIP_SEC)
        a3c, a3d = wc.alarms(wsc), wd.alarms(wsd_)
        a2 = w2.alarms(Z.window_max(Z.combine(sparse_load(CACHE / ("l2b_" + group) / (c + ".npz"))), Wt["st"]))
        if l1 is not None:
            df = pd.DataFrame({"group": c, "sec": np.floor(Wt["tm"][Wt["st"]]).astype(int)}).merge(l1, on=["group", "sec"], how="left")
            a1 = df["l1_alarm"].fillna(False).to_numpy(bool)
        else:
            a1 = np.zeros(len(a2), bool)
        A = {"L1": a1, "L2b": a2, "L3c": a3c, "L3d": a3d, "L3": a3c | a3d, "L2b+L3": a2 | a3c | a3d, "L1+L2b": a1 | a2,
             "L1+L2b+L3": a1 | a2 | a3c | a3d, "L1+L3": a1 | a3c | a3d}
        r = {k: per_cap(Wt, A[k], valid) for k in COMBOS}
        gi = P.grid_index(Wt["tm"], float(np.load(CACHE / ("scores_" + group) / (c + ".npz"))["t0"]), 10 ** 9)
        late = (gi >= 0) & (Wt["tm"] > Wt["tm"][0] + 3.0)
        fa3 = (fc.alarms(fsc) | fd.alarms(fsd_))[late]
        yl = Wt["label"][late] > 0
        cl = Wt["clean_fr"][late] & ~yl
        r["frame_L3"] = {"recall_1pct_each": float(fa3[yl].mean()) if yl.any() else None, "fa_clean": float(fa3[cl].mean()) if cl.any() else None}
        r["top_signals_in_attack_steps"] = top_signals(c, vi) if Wt["y"].max() else {}
        r["median_z_top_signals_[z, r2]"] = z_profile(c, vi) if Wt["y"].max() else {}
        r["windows_scored"] = int(valid.sum())
        out["captures"][c] = r
        allw.append((c, Wt, A, valid, wsc, wsd_))

    def agg(sel):
        res = {}
        for k in COMBOS:
            fa = n = 0
            for c, Wt, A, valid, _, _ in allw:
                if sel(c):
                    m = Wt["clean"] & ~(Wt["y"] == 1) & valid
                    fa += int(A[k][m].sum())
                    n += int(m.sum())
            res[k] = fa / n if n else None
            res["n"] = n
        return res

    out["clean_window_fa_all"] = agg(lambda c: True)
    out["clean_window_fa_ambient_only"] = agg(lambda c: c.startswith("ambient"))
    out["clean_window_fa_leads_only"] = agg(lambda c: not c.startswith("ambient"))
    y_all = np.concatenate([(Wt["y"] == 1)[valid] for _, Wt, _, valid, _, _ in allw])
    c_all = np.concatenate([(Wt["clean"] | (Wt["y"] == 1))[valid] for _, Wt, _, valid, _, _ in allw])
    s_all = np.concatenate([np.maximum(wc.calibrated(a), wd.calibrated(b))[valid] for _, _, _, valid, a, b in allw])
    out["auc_window_l3_all"] = float(auc(y_all[c_all].astype(int), s_all[c_all]))
    masq = [c for c in names if "masquerade" in c]
    out["masquerade_detected"] = {k: {c: out["captures"][c][k].get("detected") for c in masq} for k in COMBOS}
    json.dump(out, open(OUT / f"{tag}.json", "w"), indent=1)
    f = lambda x: "-" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))
    lines = ["| capture | " + " | ".join(f"{k} det / delay / FA" for k in SHOW) + " | frame recall L3 | top signals |", "|---|" + "---|" * 9]
    for c, r in out["captures"].items():
        cells = [f"{f(r[k].get('detected'))} / {f(r[k].get('delay_s'))} / {f(r[k]['fa_clean_rate'])}" for k in SHOW]
        lines.append(f"| {c} | " + " | ".join(cells) + f" | {f(r['frame_L3']['recall_1pct_each'])} | {r['top_signals_in_attack_steps']} |")
    lines.append(f"\nClean-window FA (all / ambient only / leads only): {out['clean_window_fa_all']} | {out['clean_window_fa_ambient_only']} | {out['clean_window_fa_leads_only']}")
    lines.append(f"AUC (window, L3): {out['auc_window_l3_all']:.3f}")
    open(OUT / f"{tag}_tables.md", "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    report("attack" if sys.argv[1] == "val" else "test", int(sys.argv[2]))
