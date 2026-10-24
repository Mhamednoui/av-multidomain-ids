"""WP5 S3b: evaluation helpers for the frozen V2X physics stack on V2AIX (real CAMs): raw scores with the reception clock for cross-sender checks, variant A (frozen
VeReMi calibration) and variant B (re-calibration on V2AIX genuine validation), alarms per check / group / combined, false-alarm rates per message / sender / hour.
Inputs: V2AIX message tables (v2x/v2aix.py columns incl. recv_s, rx_id, rx_x, rx_y), the frozen domain (system/v2x_runner.py V2XPhysicsDomain, read only).
Outputs: raw dicts (12 checks, float32 like the S6 feature tables), Calib objects (ECDF + tie-safe 1% thresholds), boolean alarm arrays.
Clock rule: per-track checks use t (generation time, aligned within a sender); the two cross-sender checks (overlap, track_birth) use recv_s (the logger clock shared by all
senders and by the ego pose) and are evaluated per recording, i.e. per receiver view. Group definitions: L1 = beacon_rate + field_ranges; L2 = 7 plausibility checks; L3 =
kf_nis + kf_cusum_hi + track_birth; combined = max of the calibrated scores (the combiner of the frozen domain).
"""
import numpy as np
import pandas as pd

from common.calibration import ECDFCalibrator
from common.metrics import budget_threshold
from v2x import l1, l2, l3, l_rx
from v2x.l1 import LIMITS

# check names of the frozen domain (copied from system/v2x_runner.py so that v2x/ does not import system/)
L1_N = ["v2x.beacon_rate", "v2x.field_ranges"]
L2_N = ["v2x.pos_speed", "v2x.pos_heading", "v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate", "v2x.accel_consistency", "v2x.overlap"]
L3_N = ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.track_birth"]
LAYER_NAMES = L1_N + L2_N + L3_N
GROUPS = {"L1": L1_N, "L2": L2_N, "L3": L3_N, "physics": LAYER_NAMES}
RX_N = ["v2x.acceptance_range", "v2x.appearance_data"]
BUDGET = 0.01


def birth_per_recording(dfr: pd.DataFrame) -> np.ndarray:
    """track_birth raw score per row, computed inside each recording (receiver view) on the table whose t is the reception time."""
    out = np.zeros(len(dfr))
    for ix in dfr.groupby("rx_id").indices.values():
        out[ix] = l3.birth_density(dfr.iloc[ix])
    return out


def raws(tracker: l3.Tracker, df: pd.DataFrame) -> dict:
    """The 12 raw scores of the frozen stack on a V2AIX table (table order)."""
    r = {}
    for lay in l2.make_layers():
        if lay.name in L2_N and lay.name != "v2x.overlap":
            r[lay.name] = lay.raw_scores(df)
    run = tracker.run(df)
    r["v2x.kf_nis"], r["v2x.kf_cusum_hi"] = run["nis"], run["chi"]
    r["v2x.beacon_rate"] = l1.rate_hz(df) / LIMITS["RATE_MAX_HZ"]
    r["v2x.field_ranges"] = l1.FieldRanges().raw_scores(df)
    dfr = df.assign(t=df["recv_s"].to_numpy(float))
    r["v2x.overlap"] = l2.overlap_depth(dfr)
    r["v2x.track_birth"] = birth_per_recording(dfr)
    return {n: np.asarray(r[n], dtype=np.float32) for n in LAYER_NAMES}


class Calib:
    """Per-check ECDF calibrators and tie-safe thresholds, plus the combined (max) threshold, for one environment."""

    def __init__(self, cal, thr, comb_thr, name):
        self.cal, self.thr, self.comb_thr, self.name = cal, thr, comb_thr, name

    @classmethod
    def frozen(cls, dom):
        return cls(dom.cal, dom.thr, dom.comb_thr, "A_frozen_veremi")

    @classmethod
    def fit(cls, rw: dict, genuine, budget=BUDGET, name="B_v2aix_val"):
        g = np.asarray(genuine, bool)
        cal, thr = {}, {}
        for n in LAYER_NAMES:
            v = np.asarray(rw[n], float)
            cal[n] = ECDFCalibrator().fit(v[g])
            thr[n] = float(budget_threshold(cal[n].transform(v[g]), budget))
        c = cls(cal, thr, None, name)
        comb = c.combined(c.calibrated(rw), LAYER_NAMES)
        c.comb_thr = float(budget_threshold(comb[g], budget))
        return c

    def calibrated(self, rw: dict) -> dict:
        return {n: self.cal[n].transform(np.asarray(rw[n], float)) for n in LAYER_NAMES}

    @staticmethod
    def combined(cal: dict, names) -> np.ndarray:
        return np.max(np.stack([cal[n] for n in names]), axis=0)

    def layer_alarms(self, cal: dict) -> dict:
        return {n: cal[n] >= self.thr[n] for n in LAYER_NAMES}

    def alarm(self, cal: dict):
        return self.combined(cal, LAYER_NAMES) >= self.comb_thr


def group_threshold(cal: dict, names, genuine, budget=BUDGET) -> float:
    """Tie-safe threshold of the max of calibrated scores of `names` at `budget` of the genuine rows."""
    g = np.asarray(genuine, bool)
    return float(budget_threshold(Calib.combined(cal, names)[g], budget))


def recording_hours(df: pd.DataFrame) -> float:
    """Receiver time covered by the recordings: sum over recordings of (last - first reception) in hours."""
    span = df.groupby("recording")["recv_s"].agg(lambda s: s.max() - s.min())
    return float(span.sum() / 3600.0)


def sender_counts(df: pd.DataFrame, alarm) -> pd.DataFrame:
    d = pd.DataFrame({"sender": df["sender"].to_numpy(), "a": np.asarray(alarm, bool)})
    return d.groupby("sender", sort=False)["a"].agg(n="size", n_alarm="sum")


def k_for_budget(counts_genuine: pd.Series, budget=BUDGET, k_max=500) -> int:
    """Smallest k >= 1 such that at most `budget` of the genuine senders have >= k alarms."""
    n = len(counts_genuine)
    for k in range(1, k_max):
        if (counts_genuine >= k).sum() <= budget * n:
            return k
    return k_max


def alarm_events(df: pd.DataFrame, alarm, gap_s=10.0) -> int:
    """Alarm events: alarms of one sender merged when closer than gap_s in generation time."""
    d = pd.DataFrame({"sender": df["sender"].to_numpy(), "t": df["t"].to_numpy(float)})[np.asarray(alarm, bool)]
    if not len(d):
        return 0
    d = d.sort_values(["sender", "t"], kind="stable")
    new = (d["sender"].to_numpy()[1:] != d["sender"].to_numpy()[:-1]) | (np.diff(d["t"].to_numpy()) > gap_s)
    return int(1 + new.sum())


def boot_rate(df: pd.DataFrame, hit, B=1000, seed=42):
    """Rate = mean(hit) with a 95% cluster bootstrap over recordings. Returns (p, lo, hi, n)."""
    hit = np.asarray(hit, float)
    code, _ = pd.factorize(df["recording"])
    nb = code.max() + 1
    H = np.bincount(code, weights=hit, minlength=nb)
    N = np.bincount(code, minlength=nb).astype(float)
    rng = np.random.RandomState(seed)
    idx = rng.randint(0, nb, (B, nb))
    r = H[idx].sum(1) / np.maximum(N[idx].sum(1), 1)
    return float(H.sum() / max(N.sum(), 1)), float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5)), int(N.sum())
