"""WP1 S8 step 1: raw score matrix of every GPS layer (default stack, all S4 CUSUM candidates, optional layers) for ALL KITTI rows
(train + val + test, 6 attacks + clean runs), computed once and cached. No calibration, no labels used here: every column is a causal
per-run score with frozen parameters (the CUSUM grid candidates are only SCORED here; their selection is nested in WP1_S8_dev.py).
Optional columns (ablation rows only, not in the default stack): map_dist (L2e), cusum_lidar (S5 sequential variant), L3 / L4 score
columns of S7 (out-of-fold on dev rows, final models on test rows; same as S7).
Output: results/WP1/cache/s8_raw.pkl (DataFrame aligned to the stream index; meta columns + one raw column per layer / candidate).
Run from codes_v3/: python -u -W ignore tools/WP1_S8_scores.py
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
import WP1_S4_dev as D4
from gps import cusum, ekf, l1, lidar_dr
from gps import lidar_odom as LO
from gps import map_match as MM
from gps import learned

CACHE = L.OUT / "cache"
OUT_PKL = CACHE / "s8_raw.pkl"
META = ["t", "label", "attack", "onset", "severity", "k", "run", "drive", "part"]
L2D = ["lid_z_1", "lid_z_3", "lid_z_10", "lid_resid_1", "lid_resid_3", "lid_course"]
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def main():
    kx = L.kitti_stream()
    kx = kx.join(LO.stream_features(kx))
    runs = kx["run"].to_numpy()
    raw = kx[META].copy()
    rules = l1.make_rules(l1.COVERAGE["kitti"]["evaluated"])
    for r in rules:
        raw[r.name] = r.raw_scores(kx)
    raw["gps.dr_resid_10"] = L.S1.B2Layer().raw_scores(kx)
    log("rules + B2")
    eo = ekf.run_filter_all(kx, L.ekf_cfg())
    raw["gps.ekf_nis"] = ekf.nis_score(eo["nis"].to_numpy(), eo["dim"].to_numpy())
    log("EKF")
    for stat in ("nis", "axis"):
        for kp in D4.KAPPAS:
            raw[f"cusum_ekf_{stat}|k={kp}"] = cusum.score_from_ekf(eo, stat, kp, runs)
    log("EKF CUSUM grid")
    for sc, skw in D4.SCALES.items():
        for fr, fkw in D4.FREEZES.items():
            do = cusum.run_dr(kx, L.dr_cfg(**skw, **fkw), L.ekf_cfg())
            for stat in ("axis", "nis"):
                for kp in D4.KAPPAS:
                    raw[f"cusum_dr_{stat}|k={kp}|scale={sc}|freeze={fr}"] = cusum.score_from_dr(do, stat, kp, runs)
            log("DR branch", sc, fr)
    for c in L2D:
        raw["gps." + c.replace("lid_", "lidar_")] = kx[c].to_numpy(float)
    # ---- optional layers ----
    dev_json = json.loads((L.OUT / "S5_dev.json").read_text())
    seq = max((c for c in dev_json["candidates"] if c.startswith("cusum_lidar")), key=lambda c: dev_json["candidates"][c]["J"])
    stat, kp = seq.split("_")[2].split("|")[0], float(seq.split("k=")[1])
    raw["opt.cusum_lidar"] = lidar_dr.LidarCusumLayer(stat, kp, L.ekf_cfg()).raw_scores(kx)
    log("cusum_lidar", seq)
    rmap = MM.RoadMap.from_osm()
    raw["opt.map_dist"] = MM.stream_features(kx, rmap)["map_dist"].to_numpy(float)
    log("map_dist")
    # S7 learned columns: dev rows = out-of-fold scores, test rows = final models
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import WP1_S7_lib as W7
    dev0 = kx[kx["part"].isin(L.DEV_PARTS)]
    test0 = kx[kx["part"] == "test"]
    dev, test = W7.feature_frame(dev0, "dev"), W7.feature_frame(test0, "test")
    oof = np.load(W7.CACHE / "s7_oof.npz")
    assert (oof["index"] == dev.index.to_numpy()).all()
    final = pickle.load(open(W7.CACHE / "s7_final.pkl", "rb"))
    Ft = W7.c2_frame(test)
    raw["opt.l3"] = np.nan
    raw["opt.l4_c2"] = np.nan
    raw.loc[dev.index, "opt.l3"] = oof["l3"]
    raw.loc[dev.index, "opt.l4_c2"] = oof["l4_c2"]
    raw.loc[test.index, "opt.l3"] = final["l3"].score(test)
    raw.loc[test.index, "opt.l4_c2"] = final["l4"]["l4_c2"].score(Ft)
    assert not raw[["opt.l3", "opt.l4_c2"]].isna().any().any()
    raw.to_pickle(OUT_PKL)
    log("saved", OUT_PKL, raw.shape)


if __name__ == "__main__":
    main()
