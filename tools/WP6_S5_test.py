"""WP6 S5 stage 3: the ONE labelled test run of the frozen M2 system (results/WP6/s5_frozen.pkl, chosen on validation by tools/WP6_S5_dev.py) on the S4 test
composites (same construction and seeds). Reports: raw tick FA and alert events per clean hour with CIs, event / tick detection and delay per family and per
attacked domain, S4 held-out types, blame, response per scenario, explanations, ablation (each domain removed; correlator off), equal-FA G5 comparison
(test-informed, labelled), tick recall (v2-style view), acceptance A1-A7. Run: python -u -W ignore tools/WP6_S5_test.py
Outputs: results/WP6/s5_test.json, s5_acceptance.json   (WP6_S5_SMOKE=1: plumbing check on the validation packs, output in the temp folder)
"""
import json
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir  # noqa: E402
from common.metrics import budget_threshold  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S5_lib as L  # noqa: E402

SMOKE = bool(int(os.environ.get("WP6_S5_SMOKE", "0")))
OUT = results_dir("WP6")
OUT_W = Path(tempfile.gettempdir()) / "wp6_s5_smoke" if SMOKE else OUT
OUT_W.mkdir(parents=True, exist_ok=True)
T0 = time.time()
V2 = Path(__file__).resolve().parent.parent.parent / "codes_v2" / "results"


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def blame_pool(outs, fams):
    det = [r for r in outs if r["family"] in fams and r["detected"]]
    return {k: float(np.mean([r["blame"] == k for r in det])) for k in ("correct", "wrong", "undecided")} | {"n_detected": len(det)}


def per_domain(tab, fams, key):
    out = {}
    for f in fams:
        out.setdefault(tab[f]["attacked"], []).append(tab[f][key])
    return {d: float(np.mean(v)) for d, v in out.items()}


def explanations(sysm, comps, X, s, packs_fam, k_examples=6):
    fus, corr, doms = sysm.fusion, sysm.correlator, sysm.entries
    ln = {d: list(packs_fam[d]["layer_names"]) for d in doms}
    idx = L3.index_of(comps)
    n_ev = n_ex = 0
    ex = []
    al = s >= fus.threshold
    for ci, c in enumerate(comps):
        a = al[idx[ci]:idx[ci + 1]]
        if not a.any():
            continue
        Xc = X[idx[ci]:idx[ci + 1]]
        own, bl = L.comp_arrays(c, Xc, doms)
        reasons = np.full(c["n"], "", object)
        for e in corr.events(a, own, doms, bl):
            reasons[e.first_alarm] = fus.explain(e.first_alarm, Xc[e.first_alarm], c["parts"], ln, s[idx[ci] + e.first_alarm]).reason
        for e in corr.events(a, own, doms, bl, reasons):
            n_ev += 1
            n_ex += int(bool(reasons[e.first_alarm]) and bool(e.explanation))
            if len(ex) < k_examples and (c["family"] == "none" or len(ex) < k_examples - 2):
                ex.append({"family": c["family"], "attacked": c["attacked"], "response": e.response, "degraded": e.degraded, "actions": e.actions, "explanation": e.explanation})
    return {"events": n_ev, "with_explanation": n_ex, "examples": ex}


def tick_recall(comps, s, thr):
    lab = np.concatenate([c["label"] for c in comps])
    return float((s[lab] >= thr).mean())


