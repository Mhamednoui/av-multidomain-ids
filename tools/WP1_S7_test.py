"""WP1 S7 final pass: ONE evaluation on the KITTI test drives of the learned layers chosen / trained in tools/WP1_S7_dev.py (dev drives only),
on top of the default stack (B2 + L1 + L2a + L2b + L2d, L2e out). Every layer is calibrated twice and reported side by side:
  valonly = out-of-fold scores of the 3 val drives, lodo = pooled out-of-fold clean scores of the 15 dev drives (tie-safe 1%).
Learned layers: s7_* score columns = out-of-fold scores on dev rows, final-model scores on test rows (the calibration thresholds therefore
never see an in-sample score).
Also: shuffled-label control of L4, per-drive test FA, L4 on AV-GPS and UAV (transfer; threshold of KITTI, and of the target's own normal data).
Outputs: results/WP1/S7_kitti.json, S7_kitti_<harness>_{valonly,lodo}.json/.md, S7_external.json. DRY=1 (WP1_S7_DRY): code check on the val rows.
Run from codes_v3/: python -u -W ignore tools/WP1_S7_test.py
"""
import json
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S7_lib as W
import WP1_S4_lib as L
import WP1_S2_l1 as S2
from common.evaluate import evaluate_domain
from common.metrics import auc, budget_threshold
from gps import learned
from gps import stream as S

BUDGET = 0.01
DRY = bool(int(os.environ.get("WP1_S7_DRY", "0")))
OUT = Path(tempfile.gettempdir()) / "wp1_s7_dry" if DRY else L.OUT
OUT.mkdir(parents=True, exist_ok=True)
T0 = time.time()


def log(*a, **k):
    print(f"[{time.time() - T0:6.0f}s]", *a, **k, flush=True)


