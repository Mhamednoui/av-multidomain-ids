"""WP5 S2: evaluate the V2X L1 message checks (v2x/l1.py) on VeReMi (D12) and injected Tampa (D14), once on test.

Run from codes_v3/: python -I -u -W ignore tools/WP5_S2_l1.py   (acceptance rule: notes/WP5_v2x.md, 'S2 ... acceptance rule')
Protocol: layers calibrated on validation GENUINE messages only (1% budget, tie-safe); held-out attack types 6, 12, 17 removed
from the validation set that the harness combiner sees; test scored once. Splits from results/WP5/splits_*.json (S1).
Outputs (results/WP5/): s2_veremi.json/.md, s2_tampa.json/.md (harness), s2_summary.json (extras: sender-level, physical
operating points, unions, delays, CIs, evaluability), s2_tables.md (tables used by the report).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np
import pandas as pd

from common.config import SEED, results_dir
from common.evaluate import EvalSet, _combined, _scores, evaluate_domain
from common.metrics import budget_threshold
from common.splits import mask
from v2x import adapters, attacks, l1, splitting
from v2x.schema import CLASS_NAMES

OUT = results_dir("WP5")
BUDGET = 0.01
HELDOUT = [6, 12, 17]
SUPP = "S20_StaleReplay"
LAYERS = ["v2x.beacon_rate", "v2x.freshness", "v2x.field_ranges"]
# Tampa data configuration (WP5 S1b): default = deduplicated passages + time-block split v2. The S2 record (v1 data, split by
# coreData_id) is reproduced by tools/WP5_S1b_rerun.py --legacy, which overrides these three names.
TAMPA_SPLIT_FILE = "splits_tampa_v2.json"
TAMPA_NAME = "s2_tampa_v2"


def tampa_loader():
    return adapters.load_tampa(with_age=True)


def aname(a):
    return f"{a:02d}_{CLASS_NAMES[a]}"


def jdump(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def score_frames(frames, layers):
    """frames: list of DataFrames (each holds whole tracks). Returns {layer name: concatenated Evidence list}."""
    out = {l.name: [] for l in layers}
    for f in frames:
        for l in layers:
            l.reset()
            out[l.name].extend(l.score(f))
    return out


def cal(evs):
    return np.array([e.score for e in evs], dtype=float)


def raw(evs):
    return np.array([e.details["raw"] for e in evs], dtype=float)


def boot_ci(hits, n, rng, B=1000):
    hits, n = np.asarray(hits, float), np.asarray(n, float)
    if len(hits) == 0:
        return [None, None]
    idx = rng.randint(0, len(hits), (B, len(hits)))
    r = hits[idx].sum(1) / np.maximum(n[idx].sum(1), 1)
    return [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))]


def per_class(meta, alarms, classes):
    """meta: DataFrame with sender, t, y, atype aligned with alarms {name: bool array}. Message- and sender-level stats."""
    res = {}
    y = meta["y"].to_numpy(bool)
    for nm, al in alarms.items():
        d = {}
        gen = meta[~y].assign(a=al[~y])
        d["false_alarm_messages"] = float(al[~y].mean())
        d["false_alarm_genuine_senders"] = float(gen.groupby("sender")["a"].any().mean())
        d["n_genuine_senders"] = int(gen["sender"].nunique())
        att = meta[y].assign(a=al[y])
        d["by_class"] = {}
        for c in classes:
            g = att[att["atype"] == c]
            if len(g) == 0:
                continue
            per = g.groupby("sender").agg(h=("a", "sum"), n=("a", "size"), anyd=("a", "any"))
            first_att = g.groupby("sender")["t"].min()
            fa = g[g["a"]].groupby("sender")["t"].min()
            delay = (fa - first_att.loc[fa.index])
            d["by_class"][c] = {"msg_detection": float(g["a"].mean()), "n_msgs": int(len(g)),
                                "n_attackers": int(len(per)),
                                "sender_detected": float(per["anyd"].mean()),
                                "median_delay_s": float(delay.median()) if len(delay) else None,
                                "attackers_hits": per["h"].to_numpy().tolist(),
                                "attackers_n": per["n"].to_numpy().tolist()}
        res[nm] = d
    return res


def raw_equiv(layer_scores_cal, layer_raw, thr):
    m = layer_scores_cal >= thr
    return float(layer_raw[m].min()) if m.any() else None


# ------------------------------------------------------------------------------------------------------------
def prepare_alarms(res, val_es, test_es, layers_by_name, test_df, names):
    """Alarm arrays on test at each layer's budget operating point + combined; physical operating points (if test_df)."""
    th = {n: res["layers"][n]["threshold"] for n in names}
    alarms = {n: cal(test_es.evidence[n]) >= th[n] for n in names}
    comb, sv, st = _combined(val_es, test_es, names, res["combined"]["method"], BUDGET)
    thc = budget_threshold(sv[~np.asarray(val_es.y).astype(bool)], BUDGET)
    assert abs(thc - res["combined"]["threshold"]) < 1e-12
    alarms["combined"] = st >= thc
    phys = {}
    if test_df is not None:
        for n in names:
            if hasattr(layers_by_name[n], "physical_alarm"):
                phys[n] = layers_by_name[n].physical_alarm(test_df)
    return alarms, phys, th


