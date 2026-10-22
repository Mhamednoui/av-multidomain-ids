"""WP2 S7: freeze the CAN domain, development ablation, the single ROAD test run, the accelerator whole-capture check.
  freeze   needs results/WP2/s7_select.json + CACHE/design.pkl. Fits the combiner on the development set (LOCO normal windows + validation attack windows),
           builds CanDomain (final models), saves results/WP2/s7_domain/, writes results/WP2/s7_frozen.json (the guard that lets tables test|accel run),
           and the development ablation (results/WP2/s7_dev.json).
  test     ROAD test (exposure 6): per capture, per layer / ablation configuration; needs CACHE/tables/test (tools/WP2_S7_tables.py test). ONE run.
  accel    4 accelerator captures, whole-capture check (needs CACHE/tables/accel).
Usage: python -u -W ignore tools/WP2_S7_final.py freeze|test|accel
Rules: notes/WP2_can.md "S7 start". Nothing here changes a design choice.
"""
import json
import pickle
import sys
import time

import numpy as np

from WP2_S7_lib import (ACCEL, BLOCKS, CACHE, DYNO, FOLDS, MASQ_TEST, OUT, TEST, TEST_AMB, TEST_ATTACK, VAL_ATTACK, base_of, dump_json)
from WP2_S7_select import K_SETS, attack_windows, family, lead_windows
from can.domain import LAYER_NAMES, CanDomain, layer_raws
from can.stack_eval import block_bootstrap_rate, clopper_pearson, cluster_bootstrap_rate
from common.calibration import ECDFCalibrator
from common.combiner import DomainCombiner
from common.evaluate import EvalSet, evaluate_domain
from common.evidence import Evidence
from common.metrics import budget_threshold

BUDGET = 0.01
DOM = OUT / "s7_domain"
DOM_L2B = OUT / "s7_domain_l2b"          # optional ablation domain: the same stack plus L2b relations-only (K3); NOT the default


def pk(path):
    return pickle.load(open(path, "rb"))


def load_group(group, names):
    return {n: dict(np.load(CACHE / "tables" / group / (n + ".npz"))) for n in names}


def evidence_lists(dom: CanDomain, tabs: dict, select) -> tuple:
    """Evidence per layer name for the windows chosen by select(tab) -> bool mask over all windows; y, type, group, t aligned."""
    ev = {LAYER_NAMES[l]: [] for l in dom.layers}
    y, at, grp, tt = [], [], [], []
    for n, t in tabs.items():
        m = select(t) & t["ok"]
        cal = dom.calibrated(t)
        for i in np.flatnonzero(m):
            for l in dom.layers:
                s = float(cal[l][i])
                ev[LAYER_NAMES[l]].append(Evidence(domain="can", layer=l, name=LAYER_NAMES[l], t=float(t["w_end"][i]), score=s,
                                                   alarm=s >= dom.layer_thresholds[l], sample_id=f"{n}/{int(t['sec'][i])}"))
        y += list(t["y"][m].astype(int))
        at += [family(n) + ("_masquerade" if n.endswith("_masquerade") else "") if v else "normal" for v in t["y"][m]]
        grp += [n] * int(m.sum())
        tt += list(t["w_end"][m])
    return ev, np.array(y), np.array(at, dtype=object), np.array(grp, dtype=object), np.array(tt)


def build_domain(des, models_final, W, F, V):
    """Calibrated, thresholded domain (combiner not fitted yet)."""
    cfg = des["cfg"]
    models_final.l2b_weights = W
    keep = cfg["l3c"][0]
    models_final.l3c = {keep: models_final.l3c[keep]}
    thr = {}
    pool_l3c = DYNO if cfg["l3c"][2] == "P0" else FOLDS
    for l in des["layers"]:
        units = pool_l3c if l == "L3c" else FOLDS
        cal = []
        for u in units:
            raw = layer_raws(F[u], cfg, des["ecdf_rules"])[l][F[u]["ok"]]
            cal.append(des["calib"][l].transform(raw))
        thr[l] = budget_threshold(np.concatenate(cal), BUDGET)
    dom = CanDomain(models_final, cfg, des["ecdf_rules"], des["calib"], None, thr, BUDGET)
    return dom


def dev_sets(dom, F, V):
    folds_ev = evidence_lists(dom, F, lambda t: np.ones(len(t["ok"]), bool))
    val_ev = evidence_lists(dom, V, lambda t: attack_windows(t))
    ev = {k: folds_ev[0][k] + val_ev[0][k] for k in folds_ev[0]}
    y = np.r_[folds_ev[1], val_ev[1]]
    at = np.r_[folds_ev[2], val_ev[2]]
    grp = np.r_[folds_ev[3], val_ev[3]]
    tt = np.r_[folds_ev[4], val_ev[4]]
    return EvalSet(ev, y, at, grp, tt)


