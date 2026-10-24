"""WP6 S4 stage 3: the ONE test run of the frozen zero-day system (results/WP6/s4_frozen.pkl, chosen on validation by tools/WP6_S4_dev.py).
Scored once, labelled: (1) system level on S3-style composites (K, C): chosen variant, matched no-novelty ablation, other novelty kind, rules-only and
L3-only systems, the whole 12-config grid (information), equal-FA diagnostic (threshold at 2% of TEST clean composite ticks: test-informed, labelled);
(2) tier table per domain at tick level (rules / L3 / union / novelty / frozen domain score, GPS S7 L3, network dos_rate, LiDAR XGB), thresholds = 1% of the
clean validation half-B ticks; (3) acceptance Z1-Z6. Run: python -u -W ignore tools/WP6_S4_test.py
Outputs: results/WP6/s4_test.json, s4_acceptance.json   (WP6_S4_SMOKE=1: plumbing check with the validation packs as "test", output in the temp folder)
"""
import json
import os
import pickle
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED, results_dir  # noqa: E402
from common.metrics import budget_threshold  # noqa: E402
import WP6_S3_lib as L3  # noqa: E402
import WP6_S4_lib as L  # noqa: E402

SMOKE = bool(int(os.environ.get("WP6_S4_SMOKE", "0")))
OUT = results_dir("WP6")
OUT_W = Path(tempfile.gettempdir()) / "wp6_s4_smoke" if SMOKE else OUT
OUT_W.mkdir(parents=True, exist_ok=True)
T0 = time.time()
S3_FA = {"K": 0.0636, "C": 0.0631}                       # S3 headline clean test tick FA (results/WP6/s3_acceptance.json)


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def clean_mask(comps):
    return np.concatenate([np.full(c["n"], c["family"] == "none") for c in comps])


def run_variant(key, frozen, comps, packs_fam, fam, with_ci=False):
    var, fus = frozen["variants"][key]
    X, s = L.score_variant(var, fus, comps, packs_fam)
    m, outs, tab = L.summarize(comps, s, fus.threshold)
    held = [f for f, x in tab.items() if x["category"] == "heldout"]
    seen = [f for f, x in tab.items() if x["category"] == "seen"]
    m["ci_heldout"] = L.fast_ci(outs, held) if held else None
    m["ci_seen"] = L.fast_ci(outs, seen) if seen else None
    thr_eq = budget_threshold(s[clean_mask(comps)], 0.02)
    me, oe, te = L.summarize(comps, s, thr_eq)
    m["equal_fa"] = {"threshold": float(thr_eq), "fa_tick": me["fa_tick"], "by_category": me["by_category"], "by_category_domain": me["by_category_domain"],
                     "families": {f: x["detection"] for f, x in te.items()}}
    return m, outs, X, s, var, fus


def novelty_examples(frozen, comps, packs_fam, X, s, fus, var, fam, k=4):
    """A few alarm ticks of held-out composites where the novelty entry is the strongest entry: which layers deviate (EvidenceNovelty.explain)."""
    idx = L3.index_of(comps)
    names = [e[0] for e in var["entries"]]
    nov_j = [j for j, n in enumerate(names) if n.endswith(".nov")]
    out = []
    if not nov_j:
        return out
    for ci, c in enumerate(comps):
        if len(out) >= k or c["family"] == "none" or L.category(c["family"], c["attacked"]) != "heldout":
            continue
        a = np.flatnonzero((s[idx[ci]:idx[ci + 1]] >= fus.threshold) & c["label"])
        for i in a[:1]:
            row = X[idx[ci] + i]
            j = int(np.argmax(row))
            if j in nov_j:
                d = var["entries"][j][1]
                key = {"gps": "gps", "can": "can", "network": "network", "v2x": "v2x", "cross": "cross_kitti" if fam == "K" else "cross_comma"}[d]
                det, ix = frozen["dets"][(key, var["nov"])]
                lay = c["parts"][d]["layers"][i][ix]
                out.append({"family": c["family"], "domain": d, "tick": int(i), "top_layers": det.explain(lay)})
    return out


def lidar_extra(part):
    return None


