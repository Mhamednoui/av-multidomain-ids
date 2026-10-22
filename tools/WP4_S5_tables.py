"""WP4 S5 tables: results/WP4/s5_tables.md and s5_acceptance.json from s5_dev_val.json, s5_d10.json, s5_d23.json (verdict run). Usage: python tools/WP4_S5_tables.py"""
import json
import os

import numpy as np

RES = os.path.join(os.path.dirname(__file__), "..", "results", "WP4")
N3 = ["net.l3_service", "net.l3_iforest", "net.l3_ae"]
EVAL10 = ["Bot", "DDoS-LOIC-HTTP", "DoS-GoldenEye", "DoS-Hulk", "DoS-SlowHTTPTest", "DoS-Slowloris", "FTP-Patator", "SSH-Patator", "PortScan", "Web-BruteForce", "Web-XSS"]
BLIND = ["Bot", "Web-XSS", "Web-BruteForce", "DoS-Slowloris"]
out = []


def J(n):
    return json.load(open(os.path.join(RES, n)))


def P(x):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else "%.1f" % (100 * x)


def table(head, rows):
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "---|" * len(head))
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    out.append("")


def short(n):
    return n.split("_")[1]


dev, d10, d23 = J("s5_dev_val.json"), J("s5_d10.json"), J("s5_d23.json")
L = d10["layers_clean"]
out.append("# WP4 S5 tables (all numbers from results/WP4/s5_*.json; detection in %, 1% tie-safe budget on benign validation unless stated)\n")
out.append("## 1. Selection grid on validation (D10; blind4 = mean over Bot, Web-XSS, Web-BruteForce, Slowloris; macro = 11 evaluable families)")
table(["layer", "params", "blind4", "macro", "macro AUC", "Bot AUC", "Web-XSS AUC", "Web-BF AUC", "Slowloris det"],
      [[g["layer"], json.dumps(g["params"]), P(g["blind4"]), P(g["macro"]), "%.3f" % g["macro_auc"], "%.2f" % g["auc"]["Bot"], "%.2f" % g["auc"]["Web-XSS"],
        "%.2f" % g["auc"]["Web-BruteForce"], P(g["detection"]["DoS-Slowloris"])] for g in dev["grid"]])
out.append("Chosen: " + json.dumps(dev["chosen"]) + "\n")
fams = d10["families"]
out.append("## 2. D10 test, per layer (flow unit, clean features). n = test flows")
table(["family", "n"] + [short(n) + " det" for n in N3] + [short(n) + " AUC" for n in N3],
      [[f, L[N3[0]]["n"].get(f)] + [P(L[n]["detection"].get(f)) for n in N3] + [P(L[n]["auc_by_family"].get(f)) for n in N3] for f in fams])
table(["layer", "FA benign test (headline)", "FA published labels", "FA on audited file (%)", "macro 11", "blind4", "macro AUC", "FA at the 5% budget", "epochs"],
      [[n, "%.2f%%" % (100 * L[n]["fa_benign"]), "%.2f%%" % (100 * L[n]["fa_benign_published_labels"]), P(L[n]["fa_benign_audit_file"]), P(L[n]["summary"]["macro"]),
        P(L[n]["summary"]["blind4"]), "%.3f" % L[n]["summary"]["macro_auc"], "%.2f%%" % (100 * L[n]["at_fa5"]["fa_benign"]), L[n]["epochs"]] for n in N3])
out.append("### 2b. Diagnostics: detection at a 5% budget, and median benign-rank of each family (1.0 = above every benign flow)")
fl = [f for f in fams if f in L[N3[0]]["at_fa5"]["detection"]]
table(["family"] + [short(n) + " det@5%" for n in N3] + [short(n) + " rank" for n in N3],
      [[f] + [P(L[n]["at_fa5"]["detection"].get(f)) for n in N3] + ["%.2f" % L[n]["rank_median_of_family_among_benign"][f] for n in N3] for f in fl])
out.append("### 2c. Detection on the flows that survive de-duplication / on all pre-dedup flows")
table(["family"] + [short(n) for n in N3],
      [[f] + ["%s / %s" % (P(L[n]["detection_dedup_subset"].get(f)), P(L[n]["detection"].get(f))) for n in N3] for f in fams if f in L[N3[0]]["detection_dedup_subset"]])
