"""WP4 S6 verdict: L4 (network/l4.py, net.l4_xgb) on D10 test (the ONE run), null control, importance, Bot signature check, harness ablation, D23 zero-shot.
Usage: python -u -W ignore tools/WP4_S6_verdict.py smoke|verdict [fast]
  smoke   : the "test" side is the VALIDATION split (pipeline check); writes results/WP4/smoke/
  verdict : the ONE run on test; writes results/WP4/s6_*.json
  fast    : 1 null seed and no ablation refit (smoke only)
Chosen model: results/WP4/s6_dev_val.json (selected on validation) and the saved model in the S6 cache. Thresholds: tie-safe 1% budget on the dedup benign validation scores.
Row sets of D10 test: "dedup" = rows of the de-duplicated final table (headline), "stage" = all stream rows (S3-S5 view), benign excl. the audited Infiltration file; published-label FA also."""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN, SEED
from common.evaluate import EvalSet, evaluate_domain
from common.layer import Layer
from common.metrics import auc, binary_summary, budget_threshold
from network.flows import FEATURES, GROUP
from network.l4 import XGBNet, matrix
from tools.WP4_S3_lib import subsample
from tools.WP4_S6_lib import COLS, EVAL10, EVAL23, RES, RULE_BLIND, S6, det_at_budget, feat, load_s6, log, sel

MODE = sys.argv[1] if len(sys.argv) > 1 else "smoke"
FAST = len(sys.argv) > 2 and sys.argv[2] == "fast"
assert MODE in ("smoke", "verdict")
TEST = "val" if MODE == "smoke" else "test"
OUT = RES if MODE == "verdict" else os.path.join(RES, "smoke")
os.makedirs(OUT, exist_ok=True)
N_BEN, N_FAM = 150_000, 20_000
N_NULL = 1 if FAST else 5
L2A = ["net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.slow"]
BASE = ["net.tcp_flags"] + L2A
L3ON = ["net.l3_service", "net.l3_ae"]
LID = {"net.tcp_flags": "L1", "net.scan": "L2a", "net.trw": "L2a", "net.bruteforce": "L2a", "net.dos_rate": "L2a", "net.slow": "L2a", "net.beacon": "L2b",
       "net.l3_service": "L3", "net.l3_ae": "L3", "net.l4_xgb": "L4"}


class Col(Layer):
    """Harness wrapper: raw score = a precomputed column; calibration given."""

    def __init__(self, name, col, calibrator, thr):
        super().__init__()
        self.domain, self.name, self.layer_id, self.kind = "network", name, LID[name], "rule"
        self.score_col, self.calibrator, self.threshold, self.budget = col, calibrator, thr, BUDGET_DOMAIN

    def raw_scores(self, samples):
        return samples[self.score_col].to_numpy(float)


def evalset(layers, s):
    ev = {L.name: L.score(s) for L in layers}
    y = (s["family"].astype(str) != "BENIGN").to_numpy().astype(int)
    at = np.where(y == 1, s["family"].astype(str).to_numpy(), "normal")
    return EvalSet(evidence=ev, y=y, attack_type=at, group=s["day"].astype(str).to_numpy(), t=np.nan_to_num(s["t"].to_numpy()))


def sub(es, names):
    return EvalSet(evidence={n: es.evidence[n] for n in names}, y=es.y, attack_type=es.attack_type, group=es.group, t=es.t)


def feat_pos(d, X, pos):
    o = np.argsort(pos)
    arr = np.empty((len(pos), len(COLS)), np.float32)
    arr[o] = np.asarray(X[np.asarray(pos)[o]])[:, [FEATURES.index(c) for c in COLS]]
    return pd.DataFrame(arr, columns=COLS)


def block(raw, fam, ben, atk, thr, evaluable):
    """det_at_budget on the given row masks with a raw threshold + macro over the evaluable families."""
    r = det_at_budget(raw[ben], raw[atk], fam[atk], thr=thr)
    ev = [f for f in evaluable if f in r["detection"]]
    r["macro"] = float(np.mean([r["detection"][f] for f in ev]))
    r["macro_auc"] = float(np.mean([r["auc"][f] for f in ev]))
    r["blind4"] = float(np.mean([r["detection"][f] for f in RULE_BLIND if f in r["detection"]]))
    return r


