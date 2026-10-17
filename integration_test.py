"""
Full-System Integration Test
============================
Draws 1000 random samples from every domain dataset, feeds each to its
domain runner, then to the fusion engine, and prints a detailed results table.

Output:
  - Console: summary table per domain + fusion confusion matrix
  - integration_results.csv  -- row-per-sample full results
  - integration_report.png   -- visual summary (4 domain bars + fusion heatmap)

Run with:
    python integration_test.py
"""
import json
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import confusion_matrix

CODES = Path(__file__).parent
sys.path.insert(0, str(CODES))

from network.network_runner           import NetworkDetector
from can.can_runner                   import CANDetector
from gps.gps_runner                   import GPSDetector
from lidar.lidar_runner               import LiDARDetector
from unsupervised.unsupervised_runner import ZeroDayDetector, _probs_vec
from fusion.fusion_engine             import FusionEngine

DATA = CODES / "data"
RNG  = np.random.default_rng(2024)
N    = 1000   # samples per domain


# =============================================================================
#  SAMPLE LOADERS
# =============================================================================

def load_network_samples(n):
    feats = json.load(open(CODES / "network" / "network_features.json"))
    df = pd.read_csv(DATA / "CICIDS2017_sample_km_test.csv")
    df = df.replace([np.inf, -np.inf], 0).fillna(0)
    sampled = (df.groupby("Label", group_keys=False)
                 .apply(lambda g: g.sample(
                     min(len(g), max(1, int(n * len(g) / len(df)))),
                     random_state=42))
                 .sample(frac=1, random_state=42)
                 .head(n))
    return [(row["Label"], row[feats].to_dict()) for _, row in sampled.iterrows()]


