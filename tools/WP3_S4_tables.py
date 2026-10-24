"""WP3 S4: markdown tables from results/WP3/S4/final.json (no hand-typed numbers) -> results/WP3/S4/S4_tables.md."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS

RES = RESULTS / "WP3" / "S4"
f = json.loads((RES / "final.json").read_text())
pc = lambda x: "-" if x is None else f"{100 * x:.1f}"
L = [f"# WP3 S4 tables (final.json). nmin = {f['nmin']}, primary threshold = {f['primary']}; budget 1 % of clean validation scans\n"]
for mode in ("lodo", "val_only"):
    r = f[mode]
    L += [f"## Mode {mode}{' (PRIMARY)' if mode == f['primary'] else ''}: clean test FA {pc(r['fa_test'])} %, scoring {r['scoring_ms_per_scan']:.0f} ms/scan\n",
          "Per-drive FA (%): " + ", ".join(f"{d} {pc(v)}" for d, v in r["fa_test_per_drive"].items()) + "\n",
          "Single-stat FA (%): " + ", ".join(f"{k} {pc(v)}" for k, v in r["parts_fa"].items()) + "\n",
          "### Scan-level detection (%)\n", "| attack | n | union | " + " | ".join(r["parts_fa"]) + " |", "|---|---|---|" + "---|" * len(r["parts_fa"])]
    for a, v in r["attacks"].items():
        L.append(f"| {a} | {v['n']} | {pc(v['union'])} | " + " | ".join(pc(v[p]) for p in r["parts_fa"]) + " |")
    L += ["\n### Tile level (phantom tiles = tiles with >= 50 % injected returns)\n",
          "| attack | scans | with phantom tile | phantom tiles | tile detection % | scans with caught phantom tile % |", "|---|---|---|---|---|---|"]
    for a, v in r["object_level"].items():
        L.append(f"| {a} | {v['n_scans']} | {v['scans_with_phantom_tile']} | {v['n_phantom_tiles']} | {pc(v['tile_detection'])} | {pc(v['scan_with_phantom_tile_caught'])} |")
    e = r["episodes"]
    L += [f"\n### Persistent episodes (30 scans, rolling log-odds W=10, stat threshold {e['stat_threshold']:.3f}); false-episode rate on {e['n_clean_windows']} clean test windows: {pc(e['false_episode_rate_test_clean'])} %\n",
          "| kind | episodes | detected in 3 s | median delay of alarmed (s) | single-scan alarm % |", "|---|---|---|---|---|"]
    for k, v in e["kinds"].items():
        d = v["median_delay_s_of_alarmed"]
        L.append(f"| {k} | {v['episodes']} | {v['detected_3s']} | {'-' if d is None else f'{d:.2f}'} | {pc(v['single_scan_alarm_rate'])} |")
    L.append("")
for tag in ("harness_L1_L2a", "harness_L1_dens_int"):
    L += [f"## Harness ablation {tag} (val-only L2a model; test FA and detection in %)\n", (RES / f"{tag}.md").read_text()]
(RES / "S4_tables.md").write_text("\n".join(L))
print("\n".join(L)[:3000])
