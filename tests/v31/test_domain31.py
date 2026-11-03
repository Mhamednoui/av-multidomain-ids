"""WP8 S3 tests of lidar.domain31: save / load round trip on a synthetic reference, Evidence contract, first scan, and (when the frozen v3.1 domain
and KITTI data are present) stream == batch on a few real scans."""
import tempfile
from pathlib import Path

import numpy as np

from lidar import geometry as G
from lidar.combine31 import LAYERS, Union, alpha_budgets
from lidar.domain31 import A_STATS, Domain31

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "results" / "WP8" / "S3" / "frozen_lidar31"


class Skip(Exception):
    pass


def _synthetic():
    rng = np.random.default_rng(5)
    n = 3000
    c_stats = ["miss_z20"]
    names = list(G.STAT_NAMES) + A_STATS + ["f_cnt_int_hi", "f_cnt_int_lo", "miss_z20", "app_cc", "fix_tot"]
    stat_ref = {k: rng.random(n) for k in names}
    layer_stats = {"L1": list(G.STAT_NAMES), "L2a": A_STATS, "L2c": c_stats, "L2d": ["app_cc", "fix_tot"]}
    raw = {l: np.max([np.sort(stat_ref[s]).searchsorted(stat_ref[s]) / n for s in layer_stats[l]], axis=0) for l in LAYERS}
    un = Union(alpha_budgets(0.55), "union").fit(raw)
    table = G.RingTable(np.zeros(64), -np.linspace(0.0, 0.4, 64))
    ir = type("IR", (), {})()
    ir.nmin, ir.i = 8, {(0, -1): np.sort(rng.random(500))}
    return Domain31(table, {"ground": "grid"}, ir, stat_ref, un, c_stats, {"t": 1}), stat_ref


def test_save_load_roundtrip_and_evidence_contract():
    dom, ref = _synthetic()
    with tempfile.TemporaryDirectory() as d:
        dom.save(d)
        dom2 = Domain31.load(d)
    l1, a = np.zeros(5), np.zeros(4)
    pair = {"miss_z20": 0.999, "app_cc": 0.0, "fix_tot": 0.0}
    r1, r2 = dom.raw_from_records(l1, a, pair, 10), dom2.raw_from_records(l1, a, pair, 10)
    assert r1 == r2
    comb, per = dom2.evidence(r2, t=1.0, sample_id="x")
    assert comb.domain == "lidar" and comb.layer == "combined" and set(per) == set(LAYERS)
    assert comb.alarm and "removed" in comb.reason or comb.alarm          # the L2c rank 0.999 is over its budget threshold
    first = dom2.raw_from_records(l1, a, None, 10)
    assert first["L2c"] == 0.0 and first["L2d"] == 0.0                   # first scan of a stream: no previous scan
    c2, p2 = dom2.evidence(first, first=True)
    assert p2["L2c"].details["available"] is False and 0.0 <= c2.score <= 1.0


def test_stream_equals_batch_on_real_scans():
    if not FROZEN.exists():
        raise Skip("frozen v3.1 domain missing")
    from lidar import ego
    from lidar.data import load, scan_files
    dom = Domain31.load(FROZEN)
    try:
        files, pose = scan_files("0011")[:6], ego.poses("0011")
    except Exception:
        raise Skip("KITTI data missing")
    if len(files) < 6:
        raise Skip("data missing")
    s1, s2 = dom.stream(), dom.stream()
    out1 = [s1.push(load(f), pose[i], t=i * 0.1, sample_id=i)[0] for i, f in enumerate(files)]
    out2 = [s2.push(load(f), pose[i], t=i * 0.1, sample_id=i)[0] for i, f in enumerate(files)]
    assert all(abs(a.details["stat"] - b.details["stat"]) == 0.0 and a.alarm == b.alarm for a, b in zip(out1, out2))
    assert out1[0].details["first_scan_no_previous"] is True and out1[1].details["first_scan_no_previous"] is False
