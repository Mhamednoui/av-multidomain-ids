"""WP1 S8 final pass: ONE evaluation on the KITTI test drives of the default GPS stack with everything fitted on the 15 development drives
with runs (CUSUM configuration = the full-dev selection of WP1_S8_dev.py, layer ECDF calibration + 1% thresholds, combiner = the method chosen
by the pre-registered rule on the nested dev results, fitted WITHOUT the Doppler / meaconing attack rows). Outputs per layer alone, per
combiner method, the deployed combined detector (run- and row-level per attack, delays, per-drive FA, bootstrap CIs over test drives / runs,
paired difference to B2), ablation (all-but-one, + optional layers), and the val-only (3 drives) calibration side by side.
WP1_S8_DRY=1: code check with "test" := val rows, output to the temp folder.
Outputs: results/WP1/S8_kitti.json. Run from codes_v3/: python -u -W ignore tools/WP1_S8_test.py
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S8_lib as W
from gps import stack as ST

DRY = bool(int(os.environ.get("WP1_S8_DRY", "0")))
OUT = Path(tempfile.gettempdir()) / "wp1_s8_dry" if DRY else W.L.OUT
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()
VAL = ["0011", "0035", "0027"]


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def full_summary(test, flag):
    """L.summarize (run/row-level, delays, slow drift, clean FA) as stored by S4-S7."""
    sm = W.L.summarize(test, flag)
    return sm


def by_severity(test, ri, flag):
    """Run-level detection per attack in three equal severity bins of the generator range (gps.stream.SEV)."""
    from gps import stream as S
    det = ri.detected(flag)
    sev = test["severity"].to_numpy(float)[ri.start]
    out = {}
    for a in ST.ATTACKS:
        lo, hi = S.SEV[a]
        if hi <= lo:
            continue
        e = np.linspace(lo, hi, 4)
        m = ri.run_attack == a
        out[a] = {"edges": e.tolist(), "detected": [float(det[m & (sev >= e[i]) & (sev <= e[i + 1] if i == 2 else sev < e[i + 1])].mean())
                                                    for i in range(3)],
                  "runs": [int((m & (sev >= e[i]) & (sev <= e[i + 1] if i == 2 else sev < e[i + 1])).sum()) for i in range(3)]}
    return out


def main():
    raw = W.load_raw()
    dev = raw[raw["part"].isin(W.DEV_PARTS)].copy()
    test = (raw[raw["part"] == "val"] if DRY else raw[raw["part"] == "test"]).copy()
    ri_dev, ri_t = ST.RunIndex(dev), ST.RunIndex(test)
    drives = sorted(dev["drive"].unique())
    names, opt = ST.DEFAULT_LAYERS, ST.OPTIONAL_LAYERS
    dj = json.loads((W.L.OUT / "S8_dev.json").read_text())
    chosen = dj["chosen_method"]
    log("chosen method (dev rule):", chosen, "| test rows", len(test), "runs", len(ri_t.start), "drives", sorted(set(test["drive"])))
    F = W.FoldState(dev, ri_dev, drives, names, W.candidates(dev), optional=opt)
    assert F.sel["ekf"] == dj["cusum_selection"]["full_dev"]["ekf"] and F.sel["dr"] == dj["cusum_selection"]["full_dev"]["dr"]
    raw_t, cal_t, flags_t = F.apply(test)
    y_dev, g_dev = dev["label"].to_numpy(), dev["drive"].to_numpy()
    unseen = ((dev["attack"].isin(["doppler_spoof", "meaconing"])) & (dev["label"] == 1)).to_numpy()
    yt = test["label"].to_numpy()
    res = {"dry": DRY, "chosen_method": chosen, "chosen_reason": dj["chosen_reason"], "cusum_selection": F.sel, "n_test_rows": len(test),
           "n_test_runs": int(len(ri_t.start)), "test_drives": sorted(set(test["drive"]))}

    def fit_and_score(method, nm, exclude=True, Fx=F, dev_rows=None, cal_x=cal_t):
        X = Fx.matrix(sorted(nm))
        m = np.ones(len(dev), bool) if dev_rows is None else dev_rows
        fm = m & ~unseen if exclude else m
        c = ST.MatrixCombiner(method=method).fit_matrix(sorted(nm), X[fm], y_dev[fm], g_dev[fm])
        s = c.score_matrix(ST.stack_matrix(cal_x, sorted(nm)))
        return c, s, s >= c.threshold

    # ---- layers alone ----
    alone = {}
    for n in names + opt:
        alone[n] = W.compact(test, ri_t, flags_t[n], raw_t[n])
        alone[n]["summary"] = full_summary(test, flags_t[n])
        alone[n]["threshold_raw"] = F.thr[n]
    res["layers_test"] = alone
    log("layers done")
    # ---- combiners ----
    comb = {}
    for m in ST.METHODS_EXT + ("auto",):
        c, s, f = fit_and_score(m, names)
        comb[m] = W.compact(test, ri_t, f, s)
        comb[m]["deployed_method_after_auto"] = c.method
        comb[m]["threshold_S"] = float(c.threshold)
        log("combiner", m, "FA", round(comb[m]["fa_clean_runs"], 4), "mean", round(comb[m]["mean_run_detected"], 3))
    c, s, f = fit_and_score("logistic", names, exclude=False)
    comb["logistic_all6_seen"] = W.compact(test, ri_t, f, s)
    res["combiners_test"] = comb
    # ---- deployed ----
    c_dep, s_dep, f_dep = fit_and_score(chosen, names)
    dep = W.compact(test, ri_t, f_dep, s_dep)
    dep["summary"] = full_summary(test, f_dep)
    dep["threshold_S"] = float(c_dep.threshold)
    dep["bootstrap"] = W.bootstrap_ci(ri_t, f_dep, s_dep)
    dep["vs_B2_paired"] = W.bootstrap_diff(ri_t, f_dep, flags_t["gps.dr_resid_10"])
    dep["vs_cusum_dr_paired"] = W.bootstrap_diff(ri_t, f_dep, flags_t["gps.cusum_dr"])
    dep["by_severity"] = by_severity(test, ri_t, f_dep)
    res["deployed"] = dep
    for n in ("gps.dr_resid_10", "gps.cusum_dr", "gps.ekf_nis"):
        res["layers_test"][n]["bootstrap"] = W.bootstrap_ci(ri_t, flags_t[n], np.minimum(raw_t[n], 1e300))
        res["layers_test"][n]["by_severity"] = by_severity(test, ri_t, flags_t[n])
    log("deployed", chosen, "FA", round(dep["fa_clean_runs"], 4), "mean run", round(dep["mean_run_detected"], 3), {a: round(v, 2) for a, v in dep["run_detected"].items()})
    # ---- ablation ----
    abl = {"all": dep}
    for n in names:
        rest = [x for x in names if x != n]
        _, s, f = fit_and_score(chosen, rest)
        abl["all_but_" + n] = W.compact(test, ri_t, f, s)
    for n in opt:
        _, s, f = fit_and_score(chosen, names + [n])
        abl["plus_" + n] = W.compact(test, ri_t, f, s)
    res["ablation_test"] = abl
    log("ablation done")
    # ---- val-only (3 drives) calibration side by side ----
    val_drv = [d for d in VAL if d in drives]
    Fv = W.FoldState(dev, ri_dev, val_drv, names, W.candidates(dev), sel=F.sel, optional=opt)
    raw_v, cal_v, flags_v = Fv.apply(test)
    rows_v = np.isin(g_dev, val_drv)
    _, s_v, f_v = fit_and_score(chosen, names, Fx=Fv, dev_rows=rows_v, cal_x=cal_v)
    vo = {"calibration_drives": val_drv, "deployed": W.compact(test, ri_t, f_v, s_v),
          "layers": {n: W.compact(test, ri_t, flags_v[n], raw_v[n]) for n in names}}
    res["val_only"] = vo
    # ---- regression check against the S7 harness numbers (same LODO-pooled thresholds) ----
    if not DRY:
        s7 = json.loads((W.L.OUT / "S7_kitti.json").read_text())["calibration"]["lodo"]["per_layer"]
        chk = {}
        for n in ("gps.dr_resid_10", "gps.ekf_nis", "gps.cusum_dr", "gps.cusum_ekf", "gps.lidar_z_1"):
            ref = s7[n]["run_detected"]
            chk[n] = {"max_abs_diff_run_level": max(abs(alone[n]["run_detected"][a] - ref[a]) for a in ST.ATTACKS),
                      "fa_diff": abs(alone[n]["fa_clean_runs"] - s7[n]["false_alarm_clean_runs"])}
        res["regression_vs_S7"] = chk
        log("regression vs S7", chk)
    (OUT / "S8_kitti.json").write_text(json.dumps(res, indent=1, default=float))
    log("done ->", OUT / "S8_kitti.json")


if __name__ == "__main__":
    main()
