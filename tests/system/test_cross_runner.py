"""Tests for system/cross_runner.py (WP7 S1): residual-level stream == WhichDomainLies.evidence on the whole run; MotionEstimate alignment == the batch grid pipeline
(crossdomain.witness.to_grid + residuals); CUSUM variant carries its state; blame; save / load round trip. Synthetic witnesses, no data files."""
import tempfile

import numpy as np

from common.motion import MotionEstimate
from crossdomain import consistency as CS
from crossdomain import witness as W
from crossdomain.kitti import forward_speed
from system.cross_runner import DOMAIN_OF, EDGES, CrossObject, CrossRunner, edge_list, residuals
from system.runner import compare_sequences


def _obj(k="inst", tb=None, seed=0, n_runs=6, T=40):
    rng = np.random.default_rng(seed)
    edges = edge_list()
    models = {}
    for e in edges:
        m = W.SigmaModel(bias="linear")
        v = rng.uniform(0, 15, 400)
        m.fit(0.02 * v + rng.normal(0, 0.3, 400), v)
        models[e.name] = m
    model = CS.WhichDomainLies(edges, DOMAIN_OF, k=k, budget=0.01, tb=tb, domain_level=True)
    model.fit([rng.normal(0, 1, (T, len(edges))) for _ in range(n_runs)])
    return CrossObject(models, model)


