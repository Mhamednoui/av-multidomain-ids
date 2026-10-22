"""WP4 S5 run: L3 normal-only layers (network/l3.py) on D10 (stream of S3 / S4) and the D23 sample.
Usage: python -u -W ignore tools/WP4_S5_run.py smoke|verdict
  smoke   : the "test" side is the VALIDATION split (pipeline check); writes results/WP4/smoke/
  verdict : the ONE run on test; writes results/WP4/s5_*.json
Configurations (layer, parameters) from results/WP4/s5_dev_val.json["chosen"] (selected on validation). Fit on benign TRAIN flows only; thresholds: tie-safe 1% on benign
validation flows (audited Infiltration file excluded from fit / calibration / headline FA as in S3 / S4).
Parts: (1) D10 per-layer flow evaluation, clean vs all-76 hygiene ablation, dedup subset; (2) harness ablation on top of tcp_flags + L2a (logistic combiner, as S3 / S4);
(3) Bot signature analysis; (4) feature attributions; (5) D23 zero-shot (D10 fit) and refit (D23 benign fit)."""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN, SEED
from common.evaluate import EvalSet, evaluate_domain
from common.layer import Layer
from common.metrics import budget_threshold
from network import l1, l2a, l3
from network.flows import FEATURES
from tools.WP4_S3_lib import add_scores, fit_calibrate, flow_eval, stream, subsample
from tools.WP4_S5_lib import (CACHE, RES, RULE_BLIND, attack_mask, benign_mask, det_at_budget, frame, load_d10, log, summarise)

MODE = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert MODE in ("smoke", "verdict")
TEST = "val" if MODE == "smoke" else "test"
OUT = RES if MODE == "verdict" else os.path.join(RES, "smoke")
os.makedirs(OUT, exist_ok=True)
N_BEN, N_FAM = 150_000, 20_000
L2A = ["net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.slow"]
L3N = ["net.l3_service", "net.l3_iforest", "net.l3_ae"]
EVAL10 = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator", "PortScan", "Web-BruteForce", "Web-XSS"]
EVAL23 = ["Bot", "DDoS-HOIC", "DDoS-LOIC-HTTP", "DDoS-LOIC-UDP", "DoS-GoldenEye", "DoS-Slowloris", "Infiltration", "SSH-Patator", "Web-BruteForce"]
CLS = {"service": l3.ServiceProfile, "iforest": l3.IsoForest, "ae": l3.AutoEncoder}
NAME = {"service": "net.l3_service", "iforest": "net.l3_iforest", "ae": "net.l3_ae"}
N_ATTR = 200


class Col(Layer):
    """Harness wrapper: raw score = a precomputed column; calibration copied from the fitted layer."""

    def __init__(self, base):
        super().__init__()
        self.domain, self.layer_id, self.kind, self.name = base.domain, base.layer_id, base.kind, base.name
        self.score_col = "s_" + base.name
        self.calibrator, self.threshold, self.budget = base.calibrator, base.threshold, base.budget

    def raw_scores(self, samples):
        return samples[self.score_col].to_numpy(float)


def build(chosen, fs):
    out = []
    for key in ("service", "iforest", "ae"):
        kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in chosen[key]["params"].items()}
        out.append(CLS[key](feature_set_name=fs, **kw))
    return out


def families_of(df):
    return sorted(set(df["family"].astype(str)) - {"BENIGN"})


def evalset(layers, s):
    ev = {L.name: L.score(s) for L in layers}
    y = (s["family"].astype(str) != "BENIGN").to_numpy().astype(int)
    at = np.where(y == 1, s["family"].astype(str).to_numpy(), "normal")
    return EvalSet(evidence=ev, y=y, attack_type=at, group=s["day"].astype(str).to_numpy(), t=np.nan_to_num(s["t"].to_numpy()))


def sub(es, names):
    return EvalSet(evidence={n: es.evidence[n] for n in names}, y=es.y, attack_type=es.attack_type, group=es.group, t=es.t)


def mark_in_final(d):
    import glob
    B = os.path.join(CACHE, "..", "D10", "final")
    keys = pd.concat([pd.read_pickle(f, compression="gzip")[["file", "row"]] for f in glob.glob(os.path.join(B, "*.pkl"))], ignore_index=True)
    k = d["file"].astype(str) + "|" + d["row"].astype(str)
    return k.isin(set(keys["file"].astype(str) + "|" + keys["row"].astype(str))).to_numpy()


