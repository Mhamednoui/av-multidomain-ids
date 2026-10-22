"""WP4 S4 run: L2b beaconing (network/l2b.py) on D10 and D23 Tue-20-02. Usage: python -u -W ignore tools/WP4_S4_run.py smoke|verdict
  smoke   : the "test" side is the VALIDATION split (pipeline check); writes results/WP4/smoke/
  verdict : the ONE run on test; writes results/WP4/s4_*.json
Settings fixed on validation (notes 2026-10-22 S4): WIN 64, N_MIN 6, one benign table (no port conditioning), score = max(cv, mad, tol, acf); L2a windows from s3_dev_val.json.
Fit on benign-only TRAIN stream, calibration (flow unit via Layer.calibrate, pair-window unit via a raw threshold; tie-safe 1%) on benign-only VAL stream, audited Infiltration file excluded
from fit / calibration / headline FA as in S3. Harness: tcp_flags + 5 L2a (+ beacon), logistic combiner on a subsample drawn AFTER the stream features are computed."""
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN, SEED
from common.evaluate import EvalSet, evaluate_domain
from common.metrics import budget_threshold
from network import l1, l2a, l2b
from tools.WP4_S3_lib import RES, add_scores, cell_max, fit_calibrate, flow_eval, load, log, stream, subsample, window_eval

MODE = sys.argv[1] if len(sys.argv) > 1 else "smoke"
assert MODE in ("smoke", "verdict")
TEST = "val" if MODE == "smoke" else "test"
OUT = RES if MODE == "verdict" else os.path.join(RES, "smoke")
os.makedirs(OUT, exist_ok=True)
N_BEN, N_FAM = 150_000, 20_000
L2A = ["net.scan", "net.trw", "net.bruteforce", "net.dos_rate", "net.slow"]


def families_of(df):
    return sorted(set(df["family"].astype(str)) - {"BENIGN"})


def mark_in_final(d):
    B = os.path.join(os.path.dirname(__file__), "..", "..", "data_extra", "cache_v3", "WP4", "D10", "final")
    keys = pd.concat([pd.read_pickle(f, compression="gzip")[["file", "row"]] for f in glob.glob(os.path.join(B, "*.pkl"))], ignore_index=True)
    keys["k"] = keys["file"].astype(str) + "|" + keys["row"].astype(str)
    return (d["file"].astype(str) + "|" + d["row"].astype(str)).isin(set(keys["k"])).to_numpy()


def beacon_layers(tr, vb):
    """Main layer (fit + both calibrations) and the single-statistic ablation layers (tables shared, own calibration)."""
    B = l2b.Beacon()
    fit_calibrate([B], tr, vb)
    subs = {s: l2b.BeaconStat(s) for s in l2b.STATS}
    return B, subs


def add_beacon(df, B, subs):
    f = B.feats(df)
    sc = B.stat_scores(f)
    df[B.score_col] = np.max(np.vstack([sc[k] for k in l2b.PHASE]), axis=0)
    for s, S in subs.items():
        df[S.score_col] = sc[s]
    df["_testable"] = (f["_nact"] >= B.n_min) & (f["_med"] >= 2)
    df["_med"] = f["_med"]
    df["_nact"] = f["_nact"]


def calibrate_subs(subs, vb):
    for S in subs.values():
        S.calibrate(vb, BUDGET_DOMAIN)
        cm = cell_max(S.cells(vb), vb[S.score_col].to_numpy(float))
        S.win_threshold = budget_threshold(cm[1], BUDGET_DOMAIN)


def bot_pairs(L, df):
    """Per Bot group (src, dst, port) with >= 10 Bot flows: flows, alarmed flows, first-alarm delay (min) from the group's first Bot flow."""
    cal = L.calibrator.transform(df[L.score_col].to_numpy(float))
    al = cal >= L.threshold
    fam = df["family"].astype(str).to_numpy()
    m = fam == "Bot"
    b = pd.DataFrame({"s": df["src_id"].to_numpy()[m], "d": df["dst_id"].to_numpy()[m], "p": df["dst_port"].to_numpy()[m],
                      "min": df["minute"].to_numpy()[m], "al": al[m], "tst": df["_testable"].to_numpy()[m]})
    rows = []
    for (s, d_, p), g in b.groupby(["s", "d", "p"]):
        if len(g) < 10:
            continue
        hit = g.loc[g["al"], "min"]
        rows.append({"flows": int(len(g)), "alarmed": int(g["al"].sum()), "testable": int(g["tst"].sum()),
                     "first_alarm_delay_min": float(hit.min() - g["min"].min()) if len(hit) else None,
                     "span_min": float(g["min"].max() - g["min"].min())})
    return rows


