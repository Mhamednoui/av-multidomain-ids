"""WP2 S5: calibration (LOCO), variant selection (train/val only) and the single test report for L3 (and the harness ablation).
Usage: python -u -W ignore tools/WP2_S5_eval.py select   -> results/WP2/s5_select.json  (no test capture is read)
       python -u -W ignore tools/WP2_S5_eval.py report <variant index> -> results/WP2/s5_test.json, s5_tables.md (test; run ONCE)
Windows: 1 s by running-max time; window label = >= 1 injected frame; clean window = all frames attack-free (ambient captures or lead of attack captures minus 1 s).
Protocol: notes/WP2_can.md "S5 start".
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l1_exp as E
from can import l2b_signals as Z
from can import l3_predictors as P
from common.calibration import ECDFCalibrator
from common.config import DATA_EXTRA, RESULTS
from common.metrics import auc, budget_threshold
from WP2_S4_run import attack_names, sparse_load, test_names
from WP2_S5_run import CACHE, LOCO, VARIANTS, vname

OUT = RESULTS / "WP2"
BUDGET = 0.01
S2 = DATA_EXTRA / "WP2_S2_cache" / "road"


def load_cap(name):
    z = np.load(S2 / (name + ".npz"))
    t, label = z["t"], z["label"]
    tm = np.maximum.accumulate(t)
    return t, tm, label


def win_table(name):
    """Window structure of one capture: starts, window label y, clean flag, window end time, first injected time."""
    t, tm, label = load_cap(name)
    clean = E.lead_clean(t, label)
    st = Z.window_starts(tm)
    return {"t": t, "tm": tm, "label": label, "st": st, "clean_fr": clean,
            "w_end": np.maximum.reduceat(tm, st), "y": np.maximum.reduceat(label, st).astype(int),
            "clean": np.minimum.reduceat(clean.astype(np.int8), st).astype(bool), "fi": E.first_injected({"t": t, "label": label})}


def l3_arrays(name, group, key):
    """(window scores, grid-ok mask, frame scores) of one L3 score series 'd' or a variant name."""
    W = win_table(name)
    z = np.load(CACHE / ("scores_" + group) / (name + ".npz"))
    gs, t0 = z[key], float(z["t0"])
    ws, ok = P.window_scores(gs, W["tm"], t0, W["st"])
    return W, ws, ok, P.frame_scores(gs, W["tm"], t0)


def calib(pool_w, pool_f):
    wl = P.L3Layer("window").calibrate_from_raw(np.concatenate(pool_w), BUDGET)
    fl = P.L3Layer("frame").calibrate_from_raw(np.concatenate(pool_f), BUDGET)
    return wl, fl


class FloorRule:
    """L3d alarm = contradiction longer than the longest one seen on any held-out clean capture (lag tolerance, design change 3):
    never below the tie-safe 1% budget rule, and it keeps the ECDF calibration of the sub-layer for AUC."""

    def __init__(self, layer, pool):
        self.layer, self.m = layer, float(np.max(pool))
        self.threshold = layer.threshold

    def alarms(self, raw):
        return np.asarray(raw) > self.m

    def calibrated(self, raw):
        return self.layer.calibrated(raw)


def calib_d(pool_w, pool_f):
    wd, fd = calib(pool_w, pool_f)
    return FloorRule(wd, np.concatenate(pool_w)), FloorRule(fd, np.concatenate(pool_f))


def loco_pool(key):
    """Pooled held-out clean windows / frames of the 7 LOCO captures for one score series; frames/windows before the grid are not scored."""
    ws_l, fs_l, per = [], [], {}
    for c in LOCO:
        W, ws, ok, fs = l3_arrays(c, "loco", key)
        gi = P.grid_index(W["tm"], float(np.load(CACHE / "scores_loco" / (c + ".npz"))["t0"]), 10 ** 9)
        ws_l.append(ws[ok])
        fs_l.append(fs[gi >= 0])
        per[c] = len(ws[ok])
    return ws_l, fs_l, per


def capture_eval(name, group, key, wl, fl):
    W, ws, ok, fs = l3_arrays(name, group, key)
    al = wl.alarms(ws) & ok
    y = (W["y"] == 1) & ok
    cl = W["clean"] & ~(W["y"] == 1) & ok
    r = {"windows": int(ok.sum()), "attack_windows": int(y.sum()), "clean_windows": int(cl.sum()), "false_alerts_clean": int(al[cl].sum()),
         "fa_clean_rate": float(al[cl].mean()) if cl.any() else None}
    if y.any():
        r["detected"] = bool(al[y].any())
        r["window_recall"] = float(al[y].mean())
        idx = np.flatnonzero(al & y)
        r["delay_s"] = float(max(W["w_end"][idx[0]] - W["fi"], 0.0)) if len(idx) else None
    return r, al, ok, ws, W, fs


def select():
    res = {"variants": {}}
    masq = [c for c in attack_names(1) + attack_names(2) if "masquerade" in c]
    allatt = attack_names(1) + attack_names(2)
    # L3d
    wsl, fsl, per = loco_pool("d")
    wd, fd = calib_d(wsl, fsl)
    res["l3d"] = {"window_threshold": wd.threshold, "frame_threshold": fd.threshold, "loco_pool_windows": per}
    d_al = {}
    for c in allatt:
        r, al, ok, ws, W, _ = capture_eval(c, "attack", "d", wd, fd)
        d_al[c] = (al, ok, W)
    res["l3d"]["loco_fa_per_fold"] = {c: float(wd.alarms(w).mean()) for c, w in zip(LOCO, wsl)}
    res["l3d"]["attack_val"] = {c: capture_eval(c, "attack", "d", wd, fd)[0] for c in masq}
    for vi, v in enumerate(VARIANTS):
        k = vname(v)
        wsl, fsl, per = loco_pool(k)
        wl, fl = calib(wsl, fsl)
        rec, lead_a, lead_n, per_att = [], 0, 0, {}
        for c in allatt:
            r, al, ok, ws, W, _ = capture_eval(c, "attack", k, wl, fl)
            ad, okd, _ = d_al[c]
            u = (al | ad) & ok
            y = (W["y"] == 1) & ok
            cl = W["clean"] & ~(W["y"] == 1) & ok
            lead_a += int(u[cl].sum())
            lead_n += int(cl.sum())
            if c in masq:
                per_att[c] = {"l3c_recall": r.get("window_recall"), "l3c_detected": r.get("detected"), "union_recall": float(u[y].mean()),
                              "union_detected": bool(u[y].any()), "l3c_lead_fa": r["fa_clean_rate"]}
                rec.append(float(u[y].mean()))
        res["variants"][str(vi)] = {"name": k, "window_threshold": wl.threshold, "frame_threshold": fl.threshold,
                                    "loco_fa_per_fold": {c: float(wl.alarms(w).mean()) for c, w in zip(LOCO, wsl)},
                                    "loco_pooled_fa_union_nominal": 0.02, "lead_fa_union": lead_a / max(lead_n, 1), "lead_windows": lead_n,
                                    "mean_masq_recall_union": float(np.mean(rec)), "attack_val": per_att}
        print(vi, k, f"recall {np.mean(rec):.3f} leadFA {lead_a / max(lead_n, 1):.3f} ({lead_a}/{lead_n})", flush=True)
    ok_v = [i for i, v in res["variants"].items() if v["lead_fa_union"] <= 0.03]
    if ok_v:
        best = min(ok_v, key=lambda i: (-res["variants"][i]["mean_masq_recall_union"], res["variants"][i]["lead_fa_union"], int(i)))
    else:
        best = min(res["variants"], key=lambda i: (res["variants"][i]["lead_fa_union"], int(i)))
    res["chosen"] = int(best)
    res["chosen_rule"] = "lead FA <= 3% then max mean masquerade recall" if ok_v else "none under 3%: lowest lead FA"
    json.dump(res, open(OUT / "s5_select.json", "w"), indent=1)
    print("chosen", best, VARIANTS[int(best)])


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select()
