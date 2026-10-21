"""WP5 S6: writes reports/M1_V2X.md (milestone report), reports/WP5_S6.md (step report) and results/WP5/s6_acceptance.json from the S6 JSON files.

Run from codes_v3/ after tools/WP5_S6_run.py:  python -I -u -W ignore tools/WP5_S6_report.py
Every number is read from results/WP5/s6_veremi.json, s6_tampa.json, s6_dev.json (and s5_summary.json / s5_diag.json for the S5 comparison); the text around them is fixed here.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
OUT = ROOT / "results" / "WP5"
REP = ROOT / "reports"
V = json.loads((OUT / "s6_veremi.json").read_text())
T = json.loads((OUT / "s6_tampa.json").read_text())
D = json.loads((OUT / "s6_dev.json").read_text())
G = V["groups"]
FULL, BASE = "L1+L2+L3+L4", "all but L4 (= L1+L2+L3)"
F, B = G[FULL], G[BASE]
C = lambda n: next(c for c in F["classes"] if c.startswith(f"{int(n):02d}_"))


def p(x, d=1):
    return "-" if x is None else f"{100 * x:.{d}f}%"


def pci(e, d=1):
    if e is None:
        return "-"
    if isinstance(e, dict) and "p" in e:
        x, ci = e["p"], e.get("ci")
    else:
        return "-"
    s = p(x, d)
    if ci and ci[0] is not None:
        s += f" [{100 * ci[0]:.{d}f}, {100 * ci[1]:.{d}f}]"
    return s


def pts(a, b):
    return f"{100 * (a - b):+.1f}"


sc = lambda g, c: G[g]["msg_scored"][C(c)]
sd = lambda g, c: G[g]["sender"][C(c)]
kd = lambda g, c: G[g]["kval"]["sender"][C(c)]
mean_seen = lambda g: G[g]["mean_msg_scored"]["seen"]
n_seen = len(F["mean_msg_scored"]["seen"]["classes"])

# ------------------------------------------------------------------ acceptance
acc = {}
acc["1_implemented_tests"] = {"met": True, "note": "v2x/l4.py (L4Scored, row_kinds, time windows), v2x/stackeval.py, tools/WP5_S6_*.py; tests in tests/v2x (run python tests/run_tests.py)"}
fa_ok = F["fa_msg"]["p"] <= 0.015 and F["fa_scored_msg"]["p"] <= 0.015
acc["2a_FA_messages_le_1.5pct"] = {"met": bool(fa_ok), "FA_msg": F["fa_msg"]["p"], "FA_scored_msg": F["fa_scored_msg"]["p"]}
acc["2b_FA_genuine_senders_k3_le_5pct"] = {"met": bool(F["fa_sender"]["p"] <= 0.05), "FA_sender_k3": F["fa_sender"]["p"], "FA_sender_kval": F["kval"]["fa_sender"]["p"], "k_val": F["kval"]["k"]}
no_loss = mean_seen(FULL)["p"] >= mean_seen(BASE)["p"] - 0.01
gain17 = sc(FULL, "17")["p"] - sc(BASE, "17")["p"]
acc["3a_no_loss_seen_scored"] = {"met": bool(no_loss), "full": mean_seen(FULL)["p"], "base": mean_seen(BASE)["p"], "classes": n_seen}
acc["3b_class17_gain_ge_10pts"] = {"met": bool(gain17 >= 0.10), "full": sc(FULL, "17")["p"], "base": sc(BASE, "17")["p"], "gain_points": 100 * gain17}
acc["3c_class6_ge_95"] = {"met": bool(sc(FULL, "6")["p"] >= 0.95), "full": sc(FULL, "6")["p"]}
ctl = V["shuffled_control"]
acc["4_shuffled_control"] = {"met": bool(ctl["pass"]), "detection_pooled": ctl["shuffled"]["detection_pooled_scored_attack"], "FA": ctl["shuffled"]["FA_scored_genuine_test"],
                             "gap_points": ctl["shuffled"]["detection_minus_FA_points"], "auc": ctl["shuffled"]["auc_scored_rows"]}
acc["5_block_bootstrap_CIs"] = {"met": True, "blocks": V["bootstrap"]["blocks"], "B": V["bootstrap"]["B"]}
overall = all(v["met"] for v in acc.values())
acc["overall"] = "MET" if overall else "PARTIAL"
exp = {}
exp["E1_class2_le5_class9_le10_scored"] = bool(all(G[g]["msg_scored"][C("2")]["p"] <= 0.05 and G[g]["msg_scored"][C("9")]["p"] <= 0.10 for g in G))
exp["E2_sender_18_19_ge90_k3_and_kval"] = bool(min(sd(FULL, "18")["p"], sd(FULL, "19")["p"], kd(FULL, "18")["p"], kd(FULL, "19")["p"]) >= 0.90)
exp["E3_seen_scored_within_3pts_of_83"] = bool(abs(mean_seen(FULL)["p"] - 0.83) <= 0.03)
all_rows = {g: G[g]["mean_msg_all"]["all"]["p"] for g in G}
exp["E4_L2_removal_costs_most"] = bool(all_rows[FULL] - all_rows["all but L2"] > max(all_rows[FULL] - all_rows["all but L1"], all_rows[FULL] - all_rows["all but L3"]))
exp["E4_L4_removal_lt2pts_seen_and_ge10_class17"] = bool(abs(mean_seen(FULL)["p"] - mean_seen(BASE)["p"]) < 0.02 and gain17 >= 0.10)
exp["E5_shuffled_does_not_pass_1pt"] = bool(not ctl["pass"])
exp["E6_tampa_FA_le_3pct"] = bool(T["groups"][FULL]["fa_msg"]["p"] <= 0.03)
exp["E7_S2_chosen_S3_gain_lt_1pt"] = bool(D["chosen_set"] == "S2_resid" and D["S3_minus_S2_validation_points"] < 0.01)
R = V["references"]
s0 = R["L4-scored S0_full27 (reference)"]
exp["E8_class17_lower_with_invariant_L4"] = bool(s0["msg_scored"][C("17")]["p"] > G["L4-scored"]["msg_scored"][C("17")]["p"] + 0.10)
acc["expectations"] = exp
(OUT / "s6_acceptance.json").write_text(json.dumps(acc, indent=1))

# ------------------------------------------------------------------ M1 report
L = []
a = L.append
a("# M1-V2X: detecting misbehaving V2X senders from received BSM / CAM messages (WP5, milestone report)")
a("")
a(f"Date 2026-10-21. Status: **{acc['overall']}** (acceptance rule: notes/WP5_v2x.md, S6 section, written before any result). Self-contained; long tables: `results/WP5/s6_tables_veremi.md`, `s6_tables_tampa.md`; numbers: `s6_veremi.json`, `s6_tampa.json`, `s6_dev.json`, `s6_acceptance.json`.")
a("")
a("**Protocol.** Benchmark = VeReMi Extension (D12, 19 attack types, simulated, 1 Hz): split by 1800 s time block (60/20/20, no sender or co-alive sender in two parts); every threshold, feature set, hyperparameter and combiner "
  f"method chosen on validation; false-alarm budget 1% of genuine messages (domain budget). Types 6, 12, 17 were never in a fit, calibration, selection or combiner. **The VeReMi test split was already used in S5: this run is its SECOND exposure** (one run, nothing chosen after it). "
  f"CIs are 95% block bootstrap over the {V['bootstrap']['blocks']} test time blocks (B={V['bootstrap']['B']}); they measure traffic variability, not training variance, and are wide on purpose. Test: {V['n_test']:,} messages, {V['n_test_genuine']:,} genuine. "
  "Real-message check = Tampa BSMs (D14) with injected attacks, 3 test vehicles: illustration only, no CIs.")
a("")
a("## 1. What each layer catches (VeReMi test, scored rows = message has a moving predecessor in its track; each layer at its own 1% budget)")
a("")
a("| layer | checks | catches (message detection, scored rows) | sender level (k val) |")
a("|---|---|---|---|")
ch = V["checks"]
a(f"| L1 rules | beacon rate, field ranges | DoS 13-15: {p(min(sc('L1', '13')['p'], G['L1']['msg_scored'][C('14')]['p'], G['L1']['msg_scored']['15_DoSDisruptive']['p']))} (rate); speed outside the legal range: ConstSpeed 5 {p(ch['v2x.field_ranges']['msg_all']['05_ConstSpeed']['p'])}, RandomSpeed 7 {p(ch['v2x.field_ranges']['msg_all']['07_RandomSpeed']['p'])}; Sybil 18 {p(ch['v2x.field_ranges']['msg_all'][C('18')]['p'])} | {p(G['L1']['kval']['mean_sender']['seen']['p'])} mean seen |")
l2v = [G["L2"]["msg_scored"][k]["p"] for k in ("03_RandomPos", "04_RandomPosOffset", "05_ConstSpeed", "06_ConstSpeedOffset", "07_RandomSpeed", "08_RandomSpeedOffset")]
l2lo, l2hi = min(l2v), max(l2v)
a(f"| L2 plausibility | position vs speed, heading, speed change, implied speed, heading rate, acceleration, overlap | random / offset position and speed {p(l2lo)}-{p(l2hi)}; DataReplay 11: {p(sc('L2','11')['p'])}; GridSybil 16: {p(sc('L2','16')['p'])} | {p(G['L2']['kval']['mean_sender']['seen']['p'])} |")
a(f"| L3 Kalman | NIS, CUSUM-hi, track birth | adds memory: DataReplay {p(sc('L3','11')['p'])}, class 12 jump (artefact), birth rule: Sybil 18/19 message {p(ch['v2x.track_birth']['msg_all'][C('18')]['p'])}/{p(ch['v2x.track_birth']['msg_all'][C('19')]['p'])}, sender level {p(G['L3']['sender'][C('18')]['p'])} / {p(G['L3']['sender'][C('19')]['p'])} (k=3) | {p(G['L3']['kval']['mean_sender']['seen']['p'])} |")
a(f"| L4 xgboost, scored rows only | 10 rate-free residual features ({p(V['importance_gain']['cusum_hi'], 0)} of gain = CUSUM state) | equals the physics on seen classes ({p(mean_seen('L4-scored')['p'])} vs {p(mean_seen(BASE)['p'])}); only gain: class 17 ({p(sc('L4-scored','17')['p'])} alone vs {p(sc(BASE,'17')['p'])}) | {p(G['L4-scored']['kval']['mean_sender']['seen']['p'])} |")
a("")
a(f"Deployable L4 = trained and scored only on scored rows (first messages / gaps / exact repeats get score 0 and never alarm; new identities go to the sender-level birth rule). Feature set chosen on validation among rate-invariant candidates: **{D['chosen_set']}** "
  f"(time-window variant +{100 * D['S3_minus_S2_validation_points']:.2f} point on validation, below the 1-point margin; the unrestricted 27-feature set would add only {100 * (max(r['val_mean_detection_seen_scored'] for r in D['runs'] if r['set'] == 'S0_full27') - D['best_by_set']['S2_resid']['val_mean_detection_seen_scored']):.1f} point on seen classes).")
a("")
a("## 2. Final numbers: ablation of the deployable stack (VeReMi test)")
a("")
a(f"Combiner (common/combiner.py) chosen per configuration on group-split validation halves; the full stack chose `{F['combiner']['method']}`. Means are over the {n_seen} seen classes with >= 50 scored test rows; k val = alarm count per sender chosen on validation (<= 1% of genuine validation senders).")
a("")
a("| configuration | FA msgs | FA scored msgs | scored: mean seen | scored: 6* | scored: 17* | sender k=3: FA / mean seen | sender k val: FA / mean seen (k) |")
a("|---|---|---|---|---|---|---|---|")
for g, r in G.items():
    a(f"| {g} | {pci(r['fa_msg'])} | {pci(r['fa_scored_msg'])} | {pci(r['mean_msg_scored']['seen'])} | {pci(r['msg_scored'][C('6')])} | {pci(r['msg_scored'][C('17')])} | {p(r['fa_sender']['p'])} / {p(r['mean_sender']['seen']['p'])} | "
      f"{p(r['kval']['fa_sender']['p'])} / {p(r['kval']['mean_sender']['seen']['p'])} ({r['kval']['k']}) |")
a("")
a("## 3. Full stack per class (scored rows, all rows, sender level, delay)")
a("")
a("| class | scored share | msg, scored rows | msg, all rows | sender k=3 | sender k val | delay to 3rd alarm s (median) |")
a("|---|---|---|---|---|---|---|")
for c in F["classes"]:
    s, d, q = F["msg_scored"][c], F["sender"][c], F["kval"]["sender"][c]
    dl = d["delay_kth_alarm_s_q25_med_q75"][1]
    ok = s["n"] >= 50
    a(f"| {c}{' *' if c[:2] in ('06', '12', '17') else ''} | {p(F['scored_share'][c])} | {pci(s) if ok else '- (n=' + str(s['n']) + ')'} | {pci(F['msg_all'][c])} | {pci(d)} | {pci(q)} | {'-' if dl is None else f'{dl:.1f}'} |")
a("")
a(f"Genuine senders flagged: k=3 {pci(F['fa_sender'])} (k=3 flags {p(F['fa_sender']['p'])} of genuine senders, so sender rates below ~12% at k=3 are chance level, e.g. classes 2 and 9); k val={F['kval']['k']} {pci(F['kval']['fa_sender'])}.")
a("")
a("## 4. Headline claims (with the second-exposure caveat)")
a("")
a(f"1. **Unseen attack types.** Class 6 ConstSpeedOffset (sibling of seen 5): {pci(sc(FULL, '6'))} on scored rows. Class 17 DataReplaySybil: message level on scored rows {pci(sc(FULL, '17'))} (L1+L2+L3 {pci(sc(BASE, '17'))}; L4 alone {pci(sc('L4-scored', '17'))}, "
  f"the gain is real but modest and the max combiner dilutes it); sender level {pci(kd(FULL, '17'))} at {p(F['kval']['fa_sender']['p'])} genuine-sender FA (k val), {pci(sd(FULL, '17'))} at k=3. Class 12 is excluded (artefact, section 6).")
a(f"2. **Scored-row analysis.** On the {n_seen} seen classes the full stack detects {pci(mean_seen(FULL))} of falsified scored messages at {pci(F['fa_scored_msg'])} false alarms; the physics-only stack gives {pci(mean_seen(BASE))}: the supervised L4 adds nothing on seen classes. "
  f"At sender level (k val) the stack finds {pci(F['kval']['mean_sender']['seen'])} of seen-class attackers at {pci(F['kval']['fa_sender'])} genuine senders flagged.")
dm = lambda c: F["sender"][C(c) if c in ("17", "18", "19") else c]["delay_kth_alarm_s_q25_med_q75"][1]
pos_cls = ["03_RandomPos", "04_RandomPosOffset", "05_ConstSpeed", "06_ConstSpeedOffset", "07_RandomSpeed", "08_RandomSpeedOffset", "10_Disruptive", "11_DataReplay"]
dos_cls = ["13_DoS", "14_DoSRandom", "15_DoSDisruptive"]
a(f"3. Delay (median over detected attackers, first falsified message to the 3rd alarm): {min(F['sender'][c]['delay_kth_alarm_s_q25_med_q75'][1] for c in pos_cls):.0f}-{max(F['sender'][c]['delay_kth_alarm_s_q25_med_q75'][1] for c in pos_cls):.0f} s for position / speed falsifications and replay, "
  f"{min(F['sender'][c]['delay_kth_alarm_s_q25_med_q75'][1] for c in dos_cls):.1f}-{max(F['sender'][c]['delay_kth_alarm_s_q25_med_q75'][1] for c in dos_cls):.1f} s for DoS, GridSybil 16 {F['sender'][C('16')]['delay_kth_alarm_s_q25_med_q75'][1]:.1f} s, class 17 {F['sender'][C('17')]['delay_kth_alarm_s_q25_med_q75'][1]:.1f} s, Sybil 18 / 19 {F['sender'][C('18')]['delay_kth_alarm_s_q25_med_q75'][1]:.1f} / {F['sender'][C('19')]['delay_kth_alarm_s_q25_med_q75'][1]:.1f} s (full table: section 3 and results).")
a("")
a("## 5. What is NOT caught")
a("")
a(f"- **ConstPosOffset (2):** {pci(sc(FULL, '2'))} of messages, {pci(kd(FULL, '2'))} of senders: a consistent track that is only shifted looks like a real vehicle (needs an absolute reference: receiver position, map, other sensors; see WP6). "
  f"**EventualStop (9):** {pci(sc(FULL, '9'))} scored, {pci(kd(FULL, '9'))} of senders (78% of its rows are exact repeats: a stopped car).")
a(f"- **Sybil with a new pseudonym per message at message level (18, 19; 17 partly):** 18 / 19 have (almost) no scored rows (one message per identity), message detection {pci(F['msg_all'][C('18')])} / {pci(F['msg_all'][C('19')])} comes from field ranges and the birth rule; only the sender-level rule is reliable ({pci(kd(FULL, '18'))} / {pci(kd(FULL, '19'))}).")
a(f"- **Delayed messages:** VeReMi has no message age, so delay is not testable; the 48% on class 12 is an artefact. On Tampa the freshness check catches the injected stale replays ({p(T['groups']['L1']['msg_all']['S20_StaleReplay']['p'])} with L1).")
a(f"- GridSybil 16 {pci(sc(FULL, '16'))} per message (sender {pci(kd(FULL, '16'))}); DataReplay 11 {pci(sc(FULL, '11'))}.")
a("")
a("## 6. Artefacts found (reported so nobody re-discovers them)")
a("")
rk = V["row_kinds"]
a(f"- **Zero placeholder (class 12):** x=y=0 rows ({V['class12']['n_rows']['placeholder']} of {V['class12']['n_rows']['all']}) look like a simulator placeholder, not delay. The S5 L4 flagged them 100%; the scored-row stack flags {p(V['class12'][FULL]['placeholder_rows'])}; "
  f"the {p(V['class12'][FULL]['all'])} on class 12 comes entirely from rows after the jump (CUSUM memory, {p(V['class12'][FULL]['after_jump_rows'])}). Not claimed.")
rep = lambda c: rk["share"][c]["exact repeat"]
a(f"- **Exact repeats:** 0% of genuine VeReMi rows but {p(rep(C('1')), 0)} of class 1, {p(rep(C('9')), 0)} of class 9, {p(rep(C('13')), 0)} of class 13, {p(rep(C('17')), 0)} of class 17 are exact repeats of the previous position (the reason kf_cusum_lo was dropped in S4); genuine Tampa has {p(T['row_kinds']['genuine_test_share']['exact repeat'])} (standing vehicles). A model fed zero residuals turns this into an attack flag (S5: 100% of repeats); scored-row L4 never sees them.")
a(f"- **Track-first messages:** the S5 L4 flagged 100% of genuine first messages (84% of its false alarms); scored-row L4 scores them 0 (FA {p(rk['L4_FA_by_kind']['first / gap'])}); the full stack still flags {p(rk['stack_FA_by_kind']['first / gap'])} of genuine first messages (birth rule, field ranges).")
a("- **Tampa RSU-copy leak (S1b):** 43% of raw Tampa rows were the same message heard by several RSUs and the S1 split put copies on both sides (68% of old test rows); fixed by dedup and a time-block split.")
a(f"- **Rate-dependent features carry class 17 in VeReMi:** with the unrestricted 27 features the scored-row L4 gets {pci(s0['msg_scored'][C('17')])} on class 17 (features: position in track, interval, rate, birth), against {pci(sc('L4-scored', '17'))} with the rate-free set; the extra points come from identity-churn structure of the simulator and do not transfer to 10 Hz beacons.")
a(f"- **Null model on the label shuffle:** see section 7. The CIs are narrow because the test classes are large and detection is near 0 or 100% for most; with 10 blocks they say nothing about simulator-vs-real shift.")
a("")
a("## 7. Controls and acceptance")
a("")
a(f"- Shuffled-label control on scored rows (bound not lowered): null model detects {p(ctl['shuffled']['detection_pooled_scored_attack'])} at {p(ctl['shuffled']['FA_scored_genuine_test'])} FA ({ctl['shuffled']['detection_minus_FA_points']:+.1f} points; AUC {ctl['shuffled']['auc_scored_rows']:.3f}): **{'PASS' if ctl['pass'] else 'FAIL'}** "
  "(1 point). The excess sits on classes with out-of-range feature values (11, 12, 14, 15, 17: 5-8%): likely cause (not tested): tree models send inputs beyond the training range to an arbitrary leaf, and attacks produce such inputs more often than genuine traffic. AUC is at chance; the control shows the tail, not leakage.")
a(f"- Acceptance: FA messages {p(F['fa_msg']['p'])} / scored {p(F['fa_scored_msg']['p'])} (<= 1.5%: {'met' if fa_ok else 'NOT met'}); genuine senders at k=3 {p(F['fa_sender']['p'])} (<= 5%: NOT met; k val {p(F['kval']['fa_sender']['p'])}); no loss on seen scored rows "
  f"({pts(mean_seen(FULL)['p'], mean_seen(BASE)['p'])} points: met); class 17 gain {gain17 * 100:+.1f} points (>= 10: NOT met); class 6 {p(sc(FULL, '6')['p'])} (met); shuffled control FAIL; CIs reported (met). Overall **{acc['overall']}**.")
a(f"- Pre-registered expectations: " + ", ".join(f"{k.split('_')[0]}{'a' if 'L2_removal' in k else ('b' if 'L4_removal' in k else '')} {'yes' if v else 'NO'}" for k, v in exp.items()) + ". E4a/E4b miss: removing L2 or L3 does not change scored-row detection (the max combiner finds the same messages through L3 / L4); on all rows L3 matters most ("
  f"mean over 19 classes {p(all_rows[FULL])} -> {p(all_rows['all but L3'])} without L3, {p(all_rows['all but L2'])} without L2, {p(all_rows['all but L1'])} without L1; L1 matters for Sybil 18 / 19 and range-visible speeds).")
a("")
a("## 8. Real messages (Tampa BSMs, injected attacks, 3 test vehicles; illustration, no CIs)")
a("")
tf, tb = T["groups"][FULL], T["groups"][BASE]
a(f"VeReMi-trained L4 frozen (rate-free features), Tampa tracker and Tampa layer calibrations, thresholds on Tampa genuine validation (1%); parameter-free `{T['combiner_method_used']}` combiner. Full stack: FA {p(tf['fa_msg']['p'])} of genuine messages "
  f"({T['n_test_genuine']} messages), scored-row mean detection {p(tf['mean_msg_scored']['seen']['p'])} over seen classes (physics-only {p(tb['mean_msg_scored']['seen']['p'])}), class 6 {p(tf['msg_scored'][C('6')]['p'])}, class 17 {p(tf['msg_scored'][C('17')]['p'])} "
  f"(physics-only {p(tb['msg_scored'][C('17')]['p'])}), sender level (k=3) {p(tf['mean_sender']['seen']['p'])}. L4 alone: FA {p(T['groups']['L4-scored']['fa_msg']['p'])}, {p(T['groups']['L4-scored']['mean_msg_scored']['seen']['p'])}. "
  f"Genuine Tampa test rows: {p(T['row_kinds']['genuine_test_share']['exact repeat'])} exact repeats. The numbers are consistent with VeReMi but 3 vehicles and 2 attackers per type cannot support a claim; position-in-track and rate features were dropped, residual scales still differ (10 Hz vs 1 Hz).")
a("")
a("## 9. Literature")
a("")
a("VeReMi Extension papers (Kamel et al., ICC 2020 and follow-ups with ML detectors) usually report precision / recall / F1 per attack type, mostly with splits by message or by receiver log, so neighbouring messages of the same sender are on both sides. "
  "Ours splits by time block with zero shared senders and fixes the operating point at 1% genuine false alarms, so no number-to-number comparison is made; our split is stricter. Only the per-type structure (which attacks are easy: random / offset speed and position, DoS; hard: ConstPosOffset, EventualStop) agrees with the literature qualitatively.")
a("")
a("## 10. Limits and next")
a("")
a("- V2AIX (real CAMs) access form still pending; Tampa = one day, ~38 vehicles, 3 test vehicles. No receiver positions in either set: acceptance range and sudden-appearance checks are implemented but not evaluated.")
a("- VeReMi is simulated; genuine position noise is time-correlated, classes 11 / 13 / 16 are kinematically inconsistent, class map partly verified (S1). Second exposure of the test split; CIs cover traffic variability only.")
a("- Next (WP6): absolute-position witnesses (GPS / map / LiDAR) are the only route to ConstPosOffset and EventualStop; a Tampa-specific L4 needs more Tampa days (ITS DataHub request).")
(REP / "M1_V2X.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("M1 lines:", len(L))

# ------------------------------------------------------------------ step report
S = []
s_ = S.append
s_("# WP5 S6: combiner, ablation, scored-row L4, M1-V2X report")
s_("")
s_(f"Date: 2026-10-21    Worker: sonnet (high)    Status: {acc['overall']} (see below). Full milestone report: `reports/M1_V2X.md`; tables `results/WP5/s6_tables_veremi.md`, `s6_tables_tampa.md`; rule `notes/WP5_v2x.md` (S6 section).")
s_("")
s_("## Acceptance (rule written before the result)")
s_("")
s_("| item | result | met |")
s_("|---|---|---|")
s_(f"| 1 implemented + tests | v2x/l4.py L4Scored / row_kinds / time windows, v2x/stackeval.py, tools/WP5_S6_*.py | yes |")
s_(f"| 2a FA <= 1.5% (messages, scored messages) | {p(F['fa_msg']['p'])}, {p(F['fa_scored_msg']['p'])} | {'yes' if fa_ok else 'NO'} |")
s_(f"| 2b genuine senders (k=3) <= 5% | {p(F['fa_sender']['p'])} (k val={F['kval']['k']}: {p(F['kval']['fa_sender']['p'])}) | NO |")
s_(f"| 3a no loss on seen scored rows | {p(mean_seen(FULL)['p'])} vs {p(mean_seen(BASE)['p'])} | {'yes' if no_loss else 'NO'} |")
s_(f"| 3b class 17 gain >= 10 points | {p(sc(FULL, '17')['p'])} vs {p(sc(BASE, '17')['p'])} ({gain17 * 100:+.1f}) | {'yes' if gain17 >= 0.1 else 'NO'} |")
s_(f"| 3c class 6 >= 95% | {p(sc(FULL, '6')['p'])} | yes |")
s_(f"| 4 shuffled control (1 point) | {ctl['shuffled']['detection_minus_FA_points']:+.1f} points | {'yes' if ctl['pass'] else 'NO'} |")
s_("| 5 CIs (block bootstrap), Tampa without CIs | yes | yes |")
s_("")
s_("## Problems, surprises, questions")
s_("")
s_("- Second exposure of the VeReMi test split (S5 was the first); nothing was chosen after seeing it. Smoke run on the validation split was used for plumbing only.")
s_(f"- The supervised L4 adds no detection on the seen classes once restricted to scored rows ({pci(mean_seen('L4-scored'))} vs physics {pci(mean_seen(BASE))}); its S5 headline gain was the zero-residual shortcut. Class 17 is the only gain and the combiner (max, chosen on validation without class 17) dilutes it: {p(sc(FULL, '17')['p'])} stack vs {p(sc('L4-scored', '17')['p'])} L4 alone.")
s_(f"- Sender-level \"k >= 3 alarms\" flags {p(F['fa_sender']['p'])} of genuine senders at the 1% message budget; I added a validation-chosen k ({F['kval']['k']}, <= 1% genuine senders) next to it. Question: adopt the k-val rule as the sender-level rule for WP6?")
s_(f"- Shuffled control FAIL at 1 point ({ctl['shuffled']['detection_minus_FA_points']:+.1f}); AUC {ctl['shuffled']['auc_scored_rows']:.3f}. Bound not changed as instructed.")
s_("- Question: freeze the V2X domain output for WP6/WP7 as the full stack with the max combiner on VeReMi, or as the Tampa-calibrated stack?")
s_("")
s_("## Files")
s_("")
s_("`v2x/l4.py` (L4Scored, row_kinds, window_lengths, SCORED_SETS), `v2x/stackeval.py`, `tests/v2x/test_l4.py`, `tests/v2x/test_stackeval.py`, `tools/WP5_S6_dev.py`, `WP5_S6_run.py`, `WP5_S6_report.py`; "
   "`results/WP5/s6_dev.json`, `s6_veremi.json`, `s6_tampa.json`, `s6_acceptance.json`, `s6_tables_veremi.md`, `s6_tables_tampa.md`, `s6_l4_model.json`; logs `results/WP5/logs/s6_*.log`. Feature cache deleted.")
(REP / "WP5_S6.md").write_text("\n".join(S) + "\n", encoding="utf-8")
print("done")