def main():
    kx = L.kitti_stream()
    dev0 = kx[kx["part"].isin(L.DEV_PARTS)]
    dev = W.feature_frame(dev0, "dev")
    test0 = kx[kx["part"] == "val"] if DRY else kx[kx["part"] == "test"]
    test = W.feature_frame(test0, "dry_val" if DRY else "test")
    oof = np.load(W.CACHE / "s7_oof.npz")
    assert (oof["index"] == dev.index.to_numpy()).all()
    final = pickle.load(open(W.CACHE / "s7_final.pkl", "rb"))
    dev_cols = {"s7_l3": oof["l3"], "s7_l4": oof["l4_c2"], "s7_l4_nopos": oof["l4_nopos"], "s7_l4_all": oof["l4_all"]}
    Ft = W.c2_frame(test)
    test_cols = {"s7_l3": final["l3"].score(test), "s7_l4": final["l4"]["l4_c2"].score(Ft), "s7_l4_nopos": final["l4"]["l4_nopos"].score(Ft),
                 "s7_l4_all": final["l4"]["l4_all"].score(Ft)}
    for c in dev_cols:
        dev[c], test[c] = dev_cols[c], test_cols[c]
    val = dev[dev["part"] == "val"]
    te = test
    assert (te.index == np.concatenate([g.index.to_numpy() for _, g in te.groupby("run", sort=False)])).all()
    st = W.stack_layers()
    l3 = learned.l3_layer("s7_l3")
    l4 = learned.l4_layer("s7_l4", "gps.l4_c2")
    l4n = learned.l4_layer("s7_l4_nopos", "gps.l4_c2_nopos")
    l4a = learned.l4_layer("s7_l4_all", "gps.l4_c2_all_attacks")
    layers = st["stack"] + [l3, l4, l4n, l4a]
    names = [l.name for l in st["stack"]]
    res = {"final_choice": {"l3": final["l3_name"]}, "calibration": {}}
    for scheme, cal_df in (("valonly", val), ("lodo", dev)):
        log("=== calibration", scheme)
        norm = cal_df[cal_df["label"] == 0]
        for l in layers:
            l.calibrate(norm, budget=BUDGET)
        sets_v, sets_t, flags, raws = [], [], {}, {}
        for l in layers:
            sv, _ = L.S1.evalset(l, cal_df)
            stt, ev_t = L.S1.evalset(l, te)
            sets_v.append(sv); sets_t.append(stt)
            flags[l.name] = S2.flags_from(ev_t)
            raws[l.name] = np.array([x.score for x in ev_t])
            log("  scored", l.name)
        ESv, ESt = S2.merge_evalsets(sets_v), S2.merge_evalsets(sets_t)
        per = {}
        for l in layers:
            sm = L.summarize(te, flags[l.name])
            sm["threshold_raw_equivalent"] = L.S1.raw_equiv_threshold(l)
            sm["auc_row_level"] = auc(te["label"].to_numpy(), raws[l.name])
            sm["per_drive_clean_fa"] = W.per_drive_fa(te, flags[l.name])
            pd_fa = list(sm["per_drive_clean_fa"].values())
            sm["worst_drive_fa"], sm["n_drives_fa_gt_3pct"] = float(max(pd_fa)), int(sum(v > 0.03 for v in pd_fa))
            per[l.name] = sm
        res["calibration"][scheme] = {"per_layer": per}
        s_names = names
        runs = {"S7_stack": s_names,
                "S7_stack_plus_l3": s_names + [l3.name],
                "S7_stack_plus_l4": s_names + [l4.name],
                "S7_stack_plus_l3_l4": s_names + [l3.name, l4.name],
                "S7_l3_alone": [l3.name],
                "S7_l4_alone": [l4.name],
                "S7_l3_plus_l4": [l3.name, l4.name],
                "S7_stack_plus_l4_nopos": s_names + [l4n.name],
                "S7_stack_plus_l4_all_attacks": s_names + [l4a.name],
                "S7_stack_plus_l3_l4_all_attacks": s_names + [l3.name, l4a.name]}
        harness = {}
        for nm, ns in runs.items():
            h = evaluate_domain(f"{nm}_{scheme}", S2.subset(ESv, ns), S2.subset(ESt, ns), wp="WP1", budget=BUDGET, method="auto", out_dir=OUT)
            harness[nm] = {"layers": h["layers"], "combined": h["combined"], "ablation": h["ablation"]}
            log(scheme, nm, "AUC", round(h["combined"]["auc"], 4), "FA", round(h["combined"]["false_alarm_rate"], 4), "det", round(h["combined"]["detection"], 4))
        res["calibration"][scheme]["harness"] = harness
        if scheme == "lodo":
            raw_thr = {"l4": L.S1.raw_equiv_threshold(l4), "l4_nopos": L.S1.raw_equiv_threshold(l4n), "l4_all": L.S1.raw_equiv_threshold(l4a)}
    res["raw_thresholds_lodo"] = raw_thr
    # ---------------- leakage control: shuffled labels ----------------
    F = W.c2_frame(dev)
    y = dev["label"].to_numpy()
    part = dev["part"].to_numpy()
    mask = W.l4_rows(dev, W.V2_ATTACKS)
    ctrl = W.l4_fit(F, y, part == "train", part == "val", learned.C2_ALL, mask, shuffle_seed=12345)
    ps = ctrl.score(Ft)
    sv = ctrl.score(F[part == "val"])
    nv = (dev.loc[part == "val", "label"] == 0).to_numpy()
    thr = budget_threshold(sv[nv], BUDGET)
    flag = ps >= thr
    yt = te["label"].to_numpy()
    res["shuffled_label_control"] = {"seed": 12345, "auc_test_rows": auc(yt, ps), "threshold_val_1pct": thr, "fa_clean_runs": float(flag[(te["attack"] == "none").to_numpy()].mean()),
                                     "row_detection": {a: float(flag[(te["attack"] == a).to_numpy() & (yt == 1)].mean()) for a in L.ATT},
                                     "run_detected": L.summarize(te, flag)["run_detected"], "val_f1": ctrl.info["val_f1_macro"]}
    log("control AUC", res["shuffled_label_control"]["auc_test_rows"], "FA", res["shuffled_label_control"]["fa_clean_runs"])
    res["importance_final"] = {k: v.importance() for k, v in final["l4"].items()}
    (OUT / "S7_kitti.json").write_text(json.dumps(res, indent=1, default=float))
    if not DRY:
        external(final, raw_thr)
    log("done")


def run_scores(models, df):
    F = learned.c2_features(df)
    return {k: m.score(F) for k, m in models.items()}


