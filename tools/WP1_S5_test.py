"""WP1 S5 final pass: ONE evaluation of the L2d LiDAR-odometry layers on the KITTI test drives, with the choices made in tools/WP1_S5_dev.py
(results/WP1/S5_dev.json, 16 train+val drives). Every layer is calibrated twice and reported side by side:
  valonly = 3 validation drives, lodo = pooled clean scores of the 16 train+val drives (tie-safe 1% budget; supervisor policy).
Harness ablation on top of the S4 stack (L1 rules + B2 + L2a EKF NIS + L2b cusum_ekf + cusum_dr): + L2d primary, + all L2d, L2d alone.
Also writes the MotionEstimate publication (results/WP1/S5_motion_estimates.json: 1 Hz, phase 0, all 23 drives).
Outputs: results/WP1/S5_kitti.json, S5_kitti_<harness>_{valonly,lodo}.json/.md, S5_motion_estimates.json.
Run from codes_v3/: python -u -W ignore tools/WP1_S5_test.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
import WP1_S4_test as T4
import WP1_S2_l1 as S2
import WP1_S5_odom_run as R
from common.evaluate import evaluate_domain
from common.metrics import auc
from gps import ekf, l1, lidar_dr
from gps import lidar_odom as LO
from gps import stream as S
from gps.lodo import lodo_report

BUDGET = 0.01
DRY = bool(int(os.environ.get("WP1_S5_DRY", "0")))          # code check on development data only: "test" := val rows, nothing written to results/WP1
OUT = Path(tempfile.gettempdir()) / "wp1_s5_dry" if DRY else L.OUT
OUT.mkdir(parents=True, exist_ok=True)


def parse_seq(name):
    stat, k = name.split("_")[2].split("|")[0], float(name.split("k=")[1])
    return stat, k


def l2d_layers(dev_json):
    cands = dev_json["candidates"]
    seq = max((c for c in cands if c.startswith("cusum_lidar")), key=lambda c: cands[c]["J"])
    stat, kp = parse_seq(seq)
    layers = {"lid_z_1": LO.LidarLayer("lid_z_1"), "lid_z_3": LO.LidarLayer("lid_z_3"), "lid_z_10": LO.LidarLayer("lid_z_10"),
              "lid_resid_1": LO.LidarLayer("lid_resid_1"), "lid_resid_3": LO.LidarLayer("lid_resid_3"), "lid_course": LO.LidarLayer("lid_course")}
    cl = lidar_dr.LidarCusumLayer(stat, kp, L.ekf_cfg(), name="gps.cusum_lidar")
    return list(layers.values()) + [cl], seq


def main():
    dev_json = json.loads((L.OUT / "S5_dev.json").read_text())
    s4 = json.loads((L.OUT / "S4_dev.json").read_text())["selection"]
    primary = dev_json["selected_all16"]
    kx = L.kitti_stream()
    kx = kx.join(LO.stream_features(kx))
    dev, val, test = kx[kx["part"].isin(L.DEV_PARTS)], kx[kx["part"] == "val"], kx[kx["part"] == "test"]
    if DRY:
        test = val
    lay_e, lay_d, _, e_cfg, d_cfg, _ = T4.make_layers(s4)
    rules = l1.make_rules(l1.COVERAGE["kitti"]["evaluated"])
    b2 = L.S1.B2Layer()
    ek = ekf.EKFLayer(L.ekf_cfg(), "gps.ekf_nis")
    new, seq_name = l2d_layers(dev_json)
    prim_layer = {"lid_z_1": "gps.lidar_z_1", "lid_z_3": "gps.lidar_z_3", "lid_z_10": "gps.lidar_z_10", "lid_resid_1": "gps.lidar_resid_1",
                  "lid_resid_3": "gps.lidar_resid_3"}.get(primary, "gps.cusum_lidar")
    layers = rules + [b2, ek, lay_e, lay_d] + new
    res = {"dev_selection": {"primary_L2d": primary, "primary_layer_name": prim_layer, "sequential_candidate": seq_name},
           "calibration": {}}
    te = test
    assert (te.index == np.concatenate([g.index.to_numpy() for _, g in test.groupby("run", sort=False)])).all()
    base = [r.name for r in rules] + [b2.name, ek.name, lay_e.name, lay_d.name]
    for scheme, cal_df in (("valonly", val), ("lodo", dev)):
        print("=== calibration", scheme, flush=True)
        norm = cal_df[cal_df["label"] == 0]
        for l in layers:
            l.calibrate(norm, budget=BUDGET)
        sets_v, sets_t, flags, raws = [], [], {}, {}
        for l in layers:
            sv, _ = L.S1.evalset(l, cal_df)
            st, ev_t = L.S1.evalset(l, test)
            sets_v.append(sv); sets_t.append(st)
            flags[l.name] = S2.flags_from(ev_t)
            raws[l.name] = np.array([x.score for x in ev_t])
            print("  scored", l.name, flush=True)
        ESv, ESt = S2.merge_evalsets(sets_v), S2.merge_evalsets(sets_t)
        per = {}
        for l in layers:
            sm = L.summarize(te, flags[l.name])
            sm["threshold_raw_equivalent"] = L.S1.raw_equiv_threshold(l)
            sm["auc_row_level"] = auc(te["label"].to_numpy(), raws[l.name])
            per[l.name] = sm
        trans = {}
        for l in [b2, ek, lay_e, lay_d] + new:
            nm = dev["label"] == 0
            raw = np.asarray(l.raw_scores(dev[nm]), float)
            rep = lodo_report(raw, dev.loc[nm, "drive"].to_numpy(), BUDGET)
            trans[l.name] = {"lodo_heldout_fa_pooled": rep["heldout_fa_pooled"], "lodo_worst_drive_fa": rep["heldout_fa_worst_drive"],
                             "pooled_threshold_raw": rep["pooled_threshold"], "in_sample_fa_dev": rep["in_sample_fa"],
                             "per_drive_fa": {k: v["fa"] for k, v in rep["per_drive"].items()}}
        res["calibration"][scheme] = {"per_layer": per, "lodo_transfer": trans}
        runs = {"S5_stack": base,                                             # the S4 'all' stack (reference)
                "S5_stack_plus_primary": base + [prim_layer],
                "S5_stack_plus_seq": base + ["gps.cusum_lidar"],
                "S5_stack_plus_all_L2d": base + [n.name for n in new],
                "S5_l2d_alone_primary": [prim_layer],
                "S5_l2d_alone_all": [n.name for n in new],
                "S5_b2_plus_primary": [b2.name, prim_layer],
                "S5_b2_l1_l2a_l2b_plus_primary_no_l2a": [n for n in base if n != ek.name] + [prim_layer]}
        harness = {}
        for nm, ns in runs.items():
            h = evaluate_domain(f"{nm}_{scheme}", S2.subset(ESv, ns), S2.subset(ESt, ns), wp="WP1", budget=BUDGET, method="auto", out_dir=OUT)
            harness[nm] = {"layers": h["layers"], "combined": h["combined"], "ablation": h["ablation"]}
            print(scheme, nm, "AUC", round(h["combined"]["auc"], 4), "FA", round(h["combined"]["false_alarm_rate"], 4), "det", round(h["combined"]["detection"], 4), flush=True)
        res["calibration"][scheme]["harness"] = harness
    (OUT / "S5_kitti.json").write_text(json.dumps(res, indent=1, default=float))
    if not DRY:
        publish_motion()
    print("done", flush=True)


def publish_motion():
    """MotionEstimate stream (source 'lidar') at 1 Hz (phase 0 of the stream) for every drive, as JSON records."""
    rec = {}
    for d in sorted(S.SCENE):
        tp, rel, q = R.load_cached(d)
        P = LO.chain_poses(rel)
        t_fix = np.arange(0.0, tp[-1], 1.0)
        bad = np.r_[0.0, np.cumsum(q[:, 4] > 0)]
        ok = [bad[min(np.searchsorted(tp, t), len(tp) - 1)] - bad[min(np.searchsorted(tp, t - 1.0), len(tp) - 1)] == 0 for t in t_fix]
        me = LO.motion_estimates(t_fix, P, tp, quality_ok=ok)
        rec[d] = [{"t": m.t, "source": m.source, "speed": m.speed, "yaw_rate": m.yaw_rate, "displacement": list(m.displacement), "sigma": m.sigma} for m in me]
    (OUT / "S5_motion_estimates.json").write_text(json.dumps({"frame": "displacement = (forward, left) in metres over the last second in the body frame at the start of the second",
                                                              "drives": rec}, indent=0))


if __name__ == "__main__":
    main()
