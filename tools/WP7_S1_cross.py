"""WP7 S1 cross-domain: the 1 s witness step as a stream (system/cross_runner.py) vs the frozen WP6 batch (WhichDomainLies.evidence on the whole run).
Level 1 (residual level): every VALIDATION-part run of the WP6 S2b cache (KITTI val drives 0011 0035 0027; clean + GPS / LiDAR / CAN attacks) fed second by second.
Level 2 (MotionEstimate level): clean, GPS-spoof (doppler_spoof) and CAN-offset variants of each val drive, phase 0; the four frozen producers (gps.domain.gps_motion_estimates, imu gyro,
LiDAR odometry cache, simulated CAN wheel speed decoded by the frozen CanDomain) feed the aligner as separate MotionEstimate streams, interleaved by time.
A1 exactness, A2 causality by truncation, A3 reset, A4 latency (3 repetitions). No test drive is read. The cross object is the runtime-test object of tools/WP7_S1_cross_fit.py.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_cross.py     Output: results/WP7/S1_cross.json
"""
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S1_lib as L

import numpy as np

import WP1_S4_lib as W1
import WP6_S1_kitti as S1k
from can.domain import CanDomain
from common.config import DATA_EXTRA, SEED
from common.motion import MotionEstimate
from crossdomain import attacks as A
from crossdomain import can_sim
from crossdomain import kitti as K
from crossdomain import witness as W
from gps import stream as GS
from gps.domain import gps_motion_estimates
from system.cross_runner import CrossObject, CrossRunner, residuals
from system.runner import compare_sequences

CACHE = DATA_EXTRA / "cache_v3" / "WP6" / "s2b_kitti.pkl"
SOURCE_ORDER = {"gps": 0, "lidar": 1, "can": 2, "imu": 3}
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


merge = L.merge


def batch_evidence(obj, key, t, R, V, first_id=0):
    """Batch reference at residual level: R, V (T x E) -> Z -> WhichDomainLies.evidence over the whole run."""
    Z = np.column_stack([obj.models[e.name].z(R[:, j], V[:, j]) for j, e in enumerate(obj.edges)])
    return obj.model.evidence(t, Z, [f"{key}/{first_id + i}" for i in range(len(t))])


def grid_residuals(grid, frames):
    G = {s: W.to_grid(f, grid) for s, f in frames.items()}
    G["gps"], G["lidar"] = K.forward_speed(G["gps"]), K.forward_speed(G["lidar"])
    res = residuals(G)
    names = list(res)
    return np.column_stack([res[n][0] for n in names]), np.column_stack([res[n][1] for n in names]), names


def events(mes):
    ev = [m for ms in mes.values() for m in ms]
    return sorted(ev, key=lambda m: (m.t, SOURCE_ORDER[m.source]))


