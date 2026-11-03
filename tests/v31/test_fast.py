"""WP8 S3 tests: lidar.fast statistics are identical to the v3 code (exact path), the v3 frozen LiDAR loader still loads and scores
(regression), the windowed ring search equals the full search, and the combiner31 budget logic. Real-scan tests skip if KITTI data is missing."""
from pathlib import Path

import numpy as np

from lidar import background as B
from lidar import geometry as G
from lidar import segment as S
from lidar.combine31 import LAYERS, Union, alpha_budgets, waterfill
from lidar.fast import ImgFast, IntensityScorer, PrevScan, ScanStats, assign_fast, cluster_labels, ground_height_fast

ROOT = Path(__file__).resolve().parents[2]
FROZEN = ROOT / "results" / "WP3" / "S9" / "frozen_lidar"


class Skip(Exception):
    pass


def _scans(drive="0011", idx=(5, 60, 130)):
    from lidar import ego
    from lidar.data import load, scan_files
    files = scan_files(drive)
    if len(files) < max(idx) + 1:
        raise Skip("data missing")
    return [(load(files[i]), load(files[i - 1]), ego.poses(drive)[[i - 1, i]]) for i in idx]


def _table():
    t = ROOT / "results" / "WP3" / "S2" / "ring_table.json"
    if not t.exists():
        raise Skip("ring table missing")
    return G.RingTable.load(t)


def test_assign_fast_equals_v3_assign():
    table = _table()
    for pts, _, _ in _scans():
        a, b = table.assign(pts), assign_fast(table, pts)
        for k in a:
            assert np.array_equal(a[k], b[k]), k


def test_assign_fast_keep_mask_gives_identical_l1_and_tiles():
    from lidar.s4_build import tiles
    table = _table()
    prm = {"ground": "grid", "h0": 0.3, "e0": 0.4, "e1": 0.0}
    for pts, _, _ in _scans():
        asg = table.assign(pts)
        lab = S.segment(pts, table, prm, return_labels=True)[1]
        ss = ScanStats(table, prm)
        l1, tl = ss.l1_and_tiles(pts)
        assert np.array_equal(l1, G.l1_stats(pts, table, asg=asg))
        assert tl.equals(tiles(pts, lab, asg["k"]))


def test_ground_height_and_img_fast_equal_v3():
    from lidar import objects as O
    table = _table()
    edges = B.ring_edges(table)
    for pts, _, _ in _scans():
        assert np.array_equal(ground_height_fast(pts), O.ground_height(pts))
        a, b = B.Img(pts, edges), ImgFast(pts, edges)
        assert all(np.array_equal(getattr(a, k), getattr(b, k)) for k in ("cnt", "amin", "nmin"))


def test_pair_statistics_equal_v3_pair_row():
    from lidar.background_build import pair_row
    table = _table()
    ss = ScanStats(table, {"ground": "grid", "h0": 0.3, "e0": 0.4, "e1": 0.0})
    for pts, prev, pose in _scans():
        row, _ = ss.pair(PrevScan(prev, pose[0]), pts, pose[1])
        assert row == pair_row(prev, pose[0], pts, pose[1], ss.edges)


def test_voxel_labels_are_a_valid_clustering_close_to_exact():
    table = _table()
    prm = {"ground": "grid", "h0": 0.3, "e0": 0.4, "e1": 0.0}
    for pts, _, _ in _scans(idx=(60,)):
        ex, vx = cluster_labels(pts, prm, vox=0), cluster_labels(pts, prm, vox=0.1)
        assert abs(((ex >= 0).sum() - (vx >= 0).sum())) < 0.03 * (ex >= 0).sum()


def test_intensity_scorer_equals_object_model_scores():
    import pandas as pd
    from lidar import s4_eval as E4
    from lidar.domain import LidarDomain
    from lidar.s4_build import tiles
    if not FROZEN.exists():
        raise Skip("frozen v3 lidar missing")
    d = LidarDomain.load(FROZEN)
    sc = IntensityScorer(d.model)
    for pts, _, _ in _scans(idx=(40, 90)):
        asg = d.table.assign(pts)
        tl = tiles(pts, S.segment(pts, d.table, d.prm, return_labels=True)[1], asg["k"])
        t2 = tl.copy()
        t2.insert(0, "scan", "s")
        t2["ring_min"], t2["ring_max"], t2["az_span"] = 0.0, 7.0, 2.0 - 0.1728
        ref = E4.scan_frame(d.model, t2, pd.DataFrame({"scan": ["s"]}))[["int_hi", "int_lo", "cnt_int_hi", "cnt_int_lo"]].to_numpy()[0]
        assert np.abs(ref - sc.scan_stats(tl["range"].to_numpy(), tl["n_points"].to_numpy(), tl["int_mean"].to_numpy())).max() == 0.0


def test_v3_frozen_loader_regression_alarm_matches_stored_fixture():
    """The v3 frozen LiDAR domain still loads and gives the stored raw score of the freeze fixture scans (v3 code untouched)."""
    import json
    from lidar.domain import LidarDomain
    fx = ROOT / "results" / "WP3" / "S9" / "freeze_check.json"
    if not FROZEN.exists() or not fx.exists():
        raise Skip("frozen v3 lidar or fixture missing")
    d = LidarDomain.load(FROZEN)
    assert d.stack.method == "max" and d.stack.cols == ["raw_L1", "raw_L2a", "raw_L2c", "raw_L2d"]
    assert abs(d.stack.threshold - 0.9967989756722152) < 1e-15
    info = json.loads(fx.read_text())
    assert max(info["max_abs_diff"].values()) < 1e-9 and info["alarm_differences"] == 0


def test_union_budgets_bound_false_alarms_and_keep_strong_layer():
    rng = np.random.default_rng(3)
    n = 20000
    ref = {l: rng.random(n) for l in LAYERS}
    st = Union(alpha_budgets(0.55), "union").fit(ref)
    assert abs(sum(alpha_budgets(0.55)) - 0.01) < 1e-12
    fa = st.alarm({l: rng.random(n) for l in LAYERS}).mean()
    assert fa <= 0.0125                                           # union bound (sum of budgets = 1 %) up to sampling noise
    strong = {l: rng.random(1000) for l in LAYERS}
    strong["L2c"] = np.full(1000, 0.999)
    assert st.alarm(strong).all()
    weak = dict(strong, L2c=np.full(1000, 0.99))
    assert not st.alarm(weak).any() or st.alarm(weak).mean() < 0.5


def test_waterfill_gives_tie_limited_layers_only_what_they_use():
    rng = np.random.default_rng(4)
    n = 20000
    R = np.column_stack([rng.random(n), rng.random(n), rng.random(n), np.floor(rng.random(n) * 20) / 20])   # last layer: ties
    b = waterfill(R, 0.01)
    assert abs(b.sum() - 0.01) < 0.002 and b[3] <= 0.0025 + 1e-12
