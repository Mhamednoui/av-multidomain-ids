"""B2: the v2 dead-reckoning rule as a v3 Layer (gps.dr_resid_10), inside the deployable gps/ package.

Purpose: the GPS position change over the last 10 fixes must match the position change obtained by integrating the vehicle's own
odometry speed along its compass heading (dead reckoning). Raw score = the residual in metres; a fix at which the reported position
did not move although the odometer says the car moves ("still" flag) gets a huge score (freeze detector).
Inputs: stream columns x, y, odo_speed, heading, lat, lon, run. Outputs: columns dr_resid_10, still (features) and raw scores.
Copied from tools/WP1_S1_b2.py (b2_features, B2Layer; those are bit-identical to v2 / WP0 S3, tested in tests/gps/test_domain.py);
originally ../codes_v2/gps/kitti_external.py track(). It is the v2 baseline of the WP1 comparison.
"""
import numpy as np
import pandas as pd

from common.layer import Layer
from gps import stream as S

BIG = 1e6


def b2_features(df):
    """dr_resid_10 and still flag per run, from stream columns."""
    out = []
    for _, g in df.groupby("run", sort=False):
        rep = g[["x", "y"]].to_numpy()
        n = len(g)
        sp, h = g["odo_speed"].to_numpy(), np.radians(g["heading"].to_numpy())
        v_mid = np.r_[0, (sp[1:] + sp[:-1]) / 2]
        u = np.c_[np.sin(h), np.cos(h)]
        u_mid = np.r_[[[0, 0]], (u[1:] + u[:-1]) / 2]
        dr = np.cumsum(v_mid[:, None] * u_mid, axis=0)
        lag = np.maximum(np.arange(n) - 10, 0)
        resid = np.hypot(*((rep - rep[lag]) - (dr - dr[lag])).T)
        lat = g["lat"]
        dlat = lat.diff() * S.M_PER_DEG
        dlon = g["lon"].diff() * S.M_PER_DEG * np.cos(np.radians(lat.fillna(0)))
        step = np.sqrt(dlat ** 2 + dlon ** 2)
        still = ((step < 0.05) & (g["odo_speed"] > 0.5)).astype(float).to_numpy()
        out.append(pd.DataFrame({"dr_resid_10": np.nan_to_num(resid), "still": still}, index=g.index))
    return pd.concat(out).loc[df.index]


class B2Layer(Layer):
    """v2 dead-reckoning rule as a v3 layer."""
    domain = "gps"
    name = "gps.dr_resid_10"
    kind = "physics"
    layer_id = "L2a"

    def raw_scores(self, samples):
        raw = samples["dr_resid_10"].to_numpy(dtype=float).copy()
        raw[samples["still"].to_numpy() > 0] = BIG
        return raw

    def reasons(self, samples, raw, alarm):
        return ["GPS and vehicle motion disagree (dead-reckoning residual or frozen position)"] * len(raw)