def freeze():
    des = pk(CACHE / "design.pkl")
    sel = json.load(open(OUT / "s7_select.json"))
    F, V = load_group("folds", FOLDS), load_group("val", VAL_ATTACK)
    W = pk(CACHE / "weights.pkl")
    M = pk(CACHE / "models" / "final.pkl")
    dom = build_domain(des, M, W, F, V)
    dev = dev_sets(dom, F, V)
    comb = DomainCombiner(method="auto", budget=BUDGET).fit(dev.evidence, dev.y, dev.group)
    dom.combiner = comb
    DOM.mkdir(parents=True, exist_ok=True)
    dom.save(DOM)
    print("combiner", comb.method, comb.selection, "threshold", comb.threshold)
    # optional ablation domain with L2b (S5 relations-only set K3): rule-dropped from the default stack, kept as an ablation row
    cfg2 = dict(des["cfg"], K=K_SETS["K3"])
    raw2 = np.concatenate([layer_raws(F[u], cfg2, des["ecdf_rules"])["L2b"][F[u]["ok"]] for u in FOLDS])
    des2 = {"cfg": cfg2, "ecdf_rules": des["ecdf_rules"], "layers": ["L1", "L2b", "L3c", "L3d"],
            "calib": {**des["calib"], "L2b": ECDFCalibrator().fit(raw2)}}
    dom2 = build_domain(des2, pk(CACHE / "models" / "final.pkl"), W, F, V)
    dev2 = dev_sets(dom2, F, V)
    dom2.combiner = DomainCombiner(method="auto", budget=BUDGET).fit(dev2.evidence, dev2.y, dev2.group)
    DOM_L2B.mkdir(parents=True, exist_ok=True)
    dom2.save(DOM_L2B)
    print("combiner with L2b", dom2.combiner.method, dom2.combiner.selection)
    # development ablation (in-sample for the combiner: the dev set is also the combiner's validation set)
    res = evaluate_domain("s7_dev", dev, dev, wp="WP2", budget=BUDGET, method="auto", out_dir=OUT / "s7_dev_harness")
    frozen = {"cfg": des["cfg"], "layers": dom.layers, "layer_thresholds": dom.layer_thresholds, "combiner": {"method": comb.method, "threshold": comb.threshold,
              "selection": comb.selection}, "design_rule": sel["design_rule"], "l2b_chosen": sel["l2b_chosen"], "design_chosen": sel["design_chosen"],
              "note": "frozen before any S7 test table was built; ROAD test exposure 6"}
    dump_json(frozen, OUT / "s7_frozen.json")
    dump_json({"dev_ablation": {k: {"auc": v["auc"], "detection": v["detection"], "false_alarm_rate": v["false_alarm_rate"],
                                    "detection_by_attack": v["detection_by_attack"]} for k, v in res["ablation"].items()}}, OUT / "s7_dev.json")
    print(open(OUT / "s7_dev_harness" / "s7_dev.md").read())


# ------------------------------------------------------------------ test
def fit_combiner(dom, dev, names):
    """Combiner on the development set restricted to the layers `names` (layer ids); method chosen by 'auto' again, as common.evaluate does."""
    sub = {LAYER_NAMES[l]: dev.evidence[LAYER_NAMES[l]] for l in names}
    return DomainCombiner(method="auto", budget=BUDGET).fit(sub, dev.y, dev.group)


def configs_of(layers):
    c = {"all": list(layers)}
    for l in layers:
        c[f"only_{l}"] = [l]
    for l in layers:
        c[f"all_but_{l}"] = [m for m in layers if m != l]
    return c


