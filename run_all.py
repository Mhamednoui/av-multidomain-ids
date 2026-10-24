"""AV-IDS v3: run every step of the project in dependency order (WP7 S3).

Purpose: one entry point for the whole pipeline: WP0 regression -> WP1..WP5 (domain tools) -> WP6 (cross-domain + fusion) -> WP7 (runtime checks, report).
Inputs: the tools of tools/ (each step names its script and arguments), the data folders of DATASETS.md (never downloaded: missing data is printed and
the step is skipped), the saved results of results/.
Outputs: logs in results/WP7/logs/run_all/<step>.log, a summary in results/WP7/logs/run_all_last.json. Nothing outside codes_v3/ is ever written;
../codes and ../codes_v2 are never touched.

Step kinds
  default (run without flags): regression, tables (markdown tables regenerated from saved JSON), tests, runtime (stream-vs-batch checks on VALIDATION data), report.
  --refit only:                prep, dev (validation-only fits and choices), build (freeze a domain), eval (the ONE labelled test run of a step). These re-fit or
                               re-score test sets: every eval step adds a labelled test exposure (see RESULTS_v3.md section 10). Never use them to get a better number.
  pending:                     steps of an open milestone (M1-LiDAR); printed, never executed.

Usage (from codes_v3/, with the tf environment):
  python run_all.py --list
  python run_all.py --dry-run [--refit] [--only WP4,WP6] [--from wp4.dev]
  python run_all.py [--only WP1]            run the default steps
  python run_all.py --refit --only WP4      also re-fit / re-run the WP4 tools (hours; adds test exposures)
  python run_all.py --check                 read-only: frozen objects load and reproduce their saved freeze values (no fit, no data needed)
  --keep-going   continue after a failing step (dependents of the failed step are skipped)
Python: C:\\Users\\nouir\\miniconda3\\envs\\tf\\python.exe (3.9) only; other interpreters are refused for execution (AVIDS_ANY_PYTHON=1 overrides).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOGDIR = ROOT / "results" / "WP7" / "logs" / "run_all"
DEFAULT_KINDS = ("regression", "tables", "tests", "runtime", "report")
REFIT_KINDS = ("prep", "dev", "build", "eval")
PENDING = "pending"

# data id -> (path relative to codes_v3/, description). Locations from DATASETS.md. Only checked, never created.
DATA = {
    "D04": ("../data_extra/kitti_raw", "KITTI raw 2011_09_26 drives (velodyne + oxts)"),
    "D03": ("../codes/data/AV-GPS-Dataset", "AV-GPS-Dataset"),
    "D05": ("../data_extra/road/road", "ROAD (ORNL) CAN captures"),
    "D06": ("../data_extra/gps_uav", "UAV Attack Dataset (live part)"),
    "D02": ("../codes/data", "Car-Hacking (HCRL) csv files"),
    "D10": ("../data_extra/D10_cicids2017_generated_flows", "CICIDS2017 labelled flows (unofficial mirror)"),
    "D11": ("../data_extra/D11_can-train-and-test", "can-train-and-test (DTU)"),
    "D12": ("../data_extra/D12_veremi_extension", "VeReMi Extension"),
    "D13": ("../data_extra/D13_v2aix", "V2AIX real CAMs (non-commercial, no redistribution)"),
    "D14": ("../data_extra/D14_tampa_bsm", "Tampa CV Pilot BSM sample"),
    "D15": ("../data_extra/D15_osm", "OpenStreetMap Karlsruhe highways"),
    "D22": ("../data_extra/D22_comma2k19", "comma2k19 chunk 1 (CAN + GNSS + IMU)"),
    "D23": ("../data_extra/D23_cse-cic-ids2018", "CSE-CIC-IDS2018 processed csv"),
    "CACHE6": ("../data_extra/cache_v3/WP6", "WP6 S3/S4 tick packs (built by tools/WP6_S3_streams.py and WP6_S4_streams.py, see reports/WP6_S3.md, WP6_S4.md)"),
}

PYFLAGS = ["-u", "-W", "ignore"]
ISOL = ["-I", "-u", "-W", "ignore"]
V2X_CACHE = "../data_extra/cache_v3/WP5/run_all_s6"


def S(id, wp, kind, desc, cmds, deps=(), data=(), outputs=()):
    """cmds: list of argument lists (each run as `python <args>` from codes_v3/)."""
    return {"id": id, "wp": wp, "kind": kind, "desc": desc, "cmds": cmds, "deps": list(deps), "data": list(data), "outputs": list(outputs)}


def T(*args):
    return PYFLAGS + ["tools/" + args[0]] + list(args[1:])


def TI(*args):
    return ISOL + ["tools/" + args[0]] + list(args[1:])


def tests(flt=""):
    return PYFLAGS + ["tests/run_tests.py"] + ([flt] if flt else [])


STEPS = [
    # ---------------------------------------------------------------- WP0
    S("wp0.tests", "WP0", "tests", "unit tests of common/ (Evidence, Layer, combiner, harness, regression)", [tests("common")]),
    S("wp0.regression", "WP0", "regression", "reproduce the v2 GPS dead-reckoning number (B2) through the v3 Layer + harness",
      [T("WP0_regression.py")], ["wp0.tests"], ["D04"], ["results/WP0/regression_b2.json"]),
    # ---------------------------------------------------------------- WP1 GPS
    S("wp1.dev", "WP1", "dev", "S8 development pass: nested LODO, CUSUM selection, combiner choice (train + val drives only)",
      [T("WP1_S8_dev.py")], ["wp0.regression"], ["D04"], ["results/WP1/S8_dev.json"]),
    S("wp1.test", "WP1", "eval", "S8 single KITTI test pass of the default GPS stack (test exposure)", [T("WP1_S8_test.py")], ["wp1.dev"], ["D04"], ["results/WP1/S8_kitti.json"]),
    S("wp1.control", "WP1", "eval", "S8 shuffled-label control of the supervised GPS row", [T("WP1_S8_control.py")], ["wp1.dev"], ["D04"], ["results/WP1/S8_control.json"]),
    S("wp1.external", "WP1", "eval", "S8 external tests: UAV live spoofing flight (D06), AV-GPS (D03)", [T("WP1_S8_external.py")], ["wp1.dev"], ["D06", "D03"], ["results/WP1/S8_external.json"]),
    S("wp1.freeze", "WP1", "build", "freeze the deployable GPSDomain (results/WP1/frozen_gps) and check it reproduces the S8 test statistic",
      [T("WP1_S8_freeze.py")], ["wp1.test"], ["D04"], ["results/WP1/frozen_gps/domain.json", "results/WP1/S8_freeze.json"]),
    S("wp1.tables", "WP1", "tables", "S8 tables and acceptance verdicts from the saved JSON", [T("WP1_S8_tables.py")], [], [], ["results/WP1/S8_tables.md", "results/WP1/S8_acceptance.json"]),
    S("wp1.tests", "WP1", "tests", "unit tests of gps/", [tests("tests" + os.sep + "gps")], ["wp0.tests"]),
    # ---------------------------------------------------------------- WP2 CAN
    S("wp2.select", "WP2", "dev", "S7 selection on LOCO folds + validation attack captures (no test capture read)", [T("WP2_S7_select.py")], ["wp0.regression"], ["D05"], ["results/WP2/s7_select.json"]),
    S("wp2.fit", "WP2", "prep", "S7 fit stages prep, fold, weights, loo (resumable cache ../data_extra/WP2_S7_cache)",
      [T("WP2_S7_fit.py", s) for s in ("prep", "fold", "weights", "loo")], ["wp2.select"], ["D05"]),
    S("wp2.freeze", "WP2", "build", "freeze the CAN domain (results/WP2/s7_domain) and the development ablation", [T("WP2_S7_final.py", "freeze")], ["wp2.fit"], ["D05"], ["results/WP2/s7_frozen.json"]),
    S("wp2.tables_cache", "WP2", "eval", "S7 table cache for the ROAD test and accelerator captures (reads test captures)", [T("WP2_S7_tables.py", "test"), T("WP2_S7_tables.py", "accel")], ["wp2.freeze"], ["D05"]),
    S("wp2.test", "WP2", "eval", "S7 single ROAD test run (exposure counted in results/WP2/s7_test.json) and accelerator whole-capture check",
      [T("WP2_S7_final.py", "test"), T("WP2_S7_final.py", "accel")], ["wp2.tables_cache"], ["D05"], ["results/WP2/s7_test.json", "results/WP2/s7_accel.json"]),
    S("wp2.others", "WP2", "eval", "S7 Car-Hacking and can-train-and-test L1 numbers", [T("WP2_S7_others.py")], ["wp2.freeze"], ["D02", "D11"], ["results/WP2/s7_others.json"]),
    S("wp2.tables", "WP2", "tables", "S7 summary tables from the saved JSON", [T("WP2_S7_summary.py")], [], [], ["results/WP2/s7_summary.md"]),
    S("wp2.tests", "WP2", "tests", "unit tests of can/", [tests("tests" + os.sep + "can")], ["wp0.tests"]),
    # ---------------------------------------------------------------- WP3 LiDAR (open milestone)
    S("wp3.tables_s4", "WP3", "tables", "S4 tables (L2a density / intensity) from results/WP3/S4/final.json: INTERIM state of M1-LiDAR", [T("WP3_S4_tables.py")], [], [], ["results/WP3/S4/S4_tables.md"]),
    S("wp3.tests", "WP3", "tests", "unit tests of lidar/ (the files of the running S5 / S6 workers are included)", [tests("tests" + os.sep + "lidar")], ["wp0.tests"]),
    S("wp3.pending", "WP3", PENDING, "PENDING: M1-LiDAR (S5 occlusion, S6 background / tracking, S7, S9 combined run) is open; its build / eval tools are listed in workpackages/WP3_lidar.md", []),
    # ---------------------------------------------------------------- WP4 network
    S("wp4.prep", "WP4", "prep", "S7 score tables of the D10 validation / test stage streams", [T("WP4_S7_prep.py"), T("WP4_S7_prep_d23.py")], ["wp0.regression"], ["D10", "D23"], ["results/WP4/s7_prep.json"]),
    S("wp4.dev", "WP4", "dev", "S7 development on validation only: combiner selection per stack, warm-up length", [T("WP4_S7_dev.py")], ["wp4.prep"], ["D10"], ["results/WP4/s7_dev_val.json"]),
    S("wp4.test", "WP4", "eval", "S7 the ONE D10 test run (verdict mode) with leave-one-attack-out", [T("WP4_S7_test.py", "verdict")], ["wp4.dev"], ["D10"], ["results/WP4/s7_d10.json"]),
    S("wp4.d23", "WP4", "eval", "S7 cross-dataset run on D23 (zero-shot and on-network)", [T("WP4_S7_d23.py")], ["wp4.test"], ["D23"], ["results/WP4/s7_d23.json"]),
    S("wp4.freeze", "WP4", "build", "freeze the network domain (stack H) and check flow-by-flow reproduction of the S7 alarms", [T("WP4_S7_freeze.py")], ["wp4.test"], ["D10"], ["results/WP4/s7_domain/freeze_check.json"]),
    S("wp4.tables", "WP4", "tables", "S7 tables from the saved JSON", [T("WP4_S7_tables.py")], [], [], ["results/WP4/s7_tables_d10.md"]),
    S("wp4.tests", "WP4", "tests", "unit tests of network/", [tests("tests" + os.sep + "network")], ["wp0.tests"]),
    # ---------------------------------------------------------------- WP5 V2X
    S("wp5.dev", "WP5", "dev", "S6 choice of the scored-row L4 on VeReMi validation", [TI("WP5_S6_dev.py", "--cache", V2X_CACHE)], ["wp0.regression"], ["D12"], ["results/WP5/s6_dev.json"]),
    S("wp5.test", "WP5", "eval", "S6 final run: VeReMi test (second exposure) + Tampa illustration", [TI("WP5_S6_run.py", "--cache", V2X_CACHE)], ["wp5.dev"], ["D12", "D14"], ["results/WP5/s6_veremi.json", "results/WP5/s6_tampa.json"]),
    S("wp5.s3b_cache", "WP5", "prep", "S3b parsed V2AIX cache (derived data stays outside the repo)", [TI("WP5_S3b_cache.py")], ["wp5.test"], ["D13"]),
    S("wp5.s3b_geometry", "WP5", "eval", "S3b receiver geometry (range gate)", [TI("WP5_S3b_geometry.py")], ["wp5.s3b_cache"], ["D13"], ["results/WP5/s3b_geometry.json"]),
    S("wp5.s3b_clean", "WP5", "eval", "S3b frozen V2X physics stack on genuine real CAMs (VeReMi vs re-calibrated)", [TI("WP5_S3b_clean.py")], ["wp5.s3b_geometry"], ["D13"], ["results/WP5/s3b_clean.json"]),
    S("wp5.s3b_inject", "WP5", "eval", "S3b VeReMi-taxonomy attacks injected on real CAMs, Mobile and Stationary",
      [TI("WP5_S3b_inject.py", "--env", "Mobile"), TI("WP5_S3b_inject.py", "--env", "Stationary")], ["wp5.s3b_clean"], ["D13"], ["results/WP5/s3b_inject_Mobile.json", "results/WP5/s3b_inject_Stationary.json"]),
    S("wp5.s3b_senders", "WP5", "eval", "S3b top flagged senders (diagnostic)", [TI("WP5_S3b_senders.py")], ["wp5.s3b_clean"], ["D13"], ["results/WP5/s3b_top_senders.json"]),
    S("wp5.tables", "WP5", "tables", "S3b tables and acceptance verdicts from the saved JSON", [TI("WP5_S3b_tables.py")], [], [], ["results/WP5/s3b_acceptance.json"]),
    S("wp5.tests", "WP5", "tests", "unit tests of v2x/", [tests("tests" + os.sep + "v2x")], ["wp0.tests"]),
    # ---------------------------------------------------------------- WP6 cross-domain + fusion
    S("wp6.streams", "WP6", "prep", "S5 tick packs of the M2 system (needs the S3 / S4 packs in cache_v3/WP6)", [T("WP6_S5_streams.py")], ["wp1.tests"], ["CACHE6"]),
    S("wp6.dev", "WP6", "dev", "S5 validation-only choice of calibration + correlator; freezes results/WP6/m2_system.pkl", [T("WP6_S5_dev.py")], ["wp6.streams"], ["CACHE6"], ["results/WP6/m2_system.json"]),
    S("wp6.test", "WP6", "eval", "S5 the ONE labelled test run of the frozen M2 system (4th exposure of the composites)", [T("WP6_S5_test.py")], ["wp6.dev"], ["CACHE6"], ["results/WP6/s5_test.json", "results/WP6/s5_acceptance.json"]),
    S("wp6.tables", "WP6", "tables", "S5 tables from the saved JSON", [T("WP6_S5_tables.py")], [], [], ["results/WP6/s5_tables.md"]),
    S("wp6.tests", "WP6", "tests", "unit tests of crossdomain/ and fusion/", [tests("tests" + os.sep + "crossdomain"), tests("tests" + os.sep + "fusion")], ["wp0.tests"]),
    # ---------------------------------------------------------------- WP7 system
    S("wp7.fit_v2x", "WP7", "build", "rebuild the V2X physics-only runtime domain (32 MB, not in git) from VeReMi validation", [TI("WP7_S1_v2x_fit.py")], ["wp5.tests"], ["D12"], ["results/WP7/frozen_v2x/domain.json"]),
    S("wp7.fit_cross", "WP7", "build", "rebuild the cross-domain runtime object", [TI("WP7_S1_cross_fit.py")], ["wp6.tests"], ["D04", "D22"], ["results/WP7/frozen_cross"]),
    S("wp7.fit_lidar", "WP7", "build", "rebuild the LiDAR interim runtime object", [TI("WP7_S1_lidar_fit.py")], ["wp3.tests"], ["D04"], ["results/WP7/frozen_lidar_interim"]),
    S("wp7.runtime", "WP7", "runtime", "S1 streaming runtime: stream == batch exactness, causality, reset, latency (validation data only), one tool at a time",
      [TI("WP7_S1_" + n + ".py") for n in ("gps", "can", "cross", "v2x", "lidar", "bus")] + [TI("WP7_S1b_net.py"), TI("WP7_S1b_ties.py")],
      ["wp1.tests", "wp2.tests", "wp4.tests", "wp5.tests", "wp6.tests"], ["D04", "D05", "D10", "D12"], ["results/WP7/S1_gps.json", "results/WP7/S1b_net.json"]),
    S("wp7.report", "WP7", "report", "generate RESULTS_v3.md from the results JSON (make_report.py) with the number-trace appendix",
      [PYFLAGS + ["make_report.py"]], ["wp1.tables", "wp2.tables", "wp4.tables", "wp5.tables", "wp6.tables"], [], ["RESULTS_v3.md"]),
    S("wp7.all_tests", "WP7", "tests", "the full test suite", [tests()], ["wp7.report", "wp3.tests"]),
]
BY_ID = {s["id"]: s for s in STEPS}


# ---------------------------------------------------------------- planning
def check_declared():
    """Structural checks used by the tests: unique ids, known deps, deps declared earlier (so declared order is a topological order), scripts exist."""
    errs = []
    seen = set()
    wp_rank = {f"WP{i}": i for i in range(8)}
    last_rank = -1
    for s in STEPS:
        if s["id"] in seen:
            errs.append("duplicate id " + s["id"])
        for d in s["deps"]:
            if d not in seen:
                errs.append(f"{s['id']}: dependency {d} not declared earlier")
        r = wp_rank[s["wp"]]
        if r < last_rank:
            errs.append(f"{s['id']}: WP order broken")
        last_rank = max(last_rank, r)
        seen.add(s["id"])
        if s["kind"] not in DEFAULT_KINDS + REFIT_KINDS + (PENDING,):
            errs.append(f"{s['id']}: unknown kind {s['kind']}")
        for c in s["cmds"]:
            scripts = [a for a in c if a.endswith(".py")]
            if not scripts or not (ROOT / scripts[0]).exists():
                errs.append(f"{s['id']}: script missing {scripts[:1]}")
            if any(".." in a and a != V2X_CACHE for a in c):
                errs.append(f"{s['id']}: parent-path argument {c}")
        for d in s["data"]:
            if d not in DATA:
                errs.append(f"{s['id']}: unknown data id {d}")
    return errs


def select(only=None, from_step=None, refit=False):
    kinds = DEFAULT_KINDS + (REFIT_KINDS if refit else ()) + (PENDING,)
    chosen = [s for s in STEPS if s["kind"] in kinds]
    if only:
        wps = {w.strip().upper() for w in only.split(",") if w.strip()}
        chosen = [s for s in chosen if s["wp"] in wps]
    if from_step:
        if from_step not in BY_ID:
            raise SystemExit(f"unknown step {from_step}; see --list")
        ids = [s["id"] for s in STEPS]
        start = ids.index(from_step)
        chosen = [s for s in chosen if ids.index(s["id"]) >= start]
    return chosen


def missing_data(step):
    return [(d, DATA[d][0], DATA[d][1]) for d in step["data"] if not (ROOT / DATA[d][0]).exists()]


def cmd_text(c):
    return "python " + " ".join(c)


def do_list():
    print(f"{'step':18} {'WP':4} {'kind':10} {'run by default':14} deps / data")
    for s in STEPS:
        dflt = "yes" if s["kind"] in DEFAULT_KINDS else ("--refit" if s["kind"] in REFIT_KINDS else "never")
        extra = ("deps: " + ",".join(s["deps"]) if s["deps"] else "") + ("  data: " + ",".join(s["data"]) if s["data"] else "")
        print(f"{s['id']:18} {s['wp']:4} {s['kind']:10} {dflt:14} {extra}")
        print(f"{'':18} {s['desc']}")
    print("\nData folders (DATASETS.md; never downloaded by this script):")
    for k, (p, d) in DATA.items():
        print(f"  {k:7} {p}  [{'present' if (ROOT / p).exists() else 'MISSING'}]  {d}")


def do_plan(chosen, refit):
    n_eval = [s["id"] for s in chosen if s["kind"] == "eval"]
    if n_eval:
        print("NOTE: --refit includes eval steps that score test sets again; each adds a labelled test exposure:", ", ".join(n_eval))
    for i, s in enumerate(chosen, 1):
        print(f"[{i:2}/{len(chosen)}] {s['id']}  ({s['wp']}, {s['kind']})  {s['desc']}")
        if s["kind"] == PENDING:
            print("      PENDING: not executed")
            continue
        for c in s["cmds"]:
            print("      " + cmd_text(c))
        for d, p, desc in missing_data(s):
            print(f"      data MISSING: {d} {p} ({desc}); see DATASETS.md; the step would be SKIPPED")


def python_ok():
    return sys.version_info[:2] == (3, 9) or os.environ.get("AVIDS_ANY_PYTHON") == "1"


def do_run(chosen, keep_going):
    if not python_ok():
        raise SystemExit("refusing to run: use C:\\Users\\nouir\\miniconda3\\envs\\tf\\python.exe (Python 3.9); see RULES.md section 4")
    LOGDIR.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    status = {}
    for i, s in enumerate(chosen, 1):
        sid = s["id"]
        bad_dep = [d for d in s["deps"] if status.get(d, ("", ""))[0] in ("FAILED", "BLOCKED")]
        miss = missing_data(s)
        if s["kind"] == PENDING:
            status[sid] = ("PENDING", "open milestone")
        elif bad_dep:
            status[sid] = ("BLOCKED", "dependency failed: " + ",".join(bad_dep))
        elif miss:
            status[sid] = ("SKIPPED", "data missing: " + ", ".join(f"{d} ({p})" for d, p, _ in miss))
        else:
            t0 = time.time()
            ok = True
            with open(LOGDIR / f"{sid}.log", "w", encoding="utf-8") as log:
                for c in s["cmds"]:
                    log.write("$ " + cmd_text(c) + "\n")
                    log.flush()
                    r = subprocess.run([sys.executable] + c, cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
                    if r.returncode != 0:
                        ok = False
                        log.write(f"\nexit code {r.returncode}\n")
                        break
            status[sid] = ("OK" if ok else "FAILED", f"{time.time() - t0:.0f} s, log results/WP7/logs/run_all/{sid}.log")
        print(f"[{i:2}/{len(chosen)}] {sid:18} {status[sid][0]:8} {status[sid][1]}", flush=True)
        if status[sid][0] == "FAILED" and not keep_going:
            break
    (ROOT / "results" / "WP7" / "logs").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "WP7" / "logs" / "run_all_last.json").write_text(json.dumps({k: list(v) for k, v in status.items()}, indent=1))
    return 1 if any(v[0] == "FAILED" for v in status.values()) else 0


# ---------------------------------------------------------------- --check (read-only)
def _j(rel):
    return json.loads((ROOT / rel).read_text())


def _close(a, b, tol=1e-12):
    return abs(float(a) - float(b)) <= tol


def run_checks():
    """Read-only verification of the frozen outputs against the values saved when they were frozen. No fit, no data, no download.
    Returns a list of (name, ok, detail)."""
    out = []

    def rec(name, fn):
        try:
            ok, detail = fn()
        except Exception as e:  # a failing check is a result, not a crash
            ok, detail = False, f"{type(e).__name__}: {e}"
        out.append((name, bool(ok), detail))

    sys.path.insert(0, str(ROOT))
    sys.dont_write_bytecode = True

    def gps():
        f = _j("results/WP1/S8_freeze.json")
        from gps.domain import GPSDomain
        GPSDomain.load(str(ROOT / "results" / "WP1" / "frozen_gps"))
        ok = f["max_abs_diff_statistic"] == 0 and f["alarm_disagreements"] == 0 and f["evidence_path_alarm_disagreements"] == 0
        return ok, f"loaded; saved freeze check: score diff {f['max_abs_diff_statistic']}, alarm mismatches {f['alarm_disagreements']} on {f['n_test_rows']} rows"
    rec("gps.frozen_domain", gps)

    def can():
        fz = _j("results/WP2/s7_frozen.json")
        dj = _j("results/WP2/s7_domain/domain.json")
        from can.domain import CanDomain
        CanDomain.load(str(ROOT / "results" / "WP2" / "s7_domain"))
        ok = dj["layers"] == fz["layers"] and _close(dj["combined"]["threshold"], fz["combiner"]["threshold"]) and dj["layer_thresholds"] == fz["layer_thresholds"]
        return ok, f"loaded; layers {dj['layers']}; combiner threshold {dj['combined']['threshold']:.6f} equals the frozen verdict value"
    rec("can.frozen_domain", can)

    def net():
        fc = _j("results/WP4/s7_domain/freeze_check.json")
        dj = _j("results/WP4/s7_domain/domain.json")
        d10 = _j("results/WP4/s7_d10.json")
        from network.domain import NetworkDomain
        NetworkDomain.load(str(ROOT / "results" / "WP4" / "s7_domain"))
        ok = fc["max_abs_score_diff"] == 0 and fc["alarm_mismatches"] == 0 and list(dj["layers"]) == d10["stacks"]["H"]["layers"] and dj["method"] == d10["stacks"]["H"]["method"]
        return ok, f"loaded; saved freeze check: score diff {fc['max_abs_score_diff']}, alarm mismatches {fc['alarm_mismatches']} on {fc['n_rows']} flows"
    rec("network.frozen_domain", net)

    def v2x():
        a = _j("results/WP5/s6_acceptance.json")
        s1 = _j("results/WP7/S1_v2x_fit.json")
        same = all(_close(s1["thresholds_wp7"][k], s1["thresholds_wp5_s6"][k]) for k in s1["thresholds_wp5_s6"])
        return same and a["overall"] in ("PARTIAL", "MET", "NOT MET"), f"M1-V2X verdict {a['overall']}; runtime V2X physics domain thresholds equal the WP5 S6 thresholds: {same}"
    rec("v2x.runtime_vs_s6", v2x)

    def m2():
        cfg = _j("results/WP6/m2_system.json")
        from fusion.system import load_m2
        m = load_m2()
        ok = sorted(m) == ["C", "K"]
        for k in ("K", "C"):
            ok = ok and list(m[k].entries) == cfg["systems"][k]["entries"] and _close(m[k].fusion.threshold, cfg["systems"][k]["threshold"])
        return ok, f"loaded; systems {sorted(m)}; entries equal results/WP6/m2_system.json"
    rec("fusion.m2_system", m2)

    def s1():
        a = _j("results/WP7/S1_acceptance.json")["overall"]
        return all(a.values()), "WP7 S1 acceptance (stream == batch, causality, reset, latency, bus, labels): " + ", ".join(f"{k}={'MET' if v else 'NOT MET'}" for k, v in a.items())
    rec("system.runtime_acceptance", s1)

    def rep():
        import make_report
        r = make_report.build()
        return not r["missing_closed"], f"make_report builds; missing keys in closed milestones: {len(r['missing_closed'])}; pending sections: {', '.join(r['pending']) or 'none'}"
    rec("report.inputs", rep)
    return out


def do_check():
    res = run_checks()
    for name, ok, detail in res:
        print(f"{'OK  ' if ok else 'FAIL'} {name:26} {detail}")
    print("\nall frozen outputs consistent" if all(o for _, o, _ in res) else "\nSOME CHECKS FAILED")
    return 0 if all(o for _, o, _ in res) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Run the AV-IDS v3 pipeline in dependency order.")
    ap.add_argument("--list", action="store_true", help="list all steps and exit")
    ap.add_argument("--dry-run", action="store_true", help="print the commands in order, run nothing")
    ap.add_argument("--only", help="comma-separated WPs, e.g. WP1,WP6")
    ap.add_argument("--from", dest="from_step", help="start at this step id (see --list)")
    ap.add_argument("--refit", action="store_true", help="also run prep / dev / build / eval steps (re-fit, re-score tests)")
    ap.add_argument("--check", action="store_true", help="read-only verification of the frozen outputs")
    ap.add_argument("--keep-going", action="store_true")
    a = ap.parse_args(argv)
    if a.list:
        do_list()
        return 0
    if a.check:
        return do_check()
    errs = check_declared()
    if errs:
        print("run_all.py step table is inconsistent:\n  " + "\n  ".join(errs))
        return 2
    chosen = select(a.only, a.from_step, a.refit)
    if a.dry_run:
        do_plan(chosen, a.refit)
        return 0
    return do_run(chosen, a.keep_going)


if __name__ == "__main__":
    sys.exit(main())
