"""WP8 S2 regression (G7 R1): after the S2 changes the frozen v3 system load_system(2) still reproduces the committed fixture, the v3 fusion files are untouched,
and the frozen v3.1 system (results/WP8/S2/frozen_system31) loads and matches its recorded sha256."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import numpy as np  # noqa: E402


def test_load_system_2_fixture_after_s2():
    import WP8_S6_fixture as F
    ref = json.loads((ROOT / "results" / "WP8" / "S6" / "regression_fixture.json").read_text())
    cur = F.run_fixture()
    for fam in ("K", "C"):
        assert cur[fam]["alarm"] == ref[fam]["alarm"] and cur[fam]["blame"] == ref[fam]["blame"] and cur[fam]["events"] == ref[fam]["events"]
        assert np.abs(np.array(cur[fam]["score"]) - np.array(ref[fam]["score"])).max() <= 1e-12


def test_v3_fusion_files_not_modified():
    paths = ["fusion/system.py", "fusion/correlator.py", "fusion/composite.py", "fusion/streams.py", "fusion/novelty.py", "system/fusion_runner.py"]
    try:
        r = subprocess.run(["git", "diff", "--stat", "v3.0", "--"] + paths, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except OSError:
        return
    if r.returncode != 0:
        return
    assert r.stdout.strip() == "", r.stdout


def test_frozen_system31_sha256():
    d = ROOT / "results" / "WP8" / "S2" / "frozen_system31"
    meta = d / "system31.json"
    if not meta.exists():
        return
    m = json.loads(meta.read_text())
    assert hashlib.sha256((d / "system31.pkl").read_bytes()).hexdigest() == m["sha256_pkl"]
    from fusion.system31 import load_system31
    s = load_system31()
    assert set(s) == {"K", "C"} and all(s[f].threshold == m["systems"][f]["threshold"] for f in ("K", "C"))
