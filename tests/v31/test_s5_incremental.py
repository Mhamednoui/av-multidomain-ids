"""WP8 S5 tests: incremental CAN windows (can/incremental.py) and the single-ego V2X stream (v2x/ego_stream.py) equal the v3 batch code.
Synthetic inputs only (random frames on the IDs of the DBC; synthetic traffic with sender clock offsets); no data files."""
import numpy as np
import pandas as pd

from can import signals as S
from can.domain import CanDomain
from can.incremental import IncrementalCan
from can.stack_core import DBC
from pathlib import Path
from system.v2x_runner import LAYER_NAMES, V2XPhysicsDomain
from v2x import l3, v2aix_eval
from v2x.ego_stream import CHECKS, EgoStream
from v2x.schema import COLUMNS

FROZEN = Path(__file__).resolve().parent.parent.parent / "results" / "WP2" / "s7_domain"


def _can_frames(seed=3, secs=9, rate=400):
    rng = np.random.default_rng(seed)
    ids_pool = np.array(sorted(DBC)[:40] + [0x6E0, 0x1, 0x7F0])
    n = secs * rate
    t = np.sort(rng.uniform(0, secs, n))
    t[rng.integers(1, n, 5)] -= 0.002                     # a few timestamp inversions
    ids = rng.choice(ids_pool, n)
    dlc = np.full(n, 8)
    B = rng.integers(0, 256, (n, 8)).astype(np.uint8)
    return t, ids, dlc, B


def test_can_incremental_equals_batch():
    dom = CanDomain.load(FROZEN)
    t, ids, dlc, B = _can_frames()
    comb, per = dom.score_capture(t, ids, dlc, B, name="c", explain=True)
    me = dom.motion_estimates(t, ids, dlc, B)
    inc = IncrementalCan(dom, name="c", explain=True)
    out = []
    rng = np.random.default_rng(0)
    i = 0
    while i < len(t):                                      # irregular chunk sizes, incl. single frames
        m = int(rng.integers(1, 700))
        out.extend(inc.feed(t[i:i + m], ids[i:i + m], dlc[i:i + m], B[i:i + m]))
        i += m
    out.extend(inc.flush())
    assert len(out) == len(comb) > 0
    for (c, p), b in zip(out, comb):
        assert c.sample_id == b.sample_id and c.score == b.score and c.alarm == b.alarm and c.reason == b.reason and c.details == b.details
        for l in dom.layers:
            assert p[l].score == per[l][comb.index(b)].score
    mi = inc.pop_motion()
    assert len(mi) == len(me) and all(a.t == b.t and a.speed == b.speed and a.sigma == b.sigma for a, b in zip(mi, me))


def test_can_incremental_frame_by_frame_state_is_bounded():
    dom = CanDomain.load(FROZEN)
    t, ids, dlc, B = _can_frames(seed=5, secs=6)
    inc = IncrementalCan(dom, name="c")
    for k in range(len(t)):
        inc.push(t[k], ids[k], dlc[k], B[k])
    assert inc.buf.n < len(t)
    assert len(inc.tail[0]) < 3 * 400 and inc.cs_tail.shape[0] <= 21 and len(inc.prevG) <= 20


def _traffic(seed=1, n_veh=8, T=40, clock_offsets=False):
    rng = np.random.default_rng(seed)
    rows = []
    for v in range(n_veh):
        t0 = 2.0 * v + rng.uniform(0, 0.9)
        x0, y0, sp = 30.0 * v, 3.5 * (v % 3), 12.0 + rng.uniform(0, 4)
        off = rng.uniform(0, 60) if clock_offsets else 0.0
        for k in range(T):
            t = t0 + k * 0.5 + rng.normal(0, 0.01)
            x = x0 + sp * 0.5 * k + rng.normal(0, 0.6) + (300.0 if (v == n_veh - 1 and k > T // 2) else 0.0)
            rows.append((f"m{v}_{k}", f"s{v}", f"s{v}/0", t - off, t, x, y0 + rng.normal(0, 0.6), sp + rng.normal(0, 0.05)))
    d = pd.DataFrame(rows, columns=["msg_id", "sender", "track", "t", "recv_s", "x", "y", "speed"])
    d["pseudo"], d["source"], d["label"] = "0", "synthetic", 0
    d["vx"], d["vy"], d["heading"], d["acl"], d["yaw_rate"] = d["speed"], 0.0, 0.0, 0.0, np.nan
    d["rx_id"] = "ego"
    for c in COLUMNS:
        if c not in d.columns:
            d[c] = np.nan
    return d


def _stream(d, use_recv):
    es = EgoStream(l3.Tracker(), use_recv=use_recv)
    recs = d.to_dict("records")
    outs = [es.push(r) for r in recs]
    return {c: np.array([o[c] for o in outs], np.float32) for c in CHECKS}, es


def test_ego_stream_equals_batch_common_clock():
    d = _traffic(clock_offsets=False).sort_values("t", kind="stable").reset_index(drop=True)
    dom = V2XPhysicsDomain(l3.Tracker())
    ref = dom.raws(d)
    got, es = _stream(d.drop(columns=["recv_s"]), False)
    for c in LAYER_NAMES:
        assert np.array_equal(got[c], ref[c]), c
    assert es.reordered == 0


def test_ego_stream_equals_batch_reception_clock():
    d = _traffic(seed=2, clock_offsets=True)
    order = np.lexsort((np.arange(len(d)), d["recv_s"].to_numpy()))
    ref = v2aix_eval.raws(l3.Tracker(), d)
    s = d.iloc[order].reset_index(drop=True)
    got, es = _stream(s, True)
    for c in LAYER_NAMES:
        assert np.array_equal(got[c], np.asarray(ref[c])[order]), c
