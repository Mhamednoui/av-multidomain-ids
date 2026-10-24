"""WP6 S5b stage 2 (VALIDATION ONLY): choose the LiDAR entry variant x label-free budget allocation, the correlator and the decided-majority blame rule of the
system after the M2 addendum with nested held-out estimates over the 3 S5 group folds of validation; freeze it as fusion/system.py SystemV2 (config version 2).
Rules: notes/WP6_crossdomain.md "S5b start" (written before any S5b result). S4 held-out types, comparison rows and LiDAR episode families never enter a choice.
Run: python -u -W ignore tools/WP6_S5b_dev.py      Outputs: results/WP6/s5b_dev.json, s5b_frozen.pkl, system_v2.pkl, system_v2.json
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED, results_dir  # noqa: E402
from fusion.correlator import TemporalCorrelator  # noqa: E402
from fusion.system import CONFIG_VERSION, SystemV2, entry_domain  # noqa: E402
import WP6_S5_lib as L5  # noqa: E402
import WP6_S5b_lib as L  # noqa: E402

OUT = results_dir("WP6")
N_CLEAN, N_ATT = 300, 40
FA_MAX, EV_MAX, WRONG_MAX = 0.025, 10.0, 0.10
BLAME_CANDIDATES = ("majority_all", "majority_decided")
SAFE_STOP_MIN_DOMAINS = 2
TEST_COMPOSITES = {"K": {"n_clean": 2000, "n_attack": 300, "seed": [SEED, 66, 5, ord("K")]},
                   "C": {"n_clean": 1000, "n_attack": 300, "seed": [SEED, 66, 5, ord("C")]}}      # NEW pairing (notes "S5b start")
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def pooled(fs, ho, corr=None, cols=None):
    outs = []
    ents = fs.ents if cols is None else [fs.ents[i] for i in cols]
    for f, (s, T) in ho.items():
        X = fs.X[(f, frozenset(set(range(L.N_FOLDS)) - {f}))]
        outs += L.evaluate(fs.comps[f], X if cols is None else X[:, cols], s, T, ents, corr)
    return outs


def sel(m, fam, key="detection"):
    fams = L.selection_families(m["families"], fam)
    assert not any(m["families"][f]["category"] == "heldout" for f in fams)
    return [m["families"][f][key] for f in fams]


def corr_of(k, blame="majority_all", min_dom=SAFE_STOP_MIN_DOMAINS):
    return TemporalCorrelator(*k, blame_rule=blame, safe_stop_min_domains=min_dom)


def main():
    u = L.load_unique("val")
    folds = L.make_folds(u)
    packs = L.assemble(u)
    comps = {fam: L5.fold_composites(packs, folds, fam, N_CLEAN, N_ATT) for fam in ("K", "C")}
    for fam in ("K", "C"):
        log(fam, "fold composites", {f: len(c) for f, c in comps[fam].items()})
    fsc = {("K", v, lc): L.FoldScores(u, folds, comps["K"], "K", L.entries("K", v), lc) for v in L.VARIANTS for lc in L.LIDAR_CALS}
    fsc[("C", None, None)] = L.FoldScores(u, folds, comps["C"], "C", L.entries("C"))
    fs_of = lambda fam, v: fsc[("K",) + tuple(v)] if fam == "K" else fsc[("C", None, None)]
    log("fold scores built")
    res = {"note": "VALIDATION only (3 group folds of S5, nested held-out). S4 held-out families, comparison rows and LiDAR episode families excluded from every choice.",
           "fixed_a_priori": {"procedure": "logo", "alpha": L.ALPHAS, "budget_tick": 0.02, "safe_stop_min_domains": SAFE_STOP_MIN_DOMAINS},
           "n_clean_per_fold": N_CLEAN, "n_attack_per_family_per_fold": N_ATT, "calibration_grid": {}, "correlator_grid": {}, "blame_grid": {}}
    # ---------------- (1) LiDAR entry x budget allocation
    grid = [((v, lc), m) for lc in L.LIDAR_CALS for v in L.VARIANTS for m in L.METHODS]    # lidar_cal trainval = round 2 (post-hoc, labelled)
    score = {}
    for v, method in grid:
        row, det = {}, []
        for fam in ("K", "C"):
            fs = fs_of(fam, v)
            mm = L.summary(pooled(fs, L.heldout_scores(fs, method)))
            d = sel(mm, fam)
            det += d
            row[fam] = {"fa_tick": mm["fa_tick"], "events_per_hour_raw": mm["events_per_hour"], "mean_detection_selection": float(np.mean(d)), "n_families": len(d),
                        "lidar_families": {f: x["tick_detection"] for f, x in mm["families"].items() if x["attacked"] == "lidar"} if fam == "K" else None}
            if method == "wsplit":
                w, rho = L.wsplit_weights(fs, tuple(range(L.N_FOLDS)))
                row[fam]["weights"] = dict(zip(fs.ents, map(float, w)))
                row[fam]["rho"] = dict(zip(fs.ents, map(float, rho)))
        row["pooled_detection"] = float(np.mean(det))
        row["qualifies"] = row["K"]["fa_tick"] <= FA_MAX and row["C"]["fa_tick"] <= FA_MAX
        key = f"lidar={v[0]}|cal={v[1]}|{method}"
        res["calibration_grid"][key] = row
        score[(v, method)] = row
        log(key, "FA K/C", round(row["K"]["fa_tick"], 4), round(row["C"]["fa_tick"], 4), "det", round(row["pooled_detection"], 4), "OK" if row["qualifies"] else "")
    simp = lambda g: (L.LIDAR_CALS.index(g[0][1]), L.VARIANTS.index(g[0][0]), L.METHODS.index(g[1]))
    q = [g for g in grid if score[g]["qualifies"]]
    if q:
        best = max(q, key=lambda g: (round(score[g]["pooled_detection"], 6), tuple(-x for x in simp(g))))
        rule = f"held-out FA <= {FA_MAX} (K and C), then highest pooled selection detection, ties -> simpler"
    else:
        best = min(grid, key=lambda g: (max(score[g]["K"]["fa_tick"], score[g]["C"]["fa_tick"]), simp(g)))
        rule = "no config met the FA bound -> lowest max(FA_K, FA_C)"
    variant, method = best
    res["calibration_choice"] = {"lidar_entry": variant[0], "lidar_cal": variant[1], "method": method, "procedure": "logo", "rule": rule, "n_qualifying": len(q)}
    log("CHOSEN calibration", res["calibration_choice"])
    # ---------------- (2) correlator (S5 grid and rule) on the chosen calibration
    ho = {fam: L.heldout_scores(fs_of(fam, variant), method) for fam in ("K", "C")}
    cs = {}
    for k in L.CORR_GRID:
        corr = corr_of(k)
        row, det = {}, []
        for fam in ("K", "C"):
            mm = L.summary(pooled(fs_of(fam, variant), ho[fam], corr))
            d = sel(mm, fam)
            det += d
            row[fam] = {"events_per_hour": mm["events_per_hour"], "fa_tick": mm["fa_tick"], "mean_event_detection_selection": float(np.mean(d)),
                        "clean_response_per_hour": mm["clean_response_per_hour"]}
        row["pooled_event_detection"] = float(np.mean(det))
        row["qualifies"] = row["K"]["events_per_hour"] <= EV_MAX and row["C"]["events_per_hour"] <= EV_MAX
        cs[k] = row
        res["correlator_grid"][corr.key()] = row
        log(corr.key(), "events/h K/C", round(row["K"]["events_per_hour"], 2), round(row["C"]["events_per_hour"], 2), "det", round(row["pooled_event_detection"], 4), "OK" if row["qualifies"] else "")
    qc = [k for k in L.CORR_GRID if cs[k]["qualifies"]]
    if qc:
        bc = max(qc, key=lambda k: (round(cs[k]["pooled_event_detection"], 6), tuple(-x for x in L.corr_simplicity(k))))
        crule = f"held-out events per clean hour <= {EV_MAX} (K and C), then highest pooled event detection, ties -> simpler"
    else:
        bc = min(L.CORR_GRID, key=lambda k: (max(cs[k]["K"]["events_per_hour"], cs[k]["C"]["events_per_hour"]), L.corr_simplicity(k)))
        crule = "no config met the events bound -> lowest max(events K, events C)"
    res["correlator_choice"] = {"m": bc[0], "w": bc[1], "gap": bc[2], "corroborate": bc[3], "key": corr_of(bc).key(), "rule": crule, "n_qualifying": len(qc)}
    log("CHOSEN correlator", res["correlator_choice"])
    # ---------------- (3) decided-majority blame (plurality = M2 reference row only)
    bs = {}
    for rule_b in ("plurality",) + BLAME_CANDIDATES:
        row = {}
        for fam in ("K", "C"):
            outs = pooled(fs_of(fam, variant), ho[fam], corr_of(bc, rule_b))
            mm = L.summary(outs)
            row[fam] = L.blame_pool(outs, set(L.selection_families(mm["families"], fam)))
            row[fam]["clean_response_per_hour"] = mm["clean_response_per_hour"]
        row["qualifies"] = rule_b != "plurality" and row["K"]["wrong"] <= WRONG_MAX and row["C"]["wrong"] <= WRONG_MAX
        row["mean_correct"] = float(np.mean([row["K"]["correct"], row["C"]["correct"]]))
        bs[rule_b] = row
        res["blame_grid"][rule_b] = row
        log("blame", rule_b, "K", {a: round(b, 4) for a, b in row["K"].items() if a != "clean_response_per_hour"}, "C",
            {a: round(b, 4) for a, b in row["C"].items() if a != "clean_response_per_hour"})
    qb = [b for b in BLAME_CANDIDATES if bs[b]["qualifies"]]
    if qb:
        bb = max(qb, key=lambda b: (round(bs[b]["mean_correct"], 6), -BLAME_CANDIDATES.index(b)))
        brule = f"wrong blame <= {WRONG_MAX} (K and C), then highest mean correct, ties -> majority_all"
    else:
        bb = min(BLAME_CANDIDATES, key=lambda b: (round(max(bs[b]["K"]["wrong"], bs[b]["C"]["wrong"]), 6), BLAME_CANDIDATES.index(b)))
        brule = "no rule met the wrong-blame bound -> lowest max wrong"
    res["blame_choice"] = {"blame_rule": bb, "rule": brule, "n_qualifying": len(qb)}
    log("CHOSEN blame", res["blame_choice"])
    corr = corr_of(bc, bb)
    # ---------------- (4) freeze (deployed calibration on all folds; LOGO threshold), ablation thresholds, validation held-out numbers
    frozen = {"calibration_choice": res["calibration_choice"], "correlator_choice": res["correlator_choice"], "blame_choice": res["blame_choice"],
              "composites_test": TEST_COMPOSITES, "systems": {}, "ablation": {}, "folds": folds}
    res["val_heldout_chosen"], res["ablation_val"] = {}, {}
    allf = tuple(range(L.N_FOLDS))
    for fam in ("K", "C"):
        fs = fs_of(fam, variant)
        T, F, w = L.procedure_threshold(fs, method, allf)
        dens, fus = fs.cal[frozenset(allf)]
        fus.method, fus.threshold, fus.weights = method, float(T), None if w is None else np.asarray(w, float)
        sysm = SystemV2(fs.ents, dens, fus, corr, meta={"family": fam, "config_version": CONFIG_VERSION, "procedure": "logo", "alpha": L.ALPHAS, "lidar_entry": variant[0] if fam == "K" else None, "lidar_cal": variant[1] if fam == "K" else None,
                                                        "lidar": "FROZEN lidar/domain.py (WP3 S9)", "status": "system re-frozen after the M2 addendum (WP6 S5b)"})
        frozen["systems"][fam] = sysm
        mm = L.summary(pooled(fs, ho[fam], corr))
        res["val_heldout_chosen"][fam] = {"fa_tick": mm["fa_tick"], "events_per_hour": mm["events_per_hour"], "by_category_event": {c: v for c, v in mm["by_category"].items() if c != "heldout"},
                                          "clean_response_per_hour": mm["clean_response_per_hour"], "deployed_threshold": float(T),
                                          "weights": None if w is None else dict(zip(fs.ents, map(float, w)))}
        frozen["ablation"][fam], res["ablation_val"][fam] = {}, {}
        for d in L.domains_of(fs.ents):
            cols = [i for i, e in enumerate(fs.ents) if entry_domain(e) != d]
            Tj, _, wj = L.procedure_threshold(fs, method, allf, cols)
            frozen["ablation"][fam][f"without {d}"] = {"cols": cols, "threshold": float(Tj), "weights": None if wj is None else np.asarray(wj, float)}
            mj = L.summary(pooled(fs, L.heldout_scores(fs, method, cols), corr, cols))
            res["ablation_val"][fam][f"without {d}"] = {"fa_tick": mj["fa_tick"], "events_per_hour": mj["events_per_hour"],
                                                        "mean_event_detection_selection": float(np.mean(sel(mj, fam))), "deployed_threshold": float(Tj)}
        log(fam, "frozen; threshold", round(T, 6), "val held-out FA", round(res["val_heldout_chosen"][fam]["fa_tick"], 4), "events/h", round(res["val_heldout_chosen"][fam]["events_per_hour"], 2))
    pickle.dump(frozen, open(OUT / "s5b_frozen.pkl", "wb"))
    pickle.dump(frozen["systems"], open(OUT / "system_v2.pkl", "wb"))
    summ = {"status": "System re-frozen after the M2 addendum (WP6 S5b, 2026-10-25), config version 2; replaces the M2 system (results/WP6/m2_system.pkl) for WP7 S2",
            "config_version": CONFIG_VERSION,
            "how_to_load": "fusion.system.load_system(2) -> {'K': SystemV2, 'C': SystemV2}; SystemV2.run(parts) (fusion/system.py)",
            "inputs": "per-tick parts per DOMAIN: score (domain combined calibrated tick max), count (samples in the tick), layers / layer_alarm (per-layer scores / own alarms; "
                      "LiDAR: 4 columns L1, L2a, L2c, L2d), dom_alarm, blame (cross)",
            "lidar_input": "frozen lidar/domain.py (results/WP3/S9/frozen_lidar), LidarDomain.stream().push(points, pose, t) per scan; tick = floor(scan time); tick value = max over "
                           "the scans of the second of the combined score and of every per-layer score; own alarm = any scan alarm in the second (combined / per layer)",
            "v2x_input": "VeReMi-calibrated frozen physics stack for the VeReMi view; on REAL V2X (V2AIX) the on-deployment variant (WP5 S3b thresholds fitted on the "
                         "deployment's own genuine validation + freshness age check) must replace it and the v2x entry ECDF must be re-fitted on that deployment's clean ticks",
            "systems": {fam: {"entries": s.entries, "domains": s.domains, "method": s.fusion.method, "threshold": s.fusion.threshold,
                              "weights": None if s.fusion.weights is None else dict(zip(s.entries, map(float, s.fusion.weights))),
                              "density_alpha": {d: t.alpha for d, t in s.density.items()}, "correlator": s.correlator.to_dict(), "budget_tick": s.fusion.budget}
                        for fam, s in frozen["systems"].items()},
            "response_policy": "fusion/correlator.py respond(): WARN every event; DEGRADE blamed domain >= 3 blamed ticks; SAFE_STOP (>= 2 motion-critical domains degraded or a "
                               "motion-critical degrade lasting >= 30 s) AND >= 2 different domains with their own alarm in the event; V2X / network alone never above DEGRADE; "
                               f"event blame = {bb}"}
    (OUT / "system_v2.json").write_text(json.dumps(summ, indent=1))
    (OUT / "s5b_dev.json").write_text(json.dumps(res, indent=1, default=str))
    log("done")


if __name__ == "__main__":
    main()
