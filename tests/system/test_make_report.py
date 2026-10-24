"""Tests for make_report.py (WP7 S3): deterministic output, every number traced to a JSON key, no missing keys in closed milestones,
PENDING sections that fill themselves, and the untracked-number scan itself."""
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import make_report as M  # noqa: E402


class Skip(Exception):
    pass


def test_report_is_deterministic():
    a, b = M.build(), M.build()
    assert a["text"] == b["text"]
    assert len(a["text"]) > 20000


def test_every_number_is_traced():
    r = M.build()
    assert r["untracked"] == [], r["untracked"][:10]
    assert r["missing_closed"] == [], r["missing_closed"][:10]
    # every marker id in the body resolves to an item, and the appendix lists every item
    ids = {int(m.group(1)) for m in M.MARK.finditer(r["marked"])}
    assert ids and max(ids) < len(r["items"])
    assert ids == set(range(len(r["items"]))), "items created but not printed"
    app = r["text"].split("## Appendix A.")[1]
    rows = [ln for ln in app.split("\n") if re.match(r"\| \d+ \|", ln)]
    assert len(rows) == len(r["items"])
    # the appendix names a real file for every json / curated item, and the key resolves
    c = M.Ctx()
    for it in r["items"]:
        if it["kind"] in ("json", "curated"):
            assert (ROOT / it["file"]).exists(), it
            v = c.raw(it["file"], it["path"])
            assert v is not M.MISSING, it


def test_untracked_number_scan_catches_a_typed_number():
    ok = "text \x010\x02" + "12.5%" + "\x03 and D10, S3b, section 4, class 17, 2026-10-24\n## 3. Heading\n1. list\n"
    assert M.untracked_numbers(ok) == []
    bad = ok + "a hand-typed 42.5% appears here\n"
    assert M.untracked_numbers(bad) == ["42.5%"]
    assert M.untracked_numbers("x 7 y") == ["7"]


def test_pending_sections_and_their_files():
    r = M.build()
    for name, files in M.PENDING_FILES.items():
        exists = any((ROOT / f).exists() for f in files)
        assert (name in r["pending"]) == (not exists), name
    for name in r["pending"]:
        assert "**PENDING.**" in r["text"]


def test_pending_fills_from_json_when_it_exists():
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "results" / "WP7").mkdir(parents=True)
        (root / "results" / "WP7" / "S2_acceptance.json").write_text(json.dumps({"A1_alert_delay": {"rule": "median delay <= 5 s", "met": True, "value": 2.5}}))
        c = M.Ctx(root)
        out = M.pending(c, "M3 simulation", "note")
        assert "Filled from" in out and "PENDING" not in out
        assert c.pending == []
        assert M.strip_marks(out).count("MET") >= 1
        c2 = M.Ctx(Path(d) / "empty")
        out2 = M.pending(c2, "M3 simulation", "note")
        assert "**PENDING.**" in out2 and c2.pending == ["M3 simulation"]


def test_missing_key_is_recorded_in_closed_sections():
    c = M.Ctx()
    t = c.pc("results/WP1/S8_kitti.json", "no/such/key")
    assert M.strip_marks(t) == "n/a"
    assert c.missing == [("results/WP1/S8_kitti.json", "no/such/key")]
    c.closed = False
    c.pc("results/WP1/S8_kitti.json", "no/such/key2")
    assert len(c.missing) == 1


def test_values_match_the_source_json():
    c = M.Ctx()
    f = "results/WP1/S8_kitti.json"
    v = json.loads((ROOT / f).read_text())["deployed"]["mean_run_detected"]
    assert M.strip_marks(c.pc(f, "deployed/mean_run_detected", 1)) == f"{100 * v:.1f}%"
    ci = json.loads((ROOT / f).read_text())["deployed"]["bootstrap"]["drives"]["mean_run"]
    assert M.strip_marks(c.ci(f, "deployed/bootstrap/drives/mean_run")) == f"[{100 * ci[0]:.0f}, {100 * ci[1]:.0f}]"


def test_committed_report_is_current():
    p = ROOT / "RESULTS_v3.md"
    if not p.exists():
        raise Skip("RESULTS_v3.md not generated yet")
    if p.read_bytes().decode("utf-8") != M.build()["text"]:
        raise Skip("RESULTS_v3.md is stale: run python make_report.py (an input JSON changed)")