out.append("## 3. Hygiene: clean vs all 76 columns, D10 test")
A = d10["layers_all"]
table(["layer", "FA clean", "FA all", "macro clean", "macro all", "blind4 clean", "blind4 all", "macro AUC clean", "macro AUC all"],
      [[n, "%.2f" % (100 * L[n]["fa_benign"]), "%.2f" % (100 * A[n]["fa_benign"]), P(L[n]["summary"]["macro"]), P(A[n]["summary"]["macro"]), P(L[n]["summary"]["blind4"]),
        P(A[n]["summary"]["blind4"]), "%.3f" % L[n]["summary"]["macro_auc"], "%.3f" % A[n]["summary"]["macro_auc"]] for n in N3])
out.append("## 4. Harness ablation (tcp_flags + L2a + L3, logistic combiner, subsample as S3 / S4), D10 test")
h = d10["harness"]
cfg = ["base", "base_svc", "base_if", "base_ae", "base_l3", "l3_only"]
table(["configuration", "combined FA", "detection (all attack flows)", "macro 11", "blind4"] + EVAL10,
      [[c, "%.2f%%" % (100 * h[c]["combined"]["false_alarm_rate"]), P(h[c]["combined"]["detection"]), P(h[c]["macro11"]), P(h[c]["blind4"])] +
       [P(h[c]["combined"]["detection_by_attack"].get(f)) for f in EVAL10] for c in cfg])
out.append("Ablation inside base_l3 (each layer alone / all but one): results/WP4/s5_d10_base_l3.md.\n")
out.append("OR view (any layer alarms; the 1% budgets add up):")
table(["view", "FA benign", "FA published"] + EVAL10, [[k, "%.2f%%" % (100 * v["fa_benign"]), "%.2f%%" % (100 * v["fa_benign_published_labels"])] + [P(v["detection"].get(f)) for f in EVAL10]
                                                     for k, v in d10["or_view"].items()])
out.append("## 5. Bot: is a hit the fixed flow signature?")
b = d10["bot"]
s = b["signature"]
out.append("Signature from Bot TRAIN flows to port 8080: %g fwd / %g bwd packets, duration %.0f-%.0f us; %.1f%% of the %d train flows to 8080; shapes %s.\n" % (
    s["fwd_pkts"], s["bwd_pkts"], s["duration_us_p5_p95"][0], s["duration_us_p5_p95"][1], 100 * s["share_of_bot_train_8080_flows"], s["n_bot_train_8080"], s["bot_train_pairs_top5"]))
t = b["test"]
out.append("Test: %d Bot flows, %d match the signature (shape + port 8080), %d go to port 8080; benign flows matching the signature: %d of %d (shape on any port: %d); benign share on port 8080: %.2f%%.\n" % (
    t["n_bot"], t["bot_match_signature"], t["bot_port_8080"], t["benign_match_signature"], t["n_benign"], t["benign_match_shape_any_port"], 100 * t["benign_port_8080_share"]))
table(["layer", "Bot det", "alarms", "alarms matching signature", "det on matching", "det on non-matching", "FA of benign matching signature", "median benign-rank of Bot"],
      [[n, P(t["layers"][n]["bot_detection"]), t["layers"][n]["bot_alarms"], t["layers"][n]["bot_alarms_matching_signature"], P(t["layers"][n]["detection_signature_matching"]),
        P(t["layers"][n]["detection_not_matching"]), P(t["layers"][n]["fa_benign_matching_signature"]), "%.2f" % t["layers"][n]["bot_score_rank_median"]] for n in N3])
bs = d23["bot_signature_in_d23"]
out.append("D23 sample (test side): %d Bot flows; same shape %d, shape and port 8080 %d; benign with shape and port 8080: %d; Bot destination ports %s.\n" % (
    bs["n_bot"], bs["bot_match_shape"], bs["bot_match_shape_port8080"], bs["benign_match_shape_port8080"], bs["bot_port_counts_top3"]))
out.append("## 6. Feature attributions (top-5 features by mean share of the positive score contribution; top 200 alarmed flows per group; D10 test)")
for n in N3:
    out.append("### " + n)
    table(["group", "flows", "top features (share)"], [[g, v["n_flows"], "; ".join("%s %.2f" % (a, sh) for a, sh in v["top"])] for g, v in d10["attribution"][n].items()])
