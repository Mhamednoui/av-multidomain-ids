"""WP4 S7 D10 test run (the ONE run): frozen stacks (combiners.pkl chosen on validation by tools/WP4_S7_dev.py) on the D10 test STAGE stream.
Usage: python -u -W ignore tools/WP4_S7_test.py smoke|verdict [noloao]
  smoke   : the "test" side is the VALIDATION table (pipeline check); writes results/WP4/smoke/
  verdict : the ONE run on test; writes results/WP4/s7_d10.json
Contents: per stack (H, O, optional rows) combined FA / per-family detection with 95% CIs (bootstrap over 10-minute blocks), published and Bot-corrected labels, dedup view,
delay, AUC, ablation (each layer alone, all, all-but-one for H and O), OR view, flow-level null control of the combiner, leave-one-attack-out (test side; combiner selection
without the family; L4 retrained without it)."""
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import combiner as cb
from common.config import BUDGET_DOMAIN, SEED
from common.metrics import budget_threshold
from network.flows import FEATURES
from network.l4 import XGBNet
from tools.WP4_S6_lib import COLS, feat, load_s6, sel
from tools.WP4_S7_lib import (EVAL10, GROUPS_LOAO, H, O, RES, S7, STACKS, Scorer, comb_alarm, fit_combiner, layer_alarm, load_combiner, load_tables, log, or_alarm,
                              val_sample)

MODE = sys.argv[1] if len(sys.argv) > 1 else "smoke"
NOLOAO = "noloao" in sys.argv
assert MODE in ("smoke", "verdict")
OUT = RES if MODE == "verdict" else os.path.join(RES, "smoke")
os.makedirs(OUT, exist_ok=True)
LOAO_STACKS = ["H", "O", "O+topology", "O+L4", "L4 alone"]
DET_FAMS = ("Infiltration", "Heartbleed", "Web-SQLi")        # not evaluable (few flows): shown for information


def feat_pos(X, pos):
    o = np.argsort(pos)
    arr = np.empty((len(pos), len(COLS)), np.float32)
    arr[o] = np.asarray(X[np.asarray(pos)[o]])[:, [FEATURES.index(c) for c in COLS]]
    return pd.DataFrame(arr, columns=COLS)


def views(df, alarm, score=None, ci=True):
    """published labels / corrected Bot labels / dedup subset."""
    out = {}
    for nm, col in (("published", "fam"), ("bot_corrected", "fam_corr")):
        sc = Scorer(df, col)
        r = sc.summary(alarm, ci=ci, extra_fams=DET_FAMS)
        if score is not None and nm == "published":
            r["auc"] = sc.auc_all(score)
        out[nm] = r
    m = df["in_final"].to_numpy()
    out["dedup_rows"] = Scorer(df[m].reset_index(drop=True), "fam").summary(np.asarray(alarm)[m], ci=False, extra_fams=DET_FAMS)
    return out


def run_stack(name, names, df, cal, combs):
    C = load_combiner(combs[name])
    s, al = comb_alarm(C, df, cal)
    r = views(df, al, s)
    r["method"] = C.method
    r["layers"] = names
    r["delay_min"] = Scorer(df, "fam").delay(al)
    return r, s, al


