"""WP5 S3b: receiver-position checks for V2X (acceptance range, sudden appearance), as v3 Layers (domain "v2x", layer "L2", kind "rule").

Purpose: the two deferred checks that need the receiver position (rx_x, rx_y). Evaluated on V2AIX CAMs with the ego GNSS (or the fixed unit) as receiver.
 - AcceptanceRange   v2x.acceptance_range   raw = distance d between the claimed sender position and the receiver (km). A message received from farther
                                            than any genuine sender was ever heard is implausible (radio range; wormhole / far spoof). The threshold is
                                            DATA-DRIVEN: tie-safe 1% of the genuine validation messages of the environment (V2AIX reach is km-scale, not
                                            the 300-1000 m of 802.11p textbooks; see reports/WP5_S3b.md for the geometry gate that precedes its use).
 - AppearanceData    v2x.appearance_data    raw = 1 / (1 + d / 100 m) for the EVALUABLE first message of a track (the track starts at least GRACE_S seconds after
                                            the first message of its recording, i.e. the receiver was already listening, and the receiver position is known), 0
                                            otherwise: a real vehicle enters radio range at its edge, so a first message close to the receiver is suspicious.
                                            Threshold: tie-safe 1% of the genuine validation evaluable first messages (the layer's own population).
 - appearance_physical: the frozen v2x.l1 SuddenAppearance (R_EDGE = 300 m) restricted to the evaluable first messages, for the transfer demonstration.
Non-evaluable rows (rx NaN, track not evaluable) score 0 and never alarm. Causal: a message uses its own distance and, for the appearance, the first-message flag of its
track (decided when the track starts); no future message. A batch must hold whole recordings (the recording start is the earliest reception in the batch for
that rx_id).
Inputs: unified table with rx_x, rx_y, rx_id, track, t, recv_s (reception time, logger clock). Outputs: raw scores, Layer.score Evidence after calibrate_fit().
References: Kamel et al., F2MD (IEEE TVT 2020: acceptance range, sudden appearance); VeReMi (van der Heijden 2018).
"""
import numpy as np
import pandas as pd

from common.calibration import ECDFCalibrator
from common.layer import Layer
from common.metrics import budget_threshold

GRACE_S = 5.0
R_EDGE_M = 300.0


def distance_to_receiver(df) -> np.ndarray:
    """Sender-to-receiver distance (m); NaN when the receiver position is unknown."""
    return np.hypot(df["x"].to_numpy(float) - df["rx_x"].to_numpy(float), df["y"].to_numpy(float) - df["rx_y"].to_numpy(float))


def first_flags(df, grace_s=GRACE_S):
    """(first, evaluable): first = earliest-received message of its track; evaluable = first AND finite receiver position AND received at least grace_s after the
    first reception of its recording (rx_id) in this table."""
    n = len(df)
    if n == 0:
        return np.zeros(0, bool), np.zeros(0, bool)
    trk = pd.factorize(df["track"])[0]
    rt = df["recv_s"].to_numpy(float)
    order = np.lexsort((np.arange(n), rt, trk))
    first = np.zeros(n, bool)
    cs = trk[order]
    first[order[0]] = True
    first[order[1:][cs[1:] != cs[:-1]]] = True
    start = df.groupby("rx_id")["recv_s"].transform("min").to_numpy(float)
    finite = np.isfinite(df["rx_x"].to_numpy(float)) & np.isfinite(df["rx_y"].to_numpy(float))
    return first, first & finite & (rt - start >= grace_s)


class _RxLayer(Layer):
    domain, kind, layer_id = "v2x", "rule", "L2"
    physical = False

    def evaluable(self, df):
        return bool(np.isfinite(df["rx_x"].to_numpy(float)).any())

    def calibrate_fit(self, val_df, genuine_mask, budget=0.01):
        """ECDF + tie-safe budget threshold on the genuine validation rows of the layer's own population (self.population)."""
        raw = np.asarray(self.raw_scores(val_df), float)
        pop = np.asarray(genuine_mask, bool) & self.population(val_df)
        if pop.sum() == 0:
            self.calibrator, self.threshold, self.budget = None, np.inf, budget
            return self
        self.calibrator = ECDFCalibrator().fit(raw[pop])
        self.budget = budget
        self.threshold = budget_threshold(self.calibrator.transform(raw[pop]), budget)
        return self

    def calibrated(self, df):
        raw = np.asarray(self.raw_scores(df), float)
        if self.calibrator is None:
            return np.zeros(len(df))
        return np.where(self.population(df), self.calibrator.transform(raw), 0.0)

    def alarms(self, df):
        return self.calibrated(df) >= self.threshold if np.isfinite(self.threshold) else np.zeros(len(df), bool)


class AcceptanceRange(_RxLayer):
    name = "v2x.acceptance_range"

    def raw_scores(self, df):
        return np.nan_to_num(distance_to_receiver(df), nan=0.0) / 1000.0

    def population(self, df):
        return np.isfinite(distance_to_receiver(df))

    def reasons(self, df, raw, alarm):
        return [f"message received from {r:.1f} km, farther than any genuine sender was heard" for r in raw]


class AppearanceData(_RxLayer):
    name = "v2x.appearance_data"

    def raw_scores(self, df):
        _, ev = first_flags(df)
        d = np.nan_to_num(distance_to_receiver(df), nan=1e9)
        return np.where(ev, 1.0 / (1.0 + d / 100.0), 0.0)

    def population(self, df):
        return first_flags(df)[1]

    def reasons(self, df, raw, alarm):
        return [f"new sender first heard {100.0 * (1.0 / max(r, 1e-9) - 1.0):.0f} m from the receiver, closer than genuine senders first appear" for r in raw]


def appearance_physical_alarm(df) -> np.ndarray:
    """Frozen design value: evaluable first message heard closer than R_EDGE_M."""
    _, ev = first_flags(df)
    d = distance_to_receiver(df)
    return ev & (np.nan_to_num(d, nan=1e9) < R_EDGE_M)
