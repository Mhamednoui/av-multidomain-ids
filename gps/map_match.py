"""WP1 S6 L2e: map matching of the reported GPS fix on OpenStreetMap drivable roads.

Purpose: a spoofed position that leaves the road network (or a course that disagrees with the road direction, one-way
streets included) is physically implausible for a car. The check uses a static map, nothing from the receiver but the fix.
Inputs: the D15 extract (Overpass JSON: nodes + highway ways with tags), stream columns lat, lon, course, odo_speed.
Outputs: gps.map_dist (m to the nearest drivable segment), gps.map_heading (deg between course and road direction),
gps.map_comb (max of the two, each divided by its clean 95th percentile).
Method: ways filtered to DRIVABLE classes (fixed before any result); segments densified every 3 m in a scipy cKDTree;
for the 32 nearest dense points the exact point-to-segment distance and direction are computed.
Limit (physics): a spoof that stays on a road (drift along the road, route-following replay, freeze) is invisible here.
References: Quddus, Ochieng, Noland 2007 (map-matching algorithms review); Zeng et al. 2018 (road-following spoofing, USENIX Sec).
"""
import json
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

OSM_JSON = Path(__file__).resolve().parents[2] / "data_extra" / "D15_osm" / "karlsruhe_highways.json"
LAT0, LON0 = 48.99, 8.40
M_PER_DEG = 111_320.0
DRIVABLE = ("motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "service", "living_street")
DRIVABLE_CLASSES = frozenset(DRIVABLE) | frozenset(c + "_link" for c in DRIVABLE[:5])
DENSIFY_M = 3.0
K_NEAR = 32
HEADING_BAND_M = 10.0
MIN_SPEED = 3.0


def to_xy(lat, lon):
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    return np.c_[(lon - LON0) * M_PER_DEG * np.cos(np.radians(LAT0)), (lat - LAT0) * M_PER_DEG]


def oneway_sign(tags):
    """+1: travel allowed along node order, -1: against it, 0: both ways."""
    ow = str(tags.get("oneway", "")).lower()
    if ow in ("yes", "1", "true"):
        return 1
    if ow == "-1":
        return -1
    if tags.get("junction") == "roundabout":
        return 1
    return 0


def load_segments(path=OSM_JSON, classes=DRIVABLE_CLASSES):
    """Segments (A, B, oneway sign) of the ways whose highway tag is in `classes`."""
    els = json.load(open(path, encoding="utf-8"))["elements"]
    nodes = {e["id"]: (e["lat"], e["lon"]) for e in els if e["type"] == "node"}
    A, B, O = [], [], []
    for w in els:
        if w["type"] != "way" or w.get("tags", {}).get("highway") not in classes:
            continue
        pts = [nodes[n] for n in w["nodes"] if n in nodes]
        if len(pts) < 2:
            continue
        xy = to_xy([p[0] for p in pts], [p[1] for p in pts])
        s = oneway_sign(w["tags"])
        A.append(xy[:-1]); B.append(xy[1:]); O.append(np.full(len(xy) - 1, s))
    return np.vstack(A), np.vstack(B), np.concatenate(O)


class RoadMap:
    def __init__(self, A, B, O):
        self.A, self.B, self.O = A, B, O
        d = B - A
        self.len = np.hypot(d[:, 0], d[:, 1])
        ok = self.len > 1e-6
        self.A, self.B, self.O, self.len, d = A[ok], B[ok], O[ok], self.len[ok], d[ok]
        self.d = d
        self.bearing = np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 360.0          # from north, clockwise
        n = np.ceil(self.len / DENSIFY_M).astype(int) + 1
        sid = np.repeat(np.arange(len(self.len)), n)
        k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
        f = (k / np.repeat(n - 1, n))[:, None]
        pts = self.A[sid] + f * self.d[sid]
        self.sid = sid
        self.tree = cKDTree(pts)

    @classmethod
    def from_osm(cls, path=OSM_JSON, classes=DRIVABLE_CLASSES):
        return cls(*load_segments(path, classes))

    def query(self, xy, course=None, speed=None, chunk=20000):
        """Distance to the nearest segment (m) and heading deviation (deg; 0 where speed < MIN_SPEED or course is NaN)."""
        n = len(xy)
        dist, head = np.zeros(n), np.zeros(n)
        for i in range(0, n, chunk):
            p = xy[i:i + chunk]
            _, ix = self.tree.query(p, k=K_NEAR)
            s = self.sid[ix]                                                    # (m, K)
            a, d, ln2 = self.A[s], self.d[s], np.maximum(self.len[s] ** 2, 1e-9)
            t = np.clip(((p[:, None, :] - a) * d).sum(-1) / ln2, 0.0, 1.0)
            q = a + t[..., None] * d
            dd = np.hypot(*(p[:, None, :] - q).transpose(2, 0, 1))
            dmin = dd.min(1)
            dist[i:i + chunk] = dmin
            if course is None:
                continue
            c = np.asarray(course[i:i + chunk], float)[:, None]
            diff = np.abs((c - self.bearing[s] + 180.0) % 360.0 - 180.0)
            o = self.O[s]
            dev = np.where(o == 0, np.minimum(diff, 180.0 - diff), np.where(o == 1, diff, 180.0 - diff))
            dev = np.where(dd <= (dmin + HEADING_BAND_M)[:, None], dev, 180.0).min(1)
            moving = np.asarray(speed[i:i + chunk], float) >= MIN_SPEED
            head[i:i + chunk] = np.where(moving & np.isfinite(c[:, 0]), dev, 0.0)
        return dist, head


def stream_features(df, rmap):
    """Columns map_dist, map_heading for a stream (index aligned to df)."""
    import pandas as pd
    xy = to_xy(df["lat"].to_numpy(), df["lon"].to_numpy())
    dist, head = rmap.query(xy, df["course"].to_numpy(), df["odo_speed"].to_numpy())
    return pd.DataFrame({"map_dist": dist, "map_heading": head}, index=df.index)


def _layer_class():
    from common.layer import Layer

    class MapLayer(Layer):
        """L2e: raw score = a stream column (map_dist, map_heading, map_comb). Reads the columns of stream_features()."""
        domain = "gps"
        kind = "physics"
        layer_id = "L2e"

        def __init__(self, column="map_dist", name=None):
            super().__init__()
            self.column = column
            self.name = name or f"gps.{column}"

        def raw_scores(self, samples):
            return samples[self.column].to_numpy(dtype=float).copy()

        def reasons(self, samples, raw, alarm):
            return [f"fix/course inconsistent with the drivable road map (score {r:.2f})" for r in raw]

    return MapLayer


MapLayer = _layer_class()
