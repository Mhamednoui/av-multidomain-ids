"""WP6 S5 stage 2 (VALIDATION ONLY): choose the calibration (procedure x combiner x density alphas) and the temporal correlator of the M2 system with nested
held-out estimates over 3 group folds of validation, then freeze the M2 system (fusion/system.py M2System) for the test run and for WP7.
Rules: notes/WP6_crossdomain.md "S5 start" (written before any S5 result). S4 held-out types never enter a choice (asserted); GhostCluster excluded.
Run: python -u -W ignore tools/WP6_S5_dev.py      Outputs: results/WP6/s5_dev.json, s5_frozen.pkl, m2_system.pkl, m2_system.json
"""
import itertools
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
from fusion.system import M2System  # noqa: E402
import WP6_S5_lib as L  # noqa: E402

OUT = results_dir("WP6")
N_CLEAN, N_ATT = 300, 40
ALPHAS = (0.0, 0.5, 1.0)
FA_MAX, EV_MAX = 0.025, 10.0
TEST_COMPOSITES = {"K": {"n_clean": 2000, "n_attack": 300, "seed": [SEED, 64, 9, ord("K")]},
                   "C": {"n_clean": 1000, "n_attack": 300, "seed": [SEED, 64, 9, ord("C")]}}       # = S4 test composites
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def pooled(fs, ho, fam, corr=None, cols=None, domains=None):
    """Held-out alarms of every fold -> pooled outcomes."""
    outs = []
    domains = domains or L.DOMS[fam]
    for f, (s, T) in ho.items():
        X = fs.X[(f, frozenset(set(range(L.N_FOLDS)) - {f}))] if cols is None else fs.X[(f, frozenset(set(range(L.N_FOLDS)) - {f}))][:, cols]
        outs += L.evaluate(fs.comps[f], X, s, T, domains, corr)
    return outs


def sel_detection(m):
    fams = L.selection_families(m["families"])
    assert not any(m["families"][f]["category"] == "heldout" for f in fams)
    return [m["families"][f]["detection"] for f in fams]


