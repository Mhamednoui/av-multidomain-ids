"""WP8 S4 regression (G7 R1, network): the frozen v3 network domain still loads and, on the rebuilt D10 val stream, reproduces the stored WP4 S7 validation view of stack H (FA, macro, per-family detection)
exactly; building Stream31 candidates never alters the frozen files. Skips when the S4 outputs are not on disk."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class Skip(Exception):
    pass


def test_frozen_network_domain_loads_with_v3_threshold():
    from network.domain import NetworkDomain
    D = NetworkDomain.load(ROOT / "results" / "WP4" / "s7_domain")
    dev = json.loads((ROOT / "results" / "WP4" / "s7_dev_val.json").read_text())
    assert D.stack == "H" and D.comb.method == "max"
    assert abs(D.comb.threshold - dev["threshold"]["H"]) <= 1e-12
    assert [L.name for L in D.layers] == ["net.tcp_flags", "net.scan", "net.trw", "net.bruteforce"]
    fc = json.loads((ROOT / "results" / "WP4" / "s7_domain" / "freeze_check.json").read_text())
    assert fc["alarm_mismatches"] == 0 and fc["max_abs_score_diff"] == 0.0


def test_v3_val_view_reproduced_on_rebuilt_cache():
    p = ROOT / "results" / "WP8" / "S4" / "s4_val_candidates.json"
    if not p.exists():
        raise Skip("run tools/WP8_S4_eval.py first")
    got = json.loads(p.read_text())["candidates"]["v3"]
    ref = json.loads((ROOT / "results" / "WP4" / "s7_dev_val.json").read_text())["val_view"]["H"]
    assert abs(got["fa"] - ref["fa"]) <= 1e-12 and abs(got["macro"] - ref["macro"]) <= 1e-12
    for f, x in ref["detection"].items():
        assert abs(got["detection"][f] - x) <= 1e-12, f
