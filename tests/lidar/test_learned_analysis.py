"""WP3 S7 tests: stack evaluation, episodes and the 'adds beyond physics' decision on synthetic score stores."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from lidar import learned_eval as LE
from WP3_S7_analysis import analyse


def _store(seed=0, gain=True):
    rng = np.random.default_rng(seed)
    drives = ["0001", "0002", "0003", "0004"]

    def clean(n_per):
        return pd.DataFrame({"scan": [f"{d}/{i}" for d in drives for i in range(n_per)], "drive": np.repeat(drives, n_per),
                             "idx": np.tile(np.arange(n_per), len(drives)), "attack": "clean"})

    ref, cl = clean(400), clean(150)
    for c in ("raw_L1", "raw_L2a", "raw_L2c", "raw_L2d", "raw_L3", "raw_L4"):
        ref[c] = rng.random(len(ref))
        cl[c] = rng.random(len(cl))
    att = pd.concat([pd.DataFrame({"scan": [f"x{a}{i}" for i in range(200)], "drive": "0001", "idx": np.arange(200), "attack": a})
                     for a in LE.PHYS], ignore_index=True)
    for c in ("raw_L1", "raw_L2a", "raw_L2c", "raw_L2d", "raw_L3", "raw_L4"):
        att[c] = rng.random(len(att))
    att.loc[att.attack == "PointDrop", "raw_L2c"] = 0.999 + 1e-4 * rng.random((att.attack == "PointDrop").sum())      # physics layer catches PointDrop
    if gain:
        k = att.attack == "ph_replace_near"
        att.loc[k, "raw_L4"] = 0.99 + 0.01 * rng.random(k.sum())                                                # L4 catches near replace phantoms
    ep_rows = []
    for e in range(4):
        for st in range(1, 31):
            ep_rows.append(("0001", 10 + st, f"e{e}/{st}", "ep_replace_near", e, st))
    ep = pd.DataFrame(ep_rows, columns=["drive", "idx", "scan", "attack", "ep", "step"])
    for c in ("raw_L1", "raw_L2a", "raw_L2c", "raw_L2d", "raw_L3", "raw_L4"):
        ep[c] = rng.random(len(ep)) if c != "raw_L4" else 0.99 + 0.01 * rng.random(len(ep))
    return {"ref": ref, "clean": cl, "att": att, "ep": ep}


def test_analyse_detects_gain_and_no_gain():
    res = analyse(_store(gain=True), "max")
    assert res["layers"]["raw_L2c"]["det"]["PointDrop"] > 0.95
    assert res["stacks"]["physics/max"]["det"]["PointDrop"] > 0.9
    a = res["adds"]["physics+L4"]
    assert "ph_replace_near" in a["attacks_with_gain"] and a["per_attack"]["ph_replace_near"]["ci95"][0] > 0
    res0 = analyse(_store(gain=False), "max")
    assert res0["adds"]["physics+L4"]["attacks_with_gain"] == []
    assert not res0["adds"]["physics+L4"]["adds"]


def test_threshold_gives_one_percent_on_reference_and_stack_fa_bounded():
    s = _store()
    r = LE.evaluate_stack(s["ref"], s["clean"], s["att"], ["raw_L1", "raw_L2a"], "max")
    assert r["fa_ref"] <= 0.0101
    assert 0 <= r["fa"] <= 0.1 and set(r["fa_per_drive"]) == {"0001", "0002", "0003", "0004"}


def test_episodes_detect_persistent_high_scores_and_report_false_rate():
    res = analyse(_store(), "max")
    ep = res["layers"]["raw_L4"]["episodes"]
    assert ep["kinds"]["ep_replace_near"]["detected_3s"] == 4 and ep["kinds"]["ep_replace_near"]["episodes"] == 4
    assert 0 <= ep["false_episode_rate"] <= 1 and ep["n_clean_windows"] > 0
    flat = res["layers"]["raw_L3"]["episodes"]["kinds"]["ep_replace_near"]
    assert flat["detected_3s"] <= 2
