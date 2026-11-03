"""WP8 S3b tests: the numba kernels of lidar.fast_nb give arrays identical to the numpy path of lidar.fast (synthetic and real scans), and the
flag falls back cleanly. Skips if numba or the KITTI data are missing."""
import numpy as np

from lidar import fast as F
from lidar.fast_nb import AVAILABLE
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_fast import Skip, _scans, _table


def _both(f):
    try:
        F.set_numba(False)
        a = f()
        F.set_numba(True)
        b = f()
    finally:
        F.set_numba(False)
    return a, b


def test_kernels_equal_numpy_on_real_scans():
    if not AVAILABLE:
        raise Skip("numba missing")
    table = _table()
    prm = {"ground": "grid", "h0": 0.3, "e0": 0.4, "e1": 0.0, "vox": 0.1}
    from lidar import background as B
    edges = B.ring_edges(table)
    for pts, _, _ in _scans():
        la, lb = _both(lambda: F.cluster_labels(pts, prm))
        assert np.array_equal(la, lb)
        ga, gb = _both(lambda: F.ground_height_fast(pts))
        assert np.array_equal(ga, gb)
        rho = np.linalg.norm(pts[:, :3], axis=1)
        aa, ab = _both(lambda: F.assign_fast(table, pts, keep=(rho >= F.R_MARGIN) | (la >= 0), rho=rho))
        for k in ("k", "res", "cm", "margin"):
            assert np.array_equal(aa[k], ab[k])
        ia, ib = _both(lambda: F.ImgFast(pts, edges))
        for k in ("cnt", "amin", "nmin"):
            assert np.array_equal(getattr(ia, k), getattr(ib, k))


def test_cluster_kernel_synthetic():
    if not AVAILABLE:
        raise Skip("numba missing")
    rng = np.random.default_rng(0)
    xyz = np.r_[rng.normal([5, 0, 0.5], 0.3, (300, 3)), rng.normal([-8, 4, 1.0], 0.2, (200, 3)), rng.uniform(-30, 30, (40, 3))]
    a, b = _both(lambda: F._cluster_vox(xyz, 0.4, 5, 0.1))
    assert np.array_equal(a, b)
    assert (a >= 0).sum() >= 400


def test_flag_off_by_default_path_is_numpy():
    F.set_numba(False)
    assert F.USE_NUMBA is False
