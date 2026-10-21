"""WP2 S4: calibration (LOCO), variant selection (validation) and the single test report for L2b.
Usage: python -u -W ignore tools/WP2_S4_eval.py select          -> results/WP2/s4_select.json (train/val only)
       python -u -W ignore tools/WP2_S4_eval.py report <variant> -> results/WP2/s4_test.json, s4_tables.md (test; run once)
Protocol: notes/WP2_can.md "S4 start". Windows are 1 s by running-max time; window label = >= 1 injected frame; clean window =
all frames attack-free (ambient captures, or lead of attack captures minus 1 s).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l1_exp as E
from can import l2b_signals as Z
from common.calibration import ECDFCalibrator
from common.config import DATA_EXTRA, RESULTS
from common.metrics import auc, budget_threshold
from WP2_S4_run import CACHE, H, LOCO, attack_names, sparse_load, test_names

OUT = RESULTS / "WP2"
BUDGET = 0.01
SUF = os.environ.get("S4_SUFFIX", "_m")
TAG = "" if SUF == "_m" else SUF
Z.MUTE_T0 = 3.0
SKIP_W = 4          # windows 0..3 (first 3 s + the partial window) belong to the in-situ baseline


def loco_pool(h):
    raws = [sparse_load(CACHE / ("loco" + SUF) / f"h{h}__{c}.npz") for c in LOCO]
    comb = [Z.combine(r) for r in raws]
    wins = []
    for i, (c, cb) in enumerate(zip(LOCO, comb)):
        tm = np.maximum.accumulate(np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (c + ".npz"))["t"])
        wins.append(Z.window_max(cb, Z.window_starts(tm))[SKIP_W:])
        comb[i] = cb[tm > tm[0] + Z.MUTE_T0]                 # frames inside the in-situ baseline period are not scored
    frl = Z.SignalPhysicsLayer("frame").calibrate_from_raw(np.concatenate(comb), BUDGET)
    wl = Z.SignalPhysicsLayer("window").calibrate_from_raw(np.concatenate(wins), BUDGET)
    per_fold = {c: {"window_fa_at_pool_thr": float(wl.alarms(w).mean()), "windows": int(len(w)),
                    "frame_fa_at_pool_thr": float(frl.alarms(cb).mean())} for c, w, cb in zip(LOCO, wins, comb)}
    return frl, wl, per_fold


def capture_windows(name, raws):
    """Window table of one capture (weighted check scores)."""
    z = np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (name + ".npz"))
    t, label = z["t"], z["label"]
    tm = np.maximum.accumulate(t)
    clean = E.lead_clean(t, label)
    st = Z.window_starts(tm)
    comb = Z.combine(raws)
    d = {"w_end": np.maximum.reduceat(tm, st), "sec": np.floor(tm[st]).astype(int),
         "y": np.maximum.reduceat(label, st).astype(int), "clean": np.minimum.reduceat(clean.astype(np.int8), st).astype(bool),
         "score": Z.window_max(comb, st)}
    for k in Z.TYPES:
        d["raw_" + k] = Z.window_max(raws[k].astype(np.float64), st)
    ok = d["sec"] >= SKIP_W
    d["clean"], d["y"] = d["clean"] & ok, d["y"] * ok
    return d, comb, label, E.first_injected({"t": t, "label": label})


def select():
    res = {"variants": {}}
    for h in range(len(H)):
        frl, wl, per_fold = loco_pool(h)
        rec = {}
        for c in attack_names(1) + attack_names(2):
            if "masquerade" not in c:
                continue
            w, _, _, _ = capture_windows(c, sparse_load(CACHE / ("attack" + SUF) / f"h{h}__{c}.npz"))
            al = wl.alarms(w["score"])
            y = w["y"] == 1
            rec[c] = {"window_recall": float(al[y].mean()), "fa_clean_windows": float(al[w["clean"] & ~y].mean())}
        res["variants"][str(h)] = {"rho_ms": H[h], "mean_masq_recall": float(np.mean([v["window_recall"] for v in rec.values()])),
                                   "window_threshold": wl.threshold, "frame_threshold": frl.threshold,
                                   "loco_per_capture": per_fold, "attack_val": rec}
        print(h, H[h], res["variants"][str(h)]["mean_masq_recall"], flush=True)
    best = max(res["variants"], key=lambda k: (res["variants"][k]["mean_masq_recall"], -int(k)))
    res["chosen"] = int(best)
    json.dump(res, open(OUT / f"s4_select{SUF if SUF != '_m' else ''}.json", "w"), indent=1)
    print("chosen", best)


def l1_alarms():
    """L1 (S2 run 1 design): five rules, window level, calibrated on clean validation windows at 1% each, OR.
    Windows from results/WP2/s3_run1_frozen/*.csv.gz (stored raw L1 scores); joined to L2b windows on (group, second)."""
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


def per_capture(name, w, alarm, first_inj):
    y = w["y"] == 1
    clean = w["clean"] & ~y
    r = {"attack_windows": int(y.sum()), "clean_windows": int(clean.sum()),
         "false_alerts_clean": int(alarm[clean].sum()), "fa_clean_rate": float(alarm[clean].mean()) if clean.any() else None}
    if y.any():
        r["detected"] = bool(alarm[y].any())
        r["window_recall"] = float(alarm[y].mean())
        idx = np.flatnonzero(alarm & y)
        r["delay_s"] = float(max(w["w_end"][idx[0]] - first_inj, 0.0)) if len(idx) else None
    return r


def report(h):
    frl, wl, per_fold = loco_pool(h)
    l1 = l1_alarms()
    out = {"variant": h, "rho_ms": H[h], "loco": per_fold, "window_threshold": wl.threshold, "frame_threshold": frl.threshold,
           "captures": {}}
    allw = []
    for c in test_names():
        raws = sparse_load(CACHE / ("test" + SUF) / f"h{h}__{c}.npz")
        w, comb, label, fi = capture_windows(c, raws)
        a2 = wl.alarms(w["score"])
        df = pd.DataFrame({"group": c, "sec": w["sec"]}).merge(l1, on=["group", "sec"], how="left")
        a1 = df["l1_alarm"].fillna(False).to_numpy(bool)
        r = {"l2b": per_capture(c, w, a2, fi), "l1": per_capture(c, w, a1, fi), "l1_or_l2b": per_capture(c, w, a1 | a2, fi),
             "l1_matched_windows": int(df["l1_alarm"].notna().sum()), "windows": int(len(a2))}
        y = w["y"] == 1
        if y.any():
            dom = {k: float((w["raw_" + k][y & a2] >= w["score"][y & a2] - 1e-9).mean()) if (y & a2).any() else None for k in Z.TYPES}
            r["dominant_type_share_in_alarmed_attack_windows"] = dom
        late = np.maximum.accumulate(np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (c + ".npz"))["t"]) > Z.MUTE_T0
        comb, label = comb[late], label[late]
        fa = frl.alarms(comb)
        yl = label > 0
        r["frame_recall_1pct"] = float(fa[yl].mean()) if yl.any() else None
        r["frame_fa_clean"] = float(fa[E.lead_clean(np.load(DATA_EXTRA / "WP2_S2_cache" / "road" / (c + ".npz"))["t"][late], label)].mean())
        out["captures"][c] = r
        allw.append((c, w, a1, a2))
    # aggregated clean-window FA and AUC on the test split
    def agg(sel):
        fa = {"l1": 0, "l2b": 0, "l1_or_l2b": 0, "n": 0}
        for c, w, a1, a2 in allw:
            m = w["clean"] & ~(w["y"] == 1)
            fa["n"] += int(m.sum())
            fa["l1"] += int(a1[m].sum())
            fa["l2b"] += int(a2[m].sum())
            fa["l1_or_l2b"] += int((a1 | a2)[m].sum())
        return {k: (v / fa["n"] if k != "n" else v) for k, v in fa.items()}
    out["clean_window_fa_test"] = agg(None)
    y_all = np.concatenate([w["y"] for _, w, _, _ in allw])
    c_all = np.concatenate([w["clean"] | (w["y"] == 1) for _, w, _, _ in allw])
    s_all = np.concatenate([w["score"] for _, w, _, _ in allw])
    out["auc_window_l2b_all_test"] = float(auc(y_all[c_all], s_all[c_all]))
    masq = [c for c in test_names() if "masquerade" in c]
    out["masquerade_detected"] = {c: out["captures"][c]["l2b"]["detected"] for c in masq}
    json.dump(out, open(OUT / f"s4_test{TAG}.json", "w"), indent=1)
    lines = ["| capture | L2b detected | recall | delay s | FA clean | L1 detected | L1 delay | L1+L2b detected | L1+L2b delay | L1+L2b FA | frame recall 1% |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    f = lambda v: "-" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
    for c, r in out["captures"].items():
        a, b, o = r["l2b"], r["l1"], r["l1_or_l2b"]
        lines.append(f"| {c} | {f(a.get('detected'))} | {f(a.get('window_recall'))} | {f(a.get('delay_s'))} | {f(a['fa_clean_rate'])} | "
                     f"{f(b.get('detected'))} | {f(b.get('delay_s'))} | {f(o.get('detected'))} | {f(o.get('delay_s'))} | {f(o['fa_clean_rate'])} | {f(r['frame_recall_1pct'])} |")
    lines.append(f"\nClean-window FA over the test split: {out['clean_window_fa_test']}")
    lines.append(f"AUC (window, all test): {out['auc_window_l2b_all_test']:.3f}")
    open(OUT / f"s4_tables{TAG}.md", "w").write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select()
    else:
        report(int(sys.argv[2]))
