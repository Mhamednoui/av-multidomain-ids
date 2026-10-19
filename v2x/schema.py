"""Unified V2X message schema (WP5 S1) and the VeReMi Extension class map.

Purpose: one table format for received BSM / CAM messages from any source (VeReMi, Tampa BSM,
V2AIX CAM), so layers L1-L4 never care where a message came from.
Inputs: none (constants + validate()). Output: validate(df) raises ValueError on a bad table.
Units: SI. x, y metres in a local East-North frame; heading radians, mathematical convention
(0 = East, counter-clockwise positive); speed m/s (scalar >= 0); acl m/s^2 along the heading;
yaw_rate rad/s (counter-clockwise positive); t seconds (stream time of the message).
References: Kamel et al., "VeReMi Extension" (ICC 2020); SAE J2735 BSM; ETSI EN 302 637-2 CAM.
"""
import numpy as np
import pandas as pd

COLUMNS = ["msg_id", "source", "sender", "pseudo", "track", "t", "x", "y", "speed", "vx", "vy",
           "heading", "acl", "yaw_rate", "pos_sigma", "spd_sigma", "acl_sigma",
           "rx_id", "rx_x", "rx_y", "lat", "lon", "label", "attack", "injected"]
TEXT = ("msg_id", "source", "sender", "pseudo", "track", "rx_id", "attack")
NUMERIC = ["t", "x", "y", "speed", "vx", "vy", "heading", "acl", "yaw_rate", "pos_sigma",
           "spd_sigma", "acl_sigma", "rx_x", "rx_y", "lat", "lon"]
REQUIRED_FINITE = ["t", "x", "y", "speed"]   # the rest may be NaN when a source lacks it

# VeReMi Extension class ids (Kamel et al. 2020; F2MD). See reports/WP5_S1.md for the evidence.
CLASS_NAMES = {
    0: "Genuine", 1: "ConstPos", 2: "ConstPosOffset", 3: "RandomPos", 4: "RandomPosOffset",
    5: "ConstSpeed", 6: "ConstSpeedOffset", 7: "RandomSpeed", 8: "RandomSpeedOffset",
    9: "EventualStop", 10: "Disruptive", 11: "DataReplay", 12: "DelayedMessages", 13: "DoS",
    14: "DoSRandom", 15: "DoSDisruptive", 16: "GridSybil", 17: "DataReplaySybil",
    18: "DoSRandomSybil", 19: "DoSDisruptiveSybil",
}
NAME_TO_ID = {v: k for k, v in CLASS_NAMES.items()}


class DataNotAvailableError(RuntimeError):
    """A dataset adapter was called but the data has not been obtained (e.g. V2AIX access form)."""


def validate(df: pd.DataFrame, sorted_per_track: bool = True) -> None:
    miss = [c for c in COLUMNS if c not in df.columns]
    if miss:
        raise ValueError(f"missing columns: {miss}")
    for c in NUMERIC:
        if not np.issubdtype(df[c].dtype, np.floating):
            raise ValueError(f"column {c} must be float, is {df[c].dtype}")
    for c in REQUIRED_FINITE:
        if not np.isfinite(df[c].to_numpy()).all():
            raise ValueError(f"non-finite values in {c}")
    if (df["speed"] < 0).any():
        raise ValueError("negative speed")
    if df["msg_id"].duplicated().any():
        raise ValueError("duplicate msg_id")
    if not df["label"].isin(list(CLASS_NAMES)).all():
        raise ValueError("label outside 0..19")
    if sorted_per_track and len(df):
        dt = df.groupby("track", sort=False)["t"].diff().dropna()
        if (dt < 0).any():
            raise ValueError("time goes backwards inside a track")
