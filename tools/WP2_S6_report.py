"""WP2 S6: Car-Hacking and D11 report tables (window level, L1 vs L4 vs combinations), from the frozen test window tables.
Usage: python -u -W ignore tools/WP2_S6_report.py ch|d11  -> results/WP2/s6_ch.json|s6_d11.json and *_tables.md
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import l4_exp as X
from common.config import DATA_EXTRA, RESULTS

OUT = RESULTS / "WP2"
ADD_GAIN, ADD_FA = 0.10, 0.015
CFGS = ["L1", "L4t", "L4p", "L1+L4t", "L1+L4p", "L1+L4t+L4p"]


def pct(x):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{100 * x:.1f}%"


def alarm_sets(tt, vis, thr):
    """dict cfg -> bool array. vis: {'t': variant idx, 'p': ...}; thr: {'t': window thr, 'p': ...}."""
    a = {"L1": tt["l1_alarm"].to_numpy(bool),
         "L4t": tt[f"t{vis['t']}"].to_numpy() >= thr["t"], "L4p": tt[f"p{vis['p']}"].to_numpy() >= thr["p"]}
    a["L1+L4t"], a["L1+L4p"], a["L1+L4t+L4p"] = a["L1"] | a["L4t"], a["L1"] | a["L4p"], a["L1"] | a["L4t"] | a["L4p"]
    return a


def eval_table(tt, vis, thr, names):
    A = alarm_sets(tt, vis, thr)
    y = (tt["y"] == 1).to_numpy()
    cl = (tt["clean"].to_numpy() & ~y)
    oth = (~tt["clean"].to_numpy() & ~y)
    att = tt["att"].to_numpy()
    out = {"n_windows": {"clean": int(cl.sum()), "attack": int(y.sum()), "other_normal": int(oth.sum())}, "cfg": {}}
    types = sorted({int(a) for a in np.unique(att[y])})
    for c, a in A.items():
        d = {"fa_clean": float(a[cl].mean()) if cl.any() else None, "fa_other_normal": float(a[oth].mean()) if oth.any() else None,
             "recall": {names[t]: float(a[y & (att == t)].mean()) for t in types}}
        gs = {}
        for g, idx in tt.groupby("group", sort=False).indices.items():
            yy = y[idx]
            if yy.any():
                gs[str(g)] = bool(a[idx][yy].any())
        d["files_detected"] = f"{sum(gs.values())}/{len(gs)}"
        d["per_file_detected"] = gs
        out["cfg"][c] = d
    # verdict on "adds"
    adds = {}
    for c in ("L1+L4t", "L1+L4p", "L1+L4t+L4p"):
        gain = {t: out["cfg"][c]["recall"][t] - out["cfg"]["L1"]["recall"][t] for t in out["cfg"]["L1"]["recall"]}
        dfa = (out["cfg"][c]["fa_clean"] or 0) - (out["cfg"]["L1"]["fa_clean"] or 0)
        adds[c] = {"recall_gain": gain, "extra_fa_clean": dfa,
                   "adds": bool(any(g >= ADD_GAIN for g in gain.values()) and dfa <= ADD_FA)}
    out["adds"] = adds
    return out


def table_lines(title, ev):
    types = list(ev["cfg"]["L1"]["recall"])
    L_ = [f"### {title}", f"windows: {ev['n_windows']}", "", "| config | clean FA | other-normal FA | files detected | " + " | ".join(types) + " |",
          "|---|---|---|---|" + "---|" * len(types)]
    for c, d in ev["cfg"].items():
        L_.append(f"| {c} | {pct(d['fa_clean'])} | {pct(d['fa_other_normal'])} | {d['files_detected']} | " + " | ".join(pct(d["recall"][t]) for t in types) + " |")
    L_.append("")
    L_.append("adds (recall gain >= 10 points on some attack and extra clean FA <= 1.5 points): " + ", ".join(f"{c}: {v['adds']}" for c, v in ev["adds"].items()))
    L_.append("")
    return L_


def frame_lines(title, fr, names=None):
    L_ = [f"frame level @1% (threshold from validation clean frames) {title}"]
    for k, v in fr.items():
        rec = {a: (b[1] / b[0] if b[0] else None) for a, b in v["inj"].items()}
        L_.append(f"- {k}: recall " + ", ".join(f"{a} {pct(r)}" for a, r in rec.items()) + f"; FA clean frames {pct(v['clean'][1] / v['clean'][0] if v['clean'][0] else None)}")
    return L_


def report_ch():
    RUN = DATA_EXTRA / "WP2_S6_cache" / "ch_run_m"
    info = json.load(open(RUN / "fit_info.json"))
    tt = pd.read_pickle(RUN / "test_windows.pkl")
    fr = json.load(open(RUN / "test_frames.json"))
    vis = {k: info[k]["variant_selection"]["chosen"] for k in ("t", "p")}
    thr = {k: info[k]["window_threshold"] for k in ("t", "p")}
    names = info["codes"]
    ev = eval_table(tt, vis, thr, names)
    res = {"variants": {k: [X.G.VARIANTS[v]] for k, v in vis.items()}, "thresholds": thr, "test": ev,
           "frame": fr["frame"], "importance": {k: info[k]["importance"] for k in ("t", "p")},
           "search": {k: {a: b for a, b in info[k]["search"].items() if a != "trials"} for k in ("t", "p")},
           "shuffle": json.load(open(OUT / "s6_ch_shuffle.json")) if (OUT / "s6_ch_shuffle.json").exists() else None}
    json.dump(res, open(OUT / "s6_ch.json", "w"), indent=1)
    L_ = ["# WP2 S6: Car-Hacking test blocks (scored once)", f"variants {res['variants']}; window thresholds {thr}", ""]
    L_ += table_lines("window level", ev)
    L_ += frame_lines("", fr["frame"])
    open(OUT / "s6_ch_tables.md", "w").write("\n".join(L_))
    print("\n".join(L_))


def report_d11():
    RUN = DATA_EXTRA / "WP2_S6_cache" / "d11_run"
    res = {}
    L_ = ["# WP2 S6: D11 test subsets (scored once)", ""]
    for s in ("set_01", "set_02", "set_03", "set_04"):
        f = OUT / f"s6_d11_{s}.json"
        if not f.exists():
            continue
        info = json.load(open(RUN / f"fit_{s}.json"))
        t = json.load(open(f))
        names = t["attack_names"]
        vis = {k: info[k]["variant_selection"]["chosen"] for k in ("t", "p")}
        res[s] = {"variants": {k: list(X.G.VARIANTS[v]) for k, v in vis.items()}, "fit": {k: {"search": {a: b for a, b in info[k]["search"].items() if a != "trials"},
                  "importance": info[k]["importance"], "window_threshold": info[k]["window_threshold"], "val_window_auc": info[k]["val_window_auc"]} for k in ("t", "p")},
                  "shuffle": info["shuffle"], "dt_prev_zero": info["dt_prev_zero"], "dt_zero_ablation": info.get("dt_zero_ablation"), "subsets": {}}
        L_.append(f"## {s}  variants {res[s]['variants']}  shuffle pass: " + ", ".join(f"{n} {v['pass']} ({v['mean_frame_auc']:.3f}/{v['mean_window_auc']:.3f})" for n, v in info["shuffle"].items()))
        for sub, sinfo in t["subsets"].items():
            res[s]["subsets"][sub] = {"vehicle": sinfo["vehicle"], "n_files": sinfo["n_files"], "n_eligible": sinfo["n_eligible"], "regimes": {}}
            for rn, r in sinfo["regimes"].items():
                tt = pd.read_pickle(RUN / f"testwin_{s}_{sub}_{rn}.pkl")
                thr = {k: r["thresholds"][k]["win_thr"] for k in ("t", "p")}
                ev = eval_table(tt, vis, thr, names)
                res[s]["subsets"][sub]["regimes"][rn] = {"thresholds": r["thresholds"], "test": ev, "frame": r["frame"]}
                L_ += table_lines(f"{s} {sub} {sinfo['vehicle']} regime {rn}", ev)
                L_ += frame_lines("", r["frame"])
                L_.append("")
    json.dump(res, open(OUT / "s6_d11.json", "w"), indent=1)
    open(OUT / "s6_d11_tables.md", "w").write("\n".join(L_))
    print("\n".join(L_[:60]))


if __name__ == "__main__":
    {"ch": report_ch, "d11": report_d11}[sys.argv[1]]()