def contribs(L, df, fam, raw, thr, groups, n=300):
    """Mean share of |tree contribution| per feature (top 5) for the highest-scoring alarmed flows of each group ("BENIGN" = benign false alarms)."""
    out = {}
    bst = L.model.get_booster()
    for g in groups:
        idx = np.flatnonzero((fam == g) & (raw >= thr))
        if len(idx) == 0:
            continue
        idx = idx[np.argsort(-raw[idx])][:n]
        c = bst.predict(xgb.DMatrix(matrix(df.iloc[idx], L.cols)), pred_contribs=True, iteration_range=(0, L.best_n_trees))[:, :-1]
        a = np.abs(c)
        m = (a / np.maximum(a.sum(1, keepdims=True), 1e-12)).mean(0)
        top = np.argsort(-m)[:5]
        out[g] = {"n_flows": int(len(idx)), "top": [[L.cols[j], float(m[j])] for j in top]}
    return out


def load_l4(chosen, tr=None):
    L = XGBNet(params=chosen["params"], n_trees=chosen["n_trees"])
    p = os.path.join(S6, "l4_model.json")
    L.model = xgb.XGBClassifier()
    L.model.load_model(p)
    L.best_n_trees = int(chosen["n_trees"])
    return L


def main():
    dev = json.load(open(os.path.join(RES, "s6_dev_val.json")))
    chosen = dev["chosen"]
    d, X = load_s6()
    L = load_l4(chosen)
    res = {"mode": MODE, "test_side": TEST, "chosen": chosen, "n_features": len(COLS)}
    # ---------------- calibration on dedup benign validation
    mvb = sel(d, "val", benign_only=True)
    vb = feat(d, X, mvb)
    L.calibrate(vb, BUDGET_DOMAIN)
    thr = float(budget_threshold(L.calibrator.sorted_, BUDGET_DOMAIN))
    mv = sel(d, "val")
    raw_v = L.raw_scores(feat(d, X, mv))
    fam_v = d["fam"].to_numpy()[mv]
    rv = block(raw_v, fam_v, fam_v == "BENIGN", fam_v != "BENIGN", thr, EVAL10)
    res["val_check"] = {"macro": rv["macro"], "dev_macro": dev["val_macro"], "fa": rv["fa_benign"], "threshold": thr}
    log("val check macro %.4f (dev %.4f) FA %.4f thr %.3f" % (rv["macro"], dev["val_macro"], rv["fa_benign"], thr))
    # ---------------- test side rows (all stream rows of the split) and the three row sets
    base_te = pd.read_pickle(os.path.join(S6, "base_val.pkl" if MODE == "smoke" else "base_test.pkl"))
    pos = base_te["pos"].to_numpy()
    fam = d["fam"].to_numpy()[pos]
    infin = d["in_final"].to_numpy()[pos]
    aud = d["audit"].to_numpy()[pos]
    Fte = feat_pos(d, X, pos)
    raw = L.raw_scores(Fte)
    base_te["s_net.l4_xgb"] = raw
    isb = fam == "BENIGN"
    sets = {"dedup": (isb & ~aud & infin, ~isb & infin), "stage": (isb & ~aud, ~isb), "published_labels_dedup": (isb & infin, ~isb & infin)}
    res["n"] = {k: {"benign": int(v[0].sum()), "attack": int(v[1].sum())} for k, v in sets.items()}
    res["d10"] = {}
    for k, (b, a) in sets.items():
        r = block(raw, fam, b, a, thr, EVAL10)
        res["d10"][k] = r
        log("D10", k, "FA %.4f macro %.3f macroAUC %.3f blind4 %.3f" % (r["fa_benign"], r["macro"], r["macro_auc"], r["blind4"]), {f: round(v, 3) for f, v in r["detection"].items()})
    res["d10"]["n_by_family_dedup"] = {f: int(((fam == f) & infin).sum()) for f in sorted(set(fam) - {"BENIGN"})}
    # v2-style operating point (margin 0 = p 0.5), information only (v2 used D01 and a random split: not comparable)
    b, a = sets["dedup"]
    m = b | a
    res["d10"]["v2_style_p05"] = binary_summary((~isb[m]).astype(int), (raw[m] >= 0).astype(int))
    log("p=0.5 operating point (not comparable to v2):", res["d10"]["v2_style_p05"])
    # ---------------- importance and attributions
    imp = L.importance()
    res["importance"] = {"total_gain_share": imp, "top5": list(imp.items())[:5]}
    log("importance top8", [(k, round(v, 3)) for k, v in list(imp.items())[:8]])
    famsA = [f for f in sorted(set(fam) - {"BENIGN"}) if ((fam == f) & infin).any()]
    cand = infin & ~aud
    res["attribution"] = contribs(L, Fte[cand].reset_index(drop=True), fam[cand], raw[cand], thr, famsA + ["BENIGN"])
    for g, v in res["attribution"].items():
        log("  attribution", g, [(a, round(b_, 2)) for a, b_ in v["top"]])
    ports = d["dst_port"].to_numpy()[pos]
    fa = (raw >= thr) & b
    vc = pd.Series(ports[fa]).value_counts()
    res["benign_fa_ports"] = {"n_false_alarms": int(fa.sum()), "top_ports": {int(k): float(v / fa.sum()) for k, v in vc.head(6).items()}} if fa.sum() else {}
    top1 = next(iter(imp))
    if imp[top1] > 0.30 and not FAST:
        mt = sel(d, "train")
        tr = feat(d, X, mt)
        keep = [c for c in COLS if c != top1]
        A = XGBNet(params=chosen["params"], n_trees=chosen["n_trees"])
        A.cols = keep
        A.fit(tr, (d["fam"].to_numpy()[mt] != "BENIGN").astype(int), d["grp"].to_numpy()[mt])
        ra = A.raw_scores(feat(d, X, mv))
        bv = fam_v == "BENIGN"
        rr = block(ra, fam_v, bv, ~bv, budget_threshold(ra[bv], BUDGET_DOMAIN), EVAL10)
        res["importance"]["ablation_drop_top1_val"] = {"dropped": top1, "val_macro": rr["macro"], "val_macro_full": rv["macro"], "detection": rr["detection"]}
        log("ablation drop", top1, "val macro %.3f vs %.3f" % (rr["macro"], rv["macro"]))
    # ---------------- null control: shuffled TRAIN labels, 5 seeds, same hyperparameters / tree count
    mt = sel(d, "train")
    tr = feat(d, X, mt)
    ytr = (d["fam"].to_numpy()[mt] != "BENIGN").astype(int)
    gtr = d["grp"].to_numpy()[mt]
    bd, ad = sets["dedup"]
    yset = np.r_[np.zeros(int(bd.sum())), np.ones(int(ad.sum()))]
    nulls = []
    for s in range(N_NULL):
        perm = np.random.RandomState(1000 + s).permutation(len(ytr))
        N = XGBNet(params=chosen["params"], n_trees=chosen["n_trees"], seed=SEED + s).fit(tr, ytr[perm], gtr)
        rn_te = N.raw_scores(Fte)
        a_ = auc(yset, np.r_[rn_te[bd], rn_te[ad]])
        rn_v = N.raw_scores(feat(d, X, mvb))
        tn = budget_threshold(rn_v, BUDGET_DOMAIN)
        nulls.append({"seed": s, "auc_test_dedup": a_, "fa_test": float((rn_te[bd] >= tn).mean()), "detection_test": float((rn_te[ad] >= tn).mean()),
                      "detection_at_real_threshold": float((rn_te[ad] >= thr).mean()), "fa_at_real_threshold": float((rn_te[bd] >= thr).mean())})
        log("  null seed", s, nulls[-1])
    res["null"] = {"seeds": nulls, "mean_auc": float(np.mean([n["auc_test_dedup"] for n in nulls])), "bound": 0.55,
                   "real_auc_dedup": auc(yset, np.r_[raw[bd], raw[ad]])}
    res["null"]["met"] = bool(res["null"]["mean_auc"] <= 0.55)
    log("NULL mean AUC %.4f (bound 0.55) real AUC %.4f" % (res["null"]["mean_auc"], res["null"]["real_auc_dedup"]))
    # ---------------- Bot signature check
    res["bot"] = bot_check(d, X, base_te, pos, fam, infin, aud, raw, thr, L, Fte, mt)
    json.dump(res, open(os.path.join(OUT, "s6_d10.json"), "w"), indent=1)
    # ---------------- harness
    harness(d, X, L, thr, base_te, pos, fam, infin, aud, res)
    json.dump(res, open(os.path.join(OUT, "s6_d10.json"), "w"), indent=1)
    # ---------------- D23
    d23(L, chosen, thr, raw_v_calib=np.sort(L.calibrator.sorted_))


