"""WP8 S8 step 1: where do the V2AIX genuine false alarms of the frozen physics stack come from? Same scoring as tools/WP8_S7_v2aix.py (V31_val-fitted variant-B calibration, thresholds at 1 % of the V31_val genuine
messages), genuine H31 messages only (no injection), per recording and per site / location stratum, per layer (L1 / L2 / L3 / physics). Aggregates per recording only (message counts and alarm counts): no per-message
output is written or committed. python -I compatible. Output results/WP8/S8/v2aix_fa.json. Run: python -I -u -W ignore tools/WP8_S8_v2aix_fa.py"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

import WP8_S7_lib as S7
import WP8_S7_v2aix as V
import WP5_S3b_lib as L
from v2x import v2aix

T0 = time.time()


def main():
    S7.open_guard()
    outd = S7.ROOT / "results" / "WP8" / "S8" / "v2aix_tmp"
    outd.mkdir(parents=True, exist_ok=True)
    sp = json.loads((S7.ROOT / "results" / "WP5" / "splits_v2aix.json").read_text())
    v31 = json.loads((S7.ROOT / "locks" / "V31_val.json").read_text())["domains"]["v2x"]["v2aix"]
    sp31 = dict(sp, val=sorted(v31["val"]))
    (outd / "splits_v2aix.json").write_text(json.dumps(sp31))
    L.OUT = outd
    rids = [r["rid"] for r in S7.h31()["domains"]["v2x"]["fresh"]["v2aix"]["recordings"]]
    res = {}
    for env in L.ENVS:
        S = L.Setup(env)
        df = V.load_h31(env, rids)
        sc = S.score(df)
        a = {k: np.asarray(sc["alarm"][k], bool) for k in ("physics", "L1", "L2", "L3")}
        d = pd.DataFrame({"rec": df["recording"].to_numpy(), "loc": df["loc"].to_numpy(), **a})
        d["site"] = d["rec"].map(lambda r: "/".join(r.split("/")[:3]))
        d["day"] = d["rec"].map(lambda r: r.split("/")[3][:10])
        # val reference (same scoring): per-recording FA distribution of the V31_val genuine messages
        vs = S.score(S.val)
        va = pd.DataFrame({"rec": S.val["recording"].to_numpy(), "physics": np.asarray(vs["alarm"]["physics"], bool)})
        per = d.groupby("rec").agg(n=("physics", "size"), physics=("physics", "mean"), L1=("L1", "mean"), L2=("L2", "mean"), L3=("L3", "mean"))
        perv = va.groupby("rec").agg(n=("physics", "size"), physics=("physics", "mean"))
        site = d.groupby("site").agg(n=("physics", "size"), recs=("rec", "nunique"), physics=("physics", "mean"), L1=("L1", "mean"), L2=("L2", "mean"), L3=("L3", "mean"))
        day = d.groupby(["site", "day"]).agg(n=("physics", "size"), physics=("physics", "mean")).reset_index()
        stats = lambda p: {"recordings": int(len(p)), "messages": int(p["n"].sum()), "pooled": float((p["physics"] * p["n"]).sum() / p["n"].sum()), "median_rec": float(p["physics"].median()),
                           "p90_rec": float(p["physics"].quantile(0.9)), "share_recs_zero_fa": float((p["physics"] == 0).mean()),
                           "share_of_alarms_from_top10pct_recs": float(((p["physics"] * p["n"]).sort_values(ascending=False).head(max(1, len(p) // 10)).sum()) / (p["physics"] * p["n"]).sum())}
        res[env] = {"h31": stats(per), "val": stats(perv), "site": site.round(5).reset_index().to_dict("records"),
                    "worst_site_days": day.sort_values("physics", ascending=False).head(8).round(5).to_dict("records"), "layers_pooled": {k: float(d[k].mean()) for k in ("physics", "L1", "L2", "L3")},
                    "n_messages_per_rec": {"h31_median": float(per["n"].median()), "val_median": float(perv["n"].median())}}
        print(f"[{time.time() - T0:5.0f}s]", env, json.dumps(res[env]["h31"]), "VAL", json.dumps(res[env]["val"]), flush=True)
        for r in res[env]["site"]:
            print("  ", r, flush=True)
    S7.write_json(res, S7.ROOT / "results" / "WP8" / "S8" / "v2aix_fa.json")


if __name__ == "__main__":
    main()