def main():
    val, test, cal = load_tables()
    df = (val if MODE == "smoke" else test).reset_index(drop=True)
    combs = pickle.load(open(os.path.join(S7, "combiners.pkl"), "rb"))
    res = {"mode": MODE, "n_rows": int(len(df)), "n_blocks": int(len(np.unique(Scorer(df).bu))), "stacks": {}, "ablation": {}, "layers_alone": {}, "or_view": {}}
    sc_pub = Scorer(df, "fam")
    # ---- stacks
    alarms = {}
    for nm, names in STACKS.items():
        if nm == "L4 alone":
            al = layer_alarm(df, cal, "net.l4_xgb")
            s = cal["net.l4_xgb"][0].transform(df["s_net.l4_xgb"].to_numpy(float))
            r = views(df, al, s)
            r.update({"method": "single layer", "layers": names, "delay_min": sc_pub.delay(al)})
        else:
            r, s, al = run_stack(nm, names, df, cal, combs)
        res["stacks"][nm] = r
        alarms[nm] = al
        p = r["published"]
        log("%-11s [%s] FA %.4f [%.4f,%.4f] (pub %.4f, audit file %.4f) macro %.3f [%.3f,%.3f] >=50%%: %d AUC %.4f" % (
            nm, r["method"], p["fa"], *p["fa_ci"], p["fa_pub"], p["fa_audit_file"] or 0, p["macro"], *p["macro_ci"], p["n_ge50"], p["auc"]),
            {f: round(v, 3) for f, v in p["detection"].items()})
    # ---- layers alone (own 1% threshold) and ablation for H and O; OR view
    for nm in sorted(set(sum(STACKS.values(), []))):
        al = layer_alarm(df, cal, nm)
        res["layers_alone"][nm] = views(df, al, cal[nm][0].transform(df["s_" + nm].to_numpy(float)))
        res["layers_alone"][nm]["delay_min"] = sc_pub.delay(al)
        p = res["layers_alone"][nm]["published"]
        log("  alone %-18s FA %.4f macro %.3f" % (nm, p["fa"], p["macro"]), {f: round(v, 2) for f, v in p["detection"].items()})
    for base in ("H", "O"):
        res["ablation"][base] = {"all": res["stacks"][base]["published"], "alone": {n: res["layers_alone"][n]["published"] for n in STACKS[base]}, "all_but": {}}
        for n in STACKS[base]:
            key = f"{base} all-but {n}"
            C = load_combiner(combs[key])
            s, al = comb_alarm(C, df, cal)
            r = sc_pub.summary(al, ci=True, extra_fams=DET_FAMS)
            r["method"] = C.method
            r["auc"] = sc_pub.auc_all(s)
            res["ablation"][base]["all_but"][n] = r
            log("  %s all-but %-16s [%s] FA %.4f macro %.3f ge50 %d" % (base, n, C.method, r["fa"], r["macro"], r["n_ge50"]))
        al = or_alarm(df, cal, STACKS[base])
        res["or_view"][base] = sc_pub.summary(al, ci=False)
        log("  OR view", base, "FA %.4f macro %.3f" % (res["or_view"][base]["fa"], res["or_view"][base]["macro"]))
    # ---- combiner sensitivity (information only: every method with the same validation sample; the frozen choice is the one in 'stacks')
    vs0 = val_sample(val)
    res["combiner_sensitivity"] = {}
    for nm in ("H", "O", "O+L4"):
        res["combiner_sensitivity"][nm] = {}
        for m in ("noisy_or", "max", "logistic"):
            C = fit_combiner(vs0, cal, STACKS[nm], method=m)
            s_, al_ = comb_alarm(C, df, cal)
            r = sc_pub.summary(al_, ci=False)
            res["combiner_sensitivity"][nm][m] = {"fa": r["fa"], "macro": r["macro"], "n_ge50": r["n_ge50"], "detection": r["detection"], "auc": sc_pub.auc_all(s_)}
            log("  sensitivity %-5s %-9s FA %.4f macro %.3f ge50 %d" % (nm, m, r["fa"], r["macro"], r["n_ge50"]))
    # ---- null control of the combiner (only when the selected method is learned)
    vs = val_sample(val)
    res["null"] = {}
    for nm in ("H", "O"):
        if combs[nm]["method"] != "logistic":
            res["null"][nm] = {"method": combs[nm]["method"], "note": "no learned parameters in the combination step (threshold only)"}
            continue
        names = combs[nm]["names"]
        Xv = np.column_stack([cal[n][0].transform(vs["s_" + n].to_numpy(float)) for n in names])
        yv = (vs["fam"].to_numpy() != "BENIGN").astype(int)
        Xt = np.column_stack([cal[n][0].transform(df["s_" + n].to_numpy(float)) for n in names])
        m = sc_pub.ben | (sc_pub.fam != "BENIGN")
        yt = (sc_pub.fam[m] != "BENIGN").astype(int)
        seeds = []
        for sd in range(5):
            perm = np.random.RandomState(1000 + sd).permutation(len(yv))
            mod = cb._fit_logistic(Xv, yv[perm])
            st = mod.predict_proba(cb._surprise(Xt))[:, 1]
            sv = mod.predict_proba(cb._surprise(Xv))[:, 1]
            thr = budget_threshold(sv[yv[perm] == 0], BUDGET_DOMAIN)
            from common.metrics import auc as _auc
            seeds.append({"seed": sd, "auc": _auc(yt, st[m]), "detection_at_own_1pct": float((st[m][yt == 1] >= thr).mean()), "fa_at_own_1pct": float((st[m][yt == 0] >= thr).mean())})
        res["null"][nm] = {"method": "logistic", "seeds": seeds, "mean_auc": float(np.mean([x["auc"] for x in seeds])), "bound": 0.55}
        res["null"][nm]["met"] = bool(res["null"][nm]["mean_auc"] <= 0.55)
        log("  null", nm, "mean AUC %.3f" % res["null"][nm]["mean_auc"], [round(x["auc"], 3) for x in seeds])
    json.dump(res, open(os.path.join(OUT, "s7_d10.json"), "w"), indent=1)
    if NOLOAO:
        return
    loao(val, df, cal, combs, res)


