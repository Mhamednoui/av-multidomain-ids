"""WP7 S2 vehicle-block passes: GPS domain + cross-domain layer streamed fix by fix / witness by witness on the TEST material (K = KITTI test drives, C = comma2k19 test routes).
Stages (python -u -W ignore tools/WP7_S2_veh.py <stage>):
  check  integrity: the ORIGINAL WP1 / WP6 test runs (clean r0 of every test drive and phase, plus the original GPS attack runs) go through the same runner chain; the tick scores / alarms
         must equal the M2 packs (s3_gps, s3_cross_kitti) -> results/WP7/S2_check_veh.json. This is the proof that the stream equals the batch packs on identical input.
  k      K family: for each of the 7 test drives x 10 phases: clean run, GPS attacks drift / accel_drift / doppler_spoof / meaconing (gps.stream.make_run, onset fixed at fix 3),
         coordinated gps_can (WP6 S2 coordinated(), k0 = 3), motion-sensor attacks lidar_scale / bias / yaw and can_scale / offset / freeze (crossdomain.attacks at t_on = grid[3]).
         GPS: GPSRunner (frozen_gps) per fix with the LiDAR-odometry columns; wheel witness: simulated CAN frames through CANRunner (pop_motion); cross: CrossRunner over the
         MotionEstimate streams of gps / imu / lidar odometry / can interleaved by time. -> ../data_extra/cache_v3/WP7/S2_veh_K.pkl
  c      C family: the comma test routes (16 clean 120 s windows + every attack window x 2 repetitions x 9 attacks, onset fixed at +3 s of the window, same residual code as
         tools/WP6_S2_comma.py) through CrossRunner.step_residuals (witnesses aligned upstream, cross layer per second). -> S2_veh_C.pkl
Seeds: [42, 77, 4, drive, phase, run] (GPS runs), [42, 77, 6, ...] (aux noise), [42, 77, 5, drive, phase, attack index] (injected attacks), comma [42, 77, 5, route index, window, attack index, rep].
Latency: every runner's LatencyLog is kept (ns per push) in the output.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L

import numpy as np
import pandas as pd

from can.domain import CanDomain
from common.config import SEED
from common.motion import MotionEstimate
from crossdomain import attacks as A
from crossdomain import kitti as K
from crossdomain import witness as W
from crossdomain import can_sim
from gps import lidar_odom as LO
from gps import stream as GS
from gps.domain import gps_motion_estimates
from system.can_runner import CANRunner
from system.cross_runner import CrossRunner
from system.gps_runner import INPUT_COLUMNS, GPSRunner
import WP6_S1_kitti as S1k
import WP6_S2_kitti as SK
import WP1_S4_lib as W1

ROOT = L.ROOT
FROZEN_GPS = ROOT / "results" / "WP1" / "frozen_gps"
FROZEN_CAN = ROOT / "results" / "WP2" / "s7_domain"
GPS_ATT = ["drift", "accel_drift", "doppler_spoof", "meaconing"]
LID_ATT = ["lidar_scale", "lidar_bias", "lidar_yaw"]
CAN_ATT = ["can_scale", "can_offset", "can_freeze"]
INJ = LID_ATT + CAN_ATT + ["gps_can"]               # same order (attack index ia) as WP6 S2
SRC_ORDER = {"gps": 0, "lidar": 1, "can": 2, "imu": 3}
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def events(mes):
    ev = [m for ms in mes.values() for m in ms]
    return sorted(ev, key=lambda m: (m.t, SRC_ORDER[m.source]))


def samples(df):
    cols = [c for c in INPUT_COLUMNS if c in df.columns]
    return df[cols].to_dict("records")


def gps_series(run_runner, df, name, family, group):
    """df: run frame (stream columns + lid_*) -> GPS tick series via GPSRunner, one fix at a time."""
    n_layers = len(run_runner.dom.names)
    out = run_runner.run(samples(df), key=name)
    comb, lay = out[0::n_layers + 1], [out[1 + j::n_layers + 1] for j in range(n_layers)]
    score = np.array([e.score for e in comb])
    layers = np.column_stack([[e.score for e in l] for l in lay])
    la = np.column_stack([[e.alarm for e in l] for l in lay])
    lab = df["label"].to_numpy() > 0
    return L.make_series(group, name, "attack" if family != "none" else "clean", family, score, layers, [e.alarm for e in comb], la, lab, df["t"].to_numpy(float),
                         reasons=[e.reason for e in comb])


def ME_lidar_attack(name, mes, t_on, rng):
    """Same arithmetic and rng draws as crossdomain.attacks.lidar_attack, applied to a list of lidar MotionEstimates (displacement, yaw_rate)."""
    t = np.array([m.t for m in mes])
    dx = np.array([m.displacement[0] if m.displacement is not None else np.nan for m in mes])
    dy = np.array([m.displacement[1] if m.displacement is not None else np.nan for m in mes])
    yw = np.array([np.nan if m.yaw_rate is None else m.yaw_rate for m in mes])
    sp = np.array([np.nan if m.speed is None else m.speed for m in mes])
    on = t >= t_on
    if name == "lidar_scale":
        s = A.sign(rng) * rng.uniform(*A.LIDAR_SEV[name])
        dx, dy, sp = (np.where(on, v * (1 + s), v) for v in (dx, dy, sp))
    elif name == "lidar_bias":
        b = A.sign(rng) * rng.uniform(*A.LIDAR_SEV[name])
        w = A.ramp(t, t_on, b)
        dx, sp = dx + w, sp + w
    elif name == "lidar_yaw":
        w = A.sign(rng) * rng.uniform(*A.LIDAR_SEV[name])
        yw = np.where(on, yw + w, yw)
    else:
        raise ValueError(name)
    return [MotionEstimate(t=m.t, source="lidar", speed=None if np.isnan(a) else float(a), yaw_rate=None if np.isnan(y) else float(y),
                           displacement=None if m.displacement is None else (float(b), float(c)), sigma=m.sigma) for m, a, b, c, y in zip(mes, sp, dx, dy, yw)]


def ME_can_attack(name, mes, t_on, rng):
    t = np.array([m.t for m in mes])
    v = np.array([m.speed for m in mes])
    v2, sev = A.can_attack(name, t, v, t_on, rng)
    return [MotionEstimate(t=m.t, source="can", speed=float(s), sigma=m.sigma) for m, s in zip(mes, v2)]


def wheel_motion(d, dom_can):
    """Simulated wheel-speed frames of drive d (WP6 S1 / S2 seeds and R2 scale), decoded by the frozen CanDomain decoder (CanDomain.motion_estimates; the ROAD scoring layers of
    CANRunner need the full ROAD signal set, which a wheel-speed-only simulation does not have)."""
    ox = GS.load_oxts(d)
    scale = S1k.VEHICLE_SCALE + np.random.default_rng([SEED, 6, 4, int(d)]).normal(0, S1k.R2_DRIVE_SIGMA)
    frames = can_sim.simulate_frames(ox, np.random.default_rng([SEED, 6, 2, int(d)]), scale=scale)
    return can_sim.can_motion_estimates(dom_can, frames), ox


def cross_series(obj, mes, grid, key, family, group, onset_t, cross_run):
    cross_run.obj = obj
    out = cross_run.run(events(mes), key=key)
    score, layers, alarm, blame, present = L.cross_ticks(out, grid)
    lab = (grid >= onset_t) if np.isfinite(onset_t) else np.zeros(len(grid), bool)
    s = L.make_series(group, key, "attack" if family != "none" else "clean", family, score, layers, alarm, layers > 0, lab, grid, blame=blame, present=present)
    s["dom_alarm"] = alarm
    s["layer_alarm"] = (layers > 0)
    return s


# ---------------------------------------------------------------------------------------------------------------------------------- check
def stage_check():
    """Original WP1 test runs -> runner chain -> compare with the M2 packs."""
    import json
    kx = W1.kitti_stream()
    kx = kx[kx["part"] == "test"].copy()
    kx = kx.join(LO.stream_features(kx))
    packg = pd.read_pickle(L.WP6C / "s3_gps.pkl")["test"]
    packc = pd.read_pickle(L.WP6C / "s3_cross_kitti.pkl")["test"]
    gs = {s["name"]: s for s in packg["series"]}
    cs = {s["name"]: s for s in packc["series"]}
    grun = GPSRunner(FROZEN_GPS)
    can_run = CanDomain.load(FROZEN_CAN)
    cross_run = CrossRunner(L.kitti_cross_object())
    obj = cross_run.obj
    res = {"gps": {"runs": 0, "max_score_diff": 0.0, "alarm_mismatch": 0, "layer_alarm_mismatch": 0}, "cross": {"runs": 0, "max_score_diff": 0.0, "alarm_mismatch": 0, "blame_mismatch": 0}}
    wm = {}
    for d in sorted(set(kx["drive"])):
        wm[d] = wheel_motion(d, can_run)[0]
    log("wheel witnesses", {d: len(v) for d, v in wm.items()})
    dom = grun.dom
    for run, df in kx.groupby("run", sort=False):
        df = df.sort_values("t").reset_index(drop=True)
        if run in gs and df["attack"].iloc[0] in ("none", "drift", "accel_drift", "doppler_spoof", "meaconing"):
            s = gps_series(grun, df, run, df["attack"].iloc[0], df["drive"].iloc[0])
            p = gs[run]
            res["gps"]["runs"] += 1
            res["gps"]["max_score_diff"] = max(res["gps"]["max_score_diff"], float(np.abs(s["score"] - p["score"]).max()))
            res["gps"]["alarm_mismatch"] += int((s["dom_alarm"] != (np.asarray(p["score"]) >= packg["dom_thr"])).sum())
            la = (p["layers"] >= np.asarray(packg["layer_thr"])[None, :])
            res["gps"]["layer_alarm_mismatch"] += int((s["layer_alarm"] != la).sum())
        if df["attack"].iloc[0] == "none" and run.endswith("/r0"):
            d, ph = run.split("/")[0], run.split("/")[1]
            if run not in cs:
                continue
            grid = df["t"].to_numpy(float)
            lid = K.lidar_estimates(df, d)
            mes = {"gps": gps_motion_estimates(df), "imu": K.imu_motion_estimates(df), "lidar": lid, "can": wm[d]}
            s = cross_series(obj, mes, grid, run, "none", d, np.nan, cross_run)
            p = cs[run]
            idx = np.searchsorted(grid, np.asarray(p["t"], float) - 1e-6)
            ok = s["present"][idx]
            res["cross"]["runs"] += 1
            if ok.any():
                res["cross"]["max_score_diff"] = max(res["cross"]["max_score_diff"], float(np.abs(s["score"][idx][ok] - np.asarray(p["score"])[ok]).max()))
            res["cross"]["alarm_mismatch"] += int((s["dom_alarm"][idx][ok] != np.asarray(p["dom_alarm"], bool)[ok]).sum())
            res["cross"]["absent_pack_nonzero"] = res["cross"].get("absent_pack_nonzero", 0) + int((np.asarray(p["score"])[~ok] > 0).sum())
            res["cross"]["ticks_compared"] = res["cross"].get("ticks_compared", 0) + int(ok.sum())
            pb = np.array([None if x is None else str(x) for x in p["blame"]], object)
            sb = np.array([None if x is None else str(x) for x in s["blame"][idx]], object)
            res["cross"]["blame_mismatch"] += int(sum((x != y) for x, y, o, al in zip(sb, pb, ok, np.asarray(p["dom_alarm"], bool)) if o and al))
            res["cross"].setdefault("pack_vs_stream_len", []).append([int(s["present"].sum()), len(p["score"])])
    res["cross"]["pack_vs_stream_len"] = sorted({tuple(x) for x in res["cross"]["pack_vs_stream_len"]})[:8]
    log("check", {k: {kk: vv for kk, vv in v.items() if kk != "pack_vs_stream_len"} for k, v in res.items()})
    (L.OUT / "S2_check_veh.json").write_text(json.dumps(res, indent=1, default=lambda o: list(o) if isinstance(o, tuple) else float(o)))


# ---------------------------------------------------------------------------------------------------------------------------------- K family
def vehicle_inputs(d, ph, ox, wm):
    """All sample streams of the K vehicle block (drive d, phase ph): GPS run frames per family (with the LiDAR-odometry columns) and the MotionEstimate streams of the four cross-domain
    witnesses per family, onset at fix 3 (deterministic from the seeds [42, 77, ...])."""
    g = GS.resample_1hz(ox, ph / GS.PHASES)
    if len(g["t"]) < 6:
        return None
    grid = np.asarray(g["t"], float)
    runs = {}

    def frame(f, name):
        f = f.copy()
        f["drive"], f["part"], f["run"], f["k"] = d, "test", name, np.arange(len(f))
        f = f[GS.COLUMNS]
        return f.join(LO.stream_features(f))

    rng = lambda *x: np.random.default_rng([SEED, 77, *x])
    clean = frame(GS.make_run(ox, g, rng(4, int(d), ph, 0), None, rng(6, int(d), ph, 0)), f"{d}/p{ph}/r0")
    runs["none"] = clean
    for r, a in enumerate(GPS_ATT, start=1):
        runs[a] = frame(GS.make_run(ox, g, L.FixedOnsetRng(rng(4, int(d), ph, r)), a, rng(6, int(d), ph, r)), f"{d}/p{ph}/{a}")
    # coordinated gps_can on the clean run (WP6 S2 coordinated(), k0 = 3)
    ia = INJ.index("gps_can")
    rg = rng(5, int(d), ph, ia)
    r2, (tw, w), sev_c = SK.coordinated(clean.drop(columns=[c for c in clean.columns if c.startswith("lid_")]), ox, L.ONSET, rg)
    r2["drive"], r2["part"], r2["run"], r2["k"] = d, "test", f"{d}/p{ph}/gps_can", np.arange(len(r2))
    r2 = r2[GS.COLUMNS]
    runs["gps_can"] = r2.join(LO.stream_features(r2))
    # cross: MotionEstimate streams
    lid = K.lidar_estimates(clean, d)
    t_on = float(grid[min(L.ONSET, len(grid) - 1)])
    base = {"gps": gps_motion_estimates(clean), "imu": K.imu_motion_estimates(clean), "lidar": lid, "can": wm}
    fams = {"none": base}
    for a in GPS_ATT:
        fams[a] = {**base, "gps": gps_motion_estimates(runs[a]), "imu": K.imu_motion_estimates(runs[a])}
    for ia_, a in enumerate(INJ):
        rr = rng(5, int(d), ph, ia_)
        if a in LID_ATT:
            fams[a] = {**base, "lidar": ME_lidar_attack(a, lid, t_on, rr)}
        elif a in CAN_ATT:
            fams[a] = {**base, "can": ME_can_attack(a, wm, t_on, rr)}
        else:
            tt = np.array([m.t for m in wm])
            wc = np.interp(tt, tw, w, left=0.0)
            can_g = [MotionEstimate(t=m.t, source="can", speed=float(max(m.speed + x, 0.0)), sigma=m.sigma) for m, x in zip(wm, wc)]
            fams[a] = {**base, "gps": gps_motion_estimates(r2), "can": can_g}
    onset = {fam: t_on for fam in fams}
    onset["none"] = np.nan
    for fam in GPS_ATT:
        onset[fam] = float(runs[fam]["onset_t"].iloc[0])
    onset["gps_can"] = float(grid[L.ONSET])
    return {"grid": grid, "runs": runs, "fams": fams, "onset": onset}


def stage_k():
    can_run = CanDomain.load(FROZEN_CAN)
    grun = GPSRunner(FROZEN_GPS)
    cross_run = CrossRunner(L.kitti_cross_object())
    obj = cross_run.obj
    res = {"series": {}, "meta": {}}
    for d in GS.TEST:
        wm, ox = wheel_motion(d, can_run)
        res["meta"][d] = {"n_wheel_me": len(wm), "scale": None}
        for ph in range(GS.PHASES):
            vi = vehicle_inputs(d, ph, ox, wm)
            if vi is None:
                continue
            grid, runs, fams = vi["grid"], vi["runs"], vi["fams"]
            gseries = {fam: gps_series(grun, df, df["run"].iloc[0], fam, d) for fam, df in runs.items()}
            for fam, s in gseries.items():
                s["onset"] = int(np.argmax(s["label"])) if s["label"].any() else -1
            for fam, mes in fams.items():
                cs = cross_series(obj, mes, grid, f"{d}/p{ph}/{fam}", fam, d, vi["onset"][fam], cross_run)
                cs["onset"] = int(np.argmax(cs["label"])) if cs["label"].any() else -1
                res["series"][(d, ph, fam)] = {"gps": gseries[fam if fam in gseries else "none"], "cross": cs, "t": grid, "n": len(grid)}
        log("K drive", d, "series", len(res["series"]))
    res["latency"] = {"gps": {"ns": list(grun.latency.ns), "emit": list(grun.latency.emit), "size": list(grun.latency.size)},
                      "cross": {"ns": list(cross_run.latency.ns), "emit": list(cross_run.latency.emit), "size": list(cross_run.latency.size)}}
    L.save_pickle(res, "S2_veh_K.pkl")
    log("saved K", len(res["series"]))


# ---------------------------------------------------------------------------------------------------------------------------------- C family
def comma_windows():
    """Test windows of the comma routes: yields (route, route index, window, family, rep, grid, residual rows {edge: (r, v)}, attack onset time or nan). Same code and seeds as stage_c."""
    import json
    import WP6_S2_comma as SC
    sm = json.loads((ROOT / "results" / "WP6" / "s1_sigma_models.json").read_text())["comma_R"]
    lags, gyro = sm["lags"], (sm["gyro"]["axis"], sm["gyro"]["sign"])
    c = pd.read_pickle(L.WP6C / "s1_comma_routes.pkl")
    data, part = c["data"], c["part"]
    for ri, n in enumerate(sorted(data)):
        if part[n] != "test":
            continue
        r = data[n]
        t0 = max(r["can_t"][0], r["gnss_t"][0], r["gyro_t"][0])
        t1 = min(r["can_t"][-1], r["gnss_t"][-1], r["gyro_t"][-1])
        grid = np.arange(np.ceil(t0) + 1.0, np.floor(t1) - 1.0, 1.0)
        sig = SC.native(r)
        for wi in range(len(grid) // SC.WIN):
            g = grid[wi * SC.WIN:(wi + 1) * SC.WIN]
            sw = SC.cut(sig, g[0] - 4.0, g[-1] + 2.0)
            yield n, ri, wi, "none", 0, g, SC.residuals(sw, g, lags, gyro), np.nan
            for ai, a in enumerate(SC.ATTACKS):
                for rep in range(SC.REPS):
                    rng = np.random.default_rng([SEED, 77, 5, ri, wi, ai, rep])
                    t_on = float(g[0] + L.ONSET)
                    _ = rng.uniform(SC.ON_LO, SC.ON_HI)          # keeps the draw pattern of WP6 S2 (onset draw replaced by the fixed onset)
                    s2, sev = SC.attack(sw, a, t_on, rng)
                    yield n, ri, wi, a, rep, g, SC.residuals(s2, g, lags, gyro), t_on


def stage_c():
    objs, clsall, setup = L.comma_cross_objects()
    run = CrossRunner(objs["g100"])
    edges = [e.name for e in objs["g100"].edges]
    res = {"series": {}, "windows": []}
    last = None
    for n, ri, wi, fam, rep, g, rr, t_on in comma_windows():
        run.obj = objs[clsall[n]]
        run.reset(f"{n}/w{wi}/{fam}/{rep}")
        out = []
        for i in range(len(g)):
            out.append(run.push({"t": float(g[i]), "r": {k: float(rr[k][0][i]) for k in edges if k in rr}, "v": {k: float(rr[k][1][i]) for k in edges if k in rr}})[0])
        score, layers, alarm, blame, present = L.cross_ticks(out, g)
        lab = (g >= t_on) if np.isfinite(t_on) else np.zeros(len(g), bool)
        s = L.make_series(n, f"{n}/w{wi}/{fam}/{rep}", "attack" if fam != "none" else "clean", fam, score, layers, alarm, layers > 0, lab, g, blame=blame, present=present)
        s["dom_alarm"], s["layer_alarm"] = alarm, layers > 0
        s["onset"] = int(np.argmax(lab)) if lab.any() else -1
        res["series"][(n, wi, fam, rep)] = s
        if last != n:
            log("C route", n, "series", len(res["series"]))
            last = n
    res["latency"] = {"ns": list(run.latency.ns), "emit": list(run.latency.emit), "size": list(run.latency.size)}
    L.save_pickle(res, "S2_veh_C.pkl")
    log("saved C", len(res["series"]))


if __name__ == "__main__":
    for st in sys.argv[1:] or ["check"]:
        {"check": stage_check, "k": stage_k, "c": stage_c}[st]()
