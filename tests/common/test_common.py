"""Unit tests for common/ (WP0 S2). Fixtures: synthetic arrays and csv/json only."""
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from common.calibration import ECDFCalibrator
from common.combiner import DomainCombiner
from common.evaluate import evaluate_domain, markdown_table
from common.evidence import Evidence
from common.layer import Layer
from common.metrics import budget_threshold, detection_delay, merge_delays, detection_at_budget
from common.motion import MotionEstimate
from common.splits import group_split, group_halves, save_splits, load_splits, mask
from common.toy import toy_run, toy_layers, make_streams


def test_budget_threshold_never_exceeds_budget():
    rng = np.random.RandomState(0)
    for budget in (0.001, 0.01, 0.02, 0.1, 0.5):
        for s in (rng.normal(size=5000),
                  np.round(rng.normal(size=5000), 1),            # heavy ties
                  np.zeros(1000),                                # all tied
                  np.r_[np.zeros(990), np.ones(10)]):            # tie at the quantile
            thr = budget_threshold(s, budget)
            assert (s >= thr).mean() <= budget + 1e-12, (budget, (s >= thr).mean())


def test_budget_threshold_is_tight_without_ties():
    s = np.arange(1000, dtype=float)
    thr = budget_threshold(s, 0.01)
    assert (s >= thr).sum() == 10


def test_calibration_monotone_and_range():
    rng = np.random.RandomState(1)
    cal = ECDFCalibrator().fit(rng.exponential(size=500))
    x = np.sort(rng.exponential(size=2000) * 3)
    c = cal.transform(x)
    assert np.all(np.diff(c) >= 0) and c.min() >= 0 and c.max() <= 1
    assert 0.999 < cal.transform(np.array([1e9]))[0] < 1.0 and cal.transform(np.array([-1e9]))[0] == 0.0
    c2 = ECDFCalibrator.from_dict(json.loads(json.dumps(cal.to_dict())))
    assert np.array_equal(c2.transform(x), c)


def test_layer_contract():
    streams = make_streams(2, seed=3)
    df = pd.concat(streams.values(), ignore_index=True)
    layer = toy_layers()[0]
    layer.calibrate(df[df.y == 0], budget=0.01)
    ev = layer.score(df)
    assert len(ev) == len(df) and isinstance(ev[0], Evidence)
    assert all(0 <= e.score <= 1 for e in ev)
    fa = np.mean([e.alarm for e, y in zip(ev, df.y) if y == 0])
    assert fa <= 0.01 + 1e-12
    assert all((e.reason != "") == e.alarm for e in ev)
    with tempfile.TemporaryDirectory() as d:
        layer.save(d)
        l2 = toy_layers()[0].load(d)
        assert [e.alarm for e in l2.score(df)] == [e.alarm for e in ev]


def test_motion_estimate_fields():
    m = MotionEstimate(t=1.0, source="can", speed=3.0, yaw_rate=0.1, displacement=(1.0, 2.0), sigma=0.5)
    assert m.source == "can" and m.displacement == (1.0, 2.0)


def test_combiner_on_synthetic_layers():
    val, test = toy_run(seed=0)
    for method in ("noisy_or", "max", "logistic", "auto"):
        comb = DomainCombiner(method=method).fit(val.evidence, val.y, val.group)
        out = comb.combine(test.evidence)
        assert len(out) == len(test.y) and all(e.layer == "combined" for e in out)
        s = np.array([e.score for e in out]); assert s.min() >= 0 and s.max() <= 1
        a = np.array([e.alarm for e in out]); y = np.asarray(test.y).astype(bool)
        assert a[y].mean() > 0.4                    # toy attacks are only partly separable at a 1% budget
        assert a[~y].mean() < 0.05                  # false alarms stay small on unseen test streams
        if a.any():
            i = int(np.flatnonzero(a)[0]); assert "layers fired" in out[i].reason
        assert all(e.reason == "" for e, al in zip(out, a) if not al)
    assert comb.method in ("noisy_or", "max", "logistic") and set(comb.selection) == {"noisy_or", "logistic", "max"}


