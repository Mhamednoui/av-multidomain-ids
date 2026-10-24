"""V2AIX (D13, RWTH ika, arXiv 2403.10221) JSON reader: ETSI CAM -> unified message table (WP5 S0c).

Purpose: turn one V2AIX recording (json/<Mobile|Stationary>/<context>/<location>/scenarios/<ts>.json) into the table of v2x/schema.py,
with the ego vehicle (or the roadside unit) as receiver: rx_x / rx_y = ego GNSS position interpolated at the message reception time.
Inputs: recording files under ../data_extra/D13_v2aix/extracted/json (untrusted data: plain json parsing only, nothing is executed;
callers run python -I). Output: DataFrame with schema.COLUMNS plus extra columns (age_s, recording, station_id, station_type, rx_src).
Licence: non-commercial research, cite the paper, no redistribution: the caches are written next to the data, never inside the repo.
Topics used: /v2x/cam (parsed ETSI CAM, v2), /gps/oxts_rt3000/fix (ego, when present, ~100 Hz), /gps/cohda_mk5/fix (ego GNSS of the OBU/RSU,
5-10 Hz; a single fix for stationary units). /v2x/raw (the same packets as bytes) is ignored. The recordings hold CAMs only (no DENM).
Unit conversions (ETSI TS 102 894-2 CDD v1.3.1 / EN 302 637-2; a value equal to the unavailable code gives NaN):
  latitude / longitude  0.1 microdegree (1e-7 deg)      unavailable 900000001 / 1800000001
  heading               0.1 deg, clockwise from north   unavailable 3601   -> schema heading = pi/2 - radians(deg) (0 = East, CCW)
  speed                 0.01 m/s                        unavailable 16383
  longitudinal accel.   0.1 m/s^2 (+ = forward)         unavailable 161
  yaw rate              0.01 deg/s, clockwise positive  unavailable 32767 -> schema yaw_rate = -radians(deg/s) (CCW positive)
  position confidence   semi major / minor 0.01 m (4095 unavailable) -> pos_sigma = mean of the two, metres
  speed confidence      0.01 m/s (127 unavailable); acceleration confidence 0.1 m/s^2 (102 unavailable)
  generation_delta_time ms modulo 65536 of the sender clock (TimestampIts)
Time: the sender clock is not synchronised with the logger (apparent offset is a different constant per recording and sender).
t = reception time minus the apparent latency, where the latency is the generation_delta_time difference unwrapped around its per-(recording,
sender) median; so t is the sender's generation time on the logger clock up to one constant per (recording, sender). age_s = (recv - t) minus
its per-(recording, sender) minimum (relative latency >= 0). recv time = recording_timestamp_nsec of the /v2x/cam record (epoch seconds).
recv_s = reception time on the logger clock (epoch s), the common clock of all senders and of the ego pose (S3b: cross-sender checks use it).
Local frame: x east, y north in metres from (LAT0, LON0) with an equirectangular projection (error < 0.5% inside the dataset area).
"""
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

from common.config import DATA_EXTRA, SEED
from v2x.schema import COLUMNS, TEXT

V2AIX_DIR = DATA_EXTRA / "D13_v2aix"
JSON_ROOT = V2AIX_DIR / "extracted" / "json"
CACHE_DIR = V2AIX_DIR / "cache"
LAT0, LON0 = 50.78, 6.08
_M_PER_DEG = 111320.0
GAP_S = 5.0
UNAVAIL = {"lat": 900000001, "lon": 1800000001, "heading": 3601, "speed": 16383, "acl": 161, "yaw": 32767,
           "pos_conf": 4095, "spd_conf": 127, "acl_conf": 102}
EXTRA = ["age_s", "recording", "station_id", "station_type", "rx_src", "recv_s"]


def to_xy(lat, lon):
    lat, lon = np.asarray(lat, float), np.asarray(lon, float)
    return (lon - LON0) * _M_PER_DEG * np.cos(np.radians(LAT0)), (lat - LAT0) * _M_PER_DEG


def _val(d, *path):
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _scaled(v, unavail, scale):
    return np.nan if v is None or v == unavail else float(v) * scale


