"""WP9 B5: detection-vs-false-alarm figures per domain from SAVED score files only (no scoring, no refit).

Purpose: one plain academic figure per domain (PNG) plus the plotted data (CSV). Every title names dataset, split and exposure.
Inputs: results/WP9/scores/B1..B4/*.npz|pkl, results/WP8/scores/S7, S8 (system K), thresholds from the approved test JSONs.
Outputs: results/WP9/B5/figures/fig_*.png and fig_*.csv, results/WP9/B5/figures/ops_sanity.json (operating points recomputed from the scores
versus the values stored in the approved JSONs; they must agree).
References: RULES.md section 5.5 (operating point), WP9 brief (H = 1% validation budget, S = validation-F1-optimal).
"""
import json
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_curve  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results/WP9/B5/figures")
os.makedirs(OUT, exist_ok=True)
GRID = np.logspace(-5, 0, 200)
COL = ["#1f4e79", "#c0392b", "#2e8b57", "#b8860b", "#7d3c98", "#5d6d7e", "#d35400", "#117a8b"]
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 110, "legend.fontsize": 7.5})
SANITY = {}


def J(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as fh:
        return json.load(fh)


def curve(y, s, w=None):
    fpr, tpr, _ = roc_curve(y, s, sample_weight=w)
    return fpr, tpr


def on_grid(fpr, tpr):
    return np.interp(GRID, fpr, tpr)


def op_point(y, s, thr, w=None):
    pos, neg = (y == 1), (y == 0)
    w = np.ones(len(y)) if w is None else w
    hit = s >= thr
    tpr = float((w[pos & hit]).sum() / w[pos].sum())
    fpr = float((w[neg & hit]).sum() / w[neg].sum())
    return fpr, tpr


class Fig:
    def __init__(self, name, title, xlabel="false-alarm rate on normal samples (log scale)", ylabel="detection rate (true-positive rate)", ncols=1, figsize=(6.4, 4.8)):
        self.name = name
        self.rows = []
        self.fig, axes = plt.subplots(1, ncols, figsize=figsize if ncols == 1 else (6.4 * ncols * 0.85, 4.8), squeeze=False)
        self.axes = axes[0]
        for ax in self.axes:
            ax.set_xscale("log")
            ax.set_xlim(1e-5, 1.0)
            ax.set_ylim(0, 1.02)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
        self.width = 88 if ncols == 1 else 150
        self.fig.suptitle(chr(10).join(textwrap.fill(t, self.width) for t in title.split(chr(10))), fontsize=8)
        self.i = 0

    def add(self, label, y, s, w=None, ax=0, color=None, ls="-", ops=()):
        fpr, tpr = curve(y, s, w)
        c = color or COL[self.i % len(COL)]
        self.i += 1
        a = self.axes[ax]
        a.plot(np.maximum(fpr, 1e-6), tpr, color=c, ls=ls, lw=1.4, label=label)
        g = on_grid(fpr, tpr)
        for x, t in zip(GRID, g):
            self.rows.append({"panel": ax, "curve": label, "kind": "curve", "fpr": float(x), "tpr": float(t)})
        for tag, thr in ops:
            f, t = op_point(y, s, thr, w)
            a.plot([max(f, 1e-6)], [t], marker="o" if tag == "H" else "s" if tag == "S" else "^", color=c, ms=6, mfc="white", mew=1.5)
            self.rows.append({"panel": ax, "curve": label, "kind": f"op_{tag}", "fpr": f, "tpr": t})
        return fpr, tpr

    def save(self, subtitle=None):
        for a in self.axes:
            a.legend(loc="lower right", frameon=False)
        if subtitle:
            self.fig.text(0.5, 0.005, textwrap.fill(subtitle, self.width + 10), ha="center", va="bottom", fontsize=7, color="#444444")
        self.fig.tight_layout(rect=(0, 0.07, 1, 0.9))
        self.fig.savefig(os.path.join(OUT, self.name + ".png"), dpi=140)
        plt.close(self.fig)
        pd.DataFrame(self.rows).to_csv(os.path.join(OUT, self.name + ".csv"), index=False)


def npz_obj(path, key):
    return np.load(os.path.join(ROOT, path), allow_pickle=True)[key].item()


def fig_can():
    f = Fig("fig_can_roc", "CAN, seen attack types, 1 s windows: Car-Hacking (block split), ROAD (capture split), D11 (capture split, 4 sets)\n"
                            "test scored once (B1); o = H (1% validation budget); dashed = D11 UNKNOWN vehicle (thresholds from the known vehicle)")
    ch = npz_obj("results/WP9/scores/B1/carhacking_test.npz", "W_rf_generic__test_blocks")
    thr = J("results/WP9/B1_carhacking_test.json")["models"]["W_rf_generic"]["thr_from_validation"]
    f.add("Car-Hacking, block split", (ch["y"] != 0).astype(int), ch["s"], ops=[("H", thr)])
    rd = npz_obj("results/WP9/scores/B1/road_test.npz", "Fb__test")
    thr = J("results/WP9/B1_road_test.json")["models"]["Fb"]["thr_from_validation"]
    f.add("ROAD, capture split", (rd["y"] != 0).astype(int), rd["s"], ops=[("H", thr)])
    for s_, m in ((1, "W_xgb_a_ids"), (2, "E"), (3, "F_noid"), (4, "E")):
        o = npz_obj(f"results/WP9/scores/B1/d11_set_0{s_}_test.npz", f"{m}__test_01")
        thr = J(f"results/WP9/B1_d11_set_0{s_}_test.json")["models"][m]["thr_from_validation"]
        f.add(f"D11 set_0{s_}, known vehicle", (o["y"] != 0).astype(int), o["s"], ops=[("H", thr)])
    o = npz_obj("results/WP9/scores/B1/d11_set_01_test.npz", "W_xgb_a_ids__test_02")
    f.add("D11 set_01, UNKNOWN vehicle", (o["y"] != 0).astype(int), o["s"], ls="--", color="#555555")
    f.save("Normal windows are the negatives. Small test groups (ROAD 9 captures): curves are step-like. Shuffled-label controls failed for ROAD / D11 (see report).")


def fig_network():
    f = Fig("fig_network_det_vs_fa", "Network, seen attack types, flow level, 5-tuple group split (G): CICIDS2017 orig / corrected, CSE-CIC-IDS2018 corrected\n"
                                     "test scored once (B2); score = 1 - P(BENIGN); CSE-CIC-IDS2018 benign flows weighted 10 (1-in-10 sample)")
    for tag, lab in (("D10o_G", "CICIDS2017 original labels"), ("D10e_G", "CICIDS2017 corrected labels"), ("D23x_G", "CSE-CIC-IDS2018 corrected")):
        z = np.load(os.path.join(ROOT, f"results/WP9/scores/B2/{tag}_test.npz"), allow_pickle=True)
        y, p = z["y"], z["proba"].astype(np.float32)
        ok = y >= 0
        yb = (y[ok] != 0).astype(int)
        w = np.where(yb == 0, 10.0, 1.0) if tag.startswith("D23") else None
        f.add(lab, yb, 1.0 - p[ok][:, 0], w=w)
    f.save("In-distribution (same campaigns on both sides); AUC ~1.0 is a known property of these datasets. Random-forest units fail the shuffled-label AUC rule.")


def fig_v2x():
    z = np.load(os.path.join(ROOT, "results/WP9/scores/B3/test_chosen.npz"))
    y, s, c, v3 = z["y"], z["s"], z["c"], z["v3ref"]
    d = J("results/WP9/B3_test.json")
    thr = d["ops"]["H_budget1pct"]["thr"]
    f = Fig("fig_v2x_roc", "V2X, VeReMi Extension (one simulation), 1800 s time blocks, message level; test scored once (B3)\n"
                           "o = H (1% validation budget)")
    f.add("all 19 attack types vs genuine", (y != 0).astype(int), s, ops=[("H", thr)])
    dos = np.isin(y, [13, 14, 15, 18, 19]) | (y == 0)
    f.add("DoS family (natural prevalence)", (y[dos] != 0).astype(int), s[dos], ops=[("H", thr)])
    f.add("v3 L4 layer reused (scored rows only: unscored = 0)", (y != 0).astype(int), v3, ls="--", color="#555555")
    f.save("Genuine messages are the negatives. Failed controls: sender permutation, proxy-only (see report). Single simulation, single map.")
    SANITY["v2x_H"] = dict(zip(("fpr", "tpr"), op_point((y != 0).astype(int), s, thr)))
    SANITY["v2x_H"]["json_fpr"] = d["ops"]["H_budget1pct"]["point"]["fpr"]
    SANITY["v2x_H"]["json_recall"] = d["ops"]["H_budget1pct"]["point"]["binary.recall"]


def fig_gps():
    z = np.load(os.path.join(ROOT, "results/WP9/scores/B4/gps_test_caseI.npz"), allow_pickle=True)
    z2 = np.load(os.path.join(ROOT, "results/WP9/scores/B4/gps_test_caseII.npz"), allow_pickle=True)
    zv = np.load(os.path.join(ROOT, "results/WP9/scores/B4/gps_v3_test.npz"), allow_pickle=True)
    d = J("results/WP9/B4_gps_test.json")
    f = Fig("fig_gps_roc", "GPS, AV-GPS-Dataset (artefact-prone: copies, label predictable from vehicle state), session split; test scored once (B4)\n"
                           "left: Case I (train file 1, test file 2, 5 sessions); right: Case II (train file 2, test 25 file-1 sessions); o = H, square = S", ncols=2)
    ops = lambda v: [("H", d["case_I"][v]["H"]["thr"]), ("S", d["case_I"][v]["S"]["thr"])]  # noqa: E731
    f.add("F_full (all fields), supervised", z["y"], z["F_full"], ax=0, ops=ops("F_full"))
    f.add("F_pos (GPS-only)", z["y"], z["F_pos"], ax=0, ops=ops("F_pos"))
    f.add("F_kin_noVS (GPS vs odometry)", z["y"], z["F_kin_noVS"], ax=0, ops=ops("F_kin_noVS"))
    f.add("v3 label-free layers", zv["y"], zv["score"], ax=0, ls="--", color="#555555")
    f.add("F_full (all fields)", z2["y"], z2["F_full"], ax=1)
    f.add("F_kin", z2["y"], z2["F_kin"], ax=1)
    f.add("F_pos", z2["y"], z2["F_pos"], ax=1)
    for a, t in zip(f.axes, ("Case I (same day, other session set)", "Case II (other day: does not transfer)")):
        a.set_title(t, fontsize=8)
    f.save("Normal sessions are the negatives; 5 / 25 sessions only (intervals in the report are wide). Row-shuffle band control failed as written.")
    SANITY["gps_FfullH"] = dict(zip(("fpr", "tpr"), op_point(z["y"], z["F_full"], d["case_I"]["F_full"]["H"]["thr"])))
    SANITY["gps_FfullH"]["json_fpr"] = d["case_I"]["F_full"]["H"]["fpr"]
    SANITY["gps_FfullH"]["json_recall"] = d["case_I"]["F_full"]["H"]["recall"]


def fig_lidar():
    z = np.load(os.path.join(ROOT, "results/WP9/scores/B4/lidar_test.npz"), allow_pickle=True)
    df = pd.DataFrame({"drive": z["drive"], "i": z["i"], "attack": z["attack"], "sup": z["supervised"], "phys": z["supervised_phys_only"]})
    v = pd.read_pickle(os.path.join(ROOT, "results/WP9/scores/B4/lidar_v31_scores.pkl"))[["drive", "i", "attack", "score"]].rename(columns={"score": "v31"})
    df = df.merge(v, on=["drive", "i", "attack"], how="left")
    d = J("results/WP9/B4_lidar_test.json")
    naive = ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
    phys = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far"]
    f = Fig("fig_lidar_roc", "LiDAR, KITTI raw, 7 test drives, scan level, generated attacks seen in training; test scored once (B4)\n"
                             "left: supervised static 211-column model; right: v3.1 (leave-one-drive-out scores, tuned on these drives); o = 10% operating point", ncols=2)
    clean = df[df.attack == "clean"]
    for ax, col, name in ((0, "sup", "supervised"), (1, "v31", "v31")):
        thr10 = d["detectors"]["supervised" if col == "sup" else "v31"]["ops"]["fpr10"]["thr"]
        for lab, kinds, c, ls in (("NAIVE-ADD (box cloud + multi-return add)", naive, COL[0], "-"), ("PHYSICAL phantoms (single return)", phys, COL[1], "-"),
                                  ("IntensitySpoof", ["IntensitySpoof"], COL[2], "-"), ("PointDrop", ["PointDrop"], COL[3], "-")):
            a = df[df.attack.isin(kinds)]
            sub = pd.concat([clean, a])
            f.add(lab, (sub.attack != "clean").astype(int).values, sub[col].values, ax=ax, color=c, ls=ls, ops=[("H", thr10)])
    f.axes[0].set_title("supervised (static model)", fontsize=8)
    f.axes[1].set_title("v3.1 (LODO scores)", fontsize=8)
    for a in f.axes:
        a.axvline(0.1, color="#999999", lw=0.8, ls=":")
    f.save("Clean scans are the negatives. Marker = test point at the validation-set threshold for 10% FPR (dotted line = 10%). Not comparable to object-level / nuScenes bars.")
    sub = df[df.attack.isin(naive)]
    thr = d["detectors"]["supervised"]["ops"]["fpr10"]["thr"]
    SANITY["lidar_naive_tpr10"] = {"from_scores": float((sub["sup"] >= thr).mean()), "json": d["detectors"]["supervised"]["ops"]["fpr10"]["kinds"]["NAIVE"]["tpr"],
                                   "fpr_from_scores": float((clean["sup"] >= thr).mean()), "json_fpr": d["detectors"]["supervised"]["ops"]["fpr10"]["fpr"]["fpr"]}


def fig_h31():
    base = "results/WP8/scores/"
    runs = [("v3 frozen (M4 scoring)", base + "S7/system_K_%s_h31_v3.npz", COL[5], "-"),
            ("v3.1 frozen (M4 scoring)", base + "S7/system_K_%s_h31_v31.npz", COL[0], "-"),
            ("v3.1 + S8 gate (H31 exposure 2, NOT fresh)", base + "S8/system_K_%s_s8_h31_v31_gated.npz", COL[1], "--")]
    f = Fig("fig_h31_zeroshot", "Zero-shot / fresh track: system K (KITTI H31 vehicle block + re-used CAN / network / V2X streams = partially fresh)\n"
                                "tick-level score; negatives = ticks of 16 clean timelines; positives = attack-labelled ticks of 2137 composites; o = frozen alarm rule",
            xlabel="clean tick false-alarm rate (log scale)", ylabel="attack-labelled tick detection rate")
    for lab, pat, c, ls in runs:
        cl = np.load(os.path.join(ROOT, pat % "clean"))
        at = np.load(os.path.join(ROOT, pat % "attack"))
        yy = np.concatenate([np.zeros(len(cl["score"]), int), np.ones(int(at["label"].sum()), int)])
        ss = np.concatenate([cl["score"], at["score"][at["label"]]])
        fpr, tpr = f.add(lab, yy, ss, color=c, ls=ls)
        fa = float(cl["alarm"].mean())
        det = float(at["alarm"][at["label"]].mean())
        f.axes[0].plot([max(fa, 1e-6)], [det], marker="o", color=c, ms=6, mfc="white", mew=1.5)
        f.rows.append({"panel": 0, "curve": lab, "kind": "op_frozen_rule", "fpr": fa, "tpr": det})
    f.save("Operating points: frozen alarm rules (K clean tick FA bound 3%). Drive 0093 (defective navigation record) causes the false-alarm flood in v3 / v3.1.")


if __name__ == "__main__":
    fig_can()
    fig_network()
    fig_v2x()
    fig_gps()
    fig_lidar()
    fig_h31()
    with open(os.path.join(OUT, "ops_sanity.json"), "w", encoding="utf-8") as fh:
        json.dump(SANITY, fh, indent=1)
    print(json.dumps(SANITY, indent=1))
