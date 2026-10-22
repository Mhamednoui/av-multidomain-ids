"""Persistent-attack sequence scoring (logic of ../codes_v2/lidar/sequence.py, copied).

Per-scan attack score s = max(1 - P(Normal) of the temporal model, 1 - P(Normal) of the
single-scan model); evidence is the mean log-odds over the last W = 10 scans (1 s); an episode
is detected when the alarm (threshold = 99th percentile of that statistic on NORMAL validation
sequences) fires within 3 s (30 scans) of the onset.
Inputs: per-scan scores in time order for one sequence. Outputs: rolling statistic, alarms.
"""
import numpy as np

W = 10
EPISODE_SCANS = 30


def rolling_logodds(s, w=W):
    s = np.clip(np.asarray(s, float), 1e-4, 1 - 1e-4)
    lo = np.log(s / (1 - s))
    c = np.cumsum(np.r_[0, lo])
    k = np.arange(1, len(lo) + 1)
    start = np.maximum(k - w, 0)
    return (c[k] - c[start]) / (k - start)


def first_alarm_scan(alarm):
    hit = np.flatnonzero(alarm)
    return int(hit[0]) + 1 if len(hit) else None


def episode_detected(alarm, limit=EPISODE_SCANS):
    k = first_alarm_scan(alarm)
    return k is not None and k <= limit
