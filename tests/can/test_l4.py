"""WP2 S6: tests of the L4 features (against the v2 loop definition), window k-th largest and the Layer."""
import sys
from collections import deque
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from can import l1 as L
from can import l4_features as G


def toy(n=800, seed=0):
    rng = np.random.default_rng(seed)
    ids = rng.choice([0x10, 0x20, 0x30, 0x40, 0x7FF, 0x123], size=n, p=[.3, .25, .2, .15, .05, .05])
    t = np.cumsum(rng.uniform(0.0005, 0.002, n))
    t[100] = t[99] - 0.003                       # an inversion
    dlc = rng.integers(2, 9, n)
    B = rng.integers(0, 4, (n, 8)).astype(np.int16)
    B[np.arange(8)[None, :] >= dlc[:, None]] = -1
    return t, ids, dlc, B


def v2_loop(t, ids, B):
    """The v2 StreamFeaturizer logic (can/features.py), with dt clipped as in v3."""
    last_t, last_t_id, last_pay, window, counts = None, {}, {}, deque(), {}
    out = []
    mx = -1e9
    for k in range(len(t)):
        i = int(ids[k])
        pay = list(B[k])
        dtp = np.nan if last_t is None else max(t[k] - last_t, 0.0)
        dti = max(t[k] - last_t_id[i], 0.0) if i in last_t_id else np.nan
        nid = counts.get(i, 0)
        nu = len(counts)
        bc = sum(a != b for a, b in zip(pay, last_pay[i])) if i in last_pay else -1
        out.append((dtp, dti, nid, nu, bc))
        last_t, last_t_id[i], last_pay[i] = t[k], t[k], pay
        window.append(i)
        counts[i] = counts.get(i, 0) + 1
        if len(window) > G.WIN:
            old = window.popleft()
            counts[old] -= 1
            if counts[old] == 0:
                del counts[old]
    return out


def test_features_equal_v2_loop():
    t, ids, dlc, B = toy()
    raw = G.stream_raw(t, ids, dlc, B)
    ref = v2_loop(t, ids, B)
    for k, (dtp, dti, nid, nu, bc) in enumerate(ref):
        a, b = raw["dt_prev"][k], raw["dt_id"][k]
        assert (np.isnan(dtp) and np.isnan(a)) or abs(a - dtp) < 1e-6
        assert (np.isnan(dti) and np.isnan(b)) or abs(b - dti) < 1e-6
        assert raw["n_id"][k] == nid and raw["n_uniq"][k] == nu and raw["bchg"][k] == bc, k


def test_dt_never_negative_and_matrix():
    t, ids, dlc, B = toy()
    raw = G.stream_raw(t, ids, dlc, B)
    assert np.nanmin(raw["dt_prev"]) >= 0 and np.nanmin(raw["dt_id"]) >= 0
    pb = G.PeriodBuilder().add(ids, raw["dt_id"])
    per = pb.finish()
    X = G.feature_matrix(raw, ids, dlc, B, per)
    assert X.shape == (len(t), len(G.FEATURES))
    kn = X[:, G.FEATURES.index("id_known")]
    assert kn.min() == 1.0
    Xt = G.feature_matrix(raw, ids, dlc, B, per, G.TIMING)
    assert Xt.shape[1] == 9 and "id" not in G.TIMING and "b0" not in G.TIMING
    assert not any("t" == c or c == "timestamp" for c in G.FEATURES)


def test_window_kth_matches_bruteforce():
    t, ids, dlc, B = toy(3000, 1)
    F = L.make_features(t, ids, dlc, windows=True)
    rng = np.random.default_rng(2)
    p = rng.normal(0, 5, len(t)).astype(np.float32)
    W = G.window_kth(F, p, ids)
    keys = F["wkey"]
    for wi, wk in enumerate(F["wkeys"]):
        m = keys == wk
        s = np.sort(p[m])[::-1]
        for vi, (rule, k) in enumerate(G.VARIANTS):
            if rule == "all":
                exp = s[k - 1] if len(s) >= k else G.FLOOR
            else:
                exp = G.FLOOR
                for i in np.unique(ids[m]):
                    si = np.sort(p[m & (ids == i)])[::-1]
                    if len(si) >= k:
                        exp = max(exp, si[k - 1])
            assert abs(W[wi, vi] - exp) < 1e-6, (wi, rule, k)


def test_layer_window_and_threshold_tie_safe():
    t, ids, dlc, B = toy(3000, 3)
    F = L.make_features(t, ids, dlc, windows=True)
    F["p"] = np.random.default_rng(4).random(len(t))
    lay = G.L4Layer(unit="window", variant=("all", 3))
    raw = lay.raw_scores(F)
    assert raw.shape == (len(F["ws"]),)
    lay.calibrate_from_raw(raw, 0.01)
    assert (lay.alarms(raw)).mean() <= 0.01 + 1e-9
    assert lay.layer_id == "L4" and lay.kind == "supervised"
