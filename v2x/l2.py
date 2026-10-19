"""WP5 S3: L2 plausibility checks for V2X (F2MD style), as v3 Layers (domain "v2x", layer "L2", kind "physics").

Purpose: per-sender plausibility from consecutive beacons, kinematic consistency, overlapping vehicles and map
plausibility. No model, no attack data. Nine Layers:
 - PosSpeed          v2x.pos_speed          |d - mean(v_k, v_k-1) * dt|        displacement vs reported speed x dt (m)
 - PosHeading        v2x.pos_heading        angle(mean heading, displacement bearing) x d/(d+2 m), speeds >= 3 m/s (rad)
 - SpeedChange       v2x.speed_change       |dv| / (dt * A_MAX)                physical: raw >= 1
 - ImpliedSpeed      v2x.implied_speed      d / (dt * V_MAX)                   physical: raw >= 1
 - HeadingRate       v2x.heading_rate       |dh|/dt divided by yaw limit v/R_MIN, speeds >= 3 m/s     physical: raw >= 1
 - AccelConsistency  v2x.accel_consistency  |mean reported acl - dv/dt|        (m/s^2), needs acl
 - YawConsistency    v2x.yaw_consistency    |mean reported yaw rate - dh/dt|   (rad/s), speeds >= 3 m/s, needs yaw_rate
 - Overlap           v2x.overlap            penetration depth / vehicle width of the oriented 4.5 x 1.8 m footprints of two
                                            different tracks (the other track dead-reckoned to the current time, <= 1 s old)
 - MapRoad           v2x.map_road           distance (m) to the nearest drivable OSM way (needs a road tree; Tampa only)
Causal: the score of message k uses only earlier messages (same track for the pair checks; other tracks no later than k
in (time, row) order for overlap). dt = t_k - t_k-1 of the track rounded to 1 ms; a pair is evaluated only if
0 < dt <= DT_MAX, otherwise raw = 0. A batch must contain whole tracks (and, for overlap, the neighbouring traffic).
Thresholds: data-driven on validation genuine (1% budget, tie-safe) via calibrate_masked(); physical operating point
(raw >= 1) for the three checks that are limit ratios. Limits are those of v2x/l1.py LIMITS (sources in its docstring).

Constants and sources (fixed before any S3 result):
  DT_MAX 5 s      same gap rule that starts a new Tampa track segment (v2x/adapters.py).
  V_HEAD_MIN 3 m/s  below it the heading of a vehicle is undefined (standing, GPS heading is noise); equals YAW_MIN_SPEED of L1.
  D0 2 m          soft gate of the bearing: a displacement of a few metres has no reliable direction under GPS noise of the
                  same order (VeReMi sigma ~4 m per axis, Tampa ~1-2 m). Design constant.
  CAR_L 4.5 m, CAR_W 1.8 m  footprint of a typical passenger car (EU/US fleet average length 4.4-4.8 m, width 1.8-1.9 m;
                  ETSI TS 102 894-2 vehicle length / width data elements allow 0.1-102.3 m / 0.1-6.2 m).
  W_OVERLAP 1 s   the other vehicle's last message may be at most one beacon interval (VeReMi 1 Hz) old.
Reference: Kamel et al., "Simulation Framework for Misbehavior Detection in Vehicular Networks", IEEE TVT 2020
(F2MD: position / speed / heading plausibility, intersection check, kinematic consistency); VeReMi Extension (ICC 2020).
OSM: (c) OpenStreetMap contributors, ODbL 1.0 (../data_extra/D27_osm_tampa).
"""
import json

import numpy as np
import pandas as pd

from common.calibration import ECDFCalibrator
from common.layer import Layer
from common.metrics import budget_threshold
from v2x.l1 import LIMITS as L1

DT_MAX = 5.0
V_HEAD_MIN = 3.0
D0 = 2.0
CAR_L, CAR_W = 4.5, 1.8
W_OVERLAP = 1.0
TWO_PI = 2 * np.pi


def _col(df, name, default=np.nan):
    return df[name].to_numpy(dtype=float) if name in df.columns else np.full(len(df), default)


def wrap(a):
    return (a + np.pi) % TWO_PI - np.pi