def tier_tables(uv_val, ut, gB, part):
    import pickle as pk
    g3 = pk.load(open(L.CACHE / "s4_gps_l3.pkl", "rb"))["l3"]
    tables = {}
    for key in ("gps", "lidar", "can", "network", "v2x", "cross_kitti", "cross_comma"):
        pv, pt = uv_val[key], ut[key]
        extra = {}
        if key == "gps":
            extra["S7 L3 (MCD on motion features, WP1; gps_can runs excluded)"] = (lambda s: g3[("val", s["name"])], lambda s: g3[(part, s["name"])])
        if key == "network":
            j = pt["layer_names"].index("net.dos_rate")
            extra["net.dos_rate (on-network rule, warm-up baseline)"] = (lambda s, j=j: s["layers"][:, j], lambda s, j=j: s["layers"][:, j])
        if key == "lidar":
            extra["lidar.v2_baseline_interim (XGB, SUPERVISED: saw all three types)"] = (lambda s: s["layers"][:, 0], lambda s: s["layers"][:, 0])
        d = L.DOM_OF.get(key, key)
        rows = L.tier_rows(key, pv, pt, gB[key], extra)
        tables[key] = L.tier_summary(rows, d)
        log("tier", key, {r: (None if v["mean_det_heldout"] is None else round(v["mean_det_heldout"], 3)) for r, v in rows.items()})
    return tables


