"""WP8 S3 candidate evaluation on V31_val (rules pre-registered in notes/WP8_v31.md, section S3): builds the frame of all scans from the
records (tools/WP8_S3_build.py), evaluates the v3 rule M0 and the 26 pre-listed candidates by leave-one-drive-out over the 10 V31_val
drives, applies the selection rule, writes results/WP8/S3/candidates.json and selection.json. No H31 data is read (assert_not_h31 in the build).
Run: python -u -W ignore tools/WP8_S3_eval.py [--episodes-top 4]"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP8_S3_an as A
import WP8_S3_lib as L

OUT = L.ROOT / "results" / "WP8" / "S3"
FRAME = OUT / "frame.pkl"


def boot_ci(alarms_by_drive, n=2000, seed=31):
    """Cluster bootstrap over drives of the pooled detection rate. alarms_by_drive: list of (k, n) per drive."""
    k = np.array([a for a, b in alarms_by_drive], float)
    m = np.array([b for a, b in alarms_by_drive], float)
    rng = np.random.default_rng(seed)
    v = np.empty(n)
    for i in range(n):
        s = rng.integers(0, len(k), len(k))
        v[i] = k[s].sum() / max(m[s].sum(), 1.0)
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]


def feasible(r, m0):
    if not (0.005 <= r["fa"] <= 0.015):
        return False
    return all(r["det"][k] >= m0["det"][k] - 0.02 for k in L.ATTACKS)


A_ORDER = {"all4": 0, "tail2h": 1, "frac4": 2, "tail2": 3}
C_ORDER = {"miss_w20": 0, "u(w20,z20)": 1, "miss_z20": 2, "zmulti": 3, "zmultig": 4, "miss_w10": 5, "miss_g20": 6}


def order_key(c):
    """G8 tie order: fewer tuned parameters (W0), then the alpha family, then E shares; smaller change from v3 (a set, c statistic); name."""
    bud = c["bud"]
    fam = 0 if bud == "W0" else 1 if bud[0] == "alpha" else 2
    dist = abs(bud[1] - 0.25) if fam == 1 else 0.0
    return (fam, A_ORDER[c["a"]], C_ORDER[c["c"]], dist, c["name"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes-top", type=int, default=4)
    ap.add_argument("--tag", default="r3")
    a = ap.parse_args()
    t0 = time.time()
    if FRAME.exists():
        frame = pd.read_pickle(FRAME)
    else:
        frame = A.build_frame(A.load_parts())
        frame.to_pickle(FRAME)
    print("frame", frame.shape, f"{time.time() - t0:.0f}s", flush=True)
    res = {}
    cands = A.candidates(a.tag)
    for c in cands:
        r, _ = A.evaluate(frame, c)
        res[c["name"]] = r
        print(f"{c['name']:30s} FA {100 * r['fa']:5.2f} worst {100 * r['fa_worst_drive']:5.2f} PD {100 * r['det']['PointDrop']:5.1f} "
              f"IS {100 * r['det']['IntensitySpoof']:5.1f} nr {100 * r['det']['ph_replace_near']:5.1f} "
              f"mr_far {100 * r['det']['cmp_mradd_far']:5.1f}", flush=True)
    m0 = res["M0|all4"]
    pool_all = [c for c in cands if c["method"] != "max" and c["B"] == 0.01]
    feas = [c for c in pool_all if feasible(res[c["name"]], m0)]
    sel = {"rule": "feasible: FA in [0.5, 1.5] % and every kind >= M0|all4 - 2 points; maximise PointDrop; within 0.5 points G8 order",
           "n_candidates": len(pool_all), "exploratory_B1.25_rows": [c["name"] for c in cands if c["B"] != 0.01 and c["method"] != "max"][:0], "n_feasible": len(feas), "feasible": [c["name"] for c in feas]}
    pool = feas
    if not pool:
        def n_ok(c):
            r = res[c["name"]]
            return (0.005 <= r["fa"] <= 0.015) * 100 + sum(r["det"][k] >= m0["det"][k] - 0.02 for k in L.ATTACKS)
        best = max(n_ok(c) for c in pool_all)
        pool = [c for c in pool_all if n_ok(c) == best]
        sel["fallback"] = f"no feasible candidate; pool = candidates with the most kinds meeting the rule (score {best}: 100 if FA in range + kinds met)"
    top = max(res[c["name"]]["det"]["PointDrop"] for c in pool)
    near = sorted([c for c in pool if res[c["name"]]["det"]["PointDrop"] >= top - 0.005], key=order_key)
    chosen = near[0]
    sel["chosen"] = chosen["name"]
    sel["chosen_cfg"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in chosen.items()}
    sel["within_0.5_points"] = [c["name"] for c in near]
    expl = [c for c in cands if c["method"] != "max" and c["B"] != 0.01 and feasible(res[c["name"]], m0)]
    if expl:
        topx = max(res[c["name"]]["det"]["PointDrop"] for c in expl)
        bx = sorted([c for c in expl if res[c["name"]]["det"]["PointDrop"] >= topx - 0.005], key=order_key)[0]
        sel["exploratory_B1.25_best"] = bx["name"]
        sel["exploratory_B1.25_n_feasible"] = len(expl)
    ranked = sorted(pool_all, key=lambda c: -res[c["name"]]["det"]["PointDrop"])
    ep_names = ["M0|all4", chosen["name"]] + [c["name"] for c in ranked[:a.episodes_top] if c["name"] != chosen["name"]]
    for n in ep_names:
        c = [x for x in cands if x["name"] == n][0]
        r, _ = A.evaluate(frame, c, with_episodes=True)
        res[n]["episodes"] = r["episodes"]
        print("episodes", n, r["episodes"], flush=True)
    for n, r in res.items():
        r["det_ci95"] = {k: boot_ci(r["det_by_drive"][k]) for k in ("PointDrop", "IntensitySpoof", "ph_replace_near")}
    out = {n: {k: v for k, v in r.items() if k != "alarms"} for n, r in res.items()}
    (OUT / f"candidates_{a.tag}.json").write_text(json.dumps(out, indent=1))
    (OUT / f"selection_{a.tag}.json").write_text(json.dumps(sel, indent=1))
    print(json.dumps(sel, indent=1))
    print(f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