def or_view(layers, df, fams):
    al = np.zeros(len(df), bool)
    for L in layers:
        al |= L.calibrator.transform(df[L.score_col].to_numpy(float)) >= L.threshold
    fam = df["family"].astype(str).to_numpy()
    ben = (fam == "BENIGN") & ~df["audit"].to_numpy()
    return {"fa_benign": float(al[ben].mean()), "fa_benign_published_labels": float(al[fam == "BENIGN"].mean()),
            "detection": {f: float(al[fam == f].mean()) for f in fams if (fam == f).any()}}


def attribution(L, fr, raw, fam, thr, groups):
    """Top-5 features (mean share of the positive contribution) of the highest-scoring alarmed flows per group; groups = family names or 'BENIGN'."""
    out = {}
    for g in groups:
        idx = np.flatnonzero((fam == g) & (raw >= thr))
        if len(idx) == 0:
            continue
        idx = idx[np.argsort(-raw[idx])][:N_ATTR]
        C, names = L.contributions(fr.iloc[idx])
        C = np.maximum(C, 0)
        share = C / np.maximum(C.sum(1, keepdims=True), 1e-12)
        m = share.mean(0)
        top = np.argsort(-m)[:5]
        out[g] = {"n_flows": int(len(idx)), "top": [[names[j], float(m[j])] for j in top]}
    return out


