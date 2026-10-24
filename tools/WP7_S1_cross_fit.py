"""WP7 S1: fit the cross-domain RUNTIME-TEST object (system/cross_runner.py CrossObject) on the WP6 S2b DEV cache (KITTI train + validation drives; test drives are not in that cache).
Recipe = the S2b choice (results/WP6/s2b_choice_r2.json: KITTI "inst", domain-level blame): SigmaModel(bias="linear") per edge on the clean phase-0 rows of all dev drives
(S2b fitted them leave-one-drive-out; here they are fitted on all dev drives, in-sample: this object exercises the runtime, it is not the WP6 S3 verdict model), per-edge ECDF and
tie-safe 1% tau on the clean dev statistics. Output: results/WP7/frozen_cross/cross.json, results/WP7/S1_cross_fit.json.
Run from codes_v3/: python -I -u -W ignore tools/WP7_S1_cross_fit.py
"""
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np

from common.config import DATA_EXTRA
from crossdomain import consistency as CS
from crossdomain import witness as W
from system.cross_runner import DOMAIN_OF, CrossObject, edge_list

OUT = ROOT / "results" / "WP7"
CACHE = DATA_EXTRA / "cache_v3" / "WP6" / "s2b_kitti.pkl"


def main():
    rows = pickle.load(open(CACHE, "rb"))["rows"]
    assert set(rows["part"]) <= {"train", "val"}
    edges = edge_list()
    clean = rows[rows["attack"] == "none"]
    c0 = clean[clean["phase"] == 0]
    models = {}
    for e in edges:
        r, v = c0[f"r_{e.name}"].to_numpy(float), c0[f"v_{e.name}"].to_numpy(float)
        ok = np.isfinite(r) & np.isfinite(v)
        models[e.name] = W.SigmaModel(bias="linear").fit(r[ok], v[ok])
    runs = []
    for run, g in clean.groupby("run", sort=False):
        g = g.sort_values("t")
        Z = np.column_stack([models[e.name].z(g[f"r_{e.name}"].to_numpy(float), g[f"v_{e.name}"].to_numpy(float)) for e in edges])
        runs.append(Z)
    model = CS.WhichDomainLies(edges, DOMAIN_OF, k="inst", budget=0.01, tb=None, domain_level=True).fit(runs)
    obj = CrossObject(models, model)
    obj.save(OUT / "frozen_cross")
    res = {"n_clean_runs": len(runs), "n_rows": int(sum(len(z) for z in runs)), "tau": model.calibration.tau, "edges": [e.name for e in edges],
           "sigma_models": {n: m.to_dict() for n, m in models.items()}, "parts": sorted(set(rows["part"])), "in_sample_note": "sigma models and calibration fitted on all dev drives"}
    (OUT / "S1_cross_fit.json").write_text(json.dumps(res, indent=1))
    print({k: res[k] for k in ("n_clean_runs", "n_rows", "tau")})


if __name__ == "__main__":
    main()
