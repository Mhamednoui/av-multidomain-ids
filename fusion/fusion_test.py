"""
Fusion Engine — Full evaluation test.

Tests all 3 strategies (rule_based, weighted, meta) on real samples and
produces fusion_evaluation.png comparing strategy performance.

Run with:
    python fusion/fusion_test.py
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
CODES = HERE.parent
sys.path.insert(0, str(CODES))

from network.network_runner import NetworkDetector
from can.can_runner import CANDetector
from gps.gps_runner import GPSDetector
from lidar.lidar_runner import LiDARDetector
from unsupervised.unsupervised_runner import ZeroDayDetector
from fusion.fusion_engine import FusionEngine

DATA   = CODES / "data"
RNG    = np.random.default_rng(7)
N_TEST = 150   # samples per class (normal / attack)


# ── Helpers ───────────────────────────────────────────────────────────────────

def run_all_runners(net_det, can_det, gps_det, lid_det, zd_det,
                    net_row, can_row, gps_row, lidar_src):
    net_r = net_det.predict([net_row])[0]
    can_r = can_det.predict([can_row])[0]
    gps_r = gps_det.predict([gps_row])[0]
    lid_r = lid_det.predict_one(lidar_src)

    from unsupervised.unsupervised_runner import _probs_vec
    zd_vec = np.concatenate([
        _probs_vec(net_r, ["BENIGN","Bot","BruteForce","DoS","Infiltration","PortScan","WebAttack"]),
        _probs_vec(can_r, ["BENIGN","DoS","GAS","RPM","SPEED","STEERING_WHEEL"]),
        _probs_vec(gps_r, ["Normal","Spoofing"]),
        _probs_vec(lid_r, ["Normal","PointDrop","IntensitySpoof","GhostCluster"]),
    ])
    zd_sc = zd_det.scaler.transform(zd_vec.reshape(1,-1))
    zd_score = float(zd_det.ocsvm.decision_function(zd_sc)[0])
    zd_flag  = bool(zd_det.ocsvm.predict(zd_sc)[0] == -1)
    zd_r = {"anomaly_score": zd_score, "is_zero_day": zd_flag}

    return net_r, can_r, gps_r, lid_r, zd_r


def collect_test_pairs(net_det, can_det, gps_det, lid_det, zd_det, n=N_TEST):
    """Returns list of (label, net_r, can_r, gps_r, lid_r, zd_r) tuples."""
    print(f"  Collecting {n} normal + {n} attack test pairs ...")

    net_feats = json.load(open(CODES / "network" / "network_features.json"))
    df_net = pd.read_csv(DATA / "CICIDS2017_sample.csv")
    net_b = (df_net[df_net["Label"]=="BENIGN"][net_feats]
             .replace([np.inf,-np.inf],0).fillna(0).sample(n, random_state=5)
             .to_dict(orient="records"))
    net_a = (df_net[df_net["Label"]!="BENIGN"][net_feats]
             .replace([np.inf,-np.inf],0).fillna(0).sample(n, random_state=5)
             .to_dict(orient="records"))

    df_can_b = pd.read_csv(DATA/"CICIoV2024"/"decimal"/"decimal_benign.csv",
                           encoding="latin-1", nrows=n*2)
    df_can_a = pd.read_csv(DATA/"CICIoV2024"/"decimal"/"decimal_DoS.csv",
                           encoding="latin-1", nrows=n*2)
    can_b_rows = df_can_b[["ID","DATA_0","DATA_1","DATA_2","DATA_3",
                             "DATA_4","DATA_5","DATA_6","DATA_7"]].head(n).to_dict(orient="records")
    can_a_rows = df_can_a[["ID","DATA_0","DATA_1","DATA_2","DATA_3",
                             "DATA_4","DATA_5","DATA_6","DATA_7"]].head(n).to_dict(orient="records")

    drop = ["Clock Time","GPS MGRS","Hobbs","Data Type","Hobbs Time","Arming State","Flight Mode"]
    gps_b_rows, gps_a_rows = [], []
    for i in range(4):
        df = pd.read_csv(DATA/"AV-GPS-Dataset"/f"AV-GPS-Dataset-{i}.csv")
        d  = df.drop(columns=[c for c in drop if c in df.columns], errors="ignore")
        gps_b_rows += d[df["Data Type"]==0].to_dict(orient="records")
        gps_a_rows += d[df["Data Type"]==1].to_dict(orient="records")
    if not gps_a_rows:
        gps_a_rows = gps_b_rows

    seq_dirs = [
        DATA/"Depth"/"2011_09_26_drive_0001_sync"/"2011_09_26"/"2011_09_26_drive_0001_sync"/"velodyne_points"/"data",
    ]
    bins = sorted(seq_dirs[0].glob("*.bin"))

    samples = []
    for i in range(n):
        # Normal
        net_r, can_r, gps_r, lid_r, zd_r = run_all_runners(
            net_det, can_det, gps_det, lid_det, zd_det,
            net_b[i], can_b_rows[i % len(can_b_rows)],
            gps_b_rows[i % len(gps_b_rows)], bins[i % len(bins)]
        )
        samples.append((0, net_r, can_r, gps_r, lid_r, zd_r))

        # Attack — synthesize lidar attack
        pts = np.fromfile(bins[i % len(bins)], dtype=np.float32).reshape(-1, 4)
        keep = RNG.random(len(pts)) > 0.55
        apts = pts[keep] if keep.sum() > 100 else pts[:100]

        net_r, can_r, gps_r, lid_r, zd_r = run_all_runners(
            net_det, can_det, gps_det, lid_det, zd_det,
            net_a[i], can_a_rows[i % len(can_a_rows)],
            gps_a_rows[i % len(gps_a_rows)], apts
        )
        samples.append((1, net_r, can_r, gps_r, lid_r, zd_r))

    return samples


def evaluate_strategy(engine, samples):
    y_true, y_pred, scores = [], [], []
    for label, net_r, can_r, gps_r, lid_r, zd_r in samples:
        alert = engine.predict(net_r, can_r, gps_r, lid_r, zd_r)
        y_true.append(label)
        y_pred.append(1 if alert.is_attack else 0)
        scores.append(alert.attack_score)
    y_true  = np.array(y_true)
    y_pred  = np.array(y_pred)
    scores  = np.array(scores)
    acc     = (y_true == y_pred).mean()
    tp = ((y_pred==1) & (y_true==1)).sum()
    fp = ((y_pred==1) & (y_true==0)).sum()
    fn = ((y_pred==0) & (y_true==1)).sum()
    tn = ((y_pred==0) & (y_true==0)).sum()
    prec = tp / (tp + fp + 1e-9)
    rec  = tp / (tp + fn + 1e-9)
    f1   = 2 * prec * rec / (prec + rec + 1e-9)
    return {"acc": acc, "precision": prec, "recall": rec, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "y_true": y_true, "y_pred": y_pred, "scores": scores}


def save_comparison_png(results_by_strategy, out_path):
    strategies = list(results_by_strategy.keys())
    metrics    = ["acc","precision","recall","f1"]
    labels     = ["Accuracy","Precision","Recall","F1"]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Bar chart comparison
    x = np.arange(len(metrics))
    w = 0.25
    colors = ["#4C72B0","#55A868","#C44E52"]
    for k, (strat, res) in enumerate(results_by_strategy.items()):
        vals = [res[m] for m in metrics]
        axes[0].bar(x + k*w, vals, w, label=strat, color=colors[k])
    axes[0].set_xticks(x + w)
    axes[0].set_xticklabels(labels)
    axes[0].set_ylim(0, 1.1)
    axes[0].set_title("Fusion Strategy Comparison")
    axes[0].legend()
    axes[0].set_ylabel("Score")

    # Score distribution for best strategy (weighted)
    best = results_by_strategy.get("weighted",
           list(results_by_strategy.values())[0])
    axes[1].hist(best["scores"][best["y_true"]==0], bins=30, alpha=0.6,
                 color="#4C72B0", label="Normal", density=True)
    axes[1].hist(best["scores"][best["y_true"]==1], bins=30, alpha=0.6,
                 color="#C44E52", label="Attack", density=True)
    axes[1].axvline(0.5, color="black", linestyle="--", linewidth=1.5,
                    label="Threshold 0.5")
    axes[1].set_title("Attack Score Distribution (Weighted Strategy)")
    axes[1].set_xlabel("Attack Score"); axes[1].set_ylabel("Density")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close()
    print(f"Saved: {out_path}")


def main():
    print("=== Fusion Engine — Full Evaluation ===")

    print("\nLoading runners ...")
    net_det = NetworkDetector()
    can_det = CANDetector()
    gps_det = GPSDetector()
    lid_det = LiDARDetector()
    zd_det  = ZeroDayDetector(
        network_det=net_det, can_det=can_det,
        gps_det=gps_det, lidar_det=lid_det
    )

    print("\nCollecting test pairs ...")
    samples = collect_test_pairs(net_det, can_det, gps_det, lid_det, zd_det)
    print(f"  {len(samples)} total samples")

    strategies = {
        "rule_based": FusionEngine(strategy="rule_based"),
        "weighted":   FusionEngine(strategy="weighted"),
    }
    if (HERE / "fusion_meta_model.json").exists():
        strategies["meta"] = FusionEngine(strategy="meta")

    print("\n" + "="*55)
    print(f"{'Strategy':<14} {'Acc':>7} {'Prec':>7} {'Rec':>7} {'F1':>7}")
    print("-"*55)

    results_by_strategy = {}
    for name, engine in strategies.items():
        res = evaluate_strategy(engine, samples)
        results_by_strategy[name] = res
        print(f"{name:<14} {res['acc']:>7.2%} {res['precision']:>7.2%}"
              f" {res['recall']:>7.2%} {res['f1']:>7.2%}")
        print(f"{'':14}  TP={res['tp']} FP={res['fp']}"
              f" FN={res['fn']} TN={res['tn']}")

    print("="*55)

    save_comparison_png(results_by_strategy, HERE / "fusion_evaluation.png")

    # Print example alert
    print("\n--- Example alert (weighted strategy, first attack sample) ---")
    engine = FusionEngine(strategy="weighted")
    label, net_r, can_r, gps_r, lid_r, zd_r = next(s for s in samples if s[0]==1)
    alert = engine.predict(net_r, can_r, gps_r, lid_r, zd_r)
    d = engine.alert_to_dict(alert)
    print(json.dumps(d, indent=2, default=str))


if __name__ == "__main__":
    main()