def union_alarm(alarms, phys, names, evaluable):
    parts = []
    for n in names:
        if not evaluable.get(n, True):
            continue
        parts.append(phys[n] if n == "v2x.field_ranges" else alarms[n])
    return np.any(parts, axis=0)


def md_table(title, rows, cols, classes, getter, note=""):
    lines = [f"**{title}**", "", note, "", "| class | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for c in classes:
        star = " *" if c.split("_")[0].isdigit() and int(c.split("_")[0]) in HELDOUT else ""
        vals = [getter(rows[k], c) for k in cols]
        lines.append(f"| {c}{star} | " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def fmt(x, pct=True):
    if x is None:
        return "-"
    return f"{100 * x:.1f}%" if pct else f"{x:.1f}"


# ------------------------------------------------------------------------------------------------------------
def run_veremi(summary, tables):
    log("VeReMi: loading")
    v = adapters.load_veremi()
    v["sample_id"] = v["msg_id"]
    sp = json.loads((OUT / "splits_veremi.json").read_text())
    first_t = v.groupby("sender")["t"].min()
    blk = (first_t // splitting.BLOCK_S).astype(int).astype(str)
    v["group"] = v["sender"].map(blk)
    val_all, test = splitting.rows_of(v, sp["val"]), splitting.rows_of(v, sp["test"])
    val_norm = val_all[val_all["label"] == 0]
    layers = l1.make_layers()
    byname = {l.name: l for l in layers}
    evaluable = {l.name: bool(l.evaluable(test)) for l in layers}
    log("evaluable on VeReMi:", evaluable)
    run = [byname[n] for n in LAYERS if evaluable[n]]
    names = [l.name for l in run]
    for l in run:
        l.calibrate(val_norm, budget=BUDGET)
    val_h = val_all[~val_all["label"].isin(HELDOUT)]           # held-out attack types never reach the combiner
    ev_val = score_frames([val_h], run)
    ev_test = score_frames([test], run)
    yv, yt = (val_h["label"] > 0).to_numpy(), (test["label"] > 0).to_numpy()
    atv = np.where(yv, val_h["label"].map(aname), "normal")
    att = np.where(yt, test["label"].map(aname), "normal")
    ES = lambda ev, y, a, d: EvalSet(ev, y, a, d["group"].to_numpy(), d["t"].to_numpy())
    log("harness VeReMi")
    val_es, test_es = ES(ev_val, yv.astype(int), atv, val_h), ES(ev_test, yt.astype(int), att, test)
    res = evaluate_domain("s2_veremi", val_es, test_es, wp="WP5", budget=BUDGET, method="auto")
    alarms, phys, th = prepare_alarms(res, val_es, test_es, byname, test, names)
    meta = pd.DataFrame({"sender": test["sender"].to_numpy(), "t": test["t"].to_numpy(), "y": yt, "atype": att})
    classes = [aname(c) for c in range(1, 20)]
    allal = dict(alarms)
    for n, a in phys.items():
        allal[n + "@physical"] = a
    allal["L1_union_at_operating_points"] = union_alarm(alarms, phys, names, evaluable)
    pc = per_class(meta, allal, classes)
    # message rate by class (explains the rate layer)
    rt = l1.rate_hz(test)
    first = l1.first_in_track(test)
    rate_by_class = {c: float(np.median(rt[(att == c) & ~first])) if ((att == c) & ~first).any() else None for c in classes}
    rate_gen = float(np.median(rt[(att == "normal") & ~first]))
    thr_raw = {n: raw_equiv(cal(ev_test[n]), raw(ev_test[n]), th[n]) for n in names}
    # validation false alarms (physical ranges check <= 0.1%)
    val_phys_fa = float(byname["v2x.field_ranges"].physical_alarm(val_norm).mean())
    test_phys_fa = float(phys["v2x.field_ranges"][~yt].mean())
    summary["veremi"] = {"evaluable": evaluable, "layers_run": names, "n_val_genuine": int(len(val_norm)),
                         "n_val_for_combiner": int(len(val_h)), "n_test": int(len(test)), "n_test_genuine": int((~yt).sum()),
                         "threshold_raw_equivalent": thr_raw, "operating_points": "rate/freshness: 1% val budget; ranges: both",
                         "physical_FA_val_genuine": val_phys_fa, "physical_FA_test_genuine": test_phys_fa,
                         "rate_median_hz_non_first_by_class": rate_by_class, "rate_median_hz_genuine": rate_gen,
                         "per_operating_point": {k: {kk: vv for kk, vv in d.items() if kk != "by_class"} for k, d in pc.items()},
                         "by_class": {k: {c: {kk: vv for kk, vv in s.items() if not kk.startswith("attackers_")}
                                          for c, s in d["by_class"].items()} for k, d in pc.items()}}
    ops = ["v2x.beacon_rate", "v2x.field_ranges", "v2x.field_ranges@physical", "L1_union_at_operating_points", "combined"]
    tables.append(md_table("VeReMi test, message-level detection per class (each check at its operating point)", pc,
                           ops, classes, lambda d, c: fmt(d["by_class"][c]["msg_detection"]),
                           "Operating points: rate and combined at the 1% validation budget; field_ranges both at the 1% budget and at the physical limit (raw >= 1); union = rate (budget) OR ranges (physical). * = attack type held out from any fitted component."))
    tables.append(md_table("VeReMi test, sender-level detection (at least one alarm among the attacker's falsified messages) and median delay (s) of the union",
                           pc, ["L1_union_at_operating_points", "combined"], classes,
                           lambda d, c: f"{fmt(d['by_class'][c]['sender_detected'])} / {fmt(d['by_class'][c]['median_delay_s'], False)} s", ""))
    fa_rows = "\n".join(f"| {k} | {fmt(d['false_alarm_messages'])} | {fmt(d['false_alarm_genuine_senders'])} |" for k, d in pc.items())
    tables.append("**VeReMi test, false alarms on genuine messages and genuine senders**\n\n| operating point | genuine messages | genuine senders with >= 1 alarm |\n|---|---|---|\n" + fa_rows + "\n")
    tables.append(open(OUT / "s2_veremi.md").read())
    return res


# ------------------------------------------------------------------------------------------------------------
def stale_replay(df, vehicles, seed=SEED + 20000, per_att=100, frac=0.5, min_msgs=50):
    """Supplemental attack (not in the 19): attacker rebroadcasts genuine messages of other vehicles verbatim (content and
    original timestamp) 10-60 s late. Every message is its own track (no stream is claimed). Label = attack."""
    rng = np.random.RandomState(seed)
    d = df[df["sender"].isin(set(map(str, vehicles)))]
    cnt = d.groupby("sender").size()
    elig = sorted(cnt.index[cnt >= min_msgs])
    att = sorted(rng.choice(elig, max(1, int(round(frac * len(elig)))), replace=False).tolist())
    pool = d[~d["sender"].isin(att)]
    parts = []
    for a in att:
        s = pool.iloc[rng.choice(len(pool), per_att, replace=False)].copy()
        s["sender"] = a
        s["pseudo"] = a
        s["track"] = [f"{a}/stale{i}" for i in range(len(s))]
        s["msg_id"] = [f"{m}!stale:{a}" for m in s["msg_id"]]
        s["age_s"] = s["age_s"].to_numpy() + rng.uniform(10, 60, len(s))
        parts.append(s)
    return pd.concat(parts, ignore_index=True), att


def run_tampa(summary, tables):
    log("Tampa: loading")
    tp = tampa_loader()
    sp = json.loads((OUT / TAMPA_SPLIT_FILE).read_text())
    layers = l1.make_layers()
    byname = {l.name: l for l in layers}
    test_df = splitting.rows_of(tp, sp["test"])
    evaluable = {l.name: bool(l.evaluable(test_df)) for l in layers}
    log("evaluable on Tampa:", evaluable)
    run = [byname[n] for n in LAYERS if evaluable[n]]
    names = [l.name for l in run]
    val_df = splitting.rows_of(tp, sp["val"])
    for l in run:
        l.calibrate(val_df.assign(sample_id=val_df["msg_id"]), budget=BUDGET)

    def build(part_df, vehicles, drop_heldout):
        clean = part_df.copy()
        clean["sample_id"] = clean["msg_id"]
        frames, metas = [clean], [pd.DataFrame({"sender": clean["sender"].to_numpy(), "t": clean["t"].to_numpy(), "y": False,
                                                "atype": "normal", "label": 0})]
        keep_masks = [np.ones(len(clean), bool)]
        for aid in attacks.ATTACK_IDS:
            if drop_heldout and aid in HELDOUT:
                continue
            sc, att = attacks.build_scenario(tp, vehicles, aid)
            a = sc[sc["sender"].isin(att)].copy()
            a["sample_id"] = a["msg_id"] + f"#{aid}"
            frames.append(a)
            keep = (a["label"] > 0).to_numpy()
            keep_masks.append(keep)
            metas.append(pd.DataFrame({"sender": a["sender"].to_numpy(), "t": a["t"].to_numpy(), "y": True,
                                       "atype": aname(aid), "label": aid})[keep])
        s, att = stale_replay(tp, vehicles)
        s["sample_id"] = s["msg_id"]
        frames.append(s)
        keep_masks.append(np.ones(len(s), bool))
        metas.append(pd.DataFrame({"sender": s["sender"].to_numpy(), "t": s["t"].to_numpy(), "y": True, "atype": SUPP, "label": 20}))
        return frames, keep_masks, pd.concat(metas, ignore_index=True)

    def score_part(frames, keep_masks, drop_cols=True):
        ev = {l.name: [] for l in run}
        for f, k in zip(frames, keep_masks):
            for l in run:
                l.reset()
                e = l.score(f)
                ev[l.name].extend([x for x, kk in zip(e, k) if kk])
        return ev

    vf, vk, vmeta = build(val_df, sp["val"], True)
    ev_val = score_part(vf, vk)
    tf, tk, tmeta = build(test_df, sp["test"], False)
    ev_test = score_part(tf, tk)
    yv, yt = vmeta["y"].to_numpy(bool), tmeta["y"].to_numpy(bool)
    ES = lambda ev, m: EvalSet(ev, m["y"].to_numpy().astype(int), m["atype"].to_numpy(), m["sender"].to_numpy(), m["t"].to_numpy())
    log("harness Tampa; test messages", len(tmeta), "attack messages", int(yt.sum()))
    val_es, test_es = ES(ev_val, vmeta), ES(ev_test, tmeta)
    res = evaluate_domain(TAMPA_NAME, val_es, test_es, wp="WP5", budget=BUDGET, method="auto")
    alarms, _, th = prepare_alarms(res, val_es, test_es, byname, None, names)
    # physical operating point on the same messages: re-evaluate rules on the frames (message order = same)
    phys = {}
    for n in ("v2x.field_ranges", "v2x.beacon_rate"):
        parts = []
        for f, k in zip(tf, tk):
            parts.append(byname[n].physical_alarm(f)[k])
        phys[n] = np.concatenate(parts)
    pv = np.concatenate([byname["v2x.field_ranges"].physical_alarm(f)[k] for f, k in zip(vf, vk)])
    allal = dict(alarms)
    allal["v2x.field_ranges@physical"] = phys["v2x.field_ranges"]
    allal["v2x.beacon_rate@physical_standard"] = phys["v2x.beacon_rate"]
    allal["L1_union_at_operating_points"] = union_alarm(alarms, {"v2x.field_ranges": phys["v2x.field_ranges"]}, names, evaluable)
    classes = [aname(c) for c in range(1, 20)] + [SUPP]
    pc = per_class(tmeta, allal, classes)
    rng = np.random.RandomState(SEED)
    for nm, d in pc.items():
        for c, s in d["by_class"].items():
            s["ci95_attacker_bootstrap"] = boot_ci(s["attackers_hits"], s["attackers_n"], rng)
        # false-alarm CI over genuine vehicles
        g = tmeta[~yt].assign(a=allal[nm][~yt]).groupby("sender")["a"].agg(["sum", "size"])
        d["false_alarm_ci95_vehicle_bootstrap"] = boot_ci(g["sum"].to_numpy(), g["size"].to_numpy(), rng)
    val_norm_phys_fa = float(pv[~yv].mean())
    test_phys_fa = float(phys["v2x.field_ranges"][~yt].mean())
    age = test_df["age_s"]
    summary["tampa"] = {"evaluable": evaluable, "layers_run": names, "n_val_genuine": int((~yv).sum()),
                        "n_test_genuine": int((~yt).sum()), "n_test_attack": int(yt.sum()),
                        "threshold_raw_equivalent": {n: raw_equiv(cal(ev_test[n]), raw(ev_test[n]), th[n]) for n in names},
                        "physical_FA_val_genuine": val_norm_phys_fa, "physical_FA_test_genuine": test_phys_fa,
                        "genuine_age_s_quantiles_test": {str(q): float(age.quantile(q)) for q in (0, 0.01, 0.5, 0.99, 0.999, 1)},
                        "genuine_dt_note": "Tampa genuine inter-arrival 0.100-0.107 s",
                        "per_operating_point": {k: {kk: vv for kk, vv in d.items() if kk != "by_class"} for k, d in pc.items()},
                        "by_class": {k: {c: {kk: vv for kk, vv in s.items() if not kk.startswith("attackers_")}
                                         for c, s in d["by_class"].items()} for k, d in pc.items()}}
    ops = ["v2x.beacon_rate", "v2x.freshness", "v2x.field_ranges", "v2x.field_ranges@physical", "L1_union_at_operating_points", "combined"]
    tables.append(md_table("Tampa (injected) test, message-level detection per type", pc, ops, classes,
                           lambda d, c: fmt(d["by_class"][c]["msg_detection"]),
                           "10 attackers per type: see s2_summary.json for attacker-bootstrap 95% CIs. S20 = supplemental stale replay (not in the 19)."))
    tables.append(md_table("Tampa test, attacker-bootstrap 95% CI of message detection (combined and union)", pc,
                           ["L1_union_at_operating_points", "combined"], classes,
                           lambda d, c: "[" + ", ".join(fmt(x) for x in d["by_class"][c]["ci95_attacker_bootstrap"]) + "]", ""))
    fa_rows = "\n".join(f"| {k} | {fmt(d['false_alarm_messages'])} | [{', '.join(fmt(x) for x in d['false_alarm_ci95_vehicle_bootstrap'])}] | {fmt(d['false_alarm_genuine_senders'])} |" for k, d in pc.items())
    tables.append("**Tampa test, false alarms on genuine messages and vehicles**\n\n| operating point | genuine messages | 95% CI (vehicle bootstrap) | genuine vehicles with >= 1 alarm |\n|---|---|---|---|\n" + fa_rows + "\n")
    tables.append(open(OUT / (TAMPA_NAME + ".md")).read())
    return res


def main():
    summary = {"limits": {k: float(v) for k, v in l1.LIMITS.items()}, "budget": BUDGET, "heldout_attack_types": HELDOUT,
               "sudden_appearance": "implemented and unit-tested on synthetic data; NOT evaluated on real data (VeReMi combined CSV has no "
                                    "receiver id / position, Tampa RSU positions are not in the public sample)"}
    tables = []
    run_veremi(summary, tables)
    run_tampa(summary, tables)
    jdump("s2_summary.json", summary)
    (OUT / "s2_tables.md").write_text("\n".join(tables))
    log("done")


if __name__ == "__main__":
    main()
