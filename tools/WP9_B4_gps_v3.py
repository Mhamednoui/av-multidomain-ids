"""WP9 B4 GPS: the v3 GPS layers (label-free; WP1 code, frozen) on the B4 Case I sessions of AV-GPS.
Layers with AV-GPS inputs (as WP1 S8 external): L1 kinematic rules from position, B2, EKF NIS, EKF-CUSUM, dead-reckoning CUSUM; combiner noisy_or_log. No Doppler / IMU / LiDAR in this dataset.
Calibration: the VALIDATION NORMAL rows of locks/WP9_avgps.json case_I (1% budget, tie-safe; ECDF per layer); scored on case_I test sessions (+ the 2 file-3 normal sessions).
The stream builder is a copy of gps.stream.load_avgps (frozen WP1 file) using the B4 deduplicated sessions and parts. EKF configuration = results/WP1/S3_avgps.json (WP1, not re-tuned).
Output: results/WP9/B4_gps_v3.json; scores results/WP9/scores/B4/gps_v3_test.npz. Run (test is scored here, once): python -u -W ignore tools/WP9_B4_gps_v3.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True
import numpy as np
import pandas as pd

import WP9_B4_gps_lib as L
from common.calibration import ECDFCalibrator
from common.metrics import auc, budget_threshold
from gps import b2, l1
from gps import stack as ST
from gps import stream as S
from gps.cusum import CusumLayer, DRConfig
from gps.ekf import EKFConfig, EKFLayer

BUDGET = 0.01
OUT = ROOT / "results" / "WP9"


def build_stream():
    c1 = L.LOCK["case_I"]
    part_of = {**{s: "train" for s in c1["train"]}, **{s: "val" for s in c1["val"]}, **{s: "test" for s in c1["test"] + c1["test_normal_only_extra"]}}
    files = {i: pd.read_csv(L.AV / f"AV-GPS-Dataset-{i}.csv") for i in (1, 2, 3)}
    out = []
    for sd in L.LOCK["sessions"]:
        sid = sd["session"]
        if sid not in part_of:
            continue
        seg = files[sd["file"]].iloc[sd["start"]:sd["end"]]
        lat, lon = seg["GPS Latitude"].to_numpy(float), seg["GPS Longitude"].to_numpy(float)
        x = (lon - lon[0]) * S.M_PER_DEG * np.cos(np.radians(lat[0]))
        yy = (lat - lat[0]) * S.M_PER_DEG
        n = len(seg)
        nan = np.full(n, np.nan)
        y = seg["Data Type"].to_numpy(int)
        out.append(pd.DataFrame({
            "t": np.arange(n, dtype=float), "lat": lat, "lon": lon, "x": x, "y": yy, "x_true": nan, "y_true": nan,
            "vel_n": nan, "vel_e": nan, "speed_gps": nan, "course": seg["GPS Course"].to_numpy(float),
            "odo_speed": seg["Velocity (m/s)"].to_numpy(float), "heading": seg["Heading (deg)"].to_numpy(float),
            "yaw_rate": np.radians(seg["Yaw Rate (deg/s)"].to_numpy(float)), "acc_n": nan, "acc_e": nan,
            "numsats": seg["Satellite Count"].to_numpy(float), "hdop": seg["GPS HDOP"].to_numpy(float),
            "fix_type": nan, "clock_offset": nan,
            "label": y, "attack": np.where(y == 1, "avgps_spoof", "none"),
            "onset": 0 if y[0] == 1 else -1, "onset_t": 0.0 if y[0] == 1 else np.nan, "severity": np.nan,
            "k": np.arange(n), "run": sid, "drive": f"file{sd['file']}", "part": part_of[sid]}))
    return pd.concat(out, ignore_index=True)[S.COLUMNS]


def main():
    t0 = time.time()
    av = build_stream()
    av = av[av.part.isin(["val", "test"])].reset_index(drop=True)
    av = av.join(b2.b2_features(av)).join(l1.l1_features(av))
    sc = json.loads((ROOT / "results" / "WP1" / "S3_avgps.json").read_text())["config"]
    cfg = EKFConfig(**sc)
    dr = DRConfig(r_pos=sc["r_pos"], gm_phi=sc["gm_phi"], gm_sigma=sc["gm_sigma"], sd_odo=sc["sd_odo"], learn_scale=True, freeze_h=8.0, freeze_nis_level=0.999)
    rules = l1.make_rules(l1.COVERAGE["avgps"]["evaluated"])
    layers = rules + [b2.B2Layer(), EKFLayer(cfg, "gps.ekf_nis"), CusumLayer("ekf", "axis", 1.5, cfg, name="gps.cusum_ekf"), CusumLayer("dr", "nis", 2.0, cfg, dr, name="gps.cusum_dr")]
    names = sorted(l.name for l in layers)
    val_norm = av[(av.part == "val") & (av.label == 0)]
    test = av[av.part == "test"].reset_index(drop=True)
    yt, sess = test.label.to_numpy(), test.run.to_numpy()
    print("val normal rows", len(val_norm), "test rows", len(test), flush=True)
    raw_val = {l.name: np.asarray(l.raw_scores(val_norm), float) for l in layers}
    raw_test = {l.name: np.asarray(l.raw_scores(test), float) for l in layers}
    print("raw scores done", f"{time.time()-t0:.0f}s", flush=True)
    cal_t, cal_v, res = {}, {}, {"layers": {}}
    in_case = np.isin(sess, L.LOCK["case_I"]["test"])        # F1 / AUC on the file-2 test sessions (the file-3 normals only add false alarms)
    for l in layers:
        thr = budget_threshold(raw_val[l.name], BUDGET)
        f = raw_test[l.name] >= thr
        c = ECDFCalibrator().fit(raw_val[l.name])
        cal_t[l.name], cal_v[l.name] = c.transform(raw_test[l.name]), c.transform(raw_val[l.name])
        m = L.f1_at(yt[in_case], f[in_case])
        res["layers"][l.name] = dict(m, auc=auc(yt[in_case], np.minimum(raw_test[l.name][in_case], 1e300)), thr=float(thr), fpr_file3_normals=float(f[~in_case].mean()))
    thr = budget_threshold(ST.noisy_or_log(ST.stack_matrix(cal_v, names)), BUDGET)
    St = ST.noisy_or_log(ST.stack_matrix(cal_t, names))
    f = St >= thr
    comb = dict(L.f1_at(yt[in_case], f[in_case]), auc=auc(yt[in_case], St[in_case]), thr=float(thr))
    comb["ci_session_cluster"] = L.cluster_boot(yt[in_case], St[in_case], f[in_case], sess[in_case])
    comb["fpr_file2_normals"] = float(f[(yt == 0) & in_case].mean())
    comb["fpr_file3_normals"] = float(f[(yt == 0) & ~in_case].mean())
    comb["by_session"] = {s: {"label": int(yt[sess == s][0]), "rows": int((sess == s).sum()), "alarm_rate": float(f[sess == s].mean())} for s in sorted(set(sess))}
    rng = np.random.default_rng(42)
    ids = sorted(set(sess[in_case]))
    lab = {s: int(yt[sess == s][0]) for s in ids}
    nulls = []
    msk = in_case
    for _ in range(500):
        perm = rng.permutation([lab[s] for s in ids])
        yy = np.zeros(len(test), int)
        for s, v in zip(ids, perm):
            yy[sess == s] = v
        if 0 < yy[msk].sum() < msk.sum():
            nulls.append(auc(yy[msk], St[msk]))
    comb["auc_file2"] = auc(yt[msk], St[msk])
    comb["auc_session_label_permutation_null_q05_q95"] = [float(np.percentile(nulls, 5)), float(np.percentile(nulls, 95))]
    comb["G3_separates"] = bool(comb["auc_file2"] > comb["auc_session_label_permutation_null_q05_q95"][1])
    res["combined"] = comb
    res["layers_run"] = names
    res["calibration"] = "validation normal rows of case_I (1% budget, tie-safe)"
    res["exposure"] = "case_I test sessions scored once by the v3 layers in this step (WP1 S8 had scored file 2/3 sessions of the OLD split before: re-used data, exposure n+1)"
    (OUT / "B4_gps_v3.json").write_text(json.dumps(res, indent=1))
    (OUT / "scores" / "B4").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(OUT / "scores" / "B4" / "gps_v3_test.npz", y=yt, session=sess, score=St, alarm=f)
    print("combined", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in comb.items() if isinstance(v, (float, int, bool))}, flush=True)
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
