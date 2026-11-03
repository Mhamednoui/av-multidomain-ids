"""WP8 S6: markdown table of one evaluation JSON (results/WP8/S6/<tag>_eval.json) for the notes and the report. Usage: python -I tools/WP8_S6_table.py <tag>"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pc(x):
    return "-" if x is None else f"{100 * x:.0f}"


def ci(c, i):
    return "-" if not c else f"[{100 * c[0][i]:.0f}, {100 * c[1][i]:.0f}]"


def table(tag):
    d = json.loads((ROOT / "results" / "WP8" / "S6" / f"{tag}_eval.json").read_text())
    L = [f"Evaluation {tag} (V31_val, vehicle block; K runs {d['runs']['K']}, C runs {d['runs']['C']}); blame of detected events, % correct / wrong / undecided; 95 % CI over drives / routes in brackets", ""]
    L.append("| row | " + " | ".join(d["candidates_K"]) + " |")
    L.append("|---|" + "---|" * len(d["candidates_K"]))
    for c in d["candidates_K"]:
        pass
    g = {c: d["K"][c]["types"]["gps_can"] for c in d["candidates_K"]}
    L.append("| B1 K gps_can correct / wrong / undec (detected " + str(g["V3"]["detected"]) + " of " + str(g["V3"]["runs"]) + ") | " + " | ".join(
        f"{pc(g[c]['correct'])} {ci(d['K'][c]['ci']['gps_can_correct_wrong'], 0)} / {pc(g[c]['wrong'])} {ci(d['K'][c]['ci']['gps_can_correct_wrong'], 1)} / {pc(g[c]['undecided'])}" for c in d["candidates_K"]) + " |")
    L.append("| B3 K 10 vehicle types, mean correct / wrong | " + " | ".join(
        f"{pc(d['K'][c]['B3']['correct'])} {ci(d['K'][c]['ci']['B3_correct_wrong'], 0)} / {pc(d['K'][c]['B3']['wrong'])} {ci(d['K'][c]['ci']['B3_correct_wrong'], 1)}" for c in d["candidates_K"]) + " |")
    for t in ["drift", "accel_drift", "doppler_spoof", "meaconing", "lidar_scale", "lidar_bias", "lidar_yaw", "can_scale", "can_offset", "can_freeze"]:
        L.append(f"| K {t} (det {d['K']['V3']['types'][t]['detected']}) | " + " | ".join(
            f"{pc(d['K'][c]['types'][t]['correct'])} / {pc(d['K'][c]['types'][t]['wrong'])} / {pc(d['K'][c]['types'][t]['undecided'])}" for c in d["candidates_K"]) + " |")
    L.append("")
    cc = d["candidates_C"]
    L.append("| row (comma) | " + " | ".join(cc) + " |")
    L.append("|---|" + "---|" * len(cc))
    L.append("| B2 GNSS drift / meaconing / doppler mean correct / wrong | " + " | ".join(
        f"{pc(d['C'][c]['B2']['correct'])} {ci(d['C'][c]['ci']['B2_correct_wrong'], 0)} / {pc(d['C'][c]['B2']['wrong'])} {ci(d['C'][c]['ci']['B2_correct_wrong'], 1)}" for c in cc) + " |")
    for t in ["drift", "accel_drift", "doppler_spoof", "meaconing", "can_scale", "can_offset", "can_freeze", "can_bus", "gnss_can"]:
        L.append(f"| C {t} (det {d['C']['V3']['types'][t]['detected']} of {d['C']['V3']['types'][t]['runs']}) | " + " | ".join(
            f"{pc(d['C'][c]['types'][t]['correct'])} / {pc(d['C'][c]['types'][t]['wrong'])} / {pc(d['C'][c]['types'][t]['undecided'])}" for c in cc) + " |")
    L.append("| C3 CAN types + gnss_can mean correct | " + " | ".join(pc(d["C"][c]["C3"]["correct"]) for c in cc) + " |")
    L.append("")
    L.append("Rules met (B1 B2 B3 C3 B4): " + "; ".join(f"{c}: " + " ".join(f"{k}={'Y' if v else 'n'}" for k, v in d["rules"][c].items() if k != "n_met") for c in d["candidates_K"]))
    return "\n".join(L)


if __name__ == "__main__":
    print(table(sys.argv[1]))
