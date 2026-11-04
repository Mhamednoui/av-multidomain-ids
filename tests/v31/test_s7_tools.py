"""WP8 S7 tool tests: the H31 path patches resolve to the D04b folder without touching the v3 drives, the histogram bootstrap reproduces the exact AUC / detection, the paired bootstrap of two
identical systems is zero. Synthetic data only; no H31 file is opened (the patch test only builds path strings)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def test_h31_path_patch_maps_only_h31_ids():
    import WP8_S7_lib as S7
    from gps import stream as GS
    from lidar import data as LD
    o_oxts, o_drive = GS.oxts_dir, LD.drive_dir
    try:
        names = S7.patch_h31_paths()
        assert len(names) == 13 and not (set(names) & set(GS.TEST + GS.VAL + [d for d in LD.DRIVES]))
        d = sorted(names)[0]
        assert str(GS.oxts_dir(d)).startswith(str(S7.D04B)) and str(LD.drive_dir(d)).startswith(str(S7.D04B))
        assert GS.oxts_dir("0011") == o_oxts("0011") and LD.drive_dir("0011") == o_drive("0011")
    finally:
        GS.oxts_dir, LD.drive_dir = o_oxts, o_drive


def test_hist_bootstrap_matches_exact_auc():
    import WP8_S7_domains as D
    rng = np.random.default_rng(1)
    neg, pos = rng.normal(0, 1, 6000), rng.normal(1.2, 1, 800)
    gn, gp = rng.integers(0, 8, len(neg)).astype(str), rng.integers(0, 8, len(pos)).astype(str)
    r = D.row("t", neg, gn, pos, gp, "x")
    assert abs(r["auc"] - D.P1.auc_np(neg, pos)) < 1e-12
    assert r["auc_ci"][0] < r["auc"] < r["auc_ci"][1] and r["det@1.0%_ci"][0] <= r["det@1.0%"] <= r["det@1.0%_ci"][1] + 1e-9
    edges = np.unique(np.quantile(np.r_[neg, pos], np.linspace(0, 1, D.NBIN + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    auc, det = D._stats(D._hist(neg, edges), D._hist(pos, edges))
    assert abs(auc - r["auc"]) < 2e-3


def test_paired_clean_of_identical_runs_is_zero():
    import WP8_S7_sim as T
    rc = [{"alarm_ticks": 5, "events": 2, "n": 1000, "hours": 0.28, "levels": {"SAFE_STOP": 0}} for _ in range(6)]
    out = T.paired_clean(rc, rc, "events")
    assert out["diff"] == 0 and out["ci"] == [0.0, 0.0]
