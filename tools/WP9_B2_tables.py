"""WP9 B2: collect results/WP9/B2/*_test.json (+ select / control) into results/WP9/B2_summary.json and results/WP9/B2_tables.md (generated, not hand-typed).
Run (codes_v3): python -u -W ignore -I tools/WP9_B2_tables.py
"""
import glob, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RES = os.path.join(ROOT, "results", "WP9", "B2")
LABELS = {"D10o": "CICIDS2017, original labels", "D10e": "CICIDS2017, corrected labels (Engelen 2021)", "D23x": "CSE-CIC-IDS2018, corrected (Liu 2022)", "D23o": "CSE-CIC-IDS2018, original labels"}
PROTO = {"T": "time block", "G": "5-tuple group", "B": "5-min block group"}


def f(x, n=3):
    return "-" if x is None else ("%.*f" % (n, x))


def ci(c, n=3):
    return "[%s, %s]" % (f(c[0], n), f(c[1], n)) if c and c[0] is not None else "-"


def main():
    rows, per = [], {}
    for p in sorted(glob.glob(os.path.join(RES, "*_test.json"))):
        t = json.load(open(p))
        k = os.path.basename(p)[:-10]
        tab, proto = k.split("_")
        sel = json.load(open(os.path.join(RES, k + "_select.json")))
        ctl = json.load(open(os.path.join(RES, k + "_control.json")))
        top = list(t["importance_top10"].items())[0]
        rows.append({"table": tab, "protocol": proto, "model": t["cand"]["id"], "macro_f1": t["macro_f1"], "macro_f1_ci": t["macro_f1_ci"], "macro_f1_all_present": t["macro_f1_all_present_classes"],
                     "fpr": t["fpr"], "fpr_ci": t["fpr_ci"], "auc": t["auc_binary"], "auc_ci": t["auc_binary_ci"], "det1": t["detection_at_val_1pct"], "det1_ci": t["detection_at_val_1pct_ci"],
                     "fpr1": t["fpr_at_val_1pct"], "accuracy": t["accuracy"], "n_eligible": len(t["eligible"]), "val_macro_f1": sel["val"][t["cand"]["id"]]["macro_f1"],
                     "control_pass": ctl["pass"], "control_auc_max": max(r["auc_binary"] for r in ctl["runs"]), "control_f1_mean": sum(r["macro_f1"] for r in ctl["runs"]) / len(ctl["runs"]),
                     "top_feature": top, "test_rows": t["test_rows"]})
        per[k] = {"eligible": t["eligible"], "not_eligible": t["not_eligible"], "unseen": t["unseen_test_classes_dropped"], "per_class": t["per_class"]}
    json.dump({"rows": rows, "per_class": per}, open(os.path.join(ROOT, "results", "WP9", "B2_summary.json"), "w"), indent=1)
    L = ["# WP9 B2 generated tables (tools/WP9_B2_tables.py from results/WP9/B2/*_test.json)", "",
         "Seen attack types, standard dataset. macro-F1 over eligible classes (>= 20 flows in train and test); CI = cluster bootstrap over 10-min test blocks.", "",
         "| dataset / labels | protocol | model | test flows | classes | macro-F1 [95% CI] | macro-F1 all present | FPR [CI] | AUC [CI] | det @ val 1% FA [CI] | acc | val macro-F1 | control | top feature (share) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %s | %d | %d | %s %s | %s | %s %s | %s %s | %s %s | %s | %s | %s | %s (%.2f) |" % (
            LABELS.get(r["table"], r["table"]), PROTO[r["protocol"]], r["model"], r["test_rows"], r["n_eligible"], f(r["macro_f1"]), ci(r["macro_f1_ci"]), f(r["macro_f1_all_present"]),
            f(r["fpr"], 4), ci(r["fpr_ci"], 4), f(r["auc"], 4), ci(r["auc_ci"], 4), f(r["det1"]), ci(r["det1_ci"]), f(r["accuracy"], 4), f(r["val_macro_f1"]),
            "pass (AUC<=%.2f, F1 %.2f)" % (r["control_auc_max"], r["control_f1_mean"]) if r["control_pass"] else "FAIL (AUC %.2f, F1 %.2f)" % (r["control_auc_max"], r["control_f1_mean"]),
            r["top_feature"][0], r["top_feature"][1]))
    for k, v in per.items():
        L += ["", "## per class %s (recall [CI], support; * = not in the macro mean)" % k, "", "| class | support | recall [CI] | precision | F1 | det @ 1% FA | AUC vs benign |", "|---|---|---|---|---|---|---|"]
        for c, m in v["per_class"].items():
            L.append("| %s%s | %d | %s %s | %s | %s | %s | %s |" % (c, "" if m["eligible"] else " *", m["support"], f(m["recall"]), ci(m["recall_ci"]), f(m["precision"]), f(m["f1"]), f(m["det_at_1pct_fa"]), f(m["auc_vs_benign"], 4)))
        if v["unseen"]:
            L.append("")
            L.append("Test flows of classes absent from train (dropped from metrics): %s" % v["unseen"])
    open(os.path.join(ROOT, "results", "WP9", "B2_tables.md"), "w").write("\n".join(L) + "\n")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
