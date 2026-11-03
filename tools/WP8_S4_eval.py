"""WP8 S4: evaluate the v3 frozen network stack H and the v3.1 running-window candidates on D10 VALIDATION (V31_val), per the rules pre-registered in notes/WP8_v31.md (S4 section).

Inputs: ../data_extra/cache_v3/WP8/S4/D10_trainval_stage.pkl (train + val only; test rows are never loaded), results/WP4/s7_domain (frozen v3 domain, read only).
Steps (resumable: every candidate writes results/WP8/S4/parts/cand_<name>.npz first, finished parts are skipped):
  v3     frozen domain batch scores on the val mixed stream (+ re-derivation of its combined threshold from the rebuilt val benign stream = regression of the rebuilt cache)
  R5 R2 R1  running candidates (network/stream31.py, trw bin 5 / 2 / 1 min); calibrators and thresholds fitted on the benign val stream (audit file excluded), exactly as v3
  F1     information: v3 statistics, minute-final, trw bin 1 min (emission when the next minute arrives)
Outputs: results/WP8/S4/s4_val_candidates.json (detection per family, macro, FA, paired bootstrap vs v3, delay, selection), scores results/WP8/scores/S4/network_val.npz (rule 6 of the plan).
Usage: python -u -W ignore -I tools/WP8_S4_eval.py
"""
import json
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
import WP8_lib as W8  # noqa: E402

from common.metrics import budget_threshold  # noqa: E402
from network import l2a  # noqa: E402
from network.domain import NetworkDomain  # noqa: E402
from network.stream31 import LAYERS, Stream31  # noqa: E402

STAGE = os.path.join(ROOT, "..", "data_extra", "cache_v3", "WP8", "S4", "D10_trainval_stage.pkl")
FROZEN = os.path.join(ROOT, "results", "WP4", "s7_domain")
OUT = os.path.join(ROOT, "results", "WP8", "S4")
PARTS = os.path.join(OUT, "parts")
SCORES = os.path.join(ROOT, "results", "WP8", "scores", "S4")
EVAL11 = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator", "PortScan", "Web-BruteForce", "Web-XSS"]
AUDIT_FILE = "Infilteration"
BLOCK_S = 600
N_BOOT, SEED = 2000, 31
CANDS = [("R5", 5, False), ("R2", 2, False), ("R1", 1, False)]            # round 1
CANDS2 = [("RC5", 5, True), ("RC2", 2, True), ("RC1", 1, True)]                # round 2 (carry), pre-registered after round 1
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def load_val():
    W8.assert_not_h31([STAGE])
    d = pd.read_pickle(STAGE)
    assert set(d["split"].astype(str).unique()) <= {"train", "val"}
    d["audit"] = d["file"].astype(str).str.contains(AUDIT_FILE).to_numpy()
    d["fam"] = d["family"].astype(str)
    v = d[d["split"].astype(str) == "val"].copy()
    del d
    v = v.sort_values(["minute", "file", "row"], kind="stable").reset_index(drop=True)      # arrival order: minute resolution, then file row (the v3 order)
    v["fid"] = v["file"].astype(str).astype("category").cat.codes
    v["blk"] = v["day"].astype(str) + "|" + v["period"].astype(str)
    return v


def macro_of(alarm, fam, fams=EVAL11):
    return float(np.mean([alarm[fam == f].mean() for f in fams if (fam == f).any()]))


def summary(alarm, v):
    fam = v["fam"].to_numpy()
    ben = (fam == "BENIGN") & ~v["audit"].to_numpy()
    det = {f: float(alarm[fam == f].mean()) for f in EVAL11 if (fam == f).any()}
    return {"fa": float(alarm[ben].mean()), "fa_published_labels": float(alarm[fam == "BENIGN"].mean()), "detection": det, "n": {f: int((fam == f).sum()) for f in det},
            "macro": float(np.mean(list(det.values())))}


