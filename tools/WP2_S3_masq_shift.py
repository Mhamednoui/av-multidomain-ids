"""WP2 S3: how much do ROAD masquerade streams differ in clock rate from the legitimate ECU stream?

For each masquerade capture and its injected ID: mean gap and gap std before the attack (legit ECU) and during the attack
(attacker only, legit frames removed), the relative rate difference in ppm, and the reference spread of the segment-mean gap
of the same ID over 10 s segments of clean ambient traffic (all ROAD ambient captures): the clock-rate change must exceed this
spread to be seen by any skew method. Gaps use dt_clipped. Descriptive only; no choice depends on it.
Output: results/WP2/s3_road_masq_shift.json
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from can import adapters as A
from can import l1_exp as E
from can.frames import dt_clipped
from WP2_S2_run import dump
from common.config import RESULTS

caps = A.road_captures()
amb = {}
for n in caps[caps.kind == "ambient"].name:
    raw = E.load_cached("road", n)
    amb[n] = (raw["t"], raw["id"])


def seg_means(t, ids, iid, seg=10.0):
    tt = t[ids == iid]
    g = np.minimum(dt_clipped(tt)[1:], 3 * np.median(np.diff(tt)))
    s = np.floor(tt[1:] / seg).astype(int)
    return np.array([g[s == k].mean() for k in np.unique(s) if (s == k).sum() > 0.5 * seg / np.median(g)])


out = {}
for _, r in caps[caps.kind == "masquerade"].iterrows():
    raw = E.load_cached("road", r["name"])
    iid = int(r["meta"]["injection_id"], 16)
    a, b = r["meta"]["injection_interval"]
    t, ids = raw["t"], raw["id"]
    tt = t[ids == iid]
    pre = tt[(tt > 1.0) & (tt < a - 1.0)]
    att = tt[(tt >= a) & (tt <= b)]
    cap = 3 * np.median(np.diff(tt))
    gp, ga = np.minimum(dt_clipped(pre)[1:], cap), np.minimum(dt_clipped(att)[1:], cap)
    ref = np.concatenate([seg_means(t2, i2, iid) for t2, i2 in amb.values() if (i2 == iid).sum() > 500] or [np.zeros(0)])
    mp, ma = float(gp.mean()), float(ga.mean())
    out[r["name"]] = {"part": r["part"], "id": hex(iid), "n_pre_gaps": int(len(gp)), "n_attack_gaps": int(len(ga)),
                      "mean_gap_pre_s": mp, "mean_gap_attack_s": ma, "std_gap_pre_s": float(gp.std()), "std_gap_attack_s": float(ga.std()),
                      "rate_change_ppm": float((ma - mp) / mp * 1e6),
                      "clean_10s_segment_mean_spread_ppm": float(ref.std() / ref.mean() * 1e6) if len(ref) > 3 else None,
                      "clean_segments": int(len(ref)),
                      "per_gap_jitter_std_ppm_of_period": float(gp.std() / mp * 1e6)}
    print(r["name"], {k: (round(v, 1) if isinstance(v, float) else v) for k, v in out[r["name"]].items() if "ppm" in k})
dump(out, RESULTS / "WP2" / "s3_road_masq_shift.json")