def bot_check(d, X, base_te, pos, fam, infin, aud, raw, thr, L, Fte, mt):
    """Shapes (fwd pkts, bwd pkts, duration p5-p95) of the Bot flows to port 8080: from TRAIN (burst) and from VALIDATION (beacon phase). Compare Bot with benign flows of the same shape."""
    out = {"shapes": {}}
    ports = d["dst_port"].to_numpy()
    famall = d["fam"].to_numpy()
    sets = {}
    for nm, sp in (("train_shape", "train"), ("val_shape", "val")):
        m = sel(d, sp) & (famall == "Bot") & (ports == 8080)
        f = feat(d, X, m)
        pr = f.groupby(["Tot Fwd Pkts", "Tot Bwd Pkts"]).size().sort_values(ascending=False)
        nf, nb = pr.index[0]
        dur = f.loc[(f["Tot Fwd Pkts"] == nf) & (f["Tot Bwd Pkts"] == nb), "Flow Duration"]
        lo, hi = float(dur.quantile(0.05)), float(dur.quantile(0.95))
        lens = set(map(tuple, f.loc[(f["Tot Fwd Pkts"] == nf) & (f["Tot Bwd Pkts"] == nb), ["TotLen Fwd Pkts", "TotLen Bwd Pkts"]].to_numpy()))
        sets[nm] = (nf, nb, lo, hi, lens)
        out["shapes"][nm] = {"fwd_pkts": float(nf), "bwd_pkts": float(nb), "duration_us_p5_p95": [lo, hi], "n_defining_bot_flows": int(pr.iloc[0]), "n_bot_flows_8080": int(pr.sum()),
                             "distinct_len_pairs": len(lens)}
    bot = (fam == "Bot") & infin
    ben = (fam == "BENIGN") & infin & ~aud
    for nm, (nf, nb, lo, hi, lens) in sets.items():
        m = ((Fte["Tot Fwd Pkts"] == nf) & (Fte["Tot Bwd Pkts"] == nb) & (Fte["Flow Duration"] >= lo) & (Fte["Flow Duration"] <= hi)).to_numpy()
        lp = list(zip(Fte["TotLen Fwd Pkts"].to_numpy(), Fte["TotLen Bwd Pkts"].to_numpy()))
        inlens = np.array([p in lens for p in lp])
        r = {"bot_matched": int((bot & m).sum()), "bot_unmatched": int((bot & ~m).sum()), "benign_matched": int((ben & m).sum()),
             "benign_matched_port8080": int((ben & m & (d["dst_port"].to_numpy()[pos] == 8080)).sum()),
             "detection_bot_matched": float((raw[bot & m] >= thr).mean()) if (bot & m).any() else None,
             "detection_bot_unmatched": float((raw[bot & ~m] >= thr).mean()) if (bot & ~m).any() else None,
             "fa_benign_matched": float((raw[ben & m] >= thr).mean()) if (ben & m).any() else None,
             "bot_matched_byte_signature_share": float(inlens[bot & m].mean()) if (bot & m).any() else None,
             "benign_matched_byte_signature_share": float(inlens[ben & m].mean()) if (ben & m).any() else None}
        if (bot & m).sum() >= 5 and (ben & m).sum() >= 5:
            y = np.r_[np.zeros(int((ben & m).sum())), np.ones(int((bot & m).sum()))]
            r["auc_bot_vs_benign_same_shape"] = auc(y, np.r_[raw[ben & m], raw[bot & m]])
            a_ = r["auc_bot_vs_benign_same_shape"]
            r["reading"] = "shape only" if a_ < 0.7 else ("finer implementation signature" if a_ >= 0.9 else "mixed")
        out[nm] = r
        log("  Bot", nm, r)
    # overall Bot
    out["bot_all_dedup"] = {"n": int(bot.sum()), "detection": float((raw[bot] >= thr).mean()) if bot.any() else None,
                            "auc_vs_benign": auc(np.r_[np.zeros(int(ben.sum())), np.ones(int(bot.sum()))], np.r_[raw[ben], raw[bot]]) if bot.any() else None}
    al = np.flatnonzero(bot & (raw >= thr))
    if len(al):
        idx = al[np.argsort(-raw[al])][:300]
        c = L.model.get_booster().predict(xgb.DMatrix(matrix(Fte.iloc[idx], L.cols)), pred_contribs=True, iteration_range=(0, L.best_n_trees))[:, :-1]
        a = np.abs(c)
        mshare = (a / np.maximum(a.sum(1, keepdims=True), 1e-12)).mean(0)
        out["bot_top_features"] = [[L.cols[j], float(mshare[j])] for j in np.argsort(-mshare)[:6]]
    return out