def _stream_rows(obj, seed, T=60, att=None):
    rng = np.random.default_rng(seed)
    names = [e.name for e in obj.edges]
    R = rng.normal(0, 0.3, (T, len(names)))
    V = rng.uniform(1, 15, (T, len(names)))
    if att:
        R[T // 2:, att] += 6.0
    R[3, 2] = np.nan
    V[3, 2] = np.nan
    return names, R, V


def _batch(obj, key, t, R, V):
    Z = np.column_stack([obj.models[e.name].z(R[:, j], V[:, j]) for j, e in enumerate(obj.edges)])
    return obj.model.evidence(t, Z, [f"{key}/{i}" for i in range(len(t))])


def test_residual_level_stream_equals_batch_inst():
    obj = _obj()
    names, R, V = _stream_rows(obj, 1, att=[0, 1])
    t = np.arange(len(R), dtype=float)
    run = CrossRunner(obj)
    out = run.run(({"t": t[i], "r": dict(zip(names, R[i])), "v": dict(zip(names, V[i]))} for i in range(len(t))), key="r1")
    ev = _batch(obj, "r1", t, R, V)
    c = compare_sequences(out, ev, tol=0.0)
    assert c["identical"], c
    assert any(e.alarm for e in ev) and not all(e.alarm for e in ev)
    assert all(e.layer == "L2" and e.domain == "cross" for e in out)


def test_cusum_state_is_carried_and_reset():
    obj = _obj(k=0.5, tb=None)
    names, R, V = _stream_rows(obj, 2, att=[3])
    t = np.arange(len(R), dtype=float)
    run = CrossRunner(obj)
    out = run.run(({"t": t[i], "r": dict(zip(names, R[i])), "v": dict(zip(names, V[i]))} for i in range(len(t))), key="r2")
    assert compare_sequences(out, _batch(obj, "r2", t, R, V), tol=0.0)["identical"]
    again = run.run(({"t": t[i], "r": dict(zip(names, R[i])), "v": dict(zip(names, V[i]))} for i in range(len(t))), key="r2")
    assert compare_sequences(again, out, tol=0.0)["identical"]           # reset clears the CUSUM state
    objd = _obj(k=1.0, tb=60)
    out2 = CrossRunner(objd).run(({"t": t[i], "r": dict(zip(names, R[i])), "v": dict(zip(names, V[i]))} for i in range(len(t))), key="r3")
    assert compare_sequences(out2, _batch(objd, "r3", t, R, V), tol=0.0)["identical"]


def _witnesses(T=30, offset_can=0.0, lag_phase=0.37):
    """Constant-speed straight drive: gps / lidar publish 1 s displacements (mean kind) at fix times, can / imu instantaneous at integer seconds."""
    t_fix = lag_phase + np.arange(T, dtype=float)
    mes = {"gps": [], "lidar": [], "can": [], "imu": []}
    for k in range(1, T):
        mes["gps"].append(MotionEstimate(t=t_fix[k], source="gps", speed=10.0, yaw_rate=0.0, displacement=(10.0, 0.0), sigma=0.45))
        mes["lidar"].append(MotionEstimate(t=t_fix[k], source="lidar", speed=10.0, yaw_rate=0.0, displacement=(10.0, 0.0), sigma=0.1))
    for s in range(T + 1):
        mes["can"].append(MotionEstimate(t=float(s), source="can", speed=10.0 + offset_can, sigma=0.3))
        mes["imu"].append(MotionEstimate(t=float(s), source="imu", yaw_rate=0.0))
    return t_fix, mes


def _events(mes):
    order = {"gps": 0, "lidar": 1, "can": 2, "imu": 3}
    return sorted([m for ms in mes.values() for m in ms], key=lambda m: (m.t, order[m.source]))


def test_motion_estimate_alignment_equals_batch_pipeline():
    obj = _obj(seed=3)
    t_fix, mes = _witnesses(offset_can=3.0)
    frames = {s: W.to_frame(m, source=s) for s, m in mes.items()}
    G = {s: W.to_grid(f, t_fix) for s, f in frames.items()}
    G["gps"], G["lidar"] = forward_speed(G["gps"]), forward_speed(G["lidar"])
    res = residuals(G)
    names = list(res)
    assert names == [e.name for e in obj.edges] and [e[3] for e in EDGES][0] == "gps-lidar speed"
    R = np.column_stack([res[n][0] for n in names])[1:]
    V = np.column_stack([res[n][1] for n in names])[1:]
    ev = _batch(obj, "m", t_fix[1:], R, V)
    out = CrossRunner(obj).run(_events(mes), key="m")
    assert compare_sequences(out, ev, tol=0.0)["identical"]
    assert len(out) == len(t_fix) - 1


def test_alignment_truncation_prefix_of_full_stream_and_reset():
    obj = _obj(seed=4)
    t_fix, mes = _witnesses(offset_can=3.0)
    ev = _events(mes)
    full = CrossRunner(obj).run(ev, key="m")
    for m in (20, 55, 100):
        part = CrossRunner(obj).run(ev[:m], key="m", flush=False)
        assert compare_sequences(part, full[:len(part)], tol=0.0)["identical"]
    r = CrossRunner(obj)
    r.run(ev[:60], key="other")
    assert compare_sequences(r.run(ev, key="m"), full, tol=0.0)["identical"]


def test_blame_points_to_the_lying_domain_and_timeout_resolves():
    obj = _obj(seed=5)
    names = [e.name for e in obj.edges]
    # CAN speed lies: both CAN edges alarm, the gps-lidar edge agrees -> CAN blamed
    r = {n: 0.0 for n in names}
    v = {n: 10.0 for n in names}
    r["gps-can speed"] = r["lidar-can speed"] = 30.0
    out = CrossRunner(obj).run([{"t": 1.0, "r": r, "v": v}], key="b")
    assert out[0].alarm and out[0].details["blamed_domain"] == "can" and "can domain is blamed" in out[0].reason
    # a silent source does not stall the stream: after max_wait_s the step is resolved with what is there
    t_fix, mes = _witnesses(T=12)
    mes_no_can = {s: m for s, m in mes.items() if s != "can"}
    run = CrossRunner(obj, max_wait_s=2.5)
    got = []
    for m in _events(mes_no_can):
        got.extend(run.push(m))
    assert len(got) > 5


def test_object_save_load_round_trip():
    obj = _obj(seed=6)
    with tempfile.TemporaryDirectory() as tmp:
        obj.save(tmp)
        o2 = CrossObject.load(tmp)
    names, R, V = _stream_rows(obj, 9, att=[1])
    t = np.arange(len(R), dtype=float)
    a = CrossRunner(obj).run(({"t": t[i], "r": dict(zip(names, R[i])), "v": dict(zip(names, V[i]))} for i in range(len(t))), key="s")
    b = CrossRunner(o2).run(({"t": t[i], "r": dict(zip(names, R[i])), "v": dict(zip(names, V[i]))} for i in range(len(t))), key="s")
    assert compare_sequences(a, b, tol=1e-9)["identical"]