def run_d10():
    log("== D10", MODE)
    chosen = json.load(open(os.path.join(RES, "s5_dev_val.json")))["chosen"]
    dev = json.load(open(os.path.join(RES, "s3_dev_val.json")))["chosen"]
    d, X = load_d10()
    d["in_final"] = mark_in_final(d)
    tr_f = frame(d, X, benign_mask(d, "train"))
    vb_f = frame(d, X, benign_mask(d, "val"))
    tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
    te = vm if MODE == "smoke" else stream(d, "test")
    assert len(tr) == len(tr_f) and len(vb) == len(vb_f)
    te_f, vm_f = frame(te, X), frame(vm, X)
    res = {"mode": MODE, "test_side": TEST, "chosen": chosen, "n": {"train_benign": len(tr), "val_benign": len(vb), "test": len(te)}}
    fams = families_of(te)
    res["families"] = fams
    ben_pos = np.flatnonzero(((vm["family"].astype(str) == "BENIGN") & ~vm["audit"]).to_numpy())
    fam_te = te["family"].astype(str).to_numpy()
    audit = te["audit"].to_numpy()
    layers = {}
    for fs in ("clean", "all"):
        Ls = build(chosen, fs)
        for L in Ls:
            L.fit(tr_f)
            L.calibrate(vb_f, BUDGET_DOMAIN)
            L.score_col = "s_" + L.name + ("" if fs == "clean" else "_all")
            vm[L.score_col] = L.raw_scores(vm_f)
            te[L.score_col] = vm[L.score_col].to_numpy() if MODE == "smoke" else L.raw_scores(te_f)
            fe = flow_eval(L, te, fams)
            ev = EVAL10
            fe["auc_by_family"] = {f: float(det_at_budget(te[L.score_col].to_numpy(float)[(fam_te == "BENIGN") & ~audit],
                                                          te[L.score_col].to_numpy(float)[fam_te == f], fam_te[fam_te == f])["auc_all"]) for f in fams}
            fe["summary"] = summarise({"detection": fe["detection"], "auc": fe["auc_by_family"]}, ev)
            raw = te[L.score_col].to_numpy(float)
            m = te["in_final"].to_numpy()
            L.raw_thr = budget_threshold(L.calibrator.sorted_, BUDGET_DOMAIN)
            al = L.calibrator.transform(raw) >= L.threshold
            fe["detection_dedup_subset"] = {f: float(al[(fam_te == f) & m].mean()) for f in fams if ((fam_te == f) & m).any()}
            fe["epochs"] = getattr(L, "epochs_run", None)
            thr5 = budget_threshold(L.calibrator.sorted_, 0.05)       # diagnostic only: where the families sit between 1% and 5% false alarms
            fe["at_fa5"] = {"fa_benign": float((raw[(fam_te == "BENIGN") & ~audit] >= thr5).mean()),
                            "detection": {f: float((raw[fam_te == f] >= thr5).mean()) for f in fams if (fam_te == f).any()}}
            fe["rank_median_of_family_among_benign"] = {f: float(np.median(np.searchsorted(np.sort(raw[(fam_te == "BENIGN") & ~audit]), raw[fam_te == f])) /
                                                                 ((fam_te == "BENIGN") & ~audit).sum()) for f in fams if (fam_te == f).any()}
            res.setdefault("layers_" + fs, {})[L.name] = fe
            log(" ", fs, L.name, "FA %.4f (pub %.4f)" % (fe["fa_benign"], fe["fa_benign_published_labels"]), "macro %.3f blind4 %.3f macroAUC %.3f" % (
                fe["summary"]["macro"], fe["summary"]["blind4"], fe["summary"]["macro_auc"]), {k: round(v, 2) for k, v in fe["detection"].items()})
            layers.setdefault(fs, []).append(L)
    L3clean = layers["clean"]
    # ---- attributions (clean layers): top alarms per family and top benign false alarms
    attr = {}
    famsA = [f for f in fams if (fam_te == f).any()]
    for L in L3clean:
        raw = te[L.score_col].to_numpy(float)
        thr = L.raw_thr
        fam_a = np.where((fam_te == "BENIGN") & audit, "BENIGN_AUDIT", fam_te)
        attr[L.name] = attribution(L, te_f, raw, fam_a, thr, famsA + ["BENIGN"])
    res["attribution"] = attr
    res["benign_fa_ports"] = {}
    for L in L3clean:
        fa = (te[L.score_col].to_numpy(float) >= L.raw_thr) & (fam_te == "BENIGN") & ~audit
        vc = te.loc[fa, "dst_port"].value_counts()
        res["benign_fa_ports"][L.name] = {"n_false_alarms": int(fa.sum()), "top_ports": {int(k): float(v / fa.sum()) for k, v in vc.head(6).items()}}
    # ---- Bot signature
    res["bot"] = bot_signature(d, X, te, te_f, L3clean, vb_f, fam_te, audit)
    # ---- harness
    l2 = l2a.all_layers(dev)
    fit_calibrate(l2, tr, vb)
    add_scores(vb, l2)
    add_scores(vm, l2)
    if MODE == "verdict":
        add_scores(te, l2)
    tf = l1.TcpFlags().fit(tr)
    tf.calibrate(vb, BUDGET_DOMAIN)
    tf.score_col = "s_net.tcp_flags"
    vm_h = vm.copy()
    for L in l2:
        vm_h.loc[vm_h.index[ben_pos], L.score_col] = vb[L.score_col].to_numpy()
    for X_ in (te, vm_h):
        X_[tf.score_col] = tf.raw_scores(X_)
    cols = [Col(L) for L in L3clean]
    for c, L in zip(cols, L3clean):
        c.score_col = L.score_col
    for L, c in zip(L3clean, cols):
        vm_h[c.score_col] = vm[L.score_col].to_numpy()
    val_h, test_h = vm_h[~vm_h["audit"].to_numpy()], te[~te["audit"].to_numpy()]
    vs = subsample(val_h, N_BEN, N_FAM, SEED).sort_values("t", kind="stable")
    ts = subsample(test_h, N_BEN, N_FAM, SEED).sort_values("t", kind="stable")
    res["subsample"] = {"val": len(vs), "test": len(ts)}
    layers_h = l2 + [tf] + cols
    ev_v, ev_t = evalset(layers_h, vs), evalset(layers_h, ts)
    base = ["net.tcp_flags"] + L2A
    cfg = [("base", base), ("base_svc", base + [L3N[0]]), ("base_if", base + [L3N[1]]), ("base_ae", base + [L3N[2]]), ("base_l3", base + L3N),
           ("l3_only", L3N)]
    res["harness"] = {}
    for nm, names in cfg:
        r = evaluate_domain("s5_d10_" + nm, sub(ev_v, names), sub(ev_t, names), wp="WP4", out_dir=OUT)
        res["harness"][nm] = {"combined": r["combined"], "ablation": r["ablation"],
                              "macro11": float(np.mean([r["combined"]["detection_by_attack"].get(f, 0.0) for f in EVAL10])),
                              "blind4": float(np.mean([r["combined"]["detection_by_attack"].get(f, 0.0) for f in RULE_BLIND]))}
        log("  harness", nm, "FA %.4f det %.4f macro11 %.3f blind4 %.3f" % (r["combined"]["false_alarm_rate"], r["combined"]["detection"],
                                                                         res["harness"][nm]["macro11"], res["harness"][nm]["blind4"]),
            {k: round(v, 2) for k, v in r["combined"]["detection_by_attack"].items()})
    res["or_view"] = {"base": or_view(l2 + [tf], te, fams), "base_l3": or_view(l2 + [tf] + cols, te, fams), "l3": or_view(cols, te, fams)}
    log("  OR base", {k: round(v, 2) for k, v in res["or_view"]["base"]["detection"].items()}, "FA %.4f" % res["or_view"]["base"]["fa_benign"])
    log("  OR base+L3", {k: round(v, 2) for k, v in res["or_view"]["base_l3"]["detection"].items()}, "FA %.4f" % res["or_view"]["base_l3"]["fa_benign"])
    json.dump(res, open(os.path.join(OUT, "s5_d10.json"), "w"), indent=1)
    return L3clean, chosen, d, X


