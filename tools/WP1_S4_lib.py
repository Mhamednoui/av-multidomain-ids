"""WP1 S4 shared helpers: KITTI stream (cached), frozen configs, run-level metrics, delay distributions.
Used by tools/WP1_S4_dev.py (train+val drives only), tools/WP1_S4_test.py (one test pass), tools/WP1_S4_tables.py.
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import WP1_S1_b2 as S1
from common.config import SEED, results_dir
from gps import cusum, ekf, l1
from gps import stream as S
from gps.cusum import DRConfig
from gps.ekf import EKFConfig

ATT = S.ATTACKS_V2 + S.ATTACKS_NEW
OUT = results_dir("WP1")
TUNE = json.loads((OUT / "S3_tuning.json").read_text())
CACHE = Path(tempfile.gettempdir()) / "wp1_s4_kitti.pkl"
DEV_PARTS = ("train", "val")
MIN_PATH_M = 50.0                     # runs with less odometry path are not used for scale diagnostics


def kitti_stream():
    """Full KITTI stream with the 6 attacks (same call as S3), + B2 and L1 features. Cached as a pickle in the temp folder."""
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    kx = S.build_kitti(np.random.default_rng(SEED), new_attacks=S.ATTACKS_NEW)
    kx = kx.join(S1.b2_features(kx)).join(l1.l1_features(kx))
    kx.to_pickle(CACHE)
    return kx


def ekf_cfg():
    return EKFConfig(gm_phi=TUNE["kitti_gm_estimate_train"]["phi"], gm_sigma=TUNE["kitti_gm_estimate_train"]["sigma"], q_acc=TUNE["kitti_q_acc"])


def dr_cfg(**kw):
    g = TUNE["kitti_gm_estimate_train"]
    return DRConfig(gm_phi=g["phi"], gm_sigma=g["sigma"], **kw)


def within_30s_slow_drift(df, flag):
    d = df.assign(f=flag)
    d = d[(d["attack"] == "drift") & (d["severity"] < 0.5)]
    res = {"runs": 0, "detected": 0, "runs_with_full_30s": 0}
    for _, g in d.groupby("run", sort=False):
        k0 = int(g["onset"].iloc[0])
        w = g[(g["k"] >= k0) & (g["k"] < k0 + 30)]
        res["runs"] += 1
        res["detected"] += int(w["f"].any())
        res["runs_with_full_30s"] += int(len(w) >= 30)
    res["rate"] = res["detected"] / res["runs"] if res["runs"] else None
    return res


def delays(df, flag, attacks=ATT):
    """Per attack: detection delay (fixes after onset of the first flagged row) of every detected run -> quantiles."""
    out = {}
    d = df.assign(f=flag)
    for a in attacks:
        dl, nr = [], 0
        for _, g in d[d["attack"] == a].groupby("run", sort=False):
            nr += 1
            hit = np.flatnonzero(g[g["label"] == 1]["f"].to_numpy())
            if len(hit):
                dl.append(int(hit[0]))
        q = np.percentile(dl, [10, 25, 50, 75, 90]).tolist() if dl else None
        out[a] = {"runs": nr, "detected": len(dl), "delays_q10_25_50_75_90_s": q,
                  "within_10s": float(np.mean([x <= 10 for x in dl]) * len(dl) / nr) if nr else None,
                  "within_30s": float(np.mean([x <= 30 for x in dl]) * len(dl) / nr) if nr else None}
    return out


def summarize(df, flag):
    """Run/row-level detection, clean-run FA, slow drift, delays. df rows must be in run order (as the flags)."""
    y = df["label"].to_numpy()
    clean = (df["attack"] == "none").to_numpy()
    out = {"false_alarm_clean_runs": float(flag[clean].mean()), "false_alarm_all_normal_rows": float(flag[y == 0].mean()),
           "run_detected": {}, "row_detection": {}}
    for a in ATT:
        m = (df["attack"] == a).to_numpy()
        runs = df[m].assign(f=flag[m])
        out["row_detection"][a] = float(flag[m & (y == 1)].mean())
        det = [g.loc[g["label"] == 1, "f"].any() for _, g in runs.groupby("run", sort=False)]
        out["run_detected"][a] = float(np.mean(det))
    out["slow_drift_lt_0.5_within_30s"] = within_30s_slow_drift(df, flag)
    out["delays"] = delays(df, flag)
    return out


def j_criterion(sm):
    v = [sm["run_detected"][a] for a in ATT] + [sm["slow_drift_lt_0.5_within_30s"]["rate"] or 0.0]
    return float(np.mean(v))


def scale_diag(df, out):
    """L2c diagnostics. df: stream rows of whole runs, out: run_dr output aligned to df. Relative error of the scale state against
    s* = true path / odometry path of the run. Clean runs: median at k = 10, 30, 60 s from the start; attack runs: at onset and onset + 30 s."""
    res = {"clean": {}, "attacks": {}}
    d = df.assign(scale=out["scale"].to_numpy(), frozen=out["frozen"].to_numpy())
    errs = {k: [] for k in (10, 20, 30, 60)}
    prior = []
    for _, g in d[d["attack"] == "none"].groupby("run", sort=False):
        if g["odo_speed"].sum() < MIN_PATH_M:
            continue                                   # (nearly) stationary run: s* is not defined
        s_star = cusum.true_scale(g)
        prior.append(abs(1.0 - s_star) / s_star)
        for k in errs:
            if len(g) > k:
                errs[k].append(abs(g["scale"].iloc[k] - s_star) / s_star)
    res["clean"] = {"prior_error_median": float(np.median(prior)), "prior_error_rms": float(np.sqrt(np.mean(np.square(prior)))),
                    **{f"median_rel_error_at_{k}s": (float(np.median(v)) if v else None) for k, v in errs.items()},
                    **{f"runs_at_{k}s": len(v) for k, v in errs.items()}}
    for a in ATT:
        e30, e0, fr = [], [], []
        for _, g in d[d["attack"] == a].groupby("run", sort=False):
            if g["odo_speed"].sum() < MIN_PATH_M:
                continue
            s_star = cusum.true_scale(g)
            k0 = int(g["onset"].iloc[0])
            if k0 + 30 < len(g):
                e30.append(abs(g["scale"].iloc[k0 + 30] - s_star) / s_star)
                e0.append(abs(g["scale"].iloc[k0] - s_star) / s_star)
                fr.append(float(g["frozen"].iloc[k0:k0 + 30].mean()))
        res["attacks"][a] = {"runs": len(e30), "median_rel_error_at_onset": float(np.median(e0)) if e0 else None,
                             "median_rel_error_at_onset_plus_30s": float(np.median(e30)) if e30 else None,
                             "mean_frozen_fraction_first_30s": float(np.mean(fr)) if fr else None}
    return res


def absorption(df, out):
    """Median ratio (position-estimate error) / (reported-position error) at onset + 30 s, runs with reported error >= 5 m."""
    d = df.assign(ex=out["est_x"].to_numpy(), ey=out["est_y"].to_numpy())
    res = {}
    for a in ATT:
        ee, er = [], []
        for _, g in d[d["attack"] == a].groupby("run", sort=False):
            k = int(g["onset"].iloc[0]) + 30
            if k < len(g):
                ee.append(np.hypot(g["ex"].iloc[k] - g["x_true"].iloc[k], g["ey"].iloc[k] - g["y_true"].iloc[k]))
                er.append(np.hypot(g["x"].iloc[k] - g["x_true"].iloc[k], g["y"].iloc[k] - g["y_true"].iloc[k]))
        ee, er = np.array(ee), np.array(er)
        big = er >= 5.0
        res[a] = {"runs": int(len(ee)), "runs_reported_error_ge_5m": int(big.sum()),
                  "median_estimate_error_m": float(np.median(ee)) if len(ee) else None,
                  "median_absorbed_fraction": float(np.median(ee[big] / er[big])) if big.any() else None}
    return res