def window_alarms(dom, dev, tabs):
    """Alarm arrays (over ALL windows of each table, False where not scored) for every configuration: layer alone = its own 1% threshold,
    combinations = a combiner refitted on the development set. Returns {config: {alarms: {capture: bool array}, method}}, {capture: {layer: calibrated}}."""
    ev, order = {LAYER_NAMES[l]: [] for l in dom.layers}, []
    cals = {n: dom.calibrated(t) for n, t in tabs.items()}
    for n, t in tabs.items():
        for i in np.flatnonzero(t["ok"]):
            order.append((n, i))
            for l in dom.layers:
                s = float(cals[n][l][i])
                ev[LAYER_NAMES[l]].append(Evidence(domain="can", layer=l, name=LAYER_NAMES[l], t=float(t["w_end"][i]), score=s,
                                                   alarm=s >= dom.layer_thresholds[l], sample_id=f"{n}/{int(t['sec'][i])}"))
    out = {}
    for cname, layers in configs_of(dom.layers).items():
        if len(layers) == 1:
            al = np.array([e.alarm for e in ev[LAYER_NAMES[layers[0]]]])
            meth = "layer threshold"
        else:
            comb = dom.combiner if cname == "all" else fit_combiner(dom, dev, layers)
            ce = comb.combine({LAYER_NAMES[l]: ev[LAYER_NAMES[l]] for l in layers})
            al = np.array([e.alarm for e in ce])
            meth = comb.method
        per = {n: np.zeros(len(tabs[n]["ok"]), bool) for n in tabs}
        for a, (n, i) in zip(al, order):
            per[n][i] = a
        out[cname] = {"alarms": per, "method": meth}
    return out, cals


def capture_metrics(t, al):
    ok = t["ok"]
    y = ok & (t["y"] == 1)
    cl = ok & t["clean"] & (t["y"] == 0)
    r = {"windows": int(ok.sum()), "attack_windows": int(y.sum()), "clean_windows": int(cl.sum()), "false_alerts_clean": int(al[cl].sum()),
         "fa_clean": float(al[cl].mean()) if cl.any() else None}
    if y.any():
        hit = np.flatnonzero(al & y)
        r["detected"] = bool(len(hit))
        r["window_recall"] = float(al[y].mean())
        r["delay_s"] = float(max(t["w_end"][hit[0]] - t["first_inj"], 0.0)) if len(hit) else None
    return r


def pooled_fa(tabs, alarms, units):
    """Pooled clean FA with a cluster bootstrap over the clean units (captures / unique attack-capture leads)."""
    parts = []
    for n in units:
        t = tabs[n]
        cl = t["ok"] & t["clean"] & (t["y"] == 0)
        parts.append(alarms[n][cl])
    return cluster_bootstrap_rate(parts)


def fmtp(x, d=1):
    return "-" if x is None else f"{100 * x:.{d}f}%"