def run_family(fam, frozen, packs_fam, comps):
    sysm = frozen["systems"][fam]
    fus, corr, doms = sysm.fusion, sysm.correlator, sysm.entries
    X = L.matrix(sysm.density, fus, comps)
    s = L.combine(fus.method, X)
    T = fus.threshold
    outs = L.evaluate(comps, X, s, T, doms, corr)
    m = L.summary(outs)
    tab = m["families"]
    single = L.single_families(tab, fam)
    held = [f for f in tab if tab[f]["category"] == "heldout"]
    seen = [f for f in single if tab[f]["category"] == "seen"]
    m["mean_event_detection_single"] = float(np.mean([tab[f]["detection"] for f in single]))
    m["mean_tick_detection_single"] = float(np.mean([tab[f]["tick_detection"] for f in single]))
    m["mean_event_detection_heldout"] = float(np.mean([tab[f]["detection"] for f in held])) if held else None
    m["mean_event_detection_seen"] = float(np.mean([tab[f]["detection"] for f in seen])) if seen else None
    m["ci_single_event"] = L.cluster_ci(outs, single, "detected")
    m["ci_single_tick"] = L.cluster_ci(outs, single, "tick_detected")
    m["ci_heldout_event"] = L.cluster_ci(outs, held, "detected") if held else None
    m["blame_single_pooled"] = blame_pool(outs, set(single))
    m["blame_coordinated_pooled"] = blame_pool(outs, set(L.CP.COORDINATED[fam]))
    m["event_detection_by_attacked_domain"] = per_domain(tab, single, "detection")
    m["tick_detection_by_attacked_domain"] = per_domain(tab, single, "tick_detection")
    m["tick_recall_attack_ticks"] = tick_recall(comps, s, T)
    m["threshold"] = T
    log(fam, "A: tick FA", round(m["fa_tick"], 4), "events/h", round(m["events_per_hour"], 2), "event det single", round(m["mean_event_detection_single"], 4),
        "tick det", round(m["mean_tick_detection_single"], 4), "held-out", m["mean_event_detection_heldout"], "blame", m["blame_single_pooled"], "resp/h", m["clean_response_per_hour"])
    m["explanations"] = explanations(sysm, comps, X, s, packs_fam)
    log(fam, "explained", m["explanations"]["with_explanation"], "/", m["explanations"]["events"])
    # correlator off (S3 alarm events = maximal runs of alarm ticks)
    m0 = L.summary(L.evaluate(comps, X, s, T, doms, None))
    m["correlator_off"] = {"events_per_hour": m0["events_per_hour"], "fa_tick": m0["fa_tick"], "mean_detection_single": float(np.mean([m0["families"][f]["detection"] for f in single])),
                           "mean_detection_heldout": float(np.mean([m0["families"][f]["detection"] for f in held])) if held else None,
                           "families": {f: m0["families"][f]["detection"] for f in m0["families"]}}
    # ablation: each domain removed (threshold from validation, same procedure)
    ab = {}
    for name, a in frozen["ablation"][fam].items():
        cols = a["cols"]
        dj = [doms[i] for i in cols]
        sj = L.combine(fus.method, X, cols)
        mj = L.summary(L.evaluate(comps, X[:, cols], sj, a["threshold"], dj, corr))
        tj = mj["families"]
        ab[name] = {"fa_tick": mj["fa_tick"], "events_per_hour": mj["events_per_hour"], "mean_event_detection_single": float(np.mean([tj[f]["detection"] for f in single])),
                    "mean_event_detection_heldout": float(np.mean([tj[f]["detection"] for f in held])) if held else None,
                    "event_detection_by_attacked_domain": per_domain(tj, single, "detection"), "families": {f: tj[f]["detection"] for f in tj}}
        log(fam, name, "FA", round(mj["fa_tick"], 4), "ev/h", round(mj["events_per_hour"], 2), "det", round(ab[name]["mean_event_detection_single"], 4))
    m["ablation"] = ab
    # equal-FA G5 comparison (TEST-INFORMED, labelled): each attacked domain's own entry alone at the fused system's clean test tick FA
    cm = L.clean_mask(comps)
    idx = L3.index_of(comps)
    g5 = {}
    for d in sorted({tab[f]["attacked"] for f in single}):
        j = doms.index(d if d in doms else "cross")              # comma GNSS families: only the cross entry sees them
        thr = budget_threshold(X[cm, j], m["fa_tick"])
        fams = [f for f in single if tab[f]["attacked"] == d]
        det = {f: [] for f in fams}
        for ci, c in enumerate(comps):
            if c["family"] in det:
                det[c["family"]].append(bool(((X[idx[ci]:idx[ci + 1], j] >= thr) & c["label"]).any()))
        g5[d] = {"alone_tick_detection": float(np.mean([np.mean(v) for v in det.values()])), "fused_tick_detection": float(np.mean([tab[f]["tick_detection"] for f in fams])),
                 "fused_event_detection": float(np.mean([tab[f]["detection"] for f in fams])), "alone_threshold": float(thr), "alone_fa_tick": float((X[cm, j] >= thr).mean())}
    m["g5_equal_fa_test_informed"] = g5
    return m


