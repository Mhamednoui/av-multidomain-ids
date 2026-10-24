"""Tests for v2x/v2aix.py (V2AIX CAM adapter): unit conversions, unavailable codes, time unwrapping, ego pose, split. Synthetic data only."""
import json
import tempfile
from pathlib import Path

import numpy as np

from v2x import adapters, schema, v2aix


def _cam(sid=111, lat=508000000, lon=61000000, hd=900, sp=2500, acl=-15, yaw=250, gdt=1000, hc=0, ptype=5):
    hf = {"choice": hc, "basic_vehicle_container_high_frequency": {
        "heading": {"heading_value": {"value": hd}}, "speed": {"speed_value": {"value": sp}, "speed_confidence": {"value": 5}},
        "longitudinal_acceleration": {"longitudinal_acceleration_value": {"value": acl}, "longitudinal_acceleration_confidence": {"value": 102}},
        "yaw_rate": {"yaw_rate_value": {"value": yaw}}}}
    return {"header": {"protocol_version": 2, "message_id": 2, "station_id": {"value": sid}},
            "cam": {"generation_delta_time": {"value": gdt}, "cam_parameters": {
                "basic_container": {"station_type": {"value": ptype}, "reference_position": {
                    "latitude": {"value": lat}, "longitude": {"value": lon},
                    "position_confidence_ellipse": {"semi_major_confidence": {"value": 300}, "semi_minor_confidence": {"value": 200}}}},
                "high_frequency_container": hf}}}


def test_parse_cam_units():
    r = v2aix.parse_cam(_cam())
    assert abs(r["lat"] - 50.8) < 1e-9 and abs(r["lon"] - 6.1) < 1e-9          # 1e-7 deg
    assert abs(r["speed"] - 25.0) < 1e-9                                       # 0.01 m/s
    assert abs(r["heading"] - (np.pi / 2 - np.radians(90.0))) < 1e-9           # 90 deg clockwise from north = East = 0 rad
    assert abs(r["acl"] - (-1.5)) < 1e-9                                       # 0.1 m/s^2
    assert abs(r["yaw_rate"] - (-np.radians(2.5))) < 1e-9                      # 0.01 deg/s clockwise -> CCW positive
    assert abs(r["pos_sigma"] - 2.5) < 1e-9 and abs(r["spd_sigma"] - 0.05) < 1e-9
    assert np.isnan(r["acl_sigma"])                                            # 102 = unavailable
    assert r["station_id"] == 111 and r["gdt_ms"] == 1000
    assert abs(v2aix.parse_cam(_cam(hd=0))["heading"] - np.pi / 2) < 1e-9      # North = +pi/2
    assert abs(v2aix.parse_cam(_cam(hd=1800))["heading"] + np.pi / 2) < 1e-9   # South = -pi/2


def test_parse_cam_unavailable_and_rsu():
    r = v2aix.parse_cam(_cam(lat=900000001, lon=1800000001, hd=3601, sp=16383, acl=161, yaw=32767))
    for k in ("lat", "lon", "heading", "speed", "acl", "yaw_rate"):
        assert np.isnan(r[k]), k
    rsu = _cam(hc=1)
    r = v2aix.parse_cam(rsu)
    assert np.isnan(r["speed"]) and np.isnan(r["heading"]) and abs(r["lat"] - 50.8) < 1e-9


def test_unwrap_generation_time():
    # logger-sender offset 12345.0 s, latency 0.03 s; gdt wraps modulo 65536 ms; 200 s of 10 Hz messages
    recv = 1.7e9 + np.arange(0, 200, 0.1)
    true_gen = recv - 0.03 - 12345.0
    gdt = np.floor(true_gen * 1000) % 65536
    t, age = v2aix.unwrap_generation_time(recv, gdt)
    lat = recv - t
    assert np.ptp(lat - lat[0]) < 0.0011                                       # constant offset, only ms rounding left
    assert age.min() == 0 and age.max() < 0.0015
    # a late message (latency +0.5 s) shows as age 0.5
    gdt2 = gdt.copy()
    gdt2[50] = (gdt2[50] - 500) % 65536
    t2, age2 = v2aix.unwrap_generation_time(recv, gdt2)
    assert abs(age2[50] - 0.5) < 0.002 and np.all(np.diff(t2[:49]) > 0)


def _gps(t, lat, lon, st=0):
    s = int(t)
    return {"recording_timestamp_nsec": int(t * 1e9), "message": {"header": {"stamp": {"secs": s, "nsecs": int(round((t - s) * 1e9))}},
                                                                   "status": {"status": st}, "latitude": lat, "longitude": lon}}