def run_test():
    dom = CanDomain.load(DOM)
    F, V = load_group("folds", FOLDS), load_group("val", VAL_ATTACK)
    dev = dev_sets(dom, F, V)
    T = load_group("test", TEST)
    res_alarm, cals = window_alarms(dom, dev, T)
    uniq_lead = [n for n in TEST_ATTACK if not n.endswith("_masquerade")]
    clean_units = TEST_AMB + uniq_lead
    out = {"exposure": 6, "layers": dom.layers, "combined_method": dom.combiner.method, "layer_thresholds": dom.layer_thresholds,
           "frozen": json.load(open(OUT / "s7_frozen.json")), "configs": {}}
    hwd = "ambient_highway_street_driving_diagnostics"
    dom2 = CanDomain.load(DOM_L2B)
    dev2 = dev_sets(dom2, F, V)
    res2, cals2 = window_alarms(dom2, dev2, T)
    allcfg = dict(res_alarm)
    allcfg["all+L2b (optional)"] = res2["all"]
    allcfg["only_L2b (optional)"] = res2["only_L2b"]
    for cname, cr in allcfg.items():
        al = cr["alarms"]
        per = {n: capture_metrics(T[n], al[n]) for n in TEST}
        pooled, ci = pooled_fa(T, al, clean_units)
        nclean = sum(per[n]["clean_windows"] for n in clean_units)
        kclean = sum(per[n]["false_alerts_clean"] for n in clean_units)
        masq = {n: per[n]["detected"] for n in MASQ_TEST}
        plain = {n: per[n]["detected"] for n in TEST_ATTACK if not n.endswith("_masquerade")}
        lo, hi = clopper_pearson(sum(masq.values()), len(masq))
        blk = {n: block_bootstrap_rate(al[n][T[n]["ok"] & T[n]["clean"] & (T[n]["y"] == 0)]) for n in TEST_AMB}
        nx = max(sum(per[n]["clean_windows"] for n in clean_units if n != hwd), 1)
        out["configs"][cname] = {"method": cr["method"], "per_capture": per, "clean_fa_pooled": pooled, "clean_fa_ci95_cluster_bootstrap": ci,
                                 "clean_windows": nclean, "false_alerts": kclean, "false_alerts_per_hour": kclean / (nclean / 3600.0) if nclean else None,
                                 "masquerade_detected": int(sum(masq.values())), "masquerade_ci95_clopper_pearson": [lo, hi],
                                 "plain_detected": int(sum(plain.values())), "n_plain": len(plain),
                                 "ambient_fa": {n: per[n]["fa_clean"] for n in TEST_AMB},
                                 "ambient_fa_ci95_block_bootstrap": {n: [blk[n][0], list(blk[n][1])] for n in TEST_AMB},
                                 "fa_without_highway_diag": sum(per[n]["false_alerts_clean"] for n in clean_units if n != hwd) / nx}
    expl = {}
    for n in TEST_ATTACK:
        t = T[n]
        a = res_alarm["all"]["alarms"][n] & t["ok"] & (t["y"] == 1)
        expl[n] = {l: int(((cals[n][l] >= dom.layer_thresholds[l]) & a).sum()) for l in dom.layers}
    out["alarm_windows_by_layer_in_attack"] = expl
    dump_json(out, OUT / "s7_test.json")
    L = ["# S7 ROAD test (exposure 6), generated by tools/WP2_S7_final.py\n"]
    for cname, c in out["configs"].items():
        L.append(f"## {cname} (combiner {c['method']}): clean FA {fmtp(c['clean_fa_pooled'], 2)} (95% {fmtp(c['clean_fa_ci95_cluster_bootstrap'][0], 2)} - "
                 f"{fmtp(c['clean_fa_ci95_cluster_bootstrap'][1], 2)}), {c['false_alerts']}/{c['clean_windows']} windows, {c['false_alerts_per_hour']:.0f} false alerts/h; "
                 f"masquerade {c['masquerade_detected']}/5 (CP {fmtp(c['masquerade_ci95_clopper_pearson'][0], 0)}-{fmtp(c['masquerade_ci95_clopper_pearson'][1], 0)}); "
                 f"plain {c['plain_detected']}/{c['n_plain']}; FA without highway diagnostics {fmtp(c['fa_without_highway_diag'], 2)}")
        L.append("| capture | attack windows | detected | recall | delay s | clean windows | false alerts | FA (95% block bootstrap) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for n, r in c["per_capture"].items():
            ci = c["ambient_fa_ci95_block_bootstrap"].get(n)
            cis = f"{fmtp(ci[0], 1)} ({fmtp(ci[1][0], 1)}-{fmtp(ci[1][1], 1)})" if ci else fmtp(r["fa_clean"], 1)
            d = "-" if r.get("delay_s") is None else f"{r['delay_s']:.2f}"
            L.append(f"| {n} | {r['attack_windows']} | {r.get('detected', '-')} | {fmtp(r.get('window_recall'), 0)} | {d} | {r['clean_windows']} | {r['false_alerts_clean']} | {cis} |")
        L.append("")
    open(OUT / "s7_test_tables.md", "w").write("\n".join(L))
    print("\n".join(L[:30]))


# ------------------------------------------------------------------ accelerator whole-capture check
def run_accel():
    dom = CanDomain.load(DOM)
    F, V = load_group("folds", FOLDS), load_group("val", VAL_ATTACK)
    dev = dev_sets(dom, F, V)
    allt = {**load_group("accel", ACCEL), **load_group("test", TEST_AMB)}
    res_alarm, cals = window_alarms(dom, dev, allt)
    out = {"note": "ROAD documents the accelerator attack as injected BEFORE the capture starts; the logs have no injected frames and ROAD labels them 0. "
                   "Whole-capture check only: no onset, no window labels. Reference = the same alarm fraction on clean captures.", "captures": {}}
    for cname in ["all"] + [f"only_{l}" for l in dom.layers]:
        for n, t in allt.items():
            al = res_alarm[cname]["alarms"][n] & t["ok"]
            r = {"windows": int(t["ok"].sum()), "alarm_windows": int(al.sum()), "alarm_fraction": float(al.sum() / max(t["ok"].sum(), 1)),
                 "first_alarm_s": float(t["w_end"][np.flatnonzero(al)[0]]) if al.any() else None, "kind": "accelerator" if n in ACCEL else "clean test ambient"}
            out["captures"].setdefault(n, {})[cname] = r
    dump_json(out, OUT / "s7_accel.json")
    L = ["| capture | kind | windows | alarm fraction (combined) | first alarm s | " + " | ".join(dom.layers) + " |", "|---|---|---|---|---|" + "---|" * len(dom.layers)]
    for n, c in out["captures"].items():
        a = c["all"]
        L.append(f"| {n} | {a['kind']} | {a['windows']} | {fmtp(a['alarm_fraction'], 1)} | {a['first_alarm_s']} | " + " | ".join(fmtp(c[f'only_{l}']['alarm_fraction'], 1) for l in dom.layers) + " |")
    open(OUT / "s7_accel_tables.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    {"freeze": freeze, "test": run_test, "accel": run_accel}[sys.argv[1]]()
