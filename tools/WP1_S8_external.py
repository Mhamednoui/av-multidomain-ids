"""WP1 S8 external tests of the GPS stack: UAV live-spoofing flight (D06) and AV-GPS sessions (D03). Only layers whose inputs exist are run.
UAV: no wheel odometry (B2 / dead-reckoning CUSUM / LiDAR impossible). Layers: L1 receiver rules (fix, satellites, HDOP, satellite / HDOP /
noise / jamming-indicator jumps, Doppler-vs-position), L2a EKF NIS (IMU + Doppler, UAV noise model of S3), L2b CUSUM on the EKF innovation.
Calibration = the BENIGN flight (calibration flight, in-sample); the spoofing flight is the only test (first spoofed fix 118.0 s, pre-onset fixes
t < 117 s). Combined = noisy_or_log (parameter-free, same as the KITTI deployment). Wilson interval for the pre-onset false alarms (one flight).
AV-GPS: layers L1 kinematic rules, B2, EKF NIS, CUSUM on the EKF innovation and on the dead-reckoning branch with the AV-GPS noise model of S3
(position 6 m white, odometry = Velocity field, compass = Heading field; no Doppler, no IMU). Calibration on the AV-GPS val sessions' normal rows;
KITTI thresholds applied unchanged to the parameter-free layers (rules, B2) as the pure transfer check.
Outputs: results/WP1/S8_external.json. Run from codes_v3/: python -u -W ignore tools/WP1_S8_external.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
import WP1_S8_lib as W
from common.metrics import auc, budget_threshold
from gps import b2, l1
from gps import stack as ST
from gps import stream as S
from gps.cusum import CusumLayer, DRConfig
from gps.ekf import EKFConfig, EKFLayer

BUDGET = 0.01
T0 = time.time()
UAV_FIRST_SPOOFED_FIX_S = 118.0


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def wilson(k, n, z=1.96):
    if n == 0:
        return [None, None]
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [float(max(c - h, 0)), float(min(c + h, 1))]


# ------------------------------------------------------------------------------------------------------------------------------
def uav_eval(t, flag, name):
    out = {"fixes": int(len(t)), "alarms": int(flag.sum()), "alarm_times_s": [round(float(x), 1) for x in t[flag][:15]]}
    if name == "spoofing":
        pre, post = t < S.UAV_SPOOF_ONSET_S, t >= UAV_FIRST_SPOOFED_FIX_S
        hit = np.flatnonzero(flag & post)
        out.update({"pre_onset_fixes": int(pre.sum()), "pre_onset_alarms": int(flag[pre].sum()), "pre_onset_fa": float(flag[pre].mean()),
                    "pre_onset_fa_wilson95": wilson(int(flag[pre].sum()), int(pre.sum())),
                    "first_alarm_after_118s": float(t[hit[0]]) if len(hit) else None,
                    "delay_from_first_spoofed_fix_s": float(t[hit[0]] - UAV_FIRST_SPOOFED_FIX_S) if len(hit) else None,
                    "fraction_flagged_from_118s": float(flag[post].mean()), "fraction_flagged_118_to_138s": float(flag[post & (t < 138)].mean()),
                    "fixes_from_118s": int(post.sum())})
    return out


def run_uav():
    uav = l1.attach_uav_extras(S.load_uav())
    uav = uav.join(l1.l1_features(uav))
    c = L.TUNE["uav_cfg"]
    cfg = EKFConfig(use_odo=False, use_head=False, acc_mode="window", gm_phi=c["gm_phi"], gm_sigma=c["gm_sigma"], r_pos=c["r_pos"], sd_dop=c["sd_dop"], q_acc=c["q_acc"])
    rules = l1.make_rules(l1.COVERAGE["uav"]["evaluated"])
    layers = rules + [EKFLayer(cfg, "gps.ekf_nis"), CusumLayer("ekf", "axis", 1.5, cfg, name="gps.cusum_ekf")]
    benign = uav[uav["run"] == "uav/benign"]
    for l in layers:
        l.calibrate(benign, budget=BUDGET)
    flights = {n: uav[uav["run"] == f"uav/{n}"] for n in S.UAV_FLIGHTS}
    cal, flag = {}, {}
    for n, f in flights.items():
        for l in layers:
            l.reset()
        cal[n] = {l.name: l.calibrator.transform(np.asarray(l.raw_scores(f), float)) for l in layers}
        flag[n] = {l.name: cal[n][l.name] >= l.threshold for l in layers}
    names = sorted(l.name for l in layers)
    res = {"layers_available": names, "layers_not_available": {"gps.dr_resid_10 (B2)": "needs wheel odometry", "gps.cusum_dr": "needs wheel odometry and compass heading",
                                                                 "gps.lidar_*": "no LiDAR in the dataset", "kinematic L1 rules": "car limits do not describe a multirotor"},
           "calibration": "benign flight, 1% budget, tie-safe (in-sample for the benign flight)", "first_spoofed_fix_s": UAV_FIRST_SPOOFED_FIX_S,
           "v2_reference": "GPS-vs-IMU residual alarm at 118.0 s, 0 false alarms; PX4 EKF never alarms"}
    # combined statistic: threshold from the benign flight
    S_b = ST.noisy_or_log(ST.stack_matrix(cal["benign"], names))
    res["layers"], res["combined"], res["ablation"] = {}, {}, {}
    for n in S.UAV_FLIGHTS:
        t = flights[n]["t"].to_numpy(float)
        res["layers"][n] = {nm: uav_eval(t, flag[n][nm], n) for nm in names}
    thr = budget_threshold(S_b, BUDGET)
    for n in S.UAV_FLIGHTS:
        t = flights[n]["t"].to_numpy(float)
        Sx = ST.noisy_or_log(ST.stack_matrix(cal[n], names))
        res["combined"][n] = uav_eval(t, Sx >= thr, n)
        res["combined"][n]["statistic_threshold"] = float(thr)
    for drop in names:
        rest = [x for x in names if x != drop]
        thr_r = budget_threshold(ST.noisy_or_log(ST.stack_matrix(cal["benign"], rest)), BUDGET)
        t = flights["spoofing"]["t"].to_numpy(float)
        Sx = ST.noisy_or_log(ST.stack_matrix(cal["spoofing"], rest))
        e = uav_eval(t, Sx >= thr_r, "spoofing")
        res["ablation"]["all_but_" + drop] = {k: e[k] for k in ("pre_onset_alarms", "pre_onset_fa", "first_alarm_after_118s", "delay_from_first_spoofed_fix_s", "fraction_flagged_from_118s")}
    # which layers fire within 2 s of the first spoofed fix
    t = flights["spoofing"]["t"].to_numpy(float)
    win = (t >= UAV_FIRST_SPOOFED_FIX_S) & (t <= UAV_FIRST_SPOOFED_FIX_S + 2.0)
    res["layers_firing_within_2s_of_118s"] = [nm for nm in names if (flag["spoofing"][nm] & win).any()]
    return res


# ------------------------------------------------------------------------------------------------------------------------------
def run_avgps():
    av = S.load_avgps()
    av = av.join(b2.b2_features(av)).join(l1.l1_features(av))
    sc = json.loads((L.OUT / "S3_avgps.json").read_text())["config"]
    cfg = EKFConfig(**sc)
    dr = DRConfig(r_pos=sc["r_pos"], gm_phi=sc["gm_phi"], gm_sigma=sc["gm_sigma"], sd_odo=sc["sd_odo"], learn_scale=True, freeze_h=8.0, freeze_nis_level=0.999)
    rules = l1.make_rules(l1.COVERAGE["avgps"]["evaluated"])
    layers = rules + [b2.B2Layer(), EKFLayer(cfg, "gps.ekf_nis"), CusumLayer("ekf", "axis", 1.5, cfg, name="gps.cusum_ekf"),
                      CusumLayer("dr", "nis", 2.0, cfg, dr, name="gps.cusum_dr")]
    names = sorted(l.name for l in layers)
    val_norm = av[(av["part"] == "val") & (av["label"] == 0)]
    test = av[av["part"] == "test"]
    yt = test["label"].to_numpy()
    raw_val = {l.name: np.asarray(l.raw_scores(val_norm), float) for l in layers}
    raw_test = {l.name: np.asarray(l.raw_scores(test), float) for l in layers}
    sess = test["run"].to_numpy()
    huge = (test["r_speed"].to_numpy() * l1.LIMITS["V_MAX"] > 1e5)
    res = {"layers_run": names, "not_available": {"gps.vel_pos_consistency": "no Doppler velocity in AV-GPS", "gps.lidar_*": "no LiDAR", "IMU acceleration": "absent (EKF runs without it)"},
           "test_rows": int(len(test)), "test_normal_rows": int((yt == 0).sum()), "test_attack_rows": int(yt.sum()),
           "test_sessions": {r: {"label": int(g["label"].iloc[0]), "rows": int(len(g)), "mean_numsats": float(g["numsats"].mean()), "mean_hdop": float(g["hdop"].mean())}
                             for r, g in test.groupby("run", sort=False)},
           "attack_rows_with_step_over_100km": float(huge[yt == 1].mean()),
           "calibration": "own: val sessions' normal rows, 1% budget tie-safe; kitti: raw thresholds fitted on the KITTI dev drives, unchanged",
           "ekf_config": sc, "dr_config": {"r_pos": dr.r_pos, "gm_phi": dr.gm_phi, "gm_sigma": dr.gm_sigma, "sd_odo": dr.sd_odo}, "layers": {}}
    cal, own_flag = {}, {}
    for l in layers:
        thr = budget_threshold(raw_val[l.name], BUDGET)
        own_flag[l.name] = raw_test[l.name] >= thr
        from common.calibration import ECDFCalibrator
        c = ECDFCalibrator().fit(raw_val[l.name])
        cal[l.name] = c.transform(raw_test[l.name])
        r = {"threshold_own": float(thr), "fa_own": float(own_flag[l.name][yt == 0].mean()), "detection_own": float(own_flag[l.name][yt == 1].mean()),
             "auc": auc(yt, np.minimum(raw_test[l.name], 1e300)),
             "detected_by_session": {s: float(own_flag[l.name][(sess == s)].mean()) for s in sorted(set(sess[yt == 1]))},
             "fa_by_session": {s: float(own_flag[l.name][(sess == s)].mean()) for s in sorted(set(sess[yt == 0]))}}
        res["layers"][l.name] = r
    # KITTI thresholds, parameter-free layers
    raw = W.load_raw()
    dev = raw[raw["part"].isin(W.DEV_PARTS)]
    ri = ST.RunIndex(dev)
    F = W.FoldState(dev, ri, sorted(dev["drive"].unique()), ST.DEFAULT_LAYERS, W.candidates(dev))
    for nm in names:
        if nm in F.thr and nm in ("gps.max_speed", "gps.long_accel", "gps.lat_accel", "gps.jerk", "gps.yaw_rate", "gps.dr_resid_10"):
            f = raw_test[nm] >= F.thr[nm]
            res["layers"][nm].update({"threshold_kitti": float(F.thr[nm]), "fa_kitti_threshold": float(f[yt == 0].mean()), "detection_kitti_threshold": float(f[yt == 1].mean())})
    # combined (own calibration)
    Xc = ST.stack_matrix(cal, names)
    # combined threshold from the val normal rows
    cal_val = {l.name: __import__("common.calibration", fromlist=["ECDFCalibrator"]).ECDFCalibrator().fit(raw_val[l.name]).transform(raw_val[l.name]) for l in layers}
    thr = budget_threshold(ST.noisy_or_log(ST.stack_matrix(cal_val, names)), BUDGET)
    St = ST.noisy_or_log(Xc)
    f = St >= thr
    res["combined"] = {"fa_own": float(f[yt == 0].mean()), "detection_own": float(f[yt == 1].mean()), "auc": auc(yt, St),
                       "detected_by_session": {s: float(f[sess == s].mean()) for s in sorted(set(sess[yt == 1]))},
                       "fa_by_session": {s: float(f[sess == s].mean()) for s in sorted(set(sess[yt == 0]))},
                       "detection_attack_rows_excluding_step_over_100km": float(f[(yt == 1) & ~huge].mean()),
                       "attack_rows_flagged_total": int((f & (yt == 1)).sum()), "attack_rows_flagged_with_step_over_100km": int((f & (yt == 1) & huge).sum())}
    # label permutation null for the AUC (sessions are the units: how far can chance go?): keep simple, session-block permutation of labels
    rng = np.random.default_rng(42)
    sids = sorted(set(sess))
    lab = {s: int(test.loc[sess == s, "label"].iloc[0]) for s in sids}
    nulls = []
    for _ in range(500):
        perm = rng.permutation([lab[s] for s in sids])
        yy = np.zeros(len(test), int)
        for s, v in zip(sids, perm):
            yy[sess == s] = v
        if 0 < yy.sum() < len(yy):
            nulls.append(auc(yy, St))
    res["combined"]["auc_session_label_permutation_null_q05_q95"] = [float(np.percentile(nulls, 5)), float(np.percentile(nulls, 95))]
    return res


def main():
    out = {}
    out["uav"] = run_uav()
    log("UAV combined spoofing:", {k: out["uav"]["combined"]["spoofing"][k] for k in ("pre_onset_alarms", "first_alarm_after_118s", "fraction_flagged_from_118s")})
    out["avgps"] = run_avgps()
    log("AV-GPS combined:", {k: out["avgps"]["combined"][k] for k in ("fa_own", "detection_own", "auc")})
    (L.OUT / "S8_external.json").write_text(json.dumps(out, indent=1, default=float))
    log("done")


if __name__ == "__main__":
    main()
