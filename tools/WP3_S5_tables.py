"""WP3 S5: markdown tables from results/WP3/S5/final.json -> results/WP3/S5/S5_tables.md."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS

RES = RESULTS / "WP3" / "S5"
SRC = sys.argv[1] if len(sys.argv) > 1 else "final.json"
f = json.loads((RES / SRC).read_text())
L = [f"# S5 tables (final.json), variant (margin, gap, strict) = {f['variant']}", "",
     f"Clean test FA {100 * f['fa_test']:.2f} % (pooled train+val FA {100 * f['fa_pooled_trval']:.2f} %). Per test drive: "
     + ", ".join(f"{d} {100 * v:.1f}" for d, v in f["fa_test_per_drive"].items()),
     "Nested LODO FA (threshold from the other 15 drives, held-out drive): " + ", ".join(f"{d} {100 * v:.1f}" for d, v in f["nested_lodo_fa_trval"].items()), "",
     "## Scan-level detection (%) at the 1 % LODO operating point", "", "| attack | n | union | tot | maxf | cnt | maxn |", "|---|---|---|---|---|---|---|"]
for a, r in f["attacks"].items():
    L.append(f"| {a} | {r['n']} | {100 * r['union']:.1f} | " + " | ".join(f"{100 * r[s]:.1f}" for s in ("tot", "maxf", "cnt", "maxn")) + " |")
L += ["", "## Tile level (phantom tiles = >= 50 % injected returns; threshold = clean-scan 99th percentile of the max tile fraction "
      f"{f['tile_level']['fraction_threshold']:.2f})", "", "| attack | phantom tiles | scans with a phantom tile | tile detection % | scans with a caught phantom tile % |", "|---|---|---|---|---|"]
for a, r in f["tile_level"].items():
    if a == "fraction_threshold":
        continue
    td = "-" if r["tile_detection"] is None else f"{100 * r['tile_detection']:.2f}"
    L.append(f"| {a} | {r['n_phantom_tiles']} | {r['scans_with_phantom_tile']}/{r['n_scans']} | {td} | {100 * r['scans_with_caught_phantom_tile']:.1f} |")
e = f["episodes"]
L += ["", f"## Persistent episodes (30 scans, alarm within 3 s; stat threshold {e['stat_threshold']:.3f}; false-episode rate on clean test windows "
      f"{100 * e['false_episode_rate_test_clean']:.1f} % of {e['n_clean_windows']})", "", "| kind | episodes | detected in 3 s | median delay s | single-scan alarm rate % |", "|---|---|---|---|---|"]
for k, r in e["kinds"].items():
    md = "-" if r["median_delay_s_of_alarmed"] is None else f"{r['median_delay_s_of_alarmed']:.2f}"
    L.append(f"| {k} | {r['episodes']} | {r['detected_3s']} | {md} | {100 * r['single_scan_alarm_rate']:.1f} |")
for tag, h in f["harness"].items():
    L += ["", f"## Harness {tag} (detection % by attack at the system 1 % budget)", "", "| layers | FA % | " + " | ".join(sorted(next(iter(h['ablation'].values()))['detection_by_attack'])) + " |"]
    ks = sorted(next(iter(h['ablation'].values()))['detection_by_attack'])
    L.append("|" + "---|" * (len(ks) + 2))
    for name, r in h["ablation"].items():
        L.append(f"| {name} | {100 * r['false_alarm_rate']:.2f} | " + " | ".join(f"{100 * r['detection_by_attack'][k]:.1f}" for k in ks) + " |")
(RES / ("S5_tables.md" if SRC == "final.json" else "dry_tables.md")).write_text("\n".join(L) + "\n")
print("\n".join(L)[:1500])