def test_ego_positions_interp_gap_static():
    d = {"/gps/cohda_mk5/fix": [_gps(100.0, 50.0, 6.0), _gps(101.0, 50.001, 6.0), _gps(110.0, 50.002, 6.0)]}
    x, y, src = v2aix.ego_positions(d, np.array([100.5, 101.5, 105.0, 120.0]))
    assert src == "cohda"
    assert abs(y[0] - (50.0005 - v2aix.LAT0) * 111320.0) < 0.5
    assert np.isfinite(x[0]) and np.isfinite(y[1])
    assert np.isnan(x[2]) and np.isnan(x[3])                                   # more than 2 s from a fix
    d = {"/gps/cohda_mk5/fix": [_gps(100.0, 50.9, 6.2)]}
    x, y, src = v2aix.ego_positions(d, np.array([1.0, 5.0]))
    assert src == "cohda_static" and np.allclose(x, x[0]) and np.isfinite(x).all()
    d = {"/gps/cohda_mk5/fix": [_gps(100.0, 50.9, 6.2)], "/gps/oxts_rt3000/fix": [_gps(100.0, 50.1, 6.0), _gps(101.0, 50.1, 6.0)]}
    assert v2aix.ego_positions(d, np.array([100.5]))[2] == "oxts"
    d = {"/gps/cohda_mk5/fix": [_gps(100.0, 0.0, 0.0, st=-1)]}
    assert v2aix.ego_positions(d, np.array([100.5]))[2] == "none"


def _recording():
    cams, base = [], 1.7e9
    for k in range(20):
        t = base + 0.1 * k
        cams.append({"recording_timestamp_nsec": int(t * 1e9),
                     "message": _cam(sid=111, lat=508000000 + 50 * k, lon=61000000, hd=0, sp=1000 + 10 * k, gdt=int((t * 1000 - 5000) % 65536))})
        if k % 2 == 0:
            cams.append({"recording_timestamp_nsec": int(t * 1e9),
                         "message": _cam(sid=222, lat=508010000, lon=61010000 + 80 * k, hd=900, sp=2000, gdt=int((t * 1000 - 9000) % 65536))})
    gps = [_gps(base + 0.05 * k - 0.5, 50.8 - 1e-4 + 2e-6 * k, 6.1) for k in range(100)]
    return {"/v2x/cam": cams, "/gps/cohda_mk5/fix": gps, "/v2x/raw": []}


def test_build_table_schema_and_values():
    df = v2aix.build_table(_recording(), "Mobile/V2X-only/Test/2024-01-01T00-00-00Z")
    schema.validate(df)
    assert len(df) == 30 and df["sender"].nunique() == 2 and (df["label"] == 0).all()
    a = df[df["station_id"] == "111"].sort_values("t")
    assert np.all(np.diff(a["t"]) > 0.099) and np.all(np.diff(a["t"]) < 0.101)
    assert np.allclose(np.diff(a["y"]), 50e-7 * 111320.0, atol=1e-3)           # latitude step of 50 * 1e-7 deg
    assert abs(a["speed"].iloc[3] - 10.3) < 1e-9
    assert np.isfinite(df[["rx_x", "rx_y"]].to_numpy()).all() and (df["rx_src"] == "cohda").all()
    assert np.all(df["age_s"] >= 0)


def test_adapter_entry_and_unavailable():
    import pandas as pd
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        f = root / "extracted" / "json" / "Mobile" / "V2X-only" / "Test" / "scenarios"
        f.mkdir(parents=True)
        (f / "2024-01-01T00-00-00Z.json").write_text(json.dumps(_recording()))
        old = v2aix.CACHE_DIR
        v2aix.CACHE_DIR = root / "cache"
        try:
            df = adapters.load_v2aix(root)
        finally:
            v2aix.CACHE_DIR = old
        assert len(df) == 30 and set(df["recording"]) == {"Mobile/V2X-only/Test/2024-01-01T00-00-00Z"}
        schema.validate(df)
        try:
            adapters.load_v2aix(root / "nothing")
            raise AssertionError("expected DataNotAvailableError")
        except schema.DataNotAvailableError:
            pass


def test_split_recordings():
    recs = [f"Mobile/V2X-only/Highway/ts{i:03d}" for i in range(50)] + [f"Stationary/V2X-only/Ponttor/ts{i:03d}" for i in range(20)] \
        + ["Mobile/V2X-only/Rural/a", "Mobile/V2X-only/Aachen/b"]
    s1 = v2aix.split_recordings(recs, seed=42)
    s2 = v2aix.split_recordings(list(reversed(recs)), seed=42)
    assert s1 == s2
    allr = s1["train"] + s1["val"] + s1["test"]
    assert sorted(allr) == sorted(recs) and len(set(allr)) == len(recs)
    hw = {k: sum(r.startswith("Mobile/V2X-only/Highway") for r in v) for k, v in s1.items()}
    assert hw == {"train": 30, "val": 10, "test": 10}
    assert v2aix.split_recordings(recs, seed=1) != s1
