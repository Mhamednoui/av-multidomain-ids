"""WP1 S8 check of the one fitted piece that is not nested elsewhere: the EKF / DR-branch receiver noise model of S3 (Gauss-Markov phi, sigma
of the added receiver error, and q_acc by the S3 criterion 'mean NIS / mean dim closest to 1' on clean runs; no attack label involved).
S3 fitted them on the 13 train drives; here they are re-estimated inside each of the 15 LODO folds from the clean runs of the other dev
drives (sufficient statistics per drive), on DEV rows only. Reported: range of phi / sigma, q_acc selected per fold (grid of S3), and the
drives where q_acc differs from the S3 value. If nothing changes, nesting the noise model changes no downstream number.
Outputs: results/WP1/S8_noise_nested.json. Run from codes_v3/: python -u -W ignore tools/WP1_S8_noise.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
from gps import ekf
from gps.ekf import EKFConfig

QS = [0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2]


def main():
    kx = L.kitti_stream()
    dev = kx[kx["part"].isin(L.DEV_PARTS) & (kx["attack"] == "none")]
    drives = sorted(dev["drive"].unique())
    gm = L.TUNE["kitti_gm_estimate_train"]
    stats = {}                                   # per drive: GM sufficient statistics and NIS sums per q
    for d in drives:
        g = dev[dev["drive"] == d]
        num = den = ss = n = 0.0
        for _, r in g.groupby("run", sort=False):
            e = np.c_[r["x"] - r["x_true"], r["y"] - r["y_true"]]
            ss += (e ** 2).mean() * len(e); n += len(e)
            num += (e[1:] * e[:-1]).sum(); den += (e[:-1] ** 2).sum()
        st = {"num": num, "den": den, "ss": ss, "n": n, "nis": {}, "dim": {}}
        for q in QS:
            cfg = EKFConfig(gm_phi=gm["phi"], gm_sigma=gm["sigma"], q_acc=q)
            r = ekf.run_filter_all(g, cfg)
            ok = ~np.isnan(r["nis"].to_numpy())
            st["nis"][q], st["dim"][q] = float(r["nis"].to_numpy()[ok].sum()), float(r["dim"].to_numpy()[ok].sum())
        stats[d] = st
        print("drive", d, flush=True)
    res = {"s3_values": {"phi": gm["phi"], "sigma": gm["sigma"], "q_acc": L.TUNE["kitti_q_acc"]}, "folds": {}}
    for d in drives:
        o = [x for x in drives if x != d]
        num, den = sum(stats[x]["num"] for x in o), sum(stats[x]["den"] for x in o)
        sig = np.sqrt(sum(stats[x]["ss"] for x in o) / sum(stats[x]["n"] for x in o))
        ratio = {q: sum(stats[x]["nis"][q] for x in o) / sum(stats[x]["dim"][q] for x in o) for q in QS}
        qbest = min(QS, key=lambda q: abs(ratio[q] - 1.0))
        res["folds"][d] = {"phi": num / den, "sigma": float(sig), "q_acc": qbest, "ratio_at_selected": ratio[qbest]}
    ph = [v["phi"] for v in res["folds"].values()]
    sg = [v["sigma"] for v in res["folds"].values()]
    qs = [v["q_acc"] for v in res["folds"].values()]
    res["summary"] = {"phi_range": [min(ph), max(ph)], "sigma_range": [min(sg), max(sg)], "q_acc_selected_counts": {str(q): qs.count(q) for q in sorted(set(qs))},
                      "folds_with_q_different_from_s3": [d for d, v in res["folds"].items() if v["q_acc"] != L.TUNE["kitti_q_acc"]],
                      "max_abs_phi_diff_vs_s3": float(max(abs(p - gm["phi"]) for p in ph)), "max_abs_sigma_diff_vs_s3": float(max(abs(s - gm["sigma"]) for s in sg))}
    print(json.dumps(res["summary"], indent=1))
    (L.OUT / "S8_noise_nested.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
