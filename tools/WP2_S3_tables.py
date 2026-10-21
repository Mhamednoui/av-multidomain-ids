"""WP2 S3: markdown tables from results/WP2/s3_*.json -> results/WP2/s3_tables.md (no hand-typed numbers)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS

OUT = RESULTS / "WP2"
SK = "can.l2a_skew"
f = lambda x: "-" if x is None else f"{x:.3f}"
L = []


def road_block(title, path):
    d = json.load(open(path))
    L.append(f"## {title}\nskew variant {d['skew_variant_selection']['variants'][str(d['skew_variant_selection']['chosen'])]['variant']}, selected on {d['skew_variant_selection']['selected_on']}\n")
    for rn, r in d["regimes"].items():
        L.append(f"### regime {rn}: summary on test windows\n| layer | FA clean | FA/h | attack-window recall |\n|---|---|---|---|")
        for n, s in r["summary"].items():
            L.append(f"| {n} | {f(s['fa_clean_rate'])} | {s['false_alerts_per_hour_clean']:.0f} | {f(s['attack_window_recall'])} |")
        L.append(f"\n### regime {rn}: per capture (window recall / delay s)\n| capture | attack windows | L2a | L1 comb | L1+L2a comb |\n|---|---|---|---|---|")
        for g, x in r["per_capture"].items():
            if not x["attack_windows"]:
                continue
            c = lambda k: f"{f(x['layers'][k]['recall'])} / {f(x['layers'][k]['delay_s'])}"
            L.append(f"| {g} | {x['attack_windows']} | {c(SK)} | {c('combined_l1')} | {c('combined_l1_l2a')} |")
        h = r["harness"]
        L.append(f"\n### regime {rn}: harness ablation (AUC / detection / FA)\n| config | AUC | det | FA |\n|---|---|---|---|")
        for k, x in h["ablation"].items():
            L.append(f"| {k} | {x['auc']:.3f} | {x['detection']:.3f} | {x['false_alarm_rate']:.4f} |")
        L.append("")


road_block("ROAD run 2b (revised design, final)", OUT / "s3_road.json")
road_block("ROAD run 1 (pre-registered design, verdict)", OUT / "s3_run1_frozen" / "s3_road.json")
road_block("Car-Hacking", OUT / "s3_carhacking.json")
L.append("## D11 (window level): per set / subset / regime\n| set | sub | vehicle | regime | L2a FA clean | L2a recall | L1 comb FA | L1 comb recall | L1+L2a FA | L1+L2a recall | detected files (L1 / L1+L2a) |\n|---|---|---|---|---|---|---|---|---|---|---|")
for s in ("01", "02", "03", "04"):
    p = OUT / f"s3_d11_set_{s}.json"
    if not p.exists():
        continue
    d = json.load(open(p))
    for sub, info in d["subsets"].items():
        for rn, r in info["regimes"].items():
            sm = r["summary"]
            pc = r["per_capture"]
            det = lambda k: f"{sum(1 for x in pc.values() if x['layers'][k]['detected'])}/{sum(1 for x in pc.values() if x['layers'][k]['detected'] is not None)}"
            L.append(f"| {s} | {sub} | {'/'.join(info['vehicle'])} | {rn} | {f(sm[SK]['fa_clean_rate'])} | {f(sm[SK]['attack_window_recall'])} | "
                     f"{f(sm['combined_l1']['fa_clean_rate'])} | {f(sm['combined_l1']['attack_window_recall'])} | "
                     f"{f(sm['combined_l1_l2a']['fa_clean_rate'])} | {f(sm['combined_l1_l2a']['attack_window_recall'])} | {det('combined_l1')} / {det('combined_l1_l2a')} |")
(OUT / "s3_tables.md").write_text("\n".join(L) + "\n")
print("ok")