class Pairs:
    """Consecutive-message pairs of each track. Arrays are in track/time order; `put` maps back to the table row order."""

    def __init__(self, df):
        n = len(df)
        codes = pd.factorize(df["track"])[0]
        t = df["t"].to_numpy(dtype=float)
        self.order = np.lexsort((t, codes))
        o = self.order
        self.n = n
        c, ts = codes[o], t[o]
        self.dt = np.zeros(n)
        self.dt[1:] = np.round(np.diff(ts), 3)
        same = np.zeros(n, bool)
        same[1:] = c[1:] == c[:-1]
        self.valid = same & (self.dt > 0) & (self.dt <= DT_MAX)
        self.cur, self.prev = {}, {}
        for k in ("x", "y", "speed", "heading", "acl", "yaw_rate"):
            v = _col(df, k)[o]
            self.cur[k] = v
            p = np.empty(n)
            p[1:], p[0] = v[:-1], np.nan
            self.prev[k] = p
        self.dx = self.cur["x"] - self.prev["x"]
        self.dy = self.cur["y"] - self.prev["y"]
        self.d = np.hypot(self.dx, self.dy)

    def put(self, vals, valid=None):
        """vals in sorted order -> table order; invalid / non-finite -> 0."""
        v = np.where(self.valid if valid is None else valid, vals, 0.0)
        v = np.nan_to_num(v, nan=0.0, posinf=1e9, neginf=0.0)
        out = np.empty(self.n)
        out[self.order] = v
        return out

    def moving(self):
        return np.minimum(self.cur["speed"], self.prev["speed"]) >= V_HEAD_MIN


class _L2(Layer):
    domain, kind, layer_id = "v2x", "physics", "L2"
    physical = False

    def evaluable(self, df):
        return True

    def reset(self):
        pass

    def calibrate_masked(self, frame, mask, budget):
        """Raw scores of the WHOLE frame (neighbours matter for overlap), calibration on the genuine rows `mask` only."""
        raw = np.asarray(self.raw_scores(frame), dtype=float)[np.asarray(mask, bool)]
        self.calibrator = ECDFCalibrator().fit(raw)
        self.budget = budget
        self.threshold = budget_threshold(self.calibrator.transform(raw), budget)
        return self

    def physical_alarm(self, df):
        raise NotImplementedError


class PosSpeed(_L2):
    name = "v2x.pos_speed"

    def raw_scores(self, df):
        p = Pairs(df)
        vbar = 0.5 * (p.cur["speed"] + p.prev["speed"])
        return p.put(np.abs(p.d - vbar * p.dt))

    def reasons(self, df, raw, alarm):
        return [f"displacement between two beacons differs by {r:.1f} m from reported speed x time" for r in raw]


class PosHeading(_L2):
    name = "v2x.pos_heading"

    def raw_scores(self, df):
        p = Pairs(df)
        bearing = np.arctan2(p.dy, p.dx)
        a = np.abs(wrap(p.cur["heading"] - bearing))
        b = np.abs(wrap(p.prev["heading"] - bearing))
        ang = 0.5 * (a + b)
        return p.put(ang * p.d / (p.d + D0), p.valid & p.moving())

    def reasons(self, df, raw, alarm):
        return [f"movement direction differs from the reported heading by {np.degrees(r):.0f} degrees" for r in raw]


class SpeedChange(_L2):
    name = "v2x.speed_change"
    physical = True

    def raw_scores(self, df):
        p = Pairs(df)
        return p.put(np.abs(p.cur["speed"] - p.prev["speed"]) / (p.dt * L1["A_MAX"]))

    def physical_alarm(self, df):
        return self.raw_scores(df) >= 1.0

    def reasons(self, df, raw, alarm):
        return [f"speed changed {r:.1f} times faster than a road vehicle can accelerate or brake" for r in raw]


class ImpliedSpeed(_L2):
    name = "v2x.implied_speed"
    physical = True

    def raw_scores(self, df):
        p = Pairs(df)
        return p.put(p.d / (p.dt * L1["V_MAX"]))

    def physical_alarm(self, df):
        return self.raw_scores(df) >= 1.0

    def reasons(self, df, raw, alarm):
        return [f"position moved at {r * L1['V_MAX']:.0f} m/s between two beacons" for r in raw]