def parse_cam(msg: dict) -> dict:
    """One /v2x/cam 'message' dict -> flat SI fields (NaN when absent or the unavailable code). No schema columns yet."""
    cam = msg.get("cam", {})
    bc = _val(cam, "cam_parameters", "basic_container") or {}
    hf = _val(cam, "cam_parameters", "high_frequency_container") or {}
    bv = hf.get("basic_vehicle_container_high_frequency", {}) if hf.get("choice", 0) == 0 else {}
    rp = bc.get("reference_position", {})
    lat, lon = _val(rp, "latitude", "value"), _val(rp, "longitude", "value")
    a = _val(rp, "position_confidence_ellipse", "semi_major_confidence", "value")
    b = _val(rp, "position_confidence_ellipse", "semi_minor_confidence", "value")
    ps = np.array([_scaled(v, UNAVAIL["pos_conf"], 0.01) for v in (a, b)])
    hd = _scaled(_val(bv, "heading", "heading_value", "value"), UNAVAIL["heading"], 0.1)
    yaw = _scaled(_val(bv, "yaw_rate", "yaw_rate_value", "value"), UNAVAIL["yaw"], 0.01)
    return {
        "station_id": _val(msg, "header", "station_id", "value"),
        "station_type": _val(bc, "station_type", "value"),
        "gdt_ms": _val(cam, "generation_delta_time", "value"),
        "lat": _scaled(lat, UNAVAIL["lat"], 1e-7), "lon": _scaled(lon, UNAVAIL["lon"], 1e-7),
        "speed": _scaled(_val(bv, "speed", "speed_value", "value"), UNAVAIL["speed"], 0.01),
        "heading": np.nan if np.isnan(hd) else np.pi / 2 - np.radians(hd),
        "acl": _scaled(_val(bv, "longitudinal_acceleration", "longitudinal_acceleration_value", "value"), UNAVAIL["acl"], 0.1),
        "yaw_rate": np.nan if np.isnan(yaw) else -np.radians(yaw),
        "pos_sigma": float(np.nanmean(ps)) if not np.isnan(ps).all() else np.nan,
        "spd_sigma": _scaled(_val(bv, "speed", "speed_confidence", "value"), UNAVAIL["spd_conf"], 0.01),
        "acl_sigma": _scaled(_val(bv, "longitudinal_acceleration", "longitudinal_acceleration_confidence", "value"),
                             UNAVAIL["acl_conf"], 0.1),
    }


def unwrap_generation_time(recv_s, gdt_ms):
    """Generation time on the logger clock from reception times and generation_delta_time (mod 65536 ms) of one sender.
    Returns (t, age_s): t = recv - latency, latency = apparent offset (median) + residual wrapped into +-32.768 s; age_s >= 0, min 0."""
    recv_s, gdt_ms = np.asarray(recv_s, float), np.asarray(gdt_ms, float)
    off = (recv_s * 1000.0 - gdt_ms) % 65536.0
    ref = np.median(np.unwrap(off * 2 * np.pi / 65536.0) * 65536.0 / (2 * np.pi)) % 65536.0   # circular-safe reference
    rel = (off - ref + 32768.0) % 65536.0 - 32768.0
    lat = (ref + rel) / 1000.0
    t = recv_s - lat
    age = (recv_s - t) - (recv_s - t).min()
    return t, age


def _fix_table(records):
    t, la, lo = [], [], []
    for r in records:
        m = r.get("message", {})
        h = _val(m, "header", "stamp")
        if h is None or m.get("latitude") is None:
            continue
        st = _val(m, "status", "status")
        if st is not None and st < 0:
            continue
        if not (np.isfinite(m["latitude"]) and np.isfinite(m["longitude"])) or (m["latitude"] == 0 and m["longitude"] == 0):
            continue
        t.append(h["secs"] + h["nsecs"] / 1e9); la.append(m["latitude"]); lo.append(m["longitude"])
    o = np.argsort(t, kind="stable")
    return np.array(t)[o], np.array(la)[o], np.array(lo)[o]


def ego_positions(d: dict, recv_s, max_gap_s=2.0):
    """Ego position (local x, y) at the reception times. Source: oxts_rt3000 if the recording has it, else cohda_mk5.
    Linear interpolation in lat/lon; NaN if the nearest fix is more than max_gap_s away (a single fix = fixed unit, used at any time)."""
    recv_s = np.asarray(recv_s, float)
    for key, name in (("/gps/oxts_rt3000/fix", "oxts"), ("/gps/cohda_mk5/fix", "cohda")):
        if key in d and len(d[key]):
            t, la, lo = _fix_table(d[key])
            if len(t) == 0:
                continue
            if len(t) == 1:
                x, y = to_xy(np.full(len(recv_s), la[0]), np.full(len(recv_s), lo[0]))
                return x, y, name + "_static"
            ila, ilo = np.interp(recv_s, t, la), np.interp(recv_s, t, lo)
            idx = np.clip(np.searchsorted(t, recv_s), 1, len(t) - 1)
            near = np.minimum(np.abs(recv_s - t[idx - 1]), np.abs(recv_s - t[idx]))
            x, y = to_xy(ila, ilo)
            x[near > max_gap_s] = np.nan
            y[near > max_gap_s] = np.nan
            return x, y, name
    n = len(recv_s)
    return np.full(n, np.nan), np.full(n, np.nan), "none"


def recording_id(path, root=JSON_ROOT) -> str:
    p = Path(path).resolve().relative_to(Path(root).resolve()).with_suffix("")
    return "/".join(x for x in p.parts if x != "scenarios")


