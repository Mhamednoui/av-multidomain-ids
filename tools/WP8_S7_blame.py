"""WP8 S7 blame rows M4-12 / M4-13 on H31: the vehicle block alone (GPS + cross, as the S6 evaluation) for the candidates V3 (v3 blame + v3 tick_blame), A1 (v3.1 selected), A2, A3 (labelled variant)
on the 13 H31 KITTI drives (K: B1 gps_can; B3 single-domain types, equal weight per type; strata same-day / other-day) and the 21 comma Chunk_2 routes (C: GNSS drift / meaconing / doppler; CAN types).
Frozen inputs: the cross recipe fitted on the V31 TRAIN drives / routes (results/WP8/S7/frozen_cross31.pkl). Code = tools/WP8_S6_eval.eval_k / eval_c / summary / cis (the S6 evaluation; nothing re-tuned).
Output: results/WP8/S7/blame.json, scores results/WP8/scores/S7/blame_{kitti,comma}_h31.npz. Run: python -u -W ignore tools/WP8_S7_blame.py [--material h31|val]"""
import json
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S7_lib as S7

import numpy as np

import WP8_S6_eval as E6

E6.SCORES = S7.SCORES


def main():
    S7.open_guard()
    S7.journal("S7", "blame rows (M4-12/13): start", "tools/WP8_S7_blame.py")
    fits = pickle.load(open(S7.OUT / "frozen_cross31.pkl", "rb"))
    recs, strata = {}, {}
    for f in sorted(S7.CACHE.glob("kitti_*.pkl")):
        z = pickle.load(open(f, "rb"))
        recs[z["drive"]] = z["records"]
        strata[z["drive"]] = z["stratum"]
    routes = {}
    for f in sorted(S7.CACHE.glob("comma_*.pkl")):
        z = pickle.load(open(f, "rb"))
        routes[z["route"]] = z
    rk, sk = E6.eval_k(fits["K"], recs)
    rc, sc = E6.eval_c(fits["C"], routes)
    E6.save_scores(sk, "blame_kitti_h31.npz")
    E6.save_scores(sc, "blame_comma_h31.npz")
    out = {"exposure": S7.EXPOSURE["fresh"], "runs": {"K": len(rk), "C": len(rc)}, "candidates_K": E6.CANDS_K, "candidates_C": E6.CANDS_C, "K": {}, "C": {}, "K_by_stratum": {}}
    for c in E6.CANDS_K:
        out["K"][c] = {**E6.summary(rk, c, "K"), "ci": E6.cis(rk, "K", c)}
    for s in sorted(set(strata.values())):
        rows = [r for r in rk if strata[r["drive"]] == s]
        out["K_by_stratum"][s] = {c: {**E6.summary(rows, c, "K"), "drives": len({r["drive"] for r in rows})} for c in E6.CANDS_K}
    for c in E6.CANDS_C:
        out["C"][c] = {**E6.summary(rc, c, "C"), "ci": E6.cis(rc, "C", c)}
    out["rules"] = {c: E6.judge(out["K"][c], out["C"][c if c in E6.CANDS_C else "A2"], out["K"]["V3"], out["C"]["V3"]) for c in E6.CANDS_K}
    S7.write_json(out, S7.OUT / "blame.json")
    S7.journal("S7", "blame rows: done", "results/WP8/S7/blame.json")
    for c in ("V3", "A1", "A3"):
        print(c, "K gps_can", out["K"][c]["gps_can"], "B3", out["K"][c]["B3"], flush=True)
    for c in E6.CANDS_C:
        print(c, "C B2", out["C"][c]["B2"], flush=True)


if __name__ == "__main__":
    main()
