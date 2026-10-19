"""WP1 S3 step 2: evaluate the L2a EKF / NIS layer once on test (KITTI, AV-GPS, UAV). Noise parameters and gate level come
from results/WP1/S3_tuning.json (TRAIN / VAL only; UAV: benign flight). Thresholds: tie-safe 1% budget on validation normal rows
(UAV: benign flight).
Outputs: results/WP1/S3_kitti.json, S3_kitti_*.{json,md} (harness), S3_avgps.json, S3_uav.json, S3_tables.md.
Run from codes_v3/: python -u -W ignore tools/WP1_S3_ekf.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import WP1_S1_b2 as S1
import WP1_S2_l1 as S2
from common.config import SEED, results_dir
from common.evaluate import evaluate_domain, score_groups
from common.metrics import auc, budget_threshold
from gps import ekf, l1
from gps import stream as S
from gps.ekf import EKFConfig

BUDGET = 0.01
ATT = S.ATTACKS_V2 + S.ATTACKS_NEW
OUT = results_dir("WP1")
TUNE = json.loads((OUT / "S3_tuning.json").read_text())


def kitti_cfg(gated):
    c = EKFConfig(gm_phi=TUNE["kitti_gm_estimate_train"]["phi"], gm_sigma=TUNE["kitti_gm_estimate_train"]["sigma"],
                  q_acc=TUNE["kitti_q_acc"])
    return c.gated(TUNE["kitti_gate_level"]) if gated else c


def consistency(df, cfg):
    r = ekf.run_filter_all(df, cfg)
    ok = ~np.isnan(r["nis"].to_numpy())
    nis, dim = r["nis"].to_numpy()[ok], r["dim"].to_numpy()[ok]
    return {"rows": int(ok.sum()), "mean_nis": float(nis.mean()), "mean_dim": float(dim.mean()),
            "ratio": float(nis.mean() / dim.mean()), "frac_above_chi2_95": float((nis > chi2.ppf(0.95, dim)).mean())}


def absorption(te, cfg):
    """Position estimate error vs truth 10 / 30 s after onset (and ratio to the reported-position error)."""
    r = ekf.run_filter_all(te, cfg)
    d = te.assign(est_x=r["est_x"], est_y=r["est_y"], hold=r["hold"])
    d["e_est"] = np.hypot(d["est_x"] - d["x_true"], d["est_y"] - d["y_true"])
    d["e_rep"] = np.hypot(d["x"] - d["x_true"], d["y"] - d["y_true"])
    out = {"clean_runs_median_estimate_error_m": float(d.loc[d["attack"] == "none", "e_est"].median()),
           "clean_runs_median_reported_error_m": float(d.loc[d["attack"] == "none", "e_rep"].median())}
    for a in ATT:
        o = {}
        for lag in (10, 30):
            ee, er, hl = [], [], []
            for _, g in d[d["attack"] == a].groupby("run"):
                k = int(g["onset"].iloc[0]) + lag
                if k < len(g):
                    ee.append(g["e_est"].iloc[k]); er.append(g["e_rep"].iloc[k]); hl.append(g["hold"].iloc[k])
            ee, er = np.array(ee), np.array(er)
            big = er >= 5.0
            o[f"+{lag}s"] = {"runs": int(len(ee)), "median_estimate_error_m": float(np.median(ee)) if len(ee) else None,
                             "median_reported_error_m": float(np.median(er)) if len(er) else None,
                             "runs_with_reported_error_ge_5m": int(big.sum()),
                             "median_absorbed_fraction_est_over_rep": float(np.median(ee[big] / er[big])) if big.any() else None,
                             "fraction_in_hold": float(np.mean(hl)) if hl else None}
        out[a] = o
    return out


def within_30s_slow_drift(te, flag):
    runs = te.assign(f=flag)
    d = runs[(runs["attack"] == "drift") & (runs["severity"] < 0.5)]
    hits, n = 0, 0
    for _, g in d.groupby("run"):
        n += 1
        k0 = int(g["onset"].iloc[0])
        w = g[(g["k"] >= k0) & (g["k"] < k0 + 30)]
        hits += bool(w["f"].any())
    return {"runs": n, "detected_within_30s": hits / n if n else None}


def run_kitti():
    kx = S.build_kitti(np.random.default_rng(SEED), new_attacks=S.ATTACKS_NEW)
    kx = kx.join(S1.b2_features(kx)).join(l1.l1_features(kx))
    cols = l1.COVERAGE["kitti"]["evaluated"]
    rules = l1.make_rules(cols)
    b2 = S1.B2Layer()
    e_un = ekf.EKFLayer(kitti_cfg(False), "gps.ekf_nis")
    e_g = ekf.EKFLayer(kitti_cfg(True), "gps.ekf_nis_gated")
    val_norm = kx[(kx["part"] == "val") & (kx["label"] == 0)]
    layers = rules + [b2, e_un, e_g]
    for l in layers:
        l.calibrate(val_norm, budget=BUDGET)
    val, test = kx[kx["part"] == "val"], kx[kx["part"] == "test"]
    sets_v, sets_t, flags = [], [], {}
    for lay in layers:
        sv, _ = S1.evalset(lay, val)
        st, ev_t = S1.evalset(lay, test)
        sets_v.append(sv); sets_t.append(st)
        flags[lay.name] = S2.flags_from(ev_t)
    ESv, ESt = S2.merge_evalsets(sets_v), S2.merge_evalsets(sets_t)
    order = np.concatenate([g.index.to_numpy() for _, g in test.groupby("run", sort=False)])
    te = kx.loc[order]
    res = {"tuning": {k: TUNE[k] for k in ("kitti_gm_estimate_train", "kitti_q_acc", "kitti_gate_level", "kitti_primary_variant",
                                          "kitti_consistency_train_clean", "kitti_consistency_val_clean", "kitti_gate_val")},
           "config_ungated": kitti_cfg(False).__dict__, "config_gated": kitti_cfg(True).__dict__}
    res["consistency_test_clean_runs"] = {"ungated": consistency(te[te["attack"] == "none"], kitti_cfg(False))}
    res["per_layer"] = {}
    for lay in (b2, e_un, e_g):
        d = S2.summarize_flags(te, flags[lay.name], ATT)
        d["threshold_raw_equivalent"] = S1.raw_equiv_threshold(lay)
        d["slow_drift_lt_0.5_within_30s"] = within_30s_slow_drift(te, flags[lay.name])
        d["auc_row_level"] = auc(te["label"].to_numpy(), np.array([e.score for e in S1.evalset(lay, test)[1]]))
        res["per_layer"][lay.name] = d
    res["absorption"] = {"ungated": absorption(te, kitti_cfg(False)), "gated": absorption(te, kitti_cfg(True))}
    # --- verdict vs B2 per attack (rule A4) ---
    b2d, ekd = res["per_layer"][b2.name], res["per_layer"]["gps.ekf_nis"]
    fa_ok = ekd["false_alarm_clean_runs"] <= b2d["false_alarm_clean_runs"] + 0.005
    verdict = {}
    for a in ATT:
        diff = ekd["run_detected"][a] - b2d["run_detected"][a]
        verdict[a] = {"ekf_minus_b2_run_level": diff,
                      "verdict": ("beats B2" if (diff >= 0.05 and fa_ok) else "worse than B2" if diff <= -0.05 else "no difference (within 5 points)")}
    res["verdict_ekf_ungated_vs_b2"] = verdict
    res["fa_condition_met"] = bool(fa_ok)
    # --- harness ablation ---
    names = [l.name for l in layers]
    base = [r.name for r in rules] + [b2.name]
    runs = {"S3_kitti_all": base + ["gps.ekf_nis"],
            "S3_kitti_all_gated": base + ["gps.ekf_nis_gated"],
            "S3_kitti_b2_ekf": [b2.name, "gps.ekf_nis"],
            "S3_kitti_ekf_pair": ["gps.ekf_nis", "gps.ekf_nis_gated"]}
    res["harness"] = {}
    for nm, ns in runs.items():
        h = evaluate_domain(nm, S2.subset(ESv, ns), S2.subset(ESt, ns), wp="WP1", budget=BUDGET, method="auto")
        res["harness"][nm] = {"layers": h["layers"], "combined": h["combined"], "ablation": h["ablation"]}
        print(nm, "AUC", round(h["combined"]["auc"], 4), "FA", round(h["combined"]["false_alarm_rate"], 4), flush=True)
    (OUT / "S3_kitti.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def run_avgps():
    av = S.load_avgps()
    av = av.join(l1.l1_features(av))
    c = TUNE["avgps_cfg"]
    cfg = EKFConfig(use_dop=False, acc_mode="none", gm_sigma=1e-3, gm_phi=0.0, r_pos=c["r_pos"], q_acc=c["q_acc"], sd_odo=c["sd_odo"])
    res = {"config": cfg.__dict__, "tuning_train": TUNE["avgps_consistency_train"], "consistency_val": TUNE["avgps_consistency_val"],
           "sensors": "position, odometry speed, heading only (no Doppler, no IMU acceleration in AV-GPS)"}
    val_norm = av[(av["part"] == "val") & (av["label"] == 0)]
    test = av[av["part"] == "test"]
    for name, cf in (("ungated", cfg), ("gated", cfg.gated(TUNE["kitti_gate_level"]))):
        lay = ekf.EKFLayer(cf, f"gps.ekf_nis_{name}").calibrate(val_norm, budget=BUDGET)
        by = {r: g for r, g in test.groupby("run", sort=False)}
        ev = score_groups(lay, by)
        order = np.concatenate([g.index.to_numpy() for g in by.values()])
        te = av.loc[order]
        f, y = S2.flags_from(ev), te["label"].to_numpy()
        sc = np.array([e.score for e in ev])
        huge = (te["r_speed"] * l1.LIMITS["V_MAX"] > 1e5).to_numpy()
        res[name] = {"threshold_raw_equivalent": S1.raw_equiv_threshold(lay),
                     "false_alarm_normal_rows": float(f[y == 0].mean()), "normal_rows_flagged": int(f[y == 0].sum()),
                     "normal_rows": int((y == 0).sum()), "detection_attack_rows": float(f[y == 1].mean()),
                     "auc": auc(y, sc), "attack_rows_flagged_with_step_over_100km": int((f & (y == 1) & huge).sum()),
                     "attack_rows_flagged": int((f & (y == 1)).sum()), "attack_rows": int((y == 1).sum()),
                     "attack_rows_with_step_over_100km": int((huge & (y == 1)).sum()),
                     "detected_by_session": {r: float(f[(te["run"] == r).to_numpy()].mean()) for r in te.loc[te["label"] == 1, "run"].unique()},
                     "false_alarm_by_session": {r: float(f[(te["run"] == r).to_numpy()].mean()) for r in te.loc[te["label"] == 0, "run"].unique()}}
        # detection excluding the placeholder jumps
        m = (y == 1) & ~huge
        res[name]["detection_attack_rows_excluding_step_over_100km"] = float(f[m].mean()) if m.any() else None
        res[name]["attack_rows_excluding_step_over_100km"] = int(m.sum())
    (OUT / "S3_avgps.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def run_uav():
    uav = l1.attach_uav_extras(S.load_uav())
    c = TUNE["uav_cfg"]
    cfg = EKFConfig(use_odo=False, use_head=False, acc_mode="window", gm_phi=c["gm_phi"], gm_sigma=c["gm_sigma"], r_pos=c["r_pos"],
                    sd_dop=c["sd_dop"], q_acc=c["q_acc"])
    fl = {n: uav[uav["run"] == f"uav/{n}"] for n in S.UAV_FLIGHTS}
    res = {"config": cfg.__dict__, "calibration": "noise (grid) and threshold (1% budget, tie-safe) on the BENIGN flight (documented calibration flight)",
           "consistency_benign": TUNE["uav_consistency_benign"], "first_spoofed_fix_s": S2.UAV_FIRST_SPOOFED_FIX_S}
    for name, cf in (("ungated", cfg), ("gated", cfg.gated(TUNE["kitti_gate_level"]))):
        lay = ekf.EKFLayer(cf, f"gps.ekf_nis_{name}").calibrate(fl["benign"], budget=BUDGET)
        o = {"threshold_raw_equivalent": S1.raw_equiv_threshold(lay), "flights": {}}
        for n, f in fl.items():
            lay.reset()
            ev = lay.score(f)
            a = S2.flags_from(ev)
            t = f["t"].to_numpy()
            e = {"fixes": int(len(f)), "alarms": int(a.sum()), "alarm_times_s": [round(float(x), 1) for x in t[a][:30]]}
            r = ekf.run_filter_all(f, cf)
            e["mean_nis_over_dim"] = float(np.nanmean(r["nis"]) / np.mean(r["dim"][1:]))
            if n == "spoofing":
                pre, post = t < S.UAV_SPOOF_ONSET_S, t >= S2.UAV_FIRST_SPOOFED_FIX_S
                e["false_alarm_before_117s"] = float(a[pre].mean()); e["alarms_before_117s"] = int(a[pre].sum()); e["fixes_before_117s"] = int(pre.sum())
                hit = np.flatnonzero(a & post)
                e["first_alarm_after_onset_s"] = float(t[hit[0]]) if len(hit) else None
                e["delay_from_first_spoofed_fix_s"] = float(t[hit[0]] - 118.0) if len(hit) else None
                e["fraction_of_fixes_from_118s_flagged"] = float(a[post].mean())
                e["fraction_118_to_138s_flagged"] = float(a[post & (t < 138)].mean())
                e["fraction_of_fixes_after_138s_flagged"] = float(a[t >= 138].mean()) if (t >= 138).any() else None
                e["flight_duration_s"] = float(t.max())
                e["nis_around_onset"] = {str(round(float(tt), 1)): round(float(v), 2) for tt, v in zip(t, r["nis"]) if 112 <= tt <= 126}
                e["hold_fraction_from_118s"] = float(r["hold"].to_numpy()[post].mean())
            if n == "benign":
                e["false_alarm_in_sample"] = float(a.mean())
            o["flights"][n] = e
        res[name] = o
    (OUT / "S3_uav.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def main():
    k = run_kitti()
    print(json.dumps({k2: v["run_detected"] for k2, v in k["per_layer"].items()}, indent=1), flush=True)
    print(json.dumps(k["verdict_ekf_ungated_vs_b2"], indent=1), flush=True)
    a = run_avgps()
    print(json.dumps({n: {x: a[n][x] for x in ("false_alarm_normal_rows", "detection_attack_rows", "auc")} for n in ("ungated", "gated")}, indent=1), flush=True)
    u = run_uav()
    print(json.dumps({n: {f: {x: v for x, v in e.items() if x != "nis_around_onset"} for f, e in u[n]["flights"].items()} for n in ("ungated", "gated")}, indent=1, default=float), flush=True)


if __name__ == "__main__":
    main()
