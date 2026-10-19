"""Tests for the WP0 S3 regression (tools/WP0_regression.py): B2 layer on synthetic data, and the
stored comparison with the v2 json (skipped if the regression has not been run)."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
_spec = importlib.util.spec_from_file_location("wp0_regression", ROOT / "tools" / "WP0_regression.py")
R = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(R)


def _frame(n=2000, seed=0):
    rng = np.random.RandomState(seed)
    return pd.DataFrame({"dr_resid_10": np.abs(rng.normal(0, 3, n)), "still": np.zeros(n)})


def test_b2_layer_budget_and_still_rule():
    cal = _frame()
    lay = R.B2Layer().calibrate(cal, budget=0.01)
    ev = lay.score(cal)
    assert np.mean([e.alarm for e in ev]) <= 0.01 + 1e-12
    test = _frame(500, 1)
    test.loc[3, "still"] = 1.0
    test.loc[3, "dr_resid_10"] = 0.0
    ev = lay.score(test)
    assert ev[3].alarm and ev[3].score > 0.99          # frozen position alarms on its own


def test_b2_raw_equivalent_threshold_matches_rule():
    cal = _frame()
    lay = R.B2Layer().calibrate(cal, budget=0.01)
    t = R.raw_equiv_threshold(lay)
    x = np.r_[np.linspace(0, 15, 301), t, np.nextafter(t, np.inf)]
    probe = pd.DataFrame({"dr_resid_10": x, "still": np.zeros(len(x))})
    alarm = np.array([e.alarm for e in lay.score(probe)])
    assert (alarm == (x > t)).all()


def test_regression_matches_v2_json():
    p = ROOT / "results" / "WP0" / "regression_b2.json"
    if not p.exists():
        class Skip(Exception):
            pass
        raise Skip("run tools/WP0_regression.py first")
    cmp = json.loads(p.read_text())["comparison_with_v2"]
    bad = [k for k, v in cmp.items() if not v["match"] and k != "threshold_m"]
    assert not bad, bad
    assert abs(cmp["threshold_m"]["abs_diff"]) < 2e-3