def extra_eval(L, df, fams):
    fe = flow_eval(L, df, fams)
    cal = L.calibrator.transform(df[L.score_col].to_numpy(float))
    al = cal >= L.threshold
    fam = df["family"].astype(str).to_numpy()
    ben = (fam == "BENIGN") & ~df["audit"].to_numpy()
    tst = df["_testable"].to_numpy()
    bot = fam == "Bot"
    ex = {"testable_share_benign": float(tst[ben].mean()), "fa_among_testable_benign": float(al[ben & tst].mean()),
          "bot_testable_share": float(tst[bot].mean()) if bot.any() else None,
          "bot_detection_among_testable": float(al[bot & tst].mean()) if (bot & tst).any() else None,
          "bot_pairs": bot_pairs(L, df)}
    return fe, ex


def evalset(layers, s):
    ev = {L.name: L.score(s) for L in layers}
    y = (s["family"].astype(str) != "BENIGN").to_numpy().astype(int)
    at = np.where(y == 1, s["family"].astype(str).to_numpy(), "normal")
    return EvalSet(evidence=ev, y=y, attack_type=at, group=s["day"].astype(str).to_numpy(), t=np.nan_to_num(s["t"].to_numpy()))


def sub(es, names):
    return EvalSet(evidence={n: es.evidence[n] for n in names}, y=es.y, attack_type=es.attack_type, group=es.group, t=es.t)


def or_view(layers, df, fams):
    al = np.zeros(len(df), bool)
    for L in layers:
        al |= L.calibrator.transform(df[L.score_col].to_numpy(float)) >= L.threshold
    fam = df["family"].astype(str).to_numpy()
    ben = (fam == "BENIGN") & ~df["audit"].to_numpy()
    return {"fa_benign": float(al[ben].mean()), "fa_benign_published_labels": float(al[fam == "BENIGN"].mean()),
            "detection": {f: float(al[fam == f].mean()) for f in fams if (fam == f).any()}}


def split_counts(d):
    out = {}
    b = d[d["family"].astype(str) == "Bot"]
    for sp in ("train", "val", "test", "gap"):
        x = b[b["split"].astype(str) == sp]
        g = x.groupby(["src_id", "dst_id", "dst_port"]).size()
        out[sp] = {"flows": int(len(x)), "groups": int(len(g)), "groups_ge10_flows": int((g >= 10).sum()),
                   "flows_in_groups_ge10": int(g[g >= 10].sum()), "active_minutes": int(x["minute"].nunique())}
    return out


