"""WP3 S4 tests: tile table of the clusters and evaluation helpers."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lidar import density as D
from lidar import s4_build as B
from lidar import s4_eval as E


def test_tiles_count_and_injected_share():
    rng = np.random.default_rng(0)
    n = 60
    pts = np.c_[10 + rng.uniform(0, 0.3, n), rng.uniform(-0.1, 0.1, n), rng.uniform(0, 1, n), rng.uniform(0.2, 0.4, n)].astype(np.float32)
    lab = np.zeros(n, int)
    k = np.full(n, 20)
    inj = np.zeros(n, bool)
    inj[:30] = True
    t = B.tiles(pts, lab, k, inj)
    assert t.n_points.sum() == n and abs(t.ph_n.sum() - 30) < 1e-6
    assert (t.n_points >= B.TILE_MIN).all() and t["range"].between(9.9, 10.5).all()
    lab[:] = -1
    assert len(B.tiles(pts, lab, k)) == 0


def test_scan_counts_and_frame_fill():
    s = pd.DataFrame({"dens_hi": [1.0, 3.0, 2.5], "dens_lo": [0, 0, 0], "int_hi": [0, 0, 0], "int_lo": [0, 0, 0]})
    scan = np.array(["a", "a", "b"])
    out = D.scan_scores(pd.DataFrame({"scan": scan}), s)
    assert out.loc["a", "cnt_dens_hi"] == 1 and out.loc["b", "cnt_dens_hi"] == 1 and out.loc["a", "dens_hi"] == 3.0
    assert set(D.ALL_STATS) <= set(out.columns)


def test_lodo_pools_every_drive():
    rng = np.random.default_rng(3)
    from lidar.phantom import Calib
    calib = Calib([6, 12, 16, 20, 25, 30, 35, 45], [0.6] * 7, np.inf, [[np.array([0.2])] for _ in range(7)])
    scans, objs = [], []
    for d in ("a", "b", "c"):
        for i in range(30):
            sid = f"{d}/{i}"
            scans.append(dict(drive=d, idx=i, scan=sid))
            objs.append(pd.DataFrame(dict(scan=sid, range=rng.uniform(5, 40, 40), n_points=rng.integers(8, 60, 40).astype(float),
                                          int_mean=rng.normal(0.2, 0.05, 40), ring_min=0.0, ring_max=7.0, az_span=2.0 - 0.1728)))
    oof = E.lodo_scan_scores(pd.concat(objs, ignore_index=True), pd.DataFrame(scans), ["a", "b", "c"], calib, 8)
    assert len(oof) == 90 and set(oof.drive) == {"a", "b", "c"}
