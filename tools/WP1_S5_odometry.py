"""WP1 S5 step 2: validate the LiDAR odometry against the OXTS ground truth (clean RTK pose), fit the MotionEstimate sigma.
Metrics (planar, ground truth = OXTS lat / lon / yaw interpolated at the scan times; no lever arm correction):
  - KITTI-benchmark style: for every start scan and segment length L in (10, 25, 50, 100) m, relative-pose error between the
    LiDAR and the GT motion over the segment: translation error / L (%) and rotation error / L (deg/m); averaged per drive and pooled;
  - 1 s windows (what the detector uses): body-frame displacement error (m), speed error (m/s), yaw-change error (deg), for windows with GT speed > 1 m/s;
  - sigma model sqrt(sigma0^2 + (rel * speed)^2) fitted on the 16 train+val drives (variance of the speed error in speed bins, least squares),
    coverage |error| <= 2 sigma on dev and test drives.
Outputs: results/WP1/S5_odometry.json. Run from codes_v3/: python -u -W ignore tools/WP1_S5_odometry.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S5_odom_run as R
from common.config import results_dir
from gps import lidar_odom as LO
from gps import stream as S

OUT = results_dir("WP1")
LENGTHS = (10, 25, 50, 100)
SPEED_BINS = (1, 3, 6, 10, 15, 30)


def gt_poses(d, tp):
    ox = S.load_oxts(d)
    north = (ox["lat"] - ox["lat"][0]) * S.M_PER_DEG
    east = (ox["lon"] - ox["lon"][0]) * S.M_PER_DEG * np.cos(np.radians(ox["lat"][0]))
    yaw = np.unwrap(ox["yaw"])
    return np.c_[np.interp(tp, ox["t"], east), np.interp(tp, ox["t"], north), np.interp(tp, ox["t"], yaw)]


def rel_pose(Pa, Pb):
    f, l, dy = LO.body_displacement(Pa, Pb)
    return np.c_[f, l, dy]


def segment_errors(P, G):
    """KITTI-style (translation error ratio, rotation error rad/m) for all (start, length) pairs of one drive."""
    cum = np.r_[0, np.cumsum(np.hypot(*np.diff(G[:, :2], axis=0).T))]
    te, re, ln = [], [], []
    for L in LENGTHS:
        for i in range(len(G)):
            j = np.searchsorted(cum, cum[i] + L)
            if j >= len(G):
                break
            a, b = rel_pose(G[[i]], G[[j]])[0], rel_pose(P[[i]], P[[j]])[0]
            # error pose = inv(GT rel) * LiDAR rel, planar
            dth = b[2] - a[2]
            c, s = np.cos(a[2]), np.sin(a[2])
            d = np.array([b[0] - a[0], b[1] - a[1]])
            e = np.array([c * d[0] + s * d[1], -s * d[0] + c * d[1]])
            te.append(np.hypot(*e) / L); re.append(abs((dth + np.pi) % (2 * np.pi) - np.pi) / L); ln.append(L)
    return np.array(te), np.array(re), np.array(ln)


def window_errors(P, G, tp, w=1.0):
    """1 s windows starting at every scan: GT speed, body displacement error, speed error, yaw-change error."""
    t1 = tp + w
    keep = t1 <= tp[-1]
    Pa, Pb = LO.pose_at(tp[keep], P, tp), LO.pose_at(t1[keep], P, tp)
    Ga, Gb = LO.pose_at(tp[keep], G, tp), LO.pose_at(t1[keep], G, tp)
    pf, pl, py = LO.body_displacement(Pa, Pb)
    gf, gl, gy = LO.body_displacement(Ga, Gb)
    return {"gt_speed": np.hypot(gf, gl) / w, "disp_err": np.hypot(pf - gf, pl - gl), "speed_err": np.hypot(pf, pl) / w - np.hypot(gf, gl) / w,
            "yaw_err_deg": np.degrees(py - gy)}


def fit_sigma(v, err):
    """sigma^2(v) = s0^2 + (rel v)^2 by least squares on the robust variance (MAD) of the speed error in speed bins."""
    xs, ys, ws = [], [], []
    for lo, hi in zip(SPEED_BINS[:-1], SPEED_BINS[1:]):
        m = (v >= lo) & (v < hi)
        if m.sum() < 30:
            continue
        e = err[m]
        sg = 1.4826 * np.median(np.abs(e - np.median(e)))
        xs.append(np.mean(v[m]) ** 2); ys.append(sg ** 2); ws.append(m.sum())
    A = np.c_[np.ones(len(xs)), xs]
    w = np.sqrt(np.array(ws, float))
    coef, *_ = np.linalg.lstsq(A * w[:, None], np.array(ys) * w, rcond=None)
    s0, rel = float(np.sqrt(max(coef[0], 1e-6))), float(np.sqrt(max(coef[1], 1e-8)))
    return s0, rel


def main():
    drives = sorted(S.SCENE)
    per, pool = {}, {"dev": {"te": [], "re": [], "win": []}, "test": {"te": [], "re": [], "win": []}}
    for d in drives:
        tp, rel, q = R.load_cached(d)
        P = LO.chain_poses(rel)
        G = gt_poses(d, tp)
        te, re, ln = segment_errors(P, G)
        w = window_errors(P, G, tp)
        mov = w["gt_speed"] > 1.0
        part = S.part_of(d)
        per[d] = {"part": part, "scans": int(len(tp)), "path_m": float(np.hypot(*np.diff(G[:, :2], axis=0).T).sum()),
                  "segments": int(len(te)),
                  "translation_error_pct": float(100 * te.mean()) if len(te) else None,
                  "rotation_error_deg_per_m": float(np.degrees(re.mean())) if len(re) else None,
                  "median_1s_disp_err_m_moving": float(np.median(w["disp_err"][mov])) if mov.any() else None,
                  "median_1s_speed_rel_err_pct_moving": float(100 * np.median(np.abs(w["speed_err"][mov]) / w["gt_speed"][mov])) if mov.any() else None,
                  "icp_fallback_share": float((q[:, 4] > 0).mean()), "icp_mean_inlier_frac": float(q[:, 1].mean()),
                  "icp_mean_iters": float(q[:, 2].mean())}
        key = "test" if part == "test" else "dev"
        pool[key]["te"].append(te); pool[key]["re"].append(re); pool[key]["win"].append(w)
        print(d, part, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in per[d].items()}, flush=True)
    res = {"drives": per, "lengths_m": LENGTHS, "no_velodyne": [d for d in drives if not R.has_velodyne(d)]}
    wins = {}
    for key in ("dev", "test"):
        te, re = np.concatenate(pool[key]["te"]), np.concatenate(pool[key]["re"])
        W = {k: np.concatenate([w[k] for w in pool[key]["win"]]) for k in pool[key]["win"][0]}
        mov = W["gt_speed"] > 1.0
        wins[key] = (W, mov)
        res[key] = {"segments": int(len(te)), "translation_error_pct": float(100 * te.mean()), "rotation_error_deg_per_m": float(np.degrees(re.mean())),
                    "median_1s_disp_err_m_moving": float(np.median(W["disp_err"][mov])), "p95_1s_disp_err_m_moving": float(np.percentile(W["disp_err"][mov], 95)),
                    "median_1s_speed_err_m_s_moving": float(np.median(np.abs(W["speed_err"][mov]))),
                    "median_1s_yaw_err_deg_moving": float(np.median(np.abs(W["yaw_err_deg"][mov]))),
                    "windows_moving": int(mov.sum())}
    W, mov = wins["dev"]
    s0, rel = fit_sigma(W["gt_speed"][mov], W["speed_err"][mov])
    res["sigma_model"] = {"sigma0_m_s": s0, "rel": rel, "fitted_on": "16 train+val drives, 1 s windows, GT speed > 1 m/s"}
    for key in ("dev", "test"):
        W, mov = wins[key]
        sg = np.array([LO.lidar_motion_sigma(v, True, s0, rel) for v in W["gt_speed"][mov]])
        res[key]["sigma_coverage_2sigma"] = float(np.mean(np.abs(W["speed_err"][mov]) <= 2 * sg))
    # acceptance numbers (C2, C3)
    res["acceptance"] = {
        "C2_translation_le_2pct_dev": res["dev"]["translation_error_pct"] <= 2.0,
        "C2_rotation_le_0.02_deg_per_m_dev": res["dev"]["rotation_error_deg_per_m"] <= 0.02,
        "C2_median_1s_disp_err_le_0.10m_dev": res["dev"]["median_1s_disp_err_m_moving"] <= 0.10,
        "C3_coverage_ge_90pct_test": res["test"]["sigma_coverage_2sigma"] >= 0.90}
    (OUT / "S5_odometry.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k] for k in ("dev", "test", "sigma_model", "acceptance")}, indent=1, default=float))


if __name__ == "__main__":
    main()