out.append("### Ports of the benign false alarms (D10 test)")
table(["layer", "false alarms", "top ports (share)"], [[n, v["n_false_alarms"], "; ".join("%s %.2f" % (k, sh) for k, sh in v["top_ports"].items())] for n, v in d10["benign_fa_ports"].items()])
out.append("## 7. D23 sample (test side %s): zero-shot (D10 fit and threshold), threshold re-calibrated on D23 benign validation (no refit), refit on D23 benign" % d23["test_side"])
out.append("Test sample: %d benign, attacks %s.\n" % (d23["n"]["test_benign"], d23["n"]["test_attack"]))
fam23 = sorted(d23["n"]["test_attack"])
for key, title in (("zero_shot", "zero-shot"), ("recalibrated_no_refit", "re-calibrated threshold, no refit"), ("refit", "refit on D23")):
    out.append("### " + title)
    D = d23[key]
    table(["layer", "FA benign", "macro 9", "macro 9 AUC", "benign median score / D10-or-D23 val median", "FA by day (max)"],
          [[n, "%.2f%%" % (100 * D[n]["fa_benign"]), P(D[n]["summary"]["macro9"]), "%.3f" % D[n]["summary"]["macro9_auc"], "%.2f" % D[n]["median_shift"],
            "%.1f%%" % (100 * max(D[n]["fa_by_day"].values()))] for n in N3])
    table(["family", "n"] + [short(n) + " det" for n in N3] + [short(n) + " AUC" for n in N3],
          [[f, d23["n"]["test_attack"][f]] + [P(D[n]["detection"].get(f)) for n in N3] + ["%.2f" % D[n]["auc"][f] for n in N3] for f in fam23])
open(os.path.join(RES, "s5_tables.md"), "w").write("\n".join(out))

acc = {"D1": {"fa_benign": {n: L[n]["fa_benign"] for n in N3}, "fa_published": {n: L[n]["fa_benign_published_labels"] for n in N3},
              "met": bool(all(L[n]["fa_benign"] <= 0.02 for n in N3))}}
cnt = {n: [f for f in BLIND if L[n]["detection"].get(f, 0) >= 0.5] for n in N3}
acc["D2"] = {"blind_families_at_least_50pct": cnt, "met": bool(any(len(v) >= 2 for v in cnt.values()))}
gain = h["base_l3"]["macro11"] - h["base"]["macro11"]
acc["D3"] = {"macro11_base": h["base"]["macro11"], "macro11_base_l3": h["base_l3"]["macro11"], "gain_points": 100 * gain,
             "fa_base": h["base"]["combined"]["false_alarm_rate"], "fa_base_l3": h["base_l3"]["combined"]["false_alarm_rate"],
             "met": bool(gain >= 0.05 and h["base_l3"]["combined"]["false_alarm_rate"] <= 0.02)}
bt = b["test"]["layers"]
sig_only = {n: bool(bt[n]["bot_alarms"] > 0 and bt[n]["bot_alarms_matching_signature"] / bt[n]["bot_alarms"] >= 0.9 and (bt[n]["detection_not_matching"] or 0) < 0.1) for n in N3}
acc["D4"] = {"bot_detection": {n: bt[n]["bot_detection"] for n in N3}, "signature_only": sig_only, "statement_only": True}
acc["D5"] = {"zero_shot_fa": {n: d23["zero_shot"][n]["fa_benign"] for n in N3}, "zero_shot_transferable": {n: bool(d23["zero_shot"][n]["fa_benign"] <= 0.05) for n in N3},
             "refit_fa": {n: d23["refit"][n]["fa_benign"] for n in N3}, "refit_fa_met": bool(all(d23["refit"][n]["fa_benign"] <= 0.02 for n in N3))}
acc["D6"] = {"clean_vs_all_macro": {n: [L[n]["summary"]["macro"], A[n]["summary"]["macro"]] for n in N3}}
json.dump(acc, open(os.path.join(RES, "s5_acceptance.json"), "w"), indent=1)
print(json.dumps(acc, indent=1))
