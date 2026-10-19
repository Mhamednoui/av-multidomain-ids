"""WP5 S2: L1 message checks for V2X, as v3 Layers (domain "v2x", layer "L1", kind "rule").

Purpose: cheap per-sender checks that need no model and no attack data. Four layers:
 - BeaconRate        v2x.beacon_rate        instantaneous rate 1/dt of a track (consecutive messages of one
                                            claimed identity), divided by the standard maximum RATE_MAX_HZ.
                                            Threshold: validation genuine messages (data-driven, 1% budget).
 - Freshness         v2x.freshness          (a) age = receive time - generation time when the table has `age_s`
                                            (outside [-AGE_FUTURE_TOL, +inf) is future-dated / stale), (b) timestamp
                                            older than one already received on the same track (arrival order = row order).
                                            Threshold: validation genuine (data-driven).
 - FieldRanges       v2x.field_ranges       max(speed / V_MAX, |acceleration| / A_MAX, |yaw rate| / yaw limit). raw >= 1 is
                                            a physical violation (no fitted threshold: "physical operating point");
                                            the harness also uses the calibrated score (1% budget) for AUC / ablation.
 - SuddenAppearance  v2x.sudden_appearance  first message of a track heard closer than R_EDGE to the receiver
                                            (a real vehicle enters radio range at its edge). Needs rx_x, rx_y; NaN -> raw 0
                                            and evaluable() is False.
All layers are causal per track: the score of a message uses only that track's earlier messages (row k uses rows <= k of
its track; time order for rate / sudden appearance, row order for the freshness ordering part). The state is derived
from the `track` column of the batch, so a batch must contain whole tracks; reset() has nothing to clear.

Inputs: unified message table (v2x/schema.py) with optional extra column `age_s` (Tampa: RSU log time - generation time)
and `sample_id`. Outputs: list[Evidence] via Layer.score.

Physical limits and sources (fixed before any S2 result, never fitted):
  RATE_MAX_HZ 10   BSM / CAM maximum generation rate: SAE J2945/1 (2016) BSM at 10 Hz; ETSI EN 302 637-2 V1.4.1 CAM
                   T_GenCam_Min = 100 ms (range 1-10 Hz). 5% timing tolerance (RATE_TOL) for the physical alarm.
  TIME_RES_S 1e-3  timestamp resolution: ETSI generationDeltaTime and SAE J2735 DSecond are in milliseconds; dt is rounded to it.
  V_MAX 70 m/s     (252 km/h) electronically limited top speed of road cars (VDA voluntary 250 km/h commitment); the encodings
                   allow more (J2735 speed 8191 x 0.02 = 163.8 m/s; ETSI speed 16382 x 0.01 m/s) but no road AV drives faster.
  A_MAX 1.3 g      longitudinal / lateral acceleration of a road car on tyres: friction limit ~1.0-1.2 g (Wong, Theory of Ground
                   Vehicles, 4th ed., ch. 1-3; Rajamani, Vehicle Dynamics and Control), 1.3 g allows the fastest production launches.
                   Encodings: ETSI longitudinal acceleration +-16 m/s^2, SAE J2735 +-20 m/s^2 (both above 1.3 g = 12.7 m/s^2).
  R_MIN 5 m        minimum turn radius of a passenger car (Ackermann geometry): |yaw rate| <= v / R_MIN when v >= YAW_MIN_SPEED;
                   below it the J2735 yaw rate range (+-327.67 deg/s = 5.72 rad/s) is used.
  R_EDGE 300 m     design value, not a standard: 802.11p / DSRC vehicle-to-vehicle range is ~300-1000 m (Kenney, "Dedicated
                   short-range communications (DSRC) standards in the United States", Proc. IEEE 99(7), 2011). A vehicle first
                   heard at < R_EDGE has appeared "suddenly" (pseudonym change, trip start and Sybil ghosts also do, which is
                   why this is an indicator and not proof).
  AGE_FUTURE_TOL 1 s  the Tampa RSU log time has 1 s resolution, so a timestamp up to 1 s later than the log time is not "future".
Limitations: the limits are bounds, not typical values, so FieldRanges only fires on gross impossibilities; most
position / speed falsification in the VeReMi taxonomy is inside them (this is expected and reported).
References: Kamel et al., VeReMi Extension (ICC 2020); van der Heijden et al., VeReMi (2018); ARCHITECTURE.md sections 2-4.
"""
import numpy as np
import pandas as pd

from common.layer import Layer

G = 9.80665
LIMITS = {
    "RATE_MAX_HZ": 10.0,
    "RATE_TOL": 1.05,
    "TIME_RES_S": 1e-3,
    "V_MAX": 70.0,
    "A_MAX": 1.3 * G,
    "R_MIN": 5.0,
    "YAW_MIN_SPEED": 3.0,
    "YAW_CAP": np.radians(327.67),
    "R_EDGE": 300.0,
    "AGE_FUTURE_TOL": 1.0,
}


def _col(df, name, default=np.nan):
    return df[name].to_numpy(dtype=float) if name in df.columns else np.full(len(df), default)


def _track_codes(df):
    return pd.factorize(df["track"])[0]