def harness(d, X, L, thr, te, pos, fam, infin, aud, res):
    cal = pickle.load(open(os.path.join(S6, "base_cal.pkl"), "rb"))
    vm = pd.read_pickle(os.path.join(S6, "base_val.pkl"))
    vm["s_net.l4_xgb"] = L.raw_scores(feat_pos(d, X, vm["pos"].to_numpy()))
    for df in (vm, te):
        df["in_final"] = d["in_final"].to_numpy()[df["pos"].to_numpy()]
    cols = {n: Col(n, c[2], c[0], c[1]) for n, c in cal.items()}
    cols["net.l4_xgb"] = Col("net.l4_xgb", "s_net.l4_xgb", L.calibrator, float(L.threshold))
    cfg = [("base", BASE), ("base_l4", BASE + ["net.l4_xgb"]), ("base_beacon", BASE + ["net.beacon"]), ("base_beacon_l4", BASE + ["net.beacon", "net.l4_xgb"]),
           ("base_l3", BASE + L3ON), ("base_l3_l4", BASE + L3ON + ["net.l4_xgb"]), ("l4_only", ["net.l4_xgb"])]
    names_all = list(cols)
    res["harness"] = {}
    res["or_view"] = {}
    for rs in ("dedup", "stage"):
        vmask = ~vm["audit"].to_numpy()
        tmask = ~te["audit"].to_numpy()
        if rs == "dedup":
            vmask &= vm["in_final"].to_numpy()
            tmask &= te["in_final"].to_numpy()
        vs = subsample(vm[vmask], N_BEN, N_FAM, SEED).sort_values("t", kind="stable")
        ts = subsample(te[tmask], N_BEN, N_FAM, SEED).sort_values("t", kind="stable")
        ev_v, ev_t = evalset([cols[n] for n in names_all], vs), evalset([cols[n] for n in names_all], ts)
        res["harness"][rs] = {"subsample": {"val": len(vs), "test": len(ts)}}
        for nm, names in cfg:
            r = evaluate_domain("s6_d10_%s_%s" % (rs, nm), sub(ev_v, names), sub(ev_t, names), wp="WP4", out_dir=OUT)
            det = r["combined"]["detection_by_attack"]
            res["harness"][rs][nm] = {"combined": r["combined"], "ablation": r["ablation"], "macro11": float(np.mean([det.get(f, 0.0) for f in EVAL10])),
                                      "blind4": float(np.mean([det.get(f, 0.0) for f in RULE_BLIND]))}
            log("  harness", rs, nm, "FA %.4f macro11 %.3f blind4 %.3f" % (r["combined"]["false_alarm_rate"], res["harness"][rs][nm]["macro11"], res["harness"][rs][nm]["blind4"]),
                {k: round(v, 2) for k, v in det.items()})
        # OR view on the whole test table
        fam_t = te["family"].astype(str).to_numpy()
        if rs == "dedup":
            ben = (fam_t == "BENIGN") & ~te["audit"].to_numpy() & te["in_final"].to_numpy()
            atk_ok = te["in_final"].to_numpy()
        else:
            ben = (fam_t == "BENIGN") & ~te["audit"].to_numpy()
            atk_ok = np.ones(len(te), bool)
        res["or_view"][rs] = {}
        for nm, names in cfg:
            al = np.zeros(len(te), bool)
            for n in names:
                c = cols[n]
                al |= c.calibrator.transform(te[c.score_col].to_numpy(float)) >= c.threshold
            det = {f: float(al[(fam_t == f) & atk_ok].mean()) for f in EVAL10}
            res["or_view"][rs][nm] = {"fa_benign": float(al[ben].mean()), "detection": det, "macro11": float(np.mean(list(det.values())))}
            log("  OR", rs, nm, "FA %.4f macro11 %.3f" % (al[ben].mean(), np.mean(list(det.values()))))