def block_counts(alarm, v):
    """per 10-min block counts for paired bootstrap: columns = benign, EVAL11 families."""
    fam = v["fam"].to_numpy()
    b = (v["day"].astype(str) + "|" + (v["t"].to_numpy(float) // BLOCK_S).astype("int64").astype(str)).to_numpy()
    bu, inv = np.unique(b, return_inverse=True)
    masks = [(fam == "BENIGN") & ~v["audit"].to_numpy()] + [fam == f for f in EVAL11]
    n = np.column_stack([np.bincount(inv, weights=m.astype(float), minlength=len(bu)) for m in masks])
    k = np.column_stack([np.bincount(inv, weights=(m & alarm).astype(float), minlength=len(bu)) for m in masks])
    return n, k


def paired_boot(n, ka, kb):
    """CI of macro(a) - macro(b) (points) and of the FA difference, bootstrap over 10-min blocks."""
    rng = np.random.RandomState(SEED)
    nb = n.shape[0]
    res = []
    for _ in range(N_BOOT // 250):
        idx = rng.randint(0, nb, (250, nb))
        N, A, B = n[idx].sum(1), ka[idx].sum(1), kb[idx].sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            da, db = A / N, B / N
        macro = np.nanmean(da[:, 1:] - db[:, 1:], axis=1)
        res.append(np.column_stack([macro, da[:, 0] - db[:, 0]]))
    R = np.concatenate(res)
    return {"macro_diff_ci": [float(np.percentile(R[:, 0], 2.5) * 100), float(np.percentile(R[:, 0], 97.5) * 100)],
            "fa_diff_ci": [float(np.percentile(R[:, 1], 2.5) * 100), float(np.percentile(R[:, 1], 97.5) * 100)]}


def emission_delay(v, bin_min):
    """Flow-level Evidence delay (s) of a window layer of bin_min minutes, as NetworkRunner behaves: a flow of bin b is emitted when the first flow of a later bin arrives (flush at block end)."""
    out = np.zeros(len(v))
    t = v["t"].to_numpy(float)
    b = (v["minute"].to_numpy() // bin_min).astype("int64")
    for _, ix in v.groupby("blk", sort=False).indices.items():
        bb, tt = b[ix], t[ix]
        ub, first = np.unique(bb, return_index=True)          # arrival order: bb nondecreasing
        nxt = np.r_[tt[first[1:]], tt[-1]]                     # emission time of bin ub[i] = ts of the first flow of the next present bin; last bin: flush at the last flow
        e = nxt[np.searchsorted(ub, bb)]
        out[ix] = np.maximum(e - tt, 0.0)
    return out


def delay_stats(d, fam):
    atk = fam != "BENIGN"
    f = lambda x: {"median_s": float(np.median(x)), "p95_s": float(np.percentile(x, 95)), "max_s": float(x.max()), "median_ticks": float(np.median(x) / 60), "max_ticks": float(x.max() / 60)}
    return {"all_flows": f(d), "attack_flows": f(d[atk])}


def alarm_lag(alarm, v, delay):
    """Per attack segment (block x family): seconds from the first attack flow to the first alarm AVAILABLE (flow ts + emission delay), None = never; share of the first-tick attack flows alarmed."""
    fam, t, mn = v["fam"].to_numpy(), v["t"].to_numpy(float), v["minute"].to_numpy()
    out = {}
    for f in EVAL11:
        lags, first, never = [], [], 0
        for _, ix in v[fam == f].groupby("blk", sort=False).indices.items():
            ii = np.flatnonzero(fam == f)[ix]
            t0, m0 = t[ii].min(), mn[ii].min()
            hit = alarm[ii]
            first.append(float(hit[mn[ii] == m0].mean()))
            if hit.any():
                lags.append(float((t[ii][hit] + delay[ii][hit]).min() - t0))
            else:
                never += 1
        out[f] = {"segments": len(lags) + never, "never": never, "median_lag_s": float(np.median(lags)) if lags else None, "first_tick_alarm_share": float(np.mean(first)) if first else None}
    ok = [x["median_lag_s"] for x in out.values() if x["median_lag_s"] is not None]
    return {"per_family": out, "median_of_family_medians_s": float(np.median(ok)) if ok else None, "mean_first_tick_alarm_share": float(np.mean([x["first_tick_alarm_share"] for x in out.values() if x["first_tick_alarm_share"] is not None]))}


def run_v3(v, dom):
    s, a, X = dom.score_arrays(v)
    ben = v[(v["fam"] == "BENIGN") & ~v["audit"]]
    thr_re = float(budget_threshold(dom.score_arrays(ben)[0], 0.01))
    return s, a, X, {"frozen_threshold": float(dom.comb.threshold), "rederived_threshold_from_rebuilt_val_benign": thr_re}


def run_cand(name, trw_bin, carry, v, vb, dom):
    p = os.path.join(PARTS, f"cand_{name}.npz")
    if os.path.exists(p):
        z = np.load(p)
        return z["s"], z["a"], z["X"], json.loads(str(z["info"]))
    S = Stream31.from_frozen(dom, trw_bin=trw_bin, carry=carry)
    t0 = time.time()
    S.calibrate(vb)
    s, a, X, raw = S.score_table(v)
    info = {"trw_bin_min": trw_bin, "carry": carry, "combined_threshold": S.comb_thr, "layer_thresholds": {k: float(x) for k, x in S.thr.items()}, "seconds": time.time() - t0}
    tmp = p + ".tmp.npz"
    np.savez_compressed(tmp, s=s.astype("float32"), a=a, X=X.astype("float32"), info=json.dumps(info))
    os.replace(tmp, p)
    S.save(os.path.join(PARTS, f"stream31_{name}.pkl"))
    return s, a, X, info


def run_f1(v, vb, dom):
    """Information: v3 statistics (final per cell), trw bin 1 min, recalibrated on the benign val stream."""
    by = {L.name: L for L in dom.layers}
    trw = l2a.Trw(W=1)
    layers = [by["net.tcp_flags"], by["net.scan"], trw, by["net.bruteforce"]]
    from common.calibration import ECDFCalibrator
    cols, thr = {}, {}
    for L in layers:
        rb = np.asarray(L.stream_scores(vb) if hasattr(L, "stream_scores") else L.raw_scores(vb), float)
        if L is by["net.tcp_flags"]:
            cal, th = L.calibrator, L.threshold
        else:
            cal = ECDFCalibrator().fit(rb)
            th = budget_threshold(cal.transform(rb), 0.01)
        cols[L.name] = (L, cal)
        thr[L.name] = th
    def comb(df):
        X = np.column_stack([cols[n][1].transform(np.asarray(cols[n][0].stream_scores(df) if hasattr(cols[n][0], "stream_scores") else cols[n][0].raw_scores(df), float)) for n in LAYERS])
        return X.max(axis=1)
    c_thr = budget_threshold(comb(vb), 0.01)
    s = comb(v)
    return s, s >= c_thr, {"combined_threshold": float(c_thr)}


def main():
    os.makedirs(PARTS, exist_ok=True)
    os.makedirs(SCORES, exist_ok=True)
    log("load val")
    v = load_val()
    vb = v[(v["fam"] == "BENIGN") & ~v["audit"]].reset_index(drop=True)
    fam = v["fam"].to_numpy()
    log("val flows", len(v), "benign headline", len(vb), "families", {f: int((fam == f).sum()) for f in EVAL11})
    dom = NetworkDomain.load(FROZEN)
    res = {"material": "D10 val (V31_val), mixed stream sorted (minute, file, row); benign headline = BENIGN minus the audited Infiltration file", "n_flows": int(len(v)), "n_benign_headline": int(len(vb)),
           "candidates": {}}
    s3, a3, X3, info3 = run_v3(v, dom)
    d3 = emission_delay(v, 5)
    res["candidates"]["v3"] = {**summary(a3, v), **info3, "delay_flow_level": delay_stats(d3, fam), "emission": "5-minute bin close (NetworkRunner)", "alarm_lag": alarm_lag(a3, v, d3)}
    log("v3", res["candidates"]["v3"]["macro"], res["candidates"]["v3"]["fa"], info3)
    n_b, k3 = block_counts(a3, v)
    scores = {"v3_score": s3.astype("float32"), "v3_alarm": a3}
    zero = np.zeros(len(v))
    for name, B, carry in CANDS + CANDS2:
        s, a, X, info = run_cand(name, B, carry, v, vb, dom)
        sm = summary(a, v)
        sm.update(info)
        sm["delay_flow_level"] = delay_stats(np.zeros(len(v)), fam)
        sm["emission"] = "flow arrival (running statistics)"
        sm["alarm_lag"] = alarm_lag(a, v, zero)
        _, k = block_counts(a, v)
        sm["paired_vs_v3"] = {"macro_diff_points": (sm["macro"] - res["candidates"]["v3"]["macro"]) * 100, **paired_boot(n_b, k, k3)}
        res["candidates"][name] = sm
        scores[f"{name}_score"], scores[f"{name}_alarm"] = s.astype("float32"), a
        scores[f"{name}_layers"] = X.astype("float32")
        log(name, sm["macro"], sm["fa"], sm["paired_vs_v3"])
    s, a, info = run_f1(v, vb, dom)
    sm = summary(a, v)
    sm.update(info)
    sm["delay_flow_level"] = delay_stats(emission_delay(v, 1), fam)
    sm["emission"] = "minute close"
    d1 = emission_delay(v, 1)
    sm["alarm_lag"] = alarm_lag(a, v, d1)
    _, k = block_counts(a, v)
    sm["paired_vs_v3"] = {"macro_diff_points": (sm["macro"] - res["candidates"]["v3"]["macro"]) * 100, **paired_boot(n_b, k, k3)}
    res["candidates"]["F1"] = sm
    scores["F1_score"], scores["F1_alarm"] = s.astype("float32"), a
    log("F1", sm["macro"], sm["fa"])
    # ---- pre-registered selection (notes/WP8_v31.md, S4): round 1 over R5 R2 R1, round 2 over RC5 RC2 RC1 and F1
    v3 = res["candidates"]["v3"]
    fa_bound = 1.0 if v3["fa"] * 100 <= 1.0 else v3["fa"] * 100 + 0.1

    def judge(names):
        sel = {}
        for name in names:
            c = res["candidates"][name]
            d = c["delay_flow_level"]["all_flows"]
            sel[name] = {"N1_delay": bool(d["median_s"] <= 60 and d["max_s"] <= 120), "N2_fa": bool(c["fa"] * 100 <= fa_bound), "N2_macro": bool(c["macro"] * 100 >= v3["macro"] * 100 - 3.0)}
            sel[name]["feasible"] = all(sel[name].values())
        return sel

    sel1 = judge([n for n, _, _ in CANDS])
    feas1 = [n for n, _, _ in CANDS if sel1[n]["feasible"]]
    order2 = ["RC5", "RC2", "RC1", "F1"]
    sel2 = judge(order2)
    feas2 = [n for n in order2 if sel2[n]["feasible"]]
    chosen2 = None
    if feas2:
        med = {n: res["candidates"][n]["delay_flow_level"]["all_flows"]["median_s"] for n in feas2}
        low = [n for n in feas2 if med[n] == min(med.values())]
        best = max(res["candidates"][n]["macro"] for n in low)
        near = [n for n in low if res["candidates"][n]["macro"] >= best - 0.005]
        chosen2 = [n for n in order2 if n in near][0]
    res["selection"] = {"fa_bound_points": fa_bound, "round1": {"per_candidate": sel1, "feasible": feas1}, "round2": {"per_candidate": sel2, "feasible": feas2, "chosen": chosen2}}
    log("selection", res["selection"])
    meta = np.column_stack([v["fid"].to_numpy(), v["row"].to_numpy(), v["minute"].to_numpy()])
    np.savez_compressed(os.path.join(SCORES, "network_val.npz"), t=v["t"].to_numpy(float), meta_fid_row_minute=meta, fam=fam.astype(str), audit=v["audit"].to_numpy(), block=v["blk"].astype(str).to_numpy(),
                        **scores)
    json.dump(res, open(os.path.join(OUT, "s4_val_candidates.json"), "w"), indent=1)
    log("done")


if __name__ == "__main__":
    main()
