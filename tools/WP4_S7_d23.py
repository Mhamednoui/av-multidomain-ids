"""WP4 S7 cross-dataset run on D23 (CSE-CIC-IDS2018, the whole dataset is the external test). Usage: python -u -W ignore tools/WP4_S7_d23.py
ZERO-SHOT (D10-fitted layers, D10 calibrators, D10 frozen H combiner, nothing refitted): tcp_flags on every D23 day (flow-level); scan / trw / bruteforce need IPs: only Tue-20-02 (stage stream, full
multiplicity). Reported for H and for H without tcp_flags (pre-declared in the notes: the flag columns differ between the two CICFlowMeter runs).
ON-NETWORK (target warm-up = benign train split, calibration = benign val split, scored = test split): Tue-20-02 O = tcp_flags + scan + trw + bruteforce + dos_rate + service + AE;
all days O-flow = tcp_flags + service + AE. Combiner = the method selected on D10 validation for O (noisy_or, no attack label), threshold = 1% of the target's benign validation scores.
Rows: the S5 fixed-seed sample of cleaned (dedup) flows (S7/d23_eval.pkl, with file / row / time); L2a scores come from the full Tue stage stream and are looked up by (file, row).
Output results/WP4/s7_d23.json."""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common import combiner as cb
from common.config import BUDGET_DOMAIN
from common.metrics import budget_threshold
from network import l1, l2a, l3
from tools.WP4_S3_lib import add_scores, fit_calibrate, flow_eval, load, stream
from tools.WP4_S7_lib import EVAL23, RES, S7, Scorer, comb_alarm, load_combiner, log