def d23(L, chosen, thr, raw_v_calib):
    log("== D23 sample", MODE)
    e = pd.read_pickle(os.path.join(S6, "..", "S5", "D23_eval.pkl"))
    te = e[e["split"] == TEST].reset_index(drop=True)
    vbn = e[(e["split"] == "val") & (e["family"] == "BENIGN")].reset_index(drop=True)
    trn = e[(e["split"] == "train") & (e["family"] == "BENIGN")].reset_index(drop=True)
    fam = te["family"].to_numpy()
    ben = fam == "BENIGN"
    atk = ~ben
    day = te["day"].to_numpy()
    res = {"mode": MODE, "test_side": TEST, "n": {"test_benign": int(ben.sum()), "test_attack": {f: int((fam == f).sum()) for f in sorted(set(fam) - {"BENIGN"})}}}

    def blk(raw, t):
        r = block(raw, fam, ben, atk, t, EVAL23)
        r["fa_by_day"] = {str(k): float((raw[ben & (day == k)] >= t).mean()) for k in np.unique(day[ben])}
        return r

    rt = L.raw_scores(te)
    rvb = L.raw_scores(vbn)
    res["zero_shot"] = blk(rt, thr)
    res["zero_shot"]["median_shift_benign_vs_d10_val"] = float(np.median(rt[ben]) - np.median(raw_v_calib))
    res["recalibrated_no_refit"] = blk(rt, budget_threshold(rvb, BUDGET_DOMAIN))
    for k in ("zero_shot", "recalibrated_no_refit"):
        z = res[k]
        log(" ", k, "FA %.4f macro9 %.3f macro9_auc %.3f" % (z["fa_benign"], z["macro"], z["macro_auc"]), {a: round(b, 3) for a, b in z["detection"].items()})
        log("   auc", {a: round(b, 3) for a, b in z["auc"].items()})
    # information: on-network supervised refit = labelled attack flows of the target network's EARLIER (validation-time) window; threshold on its benign training-time flows
    tv = e[e["split"] == "val"].reset_index(drop=True)
    y = (tv["family"] != "BENIGN").astype(int).to_numpy()
    grp = tv["family"].map(lambda f: GROUP.get(f, f)).to_numpy()
    R = XGBNet(params=chosen["params"], n_trees=chosen["n_trees"]).fit(tv, y, grp)
    rb = R.raw_scores(trn)
    t2 = budget_threshold(rb, BUDGET_DOMAIN)
    res["on_network_refit"] = blk(R.raw_scores(te), t2)
    z = res["on_network_refit"]
    log("  on-network refit FA %.4f macro9 %.3f macro9_auc %.3f" % (z["fa_benign"], z["macro"], z["macro_auc"]), {a: round(b, 3) for a, b in z["detection"].items()})
    json.dump(res, open(os.path.join(OUT, "s6_d23.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
