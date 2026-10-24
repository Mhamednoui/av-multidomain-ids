"""Tests for run_all.py (WP7 S3): step table consistency, --list, --dry-run (nothing executed), dependency order, --only / --from, refit gating, --check."""
import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
import run_all as R  # noqa: E402


def run_main(args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = R.main(args)
    return code, buf.getvalue()


def test_step_table_consistent():
    assert R.check_declared() == []
    ids = [s["id"] for s in R.STEPS]
    assert len(ids) == len(set(ids))
    # WP0 first, WP6 after WP1..WP5, WP7 last
    wps = [s["wp"] for s in R.STEPS]
    assert wps[0] == "WP0" and wps[-1] == "WP7"
    assert wps.index("WP6") > max(i for i, w in enumerate(wps) if w in ("WP1", "WP2", "WP3", "WP4", "WP5"))
    assert wps.index("WP7") > max(i for i, w in enumerate(wps) if w == "WP6")


def test_list_prints_every_step_and_exits_zero():
    code, out = run_main(["--list"])
    assert code == 0
    for s in R.STEPS:
        assert s["id"] in out
    assert "DATASETS.md" in out and "MISSING" in out or "present" in out


def test_list_works_as_a_script_without_heavy_imports():
    r = subprocess.run([sys.executable, str(ROOT / "run_all.py"), "--list"], capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr
    assert "wp0.regression" in r.stdout


def test_dry_run_executes_nothing():
    real = R.subprocess.run

    def boom(*a, **k):
        raise AssertionError("dry-run must not execute anything")
    R.subprocess.run = boom
    try:
        for args in (["--dry-run"], ["--dry-run", "--refit"], ["--dry-run", "--only", "WP4,WP6"], ["--dry-run", "--from", "wp5.dev", "--refit"]):
            code, out = run_main(args)
            assert code == 0
            assert "python " in out
    finally:
        R.subprocess.run = real


def test_dry_run_order_respects_dependencies():
    for refit in (False, True):
        chosen = R.select(refit=refit)
        pos = {s["id"]: i for i, s in enumerate(chosen)}
        for s in chosen:
            for d in s["deps"]:
                if d in pos:
                    assert pos[d] < pos[s["id"]], (d, s["id"])
        wps = [s["wp"] for s in chosen]
        assert wps == sorted(wps), "WP order"


def test_default_run_has_no_refit_and_no_test_scoring():
    default = R.select()
    kinds = {s["kind"] for s in default}
    assert not (kinds & set(R.REFIT_KINDS)), kinds
    assert all(s["kind"] in R.DEFAULT_KINDS + (R.PENDING,) for s in default)
    full = R.select(refit=True)
    assert {s["id"] for s in default} < {s["id"] for s in full}
    assert any(s["kind"] == "eval" for s in full)
    code, out = run_main(["--dry-run", "--refit"])
    assert "test exposure" in out
    code, out = run_main(["--dry-run"])
    assert "test exposure" not in out


def test_only_and_from():
    only = R.select(only="WP4")
    assert only and all(s["wp"] == "WP4" for s in only)
    two = R.select(only="wp1, WP2")
    assert {s["wp"] for s in two} == {"WP1", "WP2"}
    ids = [s["id"] for s in R.STEPS]
    fr = R.select(from_step="wp6.tables")
    assert fr[0]["id"] == "wp6.tables" or fr[0]["id"] in ids[ids.index("wp6.tables"):]
    assert all(ids.index(s["id"]) >= ids.index("wp6.tables") for s in fr)
    try:
        R.select(from_step="nope")
        raise AssertionError("unknown step accepted")
    except SystemExit:
        pass


def test_pending_steps_never_run_and_nothing_touches_v1_or_v2():
    for s in R.STEPS:
        if s["kind"] == R.PENDING:
            assert s["cmds"] == []
        for c in s["cmds"]:
            joined = " ".join(c)
            assert "../codes " not in joined + " " and "codes_v2" not in joined and "/codes/" not in joined


def test_missing_data_is_reported_not_downloaded():
    s = R.S("x.t", "WP1", "tests", "d", [], data=["D10"])
    real = R.DATA["D10"]
    R.DATA["D10"] = ("../data_extra/__does_not_exist__", "x")
    try:
        miss = R.missing_data(s)
        assert miss and miss[0][0] == "D10"
    finally:
        R.DATA["D10"] = real


def test_check_frozen_outputs():
    res = R.run_checks()
    names = [n for n, _, _ in res]
    for n in ("gps.frozen_domain", "can.frozen_domain", "network.frozen_domain", "fusion.m2_system", "system.runtime_acceptance", "report.inputs"):
        assert n in names
    bad = [(n, d) for n, ok, d in res if not ok]
    assert not bad, bad