def rate_hz(df) -> np.ndarray:
    """Instantaneous rate 1/dt of each message vs the previous message of its track (time order);
    0 for the first message of a track. dt rounded to the timestamp resolution, floored at it."""
    n = len(df)
    codes, t = _track_codes(df), df["t"].to_numpy(dtype=float)
    order = np.lexsort((t, codes))
    c, ts = codes[order], t[order]
    dt = np.zeros(n)
    dt[1:] = np.round(np.diff(ts), 3)
    first = np.ones(n, bool)
    first[1:] = c[1:] != c[:-1]
    rate = np.where(first, 0.0, 1.0 / np.maximum(dt, LIMITS["TIME_RES_S"]))
    out = np.empty(n)
    out[order] = rate
    return out


def first_in_track(df) -> np.ndarray:
    """True for the earliest message (by time) of each track."""
    codes, t = _track_codes(df), df["t"].to_numpy(dtype=float)
    order = np.lexsort((t, codes))
    c = codes[order]
    first = np.ones(len(df), bool)
    first[1:] = c[1:] != c[:-1]
    out = np.empty(len(df), bool)
    out[order] = first
    return out


class BeaconRate(Layer):
    domain, name, kind, layer_id = "v2x", "v2x.beacon_rate", "rule", "L1"
    physical = False

    def raw_scores(self, df):
        return rate_hz(df) / LIMITS["RATE_MAX_HZ"]

    def physical_alarm(self, df):
        """Standard maximum exceeded (with the 5% tolerance): not used for calibration."""
        return self.raw_scores(df) > LIMITS["RATE_TOL"]

    def evaluable(self, df):
        return True

    def reasons(self, df, raw, alarm):
        return [f"claimed sender transmits at {r * LIMITS['RATE_MAX_HZ']:.1f} Hz, above its normal beacon rate" for r in raw]


class Freshness(Layer):
    domain, name, kind, layer_id = "v2x", "v2x.freshness", "rule", "L1"
    physical = False

    def raw_scores(self, df):
        n = len(df)
        age = _col(df, "age_s")
        late = np.where(np.isfinite(age), np.maximum(age, 0.0), 0.0)
        future = np.where(np.isfinite(age), np.maximum(-age - LIMITS["AGE_FUTURE_TOL"], 0.0), 0.0)
        t = pd.Series(df["t"].to_numpy(dtype=float))
        tr = _track_codes(df)
        prev_max = t.groupby(tr).cummax().groupby(tr).shift(1).to_numpy()   # arrival order = row order
        back = np.where(np.isfinite(prev_max), np.maximum(prev_max - t.to_numpy(), 0.0), 0.0)
        dup = np.isfinite(prev_max) & (prev_max == t.to_numpy())
        back = np.where(dup, LIMITS["TIME_RES_S"], back)
        return np.maximum.reduce([late, future, back]) if n else np.zeros(0)

    def evaluable(self, df):
        """Age is evaluable only with a receive time (column age_s); ordering needs arrival order (not checked here)."""
        return "age_s" in df.columns and bool(np.isfinite(df["age_s"].to_numpy(dtype=float)).any())

    def reasons(self, df, raw, alarm):
        return [f"message is {r:.1f} s older than its receive time or than an earlier message of the same sender" for r in raw]


class FieldRanges(Layer):
    domain, name, kind, layer_id = "v2x", "v2x.field_ranges", "rule", "L1"
    physical = True

    def raw_scores(self, df):
        v = _col(df, "speed", 0.0)
        a = np.nan_to_num(np.abs(_col(df, "acl")), nan=0.0)
        yaw = np.nan_to_num(np.abs(_col(df, "yaw_rate")), nan=0.0)
        ylim = np.where(v >= LIMITS["YAW_MIN_SPEED"], v / LIMITS["R_MIN"], LIMITS["YAW_CAP"])
        return np.maximum.reduce([np.nan_to_num(v, nan=0.0) / LIMITS["V_MAX"], a / LIMITS["A_MAX"], yaw / ylim])

    def physical_alarm(self, df):
        return self.raw_scores(df) >= 1.0

    def evaluable(self, df):
        return True

    def reasons(self, df, raw, alarm):
        return [f"speed, acceleration or yaw rate is {r:.2f} times the physical limit of a road vehicle" for r in raw]


class SuddenAppearance(Layer):
    domain, name, kind, layer_id = "v2x", "v2x.sudden_appearance", "rule", "L1"
    physical = False

    def raw_scores(self, df):
        rx, ry = _col(df, "rx_x"), _col(df, "rx_y")
        d = np.hypot(df["x"].to_numpy(dtype=float) - rx, df["y"].to_numpy(dtype=float) - ry)
        close = np.where(np.isfinite(d), np.maximum(1.0 - d / LIMITS["R_EDGE"], 0.0), 0.0)
        return np.where(first_in_track(df), close, 0.0)

    def physical_alarm(self, df):
        return self.raw_scores(df) > 0.0

    def evaluable(self, df):
        return bool(np.isfinite(_col(df, "rx_x")).any() and np.isfinite(_col(df, "rx_y")).any())

    def reasons(self, df, raw, alarm):
        return [f"new sender first heard {(1 - r) * LIMITS['R_EDGE']:.0f} m from the receiver, inside the normal entry distance" for r in raw]


def make_layers():
    return [BeaconRate(), Freshness(), FieldRanges(), SuddenAppearance()]
