"""WP3 S6: markdown tables from results/WP3/S6/final.json -> results/WP3/S6/S6_tables.md."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.config import RESULTS

RES = RESULTS / "WP3" / "S6"
ATT = ["ph_replace_near", "ph_replace_far", "ph_budget_near", "ph_budget_far", "PointDrop", "IntensitySpoof", "cmp_boxcloud", "cmp_mradd_near",
       "cmp_mradd_far"]
p = lambda x: "-" if x is None else f"{100 * x:.1f}"  # noqa


def main():
    f = json.loads((RES / "final.json").read_text())
    L = []
    L.append("## Scan level (onset: attacked scan vs clean previous scan), test, % of attacked scans\n")
    L.append("| layer | stats | FA test | worst drive FA | LODO FA mean / max (16 train+val) | " + " | ".join(ATT) + " |")
    L.append("|" + "---|" * (5 + len(ATT)))
    for lid, r in f["layers"].items():
        L.append(f"| {lid} | {', '.join(r['stats'])} | {p(r['fa_test'])} | {p(max(r['fa_test_per_drive'].values()))} | "
                 f"{p(sum(r['lodo_fa_trainval'].values()) / len(r['lodo_fa_trainval']))} / {p(max(r['lodo_fa_trainval'].values()))} | "
                 + " | ".join(p(r["attacks"][a]) for a in ATT) + " |")
    for lid, r in f["layers"].items():
        L.append(f"\nPer-drive test FA {lid} (%): " + ", ".join(f"{d} {p(v)}" for d, v in r["fa_test_per_drive"].items()))
        L.append(f"\nLODO FA per train+val drive {lid} (%): " + ", ".join(f"{d} {p(v)}" for d, v in r["lodo_fa_trainval"].items()))
        L.append(f"\nSingle statistics {lid} (test): FA / detection\n")
        L.append("| stat | FA | " + " | ".join(ATT) + " |")
        L.append("|" + "---|" * (2 + len(ATT)))
        for s in r["stats"]:
            L.append(f"| {s} | {p(r['parts_fa'][s])} | " + " | ".join(p(r["parts_det"][s][a]) for a in ATT) + " |")
    L.append("\n## Persistent episodes (30 scans, 3 per drive and kind = 21), test\n")
    for lid, r in f["layers"].items():
        e = r["episodes"]
        L.append(f"\n{lid}: false-episode rate on {e['n_clean_windows']} clean test windows {p(e['false_episode_rate_test_clean'])} %\n")
        L.append("| group | kind | episodes | detected in 3 s | median delay (s) | onset scan alarm % | sustained scan alarm % |")
        L.append("|---|---|---|---|---|---|---|")
        for tag in ("sensor_fixed", "sensor_fixed_ego_moving", "sensor_fixed_ego_slow", "world_fixed", "world_fixed_ego_moving", "world_fixed_ego_slow"):
            for k, v in e[tag].items():
                md = "-" if v["median_delay_s"] is None else f"{v['median_delay_s']:.2f}"
                L.append(f"| {tag} | {k} | {v['episodes']} | {v['detected_3s']} | {md} | {p(v['onset_scan'])} | {p(v['sustained_scan'])} |")
    for h in ("harness_L1_L2a_int", "harness_full"):
        d = f[h]
        atts = sorted({a for r in d["ablation"].values() for a in r["detection_by_attack"]})
        L.append(f"\n## {h} (budget 1 % on validation normals; combiner noisy_or)\n")
        L.append("| configuration | AUC | FA test % | " + " | ".join(atts) + " |")
        L.append("|" + "---|" * (3 + len(atts)))
        for k, r in d["ablation"].items():
            L.append(f"| {k} | {r['auc']:.3f} | {p(r['false_alarm_rate'])} | " + " | ".join(p(r["detection_by_attack"].get(a)) for a in atts) + " |")
    L.append(f"\nScoring cost: {f['scoring_ms_per_scan']:.0f} ms per clean scan (L2c + L2d, image build included)")
    (RES / "S6_tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
