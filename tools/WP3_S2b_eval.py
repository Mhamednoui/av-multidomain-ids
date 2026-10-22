"""WP3 S2b: VALIDATION-only re-score of v2 and L1 on single-return attacks, old (S2 tables, multi-return add) vs fixed.
Thresholds / L1 calibration exactly as S2 dev (clean validation scans, 1 % budget; v2 threshold quantile 1 - fpr).
Writes results/WP3/S2b/val_old_vs_fixed.{json,md}. No test row is read."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import WP3_S2_eval as E
from common.config import RESULTS
from lidar import geometry as G
from lidar.data import CACHE, VAL

OUTD = RESULTS / "WP3" / "S2b"
NEW = CACHE / "S2b"


def load_new(model, cols):
    gh, rays = [], []
    for d in VAL:
        a = pd.read_pickle(NEW / f"sr_v2_{d}.pkl")
        df = a["meta"].copy()
        for i, n in enumerate(G.STAT_NAMES):
            df[n] = a["stats"][:, i]
        df["v2"] = 1 - model.predict_proba(a["X"][:, cols])[:, 0]
        gh.append(df)
        b = pd.read_pickle(NEW / f"sr_ray_{d}.pkl")
        rd = b["meta"].copy()
        for i, n in enumerate(G.STAT_NAMES):
            rd[n] = b["stats"][:, i]
        rd["v2"] = 1 - model.predict_proba(b["X"][:, cols])[:, 0]
        rays.append(rd)
    return pd.concat(gh, ignore_index=True), pd.concat(rays, ignore_index=True)


def det_table(df, key, layers, thr):
    out = {}
    for k, x in df.groupby(key):
        k = "|".join(map(str, k))
        al = {n: np.array([e.alarm for e in layers[n].score(x)]) for n in ("union", "ring_total", "ring_sector", "single_return")}
        out[k] = {"n": int(len(x)), "median_points": float(x["n_spoofed"].median()) if "n_spoofed" in x else None,
                  "v2_1pct": float((x["v2"] > thr[0.01]).mean()), "v2_2pct": float((x["v2"] > thr[0.02]).mean()),
                  **{f"L1_{n}": float(a.mean()) for n, a in al.items()}}
    return out


def main():
    OUTD.mkdir(parents=True, exist_ok=True)
    model, cols = E.v2_model()
    val_v2, val_ray = E.load_part("val", model, cols)
    val = E.evalset_rows(val_v2, val_ray)
    layers = E.make_layers(val)
    vnorm = val_v2.loc[val_v2["cls"] == "Normal", "v2"].to_numpy()
    thr = {f: float(np.quantile(vnorm, 1 - f)) for f in (0.01, 0.02)}
    gh_new, ray_new = load_new(model, cols)
    res = {"thresholds": thr, "fa_check": det_table(val_v2[val_v2.cls == "Normal"].assign(g="clean"), ["g"], layers, thr)}
    gh_old = val_v2[val_v2.cls == "GhostCluster"]
    res["boxcloud_old"] = det_table(gh_old, ["mode"], layers, thr)
    res["boxcloud_fixed"] = det_table(gh_new, ["mode"], layers, thr)
    key = ["variant", "mode", "band", "timing"]
    old = val_ray[val_ray.n_spoofed > 0]
    new = ray_new[ray_new.n_spoofed > 0]
    res["ray_old_S2"] = det_table(old, key, layers, thr)
    res["ray_fixed"] = det_table(new, key, layers, thr)
    (OUTD / "val_old_vs_fixed.json").write_text(json.dumps(res, indent=1))
    L = ["# WP3 S2b: old (S2, add keeps the real return) vs fixed (single return), VALIDATION only", "",
         f"v2 thresholds (val clean 1 % / 2 %): {thr[0.01]:.3f} / {thr[0.02]:.3f}. Detection in %, onset and sustained pooled for box cloud, per timing for ray-cast.", "",
         "## Box cloud", "", "| mode | n old/fixed | v2 1% old | v2 1% fixed | L1 union old | L1 union fixed | L1 single_return old | fixed |", "|---|---|---|---|---|---|---|---|"]
    for m in res["boxcloud_old"]:
        o, f = res["boxcloud_old"][m], res["boxcloud_fixed"][m]
        L.append(f"| {m} | {o['n']}/{f['n']} | {100*o['v2_1pct']:.1f} | {100*f['v2_1pct']:.1f} | {100*o['L1_union']:.1f} | {100*f['L1_union']:.1f} | {100*o['L1_single_return']:.1f} | {100*f['L1_single_return']:.1f} |")
    L += ["", "## Ray-cast phantoms (variant cal = calibrated generator, old = S1 generator)", "",
          "| variant | mode | band | timing | n | med pts old | med pts fixed | v2 1% old | fixed | v2 2% old | fixed | L1 union old | fixed | L1 single_return old | fixed |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in res["ray_old_S2"]:
        o, f = res["ray_old_S2"][k], res["ray_fixed"][k]
        v, m, b, t = k.split("|")
        p = lambda x: f"{100*x:.1f}"
        L.append(f"| {v} | {m} | {b} | {t} | {o['n']} | {o['median_points']:.0f} | {f['median_points']:.0f} | {p(o['v2_1pct'])} | {p(f['v2_1pct'])} | {p(o['v2_2pct'])} | {p(f['v2_2pct'])} | {p(o['L1_union'])} | {p(f['L1_union'])} | {p(o['L1_single_return'])} | {p(f['L1_single_return'])} |")
    L += ["", f"Clean val FA check (v2 1 %, L1 union): {res['fa_check']}"]
    (OUTD / "val_old_vs_fixed.md").write_text("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
