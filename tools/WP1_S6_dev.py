"""WP1 S6 development pass: KITTI TRAIN + VAL drives only (16 drives); the test drives are not scored here.
  - D2 map sanity (clean dev rows): distance to the drivable network, heading deviation;
  - candidates gps.map_dist / map_heading / map_comb: LODO pooled 1% tie-safe threshold, held-out FA, run-level detections, J;
  - NESTED selection of the primary (choice on the other 15 drives, held-out FA reported); test choice = best J on all 16 drives;
  - diagnostics (not selectable): map without `service` ways, map with ALL highway classes (footways, paths, tracks), on-road fraction per attack.
q_d, q_h = 95th percentile of the clean dev scores (scale of map_comb, no attack label used; frozen before detection results).
Outputs: results/WP1/S6_dev.json, S6_dev_grid.md. Run from codes_v3/: python -u -W ignore tools/WP1_S6_dev.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP1_S4_lib as L
import WP1_S4_dev as D4
from common.metrics import budget_threshold
from gps import map_match as MM

BUDGET = 0.01
CANDS = ("map_dist", "map_heading", "map_comb")
ALL_CLASSES = None


def all_classes():
    els = json.load(open(MM.OSM_JSON, encoding="utf-8"))["elements"]
    return frozenset(e["tags"]["highway"] for e in els if e["type"] == "way" and "highway" in e.get("tags", {}))


def dev_stream(rmap):
    kx = L.kitti_stream()
    dev = kx[kx["part"].isin(L.DEV_PARTS)]
    assert not dev["part"].eq("test").any()
    return dev.join(MM.stream_features(dev, rmap))


def add_comb(df, qd, qh):
    df = df.copy()
    df["map_comb"] = np.maximum(df["map_dist"] / qd, df["map_heading"] / qh)
    return df


def on_road_fraction(df, thr):
    out = {}
    for a in L.ATT:
        m = ((df["attack"] == a) & (df["label"] == 1)).to_numpy()
        out[a] = float((df.loc[m, "map_dist"] <= thr).mean())
    return out


def main():
    rmap = MM.RoadMap.from_osm()
    print("segments", len(rmap.len), "dense points", rmap.tree.n, flush=True)
    dev = dev_stream(rmap)
    y = dev["label"].to_numpy()
    normal = y == 0
    clean = normal & (dev["attack"] == "none").to_numpy()
    qd = float(np.percentile(dev.loc[normal, "map_dist"], 95))
    mv = normal & (dev["odo_speed"] >= MM.MIN_SPEED).to_numpy()
    qh = float(np.percentile(dev.loc[mv, "map_heading"], 95))
    dev = add_comb(dev, qd, qh)
    res = {"n_segments": int(len(rmap.len)), "q_d": qd, "q_h": qh, "classes": sorted(MM.DRIVABLE_CLASSES)}
    d = dev.loc[normal, "map_dist"]
    h = dev.loc[mv, "map_heading"]
    res["D2"] = {"frac_within_10m": float((d <= 10).mean()), "median_dist_m": float(d.median()), "p95": qd, "p99": float(d.quantile(0.99)),
                 "median_heading_dev_deg": float(h.median()), "p95_heading_deg": qh, "p99_heading_deg": float(h.quantile(0.99)), "n_rows": int(normal.sum())}
    res["D2"]["met"] = bool(res["D2"]["frac_within_10m"] >= 0.95 and res["D2"]["median_dist_m"] <= 4 and res["D2"]["median_heading_dev_deg"] <= 10)
    print("D2", res["D2"], flush=True)
    drive = dev["drive"].to_numpy()
    drives = sorted(dev["drive"].unique())
    S = {c: dev[c].to_numpy() for c in CANDS}
    res["candidates"] = {}
    for c in CANDS:
        res["candidates"][c] = D4.evaluate(dev, S[c], c)
        r = res["candidates"][c]
        print(c, "J", round(r["J"], 3), "heldout FA", round(r["lodo"]["heldout_fa_pooled"], 4), "run det", {a: round(v, 2) for a, v in r["summary"]["run_detected"].items()}, flush=True)
    best_all = max(CANDS, key=lambda c: res["candidates"][c]["J"])
    res["selected_all16"] = best_all
    thr99 = float(np.percentile(dev.loc[normal, "map_dist"], 99))
    res["on_road_fraction_dev_attacks_within_clean_p99"] = on_road_fraction(dev, thr99)
    # nested selection
    choices, flag_nested = {}, np.zeros(len(dev), bool)
    for dr in drives:
        m = drive == dr
        js = {}
        for c in CANDS:
            thr = budget_threshold(S[c][normal & ~m], BUDGET)
            js[c] = L.j_criterion(L.summarize(dev[~m], S[c][~m] >= thr))
        c = max(js, key=js.get)
        thr = budget_threshold(S[c][normal & ~m], BUDGET)
        flag_nested[m] = S[c][m] >= thr
        choices[dr] = {"choice": c, "J_on_other_15": js[c], "threshold": thr, "heldout_fa": float(flag_nested[m & normal].mean()) if (m & normal).any() else None}
    nsm = L.summarize(dev, flag_nested)
    res["nested"] = {"choices": choices, "heldout_fa_pooled": float(flag_nested[normal].mean()), "summary": nsm, "J": L.j_criterion(nsm),
                     "choice_counts": {c: sum(1 for v in choices.values() if v["choice"] == c) for c in CANDS}}
    print("nested held-out FA", res["nested"]["heldout_fa_pooled"], "J", res["nested"]["J"], res["nested"]["choice_counts"], "selected:", best_all, flush=True)
    # diagnostics on other map variants (dev only, not selectable)
    res["diagnostic_maps"] = {}
    for name, classes in (("no_service", MM.DRIVABLE_CLASSES - {"service"}), ("all_highway_classes", all_classes())):
        rm = MM.RoadMap.from_osm(classes=classes)
        dd = dev.drop(columns=["map_dist", "map_heading", "map_comb"]).join(MM.stream_features(dev, rm))
        dd = add_comb(dd, qd, qh)
        sub = {}
        for c in CANDS:
            sub[c] = D4.evaluate(dd, dd[c].to_numpy(), c)
        res["diagnostic_maps"][name] = {"n_segments": int(len(rm.len)), "J": {c: sub[c]["J"] for c in CANDS},
                                        "run_detected": {c: sub[c]["summary"]["run_detected"] for c in CANDS},
                                        "median_dist_clean": float(dd.loc[normal, "map_dist"].median()),
                                        "heldout_fa": {c: sub[c]["lodo"]["heldout_fa_pooled"] for c in CANDS}}
        print("diag", name, res["diagnostic_maps"][name]["J"], flush=True)
    (L.OUT / "S6_dev.json").write_text(json.dumps(res, indent=1, default=float))
    rows = ["| candidate | J | LODO held-out FA | worst drive | " + " | ".join(L.ATT) + " |", "|---" * (4 + len(L.ATT)) + "|"]
    for c, r in sorted(res["candidates"].items(), key=lambda kv: -kv[1]["J"]):
        rows.append(f"| {c} | {r['J']:.3f} | {100 * r['lodo']['heldout_fa_pooled']:.2f}% | {100 * r['lodo']['heldout_fa_worst_drive']:.2f}% | " + " | ".join(f"{100 * r['summary']['run_detected'][a]:.0f}%" for a in L.ATT) + " |")
    (L.OUT / "S6_dev_grid.md").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
