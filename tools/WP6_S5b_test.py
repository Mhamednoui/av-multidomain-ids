"""WP6 S5b stage 3: the ONE labelled test run of the system re-frozen after the M2 addendum (results/WP6/s5b_frozen.pkl, chosen on validation by
tools/WP6_S5b_dev.py) on NEW test composites (new random pairing, seed [SEED, 66, 5, ord(family)]; 4th scoring of fusion test data), plus the COUPLING test
(GPS attacks bend the OXTS ego pose of the LiDAR background / tracking layers; cache of tools/WP6_S5b_coupling.py).
Reports the M2 metrics side by side with M2 (results/WP6/s5_test.json): raw tick FA and alert events per clean hour with CIs, event / tick detection and delay per
family and attacked domain, S4 held-out types, blame, response, explanations, ablation (each domain removed incl. LiDAR; correlator off; M2 blame rule; M2 SAFE_STOP
rule), LiDAR per-scan / episode rows, acceptance A1-A7. Run: python -u -W ignore tools/WP6_S5b_test.py
Outputs: results/WP6/s5b_test.json, s5b_acceptance.json (make_report PENDING slot "M2 addendum")
"""
import copy
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir  # noqa: E402
from fusion import composite as CP  # noqa: E402
from fusion.correlator import TemporalCorrelator  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S5b_coupling as CU  # noqa: E402
import WP6_S5b_lib as L  # noqa: E402
import WP6_S5b_lidar as LB  # noqa: E402

OUT = results_dir("WP6")
T0 = time.time()
COUPLED_FAMS = CU.GPS_FAMS + ["gps_can"]


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def corr_variant(corr, blame=None, min_dom=None):
    r, m = corr.rules()
    return TemporalCorrelator(corr.m, corr.w, corr.gap, corr.corroborate, blame or r, m if min_dom is None else min_dom)


def layer_names(sysm, packs_fam):
    return {e: list(packs_fam[e.split(".")[0]]["layer_names"]) if "." not in e else [e] for e in sysm.entries}


def explanations(sysm, comps, outs, packs_fam, k_examples=6):
    """Runs the frozen SystemV2 end to end on every composite with an alarm (also checks it gives the same events as the evaluation) and counts explained events."""
    ln = layer_names(sysm, packs_fam)
    n_ev = n_ex = 0
    ex = []
    for c, r in zip(comps, outs):
        if not r["alarm_ticks"]:
            continue
        o = sysm.run(c["parts"], ln)
        assert len(o["events"]) == r["events"], (c["family"], len(o["events"]), r["events"])
        for e in o["events"]:
            n_ev += 1
            n_ex += int("first alarm: system alarm" in e.explanation)
            if len(ex) < k_examples and (c["family"] == "none" or len(ex) < k_examples - 2):
                ex.append({"family": c["family"], "attacked": c["attacked"], "response": e.response, "degraded": e.degraded, "actions": e.actions, "explanation": e.explanation})
    return {"events": n_ev, "with_explanation": n_ex, "examples": ex}


def metrics(comps, X, s, T, ents, corr, fam):
    outs = L.evaluate(comps, X, s, T, ents, corr)
    m = L.summary(outs)
    tab = m["families"]
    single = L.single_families(tab, fam)
    held = [f for f in single if tab[f]["category"] == "heldout"]
    seen = [f for f in single if tab[f]["category"] == "seen"]
    m["single_families"] = single
    m["mean_event_detection_single"] = float(np.mean([tab[f]["detection"] for f in single]))
    m["mean_tick_detection_single"] = float(np.mean([tab[f]["tick_detection"] for f in single]))
    m["mean_event_detection_heldout"] = float(np.mean([tab[f]["detection"] for f in held])) if held else None
    m["mean_event_detection_seen"] = float(np.mean([tab[f]["detection"] for f in seen])) if seen else None
    m["blame_single_pooled"] = L.blame_pool(outs, set(single))
    m["blame_coordinated_pooled"] = L.blame_pool(outs, set(CP.COORDINATED[fam]))
    m["event_detection_by_attacked_domain"] = L.per_domain(tab, single, "detection")
    m["tick_detection_by_attacked_domain"] = L.per_domain(tab, single, "tick_detection")
    cl = [r for r in outs if r["family"] == "none"]
    m["clean_composites_with_event"] = float(np.mean([r["events"] > 0 for r in cl])) if corr is not None else float(np.mean([r["alarm_ticks"] > 0 for r in cl]))
    return m, outs