TUE = "Thues"
L2A_IP = ["net.scan", "net.trw", "net.bruteforce"]
COLS = {n: "s_" + n for n in ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.slow", "net.l3_service", "net.l3_ae"]}


def key(df):
    return (df["file"].astype(str) + "|" + df["row"].astype(str)).to_numpy()


def lookup(sample, stream_df, cols):
    """Copy the score columns of the stage-stream rows to the sample rows (by file|row)."""
    idx = pd.Index(key(stream_df)).get_indexer(key(sample))
    ok = idx >= 0
    out = sample.copy()
    for c in cols:
        v = np.full(len(sample), np.nan)
        v[ok] = stream_df[c].to_numpy(float)[idx[ok]]
        out[c] = v
    return out, int(ok.sum())


def noisy_or_alarm(Xv, Xt):
    sv, st = cb.noisy_or_score(Xv), cb.noisy_or_score(Xt)
    thr = budget_threshold(sv, BUDGET_DOMAIN)
    return st, st >= thr, float(thr)


def main():
    s = pd.read_pickle(os.path.join(S7, "d23_eval.pkl"))
    s["fam"] = s["family"].astype(str)
    s["audit"] = False
    s["period"] = 0
    s = s[s["t"].notna()].reset_index(drop=True)
    cal = pickle.load(open(os.path.join(S7, "cal.pkl"), "rb"))
    combs = pickle.load(open(os.path.join(S7, "combiners.pkl"), "rb"))
    dev3 = json.load(open(os.path.join(RES, "s3_dev_val.json")))["chosen"]
    dev5 = json.load(open(os.path.join(RES, "s5_dev_val.json")))["chosen"]
    res = {"n_sample": {sp: int((s["split"] == sp).sum()) for sp in ("train", "val", "test")}, "method_O_d10": combs["O"]["method"], "method_H_d10": combs["H"]["method"]}
    # ---------------- D10 layers (refit; thresholds checked against the frozen calibration)
    d10 = load("D10")
    tr, vb = stream(d10, "train", True), stream(d10, "val", True)
    del d10
    l2 = l2a.all_layers(dev3)
    fit_calibrate(l2, tr, vb)
    tf10 = l1.TcpFlags().fit(tr)
    tf10.calibrate(vb, BUDGET_DOMAIN)
    chk = {L.name: (float(L.threshold), float(cal[L.name][1])) for L in l2 + [tf10]}
    res["d10_threshold_check"] = chk
    assert all(abs(a - b) < 1e-9 for a, b in chk.values()), chk
    del tr, vb
    log("D10 layers refit; thresholds equal to the frozen calibration")
    # ---------------- zero-shot, flow-level tcp_flags on every D23 day (sample rows)
    st = s[s["split"] == "test"].reset_index(drop=True)
    st["s_net.tcp_flags"] = tf10.raw_scores(st)
    sc = Scorer(st, "fam", families=EVAL23)
    al_tf = cal["net.tcp_flags"][0].transform(st["s_net.tcp_flags"].to_numpy(float)) >= cal["net.tcp_flags"][1]
    r = sc.summary(al_tf, ci=True)
    r["fa_by_day"] = {k: float(al_tf[sc.ben & (st["day"].to_numpy() == k)].mean()) for k in sorted(st["day"].unique()) if (sc.ben & (st["day"].to_numpy() == k)).any()}
    res["zero_shot_tcp_flags_all_days"] = r
    log("zero-shot tcp_flags all days FA %.4f macro %.3f" % (r["fa"], r["macro"]), {k: round(v, 3) for k, v in r["fa_by_day"].items()})
    # ---------------- Tue-20-02 stage streams
    d23 = load("D23tue")
    tr, vb, te = stream(d23, "train", True), stream(d23, "val", True), stream(d23, "test")
    del d23
    log("Tue streams", len(tr), len(vb), len(te))
    # ZERO-SHOT on Tue
    add_scores(te, l2, same_network=False)
    te["s_net.tcp_flags"] = tf10.raw_scores(te)
    te["fam"] = te["family"].astype(str)
    stue = st[st["file"].str.startswith(TUE)].reset_index(drop=True)
    stue, nok = lookup(stue, te, [COLS[n] for n in L2A_IP] + ["s_net.tcp_flags"])
    log("Tue test sample rows", len(stue), "found in stage test", nok)
    zs = {"n_sample_rows": int(len(stue)), "found_in_stage": nok}
    CH = load_combiner(combs["H"])
    CL = load_combiner(combs["H all-but net.tcp_flags"])
    for view, df in (("sample_rows", stue), ("stage_stream", te)):
        scv = Scorer(df, "fam", families=EVAL23)
        v = {}
        for nm, C in (("H", CH), ("H without tcp_flags", CL)):
            s_, al = comb_alarm(C, df, cal)
            rr = scv.summary(al, ci=True)
            rr["auc"] = scv.auc_all(s_)
            rr["method"] = C.method
            v[nm] = rr
            log(" zero-shot Tue %s %-20s FA %.4f [%.4f,%.4f] LOIC %.3f" % (view, nm, rr["fa"], *rr["fa_ci"], rr["detection"].get("DDoS-LOIC-HTTP", float("nan"))))
        v["layers_alone"] = {}
        for n in L2A_IP + ["net.tcp_flags"]:
            al = cal[n][0].transform(df[COLS[n]].to_numpy(float)) >= cal[n][1]
            rr = scv.summary(al, ci=False)
            v["layers_alone"][n] = {"fa": rr["fa"], "detection": rr["detection"]}
        zs[view] = v
    res["zero_shot_tue"] = zs
    # ---------------- ON-NETWORK layers
    # flow-level layers on the sample: warm-up = benign train sample (all days), calibration = benign val sample
    trs = s[(s["split"] == "train") & (s["fam"] == "BENIGN")].reset_index(drop=True)
    vas = s[(s["split"] == "val") & (s["fam"] == "BENIGN")].reset_index(drop=True)
    tf = l1.TcpFlags().fit(trs)
    tf.calibrate(vas, BUDGET_DOMAIN)
    flow = {"net.tcp_flags": tf}
    for key_, cls in (("service", l3.ServiceProfile), ("ae", l3.AutoEncoder)):
        kw = {k: (tuple(v) if isinstance(v, list) else v) for k, v in dev5[key_]["params"].items()}
        L = cls(feature_set_name="clean", **kw)
        L.fit(trs)
        L.calibrate(vas, BUDGET_DOMAIN)
        flow[L.name] = L
        log("refit", L.name)
    cal_on = {n: (L.calibrator, float(L.threshold)) for n, L in flow.items()}
    for df in (s,):
        for n, L in flow.items():
            df[COLS[n]] = L.raw_scores(df)
    # L2a on Tue (refit on the Tue warm-up)
    layers = l2a.all_layers(dev3)
    fit_calibrate(layers, tr, vb)
    add_scores(vb, layers)
    add_scores(te, layers)
    for L in layers:
        cal_on[L.name] = (L.calibrator, float(L.threshold))
    vtue = s[(s["split"] == "val") & (s["fam"] == "BENIGN") & s["file"].str.startswith(TUE)].reset_index(drop=True)
    ttue = s[(s["split"] == "test") & s["file"].str.startswith(TUE)].reset_index(drop=True)
    l2cols = [COLS[L.name] for L in layers]
    vtue, nv = lookup(vtue, vb, l2cols)
    ttue, nt = lookup(ttue, te, l2cols)
    log("on-network Tue rows found: val", nv, "of", len(vtue), "test", nt, "of", len(ttue))
    on = {"warm_up": {"tue_train_benign_flows": int(len(tr)), "tue_val_benign_flows": int(len(vb)), "sample_train_benign": int(len(trs)), "sample_val_benign": int(len(vas)),
                      "tue_warmup_hours": float((tr["t"].max() - tr["t"].min()) / 3600)}}

    def cal_mat(df, names):
        return np.column_stack([cal_on[n][0].transform(df[COLS[n]].to_numpy(float)) for n in names])

    method = combs["O"]["method"]
    assert method == "noisy_or", method        # no attack label needed on a new network; other methods would need transferred weights
    O_tue = ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.l3_service", "net.l3_ae"]
    O_flow = ["net.tcp_flags", "net.l3_service", "net.l3_ae"]
    sc_t = Scorer(ttue, "fam", families=EVAL23)
    on["tue"] = {"layers_alone": {}, "all_but": {}}
    for n in O_tue:
        al = cal_mat(ttue, [n])[:, 0] >= cal_on[n][1]
        r = sc_t.summary(al, ci=True)
        on["tue"]["layers_alone"][n] = r
    sv, al, thr = noisy_or_alarm(cal_mat(vtue, O_tue), cal_mat(ttue, O_tue))
    r = sc_t.summary(al, ci=True)
    r["auc"] = sc_t.auc_all(sv)
    r["threshold"] = thr
    on["tue"]["O"] = r
    log(" on-network Tue O FA %.4f [%.4f,%.4f] LOIC %.3f" % (r["fa"], *r["fa_ci"], r["detection"].get("DDoS-LOIC-HTTP", float("nan"))))
    for n in O_tue:
        rest = [m for m in O_tue if m != n]
        sv_, al_, _ = noisy_or_alarm(cal_mat(vtue, rest), cal_mat(ttue, rest))
        rr = sc_t.summary(al_, ci=False)
        on["tue"]["all_but"][n] = {"fa": rr["fa"], "detection": rr["detection"]}
    sv, al, thr = noisy_or_alarm(cal_mat(vtue, O_tue[:4]), cal_mat(ttue, O_tue[:4]))
    on["tue"]["H_on_network"] = sc_t.summary(al, ci=True)
    # flow-level O on every day
    vall = s[(s["split"] == "val") & (s["fam"] == "BENIGN")].reset_index(drop=True)
    tall = s[s["split"] == "test"].reset_index(drop=True)
    sc_a = Scorer(tall, "fam", families=EVAL23)
    on["flow_all_days"] = {"layers_alone": {}}
    for n in O_flow:
        al = cal_mat(tall, [n])[:, 0] >= cal_on[n][1]
        on["flow_all_days"]["layers_alone"][n] = sc_a.summary(al, ci=True)
    sv, al, thr = noisy_or_alarm(cal_mat(vall, O_flow), cal_mat(tall, O_flow))
    r = sc_a.summary(al, ci=True)
    r["auc"] = sc_a.auc_all(sv)
    r["threshold"] = thr
    day = tall["day"].to_numpy()
    r["fa_by_day"] = {k: float(al[sc_a.ben & (day == k)].mean()) for k in sorted(set(day)) if (sc_a.ben & (day == k)).any()}
    r["detection_by_day_family"] = {f"{k}|{f}": float(al[(day == k) & (sc_a.fam == f)].mean()) for k in sorted(set(day)) for f in EVAL23 if ((day == k) & (sc_a.fam == f)).any()}
    on["flow_all_days"]["O_flow"] = r
    log(" on-network O-flow FA %.4f macro %.3f" % (r["fa"], r["macro"]), {k: round(v, 3) for k, v in r["detection"].items()})
    res["on_network"] = on
    # ---------------- dos_rate warm-up length on D23 Tue (information, pre-declared fractions)
    wu = {}
    mins = np.sort(tr["minute"].unique())
    for frac in (0.1, 0.25, 0.5, 1.0):
        cut = mins[max(int(len(mins) * frac) - 1, 0)]
        sub = tr[tr["minute"] <= cut].reset_index(drop=True)
        L = l2a.DosRate(W=dev3.get("net.dos_rate", 1))
        fit_calibrate([L], sub, vb)
        te[L.score_col] = L.stream_scores(te)
        fe = flow_eval(L, te.assign(audit=False), ["DDoS-LOIC-HTTP"])
        wu[str(frac)] = {"hours": float((sub["t"].max() - sub["t"].min()) / 3600), "flows": int(len(sub)), "known_destinations": int(len(L.ids)), "fa_benign_test": fe["fa_benign"],
                         "detection_loic": fe["detection"].get("DDoS-LOIC-HTTP"), "auc": fe["auc"]}
        log(" D23 warm-up", frac, wu[str(frac)])
    res["dos_rate_warmup_d23_tue"] = wu
    json.dump(res, open(os.path.join(RES, "s7_d23.json"), "w"), indent=1)
    log("saved s7_d23.json")


if __name__ == "__main__":
    main()