def main():
    obj = CrossObject.load(L.OUT / "frozen_cross")
    names = [e.name for e in obj.edges]
    # ---------------- level 1: residual level, all validation runs of the S2b cache ----------------
    rows = pickle.load(open(CACHE, "rb"))["rows"]
    val = rows[rows["part"] == "val"]
    runner = CrossRunner(obj)
    cmps, n_alarm, runs_l1 = [], 0, 0
    steps_ns = []
    for run, g in val.groupby("run", sort=False):
        g = g.sort_values("t").reset_index(drop=True)
        R = np.column_stack([g[f"r_{n}"].to_numpy(float) for n in names])
        V = np.column_stack([g[f"v_{n}"].to_numpy(float) for n in names])
        t = g["t"].to_numpy(float)
        ev_b = batch_evidence(obj, run, t, R, V)
        runner.reset(run)
        out = []
        for i in range(len(t)):
            out.extend(runner.push({"t": t[i], "r": {n: R[i, j] for j, n in enumerate(names)}, "v": {n: V[i, j] for j, n in enumerate(names)}}))
        cmps.append(compare_sequences(out, ev_b))
        n_alarm += sum(e.alarm for e in ev_b)
        runs_l1 += 1
    a1_res = merge(cmps)
    a1_res["alarms_in_batch"] = int(n_alarm)
    a1_res["attacks"] = sorted(val["attack"].unique())
    log("A1 residual level", a1_res["all_identical"], a1_res["n_units"], a1_res["n_evidence"], "alarms", n_alarm)
    # ---------------- level 2: MotionEstimate level ----------------
    kx = W1.kitti_stream()
    dom_can = CanDomain.load(L.ROOT / "results" / "WP2" / "s7_domain")
    variants = []
    for d in ["0011", "0035", "0027"]:
        ox = GS.load_oxts(d)
        scale = S1k.VEHICLE_SCALE + np.random.default_rng([SEED, 6, 4, int(d)]).normal(0, S1k.R2_DRIVE_SIGMA)
        frames = can_sim.simulate_frames(ox, np.random.default_rng([SEED, 6, 2, int(d)]), scale=scale)
        can_me = can_sim.can_motion_estimates(dom_can, frames)
        kd = kx[kx["drive"] == d]
        pr = kd[kd["run"].str.startswith(f"{d}/p0/")]
        clean = pr[pr["run"] == f"{d}/p0/r0"].sort_values("t").reset_index(drop=True)
        lid_me = K.lidar_estimates(clean, d)
        spoof = pr[pr["attack"] == "doppler_spoof"]
        sp = spoof[spoof["run"] == spoof["run"].iloc[0]].sort_values("t").reset_index(drop=True)
        grid = clean["t"].to_numpy(float)
        # CAN offset attack on the decoded speed (WP6 attack generator), onset in the middle of the run
        rng = np.random.default_rng([SEED, 7, 1, int(d)])
        cf = W.to_frame(can_me)
        t_on = float(grid[len(grid) // 2])
        sp_att, _ = A.can_attack("can_offset", cf["t"].to_numpy(float), cf["speed"].to_numpy(float), t_on, rng)
        can_att = [MotionEstimate(t=m.t, source="can", speed=float(s), sigma=m.sigma) for m, s in zip(can_me, sp_att)]
        variants += [(f"{d}/clean", clean, can_me, lid_me, grid), (f"{d}/gps_doppler_spoof", sp, can_me, lid_me, grid), (f"{d}/can_offset", clean, can_att, lid_me, grid)]
    log("level 2 variants", len(variants))
    cmps2, info2, evs = [], [], {}
    batch2 = {}
    for key, rdf, can_me, lid_me, grid in variants:
        mes = {"gps": gps_motion_estimates(rdf), "imu": K.imu_motion_estimates(rdf), "lidar": lid_me, "can": can_me}
        frames = {s: W.to_frame(m, source=s) for s, m in mes.items()}
        R, V, _ = grid_residuals(grid, frames)
        R, V, tg = R[1:], V[1:], grid[1:]                      # the first fix has no GPS displacement
        ev_b = batch_evidence(obj, key, tg, R, V)
        batch2[key] = (mes, ev_b)
        rn = CrossRunner(obj)
        out = rn.run(events(mes), key=key)
        cmps2.append(compare_sequences(out, ev_b))
        info2.append({"run": key, "steps": len(out), "alarms": int(sum(e.alarm for e in ev_b)), "identical": cmps2[-1]["identical"], "max_abs_score_diff": cmps2[-1]["max_abs_score_diff"],
                      "blamed_domains": sorted({str(e.details["blamed_domain"]) for e in ev_b if e.alarm})})
    a1_me = merge(cmps2)
    a1_me["runs"] = info2
    bounded = [compare_sequences(CrossRunner(obj, keep_s=4.0).run(events(batch2[k][0]), key=k), batch2[k][1]) for k in batch2]
    a1_me["bounded_buffer_variant_keep_s_4"] = {**merge(bounded), "note": "report only: the cumulative-sum origin of the interval means moves, z changes by ~1e-13, and an ECDF step can flip when z equals a calibration sample"}
    log("A1 MotionEstimate level", a1_me["all_identical"], a1_me["n_evidence"])
    # ---------------- A2 truncation ----------------
    a2 = {"stream_prefix_equals_stream_full": [], "batch_truncated_sources_equal_batch_full_on_emitted_steps": []}
    for key in [v[0] for v in variants[:6]]:
        mes, ev_b = batch2[key]
        ev_list = events(mes)
        full = CrossRunner(obj).run(ev_list, key=key)
        for frac in (0.3, 0.6, 0.9):
            m = int(frac * len(ev_list))
            outk = CrossRunner(obj).run(ev_list[:m], key=key, flush=False)
            a2["stream_prefix_equals_stream_full"].append({"run": key, "events": m, "steps": len(outk), **compare_sequences(outk, full[:len(outk)])})
            # frozen batch alignment on the truncated source frames, at the grid points the stream resolved
            cut = {s: [e for e in ev_list[:m] if e.source == s] for s in mes}
            frames = {s: W.to_frame(cut[s], source=s) for s in mes}
            grid = np.array([e.t for e in mes["gps"]])
            Rk, Vk, _ = grid_residuals(grid, frames)
            sel = slice(0, len(outk))
            evk = batch_evidence(obj, key, grid[sel], Rk[sel], Vk[sel])
            a2["batch_truncated_sources_equal_batch_full_on_emitted_steps"].append({"run": key, "events": m, "steps": len(outk), **compare_sequences(evk, ev_b[:len(outk)])})
    allc = [c for k in a2 for c in a2[k]]
    a2["all_identical"] = all(c["identical"] for c in allc)
    a2["n_checks"] = len(allc)
    log("A2", a2["all_identical"])
    # ---------------- A3 reset ----------------
    keys = [v[0] for v in variants]
    r1 = CrossRunner(obj)
    r1.run(events(batch2[keys[0]][0]), key="A")
    after = r1.run(events(batch2[keys[2]][0]), key=keys[2])
    fresh = CrossRunner(obj).run(events(batch2[keys[2]][0]), key=keys[2])
    a3 = compare_sequences(after, fresh)
    log("A3", a3["identical"])
    # ---------------- A4 latency ----------------
    ns, em, sz, ns_res = [], [], [], []
    for rep in range(3):
        rr = CrossRunner(obj)
        for key in keys:
            rr.run(events(batch2[key][0]), key=key)
        ns.append(list(rr.latency.ns)), em.append(list(rr.latency.emit)), sz.append(list(rr.latency.size))
        rs = CrossRunner(obj)
        rs.reset("res")
        g0 = val.iloc[:300]
        for _, row in g0.iterrows():
            rs.push({"t": row["t"], "r": {n: row[f"r_{n}"] for n in names}, "v": {n: row[f"v_{n}"] for n in names}})
        ns_res.append(list(rs.latency.ns))
        log("latency rep", rep)
    lat = {"motion_estimate_events_all_calls": L.pooled(ns, em), "resolving_calls_one_witness_step": L.pooled(ns, em, only_emitting=True),
           "residual_level_step": L.pooled(ns_res), "step_period_s": 1.0, "v2_reference": "none (cross-domain layer is new in v3; v2 fusion ~0.3 ms is the fusion step, not measured here)"}
    lat["p99_step_below_period"] = bool(lat["resolving_calls_one_witness_step"]["pooled"]["p99_ms"] < 1000.0)
    res = {"data": {"level1": f"{runs_l1} validation-part runs of the WP6 S2b cache (KITTI val drives)", "level2": [v[0] for v in variants]},
           "A1_exactness_residual_level": a1_res, "A1_exactness_motion_estimate_level": a1_me, "A2_causality_truncation": a2, "A3_reset": a3, "A4_latency": lat,
           "machine": L.machine(), "seconds": time.time() - T0}
    L.dump(res, "S1_cross.json")
    log("done")


if __name__ == "__main__":
    main()
