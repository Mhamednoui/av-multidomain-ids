"""WP2 S6: ROAD report for L4 (validation and out-of-fold only; ROAD test is never read).
Reads ../data_extra/WP2_S6_cache/road_run (tools/WP2_S6_road.py) -> results/WP2/s6_road.json, s6_road_tables.md.
Sections: P1 (seen families, val thresholds), OOF (unseen families, pooled OOF thresholds), per-ambient FA, reverse-bit windows,
ablation against L1 + L2b relations-only + L3 on the 11 validation captures, Car-Hacking-trained model on ROAD validation.
Usage: python -u -W ignore tools/WP2_S6_road_report.py
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l1 as L
from can import l1_exp as E
from can import l2b_signals as Z
from can import l4_exp as X
from can import l4_features as G
from common.calibration import ECDFCalibrator
from common.config import DATA_EXTRA, RESULTS
from common.metrics import budget_threshold
from WP2_S4_run import attack_names, sparse_load
from WP2_S5_eval import l3_arrays
from WP2_S5_report import SKIP_SEC, l2b_calibration
from WP2_S5_eval import calib, calib_d, loco_pool, CACHE as C5
from WP2_S5_run import LOCO, VARIANTS as V5, vname
from WP2_S6_cache import load
import WP2_S6_road as R

RUN = R.RUN
OUT = RESULTS / "WP2"
BUD = 0.01
MODELS = ["t", "p"]
NM = {"t": "L4 timing", "p": "L4 payload"}


def pct(x):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.1f}%"


def cap_rows(tbl, k, vi, thr):
    """Per-capture dict from a window table (y, clean, w_end, fi) at threshold thr."""
    out = {}
    for g, d in tbl.groupby("group", sort=False):
        al = d[f"{k}{vi}"].to_numpy() >= thr
        y = (d["y"] == 1).to_numpy()
        cl = d["clean"].to_numpy() & ~y
        r = {"attack_windows": int(y.sum()), "clean_windows": int(cl.sum()), "false_alerts_clean": int(al[cl].sum()),
             "fa_clean": float(al[cl].mean()) if cl.any() else None}
        if y.any():
            hit = np.flatnonzero(al & y)
            r.update(detected=bool(len(hit)), window_recall=float(al[y].mean()),
                     delay_s=float(max(d["w_end"].to_numpy()[hit[0]] - d["fi"].iloc[0], 0.0)) if len(hit) else None)
        out[g] = r
    return out


def family_of(name):
    return R.fam_of(name)


def by_family(caps_res):
    """detected / total per family and kind (original vs masquerade)."""
    out = {}
    for g, r in caps_res.items():
        if "detected" not in r:
            continue
        key = f"{family_of(g)}{'_masq' if g.endswith('_masquerade') else ''}"
        o = out.setdefault(key, {"detected": 0, "n": 0, "recall": []})
        o["n"] += 1
        o["detected"] += int(r["detected"])
        o["recall"].append(r["window_recall"])
    for o in out.values():
        o["mean_window_recall"] = float(np.mean(o.pop("recall")))
    return out


def l1_alarms_val():
    v = pd.read_csv(OUT / "s3_run1_frozen" / "s3_road_windows_val.csv.gz")
    cols = [c for c in v.columns if c.startswith("raw_can.l1_") and "l2a" not in c]
    cl = v["clean"].astype(bool) & (v["y"] == 0)
    al = np.zeros(len(v), bool)
    for c in cols:
        cal = ECDFCalibrator().fit(v.loc[cl, c].to_numpy())
        thr = budget_threshold(cal.transform(v.loc[cl, c].to_numpy()), BUD)
        al |= cal.transform(v[c].to_numpy()) >= thr
    return v.assign(l1_alarm=al, sec=(v["wkey"] % 10 ** 7).astype(int))[["group", "sec", "l1_alarm"]]


def base_table(names):
    """Per val capture: sec, valid (S5: grid ok and second >= 4), a1 (L1), a2 (L2b rel.), a3 (L3 = L3c | L3d)."""
    key = vname(V5[5])
    wsl, fsl, _ = loco_pool(key)
    wc, fc = calib(wsl, fsl)
    wsd, fsd, _ = loco_pool("d")
    wd, fd = calib_d(wsd, fsd)
    w2, _ = l2b_calibration()
    l1 = l1_alarms_val()
    rows = []
    for c in names:
        grp = "loco" if c.startswith("ambient") else "attack"
        Wt, wsc, ok, _ = l3_arrays(c, grp, key)
        _, wsd_, _, _ = l3_arrays(c, grp, "d")
        sec = np.floor(Wt["tm"][Wt["st"]]).astype(int)
        valid = ok & (sec >= SKIP_SEC)
        a3 = wc.alarms(wsc) | wd.alarms(wsd_)
        a2 = w2.alarms(Z.window_max(Z.combine(sparse_load(C5 / ("l2b_" + grp) / (c + ".npz"))), Wt["st"]))
        df = pd.DataFrame({"group": c, "sec": sec, "valid": valid, "a2": a2, "a3": a3})
        df = df.merge(l1, on=["group", "sec"], how="left")
        df["a1"] = df["l1_alarm"].fillna(False).to_numpy(bool)
        rows.append(df.drop(columns="l1_alarm"))
    return pd.concat(rows, ignore_index=True)


def main():
    info = json.load(open(RUN / "p1_info.json"))
    codes = E.AttCodes()
    codes.names = list(info["codes"])
    res = {"notes": "ROAD test captures are not read in S6", "p1": {}, "oof": {}}
    caps_ = R.caps_table()
    cnt = []
    for n in caps_.loc[caps_["part"] == "val", "name"]:
        d = load("road", n)
        F = X.cap_F(d, codes, 0, E.lead_clean(d["t"], d["label"]))
        cnt.append(pd.DataFrame({"y": L.window_reduce(F, F["label"]), "clean": L.window_reduce(F, F["clean"].astype(np.int8), "min").astype(bool),
                                 "nf": np.diff(np.r_[F["ws"], len(F["wo"])])}))
    res["count_auc_reference_val"] = X.count_auc(pd.concat(cnt, ignore_index=True))
    res["shuffle"] = json.load(open(OUT / "s6_road_shuffle.json")) if (OUT / "s6_road_shuffle.json").exists() else None
    # ---------------- P1
    p1 = pd.read_pickle(RUN / "p1_windows.pkl")
    p1f = pickle.load(open(RUN / "p1_frames.pkl", "rb"))
    chosen = {}
    for k in MODELS:
        s = X.select_variant(p1, k, codes)
        vi = s["chosen"]
        chosen[k] = vi
        thr = s["variants"][str(vi)]["threshold"]
        caps = cap_rows(p1, k, vi, thr)
        cl_fr = np.concatenate([p1f[g]["clean"] & (p1f[g]["y"] == 0) for g in p1f])
        fr_p = np.concatenate([p1f[g][k] for g in p1f])
        fr_y = np.concatenate([p1f[g]["y"] for g in p1f])
        fthr = budget_threshold(fr_p[cl_fr], BUD)
        rec_fr = {}
        for g in p1f:
            if p1f[g]["y"].any():
                rec_fr[g] = float((p1f[g][k][p1f[g]["y"] == 1] >= fthr).mean())
        res["p1"][NM[k]] = {"variant": list(G.VARIANTS[vi]), "mean_recall_val": s["variants"][str(vi)]["mean_recall"], "window_threshold": thr,
                            "val_clean_windows": int(X.clean_mask(p1).sum()), "captures": caps, "by_family": by_family(caps),
                            "frame_threshold": float(fthr), "frame_recall_1pct": rec_fr,
                            "frame_auc_val_all": X.frame_auc(fr_y, fr_p), "window_auc": X.window_auc(p1, k, vi),
                            "importance_top": dict(sorted(info[k]["importance"].items(), key=lambda a: -a[1])[:6]),
                            "variants": {a: {"variant": b["variant"], "mean_recall": b["mean_recall"], "fa_clean": b["fa_clean"]} for a, b in s["variants"].items()}}
    # ---------------- OOF
    oo = {}
    tabs, frs = [], {}
    for p in sorted(RUN.glob("oof_*.pkl")):
        d = pickle.load(open(p, "rb"))
        tabs.append(d["tbl"])
        frs.update(d["frames"])
    oof = pd.concat(tabs, ignore_index=True)
    oof_thr = {}
    for k in MODELS:
        vi = chosen[k]
        cl = X.clean_mask(oof)
        thr = float(budget_threshold(oof[f"{k}{vi}"].to_numpy()[cl], BUD))
        oof_thr[k] = thr
        caps = cap_rows(oof, k, vi, thr)
        amb = {g: r for g, r in caps.items() if g.startswith("ambient")}
        fr_p = np.concatenate([frs[g][k] for g in frs])
        fr_cl = np.concatenate([frs[g]["clean"] & (frs[g]["y"] == 0) for g in frs])
        fthr = budget_threshold(fr_p[fr_cl], BUD)
        rec_fr = {g: float((frs[g][k][frs[g]["y"] == 1] >= fthr).mean()) for g in frs if frs[g]["y"].any()}
        # reverse windows
        rev = oof["rev"].to_numpy() & oof["group"].str.startswith("ambient").to_numpy() & (oof["y"] == 0).to_numpy()
        oth = (~oof["rev"].to_numpy()) & oof["group"].str.startswith("ambient").to_numpy() & (oof["y"] == 0).to_numpy()
        al = oof[f"{k}{vi}"].to_numpy() >= thr
        rev_by = {g: {"windows": int((rev & (oof["group"] == g).to_numpy()).sum()), "alarms": int((al & rev & (oof["group"] == g).to_numpy()).sum())}
                  for g in oof["group"].unique() if (rev & (oof["group"] == g).to_numpy()).any()}
        res["oof"][NM[k]] = {"variant": list(G.VARIANTS[vi]), "window_threshold": thr, "pooled_clean_windows": int(cl.sum()),
                             "pooled_fa_clean": float(al[cl].mean()), "ambient_fa": {g: r["fa_clean"] for g, r in amb.items()},
                             "ambient_fa_max": max(r["fa_clean"] for r in amb.values()), "captures": caps, "by_family": by_family(caps),
                             "frame_threshold": float(fthr), "frame_recall_1pct": rec_fr, "window_auc": X.window_auc(oof, k, vi),
                             "reverse_windows": {"n": int(rev.sum()), "alarms": int(al[rev].sum()), "rate": float(al[rev].mean()) if rev.any() else None,
                                                 "other_clean_ambient_rate": float(al[oth].mean()), "n_other": int(oth.sum()), "by_capture": rev_by}}
    # ---------------- ablation on validation captures
    names = list(p1["group"].unique())
    base = base_table(names)
    val_codes = codes
    abl = {}
    first_inj = {g: float(d["fi"].iloc[0]) for g, d in p1.groupby("group")}
    for tag, src, thrs in (("OOF thresholds (unseen families)", oof, oof_thr),
                           ("P1 val thresholds (seen families)", p1, {k: res["p1"][NM[k]]["window_threshold"] for k in MODELS})):
        s = src[src["group"].isin(names)].copy()
        s["sec"] = s["sec"].astype(int)
        m = s.merge(base, on=["group", "sec"], how="left")
        m = m[m["valid"].fillna(False).astype(bool)]
        A = {"base L1+L2b+L3": m["a1"] | m["a2"] | m["a3"], "L1": m["a1"], "L2b": m["a2"], "L3": m["a3"], "L1+L2b": m["a1"] | m["a2"]}
        for k in MODELS:
            A[NM[k]] = m[f"{k}{chosen[k]}"].to_numpy() >= thrs[k]
        b = A["base L1+L2b+L3"]
        A["base + L4 timing"] = b | A[NM["t"]]
        A["base + L4 payload"] = b | A[NM["p"]]
        A["base + both L4"] = b | A[NM["t"]] | A[NM["p"]]
        y = (m["y"] == 1).to_numpy()
        cl = (m["clean"].to_numpy() & ~y)
        rows = {}
        for cfg, a in A.items():
            a = np.asarray(a, bool)
            per = {}
            for g in names:
                gm = (m["group"] == g).to_numpy()
                yy = y & gm
                if yy.any():
                    hit = np.flatnonzero(a & yy)
                    per[g] = {"detected": bool(len(hit)), "recall": float(a[yy].mean()),
                              "delay_s": float(max(m["w_end"].to_numpy()[hit[0]] - first_inj[g], 0.0)) if len(hit) else None}
            rows[cfg] = {"clean_fa": float(a[cl].mean()), "clean_windows": int(cl.sum()), "detected": int(sum(v["detected"] for v in per.values())),
                         "n_attack_captures": len(per), "masq_detected": int(sum(v["detected"] for g, v in per.items() if g.endswith("_masquerade"))),
                         "n_masq": int(sum(g.endswith("_masquerade") for g in per)), "mean_window_recall": float(np.mean([v["recall"] for v in per.values()])),
                         "per_capture": per}
        abl[tag] = rows
    res["ablation_val"] = abl
    json.dump(res, open(OUT / "s6_road.json", "w"), indent=1)
    # ---------------- tables
    L_ = ["# WP2 S6: ROAD (validation / out-of-fold only)\n"]
    for k in MODELS:
        r = res["p1"][NM[k]]
        L_.append(f"## P1 {NM[k]}: variant {r['variant']}, val-calibrated 1% window threshold, seen families (instance 2)\n")
        L_.append("| capture | detected | window recall | delay s | clean FA | frame recall @1% |\n|---|---|---|---|---|---|")
        for g, c in r["captures"].items():
            L_.append(f"| {g} | {c.get('detected', '-')} | {pct(c.get('window_recall'))} | {c.get('delay_s')} | {pct(c['fa_clean'])} | {pct(r['frame_recall_1pct'].get(g))} |")
        L_.append("")
    for k in MODELS:
        r = res["oof"][NM[k]]
        L_.append(f"## OOF {NM[k]}: variant {r['variant']}, pooled threshold {r['window_threshold']:.4g}, pooled FA {pct(r['pooled_fa_clean'])}, unseen families\n")
        L_.append("| capture | detected | window recall | delay s | clean FA | frame recall @1% |\n|---|---|---|---|---|---|")
        for g, c in r["captures"].items():
            L_.append(f"| {g} | {c.get('detected', '-')} | {pct(c.get('window_recall'))} | {c.get('delay_s')} | {pct(c['fa_clean'])} | {pct(r['frame_recall_1pct'].get(g))} |")
        L_.append(f"\nReverse-bit windows: {r['reverse_windows']['alarms']} alarms in {r['reverse_windows']['n']} windows ({pct(r['reverse_windows']['rate'])}); other clean ambient windows {pct(r['reverse_windows']['other_clean_ambient_rate'])} (n {r['reverse_windows']['n_other']}).\n")
    for tag, rows in abl.items():
        L_.append(f"## Ablation on the 11 validation captures, {tag}\n")
        L_.append("| configuration | clean FA | captures detected | masquerade detected | mean window recall |\n|---|---|---|---|---|")
        for cfg, r in rows.items():
            L_.append(f"| {cfg} | {pct(r['clean_fa'])} | {r['detected']}/{r['n_attack_captures']} | {r['masq_detected']}/{r['n_masq']} | {pct(r['mean_window_recall'])} |")
        L_.append("")
    open(OUT / "s6_road_tables.md", "w").write("\n".join(L_))
    print("\n".join(L_))


if __name__ == "__main__":
    main()