def main():
    fz = pickle.load(open(OUT / "s4_frozen.pkl", "rb"))
    ch = fz["chosen"]
    log("TEST run (once). chosen:", ch, "smoke" if SMOKE else "")
    part = "val" if SMOKE else "test"
    u_val = L.load_unique("val")
    u_t = L.load_unique(part)
    uv_val = L.attach_novelty(u_val, fz["dets"])
    ut = L.attach_novelty(u_t, fz["dets"])
    packs = L.assemble(ut)
    res = {"chosen": ch, "smoke": SMOKE, "exposure_caveat": "every domain test set was scored before (ROAD 6x, D10 several, VeReMi 2x, KITTI several); the zero-day system, "
           "the tier table and the novelty layer are scored on test once here", "system": {}}
    comps = {}
    for fam in ("K", "C"):
        c = fz["composites_test"][fam]
        comps[fam] = L3.build_set(fam, packs[fam], None, c["seed"], c["n_clean"], c["n_attack"])
        log(fam, "test composites", len(comps[fam]))
    sysres = {}
    for fam in ("K", "C"):
        R = {}
        outs_keep = {}
        main_key = L.var_key(L.variant(fam, ch["method"], ch["net"], ch["nov"]))
        nonov_key = L.var_key(L.variant(fam, ch["method"], ch["net"], None))
        names = {"headline (chosen)": main_key, "matched without novelty": nonov_key}
        for nv in L.NOV_KINDS:
            if nv != ch["nov"]:
                names[f"matched with novelty {nv}"] = L.var_key(L.variant(fam, ch["method"], ch["net"], nv))
        for g in ("rules", "l3"):
            names[f"{g}-only system"] = L.var_key(L.variant(fam, ch["method"], ch["net"], None, groups=g))
        for name, key in names.items():
            m, outs, X, s, var, fus = run_variant(key, fz, comps[fam], packs[fam], fam, with_ci=name in ("headline (chosen)", "matched without novelty"))
            R[name] = m
            outs_keep[name] = outs
            if name == "headline (chosen)":
                R[name]["novelty_examples"] = novelty_examples(fz, comps[fam], packs[fam], X, s, fus, var, fam)
            log(fam, name, "FA", round(m["fa_tick"], 4), "heldout", m["by_category"]["heldout"], "seen", m["by_category"]["seen"], "| equal-FA heldout", m["equal_fa"]["by_category"]["heldout"])
        a, b = outs_keep["headline (chosen)"], outs_keep["matched without novelty"]
        R["novelty_rescued_vs_lost"] = {
            "heldout_rescued": int(sum(1 for x, y in zip(a, b) if x["family"] != "none" and L.category(x["family"], x["attacked"]) == "heldout" and x["detected"] and not y["detected"])),
            "heldout_lost": int(sum(1 for x, y in zip(a, b) if x["family"] != "none" and L.category(x["family"], x["attacked"]) == "heldout" and not x["detected"] and y["detected"])),
            "heldout_composites": int(sum(1 for x in a if x["family"] != "none" and L.category(x["family"], x["attacked"]) == "heldout"))}
        grid = {}
        for key, (var, fus) in fz["variants"].items():
            if var["fam"] != fam or var["groups"] != "full":
                continue
            X, s = L.score_variant(var, fus, comps[fam], packs[fam])
            m, outs, tab = L.summarize(comps[fam], s, fus.threshold)
            grid[f"{var['method']}|net={var['net']}|nov={var['nov']}"] = {"fa_tick": m["fa_tick"], "by_category": m["by_category"]}
        R["grid_all_configs"] = grid
        sysres[fam] = R
    res["system"] = sysres
    log("tier tables")
    gB = fz["gB"] if "gB" in fz else L.halves_unique(u_val)[2]
    res["tier"] = tier_tables(uv_val, ut, gB, part)
    # ---------------- acceptance
    K, C = sysres["K"], sysres["C"]
    hk, hc = K["headline (chosen)"], C["headline (chosen)"]
    mk, mc = K["matched without novelty"], C["matched without novelty"]
    z1k, z1c = hk["by_category"]["heldout"], hc["by_category"]["heldout"]
    seen_k = hk["by_category"]["seen"]
    dom = {}
    for d in ("gps", "can", "network", "v2x"):
        rows = res["tier"][d]
        r, l = rows["rules (physics / rule)"]["mean_det_heldout"], rows["L3 (normal-only model)"]["mean_det_heldout"]
        dom[d] = {"rules": r, "l3": l, "rules_ge_l3": (r or 0) >= (l or 0)}
    d_det = hk["by_category"]["heldout"] - mk["by_category"]["heldout"]
    d_fa = hk["fa_tick"] - mk["fa_tick"]
    acc = {
        "Z1_heldout_detection_K": {"value": z1k, "ci": hk["ci_heldout"]["mean_detection"] if hk["ci_heldout"] else None, "rule": ">= 0.60", "met": z1k >= 0.60},
        "Z1_heldout_detection_C": {"value": z1c, "ci": hc["ci_heldout"]["mean_detection"] if hc["ci_heldout"] else None, "rule": ">= 0.60", "met": z1c >= 0.60},
        "Z2_fa_tick_K": {"value": hk["fa_tick"], "ci": hk["ci_heldout"]["fa_tick"] if hk["ci_heldout"] else None, "rule": "<= 0.030 and <= S3 + 0.010",
                         "met": hk["fa_tick"] <= 0.03 and hk["fa_tick"] <= S3_FA["K"] + 0.01, "within_s3_plus_1pt": hk["fa_tick"] <= S3_FA["K"] + 0.01, "s3": S3_FA["K"]},
        "Z2_fa_tick_C": {"value": hc["fa_tick"], "rule": "<= 0.030 and <= S3 + 0.010", "met": hc["fa_tick"] <= 0.03 and hc["fa_tick"] <= S3_FA["C"] + 0.01,
                         "within_s3_plus_1pt": hc["fa_tick"] <= S3_FA["C"] + 0.01, "s3": S3_FA["C"]},
        "Z3_zero_day_gap_K_points": {"heldout": z1k, "seen": seen_k, "value": 100 * (seen_k - z1k), "rule": "heldout >= seen - 15 points", "met": z1k >= seen_k - 0.15},
        "Z4_physics_ge_l3": {"value": dom, "n_domains": int(sum(v["rules_ge_l3"] for v in dom.values())), "rule": ">= 3 of 4 domains: rules >= L3 on held-out types (tick level)",
                             "met": sum(v["rules_ge_l3"] for v in dom.values()) >= 3},
        "Z5_novelty_layer": {"delta_heldout_points_K": 100 * d_det, "delta_fa_points_K": 100 * d_fa, "delta_heldout_points_C": 100 * (hc["by_category"]["heldout"] - mc["by_category"]["heldout"]),
                             "delta_fa_points_C": 100 * (hc["fa_tick"] - mc["fa_tick"]), "rule": "kept iff K: held-out +3 points and FA +0.5 points at most", "met": d_det >= 0.03 and d_fa <= 0.005},
        "Z6_selection_audit": {"value": "dev run asserted that no held-out family entered any choice (results/WP6/logs/s4_dev.log); selection set = non-held-out families", "met": True},
    }
    res["acceptance"] = acc
    (OUT_W / "s4_test.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT_W / "s4_acceptance.json").write_text(json.dumps(acc, indent=1, default=str))
    for k, v in acc.items():
        log(k, "MET" if v["met"] else "NOT MET", v.get("value") if not isinstance(v.get("value"), dict) else "")
    log("done")


if __name__ == "__main__":
    main()