def test_combiner_beats_weakest_layer():
    val, test = toy_run(seed=5)
    comb = DomainCombiner(method="noisy_or").fit(val.evidence, val.y, val.group)
    a = np.array([e.alarm for e in comb.combine(test.evidence)]); y = np.asarray(test.y).astype(bool)
    weakest = min(np.mean([e.alarm for e, yy in zip(evs, y) if yy]) for evs in test.evidence.values())
    assert a[y].mean() > weakest


def test_combiner_threshold_tie_safe_on_val():
    val, _ = toy_run(seed=2)
    comb = DomainCombiner(method="max").fit(val.evidence, val.y, val.group)
    a = np.array([e.alarm for e in comb.combine(val.evidence)]); y = np.asarray(val.y).astype(bool)
    assert a[~y].mean() <= comb.budget + 1e-12


def test_group_split_never_shares_a_group():
    groups = [f"drive{i}" for i in range(20) for _ in range(5)]
    for seed in range(5):
        sp = group_split(groups, seed=seed)
        allids = sum(sp.values(), [])
        assert len(allids) == len(set(allids)) == 20
        assert set(allids) == set(groups)
        for a in sp:
            for b in sp:
                if a != b:
                    assert not set(sp[a]) & set(sp[b])
    ga, gb = group_halves(groups)
    assert not set(ga) & set(gb) and set(ga) | set(gb) == set(groups)
    m = mask(groups, ga); assert m.sum() == 5 * len(ga)


def test_split_save_load_and_overlap_rejected():
    sp = {"train": ["a", "b"], "val": ["c"], "test": ["d"]}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "splits.json"
        save_splits(sp, p)
        assert load_splits(p) == sp
        try:
            save_splits({"train": ["a"], "test": ["a"]}, p)
        except ValueError:
            return
        raise AssertionError("overlap not rejected")


def test_detection_delay_segments():
    t = np.arange(10.0); y = np.array([0, 0, 1, 1, 1, 0, 1, 1, 0, 0]); al = np.array([0, 0, 0, 1, 0, 0, 0, 0, 0, 0])
    d = detection_delay(t, y, al)
    assert d["n_segments"] == 2 and d["delays"] == [1.0, None]
    m = merge_delays([d]); assert m["detected_fraction"] == 0.5 and m["median_delay_s"] == 1.0


def test_detection_at_budget_keys():
    rng = np.random.RandomState(0)
    s = rng.normal(size=1000); y = rng.rand(1000) < 0.3; s[y] += 2
    r = detection_at_budget(s[~y], s, y, np.where(y, "x", "normal"), 0.01)
    assert r["false_alarm_rate"] <= 0.01 and 0 < r["detection"] < 1 and "x" in r["detection_by_attack"]


def test_ablation_output_shape():
    val, test = toy_run(seed=0)
    with tempfile.TemporaryDirectory() as d:
        res = evaluate_domain("toy", val, test, out_dir=d)
        names = res["layer_names"]; assert len(names) == 3
        expect = {"all"} | {f"only_{n}" for n in names} | {f"all_but_{n}" for n in names}
        assert set(res["ablation"]) == expect
        assert (Path(d) / "toy.json").exists() and (Path(d) / "toy.md").exists()
        loaded = json.loads((Path(d) / "toy.json").read_text())
        assert set(loaded["ablation"]) == expect
        for r in res["ablation"].values():
            assert set(["auc", "detection", "false_alarm_rate", "detection_by_attack", "delay"]) <= set(r)
        md = markdown_table(res)
        assert all(k in md for k in expect)
        assert res["layers"][names[0]]["false_alarm_rate"] <= 0.05


def test_harness_resets_state_per_group():
    from common.evaluate import score_groups

    class Counter(Layer):
        name = "c"
        def __init__(self): super().__init__(); self.n = 0
        def reset(self): self.n = 0
        def raw_scores(self, samples):
            out = np.arange(len(samples)) + self.n; self.n += len(samples); return out

    l = Counter(); l.calibrate(pd.DataFrame({"x": range(10)}))
    streams = {"a": pd.DataFrame({"x": range(5)}), "b": pd.DataFrame({"x": range(5)})}
    ev = score_groups(l, streams)
    assert [e.details["raw"] for e in ev] == [0, 1, 2, 3, 4] * 2


