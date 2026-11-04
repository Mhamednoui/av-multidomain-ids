"""WP8 S7 freeze (milestone M4, step 1): everything that scores H31 is fixed here, BEFORE any H31 file is opened.
Stages (python -u -W ignore tools/WP8_S7_freeze.py <stage>):
  fit    (a) the frozen cross-domain recipe: tools/WP8_S6_eval.fit_k / fit_c on the V31 TRAIN drives / routes only (G1: no H31) -> results/WP8/S7/frozen_cross31.pkl;
         (b) the labelled budget variant of the v3.1 system: the S2 freeze procedure (tools/WP8_S2_freeze.py) with the key MX|L100|b1.5|m2w5|g15|d0|k1 -> results/WP8/S7/frozen_system31_b15/.
  hash   results/WP8/S7/freeze.json: sha256 of every frozen artefact (v3 and v3.1 domains, systems, locks, rules) and of every .py file of the repository, the git commit it was written on, the
         versions of python / numpy / numba, the files that differ from the tag v3.0, the scoring configuration (seeds, bootstrap, operating points). Nothing is read from H31 except the lock JSON.
After this file is committed no code and no parameter changes; a bug found later is fixed with a labelled re-run and both results are reported (notes/WP8_v31.md, G2)."""
import json
import pickle
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

ARTEFACTS = [
    # v3.1 frozen objects
    "results/WP8/S2/frozen_system31/system31.pkl", "results/WP8/S2/frozen_system31/system31.json", "results/WP8/S7/frozen_system31_b15/system31.pkl",
    "results/WP8/S3/frozen_lidar31", "results/WP8/S3/frozen_lidar31_B125", "results/WP8/S4/parts/stream31_F1.pkl", "results/WP8/S4/parts/stream31_RC5.pkl", "results/WP8/S7/frozen_cross31.pkl",
    # v3 frozen objects
    "results/WP1/frozen_gps", "results/WP2/s7_domain", "results/WP3/S9/frozen_lidar", "results/WP4/s7_domain", "results/WP7/frozen_v2x", "results/WP6/system_v2.pkl", "results/WP6/m2_system.pkl",
    "results/WP7/frozen_cross", "results/WP6/s1_sigma_models.json", "results/WP3/S2/ring_table.json", "results/WP3/S2/calibration_beta.npz",
    # locks, rules, requirements
    "locks/H31.json", "locks/V31_val.json", "notes/WP8_v31.md", "requirements.txt", "workpackages/WP8_v31.md"]
CODE_DIRS = ["common", "gps", "can", "lidar", "network", "v2x", "crossdomain", "fusion", "system", "tools", "tests", "run_all.py", "make_report.py"]
V3_PACKAGES = ["common", "gps", "can", "lidar", "network", "v2x", "crossdomain", "fusion", "system"]


def files_of(rel):
    p = S7.ROOT / rel
    if p.is_dir():
        return sorted(x for x in p.rglob("*") if x.is_file() and "__pycache__" not in x.parts and x.suffix not in (".pyc", ".nbi", ".nbc"))
    return [p] if p.exists() else []


def stage_fit():
    import WP8_S6_eval as E6
    S7.journal("S7", "freeze: fit cross recipe (V31 train only) + b1.5 system", "tools/WP8_S7_freeze.py fit")
    tk, _ = E6.load_k()
    tc, _ = E6.load_c()
    fits = {"K": E6.fit_k(tk), "C": E6.fit_c(tc)}
    out = S7.OUT / "frozen_cross31.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    pickle.dump(fits, open(out.with_suffix(".tmp"), "wb"), protocol=4)
    out.with_suffix(".tmp").replace(out)
    print("cross fit", {f: float(v["cal"].tau) for f, v in fits.items()}, flush=True)
    # budget variant
    import WP8_S2_freeze as F2
    import WP8_S2_sim as M
    tmp = S7.CACHE / "b15_eval"
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "b15_eval.json").write_text(json.dumps({"chosen": "MX|L100|b1.5|m2w5|g15|d0|k1"}))
    M.OUT = tmp
    F2.OUT = S7.OUT / "frozen_system31_b15"
    sys.argv = ["x", "--tag", "b15"]
    F2.main()