class HeadingRate(_L2):
    name = "v2x.heading_rate"
    physical = True

    def raw_scores(self, df):
        p = Pairs(df)
        v = np.maximum(p.cur["speed"], p.prev["speed"])
        lim = v / L1["R_MIN"]
        rate = np.abs(wrap(p.cur["heading"] - p.prev["heading"])) / p.dt
        return p.put(rate / lim, p.valid & p.moving())

    def physical_alarm(self, df):
        return self.raw_scores(df) >= 1.0

    def reasons(self, df, raw, alarm):
        return [f"heading turns {r:.1f} times faster than the tightest turn at this speed" for r in raw]


class AccelConsistency(_L2):
    name = "v2x.accel_consistency"

    def raw_scores(self, df):
        p = Pairs(df)
        a_rep = 0.5 * (p.cur["acl"] + p.prev["acl"])
        a_obs = (p.cur["speed"] - p.prev["speed"]) / p.dt
        return p.put(np.abs(a_rep - a_obs))

    def evaluable(self, df):
        return bool(np.isfinite(_col(df, "acl")).any())

    def reasons(self, df, raw, alarm):
        return [f"reported acceleration differs by {r:.1f} m/s^2 from the change of the reported speed" for r in raw]


class YawConsistency(_L2):
    name = "v2x.yaw_consistency"

    def raw_scores(self, df):
        p = Pairs(df)
        y_rep = 0.5 * (p.cur["yaw_rate"] + p.prev["yaw_rate"])
        y_obs = wrap(p.cur["heading"] - p.prev["heading"]) / p.dt
        return p.put(np.abs(y_rep - y_obs), p.valid & p.moving())

    def evaluable(self, df):
        return bool(np.isfinite(_col(df, "yaw_rate")).any())

    def reasons(self, df, raw, alarm):
        return [f"reported yaw rate differs by {r:.2f} rad/s from the change of the reported heading" for r in raw]


# ---------------------------------------------------------------------------------------------------------------
def _velocity(df):
    h = _col(df, "heading")
    vx, vy, sp = _col(df, "vx"), _col(df, "vy"), _col(df, "speed", 0.0)
    h = np.where(np.isfinite(h), h, np.where(np.isfinite(vx) & np.isfinite(vy), np.arctan2(vy, vx), 0.0))
    vx = np.where(np.isfinite(vx), vx, sp * np.cos(h))
    vy = np.where(np.isfinite(vy), vy, sp * np.sin(h))
    return h, vx, vy


def _penetration(c1, h1, c2, h2):
    """Minimum penetration depth of two oriented CAR_L x CAR_W rectangles (>= 0, 0 if disjoint); arrays of pairs."""
    a, b = CAR_L / 2, CAR_W / 2
    u1 = np.stack([np.cos(h1), np.sin(h1)], 1)
    n1 = np.stack([-np.sin(h1), np.cos(h1)], 1)
    u2 = np.stack([np.cos(h2), np.sin(h2)], 1)
    n2 = np.stack([-np.sin(h2), np.cos(h2)], 1)
    dc = c2 - c1
    depth = np.full(len(c1), np.inf)
    for e in (u1, n1, u2, n2):
        r1 = a * np.abs((u1 * e).sum(1)) + b * np.abs((n1 * e).sum(1))
        r2 = a * np.abs((u2 * e).sum(1)) + b * np.abs((n2 * e).sum(1))
        depth = np.minimum(depth, r1 + r2 - np.abs((dc * e).sum(1)))
    return np.maximum(depth, 0.0)