def main():
    fz = pickle.load(open(OUT / "s5_frozen.pkl", "rb"))
    part = "val" if SMOKE else "test"
    log("M2 TEST run (once).", "SMOKE on validation packs" if SMOKE else "", fz["calibration_choice"], fz["correlator_choice"]["key"])
    packs = L.assemble(L.load_unique(part))
    res = {"smoke": SMOKE, "calibration_choice": fz["calibration_choice"], "correlator_choice": fz["correlator_choice"],
           "exposure": "every domain test set was scored before (ROAD >= 6x, D10 several, VeReMi 2x, KITTI several, comma 2x); fusion test composites seen in S3 (seed 63) "
                       "and S4 (seed 64 = these composites): third fusion-level exposure; the M2 calibration, correlator and response are scored on test once here",
           "system": {}}
    for fam in ("K", "C"):
        c = fz["composites_test"][fam]
        comps = L3.build_set(fam, packs[fam], None, c["seed"], c["n_clean"], c["n_attack"])
        log(fam, "test composites", len(comps), "clean hours", round(sum(x["n"] for x in comps if x["family"] == "none") / 3600, 2))
        res["system"][fam] = run_family(fam, fz, packs[fam], comps)
    try:
        sim = json.loads((V2 / "simulation.json").read_text())
        fu = json.loads((V2 / "fusion.json").read_text())
        res["v2"] = {"simulation_with_correlator": sim.get("with_correlator"), "simulation_fusion_only": sim.get("fusion_only"),
                     "first_alert_delay_rows": sim.get("first_alert_delay_rows"), "fusion_keys": sorted(fu)[:20]}
    except Exception as e:  # noqa: BLE001
        res["v2"] = {"error": str(e)}
    K, C = res["system"]["K"], res["system"]["C"]
    acc = {
        "A1_raw_tick_fa": {"K": K["fa_tick"], "K_ci": K["ci_single_event"]["fa_tick"], "C": C["fa_tick"], "C_ci": C["ci_single_event"]["fa_tick"], "rule": "<= 0.030 (K and C)",
                           "met": K["fa_tick"] <= 0.03 and C["fa_tick"] <= 0.03},
        "A2_events_per_clean_hour": {"K": K["events_per_hour"], "K_ci": K["ci_single_event"]["events_per_hour"], "C": C["events_per_hour"], "C_ci": C["ci_single_event"]["events_per_hour"],
                                     "rule": "<= 10 (K and C)", "met": K["events_per_hour"] <= 10 and C["events_per_hour"] <= 10},
        "A3_K_event_detection_single": {"value": K["mean_event_detection_single"], "ci": K["ci_single_event"]["mean"], "rule": ">= 0.70", "met": K["mean_event_detection_single"] >= 0.70},
        "A4_K_heldout_event_detection": {"value": K["mean_event_detection_heldout"], "ci": K["ci_heldout_event"]["mean"], "rule": ">= 0.60", "met": K["mean_event_detection_heldout"] >= 0.60},
        "A5_K_blame": {"value": K["blame_single_pooled"], "rule": "correct >= 0.75 and wrong <= 0.10 (detected single-domain K events, pooled)",
                       "met": K["blame_single_pooled"]["correct"] >= 0.75 and K["blame_single_pooled"]["wrong"] <= 0.10},
        "A6_safe_stop_per_clean_hour": {"K": K["clean_response_per_hour"]["SAFE_STOP"], "C": C["clean_response_per_hour"]["SAFE_STOP"], "rule": "<= 1 (K and C)",
                                        "met": K["clean_response_per_hour"]["SAFE_STOP"] <= 1 and C["clean_response_per_hour"]["SAFE_STOP"] <= 1},
        "A7_explained": {"K": [K["explanations"]["with_explanation"], K["explanations"]["events"]], "C": [C["explanations"]["with_explanation"], C["explanations"]["events"]],
                         "rule": "100% of alert events", "met": all(x["explanations"]["with_explanation"] == x["explanations"]["events"] for x in (K, C))},
    }
    res["acceptance"] = acc
    (OUT_W / "s5_test.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT_W / "s5_acceptance.json").write_text(json.dumps(acc, indent=1, default=str))
    for k, v in acc.items():
        log(k, "MET" if v["met"] else "NOT MET", {a: b for a, b in v.items() if a not in ("rule", "met")})
    log("done", OUT_W)


if __name__ == "__main__":
    main()