def run_family(fam, fz, packs_fam, comps, m2):
    sysm = fz["systems"][fam]
    fus, corr, ents = sysm.fusion, sysm.correlator, sysm.entries
    X = L.matrix(sysm.density, fus, comps)
    s = fus.scores(X)
    T = fus.threshold
    m, outs = metrics(comps, X, s, T, ents, corr, fam)
    tab, single = m["families"], m["single_families"]
    held = [f for f in single if tab[f]["category"] == "heldout"]
    m["ci_single_event"] = L.cluster_ci(outs, single, "detected")
    m["ci_single_tick"] = L.cluster_ci(outs, single, "tick_detected")
    m["ci_heldout_event"] = L.cluster_ci(outs, held, "detected") if held else None
    lab = np.concatenate([c["label"] for c in comps])
    m["tick_recall_attack_ticks"] = float((s[lab] >= T).mean())
    m["threshold"] = T
    # M2-shared family set (families of the M2 test run that exist here; LiDAR families differ by construction)
    m2tab = m2["families"]
    shared = [f for f in single if f in m2tab and tab[f]["attacked"] != "lidar"]
    m["m2_shared"] = {"families": shared, "mean_event_detection": float(np.mean([tab[f]["detection"] for f in shared])),
                      "m2_mean_event_detection": float(np.mean([m2tab[f]["detection"] for f in shared]))}
    lid = [f for f in tab if tab[f]["attacked"] == "lidar"]
    m["lidar_rows"] = {f: {k: tab[f].get(k) for k in ("detection", "tick_detection", "median_delay_s", "blame_correct", "blame_wrong", "blame_undecided", "response_max", "n")} for f in sorted(lid)}
    log(fam, "tick FA", round(m["fa_tick"], 4), "events/h", round(m["events_per_hour"], 2), "event det single", round(m["mean_event_detection_single"], 4), "held-out",
        m["mean_event_detection_heldout"], "blame", m["blame_single_pooled"], "resp/h", m["clean_response_per_hour"])
    m["explanations"] = explanations(sysm, comps, outs, packs_fam)
    log(fam, "explained", m["explanations"]["with_explanation"], "/", m["explanations"]["events"])
    # correlator off; M2 blame rule; M2 SAFE_STOP rule (same alarms)
    m0 = L.summary(L.evaluate(comps, X, s, T, ents, None))
    m["correlator_off"] = {"events_per_hour": m0["events_per_hour"], "fa_tick": m0["fa_tick"], "mean_detection_single": float(np.mean([m0["families"][f]["detection"] for f in single])),
                           "mean_detection_heldout": float(np.mean([m0["families"][f]["detection"] for f in held])) if held else None}
    for name, cv in (("m2_blame_rule_plurality", corr_variant(corr, blame="plurality")), ("m2_safe_stop_rule_one_domain", corr_variant(corr, min_dom=1)),
                     ("m2_rules_both", corr_variant(corr, "plurality", 1)), ("correlator_with_corroboration", TemporalCorrelator(corr.m, corr.w, corr.gap, True, *corr.rules()))):
        mv, ov = metrics(comps, X, s, T, ents, cv, fam)
        m[name] = {"events_per_hour": mv["events_per_hour"], "clean_response_per_hour": mv["clean_response_per_hour"], "blame_single_pooled": mv["blame_single_pooled"],
                   "mean_event_detection_single": mv["mean_event_detection_single"],
                   "response_max_coordinated": {f: mv["families"][f].get("response_max") for f in CP.COORDINATED[fam] if f in mv["families"]}}
        log(fam, name, "events/h", round(mv["events_per_hour"], 2), "safe/h", round(mv["clean_response_per_hour"]["SAFE_STOP"], 3), "blame", mv["blame_single_pooled"])
    # ablation: each domain removed (threshold from validation)
    ab = {}
    for name, a in fz["ablation"][fam].items():
        cols = a["cols"]
        ej = [ents[i] for i in cols]
        sj = L.combine(fus.method, X, cols, a.get("weights"))
        mj = L.summary(L.evaluate(comps, X[:, cols], sj, a["threshold"], ej, corr))
        tj = mj["families"]
        ab[name] = {"fa_tick": mj["fa_tick"], "events_per_hour": mj["events_per_hour"], "mean_event_detection_single": float(np.mean([tj[f]["detection"] for f in single])),
                    "mean_event_detection_heldout": float(np.mean([tj[f]["detection"] for f in held])) if held else None,
                    "event_detection_by_attacked_domain": L.per_domain(tj, single, "detection"), "families": {f: tj[f]["detection"] for f in tj}}
        log(fam, name, "FA", round(mj["fa_tick"], 4), "ev/h", round(mj["events_per_hour"], 2), "det", round(ab[name]["mean_event_detection_single"], 4))
    m["ablation"] = ab
    return m, X, s


