"""WP5 S4: compact tables for the step report, generated from results/WP5/s4_summary.json, s4_tampa.json, s4_diag.json (no hand-typed numbers).
Run from codes_v3/: python -I tools/WP5_S4_report.py   Output: results/WP5/s4_report_tables.md
"""
import json
from pathlib import Path

R = Path(__file__).resolve().parent.parent / "results" / "WP5"
S = json.loads((R / "s4_summary.json").read_text())
TJ = json.loads((R / "s4_tampa.json").read_text())
VJ = json.loads((R / "s4_veremi.json").read_text())
D = json.loads((R / "s4_diag.json").read_text())
f = lambda x: "-" if x is None else f"{100 * x:.1f}%"
out = []


def percls(ds, cols, title, note=""):
    s = S[ds]["by_class"]
    classes = list(s[cols[0]].keys())
    lines = [f"**{title}**", "", note, "", "| class | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for c in classes:
        lines.append(f"| {c}{' *' if c[:2] in ('06', '12', '17') else ''} | " + " | ".join(f(s[k][c]["msg_detection"]) for k in cols) + " |")
    md = S[ds]["mean_detection_19_classes"]
    lines.append("| mean over the 19 classes | " + " | ".join(f(md[k]) for k in cols) + " |")
    return "\n".join(lines) + "\n"


for ds, nm in (("veremi", "VeReMi (primary)"), ("tampa", "Tampa (illustration: 3 test vehicles, 2 attackers per type)")):
    s = S[ds]
    nf = s["noise_fit"]
    out.append(f"### {nm}\n")
    out.append(f"**Noise fit** (genuine TRAIN only): sp = {nf['params']['sp']:.3f} m, sv = {nf['params']['sv']:.3f} m/s, sa = {nf['params']['sa']:.3f} m/s^2/sqrt(s); "
               f"{nf['n_tracks']} tracks, {nf['n_messages']} messages, {nf['n_senders_used']} senders; neg. log-lik/message {nf['neg_loglik_per_message']:.3f}; "
               f"floors SP_MIN 0.05, SV_MIN 0.02 (a value equal to a floor means the data wanted less).\n")
    lines = ["**Filter consistency on genuine data** (NIS, dim 4: expected mean 4, median 3.36, above chi2 95% = 5%, below chi2 5% = 5%)", "",
             "| set | n scored | NIS mean | NIS median | above 95% | below 5% | q99 (chi2: 13.3) |", "|---|---|---|---|---|---|---|"]
    for part, key in (("val", "consistency_val_genuine"), ("test", "consistency_test_genuine")):
        for sub in ("all_genuine", "moving_ge_3mps", "slow_lt_3mps"):
            c = s[key][sub]
            lines.append(f"| {part} {sub} | {c['n']} | {c['nis_mean']:.2f} | {c['nis_median']:.3f} | {f(c['frac_above_chi2_95'])} | {f(c['frac_below_chi2_05'])} | {c['q99']:.1f} |")
    out.append("\n".join(lines) + "\n")
    cols = ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.kf_cusum_lo", "v2x.track_birth", "L3_union", "L1_and_L2_union", "L1_L2_L3_union", "combined_L1+L2", "combined_L1+L2+L3"]
    out.append(percls(ds, cols, f"{nm}: message-level detection at 1% validation budget, per class",
                      "L3_union = max of the 4 calibrated L3 scores at one 1% budget; L1_and_L2_union = S3 deployable union; L1_L2_L3_union = L1 operating points OR (L2 + L3 at one budget); combined_* = harness combiner. * = held out."))
    ks = ["L2_union", "L3_union", "L1_and_L2_union", "L1_L2_L3_union"]
    lines = [f"**{nm}: sender level, attackers with >= 3 alarms** (genuine senders with >= 3 alarms in the last row)", "",
             "| class | " + " | ".join(ks) + " |", "|---|" + "---|" * len(ks)]
    s3 = s["sender_ge3_alarms"]
    for c in s3["L3_union"]["by_class"]:
        lines.append(f"| {c} | " + " | ".join(f(s3[k]["by_class"].get(c)) for k in ks) + " |")
    lines.append("| genuine senders >= 3 alarms | " + " | ".join(f(s3[k]["false_alarm_genuine_senders"]) for k in ks) + " |")
    out.append("\n".join(lines) + "\n")
    po = s["per_operating_point"]
    lines = [f"**{nm}: false alarms on genuine TEST messages** (budget on validation 1%)", "", "| operating point | genuine test messages | genuine senders >= 1 alarm |", "|---|---|---|"]
    for k in ["v2x.kf_nis", "v2x.kf_cusum_hi", "v2x.kf_cusum_lo", "v2x.track_birth", "L3_kf_union", "L3_union", "L2_union", "L1_and_L2_union", "L1_L2_L3_union", "combined_L1+L2", "combined_L1+L2+L3"]:
        lines.append(f"| {k} | {f(po[k]['false_alarm_messages'])} | {f(po[k]['false_alarm_genuine_senders'])} |")
    out.append("\n".join(lines) + "\n")
    if s["birth"]:
        b = s["birth"]
        out.append(f"track_birth false alarms per genuine birth (first message of a genuine track): val {f(b['val_FA_per_genuine_birth'])} of {b['n_val_genuine_births']}, test {f(b['test_FA_per_genuine_birth'])} of {b['n_test_genuine_births']}.\n")
    lines = [f"**{nm}: harness group ablation** (combiner chosen on validation per group)", "", "| group | method | AUC | detection (all attacks) | false alarms |", "|---|---|---|---|---|"]
    for k, r in s["groups"].items():
        lines.append(f"| {k} | {r['method']} | {r['auc']:.3f} | {f(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% |")
    out.append("\n".join(lines) + "\n")
    J = VJ if ds == "veremi" else TJ
    lines = [f"**{nm}: harness, each layer alone and all-but-one (AUC / detection / false alarms)**", "", "| configuration | AUC | detection | false alarms |", "|---|---|---|---|"]
    for k, r in J["ablation"].items():
        if k.startswith("only_v2x.kf") or k.startswith("only_v2x.track") or k.startswith("all_but_v2x.kf") or k.startswith("all_but_v2x.track") or k == "all":
            lines.append(f"| {k} | {r['auc']:.3f} | {f(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% |")
    out.append("\n".join(lines) + "\n")
v = S["veremi"]["track_length_attack_test"]
lines = ["**VeReMi test: track length of the attackers** (why the tracker cannot see classes 17 / 18 / 19)", "", "| class | median messages per track | tracks with one message |", "|---|---|---|"]
for c in ("16_GridSybil", "17_DataReplaySybil", "18_DoSRandomSybil", "19_DoSDisruptiveSybil", "12_DelayedMessages", "09_EventualStop"):
    lines.append(f"| {c} | {v[c]['median_messages_per_track']:.0f} | {f(v[c]['frac_tracks_one_message'])} |")
out.append("\n".join(lines) + "\n")
d = D["per_class"]
lines = ["**Diagnostics on VeReMi VALIDATION** (tools/WP5_S4_diag.py)", "", "| class | cusum_hi alarm (val q99 of genuine) | alarms whose own NIS is below chi2 95% (memory of an earlier jump) | messages with own NIS above chi2 95% |", "|---|---|---|---|"]
for c, r in d.items():
    lines.append(f"| {c} | {f(r['frac_cusum_hi_alarm'])} | {f(r['frac_of_alarms_with_own_nis_below_K_HI'])} | {f(r['frac_nis_above_K_HI'])} |")
out.append("\n".join(lines) + "\n")
out.append(f"Class 12 as it appears in the CSV: {f(d['12_DelayedMessages']['frac_messages_at_origin_00'])} of the messages are exactly (0, 0) with speed 0, {f(d['12_DelayedMessages']['frac_tracks_origin_then_real'])} of the tracks go from the origin to real positions.\n")
g, e = D["genuine_standstill_pairs"], D["eventual_stop_standstill_pairs"]
out.append(f"Standstill pairs on VeReMi val: genuine {f(g['frac_displacement_exactly_zero'])} have an exactly repeated position (median displacement {g['median_displacement_m']:.2f} m); EventualStop {f(e['frac_displacement_exactly_zero'])}.\n")
(R / "s4_report_tables.md").write_text("\n".join(out))
print("ok", len("\n".join(out)))
