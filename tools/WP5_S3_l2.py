"""WP5 S3: evaluate the V2X L2 plausibility checks (v2x/l2.py) on top of L1 on VeReMi (D12) and injected Tampa (D14).

Run from codes_v3/:  python -I -u -W ignore tools/WP5_S3_l2.py [--dev]
  --dev   calibration and validation-only checks (false alarms on validation, timing); never touches the test split.
  (none)  the single final run: test scored once per dataset. Acceptance rule: notes/WP5_v2x.md, 'S3 L2 plausibility: acceptance rule'.
Protocol: thresholds on validation GENUINE messages only (1% budget, tie-safe); held-out attack types 6, 12, 17 removed from the
validation frame (calibration frame, combiner validation); splits from results/WP5/splits_*.json (S1). The evaluation harness
(common/evaluate.py) is used unchanged; for speed its DomainCombiner.combine is replaced here by a numpy version with identical
scores (it only skips building the explanation strings of Evidence objects).
Outputs (results/WP5/): s3_veremi.json/.md, s3_tampa.json/.md (harness), s3_summary.json (per-class, unions, senders, delays, CIs),
s3_tables.md (tables used by the report).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

import common.combiner as cc
import common.evaluate as ev
from common.config import DATA_EXTRA, SEED
from common.metrics import budget_threshold
from v2x import adapters, attacks, l1, l2, splitting

import WP5_S2_l1 as s2                      # helpers of S2 (per_class, boot_ci, md_table, stale_replay, ...)

OUT, BUDGET, HELDOUT, SUPP = s2.OUT, s2.BUDGET, s2.HELDOUT, s2.SUPP
SMOKE = "--smoke" in sys.argv          # exercise the whole pipeline on the VALIDATION split as a stand-in test (never touches test)
SUF = "_smoke" if SMOKE else ""
OSM_TAMPA = DATA_EXTRA / "D27_osm_tampa" / "tampa_highways.json"
L1_NAMES = ["v2x.beacon_rate", "v2x.freshness", "v2x.field_ranges"]
L2_NAMES = [l.name for l in l2.make_layers()]
PHYS_L2 = ["v2x.speed_change", "v2x.implied_speed", "v2x.heading_rate"]
log, aname, fmt = s2.log, s2.aname, s2.fmt


class Lite:
    __slots__ = ("score", "alarm")

    def __init__(self, score, alarm):
        self.score, self.alarm = score, alarm


def _fast_combine(self, evidence):
    X = self._matrix(evidence)
    s = cc._combine(self.method, X, self.model)
    return [Lite(float(v), bool(v >= self.threshold)) for v in s]


cc.DomainCombiner.combine = _fast_combine


# ----------------------------------------------------------------------------------------------------------
def raw_over_frames(frames, keeps, layers):
    """Raw scores (and physical alarms) of every layer on each frame, rows selected by keep, concatenated."""
    raw = {l.name: [] for l in layers}
    phys = {l.name: [] for l in layers if getattr(l, "physical", False)}
    for f, k in zip(frames, keeps):
        for l in layers:
            raw[l.name].append(np.asarray(l.raw_scores(f), float)[k])
            if l.name in phys:
                phys[l.name].append(np.asarray(l.physical_alarm(f))[k])
    return ({n: np.concatenate(v) for n, v in raw.items()}, {n: np.concatenate(v) for n, v in phys.items()})


def cal_alarm(layers, raw):
    cal = {l.name: l.calibrator.transform(raw[l.name]) for l in layers}
    return cal, {l.name: cal[l.name] >= l.threshold for l in layers}


def lite_list(cal, alarm):
    return [Lite(float(s), bool(a)) for s, a in zip(cal, alarm)]


def sender_k(meta, alarm, classes, k):
    """Fraction of attackers with >= k alarms among their falsified messages; false alarms on genuine senders (>= k alarms)."""
    y = meta["y"].to_numpy(bool)
    gen = meta[~y].assign(a=alarm[~y]).groupby("sender")["a"].sum()
    att = meta[y].assign(a=alarm[y])
    out = {"false_alarm_genuine_senders": float((gen >= k).mean()), "by_class": {}}
    for c in classes:
        g = att[att["atype"] == c]
        if len(g):
            out["by_class"][c] = float((g.groupby("sender")["a"].sum() >= k).mean())
    return out


def raw_equiv_val(layer, raw_val, cal_val):
    m = cal_val >= layer.threshold
    return float(raw_val[m].min()) if m.any() else None


def analyse(tag, layers_all, raw_val, raw_test, phys_val, phys_test, vmeta, tmeta, val_group, test_group, classes, evaluable, supp=False):
    """Everything after the raw scores exist. layers_all: evaluable layers (L1 + L2), calibrated."""
    names = [l.name for l in layers_all]
    n_l1 = [n for n in names if n in L1_NAMES]
    n_l2 = [n for n in names if n in L2_NAMES]
    byname = {l.name: l for l in layers_all}
    yv, yt = vmeta["y"].to_numpy(bool), tmeta["y"].to_numpy(bool)
    cal_v, al_v = cal_alarm(layers_all, raw_val)
    cal_t, al_t = cal_alarm(layers_all, raw_test)
    ES = lambda cal, al, m, grp: ev.EvalSet({n: lite_list(cal[n], al[n]) for n in names}, m["y"].to_numpy().astype(int),
                                            m["atype"].to_numpy(), grp, m["t"].to_numpy())
    val_es, test_es = ES(cal_v, al_v, vmeta, val_group), ES(cal_t, al_t, tmeta, test_group)
    log(tag, "harness (all layers)")
    res = ev.evaluate_domain(f"s3_{tag}", val_es, test_es, wp="WP5", budget=BUDGET, method="auto")
    # group rows: L1, L2, L1+L2 (combiner chosen on validation each time)
    groups = {}
    comb_alarm = {}
    for gname, gn in (("L1", n_l1), ("L2", n_l2), ("L1+L2", names)):
        if not gn:
            continue
        comb, sv, st = ev._combined(val_es, test_es, gn, "auto", BUDGET)
        thr = budget_threshold(sv[~yv], BUDGET)
        r = ev._summarize(sv, st, val_es, test_es, BUDGET)
        r["method"] = comb.method
        groups[gname] = r
        comb_alarm[f"combined_{gname}"] = st >= thr
    comb_all, sv, st = ev._combined(val_es, test_es, names, res["combined"]["method"], BUDGET)
    comb_alarm["combined_all"] = st >= budget_threshold(sv[~yv], BUDGET)
    # unions
    def union_score(ns, cal):
        return np.max([cal[n] for n in ns], axis=0)
    u2v, u2t = union_score(n_l2, cal_v), union_score(n_l2, cal_t)
    thr_u2 = budget_threshold(u2v[~yv], BUDGET)
    al_u2 = u2t >= thr_u2
    phys_l2 = [n for n in PHYS_L2 if n in phys_test]
    al_phys_l2 = np.any([phys_test[n] for n in phys_l2], axis=0) if phys_l2 else np.zeros(len(tmeta), bool)
    l1_parts = [phys_test["v2x.field_ranges"] if n == "v2x.field_ranges" else al_t[n] for n in n_l1]
    al_l1u = np.any(l1_parts, axis=0)
    ops = {}
    for n in names:
        ops[n] = al_t[n]
    for n, a in phys_test.items():
        ops[n + "@physical"] = a
    ops["L2_physical_union"] = al_phys_l2
    ops["L2_union"] = al_u2
    ops["L1_union_at_operating_points"] = al_l1u
    ops["L1_and_L2_union"] = al_l1u | al_u2
    ops.update(comb_alarm)
    pc = s2.per_class(tmeta, ops, classes)
    rng = np.random.RandomState(SEED)
    if supp:
        for nm, d in pc.items():
            for c, s in d["by_class"].items():
                s["ci95_attacker_bootstrap"] = s2.boot_ci(s["attackers_hits"], s["attackers_n"], rng)
            g = tmeta[~yt].assign(a=ops[nm][~yt]).groupby("sender")["a"].agg(["sum", "size"])
            d["false_alarm_ci95_vehicle_bootstrap"] = s2.boot_ci(g["sum"].to_numpy(), g["size"].to_numpy(), rng)
    s3 = {k: sender_k(tmeta, ops[k], classes, 3) for k in ("L2_union", "L1_and_L2_union", "combined_all")}
    # physical false alarms and thresholds
    phys_fa = {n: {"val_genuine": float(phys_val[n][~yv].mean()), "test_genuine": float(phys_test[n][~yt].mean())} for n in phys_test}
    ph_u_v = np.any([phys_val[n] for n in phys_l2], axis=0) if phys_l2 else np.zeros(len(vmeta), bool)
    phys_fa["L2_physical_union"] = {"val_genuine": float(ph_u_v[~yv].mean()), "test_genuine": float(al_phys_l2[~yt].mean())}
    summ = {"evaluable": evaluable, "layers_run": names, "n_val_genuine": int((~yv).sum()), "n_val_for_combiner": int(len(yv)),
            "n_test": int(len(yt)), "n_test_genuine": int((~yt).sum()), "n_test_attack": int(yt.sum()),
            "threshold_raw_equivalent": {n: raw_equiv_val(byname[n], raw_val[n], cal_v[n]) for n in names},
            "threshold_union_L2_score": float(thr_u2),
            "physical_FA": phys_fa,
            "val_FA_budget_ops": {n: float(al_v[n][~yv].mean()) for n in names},
            "groups": {k: {kk: vv for kk, vv in v.items() if kk != "delay"} | {"delay": v["delay"]} for k, v in groups.items()},
            "per_operating_point": {k: {kk: vv for kk, vv in d.items() if kk != "by_class"} for k, d in pc.items()},
            "by_class": {k: {c: {kk: vv for kk, vv in s.items() if not kk.startswith("attackers_")} for c, s in d["by_class"].items()}
                         for k, d in pc.items()},
            "sender_ge3_alarms": s3,
            "harness_method": res["combined"]["method"], "harness_selection": res["combined"]["method_selection"]}
    return res, summ, pc, s3, ops


def tables_for(title, pc, s3, classes, l2_cols, extra_cols=()):
    out = []
    out.append(s2.md_table(f"{title}: message-level detection per class, each L2 check at the 1% validation budget", pc, l2_cols,
                           classes, lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")),
                           "* = attack type held out of calibration and combiner. Physical limits below."))
    pcols = [c for c in ("v2x.speed_change@physical", "v2x.implied_speed@physical", "v2x.heading_rate@physical", "L2_physical_union") if c in pc]
    out.append(s2.md_table(f"{title}: message-level detection at the physical limits (no fitted threshold)", pc, pcols, classes,
                           lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")), ""))
    ucols = ["L2_union", "L1_union_at_operating_points", "L1_and_L2_union", "combined_L1", "combined_L2", "combined_L1+L2", "combined_all"]
    ucols = [c for c in ucols if c in pc]
    out.append(s2.md_table(f"{title}: message-level detection, unions and harness combinations", pc, ucols, classes,
                           lambda d, c: fmt(d["by_class"].get(c, {}).get("msg_detection")),
                           "L2_union = max of the calibrated L2 scores at one 1% budget; L1_union = beacon rate (budget) OR field ranges (physical) [OR freshness (budget) on Tampa]; "
                           "L1_and_L2_union = L1_union OR L2_union; combined_* = harness combiner (chosen on validation) of the L1 / L2 / all layers."))
    scols = ["L2_union", "L1_and_L2_union"]
    out.append(s2.md_table(f"{title}: sender-level detection (>= 1 alarm among the attacker's falsified messages / >= 3 alarms) and median delay (s)",
                           pc, scols, classes,
                           lambda d, c: f"{fmt(d['by_class'].get(c, {}).get('sender_detected'))} / {fmt(d['by_class'].get(c, {}).get('median_delay_s'), False)} s", ">= 3 alarms in the next table."))
    cl3 = {k: s3[k] for k in ("L2_union", "L1_and_L2_union")}
    lines = ["| class | L2_union >= 3 alarms | L1_and_L2_union >= 3 alarms |", "|---|---|---|"]
    for c in classes:
        if c in cl3["L2_union"]["by_class"]:
            lines.append(f"| {c} | {fmt(cl3['L2_union']['by_class'][c])} | {fmt(cl3['L1_and_L2_union']['by_class'][c])} |")
    lines.append(f"| genuine senders with >= 3 alarms | {fmt(cl3['L2_union']['false_alarm_genuine_senders'])} | {fmt(cl3['L1_and_L2_union']['false_alarm_genuine_senders'])} |")
    out.append("\n".join(lines) + "\n")
    return out


def fa_table(title, pc, ci=False):
    rows = []
    for k, d in pc.items():
        extra = ""
        if ci:
            extra = " [" + ", ".join(fmt(x) for x in d["false_alarm_ci95_vehicle_bootstrap"]) + "] |"
        rows.append(f"| {k} | {fmt(d['false_alarm_messages'])} |{extra} {fmt(d['false_alarm_genuine_senders'])} |")
    head = "| operating point | genuine messages |" + (" 95% CI (vehicle bootstrap) |" if ci else "") + " genuine senders with >= 1 alarm |"
    return f"**{title}: false alarms on genuine test messages and senders**\n\n{head}\n|---|---|{'---|' if ci else ''}---|\n" + "\n".join(rows) + "\n"


# ----------------------------------------------------------------------------------------------------------
def run_veremi(dev, summary, tables):
    log("VeReMi: loading")
    v = adapters.load_veremi()
    v["sample_id"] = v["msg_id"]
    sp = json.loads((OUT / "splits_veremi.json").read_text())
    first_t = v.groupby("sender")["t"].min()
    v["group"] = v["sender"].map((first_t // splitting.BLOCK_S).astype(int).astype(str))
    val_all = splitting.rows_of(v, sp["val"])
    val_h = val_all[~val_all["label"].isin(HELDOUT)]
    val_norm = val_all[val_all["label"] == 0]
    l1_layers = [l for l in l1.make_layers() if l.name in ("v2x.beacon_rate", "v2x.field_ranges")]      # as S2 (freshness / sudden: not evaluable)
    for l in l1_layers:
        l.calibrate(val_norm, budget=BUDGET)
    l2_layers = [l for l in l2.make_layers() if l.name not in ("v2x.yaw_consistency", "v2x.map_road")]
    evaluable = {"v2x.yaw_consistency": False, "v2x.map_road": False, "note": "VeReMi: no yaw rate in the CSV, no Luxembourg map"}
    log("VeReMi: L2 calibration on val frame", len(val_h), "rows")
    gen_mask = (val_h["label"] == 0).to_numpy()
    for l in l2_layers:
        t0 = time.time()
        l.calibrate_masked(val_h, gen_mask, BUDGET)
        log("  calibrated", l.name, f"{time.time() - t0:.0f}s thr", l.threshold)
    layers = l1_layers + l2_layers
    yv = (val_h["label"] > 0).to_numpy()
    raw_val, phys_val = raw_over_frames([val_h], [np.ones(len(val_h), bool)], layers)
    vmeta = pd.DataFrame({"sender": val_h["sender"].to_numpy(), "t": val_h["t"].to_numpy(), "y": yv,
                          "atype": np.where(yv, val_h["label"].map(aname), "normal")})
    _, al_v = cal_alarm(layers, raw_val)
    log("VeReMi val genuine FA at budget ops:", {n: round(float(a[~yv].mean()), 4) for n, a in al_v.items()})
    log("VeReMi val genuine physical FA:", {n: round(float(a[~yv].mean()), 5) for n, a in phys_val.items()})
    if dev:
        return None
    test = val_all if SMOKE else splitting.rows_of(v, sp["test"])
    log("VeReMi: scoring test", len(test))
    raw_test, phys_test = raw_over_frames([test], [np.ones(len(test), bool)], layers)
    yt = (test["label"] > 0).to_numpy()
    tmeta = pd.DataFrame({"sender": test["sender"].to_numpy(), "t": test["t"].to_numpy(), "y": yt,
                          "atype": np.where(yt, test["label"].map(aname), "normal")})
    classes = [aname(c) for c in range(1, 20)]
    res, summ, pc, s3, ops = analyse("veremi" + SUF, layers, raw_val, raw_test, phys_val, phys_test, vmeta, tmeta,
                                     val_h["group"].to_numpy(), test["group"].to_numpy(), classes, evaluable)
    summ["val_physical_FA_L1_ranges"] = float(phys_val["v2x.field_ranges"][~yv].mean())
    summ["map_check"] = "SKIPPED on VeReMi: the Luxembourg (LuST) map is not available"
    summary["veremi"] = summ
    l2cols = [n for n in L2_NAMES if n in summ["layers_run"]]
    tables.append("### VeReMi (D12) test\n")
    tables += tables_for("VeReMi test", pc, s3, classes, l2cols)
    tables.append(fa_table("VeReMi test", pc))
    tables.append(open(OUT / f"s3_veremi{SUF}.md").read())
    gl = ["| group | method | AUC | detection (all attacks) | false alarms |", "|---|---|---|---|---|"]
    for k, r in summ["groups"].items():
        gl.append(f"| {k} | {r['method']} | {r['auc']:.3f} | {fmt(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% |")
    tables.append("**VeReMi test, harness group ablation on top of L1**\n\n" + "\n".join(gl) + "\n")
    return res


def tampa_frames(tp, vehicles, drop_heldout):
    """Frames with neighbours: (frames, keeps, meta). The clean frame carries the genuine messages; scenario frames carry the rest of the
    split as genuine neighbours and the attackers (evaluated rows only)."""
    clean = tp[tp["sender"].isin(set(map(str, vehicles)))].copy()
    clean["sample_id"] = clean["msg_id"]
    frames, keeps = [clean], [np.ones(len(clean), bool)]
    metas = [pd.DataFrame({"sender": clean["sender"].to_numpy(), "t": clean["t"].to_numpy(), "y": False, "atype": "normal"})]
    for aid in attacks.ATTACK_IDS:
        if drop_heldout and aid in HELDOUT:
            continue
        sc, att = attacks.build_scenario(tp, vehicles, aid)
        sc["sample_id"] = sc["msg_id"] + f"#{aid}"
        keep = (sc["sender"].isin(att) & (sc["label"] > 0)).to_numpy()
        frames.append(sc)
        keeps.append(keep)
        k = sc[keep]
        metas.append(pd.DataFrame({"sender": k["sender"].to_numpy(), "t": k["t"].to_numpy(), "y": True, "atype": aname(aid)}))
    st, _ = s2.stale_replay(tp, vehicles)
    st["sample_id"] = st["msg_id"]
    frames.append(st)
    keeps.append(np.ones(len(st), bool))
    metas.append(pd.DataFrame({"sender": st["sender"].to_numpy(), "t": st["t"].to_numpy(), "y": True, "atype": SUPP}))
    return frames, keeps, pd.concat(metas, ignore_index=True)


def run_tampa(dev, summary, tables):
    log("Tampa: loading")
    tp = adapters.load_tampa(with_age=True)
    sp = json.loads((OUT / "splits_tampa.json").read_text())
    tree = l2.build_road_tree(OSM_TAMPA, adapters.TAMPA_LAT0, adapters.TAMPA_LON0)
    log("road tree points", tree.n)
    val_df = splitting.rows_of(tp, sp["val"])
    val_df = val_df.assign(sample_id=val_df["msg_id"])
    l1_layers = [l for l in l1.make_layers() if l.name in L1_NAMES]
    for l in l1_layers:
        l.calibrate(val_df, budget=BUDGET)
    l2_layers = l2.make_layers(tree)
    for l in l2_layers:
        l.calibrate_masked(val_df, np.ones(len(val_df), bool), BUDGET)
    layers = l1_layers + l2_layers
    evaluable = {l.name: bool(l.evaluable(val_df)) for l in layers}
    log("Tampa evaluable:", evaluable)
    vf, vk, vmeta = tampa_frames(tp, sp["val"], True)
    raw_val, phys_val = raw_over_frames(vf, vk, layers)
    yv = vmeta["y"].to_numpy(bool)
    _, al_v = cal_alarm(layers, raw_val)
    log("Tampa val genuine FA at budget ops:", {n: round(float(a[~yv].mean()), 4) for n, a in al_v.items()})
    log("Tampa val genuine physical FA:", {n: round(float(a[~yv].mean()), 5) for n, a in phys_val.items()})
    if dev:
        return None
    sp_test = sp["val"] if SMOKE else sp["test"]
    tf, tk, tmeta = tampa_frames(tp, sp_test, SMOKE)
    log("Tampa: scoring test", len(tmeta), "messages")
    raw_test, phys_test = raw_over_frames(tf, tk, layers)
    classes = [aname(c) for c in range(1, 20)] + [SUPP]
    res, summ, pc, s3, ops = analyse("tampa" + SUF, layers, raw_val, raw_test, phys_val, phys_test, vmeta, tmeta,
                                     vmeta["sender"].to_numpy(), tmeta["sender"].to_numpy(), classes, evaluable, supp=True)
    summ["map_road_threshold_note"] = "distance (m) to the nearest drivable OSM way, threshold = raw equivalent above"
    summary["tampa"] = summ
    l2cols = [n for n in L2_NAMES if n in summ["layers_run"]]
    tables.append("### Tampa (injected on real BSMs) test\n")
    tables += tables_for("Tampa test", pc, s3, classes, l2cols)
    tables.append(s2.md_table("Tampa test: attacker-bootstrap 95% CI of message detection (L2_union and L1_and_L2_union)", pc,
                              ["L2_union", "L1_and_L2_union"], classes,
                              lambda d, c: "[" + ", ".join(fmt(x) for x in d["by_class"].get(c, {}).get("ci95_attacker_bootstrap", [None, None])) + "]", ""))
    tables.append(fa_table("Tampa test", pc, ci=True))
    tables.append(open(OUT / f"s3_tampa{SUF}.md").read())
    gl = ["| group | method | AUC | detection (all attacks) | false alarms |", "|---|---|---|---|---|"]
    for k, r in summ["groups"].items():
        gl.append(f"| {k} | {r['method']} | {r['auc']:.3f} | {fmt(r['detection'])} | {100 * r['false_alarm_rate']:.2f}% |")
    tables.append("**Tampa test, harness group ablation on top of L1**\n\n" + "\n".join(gl) + "\n")
    return res


def main():
    dev = "--dev" in sys.argv
    assert not (dev and SMOKE)
    summary = {"budget": BUDGET, "heldout_attack_types": HELDOUT,
               "constants": {"DT_MAX": l2.DT_MAX, "V_HEAD_MIN": l2.V_HEAD_MIN, "D0": l2.D0, "CAR_L": l2.CAR_L, "CAR_W": l2.CAR_W,
                             "W_OVERLAP": l2.W_OVERLAP},
               "not_done": "acceptance-range and sudden appearance deferred to S3b (no receiver positions); map check skipped on VeReMi"}
    tables = []
    run_veremi(dev, summary, tables)
    run_tampa(dev, summary, tables)
    if not dev:
        s2.jdump(f"s3_summary{SUF}.json", summary)
        (OUT / f"s3_tables{SUF}.md").write_text("\n".join(tables))
    log("done" + (" (dev: no test touched)" if dev else ""))


if __name__ == "__main__":
    main()
