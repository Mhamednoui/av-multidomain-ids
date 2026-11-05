"""Tests of the WP9 B5 final-comparison tools: formatting, verdict rule, and the consistency check on the committed master table."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import WP9_B5_lib as L


def test_fmt():
    assert L.fmt("f3", 0.12345) == "0.123"
    assert L.fmt("pct1", 0.0123) == "1.2%"
    assert L.fmt("ci3", [0.1, 0.25]) == "[0.100, 0.250]"
    assert L.fmt("sgn_pts1", -0.0204) == "-2.0"
    assert L.fmt("cipct2", [0.0, 0.0104]) == "[0.00%, 1.04%]"


def test_verdict_words():
    assert set(L.ALLOWED_VERDICTS) == {"better", "equal", "comparable-not-like-for-like", "not comparable", "below"}


def test_master_has_no_better_without_flags():
    import json
    m = json.load(open(ROOT / "results/WP9/B5_master.json", encoding="utf-8"))
    for r in m["rows"]:
        assert r["verdict"] in L.ALLOWED_VERDICTS
        if r["verdict"] == "better":
            assert all(r["flags"].values())


def test_consistency_check_passes():
    import WP9_B5_check as C
    assert C.main() == 0
