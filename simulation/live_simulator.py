"""
AV-IDS Live Simulator
======================
Reads simulation_dataset.csv row by row and runs the full IDS pipeline
in real time, printing a live feed to the terminal.

Each row = one sensor cycle. The script plays through the dataset at a
configurable speed, printing one line per cycle with:
  - elapsed time
  - current scenario (ground truth)
  - per-domain detection result
  - fusion threat level
  - temporal correlator result (escalated?)

Run with:
    python simulation/live_simulator.py
    python simulation/live_simulator.py --duration 50
    python simulation/live_simulator.py --duration 30 --speed 2
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE  = Path(__file__).parent
CODES = HERE.parent
sys.path.insert(0, str(CODES))

from can.can_runner                   import CANDetector
from gps.gps_runner                   import GPSDetector
from network.network_runner           import NetworkDetector
from lidar.lidar_runner               import LiDARDetector
from unsupervised.unsupervised_runner import ZeroDayDetector, _probs_vec
from fusion.fusion_engine             import FusionEngine
from temporal.temporal_correlator     import TemporalCorrelator
from windowing.window_engine          import CANWindow, GPSWindow

DATASET = HERE / "simulation_dataset.csv"

CAN_RAW  = ["ID","DATA_0","DATA_1","DATA_2","DATA_3","DATA_4","DATA_5","DATA_6","DATA_7"]
GPS_COLS = ['Roll (deg)','Pitch (deg)','Heading (deg)','Yaw (deg)','Yaw Rate (deg/s)',
            'Velocity (m/s)','Steering Angle (deg)','Relative Altitude (m)','Altitude AMSL (m)',
            'Altitude Tuning','Altitude Tuning Setpoint','X-Track Error (m)',
            'Travelled Distance (m)','Run Time','Distance To Home (m)','Mission Index',
            'Heading To Next WP (deg)','Heading To Home (deg)','Distance To GCS (m)',
            'Throttle (%)','Clock Date','GPS Latitude','GPS Longitude','GPS HDOP','GPS VDOP',
            'GPS Course','Satellite Locks','Satellite Count','Longitudinal Position (m)',
            'Lateral Position (m)','Vertical Position (m)','Longitudinal Velocity (m/s)',
            'Absolute Longitudinal Velocity (m/s)','Lateral Velocity (m/s)',
            'Absolute Lateral Velocity (m/s)','Vertical Velocity (m/s)','Temperature (F)',
            'Longitudinal Vibration','Lateral Vibration','Vertical Vibration']

NET_FEATS = json.load(open(CODES / "network" / "network_features.json"))

# ── colour codes (ANSI) ───────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

THREAT_COLOR = {
    "NORMAL":   GREEN,
    "LOW":      CYAN,
    "MEDIUM":   YELLOW,
    "HIGH":     "\033[33m",
    "CRITICAL": RED + BOLD,
}


def threat_colored(label: str) -> str:
    return f"{THREAT_COLOR.get(label, '')}{label:<8}{RESET}"


def compute_zd(zd_det, net_r, can_r, gps_r, lid_r):
    NET_C = ["BENIGN","Bot","BruteForce","DoS","Infiltration","PortScan","WebAttack"]
    CAN_C = ["BENIGN","DoS","GAS","RPM","SPEED","STEERING_WHEEL"]
    GPS_C = ["Normal","Spoofing"]
    LID_C = ["Normal","PointDrop","IntensitySpoof","GhostCluster"]
    vec   = np.concatenate([_probs_vec(net_r, NET_C), _probs_vec(can_r, CAN_C),
                             _probs_vec(gps_r, GPS_C), _probs_vec(lid_r, LID_C)])
    sc    = zd_det.scaler.transform(vec.reshape(1,-1))
    score = float(zd_det.ocsvm.decision_function(sc)[0])
    # Only flag as zero-day when score is deeply negative (< -2.0) AND supervised
    # models are clean — avoids the high FPR of the OC-SVM on borderline packets.
    supervised_clean = (net_r.get("label_name") == "BENIGN" and
                        not can_r.get("is_attack", False) and
                        gps_r.get("label", gps_r.get("label_name", "Normal")) == "Normal" and
                        not lid_r.get("is_attack", False))
    is_zd = (score < -2.0) and supervised_clean
    return {
        "anomaly_score": score,
        "is_zero_day":   is_zd,
    }


def extract_can(row: pd.Series) -> dict:
    return {c: row[f"can_{c}"] for c in CAN_RAW}


def extract_gps(row: pd.Series) -> dict:
    return {c: row.get(f"gps_{c}", 0.0) for c in GPS_COLS}


def extract_net(row: pd.Series) -> dict:
    return {c: row[f"net_{c}"] for c in NET_FEATS}


def format_domain(label: str, is_attack: bool) -> str:
    if is_attack:
        return f"{RED}{label[:12]:<12}{RESET}"
    return f"{GREEN}{'ok':<12}{RESET}"


def print_header():
    print(f"\n{BOLD}{'='*100}{RESET}")
    print(f"{BOLD}  AV-IDS Live Simulator{RESET}")
    print(f"{'='*100}{RESET}")
    print(f"\n{BOLD}  {'Time':>6}  {'Scenario':<16}  {'Network':<12}  {'CAN':<12}  "
          f"{'GPS':<12}  {'LiDAR':<12}  {'Fusion':<10}  {'Correlated':<10}  {'Alert'}{RESET}")
    print(f"  {'-'*95}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=50,
                        help="Simulation duration in seconds (default 50)")
    parser.add_argument("--speed", type=float, default=1.0,
                        help="Speed multiplier — 2.0 = 2x faster (default 1.0)")
    args = parser.parse_args()

    DURATION = args.duration
    SPEED    = args.speed
    # time per row = total duration / total rows, adjusted by speed
    df = pd.read_csv(DATASET)
    total_rows  = len(df)
    time_per_row = (DURATION / total_rows) / SPEED

    print(f"\n  Loading dataset: {total_rows} rows, {DURATION}s duration, speed x{SPEED}")
    print(f"  Each row plays in {time_per_row:.3f}s  ({1/time_per_row:.1f} cycles/sec)\n")

    # ── load runners ──────────────────────────────────────────────────────────
    print("  Loading models ...", end=" ", flush=True)
    can_det = CANDetector()
    gps_det = GPSDetector()
    net_det = NetworkDetector()
    lid_det = LiDARDetector()
    zd_det  = ZeroDayDetector(network_det=net_det, can_det=can_det,
                               gps_det=gps_det, lidar_det=lid_det)
    engine  = FusionEngine(strategy="rule_based", conf_threshold=0.6)
    tc      = TemporalCorrelator(window=10, threshold=0.6)

    # small GPS window to carry consecutive frames for delta features
    gps_win = GPSWindow(window_size=5, stride=1)
    print("done.")

    print_header()

    stats = {"total": 0, "normal": 0, "attacks": 0,
             "TP": 0, "FP": 0, "FN": 0, "TN": 0}
    prev_scenario = None
    t_start = time.time()

    for idx, row in df.iterrows():
        row_start = time.time()
        elapsed   = row_start - t_start

        if elapsed > DURATION:
            break

        scenario    = row["scenario"]
        true_attack = bool(row["true_attack"])

        # ── print scenario transition banner ──────────────────────────────────
        if scenario != prev_scenario:
            color = RED if true_attack else GREEN
            tag   = "[ATTACK SCENARIO]" if true_attack else "[NORMAL TRAFFIC]"
            print(f"\n  {color}{BOLD}  >>> {scenario}  {tag}{RESET}\n")
            prev_scenario = scenario

        # ── extract inputs ────────────────────────────────────────────────────
        can_pkt = extract_can(row)
        gps_frm = extract_gps(row)
        net_flw = extract_net(row)
        lid_src = str(row["lidar_bin"])

        # GPS: push into small window for consecutive-frame deltas
        # Need at least 2 frames so diff() features are non-zero
        gps_win.push(gps_frm)
        if len(gps_win._buffer) >= 2:
            gps_batch = gps_win.flush()
            gps_r = gps_det.predict(gps_batch)[-1]
        else:
            gps_r = {"label": "Normal", "label_int": 0,
                     "confidence": 1.0, "prob_normal": 1.0, "prob_spoof": 0.0}

        # ── run domain runners ────────────────────────────────────────────────
        can_r   = can_det.predict([can_pkt])[0]
        net_r   = net_det.predict([net_flw])[0]
        lid_r   = lid_det.predict_one(lid_src)

        # Network: pass through directly (benign dataset is pre-filtered)
        net_r_fused = net_r

        # ── zero-day + fusion ─────────────────────────────────────────────────
        zd_r  = compute_zd(zd_det, net_r, can_r, gps_r, lid_r)
        # Pass zeroday_result=None to fusion so noisy ZD signal doesn't
        # inflate the weighted score — [ZD] tag is shown separately for display.
        alert = engine.predict(net_r_fused, can_r, gps_r, lid_r, zeroday_result=None)
        corr  = tc.correlate(alert)

        # ── stats ─────────────────────────────────────────────────────────────
        stats["total"] += 1
        pred_attack = corr.is_attack
        if true_attack and pred_attack:     stats["TP"] += 1; stats["attacks"] += 1
        elif not true_attack and pred_attack: stats["FP"] += 1; stats["normal"] += 1
        elif true_attack and not pred_attack: stats["FN"] += 1; stats["attacks"] += 1
        else:                                stats["TN"] += 1; stats["normal"] += 1

        # ── format line ───────────────────────────────────────────────────────
        net_lbl  = net_r["label_name"]
        can_lbl  = can_r["label_name"]
        gps_lbl  = gps_r.get("label") or gps_r.get("label_name", "?")
        lid_lbl  = lid_r["label_name"]

        net_str  = format_domain(net_lbl, net_lbl != "BENIGN")
        can_str  = format_domain(can_lbl, can_r["is_attack"])
        gps_str  = format_domain(gps_lbl, gps_lbl == "Spoofing")
        lid_str  = format_domain(lid_lbl, lid_r["is_attack"])

        fus_str  = threat_colored(alert.threat_label)
        cor_str  = threat_colored(corr.threat_label)

        esc_tag  = f" {YELLOW}[ESC]{RESET}" if corr.escalated else ""
        zd_tag   = f" {CYAN}[ZD]{RESET}"   if zd_r["is_zero_day"] else ""

        true_tag = f"[TRUE:{('ATK' if true_attack else 'OK')}]"
        true_col = RED if true_attack else DIM

        print(f"  {elapsed:>5.1f}s  "
              f"{true_col}{scenario:<16}{RESET}  "
              f"{net_str}  {can_str}  {gps_str}  {lid_str}  "
              f"{fus_str}  {cor_str}{esc_tag}{zd_tag}")

        # ── timing sleep ──────────────────────────────────────────────────────
        elapsed_row = time.time() - row_start
        sleep_time  = time_per_row - elapsed_row
        if sleep_time > 0:
            time.sleep(sleep_time)

    # ── final summary ─────────────────────────────────────────────────────────
    total_time = time.time() - t_start
    tp, fp, fn, tn = stats["TP"], stats["FP"], stats["FN"], stats["TN"]
    prec = tp / (tp + fp + 1e-9)
    rec  = tp / (tp + fn + 1e-9)
    f1   = 2 * prec * rec / (prec + rec + 1e-9)

    print(f"\n  {'='*95}")
    print(f"\n  {BOLD}SIMULATION COMPLETE{RESET}  ({total_time:.1f}s)")
    print(f"\n  Rows processed  : {stats['total']}")
    print(f"  True normal     : {stats['normal']}")
    print(f"  True attacks    : {stats['attacks']}")
    print(f"\n  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision : {prec:.2%}")
    print(f"  Recall    : {rec:.2%}")
    print(f"  F1        : {f1:.2%}")
    print(f"\n  {'='*95}\n")


if __name__ == "__main__":
    main()
