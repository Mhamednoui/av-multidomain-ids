"""WP2 S7: Car-Hacking, D11 (unknown-vehicle tests, both regimes) and the v2 side-by-side, from stored results. NO new scoring of any test set.
Sources: results/WP2/s2_carhacking.json, s2_d11_set_0N.json (L1 specification rules; deterministic, code unchanged since S2), ../codes_v2/results/road_windows.json (read only).
For these data sets the CAN stack is L1 only: no DBC exists for Car-Hacking / D11, so L2b and L3 cannot run (stated, not faked).
Output: results/WP2/s7_others.json, s7_others.md.  Usage: python -u -W ignore tools/WP2_S7_others.py
"""
import json

import numpy as np

from WP2_S7_lib import OUT, dump_json

V2 = OUT.parent.parent.parent / "codes_v2" / "results" / "road_windows.json"
COMB = "combined"


def counts_bootstrap(k, n, n_boot=4000, seed=42):
    """Pooled rate k.sum()/n.sum() with a 95% percentile interval over resampled files (clusters)."""
    k, n = np.asarray(k, float), np.asarray(n, float)
    if n.sum() == 0:
        return None, (None, None)
    rate = k.sum() / n.sum()
    if len(k) < 2:
        return float(rate), (None, None)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(k), size=(n_boot, len(k)))
    r = k[idx].sum(1) / np.maximum(n[idx].sum(1), 1)
    return float(rate), (float(np.quantile(r, 0.025)), float(np.quantile(r, 0.975)))


def fmt(x, d=1):
    return "-" if x is None else f"{100 * x:.{d}f}%"


def carhacking():
    d = json.load(open(OUT / "s2_carhacking.json"))
    R = d["regimes"]["A"]
    rows = {}
    for att, rec in R["per_capture"].items():
        c = rec["layers"][COMB]
        rows[att] = {"attack_windows": rec["attack_windows"], "clean_windows": rec["clean_windows"], "window_recall": c["recall"], "detected": c["detected"],
                     "false_alerts_clean": c["false_alerts_clean"], "alone": {l: v["recall"] for l, v in rec["layers"].items()}}
    k = [r["false_alerts_clean"] for r in rows.values()]
    n = [r["clean_windows"] for r in rows.values()]
    fa, ci = counts_bootstrap(k, n)
    ab = {kk: {"detection": v["detection"], "false_alarm_rate": v["false_alarm_rate"], "auc": v["auc"], "by_attack": v["detection_by_attack"]}
          for kk, v in R["harness"]["ablation"].items()}
    return {"per_attack": rows, "clean_fa": fa, "clean_fa_ci95_bootstrap_over_attack_files": ci, "false_alerts_per_hour": R["summary"][COMB]["false_alerts_per_hour_clean"],
            "ablation": ab, "note": R.get("note", "test blocks are interleaved: delay fields are not onset delays")}


def d11():
    out = {}
    for s in ("01", "02", "03", "04"):
        d = json.load(open(OUT / f"s2_d11_set_{s}.json"))
        for sub, S in d["subsets"].items():
            known = S["vehicle"][0] == d["vehicle_train"]
            for reg in ("A", "B"):
                R = S["regimes"][reg]
                files = {}
                for g, rec in R["per_capture"].items():
                    c = rec["layers"][COMB]
                    files[g] = {"attack_windows": rec["attack_windows"], "clean_windows": rec["clean_windows"], "recall": c["recall"], "detected": c["detected"],
                                "delay_s": c["delay_s"], "false_alerts_clean": c["false_alerts_clean"]}
                out[f"set_{s}/{sub}/{reg}"] = {"set": s, "subset": sub, "regime": reg, "train_vehicle": d["vehicle_train"], "test_vehicle": S["vehicle"][0],
                                              "known_vehicle": known, "files": files, "n_eligible": S["n_eligible"]}
    return out


def d11_summary(cells):
    res = {}
    for reg in ("A", "B"):
        for known in (True, False):
            sel = [c for c in cells.values() if c["regime"] == reg and c["known_vehicle"] == known]
            files = [f for c in sel for f in c["files"].values()]
            att = [f for f in files if f["attack_windows"] > 0]
            k = [f["false_alerts_clean"] for f in files if f["clean_windows"] > 0]
            n = [f["clean_windows"] for f in files if f["clean_windows"] > 0]
            fa, ci = counts_bootstrap(k, n)
            lo, hi = (0.0, 1.0)
            det = sum(1 for f in att if f["detected"])
            from can.stack_eval import clopper_pearson
            lo, hi = clopper_pearson(det, len(att)) if att else (None, None)
            rec = [f["recall"] for f in att if f["recall"] is not None]
            res[f"{reg}_{'known' if known else 'unknown'}"] = {
                "subsets": len(sel), "files_with_attack": len(att), "files_detected": det, "files_detected_ci95_clopper_pearson": [lo, hi],
                "mean_window_recall": float(np.mean(rec)) if rec else None, "median_delay_s": float(np.median([f["delay_s"] for f in att if f["delay_s"] is not None])) if att else None,
                "clean_windows": int(sum(n)), "clean_fa_pooled": fa, "clean_fa_ci95_bootstrap_over_files": ci,
                "subset_fa": {"set_" + c["set"] + "/" + c["subset"] + "/" + c["test_vehicle"]: (sum(f["false_alerts_clean"] for f in c["files"].values()) / max(sum(f["clean_windows"] for f in c["files"].values()), 1)) for c in sel}}
    return res


