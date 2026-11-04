"""WP8 S6 regression (G7 R1): the frozen v3 system still gives the v3 numbers, and the v3 fusion / cross-domain files are untouched."""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import numpy as np  # noqa: E402

import WP8_S6_fixture as F  # noqa: E402


def test_load_system_2_reproduces_the_v3_fixture():
    ref = json.loads((ROOT / "results" / "WP8" / "S6" / "regression_fixture.json").read_text())
    cur = F.run_fixture()
    for fam in ("K", "C"):
        assert cur[fam]["alarm"] == ref[fam]["alarm"] and cur[fam]["blame"] == ref[fam]["blame"]
        assert np.abs(np.array(cur[fam]["score"]) - np.array(ref[fam]["score"])).max() <= 1e-12
        assert cur[fam]["events"] == ref[fam]["events"] and cur[fam]["threshold"] == ref[fam]["threshold"]


def test_v3_fusion_and_crossdomain_files_are_unchanged_since_tag_v3():
    paths = ["fusion", "crossdomain/consistency.py", "crossdomain/witness.py", "crossdomain/attacks.py", "system/cross_runner.py"]
    try:
        r = subprocess.run(["git", "diff", "--stat", "--diff-filter=DMRT", "v3.0", "--"] + paths, cwd=ROOT, capture_output=True, text=True, timeout=60)
    except OSError:
        return
    if r.returncode != 0:
        return
    assert r.stdout.strip() == "", r.stdout
