"""WP1 S4 final pass: ONE evaluation on the KITTI test drives (and the UAV flights) with the configuration chosen in tools/WP1_S4_dev.py
(results/WP1/S4_dev.json, 16 train+val drives). Every layer is calibrated twice and the two results are reported side by side:
  valonly = 3 validation drives (S2/S3 practice), lodo = pooled clean scores of the 16 train+val drives (tie-safe 1% budget; supervisor policy).
Outputs: results/WP1/S4_kitti.json (+ S4_kitti_<harness>_{valonly,lodo}.json/.md), S4_l2c.json, S4_uav.json.
Run from codes_v3/: python -u -W ignore tools/WP1_S4_test.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
import WP1_S2_l1 as S2
from common.evaluate import evaluate_domain
from common.metrics import auc
from gps import cusum, ekf, l1
from gps import stream as S
from gps.cusum import CusumLayer
from gps.ekf import EKFConfig
from gps.lodo import lodo_report

BUDGET = 0.01
DRY = bool(int(__import__('os').environ.get('WP1_S4_DRY', '0')))
OUT = Path(__import__('tempfile').gettempdir()) / 'wp1_s4_dry' if DRY else L.OUT
OUT.mkdir(parents=True, exist_ok=True)


def parse(name):
    p = name.split("|")
    head = p[0].split("_")                          # cusum, src, stat
    d = {"source": head[1], "stat": head[2], "kappa": float(p[1].split("=")[1])}
    if len(p) > 2:
        d["scale"], d["freeze"] = p[2].split("=")[1], p[3].split("=")[1]
    return d


def dr_kwargs(scale, freeze):
    from WP1_S4_dev import FREEZES, SCALES
    return {**SCALES[scale], **FREEZES[freeze]}


def make_layers(sel):
    e = parse(sel["best_ekf"])
    d = parse(sel["best_dr"])
    lay_e = CusumLayer("ekf", e["stat"], e["kappa"], L.ekf_cfg(), name="gps.cusum_ekf")
    cfg = L.dr_cfg(**dr_kwargs(d["scale"], d["freeze"]))
    lay_d = CusumLayer("dr", d["stat"], d["kappa"], L.ekf_cfg(), cfg, name="gps.cusum_dr")
    # ablation variants of the DR layer (same kappa / statistic)
    var = {
        "gps.cusum_dr_noscale": CusumLayer("dr", d["stat"], d["kappa"], L.ekf_cfg(), L.dr_cfg(**dr_kwargs("none", d["freeze"])), name="gps.cusum_dr_noscale"),
        "gps.cusum_dr_nofreeze": CusumLayer("dr", d["stat"], d["kappa"], L.ekf_cfg(), L.dr_cfg(**dr_kwargs(d["scale"], "never")), name="gps.cusum_dr_nofreeze"),
    }
    return lay_e, lay_d, var, e, d, cfg


def main():
    dev_json = json.loads((L.OUT / "S4_dev.json").read_text())
    sel = dev_json["selection"]
    kx = L.kitti_stream()
    dev, val, test = kx[kx["part"].isin(L.DEV_PARTS)], kx[kx["part"] == "val"], kx[kx["part"] == "test"]
    if DRY:                                          # code check on development data only: "test" := val rows, nothing written to results/WP1
        test = val
    lay_e, lay_d, var, e_cfg, d_cfg, dr_config = make_layers(sel)
    cols = l1.COVERAGE["kitti"]["evaluated"]
    rules = l1.make_rules(cols)
    b2 = L.S1.B2Layer()
    ek = ekf.EKFLayer(L.ekf_cfg(), "gps.ekf_nis")
    layers = rules + [b2, ek, lay_e, lay_d] + list(var.values())
    names = [l.name for l in layers]
    res = {"selection": sel, "ekf_cusum_config": e_cfg, "dr_cusum_config": d_cfg, "dr_config": dr_config.__dict__ | {"freeze_h": str(dr_config.freeze_h)},
           "calibration": {}}
    te = test
    assert (te.index == np.concatenate([g.index.to_numpy() for _, g in test.groupby("run", sort=False)])).all()
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
            sm = L.summarize(te, flags[l.name])
            sm["threshold_raw_equivalent"] = L.S1.raw_equiv_threshold(l)
            sm["auc_row_level"] = auc(te["label"].to_numpy(), raws[l.name])
            per[l.name] = sm
        # LODO transfer estimate vs actual test FA (new layers, B2, EKF)
        trans = {}
        for l in (b2, ek, lay_e, lay_d):
            nm = dev["label"] == 0
            raw = np.asarray(l.raw_scores(dev[nm]), float)
            rep = lodo_report(raw, dev.loc[nm, "drive"].to_numpy(), BUDGET)
            rep.pop("per_drive_full", None)
            trans[l.name] = {"lodo_heldout_fa_pooled": rep["heldout_fa_pooled"], "lodo_worst_drive_fa": rep["heldout_fa_worst_drive"],
                             "pooled_threshold_raw": rep["pooled_threshold"], "in_sample_fa_dev": rep["in_sample_fa"],
                             "per_drive_fa": {k: v["fa"] for k, v in rep["per_drive"].items()}}
        res["calibration"][scheme] = {"per_layer": per, "lodo_transfer": trans}
        base = [r.name for r in rules] + [b2.name, ek.name]
        runs = {"S4_all": base + [lay_e.name, lay_d.name],
                "S4_base_dr": base + [lay_d.name],
                "S4_base_ekfcusum": base + [lay_e.name],
                "S4_base": base,
                "S4_l2b_pair": [b2.name, ek.name, lay_e.name, lay_d.name]}
        harness = {}
        for nm, ns in runs.items():
            h = evaluate_domain(f"{nm}_{scheme}", S2.subset(ESv, ns), S2.subset(ESt, ns), wp="WP1", budget=BUDGET, method="auto", out_dir=OUT)
            harness[nm] = {"layers": h["layers"], "combined": h["combined"], "ablation": h["ablation"]}
            print(scheme, nm, "AUC", round(h["combined"]["auc"], 4), "FA", round(h["combined"]["false_alarm_rate"], 4), "det", round(h["combined"]["detection"], 4), flush=True)
        res["calibration"][scheme]["harness"] = harness
    # ---- L2c on test: scale convergence, drag with / without freezing; absorption of the DR branch ----
    l2c = {}
    for key, kw in {"learn+freeze(selected)": dr_kwargs(d_cfg["scale"], d_cfg["freeze"]), "learn+nofreeze": dr_kwargs("learn", "never"),
                    "noscale+freeze": dr_kwargs("none", d_cfg["freeze"])}.items():
        do = cusum.run_dr(test, L.dr_cfg(**kw), L.ekf_cfg())
        l2c[key] = {"scale": L.scale_diag(test, do), "absorption": L.absorption(test, do)}
    eo = ekf.run_filter_all(test, L.ekf_cfg())
    l2c["ungated_ekf_absorption"] = L.absorption(test, eo)
    (OUT / "S4_l2c.json").write_text(json.dumps(l2c, indent=1, default=float))
    (OUT / "S4_kitti.json").write_text(json.dumps(res, indent=1, default=float))
    if not DRY:
        run_uav(e_cfg)
    print("done", flush=True)


def run_uav(e_cfg):
    uav = l1.attach_uav_extras(S.load_uav())
    c = L.TUNE["uav_cfg"]
    cfg = EKFConfig(use_odo=False, use_head=False, acc_mode="window", gm_phi=c["gm_phi"], gm_sigma=c["gm_sigma"], r_pos=c["r_pos"], sd_dop=c["sd_dop"], q_acc=c["q_acc"])
    fl = {n: uav[uav["run"] == f"uav/{n}"] for n in S.UAV_FLIGHTS}
    res = {"calibration": "threshold at the 1% budget on the BENIGN flight (in-sample), noise from S3 (benign flight)"}
    for stat in ("nis", "axis"):
        for kp in (e_cfg["kappa"], 0.5, 1.0):
            nm = f"cusum_ekf_{stat}_k{kp}"
            lay = CusumLayer("ekf", stat, kp, cfg, name=nm).calibrate(fl["benign"], budget=BUDGET)
            o = {"flights": {}}
            for n, f in fl.items():
                lay.reset()
                a = S2.flags_from(lay.score(f))
                t = f["t"].to_numpy()
                r = {"fixes": int(len(f)), "alarms": int(a.sum())}
                if n == "spoofing":
                    pre, post = t < S.UAV_SPOOF_ONSET_S, t >= S2.UAV_FIRST_SPOOFED_FIX_S
                    hit = np.flatnonzero(a & post)
                    r.update({"false_alarm_before_117s": float(a[pre].mean()), "alarms_before_117s": int(a[pre].sum()), "fixes_before_117s": int(pre.sum()),
                              "first_alarm_after_118s": float(t[hit[0]]) if len(hit) else None,
                              "delay_from_first_spoofed_fix_s": float(t[hit[0]] - 118.0) if len(hit) else None,
                              "fraction_from_118s_flagged": float(a[post].mean())})
                o["flights"][n] = r
            res[nm] = o
    (OUT / "S4_uav.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