def load_can_samples(n):
    can_files = {
        "BENIGN":         "decimal_benign.csv",
        "DoS":            "decimal_DoS.csv",
        "GAS":            "decimal_spoofing-GAS.csv",
        "RPM":            "decimal_spoofing-RPM.csv",
        "SPEED":          "decimal_spoofing-SPEED.csv",
        "STEERING_WHEEL": "decimal_spoofing-STEERING_WHEEL.csv",
    }
    raw_cols = ["ID","DATA_0","DATA_1","DATA_2","DATA_3",
                "DATA_4","DATA_5","DATA_6","DATA_7"]
    per_class = max(1, n // len(can_files))
    rows = []
    for label, fname in can_files.items():
        df = pd.read_csv(DATA / "CICIoV2024" / "decimal" / fname,
                         encoding="latin-1", nrows=per_class * 3)
        sample = df[raw_cols].sample(min(per_class, len(df)), random_state=42)
        for _, row in sample.iterrows():
            rows.append((label, row.to_dict()))
    RNG.shuffle(rows)
    return rows[:n]


def load_gps_samples(n):
    drop_cols = ["Clock Time","GPS MGRS","Hobbs","Data Type",
                 "Hobbs Time","Arming State","Flight Mode"]
    all_normal, all_spoof = [], []
    for i in range(4):
        df = pd.read_csv(DATA / "AV-GPS-Dataset" / f"AV-GPS-Dataset-{i}.csv")
        d  = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
        all_normal.extend(d[df["Data Type"] == 0].to_dict(orient="records"))
        all_spoof.extend( d[df["Data Type"] == 1].to_dict(orient="records"))
    half = n // 2
    ni = RNG.choice(len(all_normal), min(half, len(all_normal)), replace=False)
    si = RNG.choice(len(all_spoof),  min(half, len(all_spoof)),  replace=False) if all_spoof else []
    rows = ([("Normal",  all_normal[i]) for i in ni] +
            ([("Spoofing", all_spoof[i]) for i in si] if len(si) else []))
    RNG.shuffle(rows)
    return rows[:n]


def load_lidar_samples(n):
    seq_dirs = [
        DATA/"Depth"/"2011_09_26_drive_0001_sync"/"2011_09_26"
             /"2011_09_26_drive_0001_sync"/"velodyne_points"/"data",
        DATA/"Depth"/"2011_09_26_drive_0015_sync"/"2011_09_26"
             /"2011_09_26_drive_0015_sync"/"velodyne_points"/"data",
    ]
    bins = []
    for d in seq_dirs:
        bins += sorted(d.glob("*.bin"))

    per_class = max(1, n // 4)

    def drop_pts(pts):
        keep = RNG.random(len(pts)) > RNG.uniform(0.4, 0.7)
        return pts[keep] if keep.sum() > 100 else pts[:100]

    def spoof_int(pts):
        out = pts.copy()
        out[:, 3] = RNG.uniform(0.88, 1.0, len(pts)).astype(np.float32)
        return out

    def ghost(pts):
        ng = int(RNG.integers(2000, 6000))
        g = np.stack([
            RNG.uniform(8, 20, ng).astype(np.float32),
            RNG.uniform(-1.5, 1.5, ng).astype(np.float32),
            RNG.uniform(-1.5, 1.5, ng).astype(np.float32),
            RNG.uniform(0.1, 0.6, ng).astype(np.float32),
        ], axis=1)
        return np.concatenate([pts, g])

    attack_fns = {"PointDrop": drop_pts, "IntensitySpoof": spoof_int, "GhostCluster": ghost}
    rows = []
    chosen = RNG.choice(len(bins), min(per_class, len(bins)), replace=False)
    for i in chosen:
        rows.append(("Normal", str(bins[i])))
    for aname, afn in attack_fns.items():
        idx = RNG.choice(len(bins), per_class, replace=True)
        for i in idx:
            pts = np.fromfile(bins[i], dtype=np.float32).reshape(-1, 4)
            rows.append((aname, afn(pts)))
    RNG.shuffle(rows)
    return rows[:n]


# =============================================================================
#  ZERO-DAY HELPER
# =============================================================================

def compute_zd(zd_det, net_r, can_r, gps_r, lid_r):
    NET_C = ["BENIGN","Bot","BruteForce","DoS","Infiltration","PortScan","WebAttack"]
    CAN_C = ["BENIGN","DoS","GAS","RPM","SPEED","STEERING_WHEEL"]
    GPS_C = ["Normal","Spoofing"]
    LID_C = ["Normal","PointDrop","IntensitySpoof","GhostCluster"]
    vec = np.concatenate([
        _probs_vec(net_r, NET_C), _probs_vec(can_r, CAN_C),
        _probs_vec(gps_r, GPS_C), _probs_vec(lid_r, LID_C),
    ])
    sc    = zd_det.scaler.transform(vec.reshape(1, -1))
    score = float(zd_det.ocsvm.decision_function(sc)[0])
    flag  = bool(zd_det.ocsvm.predict(sc)[0] == -1)
    return {"anomaly_score": score, "is_zero_day": flag}


# =============================================================================
#  PRINT HELPERS
# =============================================================================

def domain_accuracy_table(df, true_col, pred_col):
    classes = sorted(df[true_col].unique())
    print(f"  {'Class':<24} {'Total':>7} {'Correct':>8} {'Accuracy':>9}")
    print(f"  {'-'*52}")
    tot, cor = 0, 0
    for cls in classes:
        mask  = df[true_col] == cls
        total = mask.sum()
        corr  = (df.loc[mask, pred_col] == cls).sum()
        tot  += total; cor += corr
        print(f"  {cls:<24} {total:>7} {corr:>8} {corr/total:>9.2%}")
    print(f"  {'OVERALL':<24} {tot:>7} {cor:>8} {cor/tot:>9.2%}")
    return cor / tot


def print_fusion_table(df):
    ta = df["true_any_attack"]
    fa = df["fusion_is_attack"]
    tp = (fa &  ta).sum(); fp = (fa & ~ta).sum()
    fn = (~fa &  ta).sum(); tn = (~fa & ~ta).sum()
    acc  = (tp+tn)/len(df)
    prec = tp/(tp+fp+1e-9)
    rec  = tp/(tp+fn+1e-9)
    f1   = 2*prec*rec/(prec+rec+1e-9)

    print(f"\n  {'Threat Level':<12} {'Count':>7} {'True Normal %':>15} {'True Attack %':>15}")
    print(f"  {'-'*52}")
    for lvl, lbl in {0:"NORMAL",1:"LOW",2:"MEDIUM",3:"HIGH",4:"CRITICAL"}.items():
        mask = df["fusion_threat"] == lvl
        if not mask.any(): continue
        pn = (~ta[mask]).mean(); pa = ta[mask].mean()
        print(f"  {lbl:<12} {mask.sum():>7} {pn:>15.1%} {pa:>15.1%}")
    print(f"\n  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Accuracy={acc:.2%}  Precision={prec:.2%}  Recall={rec:.2%}  F1={f1:.2%}")


# =============================================================================
#  PNG REPORT
# =============================================================================

def save_report_png(df, out_path):
    fig = plt.figure(figsize=(22, 16))
    fig.patch.set_facecolor("#0d1117")
    gs  = gridspec.GridSpec(3, 4, figure=fig, hspace=0.55, wspace=0.4)
    tk  = dict(fontsize=10, fontweight="bold", color="#f0ede6", pad=8)
    BC  = ["#4C72B0","#C44E52","#55A868","#DD8452","#8172B2","#937860","#DA8BC3"]

    def bar_panel(ax, true_col, pred_col, title):
        ax.set_facecolor("#161b22")
        classes = sorted(df[true_col].unique())
        vals, labs = [], []
        for cls in classes:
            m = df[true_col] == cls
            vals.append((df.loc[m, pred_col] == cls).mean())
            labs.append(f"{cls[:9]}\n(n={m.sum()})")
        bars = ax.bar(range(len(classes)), vals,
                      color=BC[:len(classes)], edgecolor="#333")
        ax.set_xticks(range(len(classes)))
        ax.set_xticklabels(labs, fontsize=6.5, color="#9c9a92")
        ax.set_ylim(0, 1.12)
        ax.tick_params(axis="y", colors="#9c9a92", labelsize=7)
        ax.set_title(title, **tk)
        for b, v in zip(bars, vals):
            ax.text(b.get_x()+b.get_width()/2, v+0.02, f"{v:.0%}",
                    ha="center", fontsize=6.5, color="#f0ede6")

    bar_panel(fig.add_subplot(gs[0, 0]), "net_true", "net_pred",
              "Network Domain -- Per-class Accuracy")
    bar_panel(fig.add_subplot(gs[0, 1]), "can_true", "can_pred",
              "CAN Bus Domain -- Per-class Accuracy")
    bar_panel(fig.add_subplot(gs[0, 2]), "gps_true", "gps_pred",
              "GPS Domain -- Per-class Accuracy")
    bar_panel(fig.add_subplot(gs[0, 3]), "lid_true", "lid_pred",
              "LiDAR Domain -- Per-class Accuracy")

    # Fusion confusion matrix
    ax5 = fig.add_subplot(gs[1, :2])
    ax5.set_facecolor("#161b22")
    cm = confusion_matrix(df["true_any_attack"].astype(int),
                          df["fusion_is_attack"].astype(int), labels=[0, 1])
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax5,
                xticklabels=["NORMAL","ATTACK"],
                yticklabels=["NORMAL","ATTACK"],
                annot_kws={"size": 14, "color": "white"})
    ax5.set_title("Fusion Engine -- Confusion Matrix (meta)", **tk)
    ax5.set_xlabel("Predicted", color="#9c9a92")
    ax5.set_ylabel("True", color="#9c9a92")
    ax5.tick_params(colors="#9c9a92")

    # Threat level distribution
    ax6 = fig.add_subplot(gs[1, 2:])
    ax6.set_facecolor("#161b22")
    ta = df["true_any_attack"]
    all_levels = ["NORMAL","LOW","MEDIUM","HIGH","CRITICAL"]
    nc = [df.loc[~ta, "fusion_threat_label"].value_counts().get(l, 0) for l in all_levels]
    ac = [df.loc[ ta, "fusion_threat_label"].value_counts().get(l, 0) for l in all_levels]
    x = np.arange(len(all_levels))
    ax6.bar(x-0.2, nc, 0.38, label="True Normal", color="#4C72B0", alpha=0.85)
    ax6.bar(x+0.2, ac, 0.38, label="True Attack", color="#C44E52", alpha=0.85)
    ax6.set_xticks(x); ax6.set_xticklabels(all_levels, color="#9c9a92", fontsize=9)
    ax6.tick_params(axis="y", colors="#9c9a92", labelsize=8)
    ax6.set_title("Fusion Threat Level vs True Label", **tk)
    ax6.set_ylabel("Count", color="#9c9a92")
    ax6.legend(fontsize=8, labelcolor="#9c9a92", facecolor="#161b22", edgecolor="#333")

    # Detection rate vs FPR per domain
    ax7 = fig.add_subplot(gs[2, :2])
    ax7.set_facecolor("#161b22")
    domain_info = [("Network","net_pred","net_true","BENIGN"),
                   ("CAN",    "can_pred","can_true","BENIGN"),
                   ("GPS",    "gps_pred","gps_true","Normal"),
                   ("LiDAR",  "lid_pred","lid_true","Normal")]
    doms, drs, fprs = [], [], []
    for dom, pc, tc, bv in domain_info:
        ta2 = df[tc] != bv; pa = df[pc] != bv
        if ta2.sum() == 0: continue
        drs.append((pa & ta2).sum() / ta2.sum())
        fprs.append((pa & ~ta2).sum() / max((~ta2).sum(), 1))
        doms.append(dom)
    x2 = np.arange(len(doms))
    ax7.bar(x2-0.2, drs,  0.38, label="Detection Rate",      color="#55A868", alpha=0.9)
    ax7.bar(x2+0.2, fprs, 0.38, label="False Positive Rate", color="#C44E52", alpha=0.9)
    ax7.set_xticks(x2); ax7.set_xticklabels(doms, color="#9c9a92", fontsize=10)
    ax7.set_ylim(0, 1.15); ax7.tick_params(axis="y", colors="#9c9a92", labelsize=8)
    ax7.set_title("Per-Domain Detection Rate vs False Positive Rate", **tk)
    ax7.legend(fontsize=8, labelcolor="#9c9a92", facecolor="#161b22", edgecolor="#333")
    for i, (dr, fpr) in enumerate(zip(drs, fprs)):
        ax7.text(i-0.2, dr+0.02,  f"{dr:.0%}",  ha="center", fontsize=9, color="#f0ede6")
        ax7.text(i+0.2, fpr+0.02, f"{fpr:.0%}", ha="center", fontsize=9, color="#f0ede6")

    # Summary text box
    ax8 = fig.add_subplot(gs[2, 2:])
    ax8.set_facecolor("#161b22"); ax8.axis("off")
    tp = (df["fusion_is_attack"] &  ta).sum()
    fp_ = (df["fusion_is_attack"] & ~ta).sum()
    fn = (~df["fusion_is_attack"] &  ta).sum()
    tn = (~df["fusion_is_attack"] & ~ta).sum()
    acc = (tp+tn)/len(df); prec = tp/(tp+fp_+1e-9)
    rec = tp/(tp+fn+1e-9); f1 = 2*prec*rec/(prec+rec+1e-9)
    summary = (
        "SYSTEM SUMMARY\n"
        f"{'='*30}\n"
        f"Total samples   : {len(df):,}\n"
        f"True normal     : {(~ta).sum():,}\n"
        f"True attack     : {ta.sum():,}\n"
        f"{'='*30}\n"
        f"Fusion strategy : meta\n"
        f"Accuracy        : {acc:.2%}\n"
        f"Precision       : {prec:.2%}\n"
        f"Recall          : {rec:.2%}\n"
        f"F1              : {f1:.2%}\n"
        f"{'='*30}\n"
        f"TP={tp}  FP={fp_}  FN={fn}  TN={tn}\n"
    )
    ax8.text(0.05, 0.95, summary, transform=ax8.transAxes,
             fontsize=9.5, va="top", fontfamily="monospace", color="#f0ede6",
             bbox=dict(boxstyle="round,pad=0.6", facecolor="#0d1117",
                       edgecolor="#3a3a3a", linewidth=0.8))

    fig.suptitle(
        "AV-IDS Full System Integration Test -- 1000 samples per domain",
        fontsize=13, fontweight="bold", color="#f0ede6", y=0.98)
    plt.savefig(out_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"\nReport PNG saved: {out_path}")


# =============================================================================
#  MAIN
# =============================================================================

def main():
    t0 = time.time()
    print("=" * 60)
    print("  AV-IDS Full System Integration Test")
    print(f"  {N} random samples per domain")
    print("=" * 60)

    print("\n[1/6] Loading all runners ...")
    net_det = NetworkDetector()
    can_det = CANDetector()
    gps_det = GPSDetector()
    lid_det = LiDARDetector()
    zd_det  = ZeroDayDetector(
        network_det=net_det, can_det=can_det,
        gps_det=gps_det, lidar_det=lid_det
    )
    engine = FusionEngine(strategy="meta")
    print("  All runners loaded.")

    print(f"\n[2/6] Loading {N} samples per domain ...")
    net_samples = load_network_samples(N)
    can_samples = load_can_samples(N)
    gps_samples = load_gps_samples(N)
    lid_samples = load_lidar_samples(N)
    m = min(len(net_samples), len(can_samples),
            len(gps_samples), len(lid_samples))
    net_samples = net_samples[:m]; can_samples = can_samples[:m]
    gps_samples = gps_samples[:m]; lid_samples = lid_samples[:m]
    print(f"  Network={len(net_samples)}  CAN={len(can_samples)}"
          f"  GPS={len(gps_samples)}  LiDAR={len(lid_samples)}")

    print(f"\n[3/6] Running all models on {m} sample sets ...")
    records = []
    for i in range(m):
        if i % 200 == 0:
            print(f"  [{i}/{m}] ...")

        net_true, net_feat = net_samples[i]
        can_true, can_feat = can_samples[i]
        gps_true, gps_feat = gps_samples[i]
        lid_true, lid_src  = lid_samples[i]

        net_r = net_det.predict([net_feat])[0]
        can_r = can_det.predict([can_feat])[0]
        gps_r = gps_det.predict([gps_feat])[0]
        lid_r = lid_det.predict_one(lid_src)
        zd_r  = compute_zd(zd_det, net_r, can_r, gps_r, lid_r)
        alert = engine.predict(net_r, can_r, gps_r, lid_r, zd_r)

        true_any_attack = (
            net_true != "BENIGN" or
            can_true != "BENIGN" or
            gps_true == "Spoofing" or
            lid_true != "Normal"
        )

        gps_pred = gps_r.get("label") or gps_r.get("label_name", "?")

        records.append({
            "net_true":            net_true,
            "can_true":            can_true,
            "gps_true":            gps_true,
            "lid_true":            lid_true,
            "true_any_attack":     true_any_attack,
            "net_pred":            net_r["label_name"],
            "net_conf":            round(net_r["confidence"], 3),
            "can_pred":            can_r["label_name"],
            "can_conf":            round(can_r["confidence"], 3),
            "gps_pred":            gps_pred,
            "gps_conf":            round(gps_r["confidence"], 3),
            "lid_pred":            lid_r["label_name"],
            "lid_conf":            round(lid_r["confidence"], 3),
            "zd_is_zero_day":      zd_r["is_zero_day"],
            "zd_score":            round(zd_r["anomaly_score"], 3),
            "fusion_threat":       alert.threat_level,
            "fusion_threat_label": alert.threat_label,
            "fusion_attack_score": round(alert.attack_score, 3),
            "fusion_is_attack":    alert.is_attack,
            "fusion_triggered_by": "|".join(alert.triggered_by),
        })

    df = pd.DataFrame(records)

    print(f"\n[4/6] Results")

    print("\n" + "=" * 60)
    print("  NETWORK DOMAIN")
    print("=" * 60)
    domain_accuracy_table(df, "net_true", "net_pred")

    print("\n" + "=" * 60)
    print("  CAN BUS DOMAIN")
    print("=" * 60)
    domain_accuracy_table(df, "can_true", "can_pred")

    print("\n" + "=" * 60)
    print("  GPS DOMAIN")
    print("=" * 60)
    domain_accuracy_table(df, "gps_true", "gps_pred")

    print("\n" + "=" * 60)
    print("  LiDAR DOMAIN")
    print("=" * 60)
    domain_accuracy_table(df, "lid_true", "lid_pred")

    print("\n" + "=" * 60)
    print("  FUSION ENGINE  (meta strategy)")
    print("=" * 60)
    print_fusion_table(df)

    print("\n[5/6] Sample rows (first 20):")
    disp = ["net_true","net_pred","can_true","can_pred",
            "gps_true","gps_pred","lid_true","lid_pred",
            "fusion_threat_label","fusion_is_attack"]
    print(df[disp].head(20).to_string(index=False))

    csv_path = CODES / "integration_results.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n[6/6] Full results saved: {csv_path}")

    save_report_png(df, CODES / "integration_report.png")

    print(f"\nTotal time: {time.time()-t0:.1f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
