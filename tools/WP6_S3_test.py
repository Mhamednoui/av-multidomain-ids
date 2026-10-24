"""WP6 S3 stage 3: the ONE test run of the frozen system fusion (results/WP6/s3_frozen.pkl, chosen on validation by tools/WP6_S3_dev.py).
Test composites from every domain's own TEST material (construction notes/WP6_crossdomain.md "S3 start"), scored once: headline zero-shot
fusion, the other label-free combiner (information), the labelled seen-attack logistic row, ablation (each domain removed / alone), G3 no-cross,
G5 domain alone, explanations of every alarm, cross-domain S2b/S3 choice first test number, v2-style composite accuracy (not like-for-like),
acceptance G1-G5. Run: python -u -W ignore tools/WP6_S3_test.py     Outputs: results/WP6/s3_test.json, s3_acceptance.json, s3_tables.md
"""
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common.config import SEED, results_dir  # noqa: E402
from fusion import composite as CP  # noqa: E402
import WP6_S3_lib as L  # noqa: E402

import os  # noqa: E402
import tempfile  # noqa: E402

SMOKE = bool(int(os.environ.get("WP6_S3_SMOKE", "0")))           # plumbing check: "test" := validation packs, output to the temp folder
OUT = results_dir("WP6")
OUT_W = Path(tempfile.gettempdir()) / "wp6_s3_smoke" if SMOKE else OUT
OUT_W.mkdir(parents=True, exist_ok=True)
T0 = time.time()
V2_META = {"accuracy": 0.9523, "fa": 0.0106, "source": "../codes_v2/results/fusion.json (meta fusion, 2% val budget)"}


def log(*a):
    print(f"[{time.time() - T0:6.0f}s]", *a, flush=True)


def layer_names(packs):
    return {d: list(p["layer_names"]) for d, p in packs.items()}


def domain_means(tab, fam):
    out = {}
    for f in L.single_families(tab, fam):
        out.setdefault(tab[f]["attacked"], []).append(tab[f]["detection"])
    return {d: float(np.mean(v)) for d, v in out.items()}


def v2_style(outs, seed):
    """50% clean composites / 50% attacked composites (single-domain families, uniform over families): composite-level accuracy."""
    rng = np.random.default_rng(seed)
    clean = [r for r in outs if r["family"] == "none"]
    att = [r for r in outs if r["family"] != "none" and r["family"] not in CP.V2_COMPARISON and r["attacked"] in ("gps", "lidar", "can", "network", "v2x", "cross")]
    fams = sorted({r["family"] for r in att})
    by = {f: [r for r in att if r["family"] == f] for f in fams}
    pick = [by[fams[rng.integers(len(fams))]] for _ in range(len(clean))]
    pick = [p[rng.integers(len(p))] for p in pick]
    tn = sum(r["alarm_ticks"] == 0 for r in clean)
    tp = sum(r["detected"] for r in pick)
    return {"accuracy": (tn + tp) / (len(clean) + len(pick)), "composite_FA": 1 - tn / len(clean), "composite_detection": tp / len(pick), "n": len(clean) + len(pick)}


def cross_first_test(packs):
    """S2b / S3 frozen cross-domain choice at its OWN 1% threshold on the test series (first test number, labelled)."""
    out = {}
    for f in ("K", "C"):
        p = packs[f]["cross"]
        cl = [s for s in p["series"] if s["kind"] == "clean"]
        fa = float(np.concatenate([s["dom_alarm"] for s in cl]).mean())
        det, blame = {}, {}
        for s in p["series"]:
            if s["kind"] != "attack":
                continue
            hit = s["dom_alarm"] & s["label"]
            det.setdefault(s["family"], []).append(bool(hit.any()))
            if hit.any():
                b = [x for x in s["blame"][s["label"]] if x not in (None, "undecided")]
                blame.setdefault(s["family"], []).append(b[0] if b else "undecided")
        out[f] = {"fa_rows": fa, "clean_rows": int(sum(len(s["score"]) for s in cl)),
                  "detection": {k: float(np.mean(v)) for k, v in det.items()},
                  "blame": {k: {str(a): int(c) for a, c in zip(*np.unique(np.array(v, dtype=str), return_counts=True))} for k, v in blame.items()}}
    return out


def domain_own_fa(packs):
    out = {}
    for d, p in packs["K"].items():
        cl = [s for s in p["series"] if s["kind"] == "clean"]
        a = np.concatenate([s["dom_alarm"] if "dom_alarm" in s else s["score"] >= p["dom_thr"] for s in cl])
        out[d] = {"fa_ticks_own_threshold": float(a.mean()), "clean_ticks": int(len(a))}
    out["cross_comma"] = {"fa_ticks_own_threshold": float(np.concatenate([s["dom_alarm"] for s in packs["C"]["cross"]["series"] if s["kind"] == "clean"]).mean())}
    return out