def overlap_depth(df):
    """Per message: max over other tracks (latest message <= W_OVERLAP earlier in (t, row) order, dead-reckoned to t_k) of the
    footprint penetration depth (m); 0 if nothing overlaps. Only tracks heard by the same receiver (column rx_id, if present)
    are compared: in the Tampa sample every id belongs to one RSU (the same vehicle appears under different ids at different
    RSUs with bit-identical messages), so a cross-receiver pair is one vehicle, not two."""
    n = len(df)
    out = np.zeros(n)
    if n == 0:
        return out
    t = df["t"].to_numpy(dtype=float)
    x, y = df["x"].to_numpy(dtype=float), df["y"].to_numpy(dtype=float)
    h, vx, vy = _velocity(df)
    trk = pd.factorize(df["track"])[0]
    rx = pd.factorize(df["rx_id"].astype(object).where(df["rx_id"].notna(), ""))[0] if "rx_id" in df.columns else np.zeros(n, int)
    order = np.lexsort((np.arange(n), t))
    t, x, y, h, vx, vy, trk, rx = t[order], x[order], y[order], h[order], vx[order], vy[order], trk[order], rx[order]
    slot = np.floor(t / W_OVERLAP).astype(np.int64)
    starts = np.r_[0, np.flatnonzero(np.diff(slot)) + 1]
    ends = np.r_[starts[1:], n]
    res = np.zeros(n)
    reach = CAR_L ** 2 + CAR_W ** 2
    for a, b in zip(starts, ends):
        lo = np.searchsorted(slot, slot[a] - 1, side="left")
        ks = np.arange(a, b)
        js = np.arange(lo, b)
        if len(js) < 2:
            continue
        kk, jj = np.meshgrid(ks, js, indexing="ij")
        kk, jj = kk.ravel(), jj.ravel()
        m = (jj < kk) & (trk[jj] != trk[kk]) & (rx[jj] == rx[kk]) & (t[kk] - t[jj] <= W_OVERLAP)
        kk, jj = kk[m], jj[m]
        if not len(kk):
            continue
        age = t[kk] - t[jj]
        xj, yj = x[jj] + vx[jj] * age, y[jj] + vy[jj] * age
        near = (xj - x[kk]) ** 2 + (yj - y[kk]) ** 2 < reach
        kk, jj, xj, yj, age = kk[near], jj[near], xj[near], yj[near], age[near]
        if not len(kk):
            continue
        o = np.lexsort((t[jj], trk[jj], kk))                 # latest message of each other track per k
        kk, jj, xj, yj = kk[o], jj[o], xj[o], yj[o]
        last = np.r_[(kk[1:] != kk[:-1]) | (trk[jj][1:] != trk[jj][:-1]), True]
        kk, jj, xj, yj = kk[last], jj[last], xj[last], yj[last]
        dep = _penetration(np.stack([x[kk], y[kk]], 1), h[kk], np.stack([xj, yj], 1), h[jj])
        np.maximum.at(res, kk, dep)
    out[order] = res / CAR_W
    return out


class Overlap(_L2):
    name = "v2x.overlap"

    def raw_scores(self, df):
        return overlap_depth(df)

    def reasons(self, df, raw, alarm):
        return [f"two different senders claim the same road space (overlap {r * CAR_W:.1f} m)" for r in raw]


# ---------------------------------------------------------------------------------------------------------------
def build_road_tree(path, lat0, lon0, step=1.0):
    """cKDTree of points every <= `step` m along the OSM drivable ways, in the local frame of v2x/adapters (same lat0, lon0)."""
    from scipy.spatial import cKDTree
    d = json.loads(open(path, encoding="utf-8").read())
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in d["elements"] if e["type"] == "node"}
    m = 111320.0
    pts = []
    for e in d["elements"]:
        if e["type"] != "way":
            continue
        ll = np.array([nodes[i] for i in e["nodes"] if i in nodes], dtype=float)
        if len(ll) < 2:
            continue
        xy = np.stack([(ll[:, 1] - lon0) * m * np.cos(np.radians(lat0)), (ll[:, 0] - lat0) * m], 1)
        for a, b in zip(xy[:-1], xy[1:]):
            k = max(int(np.ceil(np.hypot(*(b - a)) / step)), 1)
            pts.append(a + (b - a) * (np.arange(k) / k)[:, None])
        pts.append(xy[-1:])
    return cKDTree(np.vstack(pts))


class MapRoad(_L2):
    name = "v2x.map_road"

    def __init__(self, tree=None):
        super().__init__()
        self.tree = tree

    def raw_scores(self, df):
        if self.tree is None or not len(df):
            return np.zeros(len(df))
        xy = np.stack([df["x"].to_numpy(dtype=float), df["y"].to_numpy(dtype=float)], 1)
        return self.tree.query(xy)[0]

    def evaluable(self, df):
        return self.tree is not None

    def reasons(self, df, raw, alarm):
        return [f"claimed position is {r:.0f} m from the nearest drivable road" for r in raw]


def make_layers(road_tree=None):
    return [PosSpeed(), PosHeading(), SpeedChange(), ImpliedSpeed(), HeadingRate(), AccelConsistency(),
            YawConsistency(), Overlap(), MapRoad(road_tree)]
