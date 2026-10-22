"""WP6 S1: V2X motion reports -> MotionEstimate (source "v2x").

Purpose: a BSM / CAM carries the sender's own position, speed, heading and (sometimes) yaw rate. For the EGO vehicle, its
own outgoing BSM is a self-report that could be compared with the in-vehicle witnesses; for other vehicles, the same
conversion gives their claimed motion (used by WP5 / later steps, not by the ego witness layer).
Data reality (S1): no data set in the project has the ego's own BSM / CAM together with GPS / LiDAR / CAN logs of the same
car (VeReMi here = combined received-message CSV without receiver records; Tampa = RSU-heard BSMs; V2AIX pending). So V2X
gives OTHER vehicles' motion only and no ego pair is evaluable in S1. An ego BSM is built from the ego GNSS: even if it were
logged it would not be independent of the GPS claim (a GPS spoof propagates into it); it can only reveal a tampered V2X stack.
Inputs: one track of the WP5 schema (v2x/schema.py: t, x, y East-North m, speed m/s, heading rad math convention, yaw_rate,
spd_sigma). Output: list of MotionEstimate, one per message after the first whose predecessor is <= max_dt s older:
speed = reported speed, yaw_rate = reported (NaN -> None), displacement = position change since the previous message
rotated into the body frame of the previous reported heading and scaled to 1 s, sigma = spd_sigma if finite else default.
"""
import numpy as np

from common.motion import MotionEstimate

DEFAULT_SIGMA = 0.45     # same as the GPS claim (a BSM speed comes from the sender's GNSS)


def bsm_motion_estimates(track, max_dt=1.5, default_sigma=DEFAULT_SIGMA):
    t = track["t"].to_numpy(float)
    x, y = track["x"].to_numpy(float), track["y"].to_numpy(float)
    sp, hd = track["speed"].to_numpy(float), track["heading"].to_numpy(float)
    yr = track["yaw_rate"].to_numpy(float) if "yaw_rate" in track else np.full(len(t), np.nan)
    ss = track["spd_sigma"].to_numpy(float) if "spd_sigma" in track else np.full(len(t), np.nan)
    out = []
    for k in range(1, len(t)):
        dt = t[k] - t[k - 1]
        if not (0 < dt <= max_dt):
            continue
        de, dn = x[k] - x[k - 1], y[k] - y[k - 1]
        h = hd[k - 1] if np.isfinite(hd[k - 1]) else np.arctan2(dn, de)
        fwd = (de * np.cos(h) + dn * np.sin(h)) / dt
        left = (-de * np.sin(h) + dn * np.cos(h)) / dt
        out.append(MotionEstimate(t=float(t[k]), source="v2x", speed=float(sp[k]),
                                  yaw_rate=float(yr[k]) if np.isfinite(yr[k]) else None,
                                  displacement=(float(fwd), float(left)),
                                  sigma=float(ss[k]) if np.isfinite(ss[k]) and ss[k] > 0 else default_sigma))
    return out