def main():
    fz = pickle.load(open(OUT / "s3_frozen.pkl", "rb"))
    chosen = fz["chosen"]
    pt = L.load_packs("val" if SMOKE else "test")
    log("TEST run (once). chosen combiner:", chosen)
    res = {"chosen": chosen, "exposure_caveat": "domain test sets scored before: ROAD 6x, D10 several (WP4 S2-S7), VeReMi 2x, KITTI several; "
           "the fusion layer and the S2b cross choice are scored here once", "families": {}}
    comps = {}
    for fam in ("K", "C"):
        c = fz["composites"][fam]
        comps[fam] = L.build_set(fam, pt[fam], None, c["seed"], c["n_clean"], c["n_attack"])
        log(fam, "test composites", len(comps[fam]))
    acc = {}
    for fam in ("K", "C"):
        ln = layer_names(pt[fam])
        R = {}
        fus = fz["fusions"][(chosen, fam, "all")]
        m, outs = L.evaluate(fus, comps[fam], explain_all=True, layer_names=ln)
        tab = L.family_table(outs)
        sf = L.single_families(tab, fam)
        m["mean_detection_single"] = L.mean_detection(tab, sf)
        m["per_domain_mean_detection"] = domain_means(tab, fam)
        m["ci"] = L.cluster_ci(outs, sf)
        m["families"] = tab
        m["v2_style"] = v2_style(outs, [SEED, 63, 11, ord(fam)])
        att = [r for r in outs if r["family"] != "none" and r["detected"] and r["family"] in sf]
        m["attributed_pooled"] = float(np.mean([r["attributed"] for r in att])) if att else None
        R["headline"] = m
        log(fam, "headline FA tick", round(m["fa_tick"], 4), "events/h", round(m["fa_events_per_hour"], 1), "mean det", round(m["mean_detection_single"], 3),
            "expl", m["alarms_with_explanation"], "/", m["alarms"])
        other = "max" if chosen == "noisy_or" else "noisy_or"
        for name, f2 in ((f"{other} (label-free, not chosen)", fz["fusions"][(other, fam, "all")]),
                         ("seen-attack logistic (labelled)", fz["fusions"][("logistic", fam, "all")])):
            mm, oo = L.evaluate(f2, comps[fam])
            tt = L.family_table(oo)
            R[name] = {"fa_tick": mm["fa_tick"], "fa_events_per_hour": mm["fa_events_per_hour"], "mean_detection_single": L.mean_detection(tt, L.single_families(tt, fam)),
                       "per_domain_mean_detection": domain_means(tt, fam), "families": {f: v["detection"] for f, v in tt.items()}}
        R["ablation"] = {}
        for (meth, ff, name), f2 in fz["fusions"].items():
            if meth != chosen or ff != fam or name == "all":
                continue
            mm, oo = L.evaluate(f2, comps[fam])
            tt = L.family_table(oo)
            R["ablation"][name] = {"domains": f2.domains, "fa_tick": mm["fa_tick"], "fa_events_per_hour": mm["fa_events_per_hour"],
                                   "mean_detection_single": L.mean_detection(tt, L.single_families(tt, fam)), "per_domain_mean_detection": domain_means(tt, fam),
                                   "families": {f: v["detection"] for f, v in tt.items()}}
        res["families"][fam] = R
        log(fam, "ablation done")
    res["cross_first_test"] = cross_first_test(pt)
    res["domain_own_fa_ticks"] = domain_own_fa(pt)
    res["v2_reference"] = V2_META
    # ---------------- acceptance ----------------
    K, C = res["families"]["K"], res["families"]["C"]
    hk = K["headline"]
    vf = [f for f in CP.K_VEHICLE_FAMILIES if f in hk["families"]]
    gf = [f for f in CP.GPS_FAMILIES if f in hk["families"]]
    noc = K["ablation"]["without cross"]["families"]
    g3_all = float(np.mean([hk["families"][f]["detection"] for f in vf]) - np.mean([noc[f] for f in vf]))
    g3_gps = float(np.mean([hk["families"][f]["detection"] for f in gf]) - np.mean([noc[f] for f in gf]))
    g5 = {}
    for d in ("gps", "lidar", "can", "network", "v2x", "cross"):
        fams = [f for f in L.single_families(hk["families"], "K") if hk["families"][f]["attacked"] == d]
        alone = K["ablation"].get(f"{d} alone")
        if not fams or alone is None:
            continue
        fused = float(np.mean([hk["families"][f]["detection"] for f in fams]))
        al = float(np.mean([alone["families"][f] for f in fams]))
        g5[d] = {"fused": fused, "alone": al, "loss_points": 100 * (al - fused), "met": fused >= al - 0.15}
    acc = {
        "G1_fa_tick_K": {"value": hk["fa_tick"], "ci": hk["ci"]["fa_tick"], "rule": "<= 0.030", "met": hk["fa_tick"] <= 0.03},
        "G1_fa_tick_C": {"value": C["headline"]["fa_tick"], "ci": C["headline"]["ci"]["fa_tick"], "rule": "<= 0.030", "met": C["headline"]["fa_tick"] <= 0.03},
        "G2_mean_detection_K": {"value": hk["mean_detection_single"], "ci": hk["ci"]["mean_detection"], "rule": ">= 0.70", "met": hk["mean_detection_single"] >= 0.70},
        "G3_cross_gain_vehicle_families_points": {"value": 100 * g3_all, "rule": ">= +10", "met": g3_all >= 0.10},
        "G3_cross_gain_gps_families_points": {"value": 100 * g3_gps, "rule": ">= +5", "met": g3_gps >= 0.05},
        "G4_explanations": {"value": hk["alarms_with_explanation"] / max(hk["alarms"], 1), "alarms": hk["alarms"], "rule": "1.0", "met": hk["alarms_with_explanation"] == hk["alarms"]},
        "G4_attributed_K": {"value": hk["attributed_pooled"], "rule": ">= 0.80", "met": (hk["attributed_pooled"] or 0) >= 0.80},
        "G5_no_domain_lost": {"value": g5, "rule": "fused >= alone - 15 points per attacked domain", "met": all(v["met"] for v in g5.values())},
    }
    res["acceptance"] = acc
    (OUT_W / "s3_test.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT_W / "s3_acceptance.json").write_text(json.dumps(acc, indent=1, default=str))
    for k, v in acc.items():
        log(k, "MET" if v["met"] else "NOT MET", v["value"] if not isinstance(v["value"], dict) else "")
    log("done")


if __name__ == "__main__":
    main()
