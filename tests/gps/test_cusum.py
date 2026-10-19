"""Tests for gps/cusum.py and gps/lodo.py: CUSUM maths, scale convergence, freeze vs drag, drift detection, LODO helper, layer contract."""
import numpy as np
import pandas as pd

from gps import cusum
from gps.cusum import DRConfig
from gps.lodo import lodo_report


def car(n=200, seed=0, v=10.0, scale_err=0.03, drift=0.0, k0=100, sd_head=2.0, theta=0.0):
    """Straight eastbound drive: reported = truth + Gauss-Markov receiver error (+ drift after k0), odometry with scale error."""
    rng = np.random.default_rng(seed)
    t = np.arange(n, dtype=float)
    w = np.zeros((n, 2))
    for k in range(1, n):
        w[k] = 0.9 * w[k - 1] + np.sqrt(1 - 0.81) * 1.0 * rng.normal(size=2)
    off = np.outer(np.clip(t - k0, 0, None) * drift, [np.cos(theta), np.sin(theta)])
    x, y = t * v + w[:, 0] + off[:, 0] + rng.normal(0, 0.3, n), w[:, 1] + off[:, 1] + rng.normal(0, 0.3, n)
    return pd.DataFrame({"t": t, "x": x, "y": y, "x_true": t * v, "y_true": np.zeros(n),
                         "odo_speed": v * (1 + scale_err) + rng.normal(0, 0.05, n), "heading": 90.0 + rng.normal(0, sd_head, n), "run": "r"})


def cfg(**kw):
    return DRConfig(gm_phi=0.9, gm_sigma=1.0, **kw)


def test_cusum_scalar_and_bank_maths():
    s = cusum.cusum_scalar([1, 1, 1, -5, 1], 0.5)
    assert np.allclose(s, [0.5, 1.0, 1.5, 0.0, 0.5])
    # bank: a constant +1 sigma shift along north reaches (1 - kappa) * n in the north direction
    nu = np.tile([0.0, 1.0], (20, 1)); S = np.tile([1.0, 0.0, 1.0], (20, 1))
    b = cusum.cusum_bank(cusum.bank_projection(nu, S), 0.5)
    assert abs(b[-1] - 10.0) < 1e-9
    # NIS excess is zero-mean for chi2(m)
    rng = np.random.default_rng(0)
    x = cusum.nis_excess(rng.chisquare(4, 20000), np.full(20000, 4))
    assert abs(x.mean()) < 0.03 and abs(x.std() - 1) < 0.05


def test_clean_innovations_are_standardised_and_scale_converges():
    errs, z = [], []
    for sd in range(6):
        d = car(seed=sd, n=300)
        o = cusum.dr_branch(d, cfg())
        z.append(o["nis2"].to_numpy()[5:])
        errs.append(abs(o["scale"].iloc[-1] - cusum.true_scale(d)) / cusum.true_scale(d))
    assert 1.2 < np.concatenate(z).mean() < 3.2          # chi2(2) mean 2, tolerant
    assert np.median(errs) < 0.006                        # 3% prior error -> well below 1% after 300 s at 10 m/s


def test_freezing_prevents_dragging_the_scale():
    d = car(n=300, drift=1.0, k0=50, theta=0.0)           # 1 m/s pull along the travel direction = 10% scale pull if followed
    free = cusum.dr_branch(d, cfg())
    froz = cusum.dr_branch(d, cfg(freeze_h=4.0))
    s_true = cusum.true_scale(d.assign(x_true=d["x_true"]))
    e_free = abs(free["scale"].iloc[-1] - s_true)
    e_froz = abs(froz["scale"].iloc[-1] - s_true)
    assert froz["frozen"].iloc[100:].mean() > 0.9
    assert e_froz < 0.5 * e_free


def test_drift_detected_clean_not():
    for th in (0.0, np.pi / 4, np.pi / 2):
        att = car(n=200, drift=0.4, k0=60, theta=th)
        a = cusum.score_from_dr(cusum.dr_branch(att, cfg(freeze_h=6.0)), "axis", 0.5, att["run"])
        assert a[60:90].max() > 3 * a[:60].max() + 1
    clean = [cusum.score_from_dr(cusum.dr_branch(car(seed=s), cfg()), "axis", 0.5, np.zeros(200)).max() for s in range(5)]
    assert max(clean) < 14.0


def test_layer_contract_and_calibration():
    tr = pd.concat([car(seed=s).assign(run=f"r{s}", label=0) for s in range(4)], ignore_index=True)
    lay = cusum.CusumLayer("dr", "axis", 0.5, ekf_cfg=None, dr_cfg=cfg(freeze_h=6.0)).calibrate(tr, budget=0.05)
    att = car(seed=9, drift=0.5, k0=60).assign(label=0)
    ev = lay.score(att)
    assert len(ev) == len(att) and ev[0].layer == "L2b" and ev[0].domain == "gps"
    assert any(e.alarm for e in ev[70:]) and sum(e.alarm for e in ev[:60]) <= 3
    assert all(0.0 <= e.score <= 1.0 for e in ev)


def test_lodo_report():
    rng = np.random.default_rng(1)
    s = np.r_[rng.normal(0, 1, 3000), rng.normal(0, 1, 3000) + 1.0]     # second drive harder
    g = np.r_[np.zeros(3000, int), np.ones(3000, int)]
    r = lodo_report(s, g, 0.01)
    assert r["in_sample_fa"] <= 0.0101
    assert r["per_drive"]["1"]["fa"] > 0.05                              # threshold from the easy drive does not transfer
    assert r["per_drive"]["0"]["fa"] < 0.01
