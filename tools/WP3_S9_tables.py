"""WP3 S9: markdown tables from results/WP3/S9/final.json (or the dry-run json) -> results/WP3/S9/S9_tables.md (or dry_tables.md).
Usage: python -u -W ignore tools/WP3_S9_tables.py [final|dryrun_val]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS

RES = RESULTS / "WP3" / "S9"
PHYS = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof"]
CMP = ["cmp_boxcloud", "cmp_mradd_near", "cmp_mradd_far"]
SHORT = {"ph_replace_near": "replace near", "ph_replace_far": "replace far", "ph_budget_near": "budget near", "ph_budget_far": "budget far", "PointDrop": "PointDrop",
         "IntensitySpoof": "IntensitySpoof", "cmp_boxcloud": "box cloud*", "cmp_mradd_near": "multi-return add near*", "cmp_mradd_far": "multi-return add far*"}
LNAME = {"raw_L1": "L1", "raw_L2a": "L2a", "raw_L2aF": "L2a+density", "raw_L2c": "L2c", "raw_L2d": "L2d", "raw_L2b": "L2b", "raw_L4": "L4"}


def pc(x, d=1):
    return "-" if x is None else f"{100 * x:.{d}f}"


def md(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]) + "\n"


def stack_row(name, r, names=PHYS + CMP):
    return [name, pc(r["fa"], 2)] + [pc(r["det"][a]["det"]) if a in r["det"] else "-" for a in names]


def main(src):
    R = json.loads((RES / f"{src}.json").read_text())
    h = R["headline"]
    out = [f"# S9 tables ({src}); combiner {R.get('choices', {}).get('combiner', R['method'])}; detection and FA in %; * = physically impossible on a single-return sensor (comparison)\n"]
    out.append("## Headline stack, per attack (95 % CI = bootstrap over test drives)\n")
    rows = []
    for a in PHYS + CMP:
        if a in h["det"]:
            v = h["det"][a]
            pd_ = v["per_drive"]
            rows.append([SHORT[a], pc(v["det"]), f"[{pc(v['ci95'][0])}, {pc(v['ci95'][1])}]", v["n"], f"{pc(min(pd_.values()))}-{pc(max(pd_.values()))}", f"{h['auc'][a]:.3f}"])
    out.append(md(["attack", "detection", "95 % CI", "n scans", "per-drive range", "AUC"], rows))
    out.append(f"\nFA clean scans {pc(h['fa'], 2)} [{pc(h['fa_ci95'][0], 2)}, {pc(h['fa_ci95'][1], 2)}], threshold from reference FA {pc(h['fa_ref'], 2)}; LODO FA (16 train+val drives) mean {pc(h['lodo_mean'], 2)}, worst {pc(h['lodo_worst'], 2)} ({h['lodo_worst_drive']}).\n")
    out.append("\n## False alarms per drive (test clean scans) and leave-one-drive-out on the reference\n")
    out.append(md(["drive", "test FA"], [[d, pc(v, 2)] for d, v in sorted(h["fa_per_drive"].items())]))
    out.append(md(["drive", "LODO FA"], [[d, pc(v, 2)] for d, v in sorted(h["lodo_fa"].items())]))
    out.append("\n## Ablation (same combiner, 1 % total budget)\n")
    rows = [stack_row("all four", h)]
    for c, r in R["all_but"].items():
        rows.append(stack_row("all but " + LNAME[c], r))
    for c, r in R["layers_alone"].items():
        rows.append(stack_row(LNAME[c] + " alone (own 1 %)", r))
    rows.append(stack_row("each layer at its own 1 %, union", R["each_layer_at_own_1pct_union"]))
    out.append(md(["configuration", "FA"] + [SHORT[a] for a in PHYS + CMP], rows))
    out.append("\n## Does each layer earn its place? (largest detection loss when removed, rule: >= 3 points)\n")
    out.append(md(["layer", "largest loss", "on", "earns"], [[LNAME[c], pc(v["largest_loss_when_removed"]), SHORT[v["attack"]], v["earns_place"]] for c, v in R["earns_place"].items()]))
    out.append("\n## Combiners and budgets\n")
    rows = [stack_row(f"{h['method']} 1 % (chosen)", h)] + [stack_row(f"{m} 1 %", r) for m, r in R["other_combiners"].items()]
    rows += [stack_row(f"{h['method']} total {float(b) * 100:.0f} %", r) for b, r in R["budgets"].items()]
    out.append(md(["configuration", "FA"] + [SHORT[a] for a in PHYS + CMP], rows))
    out.append("\n## Dilution: stack versus the best single layer per attack (that layer at its own 1 %)\n")
    out.append(md(["attack", "best layer", "layer alone", "stack", "loss"], [[SHORT[a], LNAME[v["best_layer"]], pc(v["best_layer_alone"]), pc(v["stack"]), pc(v["loss"])] for a, v in R["dilution"].items()]))
    if R.get("optional"):
        out.append("\n## Optional rows (never headline)\n")
        out.append(md(["configuration", "FA"] + [SHORT[a] for a in PHYS + CMP], [stack_row(n, r) for n, r in R["optional"].items()]))
    if "dominant_layer_of_alarms" in h:
        out.append("\n## Which layer carries the alarms of the stack (count of alarmed scans by dominant layer)\n")
        cols = h["cols"]
        out.append(md(["attack"] + [LNAME[c] for c in cols], [[SHORT[a]] + [v[c] for c in cols] for a, v in h["dominant_layer_of_alarms"].items()]))
    for tag, title in (("ep", "sensor-fixed"), ("epw", "world-fixed")):
        if tag not in R["episodes"]:
            continue
        e = R["episodes"][tag]
        out.append(f"\n## Persistent {title} episodes (3 s rule; false-episode rate stack {pc(e['stack']['false_episode_rate'])} % of {e['stack']['n_clean_windows']} clean windows)\n")
        rows = []
        for name, blk in [("stack", e["stack"])] + [(LNAME[c], b) for c, b in e["layers"].items()] + list(e.get("optional", {}).items()):
            for k, v in sorted(blk["kinds"].items()):
                rows.append([name, k, f"{v['detected_3s']}/{v['episodes']}", f"[{pc(v['ci95_exact'][0], 0)}, {pc(v['ci95_exact'][1], 0)}]",
                             "-" if v["median_first_alert_s"] is None else f"{v['median_first_alert_s']:.2f}", pc(v["onset_scan_alarm"]), pc(v["sustained_scan_alarm"]), pc(blk["false_episode_rate"])])
        out.append(md(["detector", "kind", "detected", "exact 95 % CI", "median first alert (s)", "onset scan", "sustained scan", "false-episode rate"], rows))
    if "v2_side_by_side" in R:
        v = R["v2_side_by_side"]
        out.append(f"\n## v2 model (retrained v2 descriptor, box-cloud class) on the same single-return attacks, threshold val 1 % (test FA {pc(v['fa_test'], 2)} %)\n")
        out.append(md(["attack", "v2 detection", "95 % CI", "v2 AUC", "v3 stack detection", "v3 AUC"],
                      [[SHORT[a], pc(d["det"]), f"[{pc(d['ci95'][0])}, {pc(d['ci95'][1])}]", f"{v['auc'][a]:.3f}", pc(h["det"][a]["det"]), f"{h['auc'][a]:.3f}"] for a, d in v["det"].items() if a in h["det"]]))
        out.append(f"\nPooled AUC over the six single-return attacks: v2 {v['auc_pooled_single_return_set']:.3f}, v3 stack {R['v3_auc_pooled_single_return_set']:.3f}.\n")
    (RES / ("S9_tables.md" if src == "final" else "dry_tables.md")).write_text("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "final")