def loao(val, df, cal, combs, res):
    log("== LOAO")
    chosen = json.load(open(os.path.join(RES, "s6_dev_val.json")))["chosen"]
    d, X = load_s6()
    mt, mv = sel(d, "train"), sel(d, "val")
    mvb = sel(d, "val", benign_only=True)
    tr, vbf = feat(d, X, mt), feat(d, X, mvb)
    fam_tr, grp_tr = d["fam"].to_numpy()[mt], d["grp"].to_numpy()[mt]
    pos_v, pos_t = val["pos"].to_numpy(), df["pos"].to_numpy()
    F_val, F_te = feat_pos(X, pos_v), feat_pos(X, pos_t)
    names = [(f, [f]) for f in EVAL10] + [(g, m) for g, m in GROUPS_LOAO.items()]
    if MODE == "smoke":
        names = [x for x in names if x[0] in ("Bot", "DoS-4")]
    out = {}
    sc_pub = Scorer(df, "fam")
    for nm, members in names:
        t0 = time.time()
        keep = ~np.isin(fam_tr, members)
        L = XGBNet(params=chosen["params"], n_trees=chosen["n_trees"]).fit(tr[keep], (fam_tr[keep] != "BENIGN").astype(int), grp_tr[keep])
        L.calibrate(vbf, BUDGET_DOMAIN)
        calf = dict(cal)
        calf["net.l4_xgb"] = (L.calibrator, float(L.threshold), "s_net.l4_xgb")
        v2, d2 = val.copy(), df.copy()
        v2["s_net.l4_xgb"] = L.raw_scores(F_val)
        d2["s_net.l4_xgb"] = L.raw_scores(F_te)
        vs = val_sample(v2, exclude=members)
        r = {"members": members, "stacks": {}}
        for sn in LOAO_STACKS:
            nmz = STACKS[sn]
            if sn == "L4 alone":
                al = layer_alarm(d2, calf, "net.l4_xgb")
                method = "single layer"
            else:
                C = fit_combiner(vs, calf, nmz)
                _, al = comb_alarm(C, d2, calf)
                method = C.method
            held = np.isin(sc_pub.fam, members)
            s = sc_pub.summary(al, ci=True, extra_fams=members)
            entry = {"method": method, "fa": s["fa"], "fa_ci": s["fa_ci"], "detection": {m: s["detection"][m] for m in members if m in s["detection"]},
                     "detection_ci": {m: s["detection_ci"][m] for m in members if m in s["detection_ci"]}, "n": {m: s["n"][m] for m in members if m in s["n"]}}
            if len(members) > 1:
                entry["group_detection"] = float(al[held].mean())
                entry["group_n"] = int(held.sum())
            r["stacks"][sn] = entry
            # macro over the OTHER families (seen) for information
            r["stacks"][sn]["macro_other_families"] = float(np.mean([s["detection"][f] for f in EVAL10 if f in s["detection"] and f not in members]))
        out[nm] = r
        log(nm, "(%.0fs)" % (time.time() - t0), {sn: (round(e.get("group_detection", list(e["detection"].values())[0] if e["detection"] else float("nan")), 3), round(e["fa"], 4)) for sn, e in r["stacks"].items()})
        res["loao"] = out
        json.dump(res, open(os.path.join(OUT, "s7_d10.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
