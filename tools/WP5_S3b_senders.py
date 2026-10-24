"""WP5 S3b step 2b: look at the genuine TEST senders with the most alarms of the V2AIX-re-calibrated stack (variant B) and describe what is unusual about them
(reception gaps, speed vs position mismatch, GNSS jumps, standstill noise). Same scoring as WP5_S3b_clean.py (nothing re-fitted); no per-message output.
Output: results/WP5/s3b_top_senders.json / .md. Run from codes_v3/: python -I -u -W ignore tools/WP5_S3b_senders.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP5_S3b_lib as L

import numpy as np
import pandas as pd

from v2x import l_rx

TOP = 6


def describe_sender(g):
    g = g.sort_values("t", kind="stable")
    t, x, y, v = g["t"].to_numpy(), g["x"].to_numpy(), g["y"].to_numpy(), g["speed"].to_numpy()
    dt = np.diff(t)
    ok = (dt > 0) & (dt <= 5.0)
    dd = np.hypot(np.diff(x), np.diff(y))
    imp = np.where(ok, dd / np.maximum(dt, 1e-3), np.nan)
    vbar = 0.5 * (v[1:] + v[:-1])
    mism = np.abs(imp - vbar)
    d = l_rx.distance_to_receiver(g)
    return {"messages": int(len(g)), "duration_s": float(t[-1] - t[0]), "dt_median_s": float(np.median(dt)) if len(dt) else None, "dt_p95_s": float(np.quantile(dt, 0.95)) if len(dt) else None,
            "share_dt_gt_1s": float((dt > 1.0).mean()) if len(dt) else None, "dist_to_rx_m_min_max": [float(np.nanmin(d)), float(np.nanmax(d))] if np.isfinite(d).any() else None,
            "speed_median": float(np.median(v)), "speed_max": float(v.max()), "implied_speed_max": float(np.nanmax(imp)) if np.isfinite(imp).any() else None,
            "share_pairs_speed_position_mismatch_gt_10": float(np.nanmean(mism > 10)) if np.isfinite(mism).any() else None,
            "gnss_jumps(implied>70&jump>=15m)": int(((imp > 70) & (dd >= 15)).sum()), "pos_sigma_median": float(g["pos_sigma"].median())}


def main():
    res, md = {}, ["# S3b: genuine TEST senders with the most alarms (variant B), what is unusual about them", ""]
    for env in L.ENVS:
        S = L.Setup(env)
        test = L.load_env("test", env, S.sp)
        sc = S.score(test)
        a = sc["alarm"]["physics"]
        cnt = pd.Series(a).groupby(test["sender"].to_numpy()).sum().sort_values(ascending=False)
        res[env] = []
        md += [f"## {env}", "", "| rank | location | alarms | messages | duration s | dt median / p95 s | share dt > 1 s | distance to rx m | speed median / max | implied speed max | speed-position mismatch > 10 m/s | GNSS jumps | pos sigma | checks alarming |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for i, (s, n) in enumerate(cnt.head(TOP).items()):
            m = (test["sender"] == s).to_numpy()
            g = test[m]
            r = describe_sender(g)
            lay = {k.split(".")[1]: int(v[m].sum()) for k, v in sc["B_layers"].items()}
            top = ",".join(f"{k}:{v}" for k, v in sorted(lay.items(), key=lambda kv: -kv[1])[:4] if v > 0)
            r.update({"rank": i + 1, "location": g["loc"].iloc[0], "alarms": int(n), "top_checks": top})
            res[env].append(r)
            dm = r["dist_to_rx_m_min_max"]
            md.append(f"| {i + 1} | {r['location']} | {n} | {r['messages']} | {r['duration_s']:.0f} | {r['dt_median_s']:.2f} / {r['dt_p95_s']:.2f} | {100 * r['share_dt_gt_1s']:.0f}% | " + (f"{dm[0]:.0f}-{dm[1]:.0f}" if dm else "-") +
                      f" | {r['speed_median']:.1f} / {r['speed_max']:.1f} | " + (f"{r['implied_speed_max']:.1f}" if r["implied_speed_max"] is not None else "-") + " | " +
                      (f"{100 * r['share_pairs_speed_position_mismatch_gt_10']:.0f}%" if r["share_pairs_speed_position_mismatch_gt_10"] is not None else "-") + f" | {r['gnss_jumps(implied>70&jump>=15m)']} | {r['pos_sigma_median']:.1f} | {top} |")
        md.append("")
    (L.OUT / "s3b_top_senders.json").write_text(json.dumps(res, indent=1, default=float))
    (L.OUT / "s3b_top_senders.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
