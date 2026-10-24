"""Tests for system/gps_runner.py and system/can_runner.py (WP7 S1) on small slices of real VALIDATION data and the FROZEN domains (skipped when the read-only caches are absent):
stream (one sample at a time, prefix re-scoring) == frozen batch Evidence, truncation, reset. GPS: two KITTI validation runs (clean, Doppler spoof) of drive 0011;
CAN: the first 14 s of the ROAD validation capture correlated_signal_attack_2."""
import tempfile
from pathlib import Path

import numpy as np

from common.config import DATA_EXTRA, ROOT
from system.runner import compare_sequences


class Skip(Exception):
    pass


GPS_PICKLE = Path(tempfile.gettempdir()) / "wp1_s4_kitti.pkl"
GPS_FROZEN = ROOT / "results" / "WP1" / "frozen_gps"
CAN_FROZEN = ROOT / "results" / "WP2" / "s7_domain"
CAN_T = DATA_EXTRA / "WP2_S2_cache" / "road" / "correlated_signal_attack_2.npz"
CAN_B = DATA_EXTRA / "WP2_S4_cache" / "road" / "correlated_signal_attack_2.npy"


def _gps_runs():
    if not (GPS_PICKLE.exists() and (GPS_FROZEN / "domain.json").exists() and (ROOT / "results" / "WP1" / "cache" / "lidar_odom_0011.npz").exists()):
        raise Skip("WP1 stream pickle / frozen GPS domain / LiDAR odometry cache not available")
    import pandas as pd
    from gps import lidar_odom as LO
    kx = pd.read_pickle(GPS_PICKLE)
    v = kx[(kx["part"] == "val") & (kx["drive"] == "0011")]
    runs = [v[v["attack"] == a] for a in ("none", "doppler_spoof")]
    runs = [r[r["run"] == r["run"].iloc[0]] for r in runs]
    out = []
    for r in runs:
        r = r.copy()
        out.append(r.join(LO.stream_features(r)).reset_index(drop=True))
    return out


def test_gps_runner_stream_equals_frozen_batch_truncation_reset():
    from gps import domain as GD
    from system.gps_runner import INPUT_COLUMNS, GPSRunner
    runs = _gps_runs()
    dom = GD.GPSDomain.load(GPS_FROZEN)
    cols = [c for c in INPUT_COLUMNS if c in runs[0].columns]
    smp = [r[cols].to_dict("records") for r in runs]
    run = GPSRunner(GPS_FROZEN)
    n = len(dom.names) + 1
    for r, s in zip(runs, smp):
        ev, per = dom.score(GD.prepare(r, lidar=True), with_layers=True)
        out = run.run(s, key=str(r["run"].iloc[0]))
        assert compare_sequences(out[0::n], ev, tol=1e-9)["identical"]
        for j, nm in enumerate(dom.names):
            assert compare_sequences(out[1 + j::n], per[nm], tol=1e-9)["identical"]
    # truncation: stream prefix == first fixes of the full stream; frozen batch prefix == batch full (the layers are causal)
    full = GPSRunner(GPS_FROZEN, per_layer=False).run(smp[1], key="x")
    k = len(smp[1]) // 2
    part = GPSRunner(GPS_FROZEN, per_layer=False).run(smp[1][:k], key="x")
    assert compare_sequences(part, full[:k], tol=0.0)["identical"]
    evk, _ = dom.score(GD.prepare(runs[1].iloc[:k].copy(), lidar=True), with_layers=True)
    evf, _ = dom.score(GD.prepare(runs[1], lidar=True), with_layers=True)
    assert compare_sequences(evk, evf[:k], tol=1e-9)["identical"]
    # reset: stream B after A == fresh B
    after = run.run(smp[1], key="x")
    assert compare_sequences(after[0::n], full, tol=1e-9)["identical"]
    assert any(e.alarm for e in full)


def test_can_runner_stream_equals_frozen_batch_windows_and_motion():
    if not (CAN_T.exists() and CAN_B.exists() and (CAN_FROZEN / "domain.pkl").exists()):
        raise Skip("ROAD caches / frozen CAN domain not available")
    from system.can_runner import CANRunner
    z = np.load(CAN_T)
    B = np.maximum(np.load(CAN_B), 0).astype(np.uint8)
    t, ids, dlc = z["t"], z["id"].astype(np.int64), z["dlc"].astype(np.int64)
    k = int(np.searchsorted(t, t[0] + 14.0))
    t, ids, dlc, B = t[:k], ids[:k], dlc[:k], B[:k]
    run = CANRunner(CAN_FROZEN)
    comb, per = run.dom.score_capture(t, ids, dlc, B, name="cap")
    me_b = run.dom.motion_estimates(t, ids, dlc, B)
    frames = [(t[i], ids[i], dlc[i], B[i]) for i in range(k)]
    out = run.run(frames, key="cap")
    layers = run.dom.layers
    n = len(layers) + 1
    assert len(comb) >= 10 and compare_sequences(out[0::n], comb, tol=1e-9)["identical"]
    for j, l in enumerate(layers):
        assert compare_sequences(out[1 + j::n], per[l], tol=1e-9)["identical"]
    me = run.pop_motion()
    assert len(me) == len(me_b) and all(abs(a.t - b.t) < 1e-9 and abs(a.speed - b.speed) < 1e-12 for a, b in zip(me, me_b))
    # a frame that does not complete a window emits nothing; a window is emitted when its second has passed (before flush)
    run.reset("cap")
    emitted = [len(run.push(f)) for f in frames]
    assert sum(1 for e in emitted if e) == len(comb) - 1 and run.flush()[0].sample_id == comb[-1].sample_id
    # truncation without flush: only completed windows, equal to the first windows of the full stream
    run.reset("cap")
    part = run.run(frames[: k // 2], key="cap", flush=False)
    assert len(part) > 0 and compare_sequences(part[0::n], comb[: len(part) // n], tol=1e-9)["identical"]
