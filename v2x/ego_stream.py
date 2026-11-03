"""Single-ego V2X stream: the frozen 12-check physics stack, one received message at a time, bounded state (WP8 v3.1 S5).

Purpose: what ONE receiver (the ego, ~7 messages/s) would compute while it listens. The v3 V2XRunner (system/v2x_runner.py) keeps the whole history of every track and
rebuilds a pandas context for each message; this module keeps only what the checks can see, so the cost of a message does not depend on how long the sender has been heard:
  per track   the previous message (all pairwise checks: pos_speed, pos_heading, speed_change, implied_speed, heading_rate, accel_consistency, beacon_rate) and the
              Kalman state (x, P, CUSUM) of the current filter segment (kf_nis, kf_cusum_hi) -- the batch code is a recursion over the segment, so this is exact
  receiver    messages heard in the last 1 s (overlap) and tracks born in the last 10 s (track_birth)
  field_ranges is a function of the message alone.
The per-track checks call the SAME layer code (v2x/l1.py, l2.py) on a two-row table; the Kalman step repeats the arithmetic of v2x/l3.run_filter for one row; the two
cross-sender checks call l2.overlap_depth / l3.birth_density on the small receiver context. Clock rule of the V2AIX evaluation (v2x/v2aix_eval.py): per-track checks use
the generation time t, the cross-sender checks use the reception time recv_s (VeReMi: no recv_s column, t is both).
Input: dict-like row with schema columns (msg_id, track, t, x, y, speed, vx, vy, heading, acl, yaw_rate, rx_id, [recv_s]) in reception order.
Output: dict {check name: float32 raw score} (12 checks of system/v2x_runner.LAYER_NAMES); evidence() turns it into the Evidence of V2XPhysicsDomain.
Caveats counted, not hidden: `reordered` (a message of a track older than the previous one: the batch code sorts by t, a stream cannot), `ties` (equal reception time).
References: v2x/l3.py (Kalman), notes/WP8_v31.md rule S5 V1.
"""
from collections import deque

import numpy as np
import pandas as pd

from v2x import l1, l2, l3
from v2x.l1 import LIMITS

CHECKS = ["v2x.beacon_rate", "v2x.field_ranges", "v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate",
          "v2x.accel_consistency", "v2x.overlap", "v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]
PAIR_LAYERS = {lay.name: lay for lay in l2.make_layers() if lay.name in ("v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed",
                                                                         "v2x.heading_rate", "v2x.accel_consistency")}
COLS = ["track", "t", "x", "y", "speed", "vx", "vy", "heading", "acl", "yaw_rate", "rx_id"]
MARGIN_S = 0.5


class _Kalman:
    """One-row version of l3.run_filter (same operations, batch of one)."""

    def __init__(self, p):
        self.p = p
        self.R = np.diag([p.sp ** 2, p.sp ** 2, p.sv ** 2, p.sv ** 2])
        self.eye = np.eye(4)

    def start(self, z):
        return [z.copy(), self.R.copy(), 0.0]

    def step(self, st, z, dt):
        p = self.p
        F = np.broadcast_to(self.eye, (1, 4, 4)).copy()
        dtv = np.array([dt])
        F[:, 0, 2] = dtv
        F[:, 1, 3] = dtv
        xm = np.einsum("mij,mj->mi", F, st[0][None])
        Pm = F @ st[1][None] @ F.transpose(0, 2, 1) + l3._Q(dtv, p.sa)
        S = Pm + self.R
        nu = z[None] - xm
        Si = np.linalg.inv(S)
        v = np.einsum("mi,mij,mj->m", nu, Si, nu)
        K = Pm @ Si
        x = xm + np.einsum("mij,mj->mi", K, nu)
        Pn = (self.eye - K) @ Pm
        st[0], st[1] = x[0], (0.5 * (Pn + Pn.transpose(0, 2, 1)))[0]
        st[2] = float(np.maximum(0.0, st[2] + v[0] - l3.K_HI))
        return float(v[0]), st[2]


class EgoStream:
    def __init__(self, tracker: l3.Tracker, use_recv=True):
        self.kf = _Kalman(tracker.params)
        self.use_recv = use_recv
        self.reset()

    def reset(self):
        self.last = {}            # track -> previous row (dict)
        self.kst = {}             # track -> Kalman state
        self.recent = deque()     # rows heard in the last 1 s (all tracks)
        self.births = deque()     # first rows of tracks born in the last 10 s
        self.ties = 0
        self.reordered = 0
        self.reordered_rows = []   # (message index, track) of messages older than the previous one of their track
        self.n = 0
        self.last_rx = -np.inf
        self.n_ctx = []

    def push(self, sample) -> dict:
        row = {c: sample[c] if c in sample else np.nan for c in COLS}
        row["recv_s"] = float(sample["recv_s"]) if self.use_recv else float(row["t"])
        t, tr, r = float(row["t"]), row["track"], row["recv_s"]
        if r == self.last_rx:
            self.ties += 1
        self.last_rx = max(self.last_rx, r)
        prev = self.last.get(tr)
        out = {}
        # ---- per-track checks on the two-row table [previous, this] -------------------------------------
        if prev is not None and t < prev["t"]:
            self.reordered += 1
            self.reordered_rows.append((self.n, tr))
        ctx1 = pd.DataFrame([prev, row] if prev is not None else [row])
        for n, lay in PAIR_LAYERS.items():
            out[n] = lay.raw_scores(ctx1)[-1]
        out["v2x.beacon_rate"] = l1.rate_hz(ctx1)[-1] / LIMITS["RATE_MAX_HZ"]
        out["v2x.field_ranges"] = l1.FieldRanges().raw_scores(ctx1)[-1]
        # ---- Kalman ----------------------------------------------------------------------------------------
        z, ok = l3.measurements(ctx1.iloc[[-1]])
        z, ok = z[0], bool(ok[0])
        dt = round(t - prev["t"], 3) if prev is not None else 0.0
        new = prev is None or dt > l3.DT_MAX or dt <= 0 or not ok
        if new:
            self.kst[tr] = self.kf.start(z)
            out["v2x.kf_nis"], out["v2x.kf_cusum_hi"] = 0.0, 0.0
        else:
            out["v2x.kf_nis"], out["v2x.kf_cusum_hi"] = self.kf.step(self.kst[tr], z, dt)
        # ---- cross-sender checks on the reception clock ----------------------------------------------------
        while self.recent and self.recent[0]["recv_s"] < r - l2.W_OVERLAP - MARGIN_S:
            self.recent.popleft()
        while self.births and self.births[0]["recv_s"] < r - l3.BIRTH_WINDOW_S - MARGIN_S:
            self.births.popleft()
        rows = [o for o in self.recent if o["track"] != tr] + [row]
        dfr = pd.DataFrame(rows).assign(t=lambda d: d["recv_s"])
        out["v2x.overlap"] = l2.overlap_depth(dfr)[-1]
        self.n_ctx.append(len(rows))
        if prev is None:
            brow = [o for o in self.births] + [row]
            dfb = pd.DataFrame(brow).assign(t=lambda d: d["recv_s"])
            out["v2x.track_birth"] = l3.birth_density(dfb)[-1]
            self.births.append(row)
        else:
            out["v2x.track_birth"] = 0.0
        self.last[tr] = row
        self.n += 1
        self.recent.append(row)
        return {n: np.float32(out[n]) for n in CHECKS}
