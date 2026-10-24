"""WP3 S4 tests: L2a density / intensity vs range per object (synthetic object tables)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lidar import density as D
from lidar.phantom import Calib


def calib():
    return Calib([6, 12, 16, 20, 25, 30, 35, 45], [0.6] * 7, np.inf, [[np.array([0.2])] for _ in range(7)])


def objs(n, rng, r=None, q=0.6, im=None):
    rows = []
    for _ in range(n):
        rr = rng.uniform(8, 40) if r is None else r
        rings, steps = int(rng.integers(4, 12)), int(rng.integers(10, 60))
        slots = rings * (steps)
        rows.append(dict(range=rr, ring_min=10, ring_max=10 + rings - 1, az_span=(steps - 1) * 0.1728,
                         n_points=max(int(rng.binomial(int(slots), min(q, 1.0))), 1), int_mean=rng.normal(0.2, 0.05) if im is None else im))
    return pd.DataFrame(rows)


def test_slots_from_angular_footprint():
    o = pd.DataFrame(dict(ring_min=[3], ring_max=[7], az_span=[10 * 0.1728]))
    assert abs(D.slots_of(o)[0] - 5 * 11) < 1e-9


def test_dense_far_and_sparse_near_are_improbable():
    rng = np.random.default_rng(0)
    m = D.ObjectModel(calib(), nmin=10).fit(objs(4000, rng))
    clean = m.scores(objs(500, rng))
    dense = m.scores(objs(200, rng, q=3.0))          # three times the expected occupancy
    sparse = m.scores(objs(200, rng, q=0.1))
    assert dense.dens_hi.median() > 3 * clean.dens_hi.median() + 0.5
    assert sparse.dens_lo.median() > 3 * clean.dens_lo.median() + 0.5
    assert dense.dens_lo.median() < 0.5 and sparse.dens_hi.median() < 0.5


def test_intensity_score_and_unscored_objects():
    rng = np.random.default_rng(1)
    m = D.ObjectModel(calib(), nmin=10).fit(objs(3000, rng))
    bright = m.scores(objs(100, rng, im=0.95))
    assert bright.int_hi.median() > 2.5 and bright.int_lo.median() < 0.5
    tiny = objs(5, rng)
    tiny["n_points"] = 3
    assert (m.scores(tiny).to_numpy() == 0).all()


def test_scan_max_and_union_layer_budget():
    rng = np.random.default_rng(2)
    m = D.ObjectModel(calib(), nmin=10).fit(objs(3000, rng))
    o = objs(3000, rng)
    o["scan"] = np.repeat(np.arange(300), 10)
    sc = D.scan_scores(o, m.scores(o))
    assert len(sc) == 300 and (sc.dens_hi >= 0).all()
    lay = D.L2aUnion().calibrate(sc, 0.01)
    a = lay.calibrator.transform(lay.raw_scores(sc)) >= lay.threshold
    assert a.mean() <= 0.011
    bad = sc.iloc[:20].copy()
    bad["dens_hi"] = 8.0
    assert (lay.calibrator.transform(lay.raw_scores(bad)) >= lay.threshold).all()
    ev = lay.score(bad)
    assert ev[0].layer == "L2a" and ev[0].alarm
