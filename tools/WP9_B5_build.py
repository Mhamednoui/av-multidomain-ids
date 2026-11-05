"""WP9 B5: build the final master table (results/WP9/B5_master.json) and the report reports/WP9_final.md.

Purpose: aggregate the approved WP9 B1-B4 results and the WP8 M4 / S8 results into ONE master table and a
fresh hold-out table. NO test scoring, NO refit: every number is read from an approved result JSON by a stored
path (copy, never recomputed, except the labelled means over the four D11 sets). Verdict words follow the
orchestrator rules in notes/WP9_brief.md ("ORCH on Bx").
Inputs: results/WP9/B*_*.json, results/WP8/S7/*.json, results/WP8/S8/*.json, results/WP9/B0_literature.json.
Outputs: results/WP9/B5_master.json, reports/WP9_final.md (summary and tables generated from the master).
Check: tools/WP9_B5_check.py re-reads every field from its source and asserts equality.
References: RULES.md section 5 and 6; workpackages/WP9_benchmark.md.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from WP9_B5_lib import ALLOWED_VERDICTS, fmt, render  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R9 = "results/WP9/"
R8 = "results/WP8/"


def P(*elems):
    out = []
    for e in elems:
        if isinstance(e, str) and "/" in e:
            out += e.split("/")
        else:
            out.append(e)
    return out


def F(file, path, f):
    return {"kind": "path", "file": file, "path": P(*path) if isinstance(path, (list, tuple)) else P(path), "fmt": f}


def AGG(kind, srcs, f):
    return {"kind": kind, "srcs": [{"file": a, "path": P(*b) if isinstance(b, (list, tuple)) else P(b)} for a, b in srcs], "fmt": f}


_cache = {}


def load(file):
    if file not in _cache:
        with open(os.path.join(ROOT, file), "r", encoding="utf-8") as fh:
            _cache[file] = json.load(fh)
    return _cache[file]


def resolve(file, path):
    o = load(file)
    for e in path:
        if isinstance(e, dict):
            hits = [x for x in o if all(x.get(k) == v for k, v in e.items())]
            assert len(hits) == 1, (file, path, e, len(hits))
            o = hits[0]
        else:
            o = o[e]
    return o


def value_of(spec):
    if spec["kind"] == "path":
        return resolve(spec["file"], spec["path"])
    vals = [resolve(s["file"], s["path"]) for s in spec["srcs"]]
    if spec["kind"] == "mean":
        return sum(vals) / len(vals)
    if spec["kind"] == "min":
        return min(vals)
    if spec["kind"] == "max":
        return max(vals)
    raise ValueError(spec["kind"])


# ------------------------------------------------------------------ files
CH = R9 + "B1_carhacking_test.json"
CHO = R9 + "B1_f1op.json"
CHC = R9 + "B1_carhacking_control2.json"
CHS = R9 + "B1_carhacking_selection.json"
RD = R9 + "B1_road_test.json"
RDC = R9 + "B1_road_control2.json"
RDS = R9 + "B1_road_selection.json"
D11 = {1: (R9 + "B1_d11_set_01_test.json", "W_xgb_a_ids"), 2: (R9 + "B1_d11_set_02_test.json", "E"),
       3: (R9 + "B1_d11_set_03_test.json", "F_noid"), 4: (R9 + "B1_d11_set_04_test.json", "E")}
D11OP = {1: "d11_set_01|W_xgb_a_ids|", 2: "d11_set_02|E|", 3: "d11_set_03|F_noid|", 4: "d11_set_04|E|"}
D11C = R9 + "B1_d11_set_01_control2.json"
D11S = R9 + "B1_d11_set_01_selection.json"
B2 = R9 + "B2_summary.json"
B3 = R9 + "B3_test.json"
B3C = R9 + "B3_controls.json"
B4G = R9 + "B4_gps_test.json"
B4V = R9 + "B4_gps_v3.json"
B4S = R9 + "B4_summary.json"
B4L = R9 + "B4_lidar_test.json"
S7SYS = R8 + "S7/system_h31.json"
S7DOM = R8 + "S7/domains.json"
S7BL = R8 + "S7/blame.json"
S7V2 = R8 + "S7/v2aix.json"
S7M4 = R8 + "S7/m4_verdict.json"
S8SUM = R8 + "S8/s8_summary.json"
S8SYS = R8 + "S8/system_s8_h31.json"
S8LID = R8 + "S8/lidar_domain.json"
B0 = R9 + "B0_literature.json"


def d11(s, subset):
    return D11[s][0], ("models", D11[s][1], "subsets", subset)


def d11f(subset, key):
    return [(D11[s][0], ("models", D11[s][1], "subsets", subset, key)) for s in (1, 2, 3, 4)]


def d11op(key):
    return [(CHO.replace("carhacking", "carhacking"), (D11OP[s] + "test_01", key)) for s in (1, 2, 3, 4)]


def b2(tab, prot, key, f):
    return F(B2, ["rows", {"table": tab, "protocol": prot}, key], f)


def b2row(tab, prot, label_set, protocol_text, leak, op_extra, bar, verdict, flags, cav, rid):
    fields = {"mf": b2(tab, prot, "macro_f1", "f3"), "mfci": b2(tab, prot, "macro_f1_ci", "ci3"),
              "fpr": b2(tab, prot, "fpr", "pct3"), "fprci": b2(tab, prot, "fpr_ci", "cipct3"),
              "auc": b2(tab, prot, "auc", "f3"), "det1": b2(tab, prot, "det1", "f3"), "fpr1": b2(tab, prot, "fpr1", "pct2"),
              "nel": b2(tab, prot, "n_eligible", "int"), "allp": b2(tab, prot, "macro_f1_all_present", "f3"),
              "ctl": b2(tab, prot, "control_pass", "bool"), "ctlauc": b2(tab, prot, "control_auc_max", "f2"),
              "rows": b2(tab, prot, "test_rows", "int")}
    fields["fprci"]["fmt"] = "cipct3"
    return {"id": rid, "domain": "network", "dataset": label_set, "protocol": protocol_text, "leak": leak,
            "ours": "macro-F1 {mf} {mfci} over {nel} classes (all present classes {allp}); FPR {fpr} {fprci}; AUC {auc}",
            "op": "argmax multiclass (macro-F1, FPR); binary detection {det1} at the 1% val budget (realised test FPR {fpr1}). " + op_extra,
            "bar": bar, "verdict": verdict, "flags": flags, "caveats": cav, "fields": fields}


NOFLAGS = {"same_data": False, "same_or_stricter": False, "ci_excludes_bar": False}

MOCZ_BAR = {"text": "Moczkodan and Ragab (arXiv 2606.11098), original labels, no dedup, 13 classes: RF on last flow, 5-tuple group 80/20 macro-F1 0.778; headline 0.89 is a non-padded-window subset only; time split degenerate (2 classes in test).",
            "probes": [[B0, 15, "0.89"], ["reports/WP9_B2.md", None, "0.778"]], "b0": [15]}
NOBAR2018 = {"text": "none: no leak-free published number for CSE-CIC-IDS2018 (B0).", "probes": [[B0, 20, "random vs temporal"]], "b0": [20]}

ROWS = []

# ---------------------------------------------------------------- CAN
ROWS.append({
    "id": "CAN_CH", "domain": "CAN", "dataset": "Car-Hacking (HCRL), seen attacks DoS/Fuzzy/RPM/Gear",
    "protocol": "100-block split + 1 s gap, 1 s windows, test = held-out blocks (locks/WP9_carhacking.json); dedup 0 rows",
    "leak": "leak-free by block (no neighbouring frames across parts); normal_run second half is a separate test",
    "ours": "macro-F1 {mf} {mfci}; attack recall {rec} {recci}; FPR {fpr}; AUC {auc}; normal_run FPR {nrfpr}",
    "op": "H = 1% val budget (headline); S = val-F1-optimal: attack F1 {sf1}, FPR {sfpr} (labelled secondary)",
    "bar": {"text": "per-attack F1 0.9997-1.0000 (Hoang and Kim; Guerra et al.), random 7:3 / unstated 80:20 split (leaky); dataset recorded parked (Lampe and Meng).",
            "probes": [[B0, 0, "0.9997"], [B0, 1, "1.0000"]], "b0": [0, 1, 4]},
    "verdict": "equal", "flags": {"same_data": True, "same_or_stricter": True, "ci_excludes_bar": False},
    "caveats": "Unit = 1 s window, bar unit = frame. Shuffled-label control passes (AUC {ctl_g}) but within-capture permutation AUC {ctl_w} (capture regime is learnable); same-segment AUC {segauc}. Dataset is trivially separable (bar also ~1.0).",
    "fields": {
        "mf": F(CH, "models/W_rf_generic/subsets/test_blocks/macro_f1", "f3"),
        "mfci": F(CH, "models/W_rf_generic/subsets/test_blocks/ci95/macro_f1", "ci3"),
        "rec": F(CH, "models/W_rf_generic/subsets/test_blocks/recall_any", "f3"),
        "recci": F(CH, "models/W_rf_generic/subsets/test_blocks/ci95/recall_any", "ci3"),
        "fpr": F(CH, "models/W_rf_generic/subsets/test_blocks/fpr", "f3"),
        "auc": F(CH, "models/W_rf_generic/subsets/test_blocks/auc", "f3"),
        "nrfpr": F(CH, "models/W_rf_generic/subsets/normal_run_test/fpr", "f3"),
        "sf1": F(CHO, ["carhacking|W_rf_generic|test_blocks", "test_f1"], "f3"),
        "sfpr": F(CHO, ["carhacking|W_rf_generic|test_blocks", "test_fpr"], "f3"),
        "ctl_g": F(CHS, "controls/W_rf_generic/shuffled_auc_window", "f2"),
        "ctl_w": F(CHC, "units/W_rf_generic/within_capture_shuffled_auc", "f2"),
        "segauc": F(R9 + "B1_regime.json", ["carhacking|W_rf_generic|test_blocks", "auc_attack_vs_normal_same_segments"], "f3")}})

ROWS.append({
    "id": "CAN_ROAD", "domain": "CAN", "dataset": "ROAD (ORNL), 10 classes (fabrication + masquerade)",
    "protocol": "capture-level split (WP2), 1 s windows from a frame XGBoost; 13 test captures, 9 with attacks (locks/WP9_road.json); coolant family only in test (separate unseen row)",
    "leak": "leak-free by capture; but ambient vs attack captures differ in regime (shortcut learnable, see caveats)",
    "ours": "macro-F1 {mf} {mfci}; attack F1 {af1}; FPR {fpr} {fprci}; recall {rec}; AUC {auc}; 9/9 attack captures alarmed; masquerade recall reverse_light_off {rl_off}, reverse_light_on {rl_on}",
    "op": "H = 1% val budget (headline); S = val-F1-optimal: attack F1 {sf1}, FPR {sfpr}",
    "bar": {"text": "Guerra et al.: multiclass LCCDE mean F1 0.3212, DCNN 0.65-0.75, LSTM 1.0 on all classes (red flag); split random-or-not NOT stated, Accelerator captures excluded.",
            "probes": [[B0, 7, "0.3212"], [B0, 7, "0.6514"], [B0, 7, "0.7468"]], "b0": [7]},
    "verdict": "comparable-not-like-for-like", "flags": NOFLAGS,
    "caveats": "Own rule NOT MET (FPR > 2%, masquerade recall low). Shuffled-label control FAILS (global AUC {ctl_g}) and within-capture AUC {ctl_w}: capture regime predicts attack-bearing. Normal windows next to attacks alarm {fpr_att} vs {fpr_amb} on ambient captures. Coolant (unseen family) recall {cool}, kept out of this row.",
    "fields": {
        "mf": F(RD, "models/Fb/subsets/test/macro_f1", "f3"), "mfci": F(RD, "models/Fb/subsets/test/ci95/macro_f1", "ci3"),
        "af1": F(RD, "models/Fb/subsets/test/f1_attack_binary", "f3"),
        "fpr": F(RD, "models/Fb/subsets/test/fpr", "pct1"), "fprci": F(RD, "models/Fb/subsets/test/ci95/fpr", "cipct1"),
        "rec": F(RD, "models/Fb/subsets/test/recall_any", "f3"), "auc": F(RD, "models/Fb/subsets/test/auc", "f3"),
        "rl_off": F(RD, "models/Fb/subsets/test/per_class_recall/7", "f2"), "rl_on": F(RD, "models/Fb/subsets/test/per_class_recall/9", "f2"),
        "sf1": F(CHO, ["road|Fb|test", "test_f1"], "f3"), "sfpr": F(CHO, ["road|Fb|test", "test_fpr"], "pct1"),
        "ctl_g": F(RDS, "controls/Fb/shuffled_auc_frame", "f2"), "ctl_w": F(RDC, "units/Fb/within_capture_shuffled_auc", "f2"),
        "fpr_att": F(RD, "models/Fb/fpr_context/normal_windows_in_attack_captures", "pct1"),
        "fpr_amb": F(RD, "models/Fb/fpr_context/ambient_captures", "pct1"),
        "cool": F(RD, "models/Fb/subsets/unseen_family/recall_any", "f2")}})

ROWS.append({
    "id": "CAN_D11K", "domain": "CAN", "dataset": "can-train-and-test (D11), known vehicle + known attacks (test_01), 4 sets",
    "protocol": "capture-disjoint train/val/test per set (WP2 splits_d11.json, locks/WP9_d11.json), 1 s windows; chosen model per set on validation",
    "leak": "leak-free by capture (same protocol family as the bar); captures of one vehicle in train and test",
    "ours": "attack F1 mean over 4 sets {f1h}; set_01 {s1f1} {s1ci}, FPR {s1fpr}; AUC mean {aucm}",
    "op": "H = 1% val budget (headline); S = val-F1-optimal (reported after H): mean {f1s} over sets (per set {f1s1} / {f1s2} / {f1s3} / {f1s4})",
    "bar": {"text": "Lampe and Meng (arXiv 2308.04972) set_01 test1: F1 0.9878 (LogReg), 0.9834 (BIRCH), 0.9811 (MLP); capture-disjoint, unit not stated, mean over 18 learners 0.42-0.46.",
            "probes": [[B0, 9, "0.9878"], [B0, 9, "0.9834"], [B0, 9, "0.9811"]], "b0": [9, 10]},
    "verdict": "below", "flags": NOFLAGS,
    "caveats": "Own rule NOT MET at the 1% budget. Unit differs (1 s window vs unstated). Shuffled-label control FAILS for most D11 units (set_01 global AUC {ctl_g}, within-capture {ctl_w}): capture regime is learnable; state this wherever D11 seen rows are used. test_03/04 are UNSEEN-attack rows (not here).",
    "fields": {
        "f1h": AGG("mean", d11f("test_01", "f1_attack_binary"), "f3"),
        "s1f1": F(D11[1][0], ["models", D11[1][1], "subsets", "test_01", "f1_attack_binary"], "f3"),
        "s1ci": F(D11[1][0], ["models", D11[1][1], "subsets", "test_01", "ci95", "f1_attack_binary"], "ci3"),
        "s1fpr": F(D11[1][0], ["models", D11[1][1], "subsets", "test_01", "fpr"], "pct1"),
        "aucm": AGG("mean", d11f("test_01", "auc"), "f3"),
        "f1s": AGG("mean", [(CHO, (D11OP[s] + "test_01", "test_f1")) for s in (1, 2, 3, 4)], "f3"),
        "f1s1": F(CHO, [D11OP[1] + "test_01", "test_f1"], "f3"), "f1s2": F(CHO, [D11OP[2] + "test_01", "test_f1"], "f3"),
        "f1s3": F(CHO, [D11OP[3] + "test_01", "test_f1"], "f3"), "f1s4": F(CHO, [D11OP[4] + "test_01", "test_f1"], "f3"),
        "ctl_g": F(D11S, "controls/W_xgb_a_ids/shuffled_auc_window", "f2"),
        "ctl_w": F(D11C, "units/W_xgb_a_ids/within_capture_shuffled_auc", "f2")}})

ROWS.append({
    "id": "CAN_D11U", "domain": "CAN", "dataset": "can-train-and-test (D11), UNKNOWN vehicle + known attacks (test_02), 4 sets",
    "protocol": "as above, thresholds calibrated on the known vehicle only",
    "leak": "leak-free by capture and by vehicle",
    "ours": "attack F1 mean {f1}; FPR min {fpr_min}, max {fpr_max} over the 4 sets; AUC mean {aucm}",
    "op": "H = 1% val budget calibrated on the KNOWN vehicle (no on-vehicle calibration)",
    "bar": {"text": "Lampe and Meng test2 (unknown vehicle): F1 0.9620 (BIRCH), 0.9594 (MLP), 0.9539 (LogReg).",
            "probes": [[B0, 9, "0.9620"], [B0, 9, "0.9594"], [B0, 9, "0.9539"]], "b0": [9]},
    "verdict": "below", "flags": NOFLAGS,
    "caveats": "Every normal window alarms (FPR 1.0): zero-shot vehicle fails with a threshold from another vehicle (same as v3 WP2). On-vehicle calibration needs benign data of the new vehicle; not tried in WP9.",
    "fields": {
        "f1": AGG("mean", d11f("test_02", "f1_attack_binary"), "f3"),
        "fpr_min": AGG("min", d11f("test_02", "fpr"), "f2"), "fpr_max": AGG("max", d11f("test_02", "fpr"), "f2"),
        "aucm": AGG("mean", d11f("test_02", "auc"), "f3")}})

# ---------------------------------------------------------------- network
CTL = ("Controls: macro-F1 shuffled-label passes everywhere; registered AUC rule: control passed = {ctl} (max shuffled AUC {ctlauc}). "
       "All CICIDS-family splits are in-distribution (same campaigns on both sides) and AUC ~1.0: these datasets are known to be trivially separable (Engelen 2021, Arp 2022).")
ROWS.append(b2row("D10o", "T", "CICIDS2017, original CICFlowMeter labels (known errors)", "time block per period, 65-80% test, dedup (T)", "leak-free by time; no row in the v3 D10 test",
                  "", {"text": MOCZ_BAR["text"] + " Time-split bar is degenerate.", "probes": MOCZ_BAR["probes"], "b0": [15]},
                  "not comparable", NOFLAGS, "Bar has no usable time-split number. " + CTL, "NET_D10o_T"))
ROWS.append(b2row("D10o", "G", "CICIDS2017, original CICFlowMeter labels (known errors)", "5-tuple group 70/10/20 (the Moczkodan and Ragab protocol), dedup (G)", "leak-free by 5-tuple group; time overlaps; 90,068 test rows are v3 D10 test rows (no v3 model reused)",
                  "", MOCZ_BAR, "comparable-not-like-for-like", NOFLAGS,
                  "Same labels and group protocol as the bar RF 0.778, but our class set is 12 classes with >= 20 flows (bar keeps 13) and we deduplicate (bar does not): not like-for-like. Bot precision 0.56 on original labels = label noise. " + CTL, "NET_D10o_G"))
ROWS.append(b2row("D10o", "B", "CICIDS2017, original CICFlowMeter labels (known errors)", "5-min block group (stricter than the bar), dedup (B)", "leak-free by 5-minute block group; 56,087 test rows are v3 D10 test rows",
                  "", {"text": "no bar at this strictness (strictest published: 5-tuple group, see G row).", "probes": MOCZ_BAR["probes"], "b0": [15]},
                  "not comparable", NOFLAGS, CTL, "NET_D10o_B"))
ROWS.append(b2row("D10e", "T", "CICIDS2017, corrected labels (Engelen 2021)", "time block per period, dedup (T)", "leak-free by time",
                  "", {"text": "no bar on corrected labels (bar uses original labels).", "probes": [[B0, 12, "20%"]], "b0": [12]},
                  "not comparable", NOFLAGS, "Corrected labels shrink the hard Web classes (12-151 flows), most fall below the support rule: a main reason the macro-F1 is higher. " + CTL, "NET_D10e_T"))
ROWS.append(b2row("D10e", "G", "CICIDS2017, corrected labels (Engelen 2021)", "5-tuple group 70/10/20, dedup (G)", "leak-free by 5-tuple group",
                  "", {"text": "no bar on corrected labels (bar uses original labels).", "probes": [[B0, 12, "20%"]], "b0": [12]},
                  "not comparable", NOFLAGS, "The selected model is a random forest: the registered shuffled-label AUC rule FAILED (10-seed AUC 0.558, macro-F1 0.086). " + CTL, "NET_D10e_G"))
ROWS.append(b2row("D10e", "B", "CICIDS2017, corrected labels (Engelen 2021)", "5-min block group, dedup (B)", "leak-free by 5-minute block group",
                  "", {"text": "no bar on corrected labels (bar uses original labels).", "probes": [[B0, 12, "20%"]], "b0": [12]},
                  "not comparable", NOFLAGS, CTL, "NET_D10e_B"))
ROWS.append(b2row("D23x", "T", "CSE-CIC-IDS2018, corrected (Liu 2022 release)", "time block per period, dedup, benign 1-in-10 sample weighted 10 (T)", "leak-free by time",
                  "", NOBAR2018, "not comparable", NOFLAGS,
                  "Our numbers are the first leak-free numbers we know of; no bar to compare. Random-forest shuffled-label AUC rule FAILS (XGB control 0.52-0.60: density-structure effect, hypothesis untested). " + CTL, "NET_D23_T"))
ROWS.append(b2row("D23x", "G", "CSE-CIC-IDS2018, corrected (Liu 2022 release)", "5-tuple group 70/10/20, dedup (G)", "leak-free by 5-tuple group",
                  "", NOBAR2018, "not comparable", NOFLAGS,
                  "First leak-free numbers we know of; no bar. Random-forest shuffled-label AUC rule FAILS. Infiltration-NMAP precision 0.18-0.36 (benign scans). " + CTL, "NET_D23_G"))
ROWS.append(b2row("D23x", "B", "CSE-CIC-IDS2018, corrected (Liu 2022 release)", "5-min block group, dedup (B)", "leak-free by 5-minute block group",
                  "", NOBAR2018, "not comparable", NOFLAGS,
                  "First leak-free numbers we know of; no bar. Random-forest shuffled-label AUC rule FAILS. " + CTL, "NET_D23_B"))

# ---------------------------------------------------------------- V2X
H = "ops/H_budget1pct/point/"
HC = "ops/H_budget1pct/ci95/"
S = "ops/S_valF1opt/point/"
ROWS.append({
    "id": "V2X_ALL", "domain": "V2X", "dataset": "VeReMi Extension (D12), genuine + all 19 attack types, message level",
    "protocol": "1800 s time blocks of ONE simulation (23 train / 7 val / 8 test), H31's 10 WP5 blocks excluded (locks/WP9_veremi.json)",
    "leak": "leak-free by time block (no sender on air in two parts); but one simulation, one map, one day pattern",
    "ours": "macro-F1 {mf} {mfci}; binary F1 {bf1}; FPR {fpr} {fprci}; AUC {auc}; mean alarm recall {mar}",
    "op": "H = 1% val budget (headline); S = val-F1-optimal (secondary): macro-F1 {smf}, FPR {sfpr}",
    "bar": {"text": "none comparable: published VeReMi Extension numbers are DoS family only (5 types), 70/30 per dataset.", "probes": [[B0, 22, "DoS family only"]], "b0": [22, 23]},
    "verdict": "not comparable", "flags": NOFLAGS,
    "caveats": "Failed controls as written: within-block sender permutation {c_perm} and proxy-only {c_proxy} (band 0.42-0.58); explanation: pseudonym id carries churn (alone {c_ps}), group-permutation nulls are not centred on 0.5 (0.34-0.52). Row-shuffle control {c_row} passes. Raw x,y,speed make the model map-specific (ConstPosOffset recall {cpo}). Class 12 is a placeholder artefact. In-distribution benchmark only.",
    "fields": {
        "mf": F(B3, H + "macro_f1", "f3"), "mfci": F(B3, HC + "macro_f1", "ci3"), "bf1": F(B3, H + "binary.f1", "f3"),
        "fpr": F(B3, H + "fpr", "pct2"), "fprci": F(B3, HC + "fpr", "cipct2"), "auc": F(B3, H + "auc", "f3"),
        "mar": F(B3, H + "mean_alarm_recall", "f3"),
        "smf": F(B3, S + "macro_f1", "f3"), "sfpr": F(B3, S + "fpr", "pct2"),
        "c_perm": F(B3C, "units/chosen_within_block_sender_permutation/val_auc", "f3"),
        "c_proxy": F(B3C, "units/proxy_only_t_sender_pseudo/val_auc", "f3"),
        "c_ps": F(R9 + "B3_proxy_diag.json", "pseudo_only", "f3"),
        "c_row": F(B3C, "units/chosen_shuffled_rows/val_auc", "f3"),
        "cpo": F(B3, H + "alarm_recall.2", "f2")}})

ROWS.append({
    "id": "V2X_DOS_M", "domain": "V2X", "dataset": "VeReMi Extension (D12), DoS family (13, 14, 15, 18, 19), prevalence-matched 70 % genuine / 30 % attack",
    "protocol": "as above; genuine re-weighted so the sender mix equals the bar's 70/30",
    "leak": "stricter than the bar (block-disjoint in time; bar = 70/30 inside each dataset, per vehicle)",
    "ours": "F1 per type {dmin}-{dmax}, pooled {dpool} {dpoolci}; recall pooled {drec}",
    "op": "H = 1% val budget",
    "bar": {"text": "F1 0.93-0.998 (Baharlouei 2024; Asensio-Garriga as cited: 99.06 DoS, 99.77 DoSRandom, 97.97 DoSDisruptive, 94.46 Random Sybil, 92.56 Disruptive Sybil), 70/30 inside each dataset, dedup not stated.",
            "probes": [[B0, 23, "99.06"], [B0, 23, "99.77"], [B0, 23, "92.56"]], "b0": [22, 23]},
    "verdict": "equal", "flags": {"same_data": True, "same_or_stricter": True, "ci_excludes_bar": False},
    "caveats": "Inside the bar range, not above it: no 'better'. Same failed controls as V2X_ALL (sender permutation, proxy-only) apply; one simulation, one map.",
    "fields": {
        "dmin": AGG("min", [(B3, H + f"dos.{k}.matched.f1") for k in (13, 14, 15, 18, 19)], "f3"),
        "dmax": AGG("max", [(B3, H + f"dos.{k}.matched.f1") for k in (13, 14, 15, 18, 19)], "f3"),
        "dpool": F(B3, H + "dos.pooled.matched.f1", "f3"), "dpoolci": F(B3, HC + "dos.pooled.matched.f1", "ci3"),
        "drec": F(B3, H + "dos.pooled.matched.recall", "f3")}})

ROWS.append({
    "id": "V2X_DOS_N", "domain": "V2X", "dataset": "VeReMi Extension (D12), DoS family, natural (mixed-CSV) prevalence",
    "protocol": "as above; no re-weighting (59% genuine traffic)",
    "leak": "leak-free by time block",
    "ours": "F1 per type {dmin}-{dmax} (H), pooled {dpool}; precision pooled {dprec}",
    "op": "H = 1% val budget; at S (val-F1-optimal) F1 per type {smin}-{smax}, pooled {spool}",
    "bar": {"text": "F1 0.93-0.998 at the bar's 70/30 prevalence.", "probes": [[B0, 23, "99.06"]], "b0": [22, 23]},
    "verdict": "comparable-not-like-for-like", "flags": NOFLAGS,
    "caveats": "Prevalence differs from the bar: the 1% FPR on abundant genuine traffic lowers precision (two types below 0.93 at H). Shows what the prevalence matching changes.",
    "fields": {
        "dmin": AGG("min", [(B3, H + f"dos.{k}.natural.f1") for k in (13, 14, 15, 18, 19)], "f3"),
        "dmax": AGG("max", [(B3, H + f"dos.{k}.natural.f1") for k in (13, 14, 15, 18, 19)], "f3"),
        "dpool": F(B3, H + "dos.pooled.natural.f1", "f3"), "dprec": F(B3, H + "dos.pooled.natural.precision", "f3"),
        "smin": AGG("min", [(B3, S + f"dos.{k}.natural.f1") for k in (13, 14, 15, 18, 19)], "f3"),
        "smax": AGG("max", [(B3, S + f"dos.{k}.natural.f1") for k in (13, 14, 15, 18, 19)], "f3"),
        "spool": F(B3, S + "dos.pooled.natural.f1", "f3")}})

# ---------------------------------------------------------------- GPS
GI = "case_I/F_full/"
ROWS.append({
    "id": "GPS_I", "domain": "GPS", "dataset": "AV-GPS-Dataset (Abrar et al.), Case I: train file 1, test file 2 (+ file-3 normals)",
    "protocol": "session split, train 17 / val 8 sessions of file 1; test = 5 sessions of file 2 (2 normal + 3 spoof) after dedup (locks/WP9_avgps.json)",
    "leak": "session-disjoint (stricter than the bar's stratified folds); dataset itself has copies (file 0 inside file 1, duplicate spoof sessions, file 3 = copies of file 2)",
    "ours": "F1 at S {sf1} {sci}; FPR {sfpr}; AUC {sauc}. At H: F1 {hf1} {hci}, FPR {hfpr}",
    "op": "S = val-F1-optimal (the rule G1 was written for S); H = 1% val budget shown for completeness, below the bar range",
    "bar": {"text": "Abrar et al. (arXiv 2405.08359) cross-dataset MLP F1 0.965 (Case I), 0.964 (II), 0.905 (III); RF 0.919, XGB 0.915; stratified 5-fold, folds NOT by session.",
            "probes": [[B0, 26, "0.965"], [B0, 26, "0.905"]], "b0": [26]},
    "verdict": "equal", "flags": {"same_data": True, "same_or_stricter": True, "ci_excludes_bar": False},
    "caveats": "Equal at S only, on a dataset with artefacts; never 'better'. CI over 5 sessions spans the whole bar range. The label is predictable from vehicle state alone (val AUC {vsauc}); any F1 above ~0.9 measures that, not spoof detection under motion. GPS row-shuffle band control fails as written (8 clustered val sessions).",
    "fields": {
        "sf1": F(B4G, GI + "S/f1", "f3"), "sci": F(B4G, GI + "S/ci_session_cluster/f1", "ci3"), "sfpr": F(B4G, GI + "S/fpr", "pct1"),
        "sauc": F(B4G, GI + "S/auc", "f3"), "hf1": F(B4G, GI + "H/f1", "f3"), "hci": F(B4G, GI + "H/ci_session_cluster/f1", "ci3"),
        "hfpr": F(B4G, GI + "H/fpr", "pct1"),
        "vsauc": F(R9 + "B4_gps_controls.json", "proxy_only_vehicle_state/val_auc_by_depth/3", "f3")}})

ROWS.append({
    "id": "GPS_II", "domain": "GPS", "dataset": "AV-GPS-Dataset, Case II: train file 2 (5 sessions), test the 25 file-1 sessions",
    "protocol": "session split, fixed config, threshold 0.5",
    "leak": "session-disjoint, cross-day",
    "ours": "F_full F1 {f1}, FPR {fpr}; strongest view F_kin F1 {kf1} {kci}, recall {krec}, FPR {kfpr}",
    "op": "fixed threshold 0.5 (no validation session set for this direction)",
    "bar": {"text": "Abrar cross-dataset Case II MLP F1 0.964.", "probes": [[B0, 26, "0.964"]], "b0": [26]},
    "verdict": "below", "flags": NOFLAGS,
    "caveats": "A model trained on one day / one rover does not transfer: F_full alarms on everything. Only the vehicle-state-contaminated view F_kin reaches 0.806.",
    "fields": {
        "f1": F(B4G, "case_II/F_full/f1", "f3"), "fpr": F(B4G, "case_II/F_full/fpr", "f2"),
        "kf1": F(B4G, "case_II/F_kin/f1", "f3"), "kci": F(B4G, "case_II/F_kin/ci_session_cluster/f1", "ci3"),
        "krec": F(B4G, "case_II/F_kin/recall", "f3"), "kfpr": F(B4G, "case_II/F_kin/fpr", "pct1")}})

ROWS.append({
    "id": "GPS_POS", "domain": "GPS", "dataset": "AV-GPS-Dataset, Case I, GPS-only view (position steps + course, no vehicle-state fields)",
    "protocol": "as GPS_I (view added by amendment 1 after the vehicle-state control, before any test row)",
    "leak": "session-disjoint",
    "ours": "F_pos at H: F1 {hf1} {hci}, FPR {hfpr}; at S: F1 {sf1}, FPR {sfpr}",
    "op": "H = 1% val budget (transfers); S = val-F1-optimal (does NOT transfer: FPR {sfpr})",
    "bar": {"text": "Abrar cross-dataset F1 0.90-0.965 (uses all fields).", "probes": [[B0, 26, "0.965"]], "b0": [26]},
    "verdict": "comparable-not-like-for-like", "flags": NOFLAGS,
    "caveats": "Rule G2 (restated: artefact-free view F1 >= 0.80 and FPR <= 5% at S) NOT MET. 5 test sessions; CI wide.",
    "fields": {
        "hf1": F(B4G, "case_I/F_pos/H/f1", "f3"), "hci": F(B4G, "case_I/F_pos/H/ci_session_cluster/f1", "ci3"),
        "hfpr": F(B4G, "case_I/F_pos/H/fpr", "pct1"), "sf1": F(B4G, "case_I/F_pos/S/f1", "f3"), "sfpr": F(B4G, "case_I/F_pos/S/fpr", "pct1")}})

ROWS.append({
    "id": "GPS_V3", "domain": "GPS", "dataset": "AV-GPS-Dataset, Case I test, v3 label-free layers (no training)",
    "protocol": "v3 GPS layers calibrated on the validation normals at 1%; same 5 test sessions",
    "leak": "no training on this data",
    "ours": "F1 {f1} {fci}; recall {rec}; FPR {fpr}; AUC {auc} (session-permutation null q95 = same value, rule G3 NOT MET)",
    "op": "H = 1% val budget (calibration on validation normals)",
    "bar": {"text": "Abrar cross-dataset F1 0.90-0.965 (trained supervised models).", "probes": [[B0, 26, "0.965"]], "b0": [26]},
    "verdict": "comparable-not-like-for-like", "flags": NOFLAGS,
    "caveats": "F1 sits in the bar range but the CI is huge and AUC equals the permutation null: no evidence beyond chance on this dataset. One spoof session (171 rows) missed; the two latching CUSUMs do the work.",
    "fields": {
        "f1": F(B4V, "combined/f1", "f3"), "fci": F(B4V, "combined/ci_session_cluster/f1", "ci3"), "rec": F(B4V, "combined/recall", "f3"),
        "fpr": F(B4V, "combined/fpr", "pct1"), "auc": F(B4V, "combined/auc", "f3")}})

# ---------------------------------------------------------------- LiDAR
LI = "detectors/supervised/ops/fpr10/"
ROWS.append({
    "id": "LIDAR", "domain": "LiDAR", "dataset": "KITTI raw, 7 test drives, 9 generated attack kinds seen in training (scan level)",
    "protocol": "drive split 13 train / 3 val / 7 test (locks/WP9_kitti.json); static 211-column XGBoost; attacks generated by the WP3 recipe (documented attacker capabilities)",
    "leak": "leak-free by drive; the 7 test drives are V31_val material for v3.1 (tuned-on)",
    "ours": "NAIVE-ADD (box cloud + multi-return add) TPR {naive} {naiveci} at test FPR {fpr} {fprci}; IntensitySpoof {isp}; PointDrop {pd}; single-return phantom kinds {ph1}-{ph2}",
    "op": "10% validation clean-scan budget (headline for the bar's FPR < 10%); v3.1 at the same thresholds: NAIVE {v31naive}",
    "bar": {"text": "object-level accuracy > 94% (Shadow-Catcher, KITTI, injected ghost objects); nuScenes TPR > 85% at FPR < 10% (ADoPT).",
            "probes": [[B0, 30, "94%"], [B0, 31, "85%"]], "b0": [30, 31]},
    "verdict": "not comparable", "flags": NOFLAGS,
    "caveats": "Another metric level (object vs scan), other data (nuScenes) and other attacks. Our rule L1 (NAIVE TPR >= 0.85) NOT MET. The full 429-column model was red-flagged (temporal columns 91% of gain) and never test-scored. Single-return phantoms are at the physics bound for any detector. Within-scan permutation control marginal.",
    "fields": {
        "naive": F(B4L, LI + "kinds/NAIVE/tpr", "f3"), "naiveci": F(B4L, LI + "kinds/NAIVE/ci_drive_boot", "ci3"),
        "fpr": F(B4L, LI + "fpr/fpr", "pct1"), "fprci": F(B4L, LI + "fpr/ci_drive_boot", "cipct1"),
        "isp": F(B4L, LI + "kinds/IntensitySpoof/tpr", "f2"), "pd": F(B4L, LI + "kinds/PointDrop/tpr", "f2"),
        "ph1": AGG("min", [(B4L, P(LI + f"kinds/{k}/tpr")) for k in ("ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far")], "f2"),
        "ph2": AGG("max", [(B4L, P(LI + f"kinds/{k}/tpr")) for k in ("ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far")], "f2"),
        "v31naive": F(B4L, "detectors/v31/ops/fpr10/kinds/NAIVE/tpr", "f3")}})

# ---------------------------------------------------------------- second table (zero-shot / fresh hold-out track)
T2 = []


def t2(rid, group, track, metric, exposure, kind, note, fields, v3, v31, diff):
    T2.append({"id": rid, "group": group, "track": track, "metric": metric, "exposure": exposure, "kind": kind, "note": note,
               "fields": fields, "v3": v3, "v31": v31, "diff": diff})


FRESH = "fresh H31"
PART = "partially fresh (vehicle block fresh; CAN / network / V2X streams re-used)"
EXP2 = "H31 exposure 2, post-M4 fix, NOT fresh"


def lidrow(rid, kind_, note, kind):
    base = ["lidar", "paired_scan_level_v31_minus_v3", kind_]
    fl = {"v3": F(S7DOM, base + ["v3"], "pct1"), "v31": F(S7DOM, base + ["v31"], "pct1"),
          "d": F(S7DOM, base + ["diff_points"], "sgn1"), "ci": F(S7DOM, base + ["ci_points"], "ci_sgn1")}
    if kind_ == "PointDrop":
        fl["excl"] = F(S8SUM, ["lidar", "pointdrop_excl_0093"], "pct1")
    t2(rid, "2a", "LiDAR scan level, frozen alarm rule", f"{kind_}: detection per scan", FRESH, kind, note, fl, "{v3}", "{v31}", "{d} pts {ci}")


lidrow("T2_PD", "PointDrop", "real fresh gain (M4-8 target 65% reached ungated, but a flood on drive 0093 inflates it: v3.1 on the 12 healthy drives {excl}, S8; v3 without drive 0093 was not computed)", "gain")
lidrow("T2_IS", "IntensitySpoof", "real fresh gain, low absolute level", "gain")
lidrow("T2_PN", "ph_replace_near", "tiny gain, both near chance", "neutral")
lidrow("T2_PF", "ph_budget_far", "far single-return phantoms: at chance for both (physics bound)", "miss")
t2("T2_LFA", "2a", "LiDAR scan level", "clean scan false alarm (bound <= 1.5%)", FRESH, "miss",
   "both far above the bound; dominated by the defective drive 0093 (S8)",
   {"v3": F(S7DOM, ["lidar", "clean", "v3_fa"], "pct2"), "v31": F(S7DOM, ["lidar", "clean", "v31_fa"], "pct2")}, "{v3}", "{v31}", "-")
GP = ["gps", "rows", {"subset": "gps pooled attacks [all]"}]
CP = ["cross", "rows", {"subset": "cross pooled attacks [all]"}]
t2("T2_GPS", "2a", "GPS domain (v3 = v3.1, same frozen object)", "pooled attacks", FRESH, "miss",
   "det at 1% FA is 0 (scores saturate); clean FA 7.2% vs 1.4% on V31_val; one drive (0093) = 94% of its clean ticks",
   {"auc": F(S7DOM, GP + ["auc"], "f3"), "aci": F(S7DOM, GP + ["auc_ci"], "ci3"), "d1": F(S7DOM, GP + ["det@1.0%"], "pct1"),
    "fa": F(S7DOM, GP + ["op_fa"], "pct2"), "det": F(S7DOM, GP + ["op_det"], "pct1")},
   "AUC {auc} {aci}; det at 1% FA {d1}; frozen rule FA {fa}, det {det}", "same object", "-")
t2("T2_CROSS", "2a", "Cross-domain layer (v3 = v3.1 recipe)", "pooled attacks", FRESH, "miss",
   "det at 1% FA is 0; individual attacks as low as 8% (lidar_yaw) at the frozen rule",
   {"auc": F(S7DOM, CP + ["auc"], "f3"), "aci": F(S7DOM, CP + ["auc_ci"], "ci3"), "d1": F(S7DOM, CP + ["det@1.0%"], "pct1"),
    "fa": F(S7DOM, CP + ["op_fa"], "pct2"), "det": F(S7DOM, CP + ["op_det"], "pct1")},
   "AUC {auc} {aci}; det at 1% FA {d1}; frozen rule FA {fa}, det {det}", "same recipe", "-")
t2("T2_BL_C", "2a", "Blame, comma GNSS spoof (drift / meaconing / doppler)", "correct blame of detected runs (wrong)", FRESH, "gain",
   "real fresh gain (M4-13 MET); v3 abstains (undecided) on these types, v3.1 blames",
   {"v3": F(S7BL, ["C", "V3", "B2", "correct"], "pct1"), "v31": F(S7BL, ["C", "A1", "B2", "correct"], "pct1"),
    "w3": F(S7BL, ["C", "V3", "B2", "wrong"], "pct1"), "w31": F(S7BL, ["C", "A1", "B2", "wrong"], "pct1")},
   "{v3} ({w3})", "{v31} ({w31})", "-")
t2("T2_BL_K", "2a", "Blame, KITTI gps_can", "correct blame of detected runs (wrong)", FRESH, "miss",
   "v3.1 blames worse than v3 (M4-12 NOT MET)",
   {"v3": F(S7BL, ["K", "V3", "gps_can", "correct"], "pct1"), "v31": F(S7BL, ["K", "A1", "gps_can", "correct"], "pct1"),
    "w3": F(S7BL, ["K", "V3", "gps_can", "wrong"], "pct1"), "w31": F(S7BL, ["K", "A1", "gps_can", "wrong"], "pct1")},
   "{v3} ({w3})", "{v31} ({w31})", "-")
for env in ("Mobile", "Stationary"):
    t2("T2_V2AIX_" + env[0], "2a", f"V2AIX real V2X, {env}", "genuine false alarm per message (bound <= 1.5%); injected mean", FRESH + " (same site-day as calibration for most recordings)",
       "miss" if env == "Stationary" else "neutral", "M4-11 NOT MET" if env == "Stationary" else "inside the bound, but only 24 recordings",
       {"fa": F(S7V2, ["envs", env, "false_alarms", "physics", "per_message"], "pct2"), "inj": F(S7V2, ["envs", env, "injected_mean_over_types"], "pct1")},
       "same object", "FA {fa}; injected {inj}", "-")


def sysrow(rid, fam, key, metric, f_abs, kind, note, exposure=PART):
    pr = ["paired_v31_minus_v3", fam]
    pct = f_abs.startswith("pct")
    t2(rid, "2a", f"System {fam} ({'KITTI H31' if fam == 'K' else 'comma Chunk_2'})", metric, exposure, kind, note,
       {"v3": F(S7SYS, ["runs", "v3", fam, key], f_abs), "v31": F(S7SYS, ["runs", "v31", fam, key], f_abs),
        "d": F(S7SYS, pr + [key, "diff"], "sgn_pts1" if pct else "sgn2"), "ci": F(S7SYS, pr + [key, "ci"], "ci_pts1" if pct else "ci2")},
       "{v3}", "{v31}", "{d} " + ("pts " if pct else "") + "{ci}")


sysrow("T2_K_DET", "K", "det_single", "event detection, single-domain types (bound >= 70%)", "pct1", "gain", "paired CI excludes 0 in the good direction (partially fresh)")
sysrow("T2_K_HELD", "K", "det_heldout", "event detection, held-out (zero-day) types (bound >= 60%)", "pct1", "miss", "point estimate lower, CI includes 0")
sysrow("T2_K_FA", "K", "fa_tick", "clean tick false alarm (bound <= 3%)", "pct2", "miss", "no change; M4-1 NOT MET (defective drive 0093)")
sysrow("T2_K_EV", "K", "events_per_hour", "alert events per clean hour (bound <= 10)", "x1", "miss", "M4-2 NOT MET")
sysrow("T2_C_DET", "C", "det_single", "event detection, single-domain types", "pct1", "miss", "paired CI excludes 0 in the BAD direction")
sysrow("T2_C_HELD", "C", "det_heldout", "event detection, held-out types", "pct1", "miss", "paired CI excludes 0 in the BAD direction")
sysrow("T2_C_BLC", "C", "blame_correct", "blame correct (per type)", "pct1", "gain", "paired CI excludes 0 in the good direction (partially fresh)")
for dom, kind_ in (("cross", "gain"), ("v2x", "gain"), ("lidar", "neutral"), ("network", "neutral")):
    pr = ["paired_v31_minus_v3", "K", "by_attacked_domain", dom]
    t2("T2_KD_" + dom, "2a", "System K by attacked domain", f"event detection, {dom} types", PART, kind_,
       "paired CI excludes 0 in the good direction" if kind_ == "gain" else "no detectable change",
       {"v3": F(S7SYS, ["runs", "v3", "K", "by_attacked_domain", dom, "event_detection"], "pct1"),
        "v31": F(S7SYS, ["runs", "v31", "K", "by_attacked_domain", dom, "event_detection"], "pct1"),
        "d": F(S7SYS, pr + ["diff"], "sgn_pts1"), "ci": F(S7SYS, pr + ["ci"], "ci_pts1")}, "{v3}", "{v31}", "{d} pts {ci}")

G = ["runs", "v31_gated", "K"]
PG = ["paired_gated_minus_ungated", "K"]
t2("T2_S8_FA", "2b", "S8 gate, system K", "clean tick false alarm (bound <= 3%)", EXP2, "repair (not fresh)",
   "gate repairs the defective drive 0093; still NOT MET",
   {"v3": F(S8SUM, ["h31_K", "fa_ungated"], "pct1"), "v31": F(S8SUM, ["h31_K", "fa_gated"], "pct1"), "gci": F(S8SYS, G + ["fa_tick_ci"], "cip1_br"),
    "d": F(S8SYS, PG + ["fa_tick", "diff"], "sgn_pts1"), "ci": F(S8SYS, PG + ["fa_tick", "ci"], "ci_pts1")},
   "{v3}", "{v31} {gci}", "{d} pts {ci}")
t2("T2_S8_SS", "2b", "S8 gate, system K", "SAFE_STOP per clean hour (bound <= 1)", EXP2, "repair (not fresh)", "upper CI above 1",
   {"v3": F(S8SUM, ["h31_K", "safe_stop_ungated"], "x2"), "v31": F(S8SUM, ["h31_K", "safe_stop_gated"], "x2"), "gci": F(S8SYS, G + ["SAFE_STOP_per_hour_ci"], "ci2")},
   "{v3}", "{v31} {gci}", "-")
t2("T2_S8_EV", "2b", "S8 gate, system K", "alert events per clean hour (bound <= 10)", EXP2, "miss", "NOT MET",
   {"v3": F(S8SUM, ["h31_K", "events_ungated"], "x1"), "v31": F(S8SUM, ["h31_K", "events_gated"], "x1"),
    "d": F(S8SUM, ["h31_K", "paired", "events_per_hour", "diff"], "sgn2"), "ci": F(S8SUM, ["h31_K", "paired", "events_per_hour", "ci"], "ci2")},
   "{v3}", "{v31}", "{d} {ci}")
t2("T2_S8_DET", "2b", "S8 gate, system K", "event detection, single-domain types", EXP2, "miss",
   "cost of the gate; part of the ungated 87.1% was a flood effect on drive 0093",
   {"v3": F(S8SUM, ["h31_K", "det_ungated"], "pct1"), "v31": F(S8SUM, ["h31_K", "det_gated"], "pct1"),
    "d": F(S8SYS, PG + ["det_single", "diff"], "sgn_pts1"), "ci": F(S8SYS, PG + ["det_single", "ci"], "ci_pts1")}, "{v3}", "{v31}", "{d} pts {ci}")
t2("T2_S8_HELD", "2b", "S8 gate, system K", "event detection, held-out types", EXP2, "miss", "CI touches 0",
   {"v3": F(S8SUM, ["h31_K", "held_ungated"], "pct1"), "v31": F(S8SUM, ["h31_K", "held_gated"], "pct1"),
    "d": F(S8SYS, PG + ["det_heldout", "diff"], "sgn_pts1"), "ci": F(S8SYS, PG + ["det_heldout", "ci"], "ci_pts1")}, "{v3}", "{v31}", "{d} pts {ci}")
t2("T2_S8_LFA", "2b", "S8 gate, LiDAR domain", "clean scan false alarm (bound <= 1.5%)", EXP2, "repair (not fresh)",
   "one drive changes: drive-bootstrap CI touches 0; still NOT MET",
   {"v3": F(S8SUM, ["lidar", "clean_fa_ungated"], "pct2"), "v31": F(S8SUM, ["lidar", "clean_fa_gated"], "pct2"),
    "d": F(S8LID, ["rows", "clean scans (FA)", "paired_diff"], "sgn_pts1"), "ci": F(S8LID, ["rows", "clean scans (FA)", "paired_ci"], "ci_pts1")},
   "{v3}", "{v31}", "{d} pts {ci}")
t2("T2_S8_PD", "2b", "S8 gate, LiDAR domain", "PointDrop per scan (bound >= 65%)", EXP2, "miss",
   "part of the ungated 66.1% was flood on 0093 ({excl} on the 12 healthy drives); NOT MET after the fix",
   {"v3": F(S8SUM, ["lidar", "pointdrop_ungated"], "pct1"), "v31": F(S8SUM, ["lidar", "pointdrop_gated"], "pct1"),
    "excl": F(S8SUM, ["lidar", "pointdrop_excl_0093"], "pct1")}, "{v3}", "{v31}", "-")
t2("T2_M4", "meta", "M4 verdict", "rows MET of all rows", "-", "miss", "M4 verdict NOT MET stands",
   {"n_met": F(S7M4, ["n_met"], "int"), "n_rows": F(S7M4, ["n_rows"], "int")}, "{n_met} of {n_rows}", "-", "-")

CLAIMS = [
    ("CAN_CH", "Car-Hacking, seen attacks, block split: macro-F1 {CAN_CH.mf} {CAN_CH.mfci} matches the near-perfect published numbers (0.9997-1.0000, random or unstated splits) under a stricter block-disjoint split; it does not exceed them. Verdict equal."),
    ("V2X_DOS_M", "VeReMi Extension DoS family, prevalence-matched 70/30: pooled F1 {V2X_DOS_M.dpool} {V2X_DOS_M.dpoolci} (per type {V2X_DOS_M.dmin}-{V2X_DOS_M.dmax}) matches the best published results (0.93-0.998) under a stricter block-disjoint split. Verdict equal."),
    ("V2X_ALL", "All 19 VeReMi Extension types, block split: macro-F1 {V2X_ALL.mf} {V2X_ALL.mfci} at FPR {V2X_ALL.fpr}; no published number exists for all 19 types, so these are the first such numbers we know of (one simulation, in-distribution). Verdict not comparable."),
    ("GPS_I", "AV-GPS Case I with session-disjoint splits: F1 {GPS_I.sf1} {GPS_I.sci} at the validation-F1-optimal threshold equals the published cross-dataset F1 0.90-0.965 on a dataset with artefacts (at the 1% budget F1 is {GPS_I.hf1}). Verdict equal."),
    ("NET_D10o_G", "CICIDS2017, original labels, 5-tuple group protocol of Moczkodan and Ragab: macro-F1 {NET_D10o_G.mf} {NET_D10o_G.mfci} against their RF 0.778; class set and dedup differ, so comparable, not like-for-like."),
    ("NET_D23_G", "CICIDS2017 corrected labels and CSE-CIC-IDS2018 under time, group and block splits: macro-F1 {NET_D10e_T.mf} to {NET_D10e_G.mf} and {NET_D23_T.mf} to {NET_D23_G.mf} (the random-forest units fail the shuffled-label AUC rule). First leak-free numbers we know of for 2018; no bar (not comparable), in-distribution."),
    ("T2_PD", "Fresh hold-out H31: v3.1 beats frozen v3 on LiDAR PointDrop ({T2_PD.d} pts {T2_PD.ci}), IntensitySpoof ({T2_IS.d} pts {T2_IS.ci}) and on comma GNSS-spoof blame ({T2_BL_C.v3} to {T2_BL_C.v31} correct). Partially fresh: system event detection K {T2_K_DET.d} pts {T2_K_DET.ci}, cross {T2_KD_cross.d} pts, V2X {T2_KD_v2x.d} pts. Table 2a."),
    ("T2_S8_FA", "The S8 sensor-health gate removes the false-alarm flood caused by one defective recording: K clean tick FA {T2_S8_FA.v3} to {T2_S8_FA.v31}, SAFE_STOP per hour {T2_S8_SS.v3} to {T2_S8_SS.v31}. This is exposure 2 on H31 (a repair of a seen failure, NOT fresh evidence). Table 2b."),
]
CANNOT = [
    ("-", "No row has the verdict better: we cannot claim 'state of the art', 'best' or 'better than' anywhere. Equal rows are worded 'matches the best published results under a stricter split'."),
    ("CAN_D11U", "CAN detection on a new vehicle: D11 unknown-vehicle attack F1 mean {CAN_D11U.f1}, FPR {CAN_D11U.fpr_min} to {CAN_D11U.fpr_max} (every normal window alarms) against the bar 0.95-0.96. Verdict below."),
    ("CAN_D11K", "The published D11 known-vehicle bar: mean attack F1 {CAN_D11K.f1h} at the 1% budget, {CAN_D11K.f1s} at the validation-F1-optimal threshold, against 0.98-0.99. Verdict below. ROAD is comparable at most and our own rule is NOT MET (FPR {CAN_ROAD.fpr})."),
    ("LIDAR", "LiDAR spoofing detection at the published level: NAIVE-ADD TPR {LIDAR.naive} {LIDAR.naiveci} at test FPR {LIDAR.fpr}; the bar is object-level / nuScenes (not comparable); single-return phantoms are at the physics bound."),
    ("GPS_II", "Spoof detection under motion or transfer across days on AV-GPS: the label is predictable from vehicle state alone (val AUC {GPS_I.vsauc}); Case II (other day) F1 {GPS_II.f1} with FPR {GPS_II.fpr}; the v3 label-free layers are indistinguishable from chance there (AUC {GPS_V3.auc} = permutation null q95)."),
    ("NET_D10e_G", "Generalisation from the benchmark numbers: all CICIDS / VeReMi splits are in-distribution (same campaigns, one simulation, one map); AUC ~1.0 on CICIDS is a known dataset property; several shuffled-label controls failed as written (RF AUC rule on 4 network units, VeReMi sender permutation {V2X_ALL.c_perm} and proxy-only {V2X_ALL.c_proxy}, ROAD / D11 global shuffle, GPS row-shuffle band)."),
    ("T2_M4", "That M4 was met: M4 verdict NOT MET ({T2_M4.n_met} of {T2_M4.n_rows} rows MET). The S8 repair is exposure 2 and still misses the K FA bound ({T2_S8_FA.v31} vs 3%) and the events bound ({T2_S8_EV.v31} vs 10 per hour)."),
    ("T2_C_DET", "That v3.1 improves on v3 everywhere: on comma Chunk_2 event detection ({T2_C_DET.d} pts) and held-out ({T2_C_HELD.d} pts) are worse (CI excludes 0 in the bad direction); KITTI gps_can blame is worse ({T2_BL_K.v3} to {T2_BL_K.v31} correct); KITTI held-out detection is lower ({T2_K_HELD.d} pts, CI includes 0)."),
]

FIGS = [
    ("fig_can_roc.png", "CAN: detection vs false-alarm rate (1 s windows)", "fig_can_roc.csv"),
    ("fig_network_det_vs_fa.png", "Network: detection vs false-alarm rate (flow level, G protocol)", "fig_network_det_vs_fa.csv"),
    ("fig_v2x_roc.png", "V2X: VeReMi Extension, all 19 attack types and DoS family", "fig_v2x_roc.csv"),
    ("fig_gps_roc.png", "GPS: AV-GPS Case I, supervised views and v3 label-free", "fig_gps_roc.csv"),
    ("fig_lidar_roc.png", "LiDAR: KITTI seen attacks, supervised static model vs v3.1", "fig_lidar_roc.csv"),
    ("fig_h31_zeroshot.png", "H31 system K: v3 vs v3.1 vs v3.1 + S8 (exposure labelled)", "fig_h31_zeroshot.csv"),
]


class Obj:
    def __init__(self, d):
        self.__dict__.update(d)


def realize(spec_dict):
    out = {}
    for name, spec in spec_dict.items():
        v = value_of(spec)
        out[name] = {"spec": spec, "value": v, "text": fmt(spec["fmt"], v)}
    return out


def texts_of(fields):
    return {k: v["text"] for k, v in fields.items()}


def main():
    master_rows = []
    TX = {}
    for r in ROWS:
        assert r["verdict"] in ALLOWED_VERDICTS, r["id"]
        fl = realize(r["fields"])
        tx = texts_of(fl)
        TX[r["id"]] = Obj(tx)
        row = {k: r[k] for k in ("id", "domain", "dataset", "protocol", "leak", "verdict", "flags", "bar")}
        row["templates"] = {"ours": r["ours"], "op": r["op"], "caveats": r["caveats"]}
        row["cells"] = {k: render(r[k], tx) for k in ("ours", "op", "caveats")}
        row["fields"] = fl
        master_rows.append(row)
    t2rows = []
    for r in T2:
        fl = realize(r["fields"])
        tx = texts_of(fl)
        TX[r["id"]] = Obj(tx)
        row = {k: r[k] for k in ("id", "group", "track", "metric", "exposure", "kind")}
        row["templates"] = {"v3": r["v3"], "v31": r["v31"], "diff": r["diff"], "note": r["note"]}
        row["cells"] = {"v3": render(r["v3"], tx), "v31": render(r["v31"], tx), "diff": render(r["diff"], tx), "note": render(r["note"], tx)}
        row["fields"] = fl
        t2rows.append(row)
    claims = [{"row": rid, "template": t, "text": render(t, TX)} for rid, t in CLAIMS]
    cannot = [{"row": rid, "template": t, "text": render(t, TX)} for rid, t in CANNOT]
    master = {"generated_by": "tools/WP9_B5_build.py", "step": "WP9 B5", "allowed_verdicts": list(ALLOWED_VERDICTS),
              "verdict_rule": "better only if same data, same-or-stricter split and CI excludes the bar (flags); equal / comparable / not comparable / below otherwise",
              "operating_points": "H = threshold at the 1% validation false-alarm budget (headline); S = validation-F1-optimal (secondary, reported after H, same single test scoring)",
              "rows": master_rows, "table2": t2rows, "claims": claims, "cannot": cannot, "figures": FIGS}
    with open(os.path.join(ROOT, "results/WP9/B5_master.json"), "w", encoding="utf-8") as fh:
        json.dump(master, fh, indent=1)
    write_report(master)
    print("rows", len(master_rows), "table2", len(t2rows), "claims", len(claims))


def esc(s):
    return s.replace("|", "/")


def t2table(m, grp, h3, h31, hd):
    L = ["| id | track | metric | exposure | " + h3 + " | " + h31 + " | " + hd + " | kind | note |", "|---|---|---|---|---|---|---|---|---|"]
    for r in m["table2"]:
        if r["group"] != grp:
            continue
        c = r["cells"]
        L.append(f"| {r['id']} | {esc(r['track'])} | {esc(r['metric'])} | {esc(r['exposure'])} | {esc(c['v3'])} | {esc(c['v31'])} | {esc(c['diff'])} | {r['kind']} | {esc(c['note'])} |")
    return L


def write_report(m):
    rows = m["rows"]
    cnt = {}
    for r in rows:
        cnt[r["verdict"]] = cnt.get(r["verdict"], 0) + 1
    m4 = [r for r in m["table2"] if r["id"] == "T2_M4"][0]["cells"]["v3"]
    L = []
    A = L.append
    A("# WP9 B5: final comparison against the published bar (benchmark track)")
    A("")
    A("Date: 2026-11-05    Worker: sonnet (high, T3)    No new test scoring, no refit: every number is copied from an approved result JSON (results/WP9/B5_master.json; checked by tools/WP9_B5_check.py).")
    A("")
    A("## Summary (<= 40 lines)")
    A("- Master table (section 1): " + str(len(rows)) + " rows. Verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(cnt.items())) + ". NO row has the verdict 'better'.")
    A("- Operating points: H = threshold at the 1% validation false-alarm budget (pre-registered headline); S = validation-F1-optimal (literature convention, secondary, reported after H from the same single test scoring). Every row says which one it quotes.")
    A("- We can claim (section 3):")
    for c in m["claims"][:6]:
        A("  - " + c["text"])
    A("  - " + m["claims"][6]["text"])
    A("- We cannot claim (section 4): " + "; ".join(c["text"].split(":")[0] for c in m["cannot"][:8]) + ".")
    A("- Fresh hold-out track (section 2): M4 verdict NOT MET (" + m4 + " rows MET). Real fresh gains: LiDAR PointDrop / IntensitySpoof, comma GNSS blame. Misses: false-alarm bounds, comma detection, KITTI gps_can blame, V2AIX Stationary. S8 rows are 'H31 exposure 2, post-M4 fix, NOT fresh'.")
    A("- Failed controls are repeated in the caveat column of each row they affect: RF shuffled-label AUC rule (4 network units), VeReMi sender permutation and proxy-only, ROAD / D11 global shuffled label, GPS row-shuffle band, LiDAR within-scan permutation (marginal). Dataset defects: AV-GPS copies, CICIDS original-label errors, VeReMi single simulation.")
    A("- Figures (section 5, results/WP9/B5/figures/, PNG + CSV, saved scores only): " + ", ".join(f[0] for f in m["figures"]) + ".")
    A("- Check: `tools/WP9_B5_check.py` re-reads every field from its source JSON, asserts equality, and asserts this report contains every generated cell.")
    A("")
    A("## 1. Master table (seen attack types, standard datasets, leak-free splits; test scored once per dataset)")
    A("")
    A("Verdict words: better (same data, same-or-stricter split, CI excludes the bar) / equal / comparable-not-like-for-like / not comparable / below. Bars are quoted from results/WP9/B0_literature.json (B0 row numbers in brackets). H = 1% validation false-alarm budget (headline), S = validation-F1-optimal (secondary).")
    names = ["CAN", "network", "V2X", "GPS", "LiDAR"]
    for dom in names:
        A("")
        A(f"### 1.{names.index(dom) + 1} {dom}")
        A("")
        A("| id | dataset | split protocol (leak-free?) | our metric [95% CI] | operating point | published bar (source, protocol) | verdict | failed controls / caveats |")
        A("|---|---|---|---|---|---|---|---|")
        for r in rows:
            if r["domain"] != dom:
                continue
            c = r["cells"]
            A(f"| {r['id']} | {esc(r['dataset'])} | {esc(r['protocol'])}; {esc(r['leak'])} | {esc(c['ours'])} | {esc(c['op'])} | {esc(r['bar']['text'])} [B0 {', '.join(map(str, r['bar']['b0']))}] | **{r['verdict']}** | {esc(c['caveats'])} |")
    A("")
    A("Intervals: block / capture / drive / session / 5-tuple-group bootstrap as stated in the step reports (B1 to B4); the number of groups is small for ROAD (9 captures), AV-GPS (5 sessions) and LiDAR (7 drives), so those intervals are wide.")
    A("")
    A("## 2. Zero-shot / fresh hold-out track: v3.1 vs v3 on H31 (M4) and S8 rows")
    A("")
    A("M4 verdict: NOT MET (" + m4 + " rows MET); frozen v3 (tag v3.0) and frozen v3.1 scored once, paired (reports/M4.md, results/WP8/S7). Paired difference = v3.1 minus v3, group-bootstrap 95% CI. kind: gain = paired CI excludes 0 in the good direction (fresh or partially fresh as labelled); miss = bound not met, or difference bad or not significant; neutral = no detectable change.")
    A("")
    A("### 2a. Frozen v3 vs frozen v3.1 on H31 (M4 scoring)")
    A("")
    L.extend(t2table(m, "2a", "v3", "v3.1", "paired v3.1 - v3 [95% CI]"))
    A("")
    A("### 2b. S8 sensor-health gate on H31: frozen v3.1 vs v3.1 + S8 (H31 exposure 2, post-M4 fix, NOT fresh)")
    A("")
    L.extend(t2table(m, "2b", "frozen v3.1", "v3.1 + S8", "paired gated - ungated [95% CI]"))
    A("")
    A("Real fresh gains (v3.1 over v3): LiDAR PointDrop and IntensitySpoof, comma GNSS-spoof blame. Partially fresh gains: system K detection, cross and V2X types, comma blame. Misses: every false-alarm bound (K, C, LiDAR scans, GPS, cross, V2AIX Stationary), K held-out, C detection and held-out, KITTI gps_can blame, far phantoms (physics bound). The S8 gate repairs one defective recording; it is not a detection gain.")
    A("")
    A("## 3. What we can honestly claim")
    A("")
    for c in m["claims"]:
        A(f"- {c['text']} [row {c['row']}]")
    A("")
    A("## 4. What we cannot claim")
    A("")
    for c in m["cannot"]:
        A(f"- {c['text']} [row {c['row']}]")
    A("")
    A("## 5. Figures (saved scores only; dataset, split and exposure in every title)")
    A("")
    for f in m["figures"]:
        A(f"- results/WP9/B5/figures/{f[0]} (data: results/WP9/B5/figures/{f[2]}): {f[1]}")
    A("")
    A("## Method notes, problems, limits")
    A("- Aggregation only: values are read by path from approved JSONs (B1 to B4, WP8 S7 / S8). The D11 means are plain means over the four sets of the per-set chosen model (labelled in the table). No threshold, model or split was touched.")
    A("- DoS 'matched' V2X numbers come from the B3 test JSON (genuine re-weighted to 70/30). Bar numbers are copied from B0 and probed against B0_literature.json by the check script; 0.778 (Moczkodan RF whole test) comes from reports/WP9_B2.md (HTML read in B2).")
    A("- Known display issue in reports/M4.md: the paired K events-per-hour line prints -302.52/h; the JSON value is the correct one (T2_K_EV).")
    A("- Not done: no scoring of the withheld full 429-column LiDAR model; no on-vehicle calibration for D11; no independent VeReMi simulation; no KITTI / comma GPS supervised row.")
    A("")
    with open(os.path.join(ROOT, "reports/WP9_final.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    main()