def bot_signature(d, X, te, te_f, L3, vb_f, fam_te, audit):
    """Signature = (fwd packets, bwd packets) mode of the Bot TRAIN flows to port 8080. Matches among Bot / benign test flows and detection by match."""
    trb = (d["split"].astype(str) == "train").to_numpy() & (d["family"].astype(str) == "Bot").to_numpy() & (d["dst_port"].to_numpy() == 8080)
    f = frame(d, X, trb)
    pairs = f.groupby(["Tot Fwd Pkts", "Tot Bwd Pkts"]).size().sort_values(ascending=False)
    (nf, nb) = pairs.index[0]
    dur = f.loc[(f["Tot Fwd Pkts"] == nf) & (f["Tot Bwd Pkts"] == nb), "Flow Duration"]
    lo, hi = float(dur.quantile(0.05)), float(dur.quantile(0.95))
    res = {"signature": {"fwd_pkts": float(nf), "bwd_pkts": float(nb), "port": 8080, "duration_us_p5_p95": [lo, hi],
                         "share_of_bot_train_8080_flows": float(pairs.iloc[0] / pairs.sum()), "n_bot_train_8080": int(pairs.sum()),
                         "bot_train_pairs_top5": {"%g/%g" % k: int(v) for k, v in pairs.head(5).items()}}}

    def match(fr, port_too=True):
        m = (fr["Tot Fwd Pkts"] == nf) & (fr["Tot Bwd Pkts"] == nb) & (fr["Flow Duration"] >= lo) & (fr["Flow Duration"] <= hi)
        return (m & (fr["dst_port"] == 8080)).to_numpy() if port_too else m.to_numpy()

    sig, shape = match(te_f), match(te_f, False)
    bot, ben = fam_te == "Bot", (fam_te == "BENIGN") & ~audit
    res["test"] = {"n_bot": int(bot.sum()), "bot_match_signature": int((bot & sig).sum()), "benign_match_signature": int((ben & sig).sum()),
                   "benign_match_shape_any_port": int((ben & shape).sum()), "n_benign": int(ben.sum()), "bot_port_8080": int((bot & (te_f["dst_port"] == 8080).to_numpy()).sum()),
                   "benign_port_8080_share": float((ben & (te_f["dst_port"] == 8080).to_numpy()).sum() / ben.sum()), "layers": {}}
    for L in L3:
        raw = te[L.score_col].to_numpy(float)
        thr = L.raw_thr
        al = raw >= thr
        r = {"threshold": float(thr), "bot_detection": float(al[bot].mean()) if bot.any() else None,
             "bot_alarms": int((al & bot).sum()), "bot_alarms_matching_signature": int((al & bot & sig).sum()),
             "detection_signature_matching": float(al[bot & sig].mean()) if (bot & sig).any() else None,
             "detection_not_matching": float(al[bot & ~sig].mean()) if (bot & ~sig).any() else None,
             "fa_benign_matching_signature": float(al[ben & sig].mean()) if (ben & sig).any() else None,
             "bot_score_rank_median": float(np.median([(raw[ben] < v).mean() for v in raw[bot][:2000]])) if bot.any() else None}
        res["test"]["layers"][L.name] = r
        log("  Bot", L.name, r)
    res["_sig"] = [float(nf), float(nb), lo, hi]
    return res


