"""WP6 S3 (VALIDATION ONLY): the two allowed additions to the frozen S2b cross-domain layer, judged on the S2b leave-one-group-out dev folds.
  KITTI: LiDAR ICP quality flag -> the z of every edge with the LiDAR witness is divided by 3 in seconds whose scan pairs failed the ICP quality
         test (gps.lidar_odom lid_ok == 0; same x3 sigma inflation as gps.lidar_odom.lidar_motion_sigma).
  comma: CAN glitch filter -> an edge with the CAN or wheel message and |z| > 20 is a sensor fault, not an attack: that edge is unobserved that second.
Choice rule (S2b, notes "S3 start"): FA rows <= 1.5% then max selection detection; base = S2b frozen inst |z|.
Run: python -u -W ignore tools/WP6_S3_crosschoice.py     Outputs: results/WP6/s3_crosschoice.json
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import results_dir  # noqa: E402
from gps import lidar_odom as LO  # noqa: E402
import WP6_S1_kitti as S1  # noqa: E402
import WP6_S2b_eval as B  # noqa: E402

OUT = results_dir("WP6")
INST = {"name": "inst", "k": "inst", "tb": None}
GLITCH_Z = 20.0
QUALITY_FACTOR = 3.0


def lid_ok_table(drives):
    """(drive, phase) -> dict t -> lid_ok (bool) on the clean r0 run grid of that phase."""
    kx = S1.kitti_stream()
    out = {}
    for d in drives:
        tp, P, qual = LO.load_odometry(d)
        kd = kx[kx["drive"] == d]
        for run, g in kd[kd["run"].str.endswith("/r0")].groupby("run"):
            g = g.sort_values("t").reset_index(drop=True)
            ok = np.asarray(LO.run_features(g, tp, P, qual, windows=(1,))["lid_ok"]) > 0
            out[(d, int(run.split("/")[1][1:]))] = dict(zip(np.round(g["t"].to_numpy(float), 3), ok))
    return out


def apply_quality(edges, runs, table):
    lid = [j for j, e in enumerate(edges) if "lidar" in (e.a, e.b)]
    n_bad = n = 0
    for d, rs in runs.items():
        for r in rs:
            ph = int(r["run"].split("/")[1][1:])
            m = table.get((d, ph), {})
            bad = np.array([not m.get(round(float(t), 3), True) for t in r["t"]])
            r["Z"] = r["Z"].copy()
            r["Z"][np.ix_(bad, lid)] /= QUALITY_FACTOR
            n_bad += int(bad.sum())
            n += len(bad)
    return n_bad / max(n, 1)


def glitch(Z, cols):
    Z = Z.copy()
    sub = Z[:, cols]
    sub[np.abs(sub) > GLITCH_Z] = np.nan
    Z[:, cols] = sub
    return Z


def apply_glitch(edges, data):
    cols = [j for j, e in enumerate(edges) if {"can", "wheel"} & {e.a, e.b}]
    n_f = n = 0
    for d in data.values():
        before = np.isfinite(d["Z"][:, cols]).sum()
        d["Z"] = glitch(d["Z"], cols)
        n_f += int(before - np.isfinite(d["Z"][:, cols]).sum())
        n += int(before)
        for ep in d["episodes"]:
            ep["Z"] = glitch(ep["Z"], cols)
    return n_f / max(n, 1)


def main():
    res = {"note": "S3 val-only cross additions, DEV groups (train + val), leave-one-group-out as S2b; no test data", "rule": "FA <= 1.5% then max selection detection"}
    ke, kr = B.kitti_runs()
    s0 = B.summarise(*B.eval_kitti(ke, kr, INST), "kitti")
    res["kitti"] = {"base_inst": s0}
    frac = apply_quality(ke, kr, lid_ok_table(sorted(kr)))
    s1 = B.summarise(*B.eval_kitti(ke, kr, INST), "kitti")
    res["kitti"]["inst_quality_flag"] = s1
    res["kitti"]["poor_quality_fraction"] = frac
    ce, cd, cls = B.comma_data()
    c0 = B.summarise(*B.eval_comma(ce, cd, INST), "comma")
    res["comma"] = {"base_inst": c0}
    gf = apply_glitch(ce, cd)
    c1 = B.summarise(*B.eval_comma(ce, cd, INST), "comma")
    res["comma"]["inst_glitch_filter"] = c1
    res["comma"]["filtered_fraction"] = gf
    choice = {}
    for ds in ("kitti", "comma"):
        cands = {k: v for k, v in res[ds].items() if isinstance(v, dict)}
        ok = [k for k, v in cands.items() if v["fa_rows"] <= 0.015]
        pool = ok if ok else [min(cands, key=lambda k: cands[k]["fa_rows"])]
        choice[ds] = max(pool, key=lambda k: cands[k]["selection_mean_detection"])
        for k, v in cands.items():
            print(ds, k, "FA", round(v["fa_rows"], 4), "worst", v["worst_group"][0][-8:], round(v["worst_group"][1], 3), "sel", round(v["selection_mean_detection"], 3),
                  "mean", round(v["mean_detection_single"], 3), {a: round(x, 3) for a, x in v["pooled_single"].items()}, flush=True)
    res["choice"] = choice
    (OUT / "s3_crosschoice.json").write_text(json.dumps(res, indent=1, default=str))
    print(choice, "poor-quality fraction", round(frac, 4), "glitch-filtered fraction", round(gf, 5))


if __name__ == "__main__":
    main()
