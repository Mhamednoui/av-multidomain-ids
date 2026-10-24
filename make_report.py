"""AV-IDS v3: generate RESULTS_v3.md from the results JSON files (WP7 S3).

Purpose: one results document whose every number is read from a saved JSON file; nothing is typed by hand and no test set is scored here.
Inputs: results/WP1..WP7 JSON (the milestone acceptance and test files listed in the section builders below) and results/WP7/S3_registry.json
(curated inputs that exist in no result file: rule thresholds, test-exposure counts, v2 reference numbers, each with its source).
Outputs: RESULTS_v3.md (byte-identical on a second run) with an appendix listing, for every number of the text, the file and key path it was read from.

How the trace works: every number is produced by a Ctx method (pc, num, cnt, ci, txt, ...) that records (file, key path, printed value) and wraps the printed
text in invisible markers. After the text is built, the markers are stripped and a scan of the remaining text must find no standalone number (the scan ignores
identifiers such as D10 or S3b, dates, heading numbers and `code spans`). Sections whose result file does not exist yet (M1-LiDAR, M2 addendum, M3 simulation)
are written as PENDING and fill themselves from their acceptance JSON as soon as it exists.

Usage (from codes_v3/):  python make_report.py [--out RESULTS_v3.md] [--stdout]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REG = "results/WP7/S3_registry.json"
M1, M2_, M3_, M4_ = "\x01", "\x02", "\x03", ""
MISSING = object()
MARK = re.compile("\x01(\\d+)\x02(.*?)\x03", re.S)

# files that fill the open sections (first existing wins); names are the convention WP3 / WP6 / WP7 are asked to follow
PENDING_FILES = {
    "M1-LiDAR": ["results/WP3/S9/acceptance.json", "results/WP3/S9_acceptance.json", "results/WP3/M1_acceptance.json"],
    "M2 addendum": ["results/WP6/s5b_acceptance.json"],
    "M3 simulation": ["results/WP7/S2_acceptance.json"],
}


class Ctx:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.files = {}
        self.items = []
        self.index = {}
        self.missing = []
        self.pending = []
        self.closed = True

    # ------------------------------------------------------------ access
    def load(self, f):
        if f not in self.files:
            p = self.root / f
            self.files[f] = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        return self.files[f]

    def exists(self, f):
        return (self.root / f).exists()

    def raw(self, f, path=""):
        o = self.load(f)
        if o is None:
            return MISSING
        for seg in [s for s in path.split("/") if s != ""]:
            try:
                o = o[int(seg)] if isinstance(o, list) else o[seg]
            except (KeyError, IndexError, ValueError, TypeError):
                return MISSING
        return o

    def keys(self, f, path=""):
        o = self.raw(f, path)
        return list(o.keys()) if isinstance(o, dict) else []

    # ------------------------------------------------------------ marking
    def _mark(self, f, path, text, kind):
        key = (f, path, text, kind)
        if key not in self.index:
            self.index[key] = len(self.items)
            self.items.append({"file": f, "path": path, "text": text, "kind": kind, "uses": 0, "closed": self.closed})
        self.items[self.index[key]]["uses"] += 1
        return f"{M1}{self.index[key]}{M2_}{text}{M3_}"

    def _val(self, f, path):
        v = self.raw(f, path)
        if v is MISSING:
            if self.closed:
                self.missing.append((f, path))
            return MISSING
        return v

    def _kind(self, f):
        return "curated" if f == REG else "json"

    def pc(self, f, path, d=1, sign=True):
        v = self._val(f, path)
        t = "n/a" if v is MISSING or v is None else f"{100 * float(v):.{d}f}" + ("%" if sign else "")
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def pp(self, f, path, d=1):
        """difference of two fractions in percentage points: '16.2 points'."""
        v = self._val(f, path)
        t = "n/a" if v is MISSING or v is None else f"{100 * float(v):.{d}f} points"
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def num(self, f, path, d=2):
        v = self._val(f, path)
        t = "n/a" if v is MISSING or v is None else f"{float(v):.{d}f}"
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def cnt(self, f, path):
        v = self._val(f, path)
        t = "n/a" if v is MISSING or v is None else f"{int(round(float(v))):,}"
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def txt(self, f, path):
        v = self._val(f, path)
        t = "n/a" if v is MISSING or v is None else str(v)
        t = t.replace("|", "/").replace("\n", " ")
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def yn(self, f, path):
        v = self._val(f, path)
        t = "n/a" if v is MISSING or v is None else ("yes" if v else "no")
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def met(self, f, path):
        v = self._val(f, path)
        if v is MISSING or v is None:
            t = "n/a"
        elif isinstance(v, bool):
            t = "MET" if v else "NOT MET"
        else:
            t = str(v)
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def ci(self, f, path, d=0, pct=True):
        v = self._val(f, path)
        if v is MISSING or v is None or any(x is None for x in v):
            t = "[n/a]"
        else:
            k = 100 if pct else 1
            t = f"[{k * float(v[0]):.{d}f}, {k * float(v[1]):.{d}f}]"
        return self._mark(f, path, t, "MISSING" if v is MISSING else self._kind(f))

    def pci(self, f, path, cipath, d=1):
        """percent with its interval: '75.7% [63, 89]' (two tracked values)."""
        return self.pc(f, path, d) + " " + self.ci(f, cipath, 0)

    def derived(self, name, srcs, func, fmt):
        """value computed from tracked JSON values; the appendix lists the sources and the formula name."""
        vals = [self._val(f, p) for f, p in srcs]
        ok = all(v is not MISSING and v is not None for v in vals)
        t = fmt(func(vals)) if ok else "n/a"
        key = "; ".join(f"{f}#{p}" for f, p in srcs)
        return self._mark("derived", f"{name} := {key}", t, "derived")

    def raw_val(self, f, path):
        """value without printing (used to decide a verdict from values that are printed elsewhere in the same row)."""
        v = self._val(f, path)
        return None if v is MISSING else v


# ------------------------------------------------------------ small markdown helpers
def tbl(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out) + "\n"


def para(*parts):
    return " ".join(p.strip() for p in parts) + "\n"


def verdict_word(b):
    return "MET" if b else "NOT MET"


# ------------------------------------------------------------ rule rows
def acc_rows(c, f, ids, names=None):
    """rows from an acceptance JSON whose entries carry 'rule' and 'met' (WP6 style)."""
    rows = []
    for i in ids:
        if c.raw(f, i) is MISSING:
            continue
        rows.append([i.split("_")[0], c.txt(f, i + "/rule"), c.met(f, i + "/met")])
    return rows


def gps_rules(c):
    f = "results/WP1/S8_acceptance.json"
    a = lambda p: c.raw_val(f, p)
    g = lambda p: f + "#" + p
    rows = []
    rows.append(["G1", "unit tests pass", c.txt(f, "G1_tests/value"), c.met(f, "G1_tests/verdict"), a("G1_tests/verdict") == "MET"])
    rows.append(["G2", "clean-run false alarms at most " + c.pc(f, "G2_false_alarms/bound"),
                 c.pc(f, "G2_false_alarms/test_fa_clean_runs", 2) + " on test (nested development " + c.pc(f, "G2_false_alarms/nested_dev_fa", 2) + ")",
                 c.met(f, "G2_false_alarms/verdict"), str(a("G2_false_alarms/verdict")).startswith("MET")])
    rows.append(["G3", "Doppler-consistent spoof and meaconing detected at least " + c.pc("results/WP7/S3_registry.json", "rules/gps_G3_target/value", 0),
                 "Doppler " + c.pc(f, "G3_targets/doppler") + " " + c.ci(f, "G3_targets/ci_drives_doppler") + ", meaconing " + c.pc(f, "G3_targets/meaconing") + " " + c.ci(f, "G3_targets/ci_drives_meaconing"),
                 c.met(f, "G3_targets/verdict"), str(a("G3_targets/verdict")).startswith("MET")])
    rows.append(["G4", "better than the v2 dead-reckoning rule B2 (mean run-level gain, paired drive bootstrap)",
                 "gain " + c.pp(f, "G4_beats_B2/mean_gain") + " " + c.ci(f, "G4_beats_B2/mean_gain_ci_drives"), c.met(f, "G4_beats_B2/verdict"), str(a("G4_beats_B2/verdict")).startswith("MET")])
    rows.append(["G5", "the combination is not worse than the best single layer",
                 "combined " + c.pc(f, "G5_combining_helps/mean_combined") + " vs best single layer " + c.pc(f, "G5_combining_helps/best_single_mean/0") + " (" + c.txt(f, "G5_combining_helps/best_single_mean/1") + ")",
                 c.met(f, "G5_combining_helps/verdict"), str(a("G5_combining_helps/verdict")).startswith("MET")])
    rows.append(["G6", "shuffled-label control of the supervised row: mean AUC at most " + c.num("results/WP7/S3_registry.json", "rules/gps_G6_bound/value"),
                 "mean AUC " + c.num(f, "G6_shuffled_label_control/auc_mean") + ", max " + c.num(f, "G6_shuffled_label_control/auc_max"),
                 c.met(f, "G6_shuffled_label_control/verdict"), str(a("G6_shuffled_label_control/verdict")).startswith("MET")])
    rows.append(["G7", "intervals reported (bootstrap over test drives and runs)", c.txt(f, "G7_intervals/note"), c.met(f, "G7_intervals/verdict"), str(a("G7_intervals/verdict")).startswith("MET")])
    rows.append(["G8", "UAV flight: alarm at the first spoofed fix and pre-onset false alarms at most " + c.pc("results/WP7/S3_registry.json", "rules/gps_uav_fa_max/value", 0),
                 "first alarm " + c.num(f, "G8_uav/delay_s", 4) + " s after onset; pre-onset FA " + c.pc(f, "G8_uav/pre_onset_fa", 2) + " " + c.ci(f, "G8_uav/wilson95") + " (" + c.cnt(f, "G8_uav/pre_onset_alarms") + " alarms)",
                 c.met(f, "G8_uav/verdict"), str(a("G8_uav/verdict")).startswith("MET")])
    rows.append(["G9", "AV-GPS sessions", "combined AUC " + c.num(f, "G9_avgps/combined_auc", 3) + " = the upper end of the session-label permutation null " + c.ci(f, "G9_avgps/auc_null_q05_q95", 2, pct=False),
                 c.txt(f, "G9_avgps/verdict"), False])
    rows.append(["G10", "the frozen domain reproduces the evaluated statistic", "score difference " + c.num(f, "G10_frozen/max_abs_diff_statistic", 1) + ", alarm disagreements " + c.cnt(f, "G10_frozen/alarm_disagreements"),
                 c.met(f, "G10_frozen/verdict"), str(a("G10_frozen/verdict")).startswith("MET")])
    return rows


def can_rules(c):
    f = "results/WP2/s7_test.json"
    R = "results/WP7/S3_registry.json"
    cfg = "configs/all/"
    md, mt = c.raw_val(f, cfg + "masquerade_detected"), c.raw_val(R, "rules/can_masquerade_total/value")
    pd_, pn = c.raw_val(f, cfg + "plain_detected"), c.raw_val(f, cfg + "n_plain")
    fa, fam = c.raw_val(f, cfg + "clean_fa_pooled"), c.raw_val(R, "rules/can_fa_max/value")
    ah, ahm = c.raw_val(f, cfg + "false_alerts_per_hour"), c.raw_val(R, "rules/can_alerts_per_hour_max/value")
    rev = c.raw_val(f, cfg + "ambient_fa/ambient_dyno_reverse")
    rows = []
    rows.append(["C1", "all " + c.cnt(R, "rules/can_masquerade_total/value") + " masquerade captures detected",
                 c.cnt(f, cfg + "masquerade_detected") + " detected, exact interval " + c.ci(f, cfg + "masquerade_ci95_clopper_pearson"), verdict_word(md is not None and mt is not None and md >= mt), md is not None and md >= mt])
    rows.append(["C2", "all injected (non-masquerade) captures detected", c.cnt(f, cfg + "plain_detected") + " of " + c.cnt(f, cfg + "n_plain"), verdict_word(pd_ == pn), pd_ == pn])
    rows.append(["C3", "clean-window false alarms at most " + c.pc(R, "rules/can_fa_max/value", 0),
                 c.pc(f, cfg + "clean_fa_pooled", 2) + " " + c.ci(f, cfg + "clean_fa_ci95_cluster_bootstrap", 1), verdict_word(fa is not None and fa <= fam), fa is not None and fa <= fam])
    rows.append(["C4", "false alerts per hour at most " + c.cnt(R, "rules/can_alerts_per_hour_max/value"), c.num(f, cfg + "false_alerts_per_hour", 1) + " per hour",
                 verdict_word(ah is not None and ah <= ahm), ah is not None and ah <= ahm])
    rows.append(["C5", "no false alarm on reverse driving", c.pc(f, cfg + "ambient_fa/ambient_dyno_reverse", 1) + " of the reverse-driving windows (too few windows to bound the rate)",
                 verdict_word(rev == 0), rev == 0])
    return rows


def net_rules(c):
    f = "results/WP4/s7_d10.json"
    f2 = "results/WP4/s7_d23.json"
    R = "results/WP7/S3_registry.json"
    fa_h, fa_o = c.raw_val(f, "stacks/H/published/fa"), c.raw_val(f, "stacks/O/published/fa")
    fam = c.raw_val(R, "rules/net_fa_max/value")
    bh, bo = c.raw_val(f, "loao/Bot/stacks/H/detection/Bot"), c.raw_val(f, "loao/Bot/stacks/O/detection/Bot")
    bmin = c.raw_val(R, "rules/net_unseen_bot_min/value")
    d23 = c.raw_val(f2, "zero_shot_tue/stage_stream/H/fa")
    d23m = c.raw_val(R, "rules/net_d23_fa_max/value")
    m1 = (fa_h <= fam and fa_o <= fam)
    m2 = (bh > bmin and bo > bmin)
    m3 = (d23 <= d23m)
    rows = []
    rows.append(["N1", "benign false alarms (headline, Infiltration scan excluded) at most " + c.pc(R, "rules/net_fa_max/value", 0),
                 "H " + c.pc(f, "stacks/H/published/fa", 2) + " " + c.ci(f, "stacks/H/published/fa_ci", 2) + ", O " + c.pc(f, "stacks/O/published/fa", 2) + " " + c.ci(f, "stacks/O/published/fa_ci", 2),
                 verdict_word(m1), m1])
    rows.append(["N2", "unseen Bot (leave-one-attack-out) above " + c.pc(R, "rules/net_unseen_bot_min/value", 0),
                 "H " + c.pc(f, "loao/Bot/stacks/H/detection/Bot", 0) + ", O " + c.pc(f, "loao/Bot/stacks/O/detection/Bot", 0), verdict_word(m2), m2])
    rows.append(["N3", "zero-shot transfer to the other dataset (D23): false alarms at most " + c.pc(R, "rules/net_d23_fa_max/value", 0),
                 "H on the one day with addresses " + c.pc(f2, "zero_shot_tue/stage_stream/H/fa", 1) + "; the flag layer alone on all days " + c.pc(f2, "zero_shot_tcp_flags_all_days/fa", 1) + " " + c.ci(f2, "zero_shot_tcp_flags_all_days/fa_ci", 0),
                 verdict_word(m3), m3])
    return rows


def v2x_rules(c):
    f = "results/WP5/s6_acceptance.json"
    R = "results/WP7/S3_registry.json"
    rows = []
    rows.append(["V1", "unit tests of the V2X modules pass", "unit tests of tests/v2x (see the milestone report)", c.met(f, "1_implemented_tests/met"), bool(c.raw_val(f, "1_implemented_tests/met"))])
    rows.append(["V2a", "false alarms on messages at most " + c.pc(R, "rules/v2x_fa_msg_max/value"),
                 c.pc(f, "2a_FA_messages_le_1.5pct/FA_msg", 2) + " of all genuine messages, " + c.pc(f, "2a_FA_messages_le_1.5pct/FA_scored_msg", 2) + " of scored ones",
                 c.met(f, "2a_FA_messages_le_1.5pct/met"), bool(c.raw_val(f, "2a_FA_messages_le_1.5pct/met"))])
    rows.append(["V2b", "genuine senders flagged at the simple rule (three alarms) at most " + c.pc(R, "rules/v2x_sender_k3_fa_max/value", 0),
                 c.pc(f, "2b_FA_genuine_senders_k3_le_5pct/FA_sender_k3", 1) + "; at the validation-chosen count " + c.pc(f, "2b_FA_genuine_senders_k3_le_5pct/FA_sender_kval", 1),
                 c.met(f, "2b_FA_genuine_senders_k3_le_5pct/met"), bool(c.raw_val(f, "2b_FA_genuine_senders_k3_le_5pct/met"))])
    rows.append(["V3a", "no loss on seen classes (scored rows, full stack vs physics only)", c.pc(f, "3a_no_loss_seen_scored/full") + " vs " + c.pc(f, "3a_no_loss_seen_scored/base"),
                 c.met(f, "3a_no_loss_seen_scored/met"), bool(c.raw_val(f, "3a_no_loss_seen_scored/met"))])
    rows.append(["V3b", "learned layer gains at least " + c.cnt(R, "rules/v2x_class17_gain_min_points/value") + " points on the unseen class 17", "gain " + c.num(f, "3b_class17_gain_ge_10pts/gain_points", 1) + " points",
                 c.met(f, "3b_class17_gain_ge_10pts/met"), bool(c.raw_val(f, "3b_class17_gain_ge_10pts/met"))])
    rows.append(["V3c", "unseen class 6 at least " + c.pc(R, "rules/v2x_class6_min/value", 0), c.pc(f, "3c_class6_ge_95/full"), c.met(f, "3c_class6_ge_95/met"), bool(c.raw_val(f, "3c_class6_ge_95/met"))])
    rows.append(["V4", "shuffled-label null control within " + c.cnt(R, "rules/v2x_shuffled_gap_max_points/value") + " point of chance",
                 "null model detects " + c.pc(f, "4_shuffled_control/detection_pooled") + " at " + c.pc(f, "4_shuffled_control/FA") + " false alarms (gap " + c.num(f, "4_shuffled_control/gap_points", 1) + " points)",
                 c.met(f, "4_shuffled_control/met"), bool(c.raw_val(f, "4_shuffled_control/met"))])
    rows.append(["V5", "block-bootstrap intervals reported", c.cnt(f, "5_block_bootstrap_CIs/blocks") + " test time blocks", c.met(f, "5_block_bootstrap_CIs/met"), bool(c.raw_val(f, "5_block_bootstrap_CIs/met"))])
    return rows


M2_NAMES = {"A1": "raw clean-tick false alarms", "A2": "alert events per clean hour", "A3": "K event detection, single-domain attacks", "A4": "K event detection, held-out types",
            "A5": "blame of detected events", "A6": "SAFE_STOP recommendations per clean hour", "A7": "alert events with an explanation"}
M2_IDS = ["A1_raw_tick_fa", "A2_events_per_clean_hour", "A3_K_event_detection_single", "A4_K_heldout_event_detection", "A5_K_blame", "A6_safe_stop_per_clean_hour", "A7_explained"]


def observed(c, f, key):
    """observed value(s) of an acceptance entry: 'value', or K / C, or the blame triple (raw fractions or counts as stored)."""
    v = c.raw(f, key)
    if not isinstance(v, dict):
        return "-"
    if isinstance(v.get("value"), (int, float)):
        return c.num(f, key + "/value", 3)
    if isinstance(v.get("value"), dict) and "correct" in v["value"]:
        return "correct " + c.num(f, key + "/value/correct", 3) + ", wrong " + c.num(f, key + "/value/wrong", 3)
    if "K" in v and "C" in v:
        if isinstance(v["K"], list):
            return "K " + c.cnt(f, key + "/K/0") + " of " + c.cnt(f, key + "/K/1") + ", C " + c.cnt(f, key + "/C/0") + " of " + c.cnt(f, key + "/C/1")
        return "K " + c.num(f, key + "/K", 3) + ", C " + c.num(f, key + "/C", 3)
    return "-"


def m2_rules(c):
    f = "results/WP6/s5_acceptance.json"
    rows = []
    for i in M2_IDS:
        rows.append([i.split("_")[0], M2_NAMES[i.split("_")[0]] + ": " + c.txt(f, i + "/rule"), c.met(f, i + "/met"), bool(c.raw_val(f, i + "/met")), observed(c, f, i)])
    return rows


def tally(rows, idx):
    return sum(1 for r in rows if r[idx]), len(rows)


# ------------------------------------------------------------ sections
def sec_status(c, rules):
    R = "results/WP7/S3_registry.json"
    rows = []
    rows.append(["M0 foundation", "closed", "-", "contracts frozen; the v2 dead-reckoning number is reproduced exactly (`results/WP0/regression_b2.json`)"])

    def row(name, regkey, rl, idx, where):
        m, n = tally(rl, idx)
        return [name, c.txt(R, f"milestone_status/{regkey}/value"), c.derived(f"rules met in the {name} table", [], lambda v: (m, n), lambda t: f"{t[0]} of {t[1]}"), where]
    rows.append(row("M1-GPS", "M1_GPS", rules["gps"], 4, "section 2"))
    rows.append(row("M1-CAN", "M1_CAN", rules["can"], 4, "section 3"))
    rows.append(row("M1-NET", "M1_NET", rules["net"], 4, "section 4"))
    rows.append(row("M1-V2X", "M1_V2X", rules["v2x"], 4, "section 5"))
    rows.append(["M1-LiDAR", "PENDING (open)", "-", "section 6; WP3 S5, S6 running, S7 and S9 follow"])
    rows.append(row("M2", "M2", rules["m2"], 3, "section 7"))
    rows.append(["M3 system", "PENDING (open)", "-", "section 8; the streaming runtime of WP7 S1 is done, the simulation (S2) waits for M1-LiDAR"])
    rows.append(["M4 publication", "not started (needs the user's approval)", "-", "-"])
    out = tbl(["milestone", "status in its report", "rules met (rows of the tables below)", "where"], rows)
    out += "\nThe rule counts are rows of the tables in sections 2 to 7, each judged against the rule written before its result; a milestone report may group the rules differently.\n"
    return out


def sec_claims(c):
    S4 = "results/WP6/s4_test.json"
    AC4 = "results/WP6/s4_acceptance.json"
    CT = "results/WP2/s7_test.json"
    S3B = "results/WP5/s3b_acceptance.json"
    out = ""
    out += "### 1.1 Corrected thesis claim: physics layers and normal-only models are complementary\n\n"
    out += para("The claim \"physics is the zero-day defence\" is NOT supported by the data. The claim the data support is that physics and rule layers and normal-only (learned from clean data) models",
                "are complementary: each misses what the other catches, and together they detect more held-out attack types than either alone.",
                "Decision recorded in `notes/ORCHESTRATOR.md` (2026-10-24, WP6 row). Held-out types are attack families that no layer or choice has seen.")
    rows = []
    for label, key in (("rules only (physics / specification)", "rules-only system"), ("normal-only models (L3) only", "l3-only system"), ("both (no novelty layer)", "matched without novelty")):
        p = f"system/K/{key}/"
        rows.append([label, c.pc(S4, p + "by_category/heldout") + " " + c.ci(S4, p + "ci_heldout/mean_detection"), c.pc(S4, p + "fa_tick", 2)])
    out += "\n" + tbl(["system layers (K composites, `results/WP6/s4_test.json`)", "held-out types, mean detection, 95% interval", "clean-tick false alarms"], rows)
    out += "\nThe same split inside one domain (ROAD CAN, test captures, each layer at its own one-percent budget):\n\n"
    rows = []
    for label, cfg in (("specification rules only (L1)", "only_L1"), ("normal-only per-signal predictors (L3c)", "only_L3c"), ("all layers", "all")):
        p = f"configs/{cfg}/"
        rows.append([label, c.cnt(CT, p + "masquerade_detected") + " of " + c.cnt("results/WP7/S3_registry.json", "rules/can_masquerade_total/value"), c.pc(CT, p + "clean_fa_pooled", 2)])
    out += "\n" + tbl(["CAN layers", "masquerade captures detected (rules cannot see an in-place edit)", "clean-window false alarms"], rows)
    out += "\nRules miss exactly the attacks built to pass them (masquerade, Doppler-consistent GPS spoofs); normal-only models add value only where normal behaviour is well modelled (CAN signals, V2X tracks, the GPS filter). The evidence-novelty layer was dropped because it lowered held-out detection (section 11).\n\n"

    out += "### 1.2 Corrected V2X headline: a simulator-calibrated detector does not transfer to real traffic\n\n"
    out += para("The V2X physics stack calibrated on the simulated VeReMi traffic flags nearly every genuine message of real CAM traffic (V2AIX, Aachen region).",
                "Re-calibrated per deployment on that deployment's own genuine validation recordings, the false-alarm rate returns to the budget. The honest statement is therefore",
                "that detection needs a per-deployment calibration; the VeReMi numbers (section 5) are a benchmark, not a field result. Mobile and Stationary receivers are always separate.")
    rows = []
    for env in ("Mobile", "Stationary"):
        rows.append([env, c.pc(S3B, f"F2/{env}/fa_msg_A", 0), c.pc(S3B, f"F1/{env}/fa_msg_B", 2), c.num(S3B, f"F1/{env}/alarms_per_hour", 0),
                     c.pc(S3B, f"F1/{env}/genuine_senders_kval", 1), c.pc(S3B, f"I1/{env}/mean_scored_physics", 1)])
    out += "\n" + tbl(["receiver", "genuine messages flagged with the VeReMi calibration", "flagged after per-deployment calibration", "alarms per receiver-hour (after)", "genuine senders flagged (validation-chosen count)",
                       "injected attacks on real CAMs, mean detection of scored rows"], rows)
    out += "\nThe alarms that remain after calibration come from noise statistics of fast cars, parked-car position wobble and slow-urban heading noise, not from attacks (`reports/M1_V2X.md`, V2AIX addendum). The attacks are injected into real messages; no real V2X attack data exists.\n"
    return out


def sec_gps(c):
    f = "results/WP1/S8_kitti.json"
    A = "results/WP1/S8_acceptance.json"
    out = para("Source: `reports/M1_GPS.md`; numbers from `results/WP1/S8_kitti.json` (one test pass of seven KITTI drives), `S8_acceptance.json`, `S8_external.json`. Protocol: receiver, odometry and compass noise are simulated on",
               "top of the RTK reference, six attacks (two of them physically consistent and never seen by the combiner), thresholds by leave-one-drive-out, operating point a fixed one-percent false-alarm budget per layer.")
    out += "\n#### Pre-registered rules\n\n" + tbl(["id", "requirement", "observed", "verdict"], [r[:4] for r in RULES_CACHE["gps"]])
    out += "\n#### Headline: default stack of sixteen layers (noisy-or, log form), test drives\n\n"
    rows = []
    names = [("drift", "drift"), ("accel_drift", "accelerating drift"), ("jump", "jump"), ("freeze", "freeze"), ("doppler_spoof", "Doppler-consistent spoof (zero-shot)"), ("meaconing", "meaconing (zero-shot)")]
    for k, label in names:
        rows.append([label, c.pc(f, f"deployed/run_detected/{k}") + " " + c.ci(f, f"deployed/bootstrap/drives/{k}"), c.pc(f, f"deployed/row_detection/{k}", 0),
                     c.num(f, f"deployed/summary/delays/{k}/delays_q10_25_50_75_90_s/2", 0), c.pc(f, f"deployed/summary/delays/{k}/within_10s", 0)])
    rows.append(["mean of the six", c.pc(f, "deployed/mean_run_detected") + " " + c.ci(f, "deployed/bootstrap/drives/mean_run"), c.pc(f, "deployed/mean_row_detection", 0), "-", "-"])
    out += tbl(["attack", "run-level detection, 95% interval over test drives", "row-level", "median delay (s)", "detected within ten seconds"], rows)
    out += "\nClean-run false alarms " + c.pc(f, "deployed/fa_clean_runs", 2) + " " + c.ci(f, "deployed/bootstrap/drives/fa_clean_runs", 1) + " (drives), worst drive " + c.pc(f, "deployed/worst_drive_fa", 2) + "; AUC "
    out += c.num(f, "deployed/auc_row_level", 3) + " " + c.ci(f, "deployed/bootstrap/drives/auc", 2, pct=False) + ". Gain over the v2 rule B2 on the same runs: " + c.pp(f, "deployed/vs_B2_paired/mean_run_diff") + " " + c.ci(f, "deployed/vs_B2_paired/mean_run_diff_ci") + ".\n"
    out += "\nSlow drift below half a metre per second within thirty seconds (the pre-set target) is untestable on KITTI: " + c.cnt(f, "deployed/summary/slow_drift_lt_0.5_within_30s/runs") + " slow-drift runs, " + c.cnt(f, "deployed/summary/slow_drift_lt_0.5_within_30s/runs_with_full_30s") + " of them with thirty seconds after onset.\n"
    out += "\n#### What each layer catches (own one-percent threshold, run-level detection; test)\n\n"
    layers = [("gps.jerk", "kinematic limit: only gross inconsistency"), ("gps.vel_pos_consistency", "receiver velocity must equal the derivative of its position"),
              ("gps.dr_resid_10", "dead reckoning: odometry plus compass against GPS displacement (v2 rule B2)"), ("gps.ekf_nis", "EKF innovation: IMU, odometry, heading, Doppler arbitrate"),
              ("gps.cusum_ekf", "memory: small consistent innovations accumulate"), ("gps.cusum_dr", "same on a branch that stops trusting GPS once suspicious"),
              ("gps.lidar_z_3", "LiDAR odometry as an independent witness the spoofer does not control")]
    rows = []
    for k, why in layers:
        p = f"layers_test/{k}/"
        rows.append([k, why, c.pc(f, p + "fa_clean_runs", 2)] + [c.pc(f, p + f"run_detected/{a}", 0) for a, _ in names] + [c.pc(f, p + "mean_run_detected", 1)])
    rows.append(["combined", "noisy-or, log form", c.pc(f, "deployed/fa_clean_runs", 2)] + [c.pc(f, f"deployed/run_detected/{a}", 0) for a, _ in names] + [c.pc(f, "deployed/mean_run_detected", 1)])
    out += tbl(["layer", "physics", "FA", "drift", "accel", "jump", "freeze", "Doppler", "meacon", "mean"], rows)
    out += "\n#### Ablation (test): learned and map layers do not earn their place\n\n"
    rows = [["default stack", c.pc(f, "ablation_test/all/mean_run_detected"), c.pc(f, "ablation_test/all/fa_clean_runs", 2), "-"]]
    for k, label in (("all_but_gps.dr_resid_10", "without dead reckoning"), ("all_but_gps.ekf_nis", "without EKF NIS"), ("all_but_gps.cusum_dr", "without dead-reckoning CUSUM"),
                     ("plus_opt.l3", "plus normal-only model L3"), ("plus_opt.l4_c2", "plus supervised L4"), ("plus_opt.map_dist", "plus map matching"), ("plus_opt.cusum_lidar", "plus LiDAR CUSUM")):
        rows.append([label, c.pc(f, f"ablation_test/{k}/mean_run_detected"), c.pc(f, f"ablation_test/{k}/fa_clean_runs", 2),
                     c.derived("difference to default stack", [(f, f"ablation_test/{k}/mean_run_detected"), (f, "ablation_test/all/mean_run_detected")], lambda v: 100 * (v[0] - v[1]), lambda x: f"{x:+.1f} points")])
    out += tbl(["configuration", "mean run-level detection", "clean-run FA", "change"], rows)
    out += "\n#### External tests\n\n"
    out += para("UAV live spoofing flight (one flight, PX4): the combined detector alarms at the first spoofed fix (" + c.num(A, "G8_uav/delay_s", 4) + " s after onset) and flags every spoofed fix, but raises",
                c.cnt(A, "G8_uav/pre_onset_alarms") + " alarms before onset (" + c.pc(A, "G8_uav/pre_onset_fa", 2) + ", " + c.ci(A, "G8_uav/wilson95", 1) + "): above the bound. AV-GPS: nothing usable; its spoofed sessions are no-fix placeholders",
                "and the combined AUC " + c.num(A, "G9_avgps/combined_auc", 3) + " equals the top of the label-permutation null " + c.ci(A, "G9_avgps/auc_null_q05_q95", 2, pct=False) + ".")
    out += "\nNot caught: slow drift in the available window; Doppler-consistent spoofs and meaconing below roughly one metre per second; attacks are synthetic and non-adaptive.\n"
    return out


def sec_can(c):
    f = "results/WP2/s7_test.json"
    o = "results/WP2/s7_others.json"
    out = para("Source: `reports/M1_CAN.md`; numbers from `results/WP2/s7_test.json` (ROAD test captures, one vehicle), `s7_others.json`, `s7_accel.json`. Windows are one second; calibration by leave-one-capture-out;",
               "default stack L1 specification rules + L3c per-signal predictors + L3d reverse-light rule, combiner max. The ROAD test exposure count is stored in the file: ", c.cnt(f, "exposure"), "scorings.")
    out += "\n#### Pre-registered rules\n\n" + tbl(["id", "requirement", "observed", "verdict"], [r[:4] for r in RULES_CACHE["can"]])
    out += "\n#### Per capture (combined stack, window level)\n\n"
    rows = []
    for cap in [k for k in c.keys(f, "configs/all/per_capture") if not k.startswith("ambient")]:
        p = f"configs/all/per_capture/{cap}/"
        rows.append([cap.replace("_attack_3", "").replace("_attack", ""), c.yn(f, p + "detected"), c.pc(f, p + "window_recall", 0), c.num(f, p + "delay_s", 2)])
    out += tbl(["capture", "detected", "window recall", "delay (s)"], rows)
    out += "\n#### Ablation and false alarms (ROAD test)\n\n"
    rows = []
    for cfg, label in (("all", "L1 + L3c + L3d (default)"), ("only_L1", "L1 alone"), ("only_L3c", "L3c alone"), ("only_L3d", "L3d alone"), ("all_but_L1", "without L1 (information only)"), ("all_but_L3c", "without L3c"), ("all_but_L3d", "without L3d"),
                       ("all+L2b (optional)", "plus L2b relations (optional)")):
        p = f"configs/{cfg}/"
        rows.append([label, c.pc(f, p + "clean_fa_pooled", 2) + " " + c.ci(f, p + "clean_fa_ci95_cluster_bootstrap", 1), c.num(f, p + "false_alerts_per_hour", 0), c.cnt(f, p + "masquerade_detected"), c.cnt(f, p + "plain_detected")])
    out += tbl(["configuration", "clean-window FA [interval]", "false alerts per hour", "masquerade detected", "injected detected"], rows)
    out += "\nPer clean capture (combined stack): "
    parts = []
    for cap in c.keys(f, "configs/all/ambient_fa"):
        parts.append(cap.replace("ambient_", "").replace("_", " ") + " " + c.pc(f, f"configs/all/ambient_fa/{cap}", 1))
    out += "; ".join(parts) + ".\n"
    out += "\n#### Other data sets (L1 only: no signal definitions exist for them)\n\n"
    rows = []
    for k in ("DoS", "Fuzzy", "RPM", "Gear"):
        rows.append([f"Car-Hacking {k}", c.pc(o, f"carhacking/per_attack/{k}/window_recall", 1), c.pc(o, "carhacking/clean_fa", 1)])
    for k, label in (("A_known", "can-train-and-test, zero-shot calibration, known vehicles"), ("A_unknown", "can-train-and-test, zero-shot calibration, UNKNOWN vehicles"),
                     ("B_known", "can-train-and-test, on-vehicle calibration, known vehicles"), ("B_unknown", "can-train-and-test, on-vehicle calibration, UNKNOWN vehicles")):
        rows.append([label, c.pc(o, f"d11_summary/{k}/mean_window_recall", 1) + " (" + c.cnt(o, f"d11_summary/{k}/files_detected") + " of " + c.cnt(o, f"d11_summary/{k}/files_with_attack") + " files)",
                     c.pc(o, f"d11_summary/{k}/clean_fa_pooled", 2) + " " + c.ci(o, f"d11_summary/{k}/clean_fa_ci95_bootstrap_over_files", 1)])
    out += tbl(["data set / regime", "window recall", "clean false alarms"], rows)
    out += "\nZero-shot calibration fails on an unknown vehicle (every clean window alarms); a short clean calibration period on the target vehicle brings it near the budget.\n"
    out += "\nNot met: the false-alarm rules (C3, C4); every combined false alarm comes from the specification rules (bus load, period) on legitimate traffic bursts. The accelerator captures carry no injected frames, so there is no fresh labelled holdout.\n"
    return out


def sec_net(c):
    f = "results/WP4/s7_d10.json"
    f2 = "results/WP4/s7_d23.json"
    short = {"Bot": "Bot", "DDoS-LOIC-HTTP": "LOIC-HTTP", "DoS-GoldenEye": "GoldenEye", "DoS-Hulk": "Hulk", "DoS-SlowHTTPTest": "SlowHTTP", "DoS-Slowloris": "Slowloris",
             "FTP-Patator": "FTP", "SSH-Patator": "SSH", "PortScan": "PortScan", "Web-BruteForce": "Web-BF", "Web-XSS": "Web-XSS"}
    out = para("Source: `reports/M1_NET.md`; numbers from `results/WP4/s7_d10.json` (D10, CICIDS2017 from an unofficial mirror, time-split, one test run) and `s7_d23.json` (D23, CSE-CIC-IDS2018 as external test).",
               "Stack H is zero-shot and topology-free; stack O is refit on the target network's warm-up. Test stream: ", c.cnt(f, "n_rows"), "flows in", c.cnt(f, "n_blocks"), "ten-minute blocks.")
    out += "\n#### Pre-registered rules\n\n" + tbl(["id", "requirement", "observed", "verdict"], [r[:4] for r in RULES_CACHE["net"]])
    out += "\n#### Stacks (headline false alarms exclude the audited Infiltration scan; the published-label figure is shown)\n\n"
    rows = []
    for k, label in (("H", "H zero-shot"), ("O", "O on-network"), ("O+L4", "O + supervised L4 (in-window ceiling)"), ("O+topology", "O + topology allow-lists (lab artefact, not a detection claim)")):
        p = f"stacks/{k}/published/"
        rows.append([label, c.pc(f, p + "fa", 2) + " " + c.ci(f, p + "fa_ci", 2), c.pc(f, p + "fa_pub", 2), c.pc(f, p + "macro", 1) + " " + c.ci(f, p + "macro_ci", 0), c.num(f, p + "auc", 4) if c.raw(f, p + "auc") is not MISSING else "-"])
    out += tbl(["stack", "FA (headline) [interval]", "FA with published labels", "macro detection of eleven families [interval]", "AUC"], rows)
    out += "\n#### Per family, test (detection; intervals are over ten-minute blocks and degenerate because most families are one attack run)\n\n"
    rows = []
    for fam, sn in short.items():
        rows.append([sn, c.cnt(f, f"stacks/H/published/n/{fam}"), c.pc(f, f"stacks/H/published/detection/{fam}", 0) + " " + c.ci(f, f"stacks/H/published/detection_ci/{fam}"),
                     c.pc(f, f"stacks/O/published/detection/{fam}", 0), c.pc(f, f"stacks/O+L4/published/detection/{fam}", 0)])
    out += tbl(["family", "flows", "H [interval]", "O", "O + L4"], rows)
    out += "\n#### Leave-one-attack-out (the generalisation number)\n\n"
    rows = []
    srcs = []
    for fam in short:
        if c.raw(f, f"loao/{fam}/members") == [fam]:
            rows.append([short[fam]] + [c.pc(f, f"loao/{fam}/stacks/{s}/detection/{fam}", 0) for s in ("H", "O", "O+L4", "L4 alone")])
            srcs.append(fam)
    out += tbl(["held-out family", "H", "O", "O + L4", "L4 alone"], rows)
    mean_row = ["mean of the single hold-outs"]
    for s in ("H", "O", "O+L4", "L4 alone"):
        mean_row.append(c.derived(f"mean LOAO detection {s}", [(f, f"loao/{fam}/stacks/{s}/detection/{fam}") for fam in srcs], lambda v: sum(v) / len(v) * 100, lambda x: f"{x:.1f}%"))
    out += "\n" + tbl(["", "H", "O", "O + L4", "L4 alone"], [mean_row])
    out += "\nThe benign-fitted rule layers detect a family without having seen it because they count what the attack must do (retries to one service, fan-out, rate). The supervised layer transfers only between look-alike families. Bot has a fixed flow shape (one botnet implementation) and is not detected by any stack.\n"
    out += "\n#### Other dataset (D23, a different flow-extractor run)\n\n"
    rows = [["flag layer alone, every day, zero-shot", c.pc(f2, "zero_shot_tcp_flags_all_days/fa", 1) + " " + c.ci(f2, "zero_shot_tcp_flags_all_days/fa_ci", 0), "-"],
            ["H, the one day with addresses, zero-shot (stage stream)", c.pc(f2, "zero_shot_tue/stage_stream/H/fa", 1), c.pc(f2, "zero_shot_tue/stage_stream/H/macro", 1)],
            ["H without the flag layer, same day (stage stream)", c.pc(f2, "zero_shot_tue/stage_stream/H without tcp_flags/fa", 1), c.pc(f2, "zero_shot_tue/stage_stream/H without tcp_flags/macro", 1)],
            ["O refit on that network's warm-up, same day", c.pc(f2, "on_network/tue/O/fa", 2), c.pc(f2, "on_network/tue/O/macro", 1)],
            ["O (flow level), all days, refit", c.pc(f2, "on_network/flow_all_days/O_flow/fa", 2), c.pc(f2, "on_network/flow_all_days/O_flow/macro", 1)]]
    out += tbl(["configuration", "benign false alarms", "mean detection of that day's families"], rows)
    out += "\nThe flag columns differ between the two flow-extractor runs, so the flag layer does not transfer; the destination baseline needs a warm-up of about an hour or more on the target network.\n"
    return out


def sec_v2x(c):
    f = "results/WP5/s6_veremi.json"
    a = "results/WP5/s3b_acceptance.json"
    out = para("Source: `reports/M1_V2X.md` and its V2AIX addendum; numbers from `results/WP5/s6_veremi.json` (VeReMi Extension, simulated, time-block split, second exposure of the test split), `s6_acceptance.json`, `s3b_acceptance.json`.",
               "Frozen domain output = physics-only stack (L1 + L2 + L3); L4 is optional and not validated (null control fails).")
    out += "\n#### Pre-registered rules\n\n" + tbl(["id", "requirement", "observed", "verdict"], [r[:4] for r in RULES_CACHE["v2x"]])
    out += "\n#### Ablation of the deployable stack (VeReMi test; intervals over test time blocks)\n\n"
    rows = []
    for g in ("L1", "L2", "L3", "L4-scored", "L1+L2+L3+L4", "all but L1", "all but L2", "all but L3", "all but L4 (= L1+L2+L3)"):
        p = f"groups/{g}/"
        rows.append([g, c.pc(f, p + "fa_msg/p", 1), c.pc(f, p + "mean_msg_scored/seen/p", 1) + " " + c.ci(f, p + "mean_msg_scored/seen/ci", 1), c.pc(f, p + "msg_scored/06_ConstSpeedOffset/p", 1),
                     c.pc(f, p + "msg_scored/17_DataReplaySybil/p", 1), c.pc(f, p + "kval/fa_sender/p", 1) + " / " + c.pc(f, p + "kval/mean_sender/seen/p", 1)])
    out += tbl(["configuration", "FA messages", "mean seen classes, scored rows [interval]", "unseen class 6", "unseen class 17", "sender level: FA / mean seen"], rows)
    out += "\n#### Full stack per attack class (VeReMi test)\n\n"
    rows = []
    g = "groups/L1+L2+L3+L4/"
    for cls in c.raw(f, g + "classes") or []:
        rows.append([cls, c.pc(f, g + f"scored_share/{cls}", 0), c.pc(f, g + f"msg_scored/{cls}/p", 1), c.pc(f, g + f"msg_all/{cls}/p", 1) + " " + c.ci(f, g + f"msg_all/{cls}/ci", 1), c.pc(f, g + f"kval/sender/{cls}/p", 1)])
    out += tbl(["class", "rows with a predecessor", "message detection, scored rows", "message detection, all rows [interval]", "sender level (validation-chosen count)"], rows)
    out += "\nNot caught: a consistently shifted position (class ConstPosOffset) and EventualStop need an absolute reference such as the receiver's own position. The delayed-message class is an artefact (zero placeholder positions), not claimed.\n"
    out += "\n#### Real CAM traffic (V2AIX addendum, Mobile and Stationary receivers separately)\n\n"
    rows = []
    for env in ("Mobile", "Stationary"):
        rows.append([env, c.pc(a, f"F2/{env}/fa_msg_A", 0), c.pc(a, f"F1/{env}/fa_msg_B", 2), c.num(a, f"F1/{env}/alarms_per_hour", 0), c.pc(a, f"F1/{env}/genuine_senders_k3", 1) + " / " + c.pc(a, f"F1/{env}/genuine_senders_kval", 1),
                     c.pc(a, f"I1/{env}/mean_scored_physics", 1) + " (VeReMi, same types: " + c.pc(a, f"I1/{env}/veremi_same_types", 1) + ")", c.num(a, f"R2/{env}/range_threshold_km", 1) + " km, far-offset " + c.pc(a, f"R2/{env}/far_offset_detection_msg", 0),
                     c.pc(a, f"R3/{env}/ghost_tracks_detected", 0)])
    out += tbl(["receiver", "FA, VeReMi calibration", "FA, per-deployment calibration", "alarms per hour", "genuine senders flagged: three alarms / chosen count", "injected attacks, mean scored detection", "acceptance range threshold", "ghost tracks caught by sudden-appearance"], rows)
    out += "\nThe sudden-appearance check fails on real data (genuine first messages arrive close by). The acceptance-range gate for Stationary receivers was defective as pre-registered and is reported next to its amended form (`reports/WP5_S3b.md`).\n"
    return out


def pending(c, title, note):
    found = [p for p in PENDING_FILES[title] if c.exists(p)]
    if not found:
        c.pending.append(title)
        return "**PENDING.** " + note + " This section fills itself from the first of these files that exists: " + ", ".join(f"`{p}`" for p in PENDING_FILES[title]) + ".\n"
    f = found[0]
    rows = []
    for k in c.keys(f):
        v = c.raw(f, k)
        if isinstance(v, dict) and ("met" in v or "verdict" in v):
            scal = [kk for kk, vv in v.items() if isinstance(vv, (int, float)) and not isinstance(vv, bool)][:4]
            vals = "; ".join(f"{kk} " + c.num(f, f"{k}/{kk}", 3) for kk in scal)
            rows.append([k, c.txt(f, f"{k}/rule") if "rule" in v else "-", vals or "-", c.met(f, f"{k}/met") if "met" in v else c.txt(f, f"{k}/verdict")])
    return f"Filled from `{f}`.\n\n" + tbl(["item", "rule", "values", "verdict"], rows)


def sec_lidar(c):
    c.closed = False
    out = pending(c, "M1-LiDAR", "M1-LiDAR is open: WP3 S5 (free space / occlusion) and S6 (background model and tracking) are running, S7 and the combined S9 test run follow.")
    out += "\nUntil it closes, the M2 system uses an INTERIM LiDAR input: the label-free L1 geometry union only (the supervised v2-baseline model caused most of the first fusion's false alarms). LiDAR attack numbers in section 7 are therefore interim and weak by design.\n"
    c.closed = True
    return out


def sec_m2(c):
    f = "results/WP6/s5_test.json"
    a4 = "results/WP6/s4_acceptance.json"
    out = para("Source: `reports/M2.md`; numbers from `results/WP6/s5_test.json` and `s5_acceptance.json` (the single labelled test run of the frozen system), `s4_test.json`, `s4_acceptance.json` (held-out types). The system is five frozen domains plus the cross-domain layer",
               "into one label-free fusion, a temporal correlator and a response policy. No public dataset has all five domains on one car: every composite places each domain's own test stream on a common clock, so cross-domain correlations are constructed except inside the vehicle block (GPS, IMU, LiDAR odometry, CAN speed).",
               "K = KITTI-based composites, C = comma2k19-based composites (cross-domain only for the vehicle block). LiDAR is INTERIM.")
    out += "\n#### Pre-registered rules (S5; observed values as stored: fractions, events per hour)\n\n" + tbl(["id", "requirement", "observed", "verdict"], [[r[0], r[1], r[4], r[2]] for r in RULES_CACHE["m2"]])
    out += "\n#### Headline (test, one run; intervals are cluster bootstrap over vehicle groups)\n\n"
    rows = [["raw clean-tick false alarms", c.pc(f, "system/K/fa_tick", 2) + " " + c.ci(f, "acceptance/A1_raw_tick_fa/K_ci", 1), c.pc(f, "system/C/fa_tick", 2) + " " + c.ci(f, "acceptance/A1_raw_tick_fa/C_ci", 1)],
            ["alert events per clean hour (after the correlator)", c.num(f, "system/K/events_per_hour", 1) + " " + c.ci(f, "acceptance/A2_events_per_clean_hour/K_ci", 0, pct=False), c.num(f, "system/C/events_per_hour", 1) + " " + c.ci(f, "acceptance/A2_events_per_clean_hour/C_ci", 0, pct=False)],
            ["alert events per clean hour without the correlator", c.num(f, "system/K/correlator_off/events_per_hour", 1), c.num(f, "system/C/correlator_off/events_per_hour", 1)],
            ["WARN / DEGRADE / SAFE_STOP per clean hour", c.num(f, "system/K/clean_response_per_hour/WARN", 1) + " / " + c.num(f, "system/K/clean_response_per_hour/DEGRADE", 1) + " / " + c.num(f, "system/K/clean_response_per_hour/SAFE_STOP", 1),
             c.num(f, "system/C/clean_response_per_hour/WARN", 1) + " / " + c.num(f, "system/C/clean_response_per_hour/DEGRADE", 1) + " / " + c.num(f, "system/C/clean_response_per_hour/SAFE_STOP", 1)],
            ["mean event detection, single-domain attacks", c.pc(f, "system/K/mean_event_detection_single") + " " + c.ci(f, "system/K/ci_single_event/mean"), c.pc(f, "system/C/mean_event_detection_single") + " (not informative: most clean composites alert)"],
            ["held-out (zero-day) types", c.pc(f, "system/K/mean_event_detection_heldout") + " " + c.ci(f, "system/K/ci_heldout_event/mean"), c.pc(f, "system/C/mean_event_detection_heldout")],
            ["blame of detected single-domain events: correct / wrong / undecided", c.pc(f, "system/K/blame_single_pooled/correct") + " / " + c.pc(f, "system/K/blame_single_pooled/wrong") + " / " + c.pc(f, "system/K/blame_single_pooled/undecided"),
             c.pc(f, "system/C/blame_single_pooled/correct") + " / " + c.pc(f, "system/C/blame_single_pooled/wrong") + " / " + c.pc(f, "system/C/blame_single_pooled/undecided")],
            ["alert events with an explanation", c.cnt(f, "system/K/explanations/with_explanation") + " of " + c.cnt(f, "system/K/explanations/events"), c.cnt(f, "system/C/explanations/with_explanation") + " of " + c.cnt(f, "system/C/explanations/events")]]
    out += tbl(["quantity", "K", "C"], rows)
    out += "\nFalse alarms do not transfer from validation to test, and the event rate is far above what a vehicle could accept; the milestone is NOT MET and the numbers stand.\n"
    out += "\n#### Event detection by attacked domain (K) and ablation\n\n"
    rows = []
    for d in c.keys(f, "system/K/event_detection_by_attacked_domain"):
        wo = f"system/K/ablation/without {d}/mean_event_detection_single" if d != "cross" else "system/K/ablation/without cross/mean_event_detection_single"
        rows.append([d, c.pc(f, f"system/K/event_detection_by_attacked_domain/{d}", 0), c.pc(f, wo, 1)])
    out += tbl(["attacked domain", "event detection", "mean single-domain detection when this domain is removed"], rows)
    base = c.raw_val(f, "system/K/mean_event_detection_single")
    wo = {k.replace("without ", ""): c.raw_val(f, f"system/K/ablation/{k}/mean_event_detection_single") for k in c.keys(f, "system/K/ablation")}
    worst = min(wo, key=lambda k: wo[k]) if wo else "n/a"
    gain = [d for d in wo if wo[d] is not None and base is not None and wo[d] > base]
    out += "\nRemoving the domain with the lowest value costs the most detection: " + worst + ". Removing a domain that RAISES the mean means it costs false-alarm budget and catches little: " + (", ".join(gain) or "none") + ".\n"
    out += "\n#### Held-out types (S4) and the zero-day claim\n\n" + tbl(["item", "requirement", "observed", "verdict"], [[i, c.txt(a4, i + "/rule"), observed(c, a4, i), c.met(a4, i + "/met")] for i in c.keys(a4) if isinstance(c.raw(a4, i), dict) and "rule" in c.raw(a4, i)])
    out += "\n#### M2 addendum (after M1-LiDAR)\n\n"
    c.closed = False
    out += pending(c, "M2 addendum", "The addendum replaces the interim LiDAR input, decides event blame by majority and requires corroboration by two domains for SAFE_STOP; it is built on new random pairings of the test streams.")
    c.closed = True
    return out


def sec_m3(c):
    s1 = "results/WP7/S1_acceptance.json"
    out = para("The streaming runtime (WP7 S1, `reports/WP7_S1.md`) is finished: every frozen domain runs as a stream and gives exactly the evidence of its batch code on validation data. This is engineering evidence, not a detection result.")
    rows = []
    for d in ("gps", "can", "v2x", "cross", "lidar_interim"):
        rows.append([d, c.met(s1, f"A1/{d}/met"), c.met(s1, f"A2/{d}/met"), c.met(s1, f"A3/{d}/met")])
    out += "\n" + tbl(["domain", "stream equals batch", "causal (truncation test)", "reset"], rows)
    out += "\nThe network runner was added in S1b (`results/WP7/S1_acceptance.json`, section S1b). LiDAR and the cross-domain object are interim or runtime-test objects, labelled in every evidence record.\n"
    out += "\n#### Simulation (WP7 S2)\n\n"
    c.closed = False
    out += pending(c, "M3 simulation", "The simulation runs all five domains as real streams with coordinated multi-domain scenarios and first-alert delay per block; it waits for M1-LiDAR and the M2 addendum.")
    c.closed = True
    return out


def sec_v2_side(c):
    g = "results/WP1/S8_kitti.json"
    o = "results/WP2/s7_others.json"
    t = "results/WP2/s7_test.json"
    R = "results/WP7/S3_registry.json"
    f = "results/WP4/s7_d10.json"
    m = "results/WP6/s5_test.json"
    out = para("Every row states whether the two sides measure the same thing. Where they do not, the v2 number is shown only so nobody compares the wrong pair.")
    out += "\n#### GPS: comparable (same synthetic runs, same test drives)\n\n"
    rows = [["v2 dead-reckoning rule B2", c.pc(g, "layers_test/gps.dr_resid_10/mean_run_detected"), c.pc(g, "layers_test/gps.dr_resid_10/fa_clean_runs", 2)],
            ["v3 default stack", c.pc(g, "deployed/mean_run_detected"), c.pc(g, "deployed/fa_clean_runs", 2)]]
    out += tbl(["", "mean run-level detection (six attacks)", "clean-run FA"], rows)
    out += "\nCaveat: the six-attack mean includes the Doppler-consistent spoof and meaconing, which v2 never faced; the v3 gain over B2 is " + c.pp(g, "deployed/vs_B2_paired/mean_run_diff") + " " + c.ci(g, "deployed/vs_B2_paired/mean_run_diff_ci") + " with a higher false-alarm rate.\n"
    out += "\n#### CAN: comparable captures, not comparable operating points (ROAD test)\n\n"
    rows = []
    for k, label in (("R1_val_fpr_0.001", "v2 timing model at its strictest target"), ("R1_val_fpr_0.01", "v2 timing model at its one-percent target"), ("R2_val_fpr_0.01", "v2 payload model at its one-percent target")):
        rows.append([label, c.txt(o, f"v2_road/{k}/captures_detected") + " captures", c.pc(o, f"v2_road/{k}/test_window_fpr", 2), c.num(o, f"v2_road/{k}/false_alerts_per_hour", 0)])
    rows.append(["v3 default stack", c.cnt(t, "configs/all/masquerade_detected") + " masquerade + " + c.cnt(t, "configs/all/plain_detected") + " injected", c.pc(t, "configs/all/clean_fa_pooled", 2), c.num(t, "configs/all/false_alerts_per_hour", 0)])
    out += tbl(["", "captures detected (of the eleven)", "clean-window FA", "false alerts per hour"], rows)
    out += "\nCaveat: v3 buys the masquerade and coolant captures with false alarms; the v2 timing model at its strictest target has no false alerts and is not beaten on that axis. The v2 payload model alarms on real reverse driving.\n"
    out += "\n#### Network: NOT comparable\n\n"
    rows = [["v2 accuracy / macro F1, random split after de-duplication, 7 classes".replace("7 classes", "seven classes"), c.pc(R, "v2_reference/net_accuracy_random_split/value", 2) + " / " + c.pc(R, "v2_reference/net_macro_f1_random_split/value", 2), "-"],
            ["v2 unseen Bot: supervised / one-class SVM (FA " + c.pc(R, "v2_reference/net_ocsvm_fa/value", 1) + ")", c.pc(R, "v2_reference/net_unseen_bot_supervised/value", 1) + " / " + c.pc(R, "v2_reference/net_unseen_bot_ocsvm/value", 1), "-"],
            ["v2 unseen web attacks: supervised / one-class SVM", c.pc(R, "v2_reference/net_unseen_web_supervised/value", 1) + " / " + c.pc(R, "v2_reference/net_unseen_web_ocsvm/value", 1), "-"],
            ["v3 zero-shot stack H, time split", "macro " + c.pc(f, "stacks/H/published/macro", 1), "FA " + c.pc(f, "stacks/H/published/fa", 2)],
            ["v3 unseen Bot (leave-one-attack-out), H", c.pc(f, "loao/Bot/stacks/H/detection/Bot", 0), "-"],
            ["v3 unseen web attacks (leave-one-attack-out), H: BruteForce / XSS", c.pc(f, "loao/Web-BruteForce/stacks/H/detection/Web-BruteForce", 0) + " / " + c.pc(f, "loao/Web-XSS/stacks/H/detection/Web-XSS", 0), "-"]]
    out += tbl(["", "value", "false alarms"], rows)
    out += "\nCaveat: the v2 sample is not a subset of either official CICIDS2017 file set, the split differs (random vs time), the class set differs, and the v2 near-perfect accuracy was probably helped by flows of one attack run on both sides of the split. v3 does not reproduce v2's one-class result on unseen web attacks and does not claim it.\n"
    out += "\n#### V2X: no v2 baseline (new domain). LiDAR: PENDING (M1-LiDAR).\n\n"
    out += "\n#### System: NOT like-for-like\n\n"
    v = "v2/simulation_with_correlator/"
    rows = [["v2 live simulation (supervised meta-classifier, long attack blocks)", c.pc(m, v + "accuracy", 1) + " accuracy", c.pc(m, v + "fpr", 2), c.pc(m, v + "recall", 1) + " per row"],
            ["v3 M2 system, K composites (label-free fusion, held-out types, vehicle groups)", "-", c.pc(m, "system/K/fa_tick", 2), c.pc(m, "system/K/tick_recall_attack_ticks", 1) + " per tick"]]
    out += tbl(["", "accuracy", "false alarms per row / tick", "recall"], rows)
    out += "\nCaveat: v3 is not better than v2 on v2's own view. v2 used a supervised meta-classifier on the tested classes, long attack blocks and random halves; v3 measures harder things (held-out types, group splits, events per clean hour).\n"
    return out


def sec_exposure(c):
    R = "results/WP7/S3_registry.json"
    rows = []

    def reg(key, label, what):
        q = c.raw_val(R, f"exposure/{key}/qualifier")
        return [label, ((q + " ") if q else "") + c.cnt(R, f"exposure/{key}/value"), what]
    rows.append(reg("kitti_gps_test_drives", "KITTI test drives (GPS, LiDAR odometry)", "scorings of the seven test drives"))
    rows.append(["ROAD test captures (CAN)", c.cnt("results/WP2/s7_test.json", "exposure"), "scorings; stored in the final test file; burned for design"])
    rows.append(reg("carhacking_test_blocks", "Car-Hacking test blocks", "scorings"))
    rows.append(reg("d11_test_subsets", "can-train-and-test test subsets", "scorings"))
    rows.append(reg("d10_cicids2017_test", "CICIDS2017 test stage stream (D10)", "scorings"))
    rows.append(reg("d23_cse_cic_ids2018", "CSE-CIC-IDS2018 (D23, whole dataset as external test)", "scorings"))
    rows.append(reg("veremi_test", "VeReMi Extension test split", "scorings"))
    rows.append(reg("v2aix_test", "V2AIX test split (real CAMs)", "scorings"))
    rows.append(reg("comma2k19", "comma2k19 routes", "scorings"))
    rows.append(reg("fusion_composites", "fusion test composites", "scorings"))
    out = para("A test set that has been scored many times is no longer independent: its numbers should be read as optimistic by an unknown amount. No choice of the frozen systems used a test number after the verdict run of its own step, but the sets were looked at repeatedly across steps.")
    out += "\n" + tbl(["test set", "times scored", "unit"], rows)
    out += "\nThe fusion composites will be scored a fourth time by the planned M2 addendum, built from a new random pairing of the domain test streams. Re-fitting with `run_all.py --refit` adds exposures.\n"
    return out


def sec_negative(c):
    gk = "results/WP1/S8_kitti.json"
    gc = "results/WP1/S8_acceptance.json"
    s3 = "results/WP2/s3_road.json"
    s6 = "results/WP2/s6_road.json"
    v = "results/WP5/s6_acceptance.json"
    a4 = "results/WP6/s4_acceptance.json"
    m = "results/WP6/s5_test.json"
    net = "results/WP4/s7_d10.json"
    rows = []
    rows.append(["CAN clock-skew layer (attacker vs ECU clock drift)", "recall on attack windows " + c.pc(s3, "regimes/A/summary/can.l2a_skew/attack_window_recall", 1) + " at clean-window FA " + c.pc(s3, "regimes/A/summary/can.l2a_skew/fa_clean_rate", 1),
                 "dropped: the clock difference is below the jitter of the logged timestamps"])
    rows.append(["GPS normal-only model L3 added to the stack", "mean " + c.pc(gk, "ablation_test/plus_opt.l3/mean_run_detected") + " vs " + c.pc(gk, "ablation_test/all/mean_run_detected"), "out of the default stack (adds nothing)"])
    rows.append(["GPS supervised L4 added to the stack", "mean " + c.pc(gk, "ablation_test/plus_opt.l4_c2/mean_run_detected") + " vs " + c.pc(gk, "ablation_test/all/mean_run_detected") + "; shuffled-label AUC " + c.num(gc, "G6_shuffled_label_control/auc_mean", 2), "out of the default stack"])
    rows.append(["GPS map matching", "mean " + c.pc(gk, "ablation_test/plus_opt.map_dist/mean_run_detected") + " vs " + c.pc(gk, "ablation_test/all/mean_run_detected") + "; alone FA " + c.pc(gk, "layers_test/opt.map_dist/fa_clean_runs", 1) + ", worst drive " + c.pc(gk, "layers_test/opt.map_dist/worst_drive_fa", 0),
                 "dropped: centreline offsets and road-following spoofs"])
    rows.append(["V2X supervised L4 on seen classes", c.pc(v, "3a_no_loss_seen_scored/full") + " (full stack) vs " + c.pc(v, "3a_no_loss_seen_scored/base") + " (physics only); null model detects " + c.pc(v, "4_shuffled_control/detection_pooled") + " at " + c.pc(v, "4_shuffled_control/FA") + " FA",
                 "optional, marked not validated"])
    rows.append(["CAN supervised L4 (retrained v2 models)", "window-level shuffled-label AUC " + c.num(s6, "shuffle/can.l4_timing/mean_window_auc", 2) + " against the bound " + c.num(s6, "shuffle/can.l4_timing/bound", 2), "out of the default stack"])
    rows.append(["network supervised L4 on a family it has not seen", "Bot " + c.pc(net, "loao/Bot/stacks/L4 alone/detection/Bot", 0) + "; PortScan " + c.pc(net, "loao/PortScan/stacks/L4 alone/detection/PortScan", 0), "optional, for seen families only"])
    rows.append(["evidence-novelty layer in the system", "held-out detection " + c.num(a4, "Z5_novelty_layer/delta_heldout_points_K", 1) + " points (K), " + c.num(a4, "Z5_novelty_layer/delta_heldout_points_C", 1) + " points (C)", "dropped from the system"])
    rows.append(["interim LiDAR input in the fusion", "mean single-domain detection " + c.pc(m, "system/K/mean_event_detection_single") + " with, " + c.pc(m, "system/K/ablation/without lidar/mean_event_detection_single") + " without", "weak until M1-LiDAR closes"])
    out = para("Things that were built, tested and did not help. They are reported so nobody tries them again for the same reason.")
    return out + "\n" + tbl(["what", "evidence", "decision"], rows)


ARTEFACTS = [
    ("GPS", "The KITTI reference is RTK: without simulated receiver, odometry and compass noise every detector looks perfect.", "reports/M1_GPS.md"),
    ("GPS", "A short validation set does not transfer: thresholds calibrated on a few drives gave far more false alarms on test; leave-one-drive-out calibration fixes single layers.", "reports/M1_GPS.md"),
    ("GPS", "An ungated EKF absorbs most of a Doppler-consistent or meaconing offset within thirty seconds, so its innovation vanishes and it alarms only early; a CUSUM latches and can run away after false freezes.", "reports/M1_GPS.md"),
    ("GPS", "OpenStreetMap centrelines sit metres off the lane on some drives, so distance to road has a high false-alarm rate on one drive.", "reports/M1_GPS.md"),
    ("GPS", "AV-GPS spoofed sessions are no-fix placeholders (no satellites, HDOP at its maximum): a satellite rule detects them near-perfectly through that artefact only, and absolute-motion features encode platform speed.", "reports/M1_GPS.md"),
    ("GPS / all", "The common noisy-or saturates at exactly one with many correlated layers and then raises no alarm; the rank-equivalent log form is used.", "reports/M1_GPS.md; reports/REQUEST_WP1_combiner_noisy_or.md"),
    ("GPS", "Earlier harness steps split the combiner halves by run id (runs of one drive on both sides); a combiner that sees the new attack types inflates them.", "reports/M1_GPS.md"),
    ("CAN", "ROAD masquerade captures are edited copies: the legitimate frames of the injected ID are deleted afterwards. Accelerator captures contain no injected frames; the injection precedes the capture, so there is no onset and no window label.", "reports/M1_CAN.md"),
    ("CAN", "can-train-and-test has many byte-identical files across sets, timestamp inversions next to injected frames (the sign of the time step must never be a feature) and one subset labelled with the wrong vehicle in its readme.", "reports/M1_CAN.md"),
    ("CAN", "Car-Hacking injection is software-timed and sits in the first part of each file; test blocks are interleaved, so delay fields are not onset delays.", "reports/M1_CAN.md"),
    ("CAN", "The ROAD signal definitions are anonymised: the meaning of the wheel, speedometer, gear and light signals was derived from attack metadata and correlations, and the wheel-speed unit is an assumption to be calibrated against GPS or LiDAR speed.", "reports/M1_CAN.md"),
    ("CAN", "Winsorised scores create ties at the quantile (tie-safe thresholds above the cap alarm nothing); an unbounded CUSUM of a session offset grows without limit.", "reports/M1_CAN.md"),
    ("Network", "CICIDS2017 comes from an unofficial mirror: per-day and per-label counts equal the official labelled files and key columns match, but the v2 sample is not a subset of either official file set.", "reports/M1_NET.md"),
    ("Network", "Timestamps carry no AM/PM in either network dataset; early hours were fixed against the published attack schedule.", "reports/M1_NET.md"),
    ("Network", "De-duplication in the v2 style removes almost all PortScan flows; host-window layers must use the stream before de-duplication.", "reports/M1_NET.md"),
    ("Network", "Lab topology: nearly all attack flows go to one server from one attacker address; allow-list layers reach high detection only through that fact and are never quoted as detection.", "reports/M1_NET.md"),
    ("Network", "Label noise: the Thursday Infiltration file labels the compromised host's own network scan as benign, and some Bot beacons are unlabelled; both are audited and shown with and without correction.", "reports/M1_NET.md"),
    ("Network", "CSE-CIC-IDS2018 files end at the spreadsheet row limit as published, most files have no addresses, and the flag columns differ between the two flow-extractor runs.", "reports/M1_NET.md"),
    ("V2X", "VeReMi class 12 (delayed messages) contains placeholder positions at the origin; the apparent detection there comes from the rows after the jump, not from delay. It is not claimed.", "reports/M1_V2X.md"),
    ("V2X", "Several attack classes are mostly exact repeats of the previous position while genuine VeReMi traffic has none: a model fed zero residuals turns this into an attack flag. The deployable learned layer is trained and scored on rows with a moving predecessor only.", "reports/M1_V2X.md"),
    ("V2X", "Tampa BSM identifiers are per roadside unit and the same message was heard by several units: the first split leaked copies across sides and was fixed by de-duplication and a time-block split.", "reports/M1_V2X.md"),
    ("V2X", "Rate-dependent features carry one unseen VeReMi class through simulator identity churn; they do not transfer to real ten-hertz beacons and were dropped.", "reports/M1_V2X.md"),
    ("V2X", "V2AIX: sender-receiver distances are kilometres (explained by geometry and link budget, relay not excluded); the pre-registered range gate paired a generation-time position with a reception-time difference (a definition bug), so the amended gate is reported next to it; three speeds above seventy metres per second are real-data anomalies and are kept.", "reports/M1_V2X.md; reports/WP5_S3b.md"),
    ("Fusion", "Network evidence is final only after its five-minute bin closes, so network first-alert delays in the composites are optimistic.", "reports/M2.md"),
    ("Fusion", "Per-domain validation pools are small; every domain's clean test ticks score higher than validation, so false alarms did not transfer.", "reports/M2.md"),
]


def sec_artefacts(c):
    out = para("Pitfalls found while building the detectors, copied from the milestone reports so they are not rediscovered. Each names its source.")
    rows = [[d, t, f"`{s}`"] for d, t, s in ARTEFACTS]
    return out + "\n" + tbl(["domain", "artefact", "source"], rows)


def sec_limits(c):
    g = "results/WP1/S8_kitti.json"
    t = "results/WP2/s7_test.json"
    n = "results/WP4/s7_d10.json"
    v = "results/WP5/s6_acceptance.json"
    cl = "results/WP5/s3b_clean.json"
    m = "results/WP6/s5_test.json"
    items = [
        "GPS: " + c.cnt(g, "deployed/n_drives") + " test drives (runs of one drive are correlated phase offsets, " + c.cnt(g, "n_test_runs") + " runs in all); receiver noise, odometry error and every attack are simulated; one real attack flight; AV-GPS has placeholder spoofing; no real spoofing of a car exists in the data.",
        "CAN: one vehicle, three instances per attack type, " + c.cnt(t, "configs/all/clean_windows") + " clean windows from a handful of captures; no signal definitions for Car-Hacking or can-train-and-test; no labelled holdout for the accelerator attack; ten independent clean units give wide intervals.",
        "Network: every attack family is one run inside the test window (one to three ten-minute blocks of " + c.cnt(n, "n_blocks") + "), so family intervals are not independent-sample intervals; one lab topology; both datasets are lab traffic; the supervised layer's numbers are an in-window ceiling.",
        "V2X: VeReMi is simulated (" + c.cnt(v, "5_block_bootstrap_CIs/blocks") + " test time blocks for the intervals, which cover traffic variability only); real CAMs cover " + c.num(cl, "envs/Mobile/receiver_hours", 1) + " receiver-hours (Mobile) and " + c.num(cl, "envs/Stationary/receiver_hours", 1) + " (Stationary) of genuine traffic; all attacks on real traffic are injected.",
        "System: no public dataset has all five domains on one car; composites are built from each domain's own test stream; " + c.num(m, "system/K/clean_hours", 1) + " clean hours in the K composites; " + c.cnt(m, "system/K/ci_heldout_event/n_vehicle_groups") + " vehicle groups for the intervals; LiDAR is interim.",
        "All attacks are non-adaptive: no attacker knows the layers, thresholds or the other domains' witnesses.",
        "No claim is made about attacks on in-vehicle Ethernet (the automotive Ethernet dataset needs a login that was not available).",
    ]
    return "\n".join("- " + i for i in items) + "\n"


def sec_repro(c):
    return para("Everything in this file is regenerated by `python make_report.py` from the JSON files named in the appendix. The pipeline is `python run_all.py` (see `README.md`):",
                "`--list`, `--dry-run`, `--check` (frozen objects reproduce their saved freeze values), `--refit` (re-fits and one-shot test runs; each adds a test exposure, section 10).",
                "Datasets are not redistributed; V2AIX is non-commercial research data that must not be redistributed, and the CICIDS2017 files come from an unofficial mirror.")


# ------------------------------------------------------------ assembly
RULES_CACHE = {}


def build(root=ROOT):
    c = Ctx(root)
    RULES_CACHE.clear()
    RULES_CACHE.update({"gps": gps_rules(c), "can": can_rules(c), "net": net_rules(c), "v2x": v2x_rules(c), "m2": m2_rules(c)})
    secs = [
        ("1. Status and the two corrected claims", lambda: sec_status(c, RULES_CACHE) + "\n" + sec_claims(c)),
        ("2. M1-GPS: GPS spoofing by physics and consistency", lambda: sec_gps(c)),
        ("3. M1-CAN: CAN intrusion by specification rules and signal redundancy", lambda: sec_can(c)),
        ("4. M1-NET: network intrusion by host time-window logic and flow shape", lambda: sec_net(c)),
        ("5. M1-V2X: misbehaving V2X senders", lambda: sec_v2x(c)),
        ("6. M1-LiDAR: LiDAR phantom and tamper detection", lambda: sec_lidar(c)),
        ("7. M2: cross-domain consistency and system fusion (LiDAR interim)", lambda: sec_m2(c)),
        ("8. M3: system runtime and simulation", lambda: sec_m3(c)),
        ("9. v2 side by side, with the comparability caveats", lambda: sec_v2_side(c)),
        ("10. Test-exposure counts", lambda: sec_exposure(c)),
        ("11. Negative results", lambda: sec_negative(c)),
        ("12. Artefacts found", lambda: sec_artefacts(c)),
        ("13. Data limits", lambda: sec_limits(c)),
        ("14. How to reproduce", lambda: sec_repro(c)),
    ]
    head = ("# AV-IDS v3: results\n\nGenerated by `make_report.py` from the JSON files under `results/` (and `results/WP7/S3_registry.json` for curated inputs). Do not edit by hand: change the JSON or the generator and run it again.\n"
            "Every number below is traced to a file and key path in the appendix. Honest numbers are preferred to inflated ones: failures are stated plainly, and open milestones are marked PENDING.\n\n")
    body = head
    for title, fn in secs:
        body += f"## {title}\n\n{fn()}\n"
    stripped = strip_marks(body)
    leftover = untracked_numbers(body)
    appendix = make_appendix(c)
    text = stripped + appendix
    return {"text": text, "marked": body, "untracked": leftover, "items": c.items, "missing_closed": c.missing, "pending": c.pending}


def strip_marks(s):
    return MARK.sub(lambda m: m.group(2), s)


def untracked_numbers(marked):
    t = MARK.sub("", marked)
    t = re.sub(r"`[^`]*`", "", t)
    t = re.sub(r"\d{4}-\d{2}-\d{2}", "", t)
    t = re.sub(r"\bsections? \d+( to \d+)?|\bclass(es)? \d+|\b95% intervals?", "", t)
    lines = []
    for ln in t.split("\n"):
        ln = re.sub(r"^#+\s*\d+(\.\d+)*\.?\s*", "", ln)
        ln = re.sub(r"^\s*\d+\.\s", "", ln)
        lines.append(ln)
    return re.findall(r"(?<![\w.])\d[\d,.]*%?(?![\w])", "\n".join(lines))


def make_appendix(c):
    out = "\n## Appendix A. Where every number comes from\n\n"
    out += ("Each row is one printed value: the text as printed, the file it was read from and the key path inside it (segments separated by `/`, list positions are numbers). `curated` = read from `results/WP7/S3_registry.json` "
            "(inputs that exist in no result file, each with its source in that file); `derived` = computed from the listed keys (mean or difference of tracked values).\n\n")
    rows = []
    for i, it in enumerate(c.items):
        path = it["path"].replace("|", "/")
        src = it["file"] if it["kind"] != "derived" else "derived"
        rows.append([str(i + 1), it["text"].replace("|", "/"), f"`{src}`", f"`{path}`", it["kind"], str(it["uses"])])
    out += tbl(["#", "printed", "file", "key path", "kind", "uses"], rows)
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    outp = ROOT / "RESULTS_v3.md"
    if "--out" in argv:
        outp = Path(argv[argv.index("--out") + 1])
    r = build()
    if r["untracked"]:
        print("UNTRACKED NUMBERS in the text:", r["untracked"][:20])
        return 2
    if r["missing_closed"]:
        print("MISSING KEYS in closed milestones:", r["missing_closed"][:20])
    if "--stdout" in argv:
        sys.stdout.write(r["text"])
    else:
        with open(outp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(r["text"])
        print(f"wrote {outp}: {len(r['items'])} traced values, {len(r['missing_closed'])} missing keys, pending sections: {', '.join(r['pending']) or 'none'}")
    return 1 if r["missing_closed"] else 0


if __name__ == "__main__":
    sys.exit(main())