def v2_side():
    d = json.load(open(V2))
    out = {}
    for name, label in (("R1", "v2 timing model (ROAD behaviour)"), ("R2", "v2 payload model (ROAD full)")):
        for tgt in ("val_fpr_0.01", "val_fpr_0.001"):
            r = d["detectors"][name][tgt]
            out[f"{name}_{tgt}"] = {"label": label, "target": tgt, "captures_detected": r["captures_detected"], "test_window_recall": r["test_window_recall"],
                                    "test_window_fpr": r["test_window_fpr"], "false_alerts_per_hour": r["test_false_alerts_per_hour"],
                                    "per_capture": {c: {"detected": v["detected"], "delay_s": v["delay_s"], "window_recall": v["window_recall"]}
                                                    for c, v in r["per_capture"].items()}}
    return out


def main():
    ch, cells = carhacking(), d11()
    res = {"carhacking": ch, "d11_cells": cells, "d11_summary": d11_summary(cells), "v2_road": v2_side(),
           "note": "L1 only. Car-Hacking test blocks were scored in S2 (L1), S3 (L2a), S6 (L4); D11 test subsets in S2, S3, S6; these numbers are the S2 ones, re-read not re-scored."}
    dump_json(res, OUT / "s7_others.json")
    L = ["# S7: Car-Hacking, D11 and v2 side-by-side (generated by tools/WP2_S7_others.py)\n", "## Car-Hacking test (L1 only; window level, 1% budget)",
         "| attack | attack windows | window recall | detected | false alerts on its clean windows |", "|---|---|---|---|---|"]
    for a, r in ch["per_attack"].items():
        L.append(f"| {a} | {r['attack_windows']} | {fmt(r['window_recall'])} | {r['detected']} | {r['false_alerts_clean']} / {r['clean_windows']} |")
    L.append(f"\nClean-window FA {fmt(ch['clean_fa'])} (95% bootstrap over the 4 attack files {fmt(ch['clean_fa_ci95_bootstrap_over_attack_files'][0])} - {fmt(ch['clean_fa_ci95_bootstrap_over_attack_files'][1])}), {ch['false_alerts_per_hour']:.0f} false alerts/h.")
    L.append("\nAblation (L1 rules): configuration | detection | FA | by attack")
    for k, v in ch["ablation"].items():
        L.append(f"- {k}: {fmt(v['detection'])} | {fmt(v['false_alarm_rate'], 2)} | {({a: round(b, 3) for a, b in v['by_attack'].items()})}")
    L.append("\n## D11 (L1 only)\n| regime | vehicle | subsets | attack files | files detected (95% CP) | mean window recall | median delay (s) | clean windows | clean FA (95% bootstrap over files) |\n|---|---|---|---|---|---|---|---|---|")
    for k, v in res["d11_summary"].items():
        ci = v["clean_fa_ci95_bootstrap_over_files"]
        L.append(f"| {k.split('_')[0]} | {k.split('_')[1]} | {v['subsets']} | {v['files_with_attack']} | {v['files_detected']} ({fmt(v['files_detected_ci95_clopper_pearson'][0], 0)}-{fmt(v['files_detected_ci95_clopper_pearson'][1], 0)}) | "
                 f"{fmt(v['mean_window_recall'])} | {v['median_delay_s']:.2f} | {v['clean_windows']} | {fmt(v['clean_fa_pooled'], 2)} ({fmt(ci[0], 2)}-{fmt(ci[1], 2)}) |")
    L.append("\nPer subset clean FA:")
    for k, v in res["d11_summary"].items():
        L.append(f"- {k}: " + ", ".join(f"{a} {fmt(b, 1)}" for a, b in v["subset_fa"].items()))
    L.append("\n## v2 side-by-side on the ROAD test (v2 results, read-only: ../codes_v2/results/road_windows.json)\n| v2 detector | target | captures detected | window recall | window FA | false alerts/h |\n|---|---|---|---|---|---|")
    for k, v in res["v2_road"].items():
        L.append(f"| {v['label']} | {v['target']} | {v['captures_detected']} | {fmt(v['test_window_recall'])} | {fmt(v['test_window_fpr'], 2)} | {v['false_alerts_per_hour']:.1f} |")
    open(OUT / "s7_others.md", "w").write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    main()