def build_table(d: dict, rec: str) -> pd.DataFrame:
    """Parsed recording dict (keys = topics) -> unified table. Rows without finite time, position and speed are dropped."""
    cams = d.get("/v2x/cam", [])
    if not cams:
        return pd.DataFrame(columns=COLUMNS + EXTRA)
    df = pd.DataFrame([parse_cam(c["message"]) for c in cams])
    recv = np.array([c["recording_timestamp_nsec"] / 1e9 for c in cams], float)
    df["k"] = np.arange(len(df))
    t = np.full(len(df), np.nan)
    age = np.full(len(df), np.nan)
    for ix in df.groupby("station_id").indices.values():
        ok = df["gdt_ms"].iloc[ix].notna().to_numpy()
        if ok.any():
            tt, aa = unwrap_generation_time(recv[ix[ok]], df["gdt_ms"].iloc[ix[ok]].to_numpy())
            t[ix[ok]] = tt
            age[ix[ok]] = aa
    rx, ry, src = ego_positions(d, recv)
    x, y = to_xy(df["lat"], df["lon"])
    sid = df["station_id"].astype("int64").astype(str)
    out = pd.DataFrame({
        "msg_id": "v2aix:" + rec + ":" + df["k"].astype(str),
        "source": "v2aix", "sender": rec + "#" + sid, "pseudo": sid, "t": t, "x": x, "y": y,
        "speed": df["speed"], "heading": df["heading"], "acl": df["acl"], "yaw_rate": df["yaw_rate"],
        "pos_sigma": df["pos_sigma"], "spd_sigma": df["spd_sigma"], "acl_sigma": df["acl_sigma"],
        "rx_id": rec, "rx_x": rx, "rx_y": ry, "lat": df["lat"], "lon": df["lon"],
        "label": 0, "attack": "Genuine", "injected": False,
        "age_s": age, "recv_s": recv[df["k"].to_numpy()], "recording": rec, "station_id": sid, "station_type": df["station_type"].astype(float), "rx_src": src,
    })
    th = out["heading"].to_numpy(float)
    out["vx"] = out["speed"] * np.cos(th)
    out["vy"] = out["speed"] * np.sin(th)
    ok = np.isfinite(out[["t", "x", "y", "speed"]].to_numpy(float)).all(axis=1)
    out = out[ok].sort_values(["sender", "t"], kind="stable").drop_duplicates(["sender", "t"]).reset_index(drop=True)
    seg = (out.groupby("sender")["t"].diff() > GAP_S).groupby(out["sender"]).cumsum()
    out["track"] = out["sender"] + "/" + seg.astype(int).astype(str)
    for c in COLUMNS:
        if c not in out.columns:
            out[c] = None if c in TEXT else np.nan
    return out[COLUMNS + EXTRA].reset_index(drop=True)


def list_recordings(root=JSON_ROOT):
    """Extracted recording files (scenarios/*.json only; joined.json repeats the same data and is skipped), sorted."""
    return sorted(Path(root).glob("*/*/*/scenarios/*.json"))


def load_recording(path, root=JSON_ROOT, cache=True) -> pd.DataFrame:
    rec = recording_id(path, root)
    cf = CACHE_DIR / (rec.replace("/", "__") + ".pkl")
    if cache and cf.exists() and cf.stat().st_mtime >= Path(path).stat().st_mtime:
        old = pd.read_pickle(cf)
        if "recv_s" in old.columns:          # caches written by S0c lack the reception time (added in S3b): rebuild them
            return old
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    df = build_table(d, rec)
    if cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_pickle(cf)
    return df


def load_all(root=JSON_ROOT, recordings=None, cache=True) -> pd.DataFrame:
    paths = list_recordings(root)
    if recordings is not None:
        keep = set(recordings)
        paths = [p for p in paths if recording_id(p, root) in keep]
    parts = [load_recording(p, root, cache) for p in paths]
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS + EXTRA)


def stratum_of(rec: str) -> str:
    p = rec.split("/")
    return p[0] + "/" + p[2]          # Mobile|Stationary / location


def split_recordings(recs, seed=SEED, fractions=(0.6, 0.2, 0.2), min_stratum=3):
    """60/20/20 by recording, stratified by (Mobile|Stationary, location); strata with fewer than min_stratum recordings are pooled per
    Mobile|Stationary and split together. Deterministic for a given input set and seed. Returns {'train': [...], 'val': [...], 'test': [...]}."""
    strata = {}
    for r in sorted(recs):
        strata.setdefault(stratum_of(r), []).append(r)
    pooled = {}
    for k in sorted(strata):
        key = k if len(strata[k]) >= min_stratum else k.split("/")[0] + "/_small"
        pooled.setdefault(key, []).extend(strata[k])
    rng = random.Random(seed)
    out = {"train": [], "val": [], "test": []}
    for k in sorted(pooled):
        g = sorted(pooled[k])
        rng.shuffle(g)
        n = len(g)
        nv = max(1, int(round(fractions[1] * n))) if n >= 3 else 0
        nt = max(1, int(round(fractions[2] * n))) if n >= 3 else 0
        out["val"] += g[:nv]
        out["test"] += g[nv:nv + nt]
        out["train"] += g[nv + nt:]
    return {k: sorted(v) for k, v in out.items()}