def git(*a):
    return subprocess.run(["git", *a], cwd=S7.ROOT, capture_output=True, text=True).stdout.strip()


def stage_hash():
    import numpy
    try:
        import numba
        nb = numba.__version__
    except Exception:
        nb = None
    art, code = {}, {}
    for rel in ARTEFACTS:
        fs = files_of(rel)
        if not fs:
            art[rel] = "MISSING"
            continue
        art[rel] = {str(f.relative_to(S7.ROOT)).replace("\\", "/"): S7.sha256(f) for f in fs}
    for rel in CODE_DIRS:
        for f in files_of(rel):
            if f.suffix == ".py":
                code[str(f.relative_to(S7.ROOT)).replace("\\", "/")] = S7.sha256(f)
    changed = git("diff", "--name-status", "v3.0", "HEAD", "--", *V3_PACKAGES).splitlines()
    out = {"step": "WP8.S7 freeze (M4 step 1)", "written": S7.time.strftime("%Y-%m-%dT%H:%M:%S%z"), "git_commit_parent": git("rev-parse", "HEAD"), "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
           "tag_v3.0": git("rev-parse", "v3.0^{}"), "uncommitted_tracked_changes_at_freeze": git("status", "--porcelain", "--untracked-files=no").splitlines(),
           "environment": {"python": platform.python_version(), "numpy": numpy.__version__, "numba": nb, "platform": platform.platform()},
           "scoring_configuration": {
               "frozen_systems": {"v3": "fusion.system.load_system(2) = results/WP6/system_v2.pkl", "v3.1": "results/WP8/S2/frozen_system31/system31.pkl (MX|L100|b2|m2w5|g15|d0|k1)",
                                  "variants": ["v31_RC5 network RC5", "v31_blameA3", "v31_b15 (frozen_system31_b15)", "v31_mcSS motion-critical SAFE_STOP corroboration"]},
               "composites": "tools/WP8_S2_sim.py construction, seeds [31, 2, ord(family)] attack, [31, 100 + i] clean timeline, V2X 30 episodes per class, 40 egos per VeReMi block",
               "bootstrap": {"B": 2000, "seed": 31, "unit": "group (drive / route / recording / capture / 10-min block / clean timeline)"},
               "operating_points": "domain 1 % and system 2 % tie-safe thresholds fitted on V31_val clean data (frozen), none refitted on H31",
               "lidar": "lidar.fast.set_numba(True); v3 = frozen v3 layer objects + stack on the fast statistics (voxel 0.1), literal v3 LidarDomain on a seeded sample (tools/WP8_S7_lidar_check.py)",
               "network": "F1 = Stream31Final (primary), RC5 = labelled variant, v3 = NetworkDomain batch; D10 test split; D23 not scored (cache not on disk)",
               "can": "IncrementalCan == CanDomain.score_capture (S5); v3 and v3.1 CAN Evidence are the same numbers",
               "v2x": "VeReMi test ego views (frozen_v2x); V2AIX H31 (tools/WP8_S7_v2aix.py)", "civic_chunk4": "not scored (no Civic CAN decoder)"},
           "v3_files_changed_since_tag_v3.0 (git diff --name-status v3.0 HEAD, v3 packages)": changed, "artefacts_sha256": art, "code_sha256": code}
    S7.write_json(out, S7.OUT / "freeze.json")
    print("freeze.json written:", sum(len(v) if isinstance(v, dict) else 1 for v in art.values()), "artefact files,", len(code), "code files", flush=True)
    S7.journal("S7", "freeze.json written", f"{len(code)} code files, parent commit {out['git_commit_parent'][:8]}")


if __name__ == "__main__":
    {"fit": stage_fit, "hash": stage_hash}[sys.argv[1]]()
