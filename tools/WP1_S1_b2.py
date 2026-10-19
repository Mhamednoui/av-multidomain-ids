"""WP1 S1: build the unified GPS streams, reproduce v2 B2 from the NEW stream, check the new attacks.

B2 layer, receiver-noise / attack / evaluation code copied from tools/WP0_regression.py (not imported);
the data now comes from gps/stream.py. Steps (all test numbers come from ONE pass over the test runs):
  1. v2-only KITTI stream (same rng order) -> B2 calibrated on train+val normal rows -> compare with the
     WP0 S3 result (results/WP0/regression_b2.json) and with the v2 json.
  2. extended stream (v2 attacks + doppler_spoof + meaconing): v2 runs must be identical to step 1;
     B2 detection of the new attacks (information only; the rule is not tuned).
  3. attack physics checks on the built stream (results/WP1/S1_attack_checks.json).
  4. AV-GPS and UAV adapters: shapes, splits (results/WP1/S1_stream_summary.json, splits.json).
Run from codes_v3/: python -u -W ignore tools/WP1_S1_b2.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import SEED, results_dir
from common.evaluate import EvalSet, evaluate_domain, markdown_table, score_groups
from common.layer import Layer
from common.metrics import binary_summary
from gps import stream as S

M_PER_DEG = S.M_PER_DEG
BIG = 1e6
V2_JSON = Path(__file__).resolve().parent.parent.parent / "codes_v2" / "results" / "gps_kitti_external.json"
WP0_JSON = Path(__file__).resolve().parent.parent / "results" / "WP0" / "regression_b2.json"


def b2_features(df):
    """dr_resid_10 and still flag per run, from stream columns (v2 gps/kitti_external.py track(), same maths)."""
    out = []
    for _, g in df.groupby("run", sort=False):
        rep = g[["x", "y"]].to_numpy()
        n = len(g)
        sp, h = g["odo_speed"].to_numpy(), np.radians(g["heading"].to_numpy())
        v_mid = np.r_[0, (sp[1:] + sp[:-1]) / 2]
        u = np.c_[np.sin(h), np.cos(h)]
        u_mid = np.r_[[[0, 0]], (u[1:] + u[:-1]) / 2]
        dr = np.cumsum(v_mid[:, None] * u_mid, axis=0)
        lag = np.maximum(np.arange(n) - 10, 0)
        resid = np.hypot(*((rep - rep[lag]) - (dr - dr[lag])).T)
        lat = g["lat"]
        dlat = lat.diff() * M_PER_DEG
        dlon = g["lon"].diff() * M_PER_DEG * np.cos(np.radians(lat.fillna(0)))
        step = np.sqrt(dlat ** 2 + dlon ** 2)
        still = ((step < 0.05) & (g["odo_speed"] > 0.5)).astype(float).to_numpy()
        out.append(pd.DataFrame({"dr_resid_10": np.nan_to_num(resid), "still": still}, index=g.index))
    return pd.concat(out).loc[df.index]


class B2Layer(Layer):
    """v2 dead-reckoning rule as a v3 layer (copy of WP0 B2Layer)."""
    domain = "gps"
    name = "gps.dr_resid_10"
    kind = "physics"
    layer_id = "L2a"

    def raw_scores(self, samples):
        raw = samples["dr_resid_10"].to_numpy(dtype=float).copy()
        raw[samples["still"].to_numpy() > 0] = BIG
        return raw

    def reasons(self, samples, raw, alarm):
        return ["GPS and vehicle motion disagree (dead-reckoning residual or frozen position)"] * len(raw)


def raw_equiv_threshold(layer):
    s = layer.calibrator.sorted_
    cal = np.searchsorted(s, s, side="left") / len(s)
    return float(s[np.flatnonzero(cal < layer.threshold).max()])


def v2_evaluate(df, flag, attacks):
    te = (df["part"] == "test").to_numpy()
    y = df["label"].to_numpy()
    out = {"all_test_rows": binary_summary(y[te], flag[te].astype(int))}
    clean = te & (df["attack"] == "none").to_numpy()
    out["false_alarm_rate_clean_runs"] = float(flag[clean].mean())
    out["detection_by_attack"], out["run_level"] = {}, {}
    for a in attacks:
        ma = te & (df["attack"] == a).to_numpy()
        out["detection_by_attack"][a] = float(flag[ma & (y == 1)].mean())
        runs = df[ma].assign(flag=flag[ma])
        det, delays = 0, []
        for _, g in runs.groupby("run"):
            hit = np.flatnonzero(g[g["label"] == 1]["flag"].to_numpy())
            if len(hit):
                det += 1
                delays.append(int(hit[0]))
        nr = runs["run"].nunique()
        out["run_level"][a] = {"runs": int(nr), "detected": float(det / nr),
                               "median_delay_s": float(np.median(delays)) if delays else None}
    return out


def score_test(layer, df):
    te = df[df["part"] == "test"]
    ev = score_groups(layer, {r: g for r, g in te.groupby("run", sort=False)})
    order = np.concatenate([g.index.to_numpy() for _, g in te.groupby("run", sort=False)])
    flag = np.zeros(len(df), bool)
    flag[order] = [e.alarm for e in ev]
    return flag


def evalset(layer, d):
    by_run = {r: g for r, g in d.groupby("run", sort=False)}
    ev = score_groups(layer, by_run)
    return EvalSet({layer.name: ev}, d["label"].to_numpy(), np.where(d["label"] == 1, d["attack"], "normal"),
                   d["run"].to_numpy(), d["k"].to_numpy(dtype=float)), ev


def attack_checks(df):
    """Physics checks of the built stream (test + all parts). Central difference of the reported track vs the
    reported velocity; speed changes of the meaconing runs."""
    rows = []
    for run, g in df.groupby("run", sort=False):
        x, y = g["x"].to_numpy(), g["y"].to_numpy()
        n = len(g)
        if n < 4:
            continue
        cd = np.c_[(x[2:] - x[:-2]) / 2, (y[2:] - y[:-2]) / 2]                   # east, north
        v = g[["vel_e", "vel_n"]].to_numpy()[1:-1]
        err = np.hypot(*(v - cd).T)
        sp = g["speed_gps"].to_numpy()
        dsp = np.abs(np.diff(sp))
        k = g["k"].to_numpy()[1:-1]
        lab = g["label"].to_numpy()[1:-1]
        rows.append(pd.DataFrame({"run": run, "attack": g["attack"].iloc[0], "part": g["part"].iloc[0],
                                  "err": err, "lab": lab, "dsp": dsp[:-1] if len(dsp) > 1 else np.nan,
                                  "dsp_lab": g["label"].to_numpy()[1:-1]}))
    r = pd.concat(rows)
    res = {}
    clean = r[(r["attack"] == "none")]
    res["median_vel_vs_track_clean_rows"] = float(clean["err"].median())
    for a in sorted(r["attack"].unique()):
        if a == "none":
            continue
        m = r[(r["attack"] == a) & (r["lab"] == 1)]
        res[f"median_vel_vs_track_{a}_attacked_rows"] = float(m["err"].median())
        res[f"ratio_to_clean_{a}"] = float(m["err"].median() / clean["err"].median())
    te = r[r["part"] == "test"]
    res["clean_test_dspeed_p999"] = float(te[te["attack"] == "none"]["dsp"].quantile(0.999))
    mm = r[(r["attack"] == "meaconing") & (r["lab"] == 1)]
    res["meaconing_max_dspeed_attacked_rows"] = float(mm["dsp"].max())
    return res


def main():
    out = results_dir("WP1")
    # ---- 1. v2-only stream, B2 ---------------------------------------------------------------
    rng = np.random.default_rng(SEED)
    kv2 = S.build_kitti(rng)
    rows, runs = kv2.groupby("part").size().to_dict(), kv2.groupby("part")["run"].nunique().to_dict()
    print("v2-only rows", rows, "runs", runs, flush=True)
    kv2 = kv2.join(b2_features(kv2))
    y = kv2["label"].to_numpy()
    fit = (kv2["part"] != "test") & (y == 0)
    layer = B2Layer().calibrate(kv2[fit], budget=0.01)
    flag = score_test(layer, kv2)
    res = {"rows": rows, "runs": runs, "calibration_rows": int(fit.sum()),
           "threshold_m_raw_equivalent": raw_equiv_threshold(layer)}
    res["b2_v2_only_stream"] = v2_evaluate(kv2, flag, S.ATTACKS_V2)

    wp0 = json.loads(WP0_JSON.read_text())
    v2 = json.loads(V2_JSON.read_text())["B2_dead_reckoning_rule"]
    cmp, ok = {}, True

    def chk(key, a, b, tol=1e-4):
        nonlocal ok
        good = abs(a - b) <= tol
        ok &= good
        cmp[key] = {"wp0_s3": b, "new_stream": a, "abs_diff": abs(a - b), "match": bool(good)}

    nv, w3 = res["b2_v2_only_stream"], wp0["v3"]
    chk("false_alarm_rate_clean_runs", nv["false_alarm_rate_clean_runs"], w3["false_alarm_rate_clean_runs"])
    chk("threshold_m_raw_equivalent", res["threshold_m_raw_equivalent"], wp0["v3_threshold_m_raw_equivalent"], 1e-9)
    for a in S.ATTACKS_V2:
        chk(f"row_detection_{a}", nv["detection_by_attack"][a], w3["detection_by_attack"][a])
        chk(f"run_detected_{a}", nv["run_level"][a]["detected"], w3["run_level"][a]["detected"])
        chk(f"run_median_delay_{a}", nv["run_level"][a]["median_delay_s"], w3["run_level"][a]["median_delay_s"], 0)
    for k in ("tp", "fp", "fn", "tn"):
        chk(f"all_test_rows_{k}", nv["all_test_rows"][k], w3["all_test_rows"][k], 0)
    for part in ("test", "train", "val"):
        chk(f"rows_{part}", rows[part], wp0["rows"][part], 0)
        chk(f"runs_{part}", runs[part], wp0["runs"][part], 0)
    res["comparison_with_wp0_s3"] = cmp
    res["matches_wp0_s3"] = bool(ok)
    # and vs the v2 json (same numbers WP0 already matched to)
    ok2 = abs(nv["false_alarm_rate_clean_runs"] - v2["false_alarm_rate_clean_runs"]) < 1e-4
    for a in S.ATTACKS_V2:
        ok2 &= abs(nv["detection_by_attack"][a] - v2["detection_by_attack"][a]) < 1e-4
        ok2 &= abs(nv["run_level"][a]["detected"] - v2["run_level"][a]["detected"]) < 1e-4
    ok2 &= all(nv["all_test_rows"][k] == v2["all_test_rows"][k] for k in ("tp", "fp", "fn", "tn"))
    res["matches_v2_json"] = bool(ok2)
    res["threshold_diff_vs_v2_interpolated_m"] = abs(res["threshold_m_raw_equivalent"] - v2["threshold_m"])

    # ---- 2. extended stream --------------------------------------------------------------------
    rng = np.random.default_rng(SEED)
    kx = S.build_kitti(rng, new_attacks=S.ATTACKS_NEW)
    kx = kx.join(b2_features(kx))
    old = kx[kx["attack"].isin(["none"] + S.ATTACKS_V2)].reset_index(drop=True)
    same = bool(old.shape == kv2.shape and (old.drop(columns=[]).equals(kv2.reset_index(drop=True))))
    res["extended_keeps_v2_runs_identical"] = same
    print("extended keeps v2 runs identical:", same, flush=True)
    flagx = score_test(layer, kx)
    res["b2_extended_stream"] = v2_evaluate(kx, flagx, S.ATTACKS_V2 + S.ATTACKS_NEW)
    res["extended_rows"] = kx.groupby("part").size().to_dict()
    res["extended_runs_by_attack"] = kx[kx["part"] == "test"].groupby("attack")["run"].nunique().to_dict()
    # harness table (one layer; calibrated on VAL drives only = v3 protocol), info
    val_rows = (kx["part"] == "val") & (kx["label"] == 0)
    lay2 = B2Layer().calibrate(kx[val_rows], budget=0.01)
    vs, _ = evalset(lay2, kx[kx["part"] == "val"])
    ts, ev2 = evalset(lay2, kx[kx["part"] == "test"])
    h2 = evaluate_domain("S1_b2_extended_val_only", vs, ts, wp="WP1", method="max")
    res["b2_extended_val_only"] = {"threshold_m_raw_equivalent": raw_equiv_threshold(lay2),
                                   "auc": h2["layers"][lay2.name]["auc"],
                                   "detection_by_attack": h2["layers"][lay2.name]["detection_by_attack"],
                                   "false_alarm_rate_test_normal": h2["layers"][lay2.name]["false_alarm_rate"]}
    (out / "S1_b2_extended_table.md").write_text(markdown_table(h2))

    # ---- 3. attack physics on the stream -------------------------------------------------------
    chk3 = attack_checks(kx)
    chk3["severity_ranges"] = S.SEV
    chk3["doppler_accel_m_s2"], chk3["tau_rate_s_per_s"] = S.DOPPLER_ACCEL, S.TAU_RATE
    (out / "S1_attack_checks.json").write_text(json.dumps(chk3, indent=1, default=float))
    print(json.dumps(chk3, indent=1, default=float), flush=True)

    # ---- 4. other adapters + splits ------------------------------------------------------------
    av, uav = S.load_avgps(), S.load_uav()
    summ = {"avgps": {"rows": len(av), "sessions": int(av["run"].nunique()),
                      "by_part": av.groupby("part")["run"].nunique().to_dict(),
                      "label_rate": float(av["label"].mean())},
            "uav": {f: {"fixes": int((uav["run"] == f"uav/{f}").sum()),
                        "label_1": int(uav.loc[uav["run"] == f"uav/{f}", "label"].sum()),
                        "duration_s": float(uav.loc[uav["run"] == f"uav/{f}", "t"].max())} for f in S.UAV_FLIGHTS},
            "kitti_columns": list(kx.columns)}
    (out / "S1_stream_summary.json").write_text(json.dumps(summ, indent=1, default=float))
    S.write_splits(kx, av, uav, out / "splits.json")
    (out / "S1_b2_reproduction.json").write_text(json.dumps(res, indent=1, default=float))
    for k, v in cmp.items():
        print(f"{k:34s} wp0 {v['wp0_s3']:.6f}  new {v['new_stream']:.6f}  {'OK' if v['match'] else 'DIFF'}")
    print("MATCHES WP0 S3:", ok, " MATCHES v2 json:", ok2, " extended identical:", same)
    print(json.dumps(res["b2_extended_stream"]["detection_by_attack"], indent=1))
    print(json.dumps(res["b2_extended_stream"]["run_level"], indent=1))
    print(json.dumps(summ, indent=1, default=float))


if __name__ == "__main__":
    main()