def ext_eval(df, score, thr_kitti, label="avgps"):
    """Row-level: AUC, FA / detection at the KITTI threshold (pure transfer) and at 1% of the target's own normal rows."""
    y = df["label"].to_numpy()
    normal = y == 0
    out = {"auc": auc(y, score) if 0 < y.sum() < len(y) else None, "rows": int(len(y)), "normal_rows": int(normal.sum())}
    for nm, thr in (("kitti_threshold", thr_kitti), ("own_1pct_threshold", None)):
        t = thr if thr is not None else budget_threshold(score[normal], BUDGET)
        f = score >= t
        out[nm] = {"threshold": float(t), "fa": float(f[normal].mean()), "detection": float(f[~normal].mean()) if (~normal).any() else None}
    return out


def external(final, raw_thr):
    models = {"l4_c2": final["l4"]["l4_c2"], "l4_nopos": final["l4"]["l4_nopos"], "l4_all": final["l4"]["l4_all"]}
    thr = {"l4_c2": raw_thr["l4"], "l4_nopos": raw_thr["l4_nopos"], "l4_all": raw_thr["l4_all"]}
    res = {"note": "KITTI-trained C2 variants (final models, train drives) applied unchanged. kitti_threshold = LODO 1% raw-score threshold; "
                   "own_1pct_threshold = 1% of the target's normal rows (in-sample)."}
    # ---- AV-GPS (sessions; files 2-3 = test, val = 3 file-1 sessions) ----
    av = S.load_avgps()
    sc = run_scores(models, av)
    res["avgps"] = {"features_available": "pos_step, speed_gap (Velocity), heading_gap (Heading vs GPS course), dr_resid from Velocity + Heading: all present"}
    for part in ("test", "val", "train"):
        m = (av["part"] == part).to_numpy()
        sub = av[m]
        res["avgps"][part] = {k: ext_eval(sub, s[m], thr[k]) for k, s in sc.items()}
        res["avgps"][part]["sessions"] = int(sub["run"].nunique())
        res["avgps"][part]["spoof_rows"] = int(sub["label"].sum())
        res["avgps"][part]["median_speed_m_s"] = float(sub["odo_speed"].median())
    # target calibrated on val sessions, applied to test sessions
    mv, mt = (av["part"] == "val").to_numpy(), (av["part"] == "test").to_numpy()
    res["avgps"]["val_calibrated_on_test"] = {}
    for k, s in sc.items():
        tv = budget_threshold(s[mv & (av["label"] == 0).to_numpy()], BUDGET)
        f = s[mt] >= tv
        yy = av.loc[mt, "label"].to_numpy()
        res["avgps"]["val_calibrated_on_test"][k] = {"threshold": float(tv), "fa": float(f[yy == 0].mean()), "detection": float(f[yy == 1].mean())}
    # ---- UAV: no wheel odometry -> features speed_gap / dr_resid have no independent speed ----
    from gps import l1
    uav = l1.attach_uav_extras(S.load_uav())
    res["uav"] = {"features_available": "pos_step, heading_gap and still need only the GPS and the attitude; speed_gap, speed_gap_mean5 and dr_resid need an independent speed: "
                                         "a drone has no wheel odometry (odo_speed NaN), so L4 (C2) is NOT applicable to the UAV as trained. Proxy (diagnostic only): "
                                         "the receiver's own Doppler speed replaces the odometry (not independent: a Doppler-consistent spoofer controls it)."}
    prox = uav.copy()
    prox["odo_speed"] = prox["speed_gps"]
    sc = run_scores(models, prox)
    t = prox["t"].to_numpy()
    for k, s in sc.items():
        r = {}
        for name in S.UAV_FLIGHTS:
            m = (prox["run"] == f"uav/{name}").to_numpy()
            r[name] = {}
            for tn, tv in (("kitti_threshold", thr[k]), ("benign_1pct_threshold", budget_threshold(s[(prox["run"] == "uav/benign").to_numpy()], BUDGET))):
                a = s[m] >= tv
                tt = t[m]
                e = {"fixes": int(m.sum()), "alarm_rate": float(a.mean()), "threshold": float(tv)}
                if name == "spoofing":
                    pre, post = tt < S.UAV_SPOOF_ONSET_S, tt >= S2.UAV_FIRST_SPOOFED_FIX_S
                    hit = np.flatnonzero(a & post)
                    e.update({"alarm_rate_before_117s": float(a[pre].mean()), "alarm_rate_from_118s": float(a[post].mean()),
                              "first_alarm_after_118s": float(tt[hit[0]]) if len(hit) else None})
                r[name][tn] = e
        res["uav"][k] = r
    (OUT / "S7_external.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
