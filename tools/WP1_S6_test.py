"""WP1 S6 final pass: ONE evaluation of the L2e map-matching layers on the KITTI test drives, with the choices of tools/WP1_S6_dev.py
(results/WP1/S6_dev.json, 16 train+val drives; q_d, q_h and the primary were fixed there). Every layer is calibrated twice and reported side by side:
valonly = 3 validation drives, lodo = pooled clean scores of the 16 train+val drives (tie-safe 1% budget).
Harness ablation on top of the S5 stack (L1 rules + B2 + L2a EKF NIS + L2b cusum_ekf + cusum_dr + L2d lidar_z_1) and on top of base + all instantaneous L2d.
Outputs: results/WP1/S6_kitti.json, S6_kitti_<harness>_{valonly,lodo}.json/.md. Run from codes_v3/: python -u -W ignore tools/WP1_S6_test.py
WP1_S6_DRY=1: code check with "test" := val rows, nothing written to results/WP1.
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
import WP1_S6_dev as D6
from common.evaluate import evaluate_domain
from common.metrics import auc
from gps import ekf, l1
from gps import lidar_odom as LO
from gps import map_match as MM
from gps.lodo import lodo_report

BUDGET = 0.01
DRY = bool(int(os.environ.get("WP1_S6_DRY", "0")))
OUT = Path(tempfile.gettempdir()) / "wp1_s6_dry" if DRY else L.OUT
OUT.mkdir(parents=True, exist_ok=True)


def main():
    dev_json = json.loads((L.OUT / "S6_dev.json").read_text())
    s4 = json.loads((L.OUT / "S4_dev.json").read_text())["selection"]
    primary = dev_json["selected_all16"]
    qd, qh = dev_json["q_d"], dev_json["q_h"]
    rmap = MM.RoadMap.from_osm()
    kx = L.kitti_stream()
    kx = kx.join(LO.stream_features(kx))
    kx = D6.add_comb(kx.join(MM.stream_features(kx, rmap)), qd, qh)
    dev, val, test = kx[kx["part"].isin(L.DEV_PARTS)], kx[kx["part"] == "val"], kx[kx["part"] == "test"]
    if DRY:
        test = val
    lay_e, lay_d, _, _, _, _ = T4.make_layers(s4)
    rules = l1.make_rules(l1.COVERAGE["kitti"]["evaluated"])
    b2 = L.S1.B2Layer()
    ek = ekf.EKFLayer(L.ekf_cfg(), "gps.ekf_nis")
    lid = [LO.LidarLayer(c) for c in ("lid_z_1", "lid_z_3", "lid_z_10", "lid_resid_1", "lid_resid_3", "lid_course")]
    maps = [MM.MapLayer(c) for c in D6.CANDS]
    prim = f"gps.{primary}"
    layers = rules + [b2, ek, lay_e, lay_d] + lid + maps
    base = [r.name for r in rules] + [b2.name, ek.name, lay_e.name, lay_d.name]
    l2d_all = [l.name for l in lid]
    res = {"dev_selection": {"primary_L2e": primary, "q_d": qd, "q_h": qh}, "calibration": {}}
    # on-road fraction of the attacked rows on test (physics bound for a map check)
    thr99 = dev_json["D2"]["p99"]
    res["on_road_fraction_test_within_dev_clean_p99"] = D6.on_road_fraction(test, thr99)
    res["clean_p99_m"] = thr99
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
        ESv, ESt = S2.merge_evalsets(sets_v), S2.merge_evalsets(sets_t)
        per = {}
        for l in layers:
            sm = L.summarize(test, flags[l.name])
            sm["threshold_raw_equivalent"] = L.S1.raw_equiv_threshold(l)
            sm["auc_row_level"] = auc(test["label"].to_numpy(), raws[l.name])
            per[l.name] = sm
        trans = {}
        for l in [b2, ek, lay_e, lay_d] + lid[:1] + maps:
            nm = dev["label"] == 0
            raw = np.asarray(l.raw_scores(dev[nm]), float)
            rep = lodo_report(raw, dev.loc[nm, "drive"].to_numpy(), BUDGET)
            trans[l.name] = {"lodo_heldout_fa_pooled": rep["heldout_fa_pooled"], "lodo_worst_drive_fa": rep["heldout_fa_worst_drive"],
                             "pooled_threshold_raw": rep["pooled_threshold"], "in_sample_fa_dev": rep["in_sample_fa"],
                             "per_drive_fa": {k: v["fa"] for k, v in rep["per_drive"].items()}}
        res["calibration"][scheme] = {"per_layer": per, "lodo_transfer": trans}
        s5 = base + ["gps.lidar_z_1"]
        runs = {"S6_base": base,
                "S6_base_plus_map": base + [prim],
                "S6_s5stack": s5,
                "S6_s5stack_plus_map": s5 + [prim],
                "S6_s5stack_plus_map_all3": s5 + [m.name for m in maps],
                "S6_l2d_all_stack": base + l2d_all,
                "S6_l2d_all_stack_plus_map": base + l2d_all + [prim],
                "S6_map_alone": [prim],
                "S6_b2_plus_map": [b2.name, prim]}
        harness = {}
        for nm, ns in runs.items():
            h = evaluate_domain(f"{nm}_{scheme}", S2.subset(ESv, ns), S2.subset(ESt, ns), wp="WP1", budget=BUDGET, method="auto", out_dir=OUT)
            harness[nm] = {"layers": h["layers"], "combined": h["combined"], "ablation": h["ablation"]}
            print(scheme, nm, "AUC", round(h["combined"]["auc"], 4), "FA", round(h["combined"]["false_alarm_rate"], 4), "det", round(h["combined"]["detection"], 4), flush=True)
        res["calibration"][scheme]["harness"] = harness
    (OUT / "S6_kitti.json").write_text(json.dumps(res, indent=1, default=float))
    print("done", flush=True)


if __name__ == "__main__":
    main()