# ---------------------------------------------------------------- coupling test
def scan_level_coupling(dom):
    """Per-scan LiDAR alarm rates on all 350 test GPS attack runs: after onset, coupled pose vs true pose (same scans)."""
    fin = pickle.load(open(LB.S9C / "final_frames_s9.pkl", "rb"))["clean"]
    rows = []
    for d in LB.TEST:
        z = pickle.load(open(CU.OUT / f"{d}.pkl", "rb"))
        c = fin[fin.drive == d].set_index("idx")
        ts = LB.scan_times(d) - LB.scan_times(d)[0]
        for name, r in z["runs"].items():
            base = c.loc[r["idx"]].reset_index()
            cp = base.copy()
            cp["raw_L2c"], cp["raw_L2d"] = r["raw_L2c"], r["raw_L2d"]
            post = ts[r["idx"]] >= r["onset_t"]
            a, b = LB.scan_scores(dom, base), LB.scan_scores(dom, cp)
            rows.append({"run": name, "drive": d, "family": r["family"], "n_post": int(post.sum()), "max_offset_m": r["max_offset_m"], "max_step_m": r["max_step_m"],
                         "clean_alarm": float(a["comb_alarm"][post].mean()) if post.any() else np.nan, "coupled_alarm": float(b["comb_alarm"][post].mean()) if post.any() else np.nan,
                         "clean_L2c": float(a["layer_alarm"][post, 2].mean()) if post.any() else np.nan, "coupled_L2c": float(b["layer_alarm"][post, 2].mean()) if post.any() else np.nan,
                         "clean_L2d": float(a["layer_alarm"][post, 3].mean()) if post.any() else np.nan, "coupled_L2d": float(b["layer_alarm"][post, 3].mean()) if post.any() else np.nan})
    df = pd.DataFrame(rows)
    out = {}
    for f, g in df.groupby("family"):
        w = g["n_post"].to_numpy(float)
        wm = lambda col: float(np.nansum(g[col].to_numpy(float) * w) / w[np.isfinite(g[col].to_numpy(float))].sum())
        out[f] = {"runs": int(len(g)), "post_onset_scans": int(w.sum()), "median_max_offset_m": float(g["max_offset_m"].median()), "median_max_step_m": float(g["max_step_m"].median()),
                  **{k: wm(k) for k in ("clean_alarm", "coupled_alarm", "clean_L2c", "coupled_L2c", "clean_L2d", "coupled_L2d")}}
    return out


