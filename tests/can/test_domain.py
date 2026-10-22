"""Integration test of the frozen CanDomain (skipped when the frozen domain or the ROAD caches are not on this machine)."""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DOMAIN = ROOT / "results" / "WP2" / "s7_domain"


def _ready():
    sys.path.insert(0, str(ROOT / "tools"))
    if not (DOMAIN / "domain.pkl").exists():
        return None
    try:
        from WP2_S7_lib import load_unit
        return load_unit("correlated_signal_attack_2_masquerade")
    except Exception:
        return None


def test_frozen_domain_evidence_causal_and_motion():
    U = _ready()
    if U is None:
        return
    from can.domain import CanDomain
    dom = CanDomain.load(DOMAIN)
    assert dom.layers == ["L1", "L3c", "L3d"] and dom.combiner.method in ("noisy_or", "max", "logistic")
    comb, per = dom.score_capture(U.t, U.id, U.dlc, U.B, name="c")
    assert len(comb) > 20 and all(len(v) == len(comb) for v in per.values())
    assert all(e.domain == "can" and e.layer == "combined" and e.name == "can.combined" and 0.0 <= e.score <= 1.0 for e in comb)
    al = [e for e in comb if e.alarm]
    assert al and all(e.reason.startswith("CAN domain alarm") for e in al)
    # the rewritten wheel-speed message makes the predictors alarm after the onset (4.3 s .. end), not before
    first_inj = float(U.t[np.flatnonzero(U.label)[0]])
    assert min(e.t for e in al) >= first_inj - 1.0
    # causality: scoring only the first 20 s gives the same scores for the windows that are complete
    k = int(np.searchsorted(U.t, 20.0))
    comb2, _ = dom.score_capture(U.t[:k], U.id[:k], U.dlc[:k], U.B[:k], name="c")
    a, b = {e.sample_id: e.score for e in comb}, {e.sample_id: e.score for e in comb2}
    common = [s for s in b if s in a and int(s.split("/")[1]) < 19]
    assert len(common) >= 10 and max(abs(a[s] - b[s]) for s in common) < 1e-9
    est = dom.motion_estimates(U.t, U.id, U.dlc, U.B)
    assert len(est) > 10 and all(e.source == "can" and np.isfinite(e.speed) and e.speed >= 0 for e in est)


def test_save_load_round_trip(tmp_path=None):
    U = _ready()
    if U is None:
        return
    import tempfile
    from can.domain import CanDomain
    dom = CanDomain.load(DOMAIN)
    with tempfile.TemporaryDirectory() as d:
        dom.save(d)
        dom2 = CanDomain.load(d)
        k = int(np.searchsorted(U.t, 15.0))
        c1, _ = dom.score_capture(U.t[:k], U.id[:k], U.dlc[:k], U.B[:k], explain=False)
        c2, _ = dom2.score_capture(U.t[:k], U.id[:k], U.dlc[:k], U.B[:k], explain=False)
        assert [e.score for e in c1] == [e.score for e in c2] and [e.alarm for e in c1] == [e.alarm for e in c2]
