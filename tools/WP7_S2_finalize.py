"""WP7 S2 finalize: post-processing of results/WP7/S2_results.json (written by tools/WP7_S2_report.py, whose bootstrap took 35 min and is not repeated).
(1) B5 blame with EQUAL WEIGHT PER ATTACK TYPE (the S5b composites had the same count per family, so its pooled blame was type-weighted; here V2X episodes are 80% of the composites, so the pooled
number is shown next to it); (2) corrected real-time ratios (compute seconds per stream second: total compute of the pass / stream seconds of the pass; the report script divided by the number of
calls for the cross pass); a quiet-machine LiDAR figure from the live run (bus delay of the LiDAR runner while only the simulation was running); (3) per-domain keeps-up statement;
(4) acceptance JSON rewritten from the corrected numbers, S2_tables.md extended. No composite is re-run.   Usage: python -u -W ignore tools/WP7_S2_finalize.py
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import WP7_S2_lib as L
import WP7_S2_report as R

import numpy as np

OUT = L.OUT


def main():
    res = json.loads((OUT / "S2_results.json").read_text())
    att = L.load_pickle("S2_sim_attacks.pkl")
    # ---- (1) blame, equal weight per type
    for fam in ("K", "C"):
        single = [r for r in att if r["family"] == fam and r["scenario"] in R.SINGLE_SCEN and r["type"] not in R.COORD[fam]]
        by = defaultdict(list)
        for r in single:
            if r["detected"]:
                by[(r["scenario"], r["type"])].append(r["blame"])
        w = {k: np.mean([np.mean([b == k for b in v]) for v in by.values()]) for k in ("correct", "wrong", "undecided")}
        res["aggregate"][fam]["blame_single_type_weighted"] = {**{k: float(x) for k, x in w.items()}, "types_with_detections": len(by)}
        dom = defaultdict(list)
        for (scen, t), v in by.items():
            dom[scen].append([np.mean([b == k for b in v]) for k in ("correct", "wrong", "undecided")])
        res["aggregate"][fam]["blame_type_weighted_by_scenario"] = {s: dict(zip(("correct", "wrong", "undecided"), map(float, np.mean(x, axis=0)))) for s, x in dom.items()}
        # the share of V2X episodes in the pooled number
        res["aggregate"][fam]["share_v2x_of_single_composites"] = float(np.mean([r["scenario"] == "v2x_episode" for r in single]))
    # ---- (2) timing
    t = res["timing"]
    t["gps"]["ratio_compute_per_stream_s"] = t["gps"]["total_s"] / t["gps"]["stream_s"]
    vk = L.load_pickle("S2_veh_K.pkl")["latency"]
    steps = int(np.sum(np.array(vk["cross"]["emit"]) > 0))
    t["cross_kitti"]["stream_s"] = float(steps)
    t["cross_kitti"]["ratio_compute_per_stream_s"] = t["cross_kitti"]["total_s"] / steps
    t["cross_comma_residual"]["ratio_compute_per_stream_s"] = t["cross_comma_residual"]["total_s"] / t["cross_comma_residual"]["stream_s"]
    t["can_window"]["ratio_compute_per_stream_s"] = t["can_window"]["total_s"] / t["can_window"]["stream_s"]
    t["lidar_scan"]["ratio_compute_per_stream_s"] = t["lidar_scan"]["median_ms"] / 1000.0 / t["lidar_scan"]["period_s"]
    live = json.loads((OUT / "S2_live.json").read_text())
    lq = [c["bus_delay_ms"]["lidar.runner"]["median"] for c in live["composites"] if "lidar.runner" in c["bus_delay_ms"]]
    t["lidar_scan_live_lightly_loaded"] = {"median_ms_per_scan": float(np.median(lq)), "ratio": float(np.median(lq) / 1000.0 / 0.1032), "n_composites": len(lq),
                                           "note": "live runs, only the S2 simulation running beside it; the pass numbers above come from the 13-process load of the passes"}
    for k, v in t.items():
        if isinstance(v, dict) and "ratio_compute_per_stream_s" in v and "period_s" in v:
            v["keeps_up_amortised"] = bool(v["ratio_compute_per_stream_s"] <= 1.0)
    t["keeps_up_summary"] = {
        "gps": "yes (compute per fix far below the 1 s period)", "cross": "yes", "can_frame": "yes", "can_window": "yes on average, NO on long captures: the prefix re-score makes the window cost grow with the capture "
        "(median 0.14 s below 100k frames, 2.3 s above 600k frames, period 1 s)", "v2x": "NO for the whole-block stream of all senders (1.9 compute seconds per stream second on the loaded machine, 25 ms mean "
        "inter-arrival); the heard set of one ego is a small fraction of it (see v2x_heard_rate)", "network": "yes on average (flow pushes), with a stall of 1.4 s median / 7.7 s max at every bin close "
        "(whole-buffer re-score); the Evidence delay is 66 s median, 242 s max (bin + minute hold)", "lidar": "NO: about 1.8 s per scan against a 0.103 s period (about 18x too slow on one core, 39x under the pass load)"}
    # ---- V2X heard rate (messages heard by one ego per second)
    cnt = []
    for f in sorted(L.CACHE.glob("S2_v2x_p*.pkl")):
        for s in L.load_pickle(f.name)["series"]:
            if s["kind"] == "clean":
                cnt.append(s["count"].mean())
    t["v2x_heard_rate"] = {"mean_messages_per_second_heard_by_one_ego": float(np.mean(cnt)), "p95": float(np.percentile(cnt, 95)), "egos": len(cnt)}
    # ---- (4) acceptance
    acc = json.loads((OUT / "S2_acceptance.json").read_text())
    K = res["aggregate"]["K"]
    bw = K["blame_single_type_weighted"]
    acc["B5_blame"] = {"rule": "K blame of detected single-domain events, equal weight per attack type: correct >= 75% and wrong <= 10% (the pooled value is dominated by V2X episodes and is reported next to it)",
                       "met": bool(bw["correct"] >= 0.75 and bw["wrong"] <= 0.10), "correct": bw["correct"], "wrong": bw["wrong"], "undecided": bw["undecided"],
                       "pooled_correct": K["blame_single_pooled"]["correct"], "pooled_wrong": K["blame_single_pooled"]["wrong"]}
    acc["A4_timing"].update(lidar_median_ms=t["lidar_scan"]["median_ms"], lidar_ratio_loaded=t["lidar_scan"]["median_ms"] / 1000 / 0.1032, lidar_ratio_light=t["lidar_scan_live_lightly_loaded"]["ratio"],
                            v2x_ratio=t["v2x_message"]["ratio_compute_per_stream_s"], gps_ratio=t["gps"]["ratio_compute_per_stream_s"])
    acc["A4_timing"].pop("lidar_ratio", None)
    acc["M3_verdict"] = {"rule": "M3 = MET only if A1-A5 and B1-B7 all hold", "met": all(v["met"] for k, v in acc.items() if k != "M3_verdict"),
                         "rows_met": int(sum(v["met"] for k, v in acc.items() if k != "M3_verdict")), "rows": len(acc) - 1}
    (OUT / "S2_results.json").write_text(json.dumps(res, indent=1, default=float))
    (OUT / "S2_acceptance.json").write_text(json.dumps(acc, indent=1, default=float))
    # ---- tables
    lines = (OUT / "S2_tables.md").read_text().split("\n## 3 Timing")[0].rstrip().split("\n")
    f1 = lambda x: "-" if x is None else f"{100 * x:.1f}%"
    lines += ["", "## 3 Detection by attacked domain (equal weight per type), first-alarm delay and available delay (seconds from the true attack start)", "",
              "| family | attacked domain | types | event detection | delay ticks (median) | available delay s (median) |", "|---|---|---|---|---|---|"]
    for fam in ("K", "C"):
        for d, v in res["aggregate"][fam]["by_attacked_domain"].items():
            lines.append(f"| {fam} | {d} | {v['types']} | {f1(v['event_detection'])} | {v['delay_tick_median']['median'] if v['delay_tick_median'] else '-'} | "
                         f"{v['delay_available_median']['median'] if v['delay_available_median'] else '-'} |")
    lines += ["", "## 4 Coordinated and multi-domain scenarios", "", "| family | scenario | n | event detection | blame | worst response | worst response, variant |", "|---|---|---|---|---|---|---|"]
    for fam in ("K", "C"):
        agg = defaultdict(lambda: [0, 0, Counter(), Counter(), Counter()])
        for k, v in res["aggregate"][fam]["coordinated"].items():
            sc = k.split("|")[0]
            a = agg[sc]
            a[0] += v["n"]
            a[1] += v["n"] * v["event_detection"]
            a[2].update(v["blame"]), a[3].update(v["response_max"]), a[4].update(v["response_max_variant"])
        for sc, a in agg.items():
            lines.append(f"| {fam} | {sc} | {a[0]} | {f1(a[1] / a[0])} | {dict(a[2])} | {dict(a[3])} | {dict(a[4])} |")
    lines += ["", "## 5 Timing (this shared machine; pass load = 13 processes)", "", "| stream | period s | n | median ms | p95 ms | p99 ms | max ms | compute s per stream s | keeps up (amortised) | p99 < period |", "|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in t.items():
        if isinstance(v, dict) and "median_ms" in v and "period_s" in v:
            lines.append(f"| {k} | {v['period_s']:.4g} | {v['n']} | {v['median_ms']:.3f} | {v['p95_ms']:.3f} | {v['p99_ms']:.3f} | {v['max_ms']:.1f} | {v.get('ratio_compute_per_stream_s', float('nan')):.4g} | "
                         f"{v.get('keeps_up_amortised', '-')} | {v.get('keeps_up_p99_per_sample', '-')} |")
    lines += ["", "CAN window cost by context size (frames already in the capture): " + json.dumps(t["can_window_by_context_frames"]), "", "Network Evidence delay (s of stream time from the flow to its visible tick): " + json.dumps(t["network_evidence_delay_s"]),
              "", "LiDAR quiet-machine figure: " + json.dumps(t["lidar_scan_live_lightly_loaded"]), "", "V2X heard rate: " + json.dumps(t["v2x_heard_rate"]), "", "Keeps up: " + json.dumps(t["keeps_up_summary"], indent=1)]
    lines += ["", "## 6 Live co-simulation (A3)", "", "| id | what | equal | events | alarm ticks | bus delay median ms per runner |", "|---|---|---|---|---|---|"]
    for c in live["composites"]:
        lines.append(f"| {c['id']} | {c['what'][:60]} | {c['equal']} | {c['events']} | {c['alarm_ticks']} | {json.dumps({k: round(v['median'], 1) for k, v in c['bus_delay_ms'].items()})} |")
    (OUT / "S2_tables.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({k: (v["met"]) for k, v in acc.items()}))
    print("blame type-weighted K", bw, "C", res["aggregate"]["C"]["blame_single_type_weighted"])
    print(json.dumps(t["keeps_up_summary"], indent=1)[:200])
    for k in ("gps", "cross_kitti", "can_window", "v2x_message", "network_flow_push", "lidar_scan"):
        print(k, round(t[k]["ratio_compute_per_stream_s"], 3))
    print(t["lidar_scan_live_lightly_loaded"], t["v2x_heard_rate"])


if __name__ == "__main__":
    main()