def run_d10():
    log("== D10", MODE)
    dev = json.load(open(os.path.join(RES, "s3_dev_val.json")))["chosen"]
    d = load("D10")
    d["in_final"] = mark_in_final(d)
    res = {"mode": MODE, "test_side": TEST, "bot_split_counts": split_counts(d)}
    log(res["bot_split_counts"])
    tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
    te = vm if MODE == "smoke" else stream(d, "test")
    ben_pos = np.flatnonzero(((vm["family"].astype(str) == "BENIGN") & ~vm["audit"]).to_numpy())
    del d
    l2 = l2a.all_layers(dev)
    fit_calibrate(l2, tr, vb)
    B, subs = beacon_layers(tr, vb)
    add_beacon(vb, B, subs)
    calibrate_subs(subs, vb)
    add_scores(vb, l2)
    add_scores(vm, l2)
    add_beacon(vm, B, subs)
    if MODE == "verdict":
        add_scores(te, l2)
        add_beacon(te, B, subs)
    else:
        te = vm
    fams = families_of(te)
    res["families"] = fams
    res["n"] = {"train_benign": len(tr), "val_benign": len(vb), "test": len(te)}
    res["beacon_win_threshold"] = B.win_threshold
    res["beacon_flow_threshold"] = B.threshold
    res["layers"] = {}
    for L in [B] + list(subs.values()):
        fe, ex = extra_eval(L, te, fams)
        we = window_eval(L, te, fams)
        res["layers"][L.name] = {"flow": fe, "window": we, "extra": ex}
        log("  ", L.name, "FA %.4f (pub %.4f) win FA %.4f" % (fe["fa_benign"], fe["fa_benign_published_labels"], we["fa_benign_cells"]),
            "Bot %.3f" % fe["detection"].get("Bot", -1), "win Bot", we["detection"].get("Bot"), "testable", round(ex["testable_share_benign"], 4),
            "FA|testable %.3f" % ex["fa_among_testable_benign"])
    log("  Bot pairs", res["layers"]["net.beacon"]["extra"]["bot_pairs"])
    fam = te["family"].astype(str).to_numpy()
    cal = B.calibrator.transform(te[B.score_col].to_numpy(float)) >= B.threshold
    m = (fam == "Bot") & te["in_final"].to_numpy()
    res["bot_dedup_subset"] = {"flows": int(m.sum()), "detection": float(cal[m].mean()) if m.any() else None}
    res["or_l2a"] = or_view(l2, te, fams)
    res["or_l2a_beacon"] = or_view(l2 + [B], te, fams)
    log("  OR l2a", {k: round(v, 2) for k, v in res["or_l2a"]["detection"].items()}, "FA %.4f" % res["or_l2a"]["fa_benign"])
    log("  OR l2a+beacon", {k: round(v, 2) for k, v in res["or_l2a_beacon"]["detection"].items()}, "FA %.4f" % res["or_l2a_beacon"]["fa_benign"])
    # ---- harness
    tf = l1.TcpFlags().fit(tr)
    tf.calibrate(vb, BUDGET_DOMAIN)
    tf.score_col = "s_net.tcp_flags"
    vm_h = vm.copy()
    for L in l2 + [B]:
        vm_h.loc[vm_h.index[ben_pos], L.score_col] = vb[L.score_col].to_numpy()
    for X in (te, vm_h):
        X[tf.score_col] = tf.raw_scores(X)
    layers_h = l2 + [tf, B]
    val_h = vm_h[~vm_h["audit"].to_numpy()]
    test_h = te[~te["audit"].to_numpy()]
    vs = subsample(val_h, N_BEN, N_FAM, SEED).sort_values("t", kind="stable")
    ts = subsample(test_h, N_BEN, N_FAM, SEED).sort_values("t", kind="stable")
    res["subsample"] = {"val": len(vs), "test": len(ts)}
    ev_v, ev_t = evalset(layers_h, vs), evalset(layers_h, ts)
    cfg = (("l1_l2a", ["net.tcp_flags"] + L2A), ("l1_l2a_beacon", ["net.tcp_flags"] + L2A + ["net.beacon"]),
           ("l2a_beacon", L2A + ["net.beacon"]), ("beacon_only", ["net.beacon"]), ("l1_beacon", ["net.tcp_flags", "net.beacon"]))
    for nm, names in cfg:
        r = evaluate_domain("s4_d10_" + nm, sub(ev_v, names), sub(ev_t, names), wp="WP4", out_dir=OUT)
        res["harness_" + nm] = {"combined": r["combined"], "ablation": r["ablation"]}
        log("  harness", nm, "combined FA %.4f det %.4f" % (r["combined"]["false_alarm_rate"], r["combined"]["detection"]),
            {k: round(v, 2) for k, v in r["combined"]["detection_by_attack"].items()})
    json.dump(res, open(os.path.join(OUT, "s4_d10.json"), "w"), indent=1)
    return B


def run_d23(B10):
    log("== D23 Tue-20-02", MODE)
    d = load("D23tue")
    tr, vb, vm = stream(d, "train", True), stream(d, "val", True), stream(d, "val")
    te = vm if MODE == "smoke" else stream(d, "test")
    del d
    fams = families_of(te)
    res = {"mode": MODE, "test_side": TEST, "families": fams, "n_test": len(te),
           "note": "D23 Fri-02-03 (Bot) has no addresses (src_ip / dst_ip 100% NaN): not evaluable"}
    subs = {s: l2b.BeaconStat(s) for s in l2b.STATS}
    add_beacon(te, B10, subs)
    res["transfer"] = {"flow": flow_eval(B10, te, fams), "window": window_eval(B10, te, fams)}
    res["transfer"]["testable_share_benign"] = float(te.loc[te["family"].astype(str) == "BENIGN", "_testable"].mean())
    log("  transfer FA %.4f win FA %.4f testable %.4f" % (res["transfer"]["flow"]["fa_benign"], res["transfer"]["window"]["fa_benign_cells"],
                                                       res["transfer"]["testable_share_benign"]),
        {k: round(v, 3) for k, v in res["transfer"]["flow"]["detection"].items()})
    B2, subs2 = beacon_layers(tr, vb)
    add_beacon(te, B2, subs2)
    res["refit"] = {"flow": flow_eval(B2, te, fams), "window": window_eval(B2, te, fams)}
    log("  refit FA %.4f win FA %.4f" % (res["refit"]["flow"]["fa_benign"], res["refit"]["window"]["fa_benign_cells"]),
        {k: round(v, 3) for k, v in res["refit"]["flow"]["detection"].items()})
    json.dump(res, open(os.path.join(OUT, "s4_d23.json"), "w"), indent=1)


if __name__ == "__main__":
    B = run_d10()
    run_d23(B)
