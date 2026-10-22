"""WP4 S4 resolvable-period limit: synthetic periodic groups (NEW groups; period P seconds, jitter j = gaps P*(1+U(-j,j)); Poisson control) quantised to the
1-minute grid of D10, scored by net.beacon fitted on benign TRAIN and calibrated on benign VAL (no test data). Output results/WP4/s4_limit.json.
A real attacker could use any period and jitter (Ares-like bots use random sleeps); this measures what the minute grid can resolve, not Ares."""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from common.config import BUDGET_DOMAIN, SEED
from tools.WP4_S3_lib import RES, load, log, stream
from network import l2b

PERIODS = [5, 10, 20, 30, 45, 60, 90, 100, 120, 150, 180, 300, 600, 720, 900, 1200, 1800]
JIT = [0.0, 0.1, 0.3, "poisson"]
NG, DUR_MIN = 20, 720


def synth(P, jit, rng):
    rows = []
    for g in range(NG):
        n = int(DUR_MIN * 60 / P * 1.5) + 5
        if jit == "poisson":
            gaps = rng.exponential(P, n)
        else:
            gaps = P * (1 + rng.uniform(-jit, jit, n))
        t = rng.uniform(0, P) + np.cumsum(gaps)
        t = t[t < DUR_MIN * 60]
        rows.append(pd.DataFrame({"g": g, "minute": (t // 60).astype("int64"), "row": np.arange(len(t))}))
    d = pd.concat(rows, ignore_index=True)
    d["src_id"], d["dst_id"], d["dst_port"], d["protocol"] = d["g"] + 10_000_000, 20_000_000, 8888, 6
    return d.sort_values(["minute", "row"], kind="stable").reset_index(drop=True)


def main():
    d = load("D10")
    tr, vb = stream(d, "train", True), stream(d, "val", True)
    del d
    L = l2b.Beacon(); L.fit(tr)
    subs = {s: l2b.BeaconStat(s) for s in l2b.STATS}
    f = L.feats(vb); sc = L.stat_scores(f)
    vb[L.score_col] = np.max(np.vstack([sc[k] for k in l2b.PHASE]), axis=0)
    for s, S in subs.items():
        vb[S.score_col] = sc[s]
    layers = {"phase": L, "rate": subs["rate"]}
    for X in layers.values():
        X.calibrate(vb, BUDGET_DOMAIN)
    rng = np.random.RandomState(SEED)
    out = {}
    for jit in JIT:
        for P in PERIODS:
            d = synth(P, jit, rng)
            f = L.feats(d); sc = L.stat_scores(f)
            raw = {"phase": np.max(np.vstack([sc[k] for k in l2b.PHASE]), axis=0), "rate": sc["rate"]}
            r = {"n_flows_per_group": float(len(d) / NG)}
            for nm, X in layers.items():
                al = X.calibrator.transform(raw[nm]) >= X.threshold
                gg = pd.Series(al).groupby(d["g"].to_numpy()).max()
                r[nm + "_pair"] = float(gg.mean()); r[nm + "_flow"] = float(al.mean())
            r["testable_flows"] = float(((f["_nact"] >= l2b.N_MIN) & (f["_med"] >= 2)).mean())
            out[f"{jit}|{P}"] = r
            log(jit, P, {k: round(v, 2) for k, v in r.items()})
    json.dump(out, open(os.path.join(RES, "s4_limit.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