def test_calibration_tail_strict_and_continuous():
    rng = np.random.RandomState(4)
    normal = rng.exponential(size=1000)
    cal = ECDFCalibrator().fit(normal)
    top = normal.max()
    x = top + np.linspace(1e-6, 20, 400) * cal.scale_
    c = cal.transform(x)
    assert np.all(np.diff(c[:200]) > 0) and c.max() < 1.0 and c.min() >= cal.transform(np.array([top]))[0]
    at = cal.transform(np.array([top, np.nextafter(top, np.inf)]))
    assert at[1] >= at[0] and at[1] - at[0] <= 1.0 / len(normal) + 1e-12      # joins, no backwards step
    both = cal.transform(np.sort(np.r_[normal, x]))
    assert np.all(np.diff(both) >= 0)
    assert cal.transform(np.float64(top + 1.0)).shape == ()


def test_calibration_tail_roundtrip_and_constant_normals():
    cal = ECDFCalibrator().fit(np.r_[np.zeros(100), np.ones(5)])
    cal2 = ECDFCalibrator.from_dict(json.loads(json.dumps(cal.to_dict())))
    x = np.array([0.0, 1.0, 1.5, 3.0, 100.0])
    assert np.array_equal(cal.transform(x), cal2.transform(x)) and cal2.scale_ == cal.scale_
    k = ECDFCalibrator().fit(np.full(50, 2.0))
    r = k.transform(np.array([2.0, 2.0 + 1e-9, 2.0 + 2e-9]))
    assert r[1] < r[2] < 1.0 and k.scale_ > 0


# ---- WP0 S4: noisy_or in log space -----------------------------------------------------------------------------------
def test_noisy_or_log_same_ranking_as_product_on_unsaturated_inputs():
    from scipy.stats import spearmanr
    from common.combiner import noisy_or_score, noisy_or_stat
    from common.metrics import budget_threshold
    X = np.random.default_rng(0).uniform(0.0, 0.9, size=(3000, 4))
    old = 1.0 - np.prod(1.0 - X, axis=1); new = noisy_or_score(X)
    assert spearmanr(old, new).correlation > 1 - 1e-12      # 1.0 up to float rounding of the correlation itself
    assert np.all(np.argsort(old, kind="stable") == np.argsort(new, kind="stable"))
    S = noisy_or_stat(X)
    for q in (0.5, 0.9, 0.99):                       # same alarm set at a threshold mapped through the transform
        t_old = np.quantile(old, q); t_new = (lambda s: s / (s + 4))(-np.log1p(-t_old))
        assert np.array_equal(old >= t_old, new >= t_new - 1e-15)
    t_o = budget_threshold(old, 0.01); t_n = budget_threshold(new, 0.01)
    assert np.array_equal(old >= t_o, new >= t_n) and 0.0 <= new.min() and new.max() < 1.0 and S.min() >= 0


def test_noisy_or_log_no_saturation_with_16_correlated_layers():
    from common.combiner import noisy_or_score
    from common.metrics import budget_threshold
    rng = np.random.default_rng(1)
    e = rng.uniform(1.0, 6.0, size=(5000, 1))                         # shared severity: 1 - s = 10**-e
    X = 1.0 - 10.0 ** -(e * rng.uniform(0.8, 1.2, (5000, 16)))        # 16 correlated layers
    X[:200] = 1.0 - 10.0 ** -(rng.uniform(4.0, 8.0, (200, 1)) * rng.uniform(0.95, 1.05, (200, 16)))   # 4% extreme rows: prod(1 - s) < 1e-60
    old = 1.0 - np.prod(1.0 - X, axis=1); new = noisy_or_score(X)
    assert (old == old.max()).mean() > 0.01                      # old form ties at the top above the budget
    assert (new == new.max()).mean() <= 0.01                     # new form: ties at the top within the budget
    assert budget_threshold(old, 0.01) > old.max()               # old: threshold above every score -> 0 alarms
    t = budget_threshold(new, 0.01)
    assert 0 < (new >= t).mean() <= 0.01
