"""WP3 S9 tests: the analysis function on a synthetic score store (budget control, dilution, ablation, episodes, exact intervals)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from WP3_S9_analysis import HEAD, analyse, clopper


def _store(seed=0):
    rng = np.random.default_rng(seed)
    drives = ["0001", "0002", "0003", "0004"]

    def frame(n_per, attack, shift=None, ep=False, k=None):
        rows = []
        for d in drives:
            for i in range(n_per):
                rows.append(dict(scan=f"{d}/{i}|{attack}", drive=d, idx=i + 1, attack=attack, ep=i // 30, step=i % 30 + 1))
        f = pd.DataFrame(rows)
        for c in HEAD:
            f[c] = rng.uniform(size=len(f))
        if shift:
            f[shift] = rng.uniform(1.0, 1.5, size=len(f))
        return f

    ref, clean = frame(400, "clean"), frame(150, "clean")
    att = pd.concat([frame(60, "PointDrop", "raw_L2c"), frame(60, "IntensitySpoof", "raw_L2a"), frame(60, "ph_replace_far")], ignore_index=True)
    ep = frame(60, "ep_replace_near", "raw_L2d")
    return {"ref": ref, "clean": clean, "att": att, "ep": ep, "epw": frame(60, "epW_replace_far")}


def test_analyse_budget_dilution_and_ablation():
    res, st = analyse(_store(), "max")
    h = res["headline"]
    assert h["fa"] <= 0.03 and h["method"] == "max"
    assert h["det"]["PointDrop"]["det"] > 0.5 and h["det"]["IntensitySpoof"]["det"] > 0.5
    assert h["det"]["ph_replace_far"]["det"] < 0.1
    # a layer that carries an attack earns its place, a layer that carries nothing does not
    assert res["earns_place"]["raw_L2c"]["earns_place"] and res["earns_place"]["raw_L2a"]["earns_place"]
    assert not res["earns_place"]["raw_L1"]["earns_place"]
    # the shared budget costs detection against the layer alone
    assert res["dilution"]["PointDrop"]["loss"] >= 0
    # larger total budgets never detect less
    assert res["budgets"]["0.02"]["det"]["PointDrop"]["det"] >= h["det"]["PointDrop"]["det"]


def test_analyse_episodes_and_score_table():
    res, st = analyse(_store(1), "max")
    e = res["episodes"]["ep"]["stack"]
    assert e["kinds"]["ep_replace_near"]["detected_3s"] == e["kinds"]["ep_replace_near"]["episodes"] > 0
    assert 0 <= e["false_episode_rate"] <= 1
    assert e["kinds"]["ep_replace_near"]["median_first_alert_s"] is not None
    sc = res["_scores"]["att"]
    assert len(sc) == 720 and set(sc.columns) >= {"scan", "stat", "score", "alarm", "raw_L2c"}


def test_exact_interval():
    lo, hi = clopper(11, 21)
    assert 0.29 < lo < 0.31 and 0.73 < hi < 0.75
    assert clopper(0, 21)[0] == 0.0 and clopper(21, 21)[1] == 1.0
