"""WP1 S3 step 1: set the EKF noise parameters on TRAIN data and choose the gate on VALIDATION. Test is not touched.

KITTI: Gauss-Markov (phi, sigma) of the receiver error estimated from TRAIN clean runs (reported - true position);
q_acc (white acceleration error) by grid on TRAIN clean runs so that mean NIS / mean dim is closest to 1.
Consistency is then CHECKED (not tuned) on VAL clean runs. Gate level: grid on VAL attacked runs (rule A6/A5 in notes).
AV-GPS: q_acc and r_pos by grid on TRAIN sessions (normal rows). UAV: q_acc, gm sigma, r_pos on the benign flight.
Outputs: results/WP1/S3_tuning.json. Run from codes_v3/: python -u -W ignore tools/WP1_S3_tune.py
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
from common.config import SEED, results_dir
from common.metrics import budget_threshold
from gps import ekf
from gps import stream as S
from gps.ekf import EKFConfig

ATT = S.ATTACKS_V2 + S.ATTACKS_NEW


def nis_stats(df, cfg):
    r = ekf.run_filter_all(df, cfg)
    ok = ~np.isnan(r["nis"].to_numpy())
    nis, dim = r["nis"].to_numpy()[ok], r["dim"].to_numpy()[ok]
    return {"rows": int(ok.sum()), "mean_nis": float(nis.mean()), "mean_dim": float(dim.mean()),
            "ratio": float(nis.mean() / dim.mean()), "frac_above_chi2_95": float((nis > chi2.ppf(0.95, dim)).mean()),
            "frac_above_chi2_99": float((nis > chi2.ppf(0.99, dim)).mean())}


def estimate_gm(train_clean):
    num = den = 0.0
    sig = []
    for _, g in train_clean.groupby("run", sort=False):
        e = np.c_[g["x"] - g["x_true"], g["y"] - g["y_true"]]
        sig.append((e ** 2).mean())
        num += (e[1:] * e[:-1]).sum(); den += (e[:-1] ** 2).sum()
    return float(num / den), float(np.sqrt(np.mean(sig)))


def det_run_level(df, cfg, thr_raw):
    """mean over the 6 attacks of the fraction of runs with an alarm at/after onset (raw >= thr_raw)."""
    r = ekf.run_filter_all(df, cfg)
    raw = ekf.nis_score(r["nis"].to_numpy(), r["dim"].to_numpy())
    d = df.assign(f=raw >= thr_raw)
    out = {}
    for a in ATT:
        runs = d[d["attack"] == a]
        out[a] = float(np.mean([g.loc[g["label"] == 1, "f"].any() for _, g in runs.groupby("run")]))
    return out


def main():
    out = results_dir("WP1")
    res = {}
    kx = S.build_kitti(np.random.default_rng(SEED), new_attacks=S.ATTACKS_NEW)
    tr_clean = kx[(kx["part"] == "train") & (kx["attack"] == "none")]
    va_clean = kx[(kx["part"] == "val") & (kx["attack"] == "none")]
    phi, sig = estimate_gm(tr_clean)
    print("GM estimate on train clean (reported - true):", phi, sig, flush=True)
    res["kitti_gm_estimate_train"] = {"phi": phi, "sigma": sig}
    base = EKFConfig(gm_phi=phi, gm_sigma=sig)
    grid = {}
    for q in (0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2):
        grid[q] = nis_stats(tr_clean, EKFConfig(gm_phi=phi, gm_sigma=sig, q_acc=q))
        print("q_acc", q, grid[q], flush=True)
    res["kitti_q_grid_train_clean"] = {str(k): v for k, v in grid.items()}
    q_best = min(grid, key=lambda q: abs(np.log(grid[q]["ratio"])))
    cfg = EKFConfig(gm_phi=phi, gm_sigma=sig, q_acc=q_best)
    res["kitti_q_acc"] = q_best
    res["kitti_consistency_train_clean"] = grid[q_best]
    res["kitti_consistency_val_clean"] = nis_stats(va_clean, cfg)
    print("VAL clean consistency", res["kitti_consistency_val_clean"], flush=True)
    # ---- gate level on VAL (calibration of the raw threshold on val normal rows, 1% budget) ----
    val = kx[kx["part"] == "val"]
    val_norm = val[val["label"] == 0]
    gate = {}
    for lv in (0.0, 0.99, 0.999, 0.9999):
        c = cfg.gated(lv) if lv > 0 else cfg
        r = ekf.run_filter_all(val_norm, c)
        raw = ekf.nis_score(r["nis"].to_numpy(), r["dim"].to_numpy())
        thr = budget_threshold(raw, 0.01)
        d = det_run_level(val, c, thr)
        gate[str(lv)] = {"threshold_raw": float(thr), "run_detected_val": d, "mean_over_attacks": float(np.mean(list(d.values())))}
        print("gate", lv, gate[str(lv)]["mean_over_attacks"], d, flush=True)
    res["kitti_gate_val"] = gate
    best_g = max((k for k in gate if k != "0.0"), key=lambda k: gate[k]["mean_over_attacks"])
    res["kitti_gate_level"] = float(best_g)
    res["kitti_primary_variant"] = "gated" if gate[best_g]["mean_over_attacks"] > gate["0.0"]["mean_over_attacks"] else "ungated"
    res["kitti_primary_gate_level"] = float(best_g)
    # ---- AV-GPS (position, speed, heading only) ----
    av = S.load_avgps()
    av_tr = av[(av["part"] == "train") & (av["label"] == 0)]
    ag = {}
    for q in (0.3, 0.6, 1.0, 2.0, 4.0):
        for rp in (1.0, 3.0, 6.0):
            c = EKFConfig(use_dop=False, acc_mode="none", gm_sigma=1e-3, gm_phi=0.0, r_pos=rp, q_acc=q, sd_odo=0.2)
            ag[f"q{q}_r{rp}"] = nis_stats(av_tr, c)
    res["avgps_grid_train"] = ag
    k_best = min(ag, key=lambda k: abs(ag[k]["frac_above_chi2_95"] - 0.05))   # robust: AV-GPS has heavy-tailed glitches, the mean NIS is dominated by them
    print("AV-GPS best", k_best, ag[k_best], flush=True)
    res["avgps_best"] = k_best
    qa, ra = float(k_best.split("_r")[0][1:]), float(k_best.split("_r")[1])
    res["avgps_cfg"] = {"q_acc": qa, "r_pos": ra, "sd_odo": 0.2}
    c = EKFConfig(use_dop=False, acc_mode="none", gm_sigma=1e-3, gm_phi=0.0, r_pos=ra, q_acc=qa, sd_odo=0.2)
    av_va = av[(av["part"] == "val") & (av["label"] == 0)]
    res["avgps_consistency_train"] = nis_stats(av_tr, c)
    res["avgps_consistency_val"] = nis_stats(av_va, c)
    # ---- UAV: benign flight (calibration flight) ----
    from gps import l1
    uav = S.load_uav()
    ub = uav[uav["run"] == "uav/benign"]
    ug = {}
    for q in (0.1, 0.2, 0.4, 0.8, 1.5):
        for gs in (1.0, 2.0, 4.0):
            c = EKFConfig(use_odo=False, use_head=False, acc_mode="window", gm_phi=0.9, gm_sigma=gs, r_pos=0.5,
                          sd_dop=0.15, q_acc=q)
            ug[f"q{q}_g{gs}"] = nis_stats(ub, c)
    k_best = min(ug, key=lambda k: abs(np.log(ug[k]["ratio"])))
    print("UAV best", k_best, ug[k_best], flush=True)
    qu, gu = float(k_best[1:].split("_g")[0]), float(k_best.split("_g")[1])
    res["uav_grid_benign"] = ug
    res["uav_cfg"] = {"q_acc": qu, "gm_sigma": gu, "gm_phi": 0.9, "r_pos": 0.5, "sd_dop": 0.15, "acc_mode": "window"}
    res["uav_consistency_benign"] = ug[k_best]
    (out / "S3_tuning.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
