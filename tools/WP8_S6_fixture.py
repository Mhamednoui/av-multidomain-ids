"""WP8 S6: regression fixture of the frozen v3 system (fusion.system.load_system(2)).

Builds a deterministic synthetic composite (seeded parts for the K and C systems), runs SystemV2.run and stores the scores, alarms and
events in results/WP8/S6/regression_fixture.json. Generated from the untouched v3 code before any S6 change; tests/v31/test_s6_regression.py
reloads the system and must reproduce it (max |diff| <= 1e-12).
Run from codes_v3/: python -I -u -W ignore tools/WP8_S6_fixture.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np

from fusion.system import load_system

WIDTH = {"gps": 16, "lidar": 4, "can": 3, "v2x": 12, "network": 6, "cross": 7}


def synthetic_parts(domains, n=90, seed=7):
    rng = np.random.default_rng(seed)
    parts = {}
    for d in domains:
        w = WIDTH[d]
        score = rng.beta(1.2, 6.0, n).astype(np.float32)
        score[40:55] = np.clip(score[40:55] + 0.6, 0, 1)
        lay = rng.beta(1.2, 6.0, (n, w)).astype(np.float32)
        parts[d] = {"score": score, "count": rng.integers(1, 8, n).astype(np.float32), "layers": lay, "dom_alarm": score > 0.7,
                    "layer_alarm": lay > 0.8, "blame": np.full(n, None, object), "present": np.ones(n, bool)}
    cb = np.full(n, None, object)
    cb[42:52] = "gps"
    parts["cross"]["blame"] = cb
    parts["cross"]["dom_alarm"] = parts["cross"]["score"] > 0.6
    return parts


def run_fixture():
    sysm = load_system(2)
    out = {}
    for fam in ("K", "C"):
        s = sysm[fam]
        parts = synthetic_parts(s.domains)
        r = s.run(parts, explain=False)
        out[fam] = {"threshold": float(s.fusion.threshold), "domains": list(s.domains), "score": [float(x) for x in r["score"]],
                    "alarm": [bool(x) for x in r["alarm"]], "blame": [str(x) for x in r["blame"]],
                    "events": [{"start": e.start, "first_alarm": e.first_alarm, "end": e.end, "n_alarm_ticks": e.n_alarm_ticks, "blamed": e.blamed,
                                "response": e.response, "domains": list(e.domains), "blame_counts": e.blame_counts} for e in r["events"]]}
    return out


if __name__ == "__main__":
    out = run_fixture()
    p = ROOT / "results" / "WP8" / "S6" / "regression_fixture.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=0))
    print({f: (len(v["events"]), int(sum(v["alarm"]))) for f, v in out.items()})
