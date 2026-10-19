"""WP0 S3: reproduce the v2 GPS dead-reckoning rule (B2) through the v3 Layer + harness.

Copied from ../codes_v2/gps/kitti_external.py (data loading, receiver noise, attack injection,
dead-reckoning residual, v2 evaluate) and ../codes_v2/gps/features.py (session_features), and
../codes_v2/lidar/train.py (SCENE, split). Nothing is imported from codes_v2.

Data: 23 KITTI raw drives (OXTS) -> 1 Hz tracks, 10 phases, receiver noise AR(1), 4 synthetic attacks
(drift, accel_drift, jump, freeze). Same rng order as v2: one default_rng(42) consumed in sorted(SCENE) order.
Layer: B2Layer, raw score = dr_resid_10 (still_gps_moving_imu rows get a huge score, so the OR rule is one
score); calibrated by Layer.calibrate (ECDF + tie-safe budget_threshold) on train+val normal rows (the
rows v2 used for its threshold). Test rows are scored once, run by run (score_groups).
Outputs: results/WP0/regression_b2.json (+ .md ablation table of the harness, v3-protocol variant
calibrated on val drives only).
Run from codes_v3/: python -u -W ignore tools/WP0_regression.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import DATA, DATA_EXTRA, SEED, results_dir
from common.evaluate import EvalSet, evaluate_domain, markdown_table, score_groups
from common.layer import Layer
from common.metrics import binary_summary, budget_threshold

M_PER_DEG = 111_320.0
SENSOR = ["Roll (deg)", "Pitch (deg)", "Heading (deg)", "Yaw (deg)", "Yaw Rate (deg/s)",
          "Velocity (m/s)", "Steering Angle (deg)", "Relative Altitude (m)", "Throttle (%)",
          "GPS HDOP", "GPS VDOP", "GPS Course", "Satellite Locks", "Satellite Count",
          "Longitudinal Velocity (m/s)", "Absolute Longitudinal Velocity (m/s)",
          "Lateral Velocity (m/s)", "Absolute Lateral Velocity (m/s)", "Vertical Velocity (m/s)",
          "Longitudinal Vibration", "Lateral Vibration", "Vertical Vibration"]
SCENE = {"0001": "city", "0002": "city", "0005": "city", "0011": "city", "0013": "city", "0017": "city",
         "0048": "city", "0060": "city", "0095": "city", "0106": "city", "0113": "city",
         "0019": "residential", "0020": "residential", "0035": "residential", "0039": "residential",
         "0046": "residential", "0079": "residential",
         "0015": "road", "0027": "road", "0028": "road", "0029": "road", "0052": "road", "0070": "road"}
TEST = ["0001", "0005", "0095", "0039", "0079", "0028", "0052"]
VAL = ["0011", "0035", "0027"]
ATTACKS = ["drift", "accel_drift", "jump", "freeze"]
PHASES = 10
BIG = 1e6          # raw score of a still_gps_moving_imu row (rule fires on its own)
V2_JSON = Path(__file__).resolve().parent.parent.parent / "codes_v2" / "results" / "gps_kitti_external.json"


def part_of(d):
    return "test" if d in TEST else "val" if d in VAL else "train"


def oxts_dir(d):
    name = f"2011_09_26_drive_{d}_sync"
    root = DATA / "Depth" if d in ("0001", "0015") else DATA_EXTRA / "kitti_raw"
    return root / name / "2011_09_26" / name / "oxts" / "data"


def load_oxts(d):
    a = np.array([np.loadtxt(f) for f in sorted(oxts_dir(d).glob("*.txt"))])
    ts = pd.to_datetime(pd.read_csv(oxts_dir(d).parent / "timestamps.txt", header=None)[0])
    t = (ts - ts.iloc[0]).dt.total_seconds().to_numpy()
    return {"t": t, "lat": a[:, 0], "lon": a[:, 1], "yaw": a[:, 5], "vf": a[:, 8], "numsats": a[:, 26]}


def resample_1hz(ox, offset):
    tg = np.arange(offset, ox["t"][-1] + 1e-9, 1.0)
    g = {"t": tg, "yaw": np.interp(tg, ox["t"], np.unwrap(ox["yaw"]))}
    for k in ("lat", "lon", "vf"):
        g[k] = np.interp(tg, ox["t"], ox[k])
    g["numsats"] = ox["numsats"][np.searchsorted(ox["t"], tg).clip(0, len(ox["t"]) - 1)]
    return g


def receiver_noise(n, rng, phi=0.9, sigma=1.0):
    e = np.zeros((n, 2))
    e[0] = rng.normal(0, sigma, 2)
    for k in range(1, n):
        e[k] = phi * e[k - 1] + np.sqrt(1 - phi ** 2) * sigma * rng.normal(0, 1, 2)
    return e


def attack_offset(name, east, north, k0, rng):
    n = len(east)
    t = np.clip(np.arange(n) - k0, 0, None).astype(float)
    th = rng.uniform(0, 2 * np.pi)
    u = np.array([np.cos(th), np.sin(th)])
    if name == "drift":
        sev = rng.uniform(0.2, 2.0)
        return np.outer(sev * t, u), sev
    if name == "accel_drift":
        sev = rng.uniform(0.05, 0.5)
        return np.outer(0.5 * sev * t ** 2, u), sev
    if name == "jump":
        sev = rng.uniform(5, 50)
        return np.outer((t > 0) | (np.arange(n) == k0), u) * sev, sev
    off = np.zeros((n, 2))
    off[k0:, 0] = east[k0] - east[k0:]
    off[k0:, 1] = north[k0] - north[k0:]
    return off, 0.0


def still_flag(seg):
    """still_gps_moving_imu of v2 gps/features.session_features (the only feature of it B2 needs)."""
    lat = seg["GPS Latitude"].astype(float)
    lon = seg["GPS Longitude"].astype(float)
    dlat = lat.diff() * M_PER_DEG
    dlon = lon.diff() * M_PER_DEG * np.cos(np.radians(lat.fillna(0)))
    step = np.sqrt(dlat ** 2 + dlon ** 2)
    return ((step < 0.05) & (seg["Velocity (m/s)"].astype(float) > 0.5)).astype(float)


def track(ox, idx, rng, attack=None):
    """One 1 Hz track -> DataFrame (dr_resid_10, still, label, ...). Same rng draws as v2 track()."""
    lat0, lon0 = ox["lat"][idx[0]], ox["lon"][idx[0]]
    north = (ox["lat"][idx] - lat0) * M_PER_DEG
    east = (ox["lon"][idx] - lon0) * M_PER_DEG * np.cos(np.radians(lat0))
    n = len(idx)
    rep = np.c_[east, north] + receiver_noise(n, rng)
    label, sev, k0 = np.zeros(n, int), np.nan, -1
    if attack:
        k0 = int(rng.integers(3, max(4, n - 2)))
        off, sev = attack_offset(attack, rep[:, 0], rep[:, 1], k0, rng)
        rep = rep + off
        label[k0:] = 1
    lat = lat0 + rep[:, 1] / M_PER_DEG
    lon = lon0 + rep[:, 0] / (M_PER_DEG * np.cos(np.radians(lat0)))
    heading = (90 - np.degrees(ox["yaw"][idx])) % 360 + rng.normal(0, 2, n)
    step = np.r_[0, np.hypot(np.diff(rep[:, 0]), np.diff(rep[:, 1]))]
    course = np.degrees(np.arctan2(np.r_[0, np.diff(rep[:, 0])], np.r_[0, np.diff(rep[:, 1])])) % 360
    course[0] = heading[0]
    for k in range(1, n):
        if step[k] < 0.3:
            course[k] = course[k - 1]
    speed = np.clip(ox["vf"][idx] * (1 + rng.normal(0, 0.02)) + rng.normal(0, 0.05, n), 0, None)
    df = pd.DataFrame(0.0, index=range(n), columns=SENSOR)
    df["GPS Latitude"], df["GPS Longitude"] = lat, lon
    df["Velocity (m/s)"], df["Heading (deg)"], df["GPS Course"] = speed, heading, course % 360
    df["Satellite Count"], df["GPS HDOP"] = ox["numsats"][idx], 1.0
    f = pd.DataFrame({"still": still_flag(df).to_numpy()})
    h = np.radians(heading)
    v_mid = np.r_[0, (speed[1:] + speed[:-1]) / 2]
    u = np.c_[np.sin(h), np.cos(h)]
    u_mid = np.r_[[[0, 0]], (u[1:] + u[:-1]) / 2]
    dr = np.cumsum(v_mid[:, None] * u_mid, axis=0)
    lag = np.maximum(np.arange(n) - 10, 0)
    f["dr_resid_10"] = np.hypot(*((rep - rep[lag]) - (dr - dr[lag])).T)
    f["label"], f["k"], f["onset"], f["severity"] = label, np.arange(n), k0, sev
    return f


def build(rng):
    parts = []
    for d in sorted(SCENE):
        ox = load_oxts(d)
        part = part_of(d)
        reps = 2 if part == "train" else 1
        for ph in range(PHASES):
            g = resample_1hz(ox, ph / PHASES)
            idx = np.arange(len(g["t"]))
            if len(idx) < 6:
                continue
            runs = [None] + [a for a in ATTACKS for _ in range(reps)]
            for r, a in enumerate(runs):
                f = track(g, idx, rng, a)
                f["drive"], f["part"], f["attack"] = d, part, a or "none"
                f["run"] = f"{d}/p{ph}/r{r}"
                parts.append(f)
    df = pd.concat(parts, ignore_index=True)
    df["dr_resid_10"] = df["dr_resid_10"].fillna(0)
    return df


class B2Layer(Layer):
    """Dead-reckoning physics rule: GNSS displacement over 10 s vs odometry speed x IMU heading.
    Alarm = residual above the calibrated threshold, or GPS still while the vehicle moves."""
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


def v2_evaluate(df, flag):
    """Copy of v2 evaluate() metrics (no printing, no severity buckets)."""
    te = (df["part"] == "test").to_numpy()
    y = df["label"].to_numpy()
    out = {"all_test_rows": binary_summary(y[te], flag[te].astype(int))}
    clean = te & (df["attack"] == "none").to_numpy()
    out["false_alarm_rate_clean_runs"] = float(flag[clean].mean())
    out["detection_by_attack"], out["run_level"] = {}, {}
    for a in ATTACKS:
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


def evalset(layer, d):
    by_run = {r: g for r, g in d.groupby("run", sort=False)}
    ev = score_groups(layer, by_run)
    return EvalSet({layer.name: ev}, d["label"].to_numpy(), np.where(d["label"] == 1, d["attack"], "normal"),
                   d["run"].to_numpy(), d["k"].to_numpy(dtype=float)), ev


def raw_equiv_threshold(layer):
    """Raw-score value t such that (calibrated score >= layer.threshold) <=> raw > t."""
    s = layer.calibrator.sorted_
    cal = np.searchsorted(s, s, side="left") / len(s)
    return float(s[np.flatnonzero(cal < layer.threshold).max()])


def main():
    rng = np.random.default_rng(SEED)
    df = build(rng)
    rows, runs = df.groupby("part").size().to_dict(), df.groupby("part")["run"].nunique().to_dict()
    print("rows", rows, "runs", runs, flush=True)
    y = df["label"].to_numpy()
    te = (df["part"] == "test").to_numpy()
    fit_rows = (df["part"] != "test") & (y == 0)            # v2 threshold set: train+val normal rows

    # --- main reproduction: layer calibrated on v2's normal rows, test scored once
    layer = B2Layer().calibrate(df[fit_rows], budget=0.01)
    ev_te = score_groups(layer, {r: g for r, g in df[te].groupby("run", sort=False)})
    flag = np.zeros(len(df), bool)
    order = np.concatenate([g.index.to_numpy() for _, g in df[te].groupby("run", sort=False)])
    flag[order] = [e.alarm for e in ev_te]
    res = {"rows": rows, "runs": runs, "calibration_rows": int(fit_rows.sum()),
           "still_rate_on_calibration_rows": float(df.loc[fit_rows, "still"].mean()),
           "v3_layer_threshold_calibrated": layer.threshold, "v3_threshold_m_raw_equivalent": raw_equiv_threshold(layer)}
    res["v3"] = v2_evaluate(df, flag)

    # --- harness run with the same calibration rows as "validation" (AUC, detection at 1% budget)
    vs, _ = evalset(layer, df[fit_rows])
    ts, _ = evalset(layer, df[te])
    h = evaluate_domain("regression_b2_harness", vs, ts, wp="WP0", method="max")
    res["harness_v2_calibration_rows"] = {"threshold_cal": h["layers"][layer.name]["threshold"],
                                          "auc": h["layers"][layer.name]["auc"],
                                          "detection_by_attack": h["layers"][layer.name]["detection_by_attack"],
                                          "false_alarm_rate_test_normal": h["layers"][layer.name]["false_alarm_rate"]}

    # --- v3-protocol variant (information only): calibration on VAL drives' normal rows only
    val_rows = (df["part"] == "val") & (y == 0)
    lay2 = B2Layer().calibrate(df[val_rows], budget=0.01)
    vs2, _ = evalset(lay2, df[(df["part"] == "val")])
    ts2, ev2 = evalset(lay2, df[te])
    h2 = evaluate_domain("regression_b2_val_only", vs2, ts2, wp="WP0", method="max")
    flag2 = np.zeros(len(df), bool)
    flag2[order] = [e.alarm for e in ev2]
    res["v3_protocol_val_only"] = {"threshold_m_raw_equivalent": raw_equiv_threshold(lay2),
                                   **v2_evaluate(df, flag2), "auc": h2["layers"][lay2.name]["auc"]}

    # --- compare with v2 json
    v2 = json.loads(V2_JSON.read_text())["B2_dead_reckoning_rule"]
    cmp, ok = {}, True

    def chk(key, a, b, tol=1e-4):
        nonlocal ok
        good = abs(a - b) <= tol
        ok &= good
        cmp[key] = {"v2": b, "v3": a, "abs_diff": abs(a - b), "match": bool(good)}

    chk("false_alarm_rate_clean_runs", res["v3"]["false_alarm_rate_clean_runs"], v2["false_alarm_rate_clean_runs"])
    chk("threshold_m", res["v3_threshold_m_raw_equivalent"], v2["threshold_m"], tol=5e-4)
    for a in ATTACKS:
        chk(f"row_detection_{a}", res["v3"]["detection_by_attack"][a], v2["detection_by_attack"][a])
        chk(f"run_detected_{a}", res["v3"]["run_level"][a]["detected"], v2["run_level"][a]["detected"])
        chk(f"run_median_delay_{a}", res["v3"]["run_level"][a]["median_delay_s"], v2["run_level"][a]["median_delay_s"], 0)
    for k in ("tp", "fp", "fn", "tn"):
        chk(f"all_test_rows_{k}", res["v3"]["all_test_rows"][k], v2["all_test_rows"][k], 0)
    res["comparison_with_v2"] = cmp
    res["all_match"] = bool(ok)
    out = results_dir("WP0") / "regression_b2.json"
    out.write_text(json.dumps(res, indent=1, default=float))
    for k, v in cmp.items():
        print(f"{k:34s} v2 {v['v2']:.6f}  v3 {v['v3']:.6f}  {'OK' if v['match'] else 'DIFF'}")
    print("ALL MATCH:", ok)
    print(markdown_table(h2))


if __name__ == "__main__":
    main()