def synced_lidar(dom, d, t_grid, scan_sc, ts):
    """Composite-grid LiDAR part from per-scan scores (dict of scan_scores over scans with times ts): tick i <- scans with t in (t_i - 1, t_i]."""
    n = len(t_grid)
    i = np.searchsorted(t_grid, ts, side="left")
    ok = (i < n) & (ts > t_grid[np.minimum(i, n - 1)] - 1.0)
    k = np.where(ok, i, -1)
    v = {"score": LB.ST.tick_max(k, scan_sc["comb"], n), "layers": LB.ST.tick_max(k, scan_sc["layers"], n), "dom_alarm": LB.ST.tick_any(k, scan_sc["comb_alarm"], n),
         "layer_alarm": np.column_stack([LB.ST.tick_any(k, scan_sc["layer_alarm"][:, j], n) for j in range(4)])}
    cnt = np.bincount(k[ok], minlength=n)[:n].astype(np.float32)
    return {"score": v["score"], "layers": v["layers"], "dom_alarm": v["dom_alarm"], "layer_alarm": v["layer_alarm"], "present": cnt > 0, "label": np.zeros(n, bool),
            "blame": None, "src": f"{d}/synced", "grp": d, "count": cnt}


def coupling_composites(dom, comps, packs_K):
    fin = pickle.load(open(LB.S9C / "final_frames_s9.pkl", "rb"))["clean"]
    crt = {s["name"]: s["t"] for s in packs_K["cross"]["series"]}
    cache, ctrl, coup = {}, [], []
    for c in comps:
        if c["family"] not in COUPLED_FAMS:
            continue
        d = c["vehicle"]
        if d not in cache:
            cache[d] = (pickle.load(open(CU.OUT / f"{d}.pkl", "rb"))["runs"], fin[fin.drive == d].set_index("idx"), LB.scan_times(d) - LB.scan_times(d)[0])
        runs, cl, ts = cache[d]
        r = runs[c["parts"]["gps"]["src"]]
        t_grid = np.asarray(crt[c["parts"]["cross"]["src"]], float)
        base = cl.loc[r["idx"]].reset_index()
        cp = base.copy()
        cp["raw_L2c"], cp["raw_L2d"] = r["raw_L2c"], r["raw_L2d"]
        for df, lst in ((base, ctrl), (cp, coup)):
            x = dict(c)
            x["parts"] = dict(c["parts"])
            x["parts"]["lidar"] = synced_lidar(dom, d, t_grid[:c["n"]], LB.scan_scores(dom, df), ts[r["idx"]])
            lst.append(x)
    return ctrl, coup


def coupling_summary(sysm, comps):
    X = L.matrix(sysm.density, sysm.fusion, comps)
    s = sysm.fusion.scores(X)
    outs = L.evaluate(comps, X, s, sysm.fusion.threshold, sysm.entries, sysm.correlator)
    res = {}
    for f in COUPLED_FAMS:
        idx = [i for i, c in enumerate(comps) if c["family"] == f]
        if not idx:
            continue
        rs = [outs[i] for i in idx]
        post = np.concatenate([np.arange(comps[i]["n"]) >= max(comps[i]["onset"], 0) for i in idx])
        own = np.concatenate([comps[i]["parts"]["lidar"]["dom_alarm"] for i in idx])
        pre = ~post
        det = [r for r in rs if r["detected"]]
        res[f] = {"n": len(rs), "lidar_own_alarm_post_onset_ticks": float(own[post].mean()), "lidar_own_alarm_pre_onset_ticks": float(own[pre].mean()) if pre.any() else None,
                  "event_detection": float(np.mean([r["detected"] for r in rs])), "tick_detection": float(np.mean([r["tick_detected"] for r in rs])),
                  "blame": {k: float(np.mean([r["blame"] == k for r in det])) if det else None for k in ("correct", "wrong", "undecided")},
                  "blamed_lidar": float(np.mean([r["blamed"] == "lidar" for r in det])) if det else None,
                  "blamed_counts": {b: sum(r["blamed"] == b for r in det) for b in sorted({r["blamed"] for r in det})},
                  "response_max": {k: float(np.mean([r["response_max"] == k for r in det])) if det else None for k in ("WARN", "DEGRADE", "SAFE_STOP")}}
    return res


