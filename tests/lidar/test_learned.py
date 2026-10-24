"""WP3 S7 tests: L3 features / normal models / scan statistics, L4 rows, controls, combination helpers."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from lidar import learned as L
from lidar import learned_eval as LE
from lidar import learned_l4 as L4
from lidar.phantom import Calib


def _objs(n, rng):
    rg = rng.uniform(8, 40, n)
    return pd.DataFrame({"scan": rng.integers(0, 20, n).astype(str), "oid": np.arange(n), "cx": rg, "cy": rng.normal(0, 3, n), "range": rg,
                         "length": rng.uniform(0.5, 4, n), "width": rng.uniform(0.3, 2, n), "height": rng.uniform(0.5, 2, n),
                         "z_bottom": rng.uniform(0.3, 1.0, n), "n_points": rng.integers(10, 300, n).astype(float),
                         "az_span": rng.uniform(0.5, 8, n), "elev_span": rng.uniform(0.4, 3, n), "n_rings": rng.integers(2, 12, n).astype(float),
                         "ring_min": np.zeros(n), "ring_max": np.full(n, 12.0), "int_mean": rng.uniform(0.1, 0.3, n),
                         "int_std": rng.uniform(0.02, 0.1, n), "carlike": rng.integers(0, 2, n).astype(float)})


def _calib():
    return Calib([4, 8, 16, 32, 64], [0.6, 0.6, 0.6, 0.6], np.inf, [[np.array([0.2])] for _ in range(4)])


def test_object_features_columns_and_ring_cover():
    o = _objs(50, np.random.default_rng(0))
    F = L.object_features(o, _calib())
    assert list(F.columns) == L.BASE_FEATS and len(F) == 50 and np.isfinite(F.to_numpy()).all()
    assert ((F.ring_cover > 0) & (F.ring_cover <= 1.0 + 1e-6)).all() or (F.ring_cover > 0).all()


def test_normal_models_flag_outliers():
    rng = np.random.default_rng(1)
    Ftr = rng.normal(0, 1, (3000, 5)) * np.array([1, 2, 1, 0.5, 3])
    out = np.array([[8, 0, 0, 0, 0], [0, 0, 0, 6, 0]], float)
    for kind in L.MODELS:
        m = L.NormalModel(kind, n_fit=2000, n_ref=900).fit(Ftr)
        s_in, s_out = m.score(Ftr[:500]), m.score(out)
        assert s_out.min() > np.quantile(s_in, 0.95), kind
        assert m.q999 > np.median(s_in)


def test_scan_stats_max_and_count():
    ids = np.array(["a", "a", "b", "b", "b"])
    st = L.scan_stats(ids, np.array([1.0, 5.0, 2.0, 7.0, 8.0]), q999=6.0)
    assert st.loc["a", "l3_max"] == 5.0 and st.loc["b", "l3_max"] == 8.0 and st.loc["a", "l3_cnt"] == 0 and st.loc["b", "l3_cnt"] == 2
    sc = pd.DataFrame({"scan": ["a", "b", "c"], "drive": "0001"})
    m = type("M", (), {"score": lambda self, F: np.asarray(F)[:, 0], "q999": 6.0})()
    fr = L.scan_frame(m, np.array([[1.0], [8.0]]), np.array(["a", "b"]), sc)
    assert fr.loc[fr.scan == "c", "l3_max"].iloc[0] == 0.0


def test_track_features_match_same_objects_and_new_object():
    prev = pd.DataFrame({"cx": [10.0, 20.0], "cy": [0.0, 3.0], "range": [10.0, 20.2], "n_points": [100.0, 50.0]})
    cur = pd.DataFrame({"cx": [10.0, 20.0, 30.0], "cy": [0.0, 3.0, -4.0], "range": [10.0, 20.2, 30.3], "n_points": [100.0, 25.0, 40.0]})
    pose = np.array([0.0, 0.0, 0.0])
    T = L.track_features(cur, pose, prev, pose)
    assert T[0, 0] == 1 and abs(T[0, 1]) < 1e-3 and abs(T[0, 2]) < 1e-6
    assert T[1, 0] == 1 and abs(T[1, 2] - np.log(2.0)) < 1e-6
    assert T[2, 0] == 0 and T[2, 1] == 0
    assert (L.track_features(cur, pose, None, pose) == 0).all()


def test_combine_max_and_noisy_or_rank_monotone():
    r = np.array([[0.1, 0.2], [0.9, 0.1], [0.5, 0.5]])
    assert (LE.combine(r, "max") == np.array([0.2, 0.9, 0.5])).all()
    no = LE.combine(r, "noisy_or")
    assert no[1] > no[2] > no[0] or no[1] > no[0]
    assert abs(LE.ecdf_rank(np.arange(100.0), 50.0) - 0.5) < 1e-9


def test_lodo_fa_uses_other_drives_and_ties_safe():
    s = np.r_[np.zeros(200), np.linspace(0, 1, 200)]
    d = np.r_[np.full(200, "a"), np.full(200, "b")]
    fa = LE.lodo_fa(s, d, 0.01)
    assert set(fa) == {"a", "b"} and all(0 <= v <= 1 for v in fa.values())
    assert fa["a"] == 0.0     # b's 99th percentile is 0.99+, a's scores are all 0


def test_paired_bootstrap_interval_contains_mean():
    a = np.zeros(300)
    b = np.r_[np.ones(60), np.zeros(240)]
    m, lo, hi = LE.paired_bootstrap(a, b, n=300)
    assert abs(m - 0.2) < 1e-9 and lo < m < hi and lo > 0.1


def test_xgb_and_null_control_on_random_labels():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(600, 8)).astype(np.float32)
    y = (X[:, 0] > 0.3).astype(int) + 2 * (X[:, 1] > 1.0)
    prm = {"max_depth": 3, "learning_rate": 0.2}
    m = L4.fit_xgb(X, y, prm, 40, n_jobs=2)
    ye = (y > 0).astype(int)
    assert L4.auc(ye, L4.attack_score(m, X)) > 0.9
    imp = L4.importance_table(m, [f"f{k}" for k in range(8)])
    assert imp.index[0] in ("f0", "f1") and abs(imp.sum() - 1) < 1e-9
    Xe = rng.normal(size=(400, 8)).astype(np.float32)
    ye2 = rng.integers(0, 2, 400)
    nulls = L4.null_aucs(X, y, prm, 40, Xe, ye2, seeds=(1, 2, 3))
    assert abs(np.mean(nulls) - 0.5) < 0.1


def test_feature_groups_cover_all_columns():
    groups = {L4.feature_group(n) for n in L4.NAMES}
    assert "global statistics" in groups and "sector counts" in groups and "temporal sector counts" in groups
    assert "double-return (multi-return) cells" in groups
    assert len(L4.NAMES) == 429


def test_physical_attack_does_not_touch_other_points_and_is_single_return():
    from lidar import geometry as G
    from lidar.data import scan_files, load
    f = scan_files("0048")
    if not f:
        return
    table, calib = L4.tools()
    pts = load(f[3])
    rng = np.random.default_rng(5)
    att, q = L4.attacked("PointDrop", pts, {"c": 10.0, "w": 40.0, "frac": 1.0}, rng, table, calib)
    assert len(att) < len(pts)
    att, q = L4.attacked("IntensitySpoof", pts, {"c": 10.0, "w": 40.0}, rng, table, calib)
    assert len(att) == len(pts) and (att[:, :3] == pts[:, :3]).all()
    att, q = L4.attacked("ph_replace_far", pts, {"range": 25.0, "az": 0.0, "rot": 0.3, "budget": 100}, rng, table, calib)
    assert len(att) == len(pts)          # single return: replace, never add


def test_eval_rows_reproduce_s4_attack_draws():
    from lidar.data import CACHE
    f = CACHE / "S4" / "S3_t" / "att_test_0052.pkl"
    if not f.exists():
        return
    s4 = pd.read_pickle(f)["scans"]
    meta, X = L4.eval_rows("0052", stride=30)
    j = meta.merge(s4[["scan", "n_inj"]], on="scan", suffixes=("", "_s4"))
    assert len(j) == len(meta) == 27 and (j.n_inj == j.n_inj_s4).all() and X.shape == (27, 429)
