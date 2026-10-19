"""WP5 S1b: old vs new tables for the report, generated from the JSON files (no hand-typed numbers).

Run from codes_v3/: python -I -u -W ignore tools/WP5_S1b_report.py
Inputs (results/WP5/): S2 / S3 record (s2_summary.json, s3_summary.json, s2_tampa.json, s3_tampa.json), the same-method run on the old data
(*_tampa_v1same*), the new run (*_tampa_v2*), s1b_dedup_link.json, s1b_split_info.json.
Outputs: s1b_compare.json (numbers), s1b_tables.md (tables pasted in reports/WP5_S1b.md).
Columns: old = S2/S3 as reported (map_road inside the L2 union); v1same = same code on the old data and old split, map_road outside the union;
new = deduplicated passages, time-block split v2, map_road outside the union.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

import numpy as np

from common.config import results_dir

OUT = results_dir("WP5")
J = lambda n: json.loads((OUT / n).read_text())
HELD = (6, 12, 17)


def pct(x, d=1):
    return "-" if x is None else f"{100 * x:.{d}f}%"


def ci(x):
    return "" if not x or x[0] is None else f" [{100 * x[0]:.0f}-{100 * x[1]:.0f}]"


def main():
    s2 = {"old": J("s2_summary.json")["tampa"], "v1same": J("s2_summary_tampa_v1same.json")["tampa"], "new": J("s2_summary_tampa_v2.json")["tampa"]}
    s3 = {"old": J("s3_summary.json")["tampa"], "v1same": J("s3_summary_tampa_v1same.json")["tampa"], "new": J("s3_summary_tampa_v2.json")["tampa"]}
    h2 = {"old": J("s2_tampa.json"), "v1same": J("s2_tampa_v1same.json"), "new": J("s2_tampa_v2.json")}
    h3 = {"old": J("s3_tampa.json"), "v1same": J("s3_tampa_v1same.json"), "new": J("s3_tampa_v2.json")}
    link, sinfo = J("s1b_dedup_link.json"), J("s1b_split_info.json")
    cmp = {}
    md = []

    # ---- data
    md.append("**Tampa data, old vs new**\n\n| | old (S1) | new (S1b) |\n|---|---|---|\n"
              f"| rows in the CSV | {link['copies']['rows']} | {link['copies']['rows']} |\n"
              f"| distinct over-the-air messages | (34,453 counted, copies kept) | {link['copies']['unique_messages']} |\n"
              f"| grouping unit | {link['tier1']['ids']} coreData_ids (per RSU) | {link['linking_summary']['passages']} passages of {link['linking_summary']['physical_vehicles']} physical vehicles |\n"
              f"| split | by id 136 / 45 / 45 | time blocks (episodes) seed {sinfo['seed']}: " + " / ".join(f"{sinfo['parts'][p]['passages']}" for p in ("train", "val", "test")) + " passages |\n"
              f"| genuine val / test messages scored | {s3['old']['n_val_genuine']} / {s3['old']['n_test_genuine']} | {s3['new']['n_val_genuine']} / {s3['new']['n_test_genuine']} |\n"
              f"| attackers per type val / test | " + f"10 / 10 | {sinfo['attackers_per_type_min']['val']} / {sinfo['attackers_per_type_min']['test']} |\n")

    # ---- false alarms on genuine test messages
    ops = [("v2x.beacon_rate", "beacon rate (L1)"), ("v2x.freshness", "freshness (L1)"), ("v2x.field_ranges", "field ranges, budget (L1)"),
           ("v2x.field_ranges@physical", "field ranges, physical"), ("L1_union_at_operating_points", "L1 union"),
           ("v2x.pos_speed", "pos_speed"), ("v2x.pos_heading", "pos_heading"), ("v2x.speed_change", "speed_change"),
           ("v2x.implied_speed", "implied_speed"), ("v2x.heading_rate", "heading_rate"), ("v2x.accel_consistency", "accel_consistency"),
           ("v2x.yaw_consistency", "yaw_consistency"), ("v2x.overlap", "overlap"), ("L2_physical_union", "L2 physical union"),
           ("L2_union", "L2 union (deployable; old = with map)"), ("L1_and_L2_union", "L1 + L2 union (deployable; old = with map)"),
           ("combined_all", "harness combined, all layers"), ("v2x.map_road", "map_road alone (soft layer)"),
           ("L1_and_L2_union_OR_v2x.map_road", "L1 + L2 union OR map_road")]
    rows = []
    cmp["false_alarm_genuine_test_messages"] = {}
    for k, nm in ops:
        vals = {}
        for v in ("old", "v1same", "new"):
            pco = s3[v]["per_operating_point"]
            if k in pco:
                vals[v] = pco[k]["false_alarm_messages"]
            elif k == "L1_and_L2_union_OR_v2x.map_road" and v == "old":
                vals[v] = None
            else:
                vals[v] = None
        if k == "v2x.map_road":
            pass
        cmp["false_alarm_genuine_test_messages"][k] = vals
        c = s3["new"]["per_operating_point"].get(k, {}).get("false_alarm_ci95_vehicle_bootstrap")
        rows.append(f"| {nm} | {pct(vals['old'])} | {pct(vals['v1same'])} | {pct(vals['new'])}{ci(c)} |")
    md.append("**False alarms on genuine test messages (95% vehicle/passage bootstrap CI for new)**\n\n| operating point | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    fa_phys = {v: s3[v]["physical_FA"] for v in s3}
    md.append("**Physical limits, false alarms on genuine val / test** (bound 0.1%)\n\n| limit | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(
        f"| {n} | " + " | ".join(f"{pct(fa_phys[v].get(n, {}).get('val_genuine'), 3)} / {pct(fa_phys[v].get(n, {}).get('test_genuine'), 3)}" for v in ("old", "v1same", "new")) + " |"
        for n in fa_phys["new"]) + "\n")

    # ---- per-type detection
    classes = sorted(s3["new"]["by_class"]["L2_union"])
    cols = [("L1_union_at_operating_points", "L1 union"), ("L2_union", "L2 union"), ("L1_and_L2_union", "L1+L2 union"), ("v2x.map_road", "map_road (soft)"), ("combined_all", "combined")]
    cmp["detection_by_type"] = {}
    for k, nm in cols:
        rows = []
        cmp["detection_by_type"][k] = {}
        for c in classes:
            vals = {}
            for v in ("old", "v1same", "new"):
                d = s3[v]["by_class"].get(k, {}).get(c)
                vals[v] = None if d is None else d["msg_detection"]
            nat = s3["new"]["by_class"].get(k, {}).get(c, {})
            cmp["detection_by_type"][k][c] = vals
            star = " *" if c.split("_")[0].isdigit() and int(c.split("_")[0]) in HELD else ""
            rows.append(f"| {c}{star} | {pct(vals['old'])} | {pct(vals['v1same'])} | {pct(vals['new'])}{ci(nat.get('ci95_attacker_bootstrap'))} | {nat.get('n_attackers', '-')} |")
        md.append(f"**Tampa test, message-level detection, {nm}** (new: attacker-bootstrap CI; * held-out type)\n\n| type | old | v1same | new | attackers (new) |\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n")
    # ---- summary of the inflation
    summ = {}
    for k, nm in cols:
        for v in ("old", "v1same", "new"):
            xs = [cmp["detection_by_type"][k][c][v] for c in classes if c.startswith(tuple(f"{i:02d}_" for i in range(1, 20)))]
            xs = [x for x in xs if x is not None]
            summ.setdefault(k, {})[v] = float(np.mean(xs)) if xs else None
    cmp["mean_detection_over_19_types"] = summ
    md.append("**Mean detection over the 19 injected types (unweighted), test**\n\n| operating point | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(
        f"| {nm} | {pct(summ[k]['old'])} | {pct(summ[k]['v1same'])} | {pct(summ[k]['new'])} |" for k, nm in cols) + "\n")

    # ---- ablation (harness)
    rows = []
    cmp["ablation"] = {}
    for g in ("L1", "L2", "L1+L2"):
        r = {v: s3[v]["groups"].get(g) for v in s3}
        cmp["ablation"][g] = {v: (None if x is None else {"auc": x["auc"], "detection": x["detection"], "false_alarm_rate": x["false_alarm_rate"], "method": x["method"]}) for v, x in r.items()}
        rows.append(f"| {g} | " + " | ".join("-" if r[v] is None else f"{r[v]['auc']:.3f} / {pct(r[v]['detection'])} / FA {pct(r[v]['false_alarm_rate'])}" for v in ("old", "v1same", "new")) + " |")
    md.append("**Harness group ablation, AUC / detection at the 1% validation budget / test FA** (old L2 and L1+L2 contain map_road; v1same and new do not)\n\n| group | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    rows = []
    cmp["single_layers"] = {}
    names = sorted(set(h3["old"]["layers"]) | set(h3["new"]["layers"]))
    for n in names:
        r = {v: h3[v]["layers"].get(n) for v in h3}
        cmp["single_layers"][n] = {v: (None if x is None else {"auc": x["auc"], "detection": x["detection"], "false_alarm_rate": x["false_alarm_rate"]}) for v, x in r.items()}
        rows.append(f"| {n} | " + " | ".join("-" if r[v] is None else f"{r[v]['auc']:.3f} / {pct(r[v]['detection'])} / {pct(r[v]['false_alarm_rate'])}" for v in ("old", "v1same", "new")) + " |")
    md.append("**Each layer alone in the S3 harness (AUC / detection at 1% budget / test FA)**\n\n| layer | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    rows = []
    for n in sorted(set(h3["old"]["ablation"]) | set(h3["new"]["ablation"])):
        if n == "all" or n.startswith("only_"):
            continue
        r = {v: h3[v]["ablation"].get(n) for v in h3}
        rows.append(f"| {n} | " + " | ".join("-" if r[v] is None else f"{r[v]['auc']:.3f} / {pct(r[v]['detection'])}" for v in ("old", "v1same", "new")) + " |")
    md.append("**Leave-one-out (all-but-X) in the S3 harness (AUC / detection)**\n\n| removed | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    # ---- S2 side
    rows = []
    for k, nm in (("v2x.beacon_rate", "beacon rate"), ("v2x.freshness", "freshness"), ("v2x.field_ranges", "field ranges (budget)"),
                  ("v2x.field_ranges@physical", "field ranges (physical)"), ("L1_union_at_operating_points", "L1 union"), ("combined", "S2 combined")):
        fa = {v: s2[v]["per_operating_point"][k]["false_alarm_messages"] for v in s2}
        rows.append(f"| {nm} FA | " + " | ".join(pct(fa[v]) for v in ("old", "v1same", "new")) + " |")
    md.append("**S2 (L1) on Tampa, false alarms on genuine test messages**\n\n| | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    s2cls = sorted(s2["new"]["by_class"]["L1_union_at_operating_points"])
    rows = []
    cmp["s2_L1_union_by_type"] = {}
    for c in s2cls:
        vals = {v: s2[v]["by_class"]["L1_union_at_operating_points"][c]["msg_detection"] for v in s2}
        cmp["s2_L1_union_by_type"][c] = vals
        rows.append(f"| {c} | " + " | ".join(pct(vals[v]) for v in ("old", "v1same", "new")) + " |")
    md.append("**S2 (L1 union) on Tampa, message-level detection per type**\n\n| type | old | v1same | new |\n|---|---|---|---|\n" + "\n".join(rows) + "\n")
    # ---- map_road + soft info
    cmp["soft_layers_new"] = s3["new"].get("soft_layers")
    cmp["n_test"] = {v: {"genuine": s3[v]["n_test_genuine"], "attack": s3[v]["n_test_attack"]} for v in s3}
    (OUT / "s1b_compare.json").write_text(json.dumps(cmp, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    (OUT / "s1b_tables.md").write_text("\n".join(md))
    print("done")


if __name__ == "__main__":
    main()
