"""WP1 S3 DIAGNOSTIC (not an operating point, not used for any choice): the val-calibrated EKF threshold did not transfer
(clean test FA 2.6% vs 1% target), so detections of S3_ekf.py are not at the same FA as B2's. This script sets the threshold of
B2, EKF ungated and EKF gated on the TEST clean runs themselves (tie-safe 1% of clean-run rows), an ORACLE that no deployed system
could use, only to compare ranking quality at equal false alarms. Output: results/WP1/S3_isofa.json.
Run from codes_v3/: python -u -W ignore tools/WP1_S3_isofa.py
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import WP1_S1_b2 as S1
import WP1_S2_l1 as S2
import WP1_S3_ekf as E
from common.config import SEED
from common.metrics import budget_threshold
from gps import ekf
from gps import stream as S

ATT = S.ATTACKS_V2 + S.ATTACKS_NEW


def main():
    kx = S.build_kitti(np.random.default_rng(SEED), new_attacks=S.ATTACKS_NEW)
    kx = kx.join(S1.b2_features(kx))
    te = kx[kx["part"] == "test"]
    te = te.loc[np.concatenate([g.index.to_numpy() for _, g in te.groupby("run", sort=False)])]
    scores = {"gps.dr_resid_10": S1.B2Layer().raw_scores(te)}
    for nm, g in (("gps.ekf_nis", False), ("gps.ekf_nis_gated", True)):
        r = ekf.run_filter_all(te, E.kitti_cfg(g))
        scores[nm] = ekf.nis_score(r["nis"].to_numpy(), r["dim"].to_numpy())
    clean = (te["attack"] == "none").to_numpy()
    res = {}
    for nm, raw in scores.items():
        thr = budget_threshold(raw[clean], 0.01)
        flag = raw >= thr
        d = S2.summarize_flags(te, flag, ATT)
        d["slow_drift_lt_0.5_within_30s"] = E.within_30s_slow_drift(te, flag)
        res[nm] = d
        print(nm, {a: round(x, 2) for a, x in d["run_detected"].items()}, d["slow_drift_lt_0.5_within_30s"], flush=True)
    (E.OUT / "S3_isofa.json").write_text(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