def acceptance(K, C, m2acc):
    a = lambda k: m2acc[k]
    return {
        "A1_raw_tick_fa": {"K": K["fa_tick"], "C": C["fa_tick"], "M2_K": a("A1_raw_tick_fa")["K"], "M2_C": a("A1_raw_tick_fa")["C"], "K_ci": K["ci_single_event"]["fa_tick"],
                           "C_ci": C["ci_single_event"]["fa_tick"], "rule": "<= 0.030 (K and C)", "met": K["fa_tick"] <= 0.03 and C["fa_tick"] <= 0.03},
        "A2_events_per_clean_hour": {"K": K["events_per_hour"], "C": C["events_per_hour"], "M2_K": a("A2_events_per_clean_hour")["K"], "M2_C": a("A2_events_per_clean_hour")["C"],
                                     "K_ci": K["ci_single_event"]["events_per_hour"], "C_ci": C["ci_single_event"]["events_per_hour"], "rule": "<= 10 (K and C)",
                                     "met": K["events_per_hour"] <= 10 and C["events_per_hour"] <= 10},
        "A3_K_event_detection_single": {"value": K["mean_event_detection_single"], "M2": a("A3_K_event_detection_single")["value"], "m2_shared_families": K["m2_shared"]["mean_event_detection"],
                                        "M2_m2_shared_families": K["m2_shared"]["m2_mean_event_detection"], "ci": K["ci_single_event"]["mean"],
                                        "rule": ">= 0.70 (single-domain families; comparison rows and LiDAR episodes excluded)", "met": K["mean_event_detection_single"] >= 0.70},
        "A4_K_heldout_event_detection": {"value": K["mean_event_detection_heldout"], "M2": a("A4_K_heldout_event_detection")["value"], "ci": K["ci_heldout_event"]["mean"], "rule": ">= 0.60",
                                         "met": K["mean_event_detection_heldout"] >= 0.60},
        "A5_K_blame": {"correct": K["blame_single_pooled"]["correct"], "wrong": K["blame_single_pooled"]["wrong"], "M2_correct": a("A5_K_blame")["value"]["correct"],
                       "M2_wrong": a("A5_K_blame")["value"]["wrong"], "value": K["blame_single_pooled"],
                       "rule": "correct >= 0.75 and wrong <= 0.10 (detected single-domain K events, pooled; decided-majority event blame)",
                       "met": K["blame_single_pooled"]["correct"] >= 0.75 and K["blame_single_pooled"]["wrong"] <= 0.10},
        "A6_safe_stop_per_clean_hour": {"K": K["clean_response_per_hour"]["SAFE_STOP"], "C": C["clean_response_per_hour"]["SAFE_STOP"], "M2_K": a("A6_safe_stop_per_clean_hour")["K"],
                                        "M2_C": a("A6_safe_stop_per_clean_hour")["C"], "rule": "<= 1 (K and C; SAFE_STOP needs >= 2 corroborating domains)",
                                        "met": K["clean_response_per_hour"]["SAFE_STOP"] <= 1 and C["clean_response_per_hour"]["SAFE_STOP"] <= 1},
        "A7_explained": {"K_share": K["explanations"]["with_explanation"] / max(K["explanations"]["events"], 1), "C_share": C["explanations"]["with_explanation"] / max(C["explanations"]["events"], 1),
                         "K": [K["explanations"]["with_explanation"], K["explanations"]["events"]], "C": [C["explanations"]["with_explanation"], C["explanations"]["events"]],
                         "rule": "100% of alert events", "met": all(x["explanations"]["with_explanation"] == x["explanations"]["events"] for x in (K, C))},
    }