def main():
    u = L.load_unique("val")
    folds = L.make_folds(u)
    log("folds", {k: {f: sorted(g for g, x in v.items() if x == f) for f in range(L.N_FOLDS)} for k, v in folds.items() if k in ("gps", "cross_comma")})
    packs = L.assemble(u)
    comps = {fam: L.fold_composites(packs, folds, fam, N_CLEAN, N_ATT) for fam in ("K", "C")}
    for fam in ("K", "C"):
        log(fam, "fold composites", {f: len(c) for f, c in comps[fam].items()})
    fsc = {}
    for av, an in itertools.product(ALPHAS, ALPHAS):
        for fam in ("K", "C"):
            fsc[(fam, av, an)] = L.FoldScores(u, folds, comps[fam], fam, {"v2x": av, "network": an})
    log("fold scores built", len(fsc))
    res = {"note": "VALIDATION only (3 group folds, nested held-out estimates). S4 held-out families excluded from every choice; their numbers are not stored.",
           "folds": {k: {str(g): int(f) for g, f in v.items()} for k, v in folds.items()}, "n_clean_per_fold": N_CLEAN, "n_attack_per_family_per_fold": N_ATT,
           "calibration_grid": {}, "correlator_grid": {}}
    # ---------------- (1) calibration grid
    grid = list(itertools.product(("halves", "logo"), ("max", "noisy_or"), ALPHAS, ALPHAS))
    score = {}
    for proc, method, av, an in grid:
        key = f"{proc}|{method}|a_v2x={av}|a_net={an}"
        row, det = {}, []
        for fam in ("K", "C"):
            fs = fsc[(fam, av, an)]
            m = L.summary(pooled(fs, L.heldout_scores(fs, method, proc), fam))
            d = sel_detection(m)
            det += d
            row[fam] = {"fa_tick": m["fa_tick"], "events_per_hour_raw": m["events_per_hour"], "mean_detection_selection": float(np.mean(d)), "n_families": len(d)}
        row["pooled_detection"] = float(np.mean(det))
        row["qualifies"] = row["K"]["fa_tick"] <= FA_MAX and row["C"]["fa_tick"] <= FA_MAX
        res["calibration_grid"][key] = row
        score[(proc, method, av, an)] = row
        log(key, "FA K/C", round(row["K"]["fa_tick"], 4), round(row["C"]["fa_tick"], 4), "det", round(row["pooled_detection"], 4), "OK" if row["qualifies"] else "")
    simp = lambda g: ({"halves": 0, "logo": 1}[g[0]], {"max": 0, "noisy_or": 1}[g[1]], g[2], g[3])
    q = [g for g in grid if score[g]["qualifies"]]
    if q:
        best = max(q, key=lambda g: (round(score[g]["pooled_detection"], 6), tuple(-x for x in simp(g))))
        rule = f"held-out FA <= {FA_MAX} (K and C), then highest pooled selection detection, ties -> simpler"
    else:
        best = min(grid, key=lambda g: (max(score[g]["K"]["fa_tick"], score[g]["C"]["fa_tick"]), simp(g)))
        rule = "no config met the FA bound -> lowest max(FA_K, FA_C)"
    proc, method, av, an = best
    res["calibration_choice"] = {"procedure": proc, "method": method, "alpha_v2x": av, "alpha_net": an, "rule": rule, "n_qualifying": len(q)}
    log("CHOSEN calibration", res["calibration_choice"])
    # ---------------- (2) correlator grid on the chosen calibration's held-out alarms
    ho = {fam: L.heldout_scores(fsc[(fam, av, an)], method, proc) for fam in ("K", "C")}
    cs = {}
    for k in L.CORR_GRID:
        corr = TemporalCorrelator(*k)
        row, det = {}, []
        for fam in ("K", "C"):
            m = L.summary(pooled(fsc[(fam, av, an)], ho[fam], fam, corr))
            d = sel_detection(m)
            det += d
            row[fam] = {"events_per_hour": m["events_per_hour"], "fa_tick": m["fa_tick"], "mean_event_detection_selection": float(np.mean(d)),
                        "clean_response_per_hour": m["clean_response_per_hour"],
                        "median_delay_selection": float(np.nanmedian([m["families"][f]["median_delay_s"] if m["families"][f]["median_delay_s"] is not None else np.nan
                                                                      for f in L.selection_families(m["families"])]))}
        row["pooled_event_detection"] = float(np.mean(det))
        row["qualifies"] = row["K"]["events_per_hour"] <= EV_MAX and row["C"]["events_per_hour"] <= EV_MAX
        cs[k] = row
        res["correlator_grid"][corr.key()] = row
        log(corr.key(), "events/h K/C", round(row["K"]["events_per_hour"], 2), round(row["C"]["events_per_hour"], 2), "det", round(row["pooled_event_detection"], 4),
            "safe-stop/h K/C", round(row["K"]["clean_response_per_hour"]["SAFE_STOP"], 2), round(row["C"]["clean_response_per_hour"]["SAFE_STOP"], 2), "OK" if row["qualifies"] else "")
    off = {}
    for fam in ("K", "C"):
        m = L.summary(pooled(fsc[(fam, av, an)], ho[fam], fam, None))
        off[fam] = {"events_per_hour": m["events_per_hour"], "mean_detection_selection": float(np.mean(sel_detection(m)))}
    res["correlator_off_val"] = off
    qc = [k for k in L.CORR_GRID if cs[k]["qualifies"]]
    if qc:
        bc = max(qc, key=lambda k: (round(cs[k]["pooled_event_detection"], 6), tuple(-x for x in L.corr_simplicity(k))))
        crule = f"held-out events per clean hour <= {EV_MAX} (K and C), then highest pooled event detection, ties -> simpler"
    else:
        bc = min(L.CORR_GRID, key=lambda k: (max(cs[k]["K"]["events_per_hour"], cs[k]["C"]["events_per_hour"]), L.corr_simplicity(k)))
        crule = "no config met the events bound -> lowest max(events K, events C)"
    corr = TemporalCorrelator(*bc)
    res["correlator_choice"] = {**corr.to_dict(), "key": corr.key(), "rule": crule, "n_qualifying": len(qc)}
    log("CHOSEN correlator", res["correlator_choice"])
    # ---------------- (3) freeze: deployed calibration (all folds), threshold by the chosen procedure, ablations (each domain removed), held-out val numbers
    frozen = {"calibration_choice": res["calibration_choice"], "correlator_choice": res["correlator_choice"], "composites_test": TEST_COMPOSITES, "systems": {},
              "ablation": {}, "folds": folds}
    res["val_heldout_chosen"], res["ablation_val"] = {}, {}
    for fam in ("K", "C"):
        fs = fsc[(fam, av, an)]
        T, F = L.procedure_threshold(fs, method, proc, tuple(range(L.N_FOLDS)))
        dens, fus = L.fit_cal(u, folds if F != frozenset(range(L.N_FOLDS)) else None, F, fam, {"v2x": av, "network": an})
        if F == frozenset(range(L.N_FOLDS)):
            dens2, fus2 = fs.cal[F]
            assert all(np.array_equal(fus.cal[d].sorted_, fus2.cal[d].sorted_) for d in fus.domains)
        fus.method, fus.threshold = method, float(T)
        sysm = M2System(L.DOMS[fam], dens, fus, corr, meta={"family": fam, "procedure": proc, "alpha_v2x": av, "alpha_net": an,
                                                            "lidar": "INTERIM label-free L1 union", "status": "M2 frozen (WP6 S5)"})
        frozen["systems"][fam] = sysm
        m = L.summary(pooled(fs, ho[fam], fam, corr))
        res["val_heldout_chosen"][fam] = {"fa_tick": m["fa_tick"], "events_per_hour": m["events_per_hour"], "by_category_event": {c: v for c, v in m["by_category"].items() if c != "heldout"},
                                          "clean_response_per_hour": m["clean_response_per_hour"], "deployed_threshold": float(T)}
        frozen["ablation"][fam] = {}
        res["ablation_val"][fam] = {}
        for j, d in enumerate(L.DOMS[fam]):
            cols = [i for i in range(len(L.DOMS[fam])) if i != j]
            Tj, _ = L.procedure_threshold(fs, method, proc, tuple(range(L.N_FOLDS)), cols)
            frozen["ablation"][fam][f"without {d}"] = {"cols": cols, "threshold": float(Tj)}
            hoj = L.heldout_scores(fs, method, proc, cols)
            mj = L.summary(pooled(fs, hoj, fam, corr, cols, [x for x in L.DOMS[fam] if x != d]))
            res["ablation_val"][fam][f"without {d}"] = {"fa_tick": mj["fa_tick"], "events_per_hour": mj["events_per_hour"], "mean_event_detection_selection": float(np.mean(sel_detection(mj))),
                                                        "deployed_threshold": float(Tj)}
        log(fam, "frozen; deployed threshold", round(T, 6), "val held-out", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in res["val_heldout_chosen"][fam].items() if k != "by_category_event"})
    pickle.dump(frozen, open(OUT / "s5_frozen.pkl", "wb"))
    pickle.dump(frozen["systems"], open(OUT / "m2_system.pkl", "wb"))
    summ = {"status": "M2 system FROZEN (WP6 S5, 2026-10-24); LiDAR INTERIM (label-free L1); re-run fusion when M1-LiDAR closes (M2 addendum)",
            "how_to_load": "pickle.load(open('results/WP6/m2_system.pkl','rb')) -> {'K': M2System, 'C': M2System}; M2System.run(parts) (fusion/system.py)",
            "inputs": "per-tick parts per domain: score (domain combined calibrated tick max), count (samples in the tick), dom_alarm, layer_alarm, blame (cross)",
            "systems": {fam: {"entries": s.entries, "method": s.fusion.method, "threshold": s.fusion.threshold, "procedure": proc,
                              "density_alpha": {d: t.alpha for d, t in s.density.items()}, "correlator": s.correlator.to_dict(), "budget_tick": s.fusion.budget}
                        for fam, s in frozen["systems"].items()},
            "response_policy": "fusion/correlator.py respond(): WARN every event; DEGRADE blamed domain >= 3 blamed ticks; SAFE_STOP >= 2 motion-critical domains degraded or "
                               "motion-critical degrade lasting >= 30 s; V2X / network alone never above DEGRADE"}
    (OUT / "m2_system.json").write_text(json.dumps(summ, indent=1))
    (OUT / "s5_dev.json").write_text(json.dumps(res, indent=1, default=str))
    log("done")


if __name__ == "__main__":
    main()
