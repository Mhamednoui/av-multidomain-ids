"""WP1 S8 freeze: fit the deployable GPSDomain (gps/domain.py) on the 15 development drives with runs, save it to results/WP1/frozen_gps/, reload it,
and check that the reloaded object reproduces (a) the matrix-pipeline statistic and alarms of tools/WP1_S8_test.py on the test rows to 1e-9,
(b) its own Evidence path. Writes example Evidence / MotionEstimate records for one test run (WP6 fixture).
This is NOT a new test evaluation: it re-scores the already evaluated test rows with the saved object. Run from codes_v3/:
python -u -W ignore tools/WP1_S8_freeze.py
"""
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S8_lib as W
import WP1_S4_lib as L
from gps import domain
from gps import lidar_odom as LO
from gps import stack as ST

FROZEN = L.OUT / "frozen_gps"
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def parse_cus(name):
    head, k = name.split("|")[0], float(name.split("|")[1].split("=")[1])
    return {"stat": head.split("_")[2], "kappa": k}


def main():
    dj = json.loads((L.OUT / "S8_dev.json").read_text())
    sel = dj["cusum_selection"]["full_dev"]
    assert sel["dr"] == "cusum_dr_nis|k=2.0|scale=learn|freeze=self8+nis"          # default_config encodes exactly this DR configuration
    cfg = domain.default_config(L.TUNE, parse_cus(sel["ekf"]), parse_cus(sel["dr"]))
    kx = L.kitti_stream()
    kx = domain.prepare(kx, lidar=True)
    dev, test = kx[kx["part"].isin(L.DEV_PARTS)], kx[kx["part"] == "test"]
    log("rows dev", len(dev), "test", len(test))
    d = domain.GPSDomain(cfg, lidar=True).fit(dev)
    d.save(FROZEN)
    log("fitted + saved", FROZEN)
    d2 = domain.GPSDomain.load(FROZEN)
    S_test, sc_test, al_test = d2.score_arrays(test)
    log("scored test with the reloaded object")
    # matrix pipeline (tools/WP1_S8_test.py)
    raw = W.load_raw()
    devr, tr = raw[raw["part"].isin(W.DEV_PARTS)], raw[raw["part"] == "test"]
    ri = ST.RunIndex(devr)
    F = W.FoldState(devr, ri, sorted(devr["drive"].unique()), ST.DEFAULT_LAYERS, W.candidates(devr), sel=sel)
    _, cal_t, _ = F.apply(tr)
    names = sorted(ST.DEFAULT_LAYERS)
    X_dev = F.matrix(names)
    unseen = ((devr["attack"].isin(["doppler_spoof", "meaconing"])) & (devr["label"] == 1)).to_numpy()
    c = ST.MatrixCombiner(method="noisy_or_log").fit_matrix(names, X_dev[~unseen], devr["label"].to_numpy()[~unseen], devr["drive"].to_numpy()[~unseen])
    S_mat = c.score_matrix(ST.stack_matrix(cal_t, names))
    f_mat = S_mat >= c.threshold
    assert (test.index == tr.index).all()
    res = {"max_abs_diff_statistic": float(np.abs(S_test - S_mat).max()), "alarm_disagreements": int((al_test != f_mat).sum()), "n_test_rows": int(len(test)),
           "alarm_rate_test_normal_rows": float(al_test[test["label"].to_numpy() == 0].mean()), "threshold_statistic_matrix": float(c.threshold),
           "comb_threshold_calibrated": float(d2.comb_threshold)}
    log("check vs matrix pipeline", res)
    assert res["max_abs_diff_statistic"] < 1e-9 and res["alarm_disagreements"] == 0
    # Evidence path on one doppler_spoof run and one jump run of the first test drive
    runs = []
    for a in ("doppler_spoof", "jump"):
        runs.append(test[(test["attack"] == a)]["run"].iloc[0])
    sub = test[test["run"].isin(runs)]
    ev, per = d2.score(sub, with_layers=True)
    idx = np.flatnonzero(test["run"].isin(runs).to_numpy())
    res["evidence_path_max_abs_score_diff"] = float(np.abs(np.array([e.score for e in ev]) - sc_test[idx]).max())
    res["evidence_path_alarm_disagreements"] = int((np.array([e.alarm for e in ev]) != al_test[idx]).sum())
    assert res["evidence_path_max_abs_score_diff"] < 1e-12 and res["evidence_path_alarm_disagreements"] == 0
    # fixtures for WP6
    first = sub[sub["run"] == runs[0]]
    k = np.flatnonzero((sub["run"] == runs[0]).to_numpy())
    (FROZEN / "example_evidence_doppler_spoof_run.json").write_text(json.dumps(
        {"run": runs[0], "onset_index": int(first["onset"].iloc[0]), "note": "combined Evidence of one test run (as Evidence.to_dict) + the per-layer scores in details",
         "evidence": [ev[i].to_dict() for i in k]}, indent=1, default=float))
    me = domain.gps_motion_estimates(first)
    (FROZEN / "example_gps_motion_estimates.json").write_text(json.dumps(
        {"run": runs[0], "frame": "displacement = (forward, left) metres over the last second in the body frame (compass heading rotates the reported position change); speed = |displacement| / dt; sigma = 1-sigma of the speed in m/s",
         "estimates": [{"t": m.t, "source": m.source, "speed": m.speed, "yaw_rate": m.yaw_rate, "displacement": list(m.displacement), "sigma": m.sigma} for m in me]}, indent=1))
    res["config"] = cfg
    res["files"] = sorted(p.name for p in FROZEN.iterdir())
    res["size_bytes"] = {p.name: p.stat().st_size for p in FROZEN.iterdir()}
    (L.OUT / "S8_freeze.json").write_text(json.dumps(res, indent=1, default=float))
    log("done", res["files"], res["size_bytes"])


if __name__ == "__main__":
    main()