def main():
    fz = pickle.load(open(OUT / "s5b_frozen.pkl", "rb"))
    m2 = json.loads((OUT / "s5_test.json").read_text())
    m2acc = json.loads((OUT / "s5_acceptance.json").read_text())
    log("S5b TEST run (once).", fz["calibration_choice"], fz["correlator_choice"]["key"], fz["blame_choice"]["blame_rule"])
    packs = L.assemble(L.load_unique("test"))
    res = {"calibration_choice": fz["calibration_choice"], "correlator_choice": fz["correlator_choice"], "blame_choice": fz["blame_choice"], "composites": fz["composites_test"],
           "exposure": "4th scoring of fusion test data (S3, S4, S5 before) on a NEW random pairing of the domain test streams (seed [42, 66, 5, ord(family)]); every domain "
                       "test set was scored before (KITTI LiDAR test drives: 8th exposure; ROAD >= 6x, D10 several, VeReMi 2x, comma 2x)", "system": {}}
    comps_all = {}
    for fam in ("K", "C"):
        c = fz["composites_test"][fam]
        comps = L3.build_set(fam, packs[fam], None, c["seed"], c["n_clean"], c["n_attack"])
        comps_all[fam] = comps
        log(fam, "test composites", len(comps), "clean hours", round(sum(x["n"] for x in comps if x["family"] == "none") / 3600, 2))
        res["system"][fam], _, _ = run_family(fam, fz, packs[fam], comps, m2["system"][fam])
    (OUT / "s5b_test_partial.json").write_text(json.dumps(res, indent=1, default=str))       # checkpoint before the coupling part
    # coupling test
    dom = LB.load_domain()
    res["coupling"] = {"scan_level": scan_level_coupling(dom)}
    log("coupling scan level", {f: (round(v["clean_alarm"], 4), round(v["coupled_alarm"], 4)) for f, v in res["coupling"]["scan_level"].items()})
    ctrl, coup = coupling_composites(dom, comps_all["K"], packs["K"])
    sysm = fz["systems"]["K"]
    res["coupling"]["composites_control_synced"] = coupling_summary(sysm, ctrl)
    res["coupling"]["composites_coupled"] = coupling_summary(sysm, coup)
    res["coupling"]["model"] = ("INS position follows the spoofed GNSS 1:1 (worst case), yaw unchanged; L2c / L2d recomputed from raw scans with the shifted pose; control = the same "
                                "scans with the true pose, synchronised with the GPS run")
    for f in COUPLED_FAMS:
        a, b = res["coupling"]["composites_control_synced"].get(f), res["coupling"]["composites_coupled"].get(f)
        if a:
            log("coupling", f, "lidar own post-onset", round(a["lidar_own_alarm_post_onset_ticks"], 4), "->", round(b["lidar_own_alarm_post_onset_ticks"], 4), "blamed lidar",
                a["blamed_lidar"], "->", b["blamed_lidar"], "blame", b["blame"], "resp", b["response_max"])
    K, C = res["system"]["K"], res["system"]["C"]
    acc = acceptance(K, C, m2acc)
    cs, cc = res["coupling"]["composites_control_synced"], res["coupling"]["composites_coupled"]
    gps = [f for f in CU.GPS_FAMS if f in cc]
    acc["coupling_test"] = {"lidar_own_alarm_post_onset_control": float(np.mean([cs[f]["lidar_own_alarm_post_onset_ticks"] for f in gps])),
                            "lidar_own_alarm_post_onset_coupled": float(np.mean([cc[f]["lidar_own_alarm_post_onset_ticks"] for f in gps])),
                            "blamed_lidar_control": float(np.mean([cs[f]["blamed_lidar"] or 0.0 for f in gps])), "blamed_lidar_coupled": float(np.mean([cc[f]["blamed_lidar"] or 0.0 for f in gps])),
                            "rule": "reported, not judged (GPS families, mean over drift / accel_drift / doppler_spoof / meaconing)", "verdict": "reported"}
    res["acceptance"] = acc
    (OUT / "s5b_test.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "s5b_acceptance.json").write_text(json.dumps(acc, indent=1, default=str))
    for k, v in acc.items():
        log(k, v.get("met", v.get("verdict")), {a: b for a, b in v.items() if a not in ("rule", "met", "value")})
    log("done")


if __name__ == "__main__":
    main()