def run_d23(L10, chosen, sig):
    log("== D23 sample", MODE)
    e = pd.read_pickle(os.path.join(CACHE, "D23_eval.pkl"))
    trn = e[(e["split"] == "train") & (e["family"] == "BENIGN")].reset_index(drop=True)
    tst = TEST
    vbn = e[(e["split"] == "val") & (e["family"] == "BENIGN")].reset_index(drop=True)
    te = e[e["split"] == tst].reset_index(drop=True)
    fam = te["family"].to_numpy()
    ben = fam == "BENIGN"
    fams = sorted(set(fam) - {"BENIGN"})
    res = {"mode": MODE, "test_side": tst, "n": {"train_benign": len(trn), "val_benign": len(vbn), "test_benign": int(ben.sum()),
                                                 "test_attack": {f: int((fam == f).sum()) for f in fams}}}
    sg = {"fwd": sig[0], "bwd": sig[1], "lo": sig[2], "hi": sig[3]}
    bm = fam == "Bot"
    m = (te["Tot Fwd Pkts"] == sg["fwd"]) & (te["Tot Bwd Pkts"] == sg["bwd"]) & (te["Flow Duration"] >= sg["lo"]) & (te["Flow Duration"] <= sg["hi"])
    res["bot_signature_in_d23"] = {"n_bot": int(bm.sum()), "bot_match_shape": int((bm & m.to_numpy()).sum()),
                                   "bot_match_shape_port8080": int((bm & m.to_numpy() & (te["dst_port"] == 8080).to_numpy()).sum()),
                                   "benign_match_shape_port8080": int((ben & m.to_numpy() & (te["dst_port"] == 8080).to_numpy()).sum()),
                                   "bot_port_counts_top3": {int(k): int(v) for k, v in te.loc[bm, "dst_port"].value_counts().head(3).items()}}
    day = te["day"].to_numpy()

    def block(raw_ben_val, raw, thr):
        r = det_at_budget(raw[ben], raw[~ben], fam[~ben], thr=thr)
        r["summary"] = {"macro9": float(np.mean([r["detection"][f] for f in EVAL23 if f in r["detection"]])),
                        "macro9_auc": float(np.mean([r["auc"][f] for f in EVAL23 if f in r["auc"]]))}
        r["fa_by_day"] = {str(k): float((raw[ben & (day == k)] >= thr).mean()) for k in np.unique(day[ben])}
        r["median_shift"] = float(np.median(raw[ben]) / max(np.median(raw_ben_val), 1e-12))
        return r

    res["zero_shot"], res["recalibrated_no_refit"], res["refit"] = {}, {}, {}
    for L in L10:
        rv, rt = L.raw_scores(vbn), L.raw_scores(te)
        thr10 = budget_threshold(_d10_val_raw[L.name], BUDGET_DOMAIN)
        res["zero_shot"][L.name] = block(_d10_val_raw[L.name], rt, thr10)
        res["recalibrated_no_refit"][L.name] = block(rv, rt, budget_threshold(rv, BUDGET_DOMAIN))
        z = res["zero_shot"][L.name]
        log("  zero-shot", L.name, "FA %.4f" % z["fa_benign"], "macro9 %.3f macro9_auc %.3f" % (z["summary"]["macro9"], z["summary"]["macro9_auc"]),
            {k: round(v, 2) for k, v in z["detection"].items()})
    for L in build(chosen, "clean"):
        L.fit(trn)
        rv, rt = L.raw_scores(vbn), L.raw_scores(te)
        res["refit"][L.name] = block(rv, rt, budget_threshold(rv, BUDGET_DOMAIN))
        z = res["refit"][L.name]
        log("  refit", L.name, "FA %.4f" % z["fa_benign"], "macro9 %.3f macro9_auc %.3f" % (z["summary"]["macro9"], z["summary"]["macro9_auc"]),
            {k: round(v, 2) for k, v in z["detection"].items()})
    json.dump(res, open(os.path.join(OUT, "s5_d23.json"), "w"), indent=1)


_d10_val_raw = {}

if __name__ == "__main__":
    L10, chosen, d, X = run_d10()
    r10 = json.load(open(os.path.join(OUT, "s5_d10.json")))
    sig = r10["bot"]["_sig"]
    for L in L10:
        _d10_val_raw[L.name] = L.calibrator.sorted_
    del d
    run_d23(L10, chosen, sig)
